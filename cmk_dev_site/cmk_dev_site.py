"""cmk-dev-site

Set up sites based on the specified OMD version
Defaults to the current OMD version if version is not provided.
If a site with the same name and version already exists, it skips recreation and base
configuration, proceeding with the next steps. Use the -f option to force a full setup.
"""

import argparse
import difflib
import getpass
import json
import logging
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import (
    Any,
    NotRequired,
    Self,
    TypedDict,
)

import requests
from requests.exceptions import JSONDecodeError

from omd import BaseVersion, CMKPackage, Edition, VersionWithPatch, VersionWithReleaseDate
from utils.log import colorize, generate_log_decorator, get_logger

from .version import __version__

logger = get_logger(__name__)
log = generate_log_decorator(logger)

GUI_USER = "cmkadmin"
GUI_PW = "cmk"
INSTALLATION_PATH = Path("/omd/versions")


class Language(StrEnum):
    EN = "en"
    DE = "de"
    RO = "ro"


class BasicSettings(TypedDict):
    alias: str
    site_id: str
    customer: NotRequired[str]


class ConnectionDetails(TypedDict):
    socket_type: str
    host: str
    port: int
    encrypted: bool
    verify: bool


class StatusHost(TypedDict):
    status_host_set: str


class StatusConnection(TypedDict):
    connection: ConnectionDetails
    proxy: dict[str, str]
    connect_timeout: int
    persistent_connection: bool
    url_prefix: str
    status_host: StatusHost
    disable_in_status_gui: bool


class UserSync(TypedDict):
    sync_with_ldap_connections: str


class ConfigurationConnection(TypedDict):
    enable_replication: bool
    url_of_remote_site: str
    disable_remote_configuration: bool
    ignore_tls_errors: bool
    direct_login_to_web_gui_allowed: bool
    user_sync: UserSync
    replicate_event_console: bool
    replicate_extensions: bool
    message_broker_port: NotRequired[int]


class RemoteSiteConnectionConfig(TypedDict):
    basic_settings: BasicSettings
    status_connection: StatusConnection
    configuration_connection: ConfigurationConnection


@dataclass
class PartialCMKPackage:
    version: str

    def similarity(self, other: str) -> float:
        return difflib.SequenceMatcher(None, self.version, other).ratio()


def _prefix_log_site(self: "Site", *args: Any, **kwargs: Any) -> str:
    return f"[{colorize(self.name, 'blue')}]: "


class Site:
    def __init__(
        self,
        site_name: str,
        cmk_pkg: CMKPackage,
        *,
        is_remote: bool = False,
    ):
        self.name = site_name
        self.cmk_pkg = cmk_pkg
        self._is_remote = is_remote

    def __repr__(self):
        return (
            f"<Site name={self.name} cmk_pkg={self.cmk_pkg} is_remote_site={self.is_remote_site}>"
        )

    @property
    def is_remote_site(self):
        return self._is_remote

    @log(prefix=_prefix_log_site)
    def create_site(self) -> None:
        try:
            subprocess.run(
                [
                    "sudo",
                    "omd",
                    "-V",
                    self.cmk_pkg.omd_version,
                    "create",
                    "--apache-reload",
                    "--no-autostart",
                    self.name,
                ],
                check=True,
                capture_output=True,
            )

            # Setting the password for user
            hashalgo = "-m" if self.cmk_pkg.base_version == "2.1.0" else "-B"

            subprocess.run(
                [
                    "sudo",
                    "htpasswd",
                    "-b",
                    hashalgo,
                    f"/omd/sites/{self.name}/etc/htpasswd",
                    GUI_USER,
                    GUI_PW,
                ],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"[{self.name}]: Failed to create the site: {e}") from e

    @log(prefix=_prefix_log_site)
    def delete_site(self) -> None:
        """Delete the site if it already exists."""
        if Path("/omd/sites", self.name).exists():
            subprocess.run(
                [
                    "sudo",
                    "omd",
                    "-f",
                    "rm",
                    "--kill",
                    "--apache-reload",
                    self.name,
                ],
                check=True,
                capture_output=True,
            )

    @log(prefix=_prefix_log_site)
    def configure_site(self) -> None:
        try:
            if self.cmk_pkg.base_version == "2.1.0":
                omd_config_set(self.name, "MKEVENTD", "on")

            # TODO: EC_SYSLOG is should be taken care of in the future if this would be default
            omd_config_set(self.name, "LIVESTATUS_TCP", "on")

        except RuntimeError as e:
            logger.warning(
                "[%s]: Failed to configure the site. %s",
                colorize(self.name, "yellow"),
                e,
            )

    @log(prefix=_prefix_log_site)
    def start_site(self, api: "APIClient") -> None:
        try:
            subprocess.run(["sudo", "omd", "start", self.name], check=True)
        except subprocess.CalledProcessError as e:
            logger.warning(
                "[%s]: Failed to start the site. Site probably is running (err: %s)",
                colorize(self.name, "yellow"),
                e.stderr,
            )
        logger.debug("Make sure API is available..")
        while api.version() is None:
            logger.debug("Waiting for API to be available")
            time.sleep(1)
        logger.debug("API is available!")

    @log(prefix=_prefix_log_site)
    def trigger_site_checking_cycle(self) -> None:
        try:
            subprocess.run(
                ["sudo", "su", "-", self.name, "-c", f"cmk -n '{self.name}'"],
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning(
                "[%s]: Failed to trigger the site checking cycle. %s",
                colorize(self.name, "yellow"),
                e.stderr,
            )

    @log(prefix=_prefix_log_site)
    def discover_services(self) -> None:
        try:
            subprocess.run(
                ["sudo", "su", "-", self.name, "-c", "cmk -vI ; cmk -O"],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            logger.warning(
                "[%s]: Failed to discover services. %s",
                colorize(self.name, "yellow"),
                e.stderr,
            )

    @log(prefix=_prefix_log_site, max_level=logging.DEBUG)
    def get_site_connection_config(
        self,
        http_address: str,
        livestatus_port: int,
        message_broker_port: int | None = None,
    ) -> RemoteSiteConnectionConfig:
        internal_url = f"http://{http_address}/{self.name}/check_mk/"
        config: RemoteSiteConnectionConfig = {
            "basic_settings": {
                "alias": f"The  {self.name}",
                "site_id": self.name,
            },
            "status_connection": {
                "connection": {
                    "socket_type": "tcp",
                    "host": http_address,
                    "port": livestatus_port,
                    "encrypted": True,
                    "verify": True,
                },
                "proxy": {
                    "use_livestatus_daemon": "direct",
                },
                "connect_timeout": 2,
                "persistent_connection": False,
                "url_prefix": f"/{self.name}/",
                "status_host": {"status_host_set": "disabled"},
                "disable_in_status_gui": False,
            },
            "configuration_connection": {
                "enable_replication": True,
                "url_of_remote_site": internal_url,
                "disable_remote_configuration": False,
                "ignore_tls_errors": False,
                "direct_login_to_web_gui_allowed": True,
                "user_sync": {"sync_with_ldap_connections": "disabled"},
                "replicate_event_console": True,
                "replicate_extensions": False,
            },
        }
        if message_broker_port:
            config["configuration_connection"]["message_broker_port"] = message_broker_port

        if self.cmk_pkg.edition == Edition.MANAGED:
            # required filed for managed edition
            config["basic_settings"]["customer"] = "provider"
        return config

    def _append_to_file(self, file_path: Path, content: str) -> None:
        logger.debug("Appending content to %s", file_path)
        try:
            with subprocess.Popen(
                ["sudo", "su", "-", self.name, "-c", f"tee -a {file_path}"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,  # Capture stderr for debugging
            ) as process:
                _, stderr = process.communicate(input=content.encode())

                if process.returncode != 0:
                    raise RuntimeError(
                        f"Failed to append to {file_path}. Error: {stderr.decode().strip()}"
                    )

        except (OSError, subprocess.SubprocessError) as e:
            raise RuntimeError(f"File append operation failed: {e!s}") from e
        except UnicodeEncodeError as e:
            raise RuntimeError("Invalid content encoding") from e

    @log(prefix=_prefix_log_site)
    def add_remote_site_certificate(self, remote_site_name: str) -> None:
        cert_path = Path("/omd/sites", remote_site_name, "etc", "ssl", "ca.pem")
        ca_certificates_path = Path(
            "/omd/sites",
            self.name,
            "etc/check_mk/multisite.d/wato/ca-certificates.mk",
        )
        ssl_certificates_path = Path("/omd/sites", self.name, "var/ssl/ca-certificates.crt")

        cmd = [
            "sudo",
            "openssl",
            "x509",
            "-inform",
            "PEM",
            "-in",
            str(cert_path),
            "-outform",
            "DER",
        ]

        try:
            # First subprocess call gets its own error context
            cert_der = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
            ).stdout
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to fetch DER certificate from {remote_site_name}") from e

        try:
            cert_pem = subprocess.run(
                ["openssl", "x509", "-inform", "DER", "-outform", "PEM"],
                input=cert_der,
                capture_output=True,
                check=True,
            ).stdout.decode("utf-8")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(
                f"Failed to convert certificate for {remote_site_name} to PEM format"
            ) from e

        # Append certificate to SSL trust store
        self._append_to_file(ssl_certificates_path, cert_pem)

        # Format certificate to be inserted as a single line
        cert_escaped = cert_pem.strip().replace("\n", "\\n")
        trust_entry = (
            "trusted_certificate_authorities.setdefault"
            f'("trusted_cas", []).append("{cert_escaped}")\n'
        )

        # Append certificate trust entry to configuration file
        self._append_to_file(ca_certificates_path, trust_entry)

    @log(prefix=_prefix_log_site)
    def register_host_with_agent(self, host_name: str, gui_user: str, gui_pw: str) -> None:
        cmk_agent_ctl_path = shutil.which("cmk-agent-ctl")
        if not cmk_agent_ctl_path:
            raise RuntimeError("cmk-agent-ctl not found. Please install the Checkmk agent.")

        try:
            subprocess.run(
                args=[
                    "sudo",
                    cmk_agent_ctl_path,
                    "-v",
                    "register",
                    "--hostname",
                    host_name,
                    "--server",
                    "127.0.0.1",
                    "--site",
                    self.name,
                    "--user",
                    gui_user,
                    "--password",
                    gui_pw,
                    "--trust-cert",
                ],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            raise RuntimeError("ERROR: Failed to register host with cmk-agent-ctl. ") from e


def checkmk_agent_needs_installing() -> bool:
    """Check if the Checkmk agent is installed."""
    cmk_agent_ctl_path = shutil.which("cmk-agent-ctl")
    if cmk_agent_ctl_path:
        return True
    # Check if port 6556 is open
    port_6556_open = (
        subprocess.run(["sudo", "netstat", "-tuln"], capture_output=True, text=True).stdout.find(
            ":6556 "
        )
        != -1
    )

    apt_checkmk_installed = (
        subprocess.run(
            ["dpkg-query", "-W", "-f='${Status}'", "check-mk-agent"],
            capture_output=True,
            text=True,
        ).stdout.strip()
        == "'install ok installed'"
    )
    return port_6556_open or apt_checkmk_installed


@log()
def download_and_install_agent(api: "APIClient") -> None:
    """Download and install the Checkmk agent."""
    download_path = Path("/tmp/cmk-agent.deb")
    api.download_agent(download_path)

    try:
        subprocess.run(["sudo", "dpkg", "-i", download_path], check=True)
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Could not install the Checkmk agent.") from e


def omd_config_set(site_name: str, config_key: str, config_value: str) -> None:
    logger.debug("set omd configuration of site %s: %s => %s", site_name, config_key, config_value)
    try:
        subprocess.run(
            [
                "sudo",
                "omd",
                "config",
                site_name,
                "set",
                config_key,
                config_value,
            ],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"Could not set configuration {config_key} to {config_value} "
            f"for site {site_name}\n{e.stderr}"
        ) from e


def configure_tracing(central_site: Site, remote_sites: list[Site]) -> None:
    # has to be called after the sites have been completely set up, but before starting the sites.
    port_raw = subprocess.check_output(
        ["sudo", "omd", "config", central_site.name, "show", "TRACE_RECEIVE_PORT"]
    )
    port = int(port_raw.strip())

    # we assume that central_site and remote_sites share the same config and version

    if (
        central_site.cmk_pkg.base_version < BaseVersion(2, 4, 0)
        or central_site.cmk_pkg.edition == Edition.SAAS
    ):
        logger.warning(
            "[%s]: Tracing is not supported for version: %s",
            colorize(central_site.name, "yellow"),
            colorize(str(central_site.cmk_pkg.version), "yellow"),
        )
        return

    for remote_site in remote_sites:
        omd_config_set(remote_site.name, "TRACE_SEND_TARGET", f"http://localhost:{port}")
        omd_config_set(remote_site.name, "TRACE_SEND", "on")

    omd_config_set(central_site.name, "TRACE_RECEIVE", "on")
    omd_config_set(central_site.name, "TRACE_SEND", "on")


def raise_runtime_error(response: requests.Response) -> None:
    try:
        raise RuntimeError(json.dumps(response.json(), indent=4))
    except JSONDecodeError:
        raise RuntimeError(response.text)


def _prefix_log_api_client(self: "APIClient", *_args: Any, **_kwargs: Any) -> str:
    return f"[{colorize(self.site_name, 'blue')}]: "


class APIClient:
    """Checkmk API client."""

    def __init__(
        self,
        site_name: str = "heute",
        username: str = "cmkadmin",
        password: str = "cmk",
        # Note: don't be confused with the hosts registered on checkmk
        server_host_name: str = "localhost",
        proto: str = "http",
    ) -> None:
        self.base_url = f"{proto}://{server_host_name}/{site_name}/check_mk/api/1.0"

        self.site_name = site_name
        self.session = requests.session()
        self.session.headers["Authorization"] = f"Bearer {username} {password}"
        self.session.headers["Accept"] = "application/json"

    @log(prefix=_prefix_log_api_client)
    def version(self) -> dict[str, str] | None:
        response = self.session.get(
            f"{self.base_url}/version",
            headers={
                "Content-Type": "application/json",
            },
        )
        if response.status_code == 200:
            return response.json()
        else:
            return None

    @log(prefix=_prefix_log_api_client)
    def create_host(
        self,
        host_name: str,
        logical_site_name: str | None = None,
        ip_address: str = "127.0.0.1",
    ) -> None:
        """Create a host on the Checkmk server."""

        if host_name in self.list_all_hosts():
            logger.warning(
                "[%s]: Host %s already exists",
                colorize(self.site_name, "blue"),
                host_name,
            )
            return
        logical_site_name = logical_site_name or self.site_name
        response = self.session.post(
            f"{self.base_url}/domain-types/host_config/collections/all",
            params={
                "bake_agent": False,
            },
            headers={
                "Content-Type": "application/json",
            },
            json={
                "host_name": host_name,
                "folder": "/",
                "attributes": {
                    "ipaddress": ip_address,
                    "site": logical_site_name,
                },
            },
        )
        if response.status_code != 200:
            raise_runtime_error(response)

    @log(prefix=_prefix_log_api_client)
    def list_all_hosts(self) -> list[str]:
        """List all hosts registered on the Checkmk server."""
        response = self.session.get(
            f"{self.base_url}/domain-types/host_config/collections/all",
            headers={
                "Content-Type": "application/json",
            },
        )
        if response.status_code == 200:
            hosts = [host["title"] for host in response.json()["value"]]
            logger.debug("Hosts: %s", hosts)
            return hosts
        if response.status_code != 200:
            raise_runtime_error(response)

        return []

    def get_href_from_links(self, links: list[dict[str, str]], name: str) -> str:
        """Extract the href from the links."""
        for link in links:
            if link["rel"] == name:
                return link["href"]
        raise ValueError(f"could not find link named {name} in {links}")

    def get(self, url: str) -> requests.Response:
        """Make a GET request to the Checkmk server."""
        # this feels a bit hackish... introduced because links are absolute urls
        if not url.startswith("http://"):
            url = f"{self.base_url}{url}"
        resp = self.session.get(url)
        return resp

    @log(prefix=_prefix_log_api_client)
    def create_site_connection(self, site_config: RemoteSiteConnectionConfig) -> None:
        """Create a site connection on the Checkmk server."""
        response = self.session.post(
            f"{self.base_url}/domain-types/site_connection/collections/all",
            headers={
                "Content-Type": "application/json",
            },
            json={"site_config": site_config},
        )

        if response.status_code != 200:
            logger.debug("Status Code: %s", response.status_code)
            logger.debug("Response Headers: %s", response.headers)
            logger.debug("Response Text: %s", response.text)
            raise RuntimeError("Failed to create site connection")

    @log(prefix=_prefix_log_api_client)
    def set_user_language(self, language: str) -> None:
        """Set the user language on the Checkmk server."""
        response = self.session.put(
            f"{self.base_url}/objects/user_config/cmkadmin",
            headers={
                # (required) The value of the, to be modified, object's ETag header.
                "If-Match": "*",
                "Content-Type": "application/json",
            },
            json={"language": language},
        )
        if response.status_code != 200:
            logger.debug(response.text)
            logger.warning("Failed to set the user language")

    @log(prefix=_prefix_log_api_client)
    def list_all_site_connections(self) -> list[str]:
        """List all site connections registered on the Checkmk server."""
        response = self.session.get(
            f"{self.base_url}/domain-types/site_connection/collections/all",
            headers={
                "Content-Type": "application/json",
            },
        )
        if response.status_code != 200:
            raise_runtime_error(response)

        site_connections = [site["id"] for site in response.json()["value"]]
        logger.debug("Site Connections: %s", site_connections)
        return site_connections

    @log(prefix=_prefix_log_api_client)
    def activate_changes(self) -> None:
        """Activate changes on the Checkmk server."""
        response = self.session.post(
            f"{self.base_url}/domain-types/activation_run/actions/activate-changes/invoke",
            headers={
                # (required) The value of the, to be modified, object's ETag header.
                "If-Match": "*",
                # (required) A header specifying which type of content
                # is in the request/response body.
                "Content-Type": "application/json",
            },
            json={
                "redirect": False,
                "sites": [],
                "force_foreign_changes": True,
            },
            allow_redirects=True,
        )
        if response.status_code == 200:
            response.raise_for_status()

            # Extract the link for subsequent calls

            changes: set[str] = set()
            # Polling loop
            link = self.get_href_from_links(response.json()["links"], "self")

            while True:
                # Fetch data
                response = self.get(link)
                response.raise_for_status()
                data = response.json()

                # Process changes
                for change in data["extensions"]["changes"]:
                    change_id = change["id"]
                    if change_id not in changes:
                        changes.add(change_id)

                # Check if processing is complete
                if not data["extensions"]["is_running"]:
                    return  # Exit the function once processing is complete
                # Wait before polling again
                time.sleep(1)
        elif response.status_code == 422:
            logger.warning("[%s]: Nothing to activate", colorize(self.site_name, "blue"))
        else:
            raise_runtime_error(response)

    @log(prefix=_prefix_log_api_client)
    def login_to_remote_site(
        self, site_id: str, user: str = "cmkadmin", password: str = "cmk"
    ) -> None:
        response = self.session.post(
            f"{self.base_url}/objects/site_connection/{site_id}/actions/login/invoke",
            headers={
                "Content-Type": "application/json",
            },
            json={"username": user, "password": password},
        )

        if response.status_code != 204:
            raise_runtime_error(response)

    @log(prefix=_prefix_log_api_client)
    def download_agent(self, download_path: Path) -> None:
        """Download the Checkmk agent."""
        response = self.session.get(
            f"{self.base_url}/domain-types/agent/actions/download/invoke",
            params={"os_type": "linux_deb"},
            headers={
                "Accept": "application/octet-stream",
                "Content-Type": "application/json",
            },
        )
        if response.status_code == 200:
            with open(download_path, "wb") as f:
                f.write(response.content)
        else:
            raise_runtime_error(response)


def read_default_version() -> CMKPackage:
    raw_version = subprocess.check_output(("omd", "version", "-b"), text=True)
    package = parse_version(raw_version)
    if isinstance(package, CMKPackage):
        return package
    raise RuntimeError("🤔 Only found partial version with omd. WTF?")


def parse_version(version: str) -> CMKPackage | PartialCMKPackage:
    """Parse the version string into a cmk package."""

    if match := re.match(r"^(\d+\.\d+\.\d+)-(\d+[.-]\d+[.-]\d+)(?:\.(\w{3}))?$", version):
        try:
            return CMKPackage(
                version=VersionWithReleaseDate(
                    base_version=BaseVersion.from_str(match.group(1)),
                    release_date=datetime.strptime(
                        match.group(2).replace("-", "."), "%Y.%m.%d"
                    ).date(),
                ),
                edition=Edition(match.group(3) or "cee"),
            )
        except ValueError as e:
            raise argparse.ArgumentTypeError(e)
    elif match := re.match(r"^(\d+\.\d+\.\d+)(p|b)(\d+).(\w{3})$", version):
        try:
            return CMKPackage(
                version=VersionWithPatch(
                    base_version=BaseVersion.from_str(match.group(1)),
                    patch_type="p" if match.group(2) == "p" else "b",
                    patch=int(match.group(3)),
                ),
                edition=Edition(match.group(4)),
            )
        except ValueError as e:
            raise argparse.ArgumentTypeError(e)
    elif match := re.match(r"^(\d+\.\d+\.\d+).(\w{3})$", version):
        try:
            return CMKPackage(
                version=VersionWithPatch(
                    base_version=BaseVersion.from_str(match.group(1)),
                    patch_type="p",
                    patch=0,
                ),
                edition=Edition(match.group(2)),
            )
        except ValueError as e:
            raise argparse.ArgumentTypeError(e)
    elif match := re.match(r"^(\d+\.\d)+", version):
        try:
            return PartialCMKPackage(version)
        except ValueError as e:
            raise argparse.ArgumentTypeError(e)
    else:
        raise argparse.ArgumentTypeError(
            f"'{version}' doesn't match expected format"
            " '[<branch>p|b<patch>.<edition>|<branch>-<YYYY.MM.DD>.<edition>]'"
        )


def interactive_select(options: list[str], default: str) -> str:
    print("Available versions:")
    for i, o in enumerate(options):
        maybe_default = " (selected)" if o == default else ""
        print(f"\t{i + 1} {o}{maybe_default}")

    while True:
        user_input = input("Choose an option: ").strip()
        if not user_input:
            return default
        try:
            if (idx := int(user_input)) <= len(options) and idx > 0:
                return options[idx - 1]
        except ValueError:
            pass
        print("Invalid input. Please enter a number of press Enter for the default")


def interactive_version_select(partial_version: PartialCMKPackage) -> CMKPackage:
    raw_versions = subprocess.check_output(("omd", "versions", "-b"), text=True).strip().split("\n")
    most_similar = sorted(raw_versions, key=lambda v: partial_version.similarity(v))[-1]
    selected_version = interactive_select(raw_versions, most_similar)
    version = parse_version(selected_version)
    if isinstance(version, CMKPackage):
        return version
    raise RuntimeError("Oh we select another incomplete version from omd output WTF?")


@dataclass(frozen=True)
class Config:
    cmk_pkg: CMKPackage  # You should define this type properly
    name: str
    verbose: bool
    quiet: int
    distributed: int
    language: Language
    force: bool

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> Self:
        version: CMKPackage | PartialCMKPackage = args.version or read_default_version()
        if isinstance(version, PartialCMKPackage):
            version = interactive_version_select(version)
        return cls(
            cmk_pkg=version,
            name=args.name or cls._default_name(version.version),
            verbose=args.verbose,
            quiet=args.quiet,
            distributed=args.distributed,
            language=Language(args.language or "en"),
            force=args.force,
        )

    @staticmethod
    def _default_name(version: VersionWithPatch | VersionWithReleaseDate | BaseVersion) -> str:
        """Find the default site name based on the Checkmk version."""

        match version:
            case VersionWithPatch(base_version=base_version, patch_type=patch_type, patch=patch):
                return f"v{str(base_version).replace('.', '')}{patch_type}{patch}"
            case VersionWithReleaseDate(base_version=base_version):
                return f"v{str(base_version).replace('.', '')}"
            case BaseVersion():
                return f"v{str(version).replace('.', '')}"


class ArgFormatter(argparse.RawTextHelpFormatter):
    pass


def setup_parser() -> argparse.ArgumentParser:
    """Setup the argument parser for the script."""

    assert __doc__ is not None, "__doc__ must be a non-None string"
    prog, descr = __doc__.split("\n", 1)

    parser = argparse.ArgumentParser(
        prog=prog,
        description=descr,
        formatter_class=ArgFormatter,
    )
    parser.add_argument("--version", action="version", version=__version__)

    parser.add_argument(
        "version",
        type=parse_version,
        nargs="?",
        help="specify the full omd version\n"
        f"(default: {colorize('omd version -b', 'blue')},"
        " e.g {colorize('2.4.0-2025.04.07.cce', 'blue')}.)",
    )

    parser.add_argument(
        "-n",
        "--name",
        type=str,
        help="set the site name. Defaults to base version\n"
        "(e.g., 2.4.0 -> v240, 2.4.0p1 -> v240p1).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="increase output verbosity",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="count",
        default=0,
        help="suppress stderr output.\n('-q': suppress info, '-qq': suppress warnings)",
    )
    parser.add_argument(
        "-d",
        "--distributed",
        default=0,
        type=int,
        help="specify the number of distributed sites to set up.",
    )
    parser.add_argument(
        "-l",
        "--language",
        type=Language,
        default=Language.EN,
        choices=Language,
        help="set the language (default: %(default)s).",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="force site setup from scratch, even if the site with same name and\nversion exists",
    )

    return parser


def find_version_by_site_name(site_name: str) -> str | None:
    """
    Get the list of sitenames that are running by a specific version
    """
    path = Path("/omd/sites", site_name, "version")

    if not path.exists() or not path.is_symlink():
        return None

    try:
        target = path.readlink()  # Read the symlink target
        return target.name
    except OSError as e:
        raise RuntimeError(f"ERROR: {e.strerror}") from e


def read_config_int(remote_site: str, param: str) -> int | None:
    try:
        return int(
            subprocess.check_output(
                [
                    "sudo",
                    "su",
                    remote_site,
                    "-c",
                    f"omd config show {param}",
                ],
                stderr=subprocess.DEVNULL,  # Suppress error output
            )
            .decode()
            .split("\n")[0]
        )
    except ValueError:
        return None


@log()
def ensure_sudo() -> None:
    """It increases the sudo timeout and refreshes it."""
    try:
        # Ask for sudo privileges once and refresh them
        subprocess.run(["sudo", "-v"], check=True)
    except subprocess.CalledProcessError:
        logger.error("Failed to acquire sudo privileges.")
        sys.exit(1)


def handle_site_creation(site: Site, force: bool) -> None:
    existing_site_version = find_version_by_site_name(site.name)

    if not existing_site_version or existing_site_version != str(site.cmk_pkg) or force:
        site.delete_site()
        site.create_site()
        site.configure_site()

    else:
        logger.warning(
            "[%s]: Site already exists with version %s",
            colorize(site.name, "blue"),
            colorize(existing_site_version, "green"),
        )
        logger.warning("Use force option to delete the existing site")


def connect_central_to_remote(
    central_site: Site,
    central_api: APIClient,
    remote_site: Site,
) -> None:
    """
    Set up a distributed site.
    """
    central_site.add_remote_site_certificate(remote_site.name)
    livestatusport = read_config_int(remote_site.name, "LIVESTATUS_TCP_PORT")
    brokerport = read_config_int(remote_site.name, "RABBITMQ_PORT")

    if livestatusport is None:
        logger.error(
            "[%s]: Failed to read the Livestatus port",
            colorize(remote_site.name, "red"),
        )
        return
    # Broker port is only supported in 2.4.0 and above
    if brokerport is None:
        logger.warning(
            "[%s]: Failed to read the Broker port",
            colorize(remote_site.name, "red"),
        )

    remote_site_config = remote_site.get_site_connection_config(
        "localhost", livestatusport, brokerport
    )

    site_conns = central_api.list_all_site_connections()
    if remote_site.name in site_conns:
        logger.warning(
            "[%s]: Site connection %s already exists",
            colorize(central_site.name, "yellow"),
            remote_site.name,
        )
    else:
        central_api.create_site_connection(remote_site_config)

    # to establish connection to the remote site
    central_api.login_to_remote_site(remote_site.name)


def add_user_to_sudoers() -> None:
    # TODO: duplicate code. this is also available as ./bin/omd-setup-site-for-dev
    # we also have to be able to call this as a standalone script to be able to
    # f12 into sites not create with the offical tools
    """Add the current user to the sudoers file."""
    try:
        username = getpass.getuser()
        sites = [
            site_name
            for site_name in subprocess.check_output(["omd", "sites", "--bare"])
            .decode()
            .split("\n")
            if site_name
        ]
        sudoers_config = f"{username} ALL = ({','.join(sites)}) NOPASSWD: /bin/bash\n"
        p = subprocess.Popen(
            [
                "sudo",
                "EDITOR=tee",
                "visudo",
                "-f",
                "/etc/sudoers.d/omd-setup-site-for-dev",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
        )
        p.communicate(sudoers_config.encode("utf-8"))
    except subprocess.CalledProcessError as e:
        raise RuntimeError("Failed to add user to sudoers") from e


def format_validate_installation(cmk_pkg: CMKPackage) -> str:
    return f"Validate installation of {cmk_pkg}..."


@log(message_info=format_validate_installation)
def validate_installation(cmk_pkg: CMKPackage) -> None:
    """Validate Checkmk installation with proper error handling."""
    if not (INSTALLATION_PATH / Path(cmk_pkg.omd_version)).exists():
        raise RuntimeError(
            f"Checkmk {cmk_pkg.version} is not installed.\n"
            f"Install it using:\n cmk-dev-install {cmk_pkg.version.iso_format()} "
            f"--edition {cmk_pkg.edition.value}"
        )


@log()
def core_logic(args: argparse.Namespace) -> None:
    """Main business logic separated from error handling."""

    ensure_sudo()
    config = Config.from_args(args)
    cmk_pkg = config.cmk_pkg
    site_name = config.name

    validate_installation(cmk_pkg)

    central_site = Site(site_name, cmk_pkg)
    handle_site_creation(central_site, args.force)

    # Distributed setup
    remote_sites: list[Site] = []
    for number in range(1, args.distributed + 1):
        remote_site = Site(f"{central_site.name}_r{number}", config.cmk_pkg, is_remote=True)
        handle_site_creation(remote_site, config.force)
        remote_sites.append(remote_site)

    if central_site.cmk_pkg.base_version >= BaseVersion(2, 4):
        configure_tracing(central_site, remote_sites)

    api = APIClient(site_name=site_name)
    central_site.start_site(api)
    api.set_user_language(config.language.value)
    api.create_host(host_name=site_name)
    if not checkmk_agent_needs_installing():
        download_and_install_agent(api)

    for remote_site in remote_sites:
        remote_api = APIClient(site_name=remote_site.name)
        remote_site.start_site(remote_api)
        remote_api.set_user_language(config.language.value)
        remote_api.create_host(host_name=remote_site.name)
        remote_site.register_host_with_agent(
            host_name=remote_site.name, gui_user=GUI_USER, gui_pw=GUI_PW
        )
        remote_api.activate_changes()
        remote_site.trigger_site_checking_cycle()
        remote_site.discover_services()

        connect_central_to_remote(central_site, api, remote_site)

        # create host for the remote site in the central site
        api.create_host(host_name=remote_site.name, logical_site_name=remote_site.name)

    api.activate_changes()

    central_site.register_host_with_agent(
        host_name=central_site.name, gui_user=GUI_USER, gui_pw=GUI_PW
    )

    central_site.trigger_site_checking_cycle()
    central_site.discover_services()


def main() -> int:
    """
    Main function to set up Checkmk site and handle distributed setup.
    Returns:
       int: Exit status code.
    """
    parser: argparse.ArgumentParser = setup_parser()
    args = parser.parse_args()

    try:
        logger.setLevel(max(logging.INFO - ((args.verbose - args.quiet) * 10), logging.DEBUG))
        core_logic(args)

    except RuntimeError as e:
        logger.error(str(e))
        return 1

    return 0
