"""cmk-dev-site

Set up sites based on the specified OMD version
Defaults to the current OMD version if version is not provided.
If a site with the same name and version already exists, it skips recreation and base
configuration, proceeding with the next steps. Use the -f option to force a full setup.
"""

import argparse
import getpass
import logging
import re
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import (
    Any,
    Self,
)

from .cmk.rest_api import APIClient, CheckmkAPIException, RemoteSiteConnectionConfig
from .omd import (
    BaseVersion,
    CMKPackage,
    Edition,
    PartialCMKPackage,
    VersionWithPatch,
    VersionWithReleaseDate,
    omd_config_get,
    omd_config_set,
)
from .utils import run_command as run_command_c
from .utils.log import add_method_logging, colorize, generate_log_decorator, get_logger
from .version import __version__

logger = get_logger(__name__)
log = generate_log_decorator(logger)
omd_config_set = log(max_level=logging.DEBUG)(omd_config_set)
omd_config_get = log(max_level=logging.DEBUG)(omd_config_get)


def run_command(
    args: Sequence[str],
    check: bool = True,
    error_message: str | None = None,
    raise_runtime_error: bool = True,
    text: bool = True,
    silent: bool = False,
    **kwargs: Any,
) -> subprocess.CompletedProcess[Any]:
    return run_command_c(
        args,
        check=check,
        error_message=error_message,
        raise_runtime_error=raise_runtime_error,
        text=text,
        silent=silent,
        logger=logger,  # slightly hackish: pass in the right logger
        **kwargs,
    )


def _prefix_log_api_client(self: APIClient, *_args: Any, **_kwargs: Any) -> str:
    return f"[{colorize(self.site_name, 'blue')}]: "


add_method_logging(log(prefix=_prefix_log_api_client))(APIClient)

GUI_USER = "cmkadmin"
GUI_PW = "cmk"
INSTALLATION_PATH = Path("/omd/versions")


class Language(StrEnum):
    EN = "en"
    DE = "de"
    RO = "ro"


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
        run_command(
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
            error_message=f"[{self.name}]: Failed to create the site",
        )

        # Setting the password for user
        hashalgo = "-m" if self.cmk_pkg.base_version == "2.1.0" else "-B"

        run_command(
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
            error_message=f"[{self.name}]: Failed to create site user pass",
        )

    @log(prefix=_prefix_log_site)
    def delete_site(self) -> None:
        """Delete the site if it already exists."""
        if Path("/omd/sites", self.name).exists():
            run_command(
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
            )

    @log(prefix=_prefix_log_site)
    def configure_site(self, configs: list[tuple[str, str]]) -> None:
        try:
            if self.cmk_pkg.base_version == "2.1.0" and "MKEVENTD" not in dict(configs):
                omd_config_set(self.name, "MKEVENTD", "on")

            if "LIVESTATUS_TCP" not in dict(configs):
                omd_config_set(self.name, "LIVESTATUS_TCP", "on")

        except RuntimeError as e:
            logger.warning(
                "[%s]: Failed to configure the site. %s",
                colorize(self.name, "yellow"),
                e,
            )

        for key, value in configs:
            try:
                omd_config_set(self.name, key, value)
            except RuntimeError as e:
                logger.warning(
                    "[%s]: Failed to set option %s=%s. %s",
                    colorize(self.name, "yellow"),
                    key,
                    value,
                    e,
                )

    @log(prefix=_prefix_log_site)
    def start_site(self, api: "APIClient") -> None:
        run_command(
            ["sudo", "omd", "start", self.name],
            check=True,
            raise_runtime_error=False,
            error_message=(
                f"[{colorize(self.name, 'yellow')}]: Failed to start the site. "
                "Site probably is running"
            ),
        )
        max_try = 5
        while api.version() is None and max_try > 0:
            max_try -= 1
            time.sleep(1)
        if max_try == 0:
            raise RuntimeError(
                f"[{colorize(self.name, 'red')}]: Failed to start the site. "
                "Check if the site is running and try again."
            )

    @log(prefix=_prefix_log_site)
    def trigger_site_checking_cycle(self) -> None:
        run_command(
            ["sudo", "su", "-", self.name, "-c", f"cmk -n '{self.name}'"],
            error_message=(
                f"[{colorize(self.name, 'yellow')}]: Failed to trigger the site checking cycle"
            ),
            raise_runtime_error=False,
        )

    @log(prefix=_prefix_log_site)
    def discover_services(self) -> None:
        run_command(
            ["sudo", "su", "-", self.name, "-c", "cmk -vI ; cmk -O"],
            error_message=f"[{colorize(self.name, 'yellow')}]: Failed to discover services",
            raise_runtime_error=False,
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
                "is_trusted": False,
            },
        }
        if message_broker_port:
            config["configuration_connection"]["message_broker_port"] = message_broker_port

        if self.cmk_pkg.edition == Edition.MANAGED:
            # required filed for managed edition
            config["basic_settings"]["customer"] = "provider"
        return config

    @log(prefix=_prefix_log_site, max_level=logging.DEBUG)
    def _append_to_file(self, file_path: Path, content: str) -> None:
        try:
            run_command(
                ["sudo", "su", "-", self.name, "-c", f"tee -a {file_path}"],
                input=content,
                error_message=f"Failed to append to {file_path}",
            )
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

        cert_der = run_command(
            ("sudo", "openssl", "x509", "-inform", "PEM", "-in", str(cert_path), "-outform", "DER"),
            input=str(cert_path).encode(),
            text=False,
        ).stdout
        cert_pem: str = run_command(
            ("openssl", "x509", "-inform", "DER", "-outform", "PEM"), input=cert_der, text=False
        ).stdout.decode("utf-8")

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

        run_command(
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
            error_message=f"Failed to register host {host_name} with cmk-agent-ctl",
        )


def checkmk_agent_needs_installing() -> bool:
    """Check if the Checkmk agent is installed."""
    cmk_agent_ctl_path = shutil.which("cmk-agent-ctl")
    if cmk_agent_ctl_path:
        return True
    # Check if port 6556 is open
    port_6556_open = run_command(["sudo", "ss", "-tuln"]).stdout.find(":6556 ") != -1

    apt_checkmk_installed = (
        run_command(
            ["dpkg-query", "-W", "-f='${Status}'", "check-mk-agent"],
            check=False,  # if no package is found, status code is not 0
        ).stdout.strip()
        == "'install ok installed'"
    )
    return port_6556_open or apt_checkmk_installed


def parse_int(value: str | None) -> int | None:
    """Parse a str to an integer, returning None if the string is empty."""
    if value is None or value.strip() == "":
        return None
    try:
        return int(value)
    except ValueError:
        return None


@log()
def download_and_install_agent(api: "APIClient") -> None:
    """Download and install the Checkmk agent."""
    download_path = Path("/tmp/cmk-agent.deb")
    api.download_agent(download_path)

    run_command(
        ["sudo", "dpkg", "-i", str(download_path)],
        error_message="Failed to install the Checkmk agent",
    )


def configure_tracing(central_site: Site, remote_sites: list[Site]) -> None:
    # has to be called after the sites have been completely set up, but before starting the sites.
    port = parse_int(omd_config_get(central_site.name, "TRACE_RECEIVE_PORT"))
    if port is None:
        raise RuntimeError("Failed to read the TRACE_RECEIVE_PORT for the central site")

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


def read_default_version() -> CMKPackage:
    raw_version = run_command(["omd", "version", "-b"]).stdout.strip()
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
    raw_versions = run_command(["omd", "versions", "-b"]).stdout.strip().split("\n")
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


def create_parser() -> argparse.ArgumentParser:
    assert __doc__ is not None, "__doc__ must be a non-None string"
    prog, descr = __doc__.split("\n", 1)

    parser = argparse.ArgumentParser(
        prog=prog,
        description=descr,
        formatter_class=ArgFormatter,
    )
    parser.add_argument("--version", action="version", version=__version__)
    return parser


def setup_parser(parser: argparse.ArgumentParser) -> None:
    """Setup the argument parser for the script."""

    parser.add_argument(
        "version",
        type=parse_version,
        nargs="?",
        help="specify the full omd version\n"
        f"(default: {colorize('omd version -b', 'blue')},"
        f" e.g {colorize('2.4.0-2025.04.07.cce', 'blue')}.)",
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

    parser.add_argument(
        "--omd-configs",
        nargs="*",
        type=parse_config,
        help="list of valid key=value pairs for omd config (e.g. LIVESTATUS_TCP=on)",
        default=[],
    )


def parse_config(config: str) -> tuple[str, str]:
    """
    Parse a key=value option from the command line.
    """
    if "=" not in config:
        raise argparse.ArgumentTypeError(f"Invalid option format: {config}. Expected key=value.")
    key, value = config.split("=", 1)
    return key.strip(), value.strip()


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


@log()
def ensure_sudo() -> None:
    """It increases the sudo timeout and refreshes it."""
    run_command(["sudo", "-v"], error_message="Failed to acquire sudo privileges.")


def handle_site_creation(site: Site, force: bool, configs: list[tuple[str, str]]) -> None:
    existing_site_version = find_version_by_site_name(site.name)

    if not existing_site_version or existing_site_version != str(site.cmk_pkg) or force:
        site.delete_site()
        site.create_site()
        site.configure_site(configs)

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
    livestatusport = parse_int(omd_config_get(remote_site.name, "LIVESTATUS_TCP_PORT"))
    brokerport = parse_int(omd_config_get(remote_site.name, "RABBITMQ_PORT"))

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
    if site_conns and remote_site.name in site_conns:
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
    # f12 into sites not create with the official tools
    """Add the current user to the sudoers file."""
    username = getpass.getuser()
    sites = [
        site_name
        for site_name in subprocess.check_output(["omd", "sites", "--bare"]).decode().split("\n")
        if site_name
    ]
    sudoers_config = f"{username} ALL = ({','.join(sites)}) NOPASSWD: /bin/bash\n"
    run_command(
        [
            "sudo",
            "EDITOR=tee",
            "visudo",
            "-f",
            "/etc/sudoers.d/omd-setup-site-for-dev",
        ],
        input=sudoers_config,
        error_message="Failed to add user to sudoers",
    )


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


def activate_changes(api: APIClient) -> None:
    """Activate changes in the Checkmk site."""
    result = api.activate_changes()
    if not result:
        logger.warning(
            "[%s]: Nothing to activate",
            colorize(api.site_name, "yellow"),
        )


def ensure_host_exists(
    api: APIClient,
    host_name: str,
) -> None:
    """Ensure the host exists; create it if it does not."""
    if (hosts := api.list_all_hosts()) and host_name in hosts:
        logger.warning(
            "[%s]: Host %s already exists",
            colorize(api.site_name, "yellow"),
            host_name,
        )
    else:
        api.create_host(host_name=host_name)


@log(max_level=logging.DEBUG)
def core_logic(args: argparse.Namespace) -> None:
    """Main business logic separated from error handling."""

    ensure_sudo()
    config = Config.from_args(args)
    cmk_pkg = config.cmk_pkg
    site_name = config.name

    validate_installation(cmk_pkg)

    central_site = Site(site_name, cmk_pkg)
    handle_site_creation(central_site, args.force, args.omd_configs)

    # Distributed setup
    remote_sites: list[Site] = []
    for number in range(1, args.distributed + 1):
        remote_site = Site(f"{central_site.name}_r{number}", config.cmk_pkg, is_remote=True)
        handle_site_creation(remote_site, config.force, args.omd_configs)
        remote_sites.append(remote_site)

    if central_site.cmk_pkg.base_version >= BaseVersion(2, 4):
        try:
            configure_tracing(central_site, remote_sites)
        except RuntimeError:
            logger.warning("could not configure tracing")
            pass

    api = APIClient(site_name=site_name)
    central_site.start_site(api)
    try:
        api.set_user_language(config.language.value)
    except CheckmkAPIException as e:
        logger.warning(
            "[%s]: %s",
            colorize(site_name, "yellow"),
            e,
        )

        pass
    ensure_host_exists(api, site_name)
    if not checkmk_agent_needs_installing():
        download_and_install_agent(api)

    for remote_site in remote_sites:
        remote_api = APIClient(site_name=remote_site.name)
        remote_site.start_site(remote_api)
        try:
            remote_api.set_user_language(config.language.value)
        except CheckmkAPIException as e:
            logger.warning(
                "[%s]: %s",
                colorize(remote_site.name, "yellow"),
                e,
            )
            pass
        ensure_host_exists(remote_api, remote_site.name)
        remote_site.register_host_with_agent(
            host_name=remote_site.name, gui_user=GUI_USER, gui_pw=GUI_PW
        )
        activate_changes(remote_api)
        remote_site.trigger_site_checking_cycle()
        remote_site.discover_services()

        connect_central_to_remote(central_site, api, remote_site)

        # create host for the remote site in the central site
        api.create_host(host_name=remote_site.name, logical_site_name=remote_site.name)

    activate_changes(api)

    central_site.register_host_with_agent(
        host_name=central_site.name, gui_user=GUI_USER, gui_pw=GUI_PW
    )

    central_site.trigger_site_checking_cycle()
    central_site.discover_services()

    logger.info(
        "[%s]: Happy hacking: %s ",
        colorize(central_site.name, "green"),
        colorize(f"http://localhost/{central_site.name}/check_mk", "blue"),
    )


def execute(args: argparse.Namespace) -> int:
    try:
        logger.setLevel(max(logging.INFO - ((args.verbose - args.quiet) * 10), logging.DEBUG))
        core_logic(args)

    except RuntimeError as e:
        logger.error(str(e))
        return 1

    return 0


def main(sys_argv: list[str] | None = None) -> int:
    """
    Main function to set up Checkmk site and handle distributed setup.
    Returns:
       int: Exit status code.
    """
    parser: argparse.ArgumentParser = create_parser()
    setup_parser(parser)
    args = parser.parse_args(sys_argv or sys.argv[1:])
    return execute(args)
