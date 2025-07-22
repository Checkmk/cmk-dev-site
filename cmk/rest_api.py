import json
import time
from pathlib import Path
from typing import (
    NotRequired,
    TypedDict,
)

import requests
from requests.exceptions import JSONDecodeError


def raise_runtime_error(response: requests.Response) -> None:
    try:
        raise RuntimeError(json.dumps(response.json(), indent=4))
    except JSONDecodeError:
        raise RuntimeError(response.text)


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

    def create_host(
        self,
        host_name: str,
        logical_site_name: str | None = None,
        ip_address: str = "127.0.0.1",
    ) -> None:
        """Create a host on the Checkmk server."""

        if host_name in self.list_all_hosts():
            # TODO signal that the host already exists
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
            return hosts
        if response.status_code != 200:
            raise_runtime_error(response)

        return []

    def _get_href_from_links(self, links: list[dict[str, str]], name: str) -> str:
        """Extract the href from the links."""
        for link in links:
            if link["rel"] == name:
                return link["href"]
        raise ValueError(f"could not find link named {name} in {links}")

    def _get(self, url: str) -> requests.Response:
        """Make a GET request to the Checkmk server."""
        # this feels a bit hackish... introduced because links are absolute urls
        if not url.startswith("http://"):
            url = f"{self.base_url}{url}"
        resp = self.session.get(url)
        return resp

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
            raise RuntimeError("Failed to create site connection")

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
            # TODO: handle this more gracefully
            pass

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
        return site_connections

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
            link = self._get_href_from_links(response.json()["links"], "self")

            while True:
                # Fetch data
                response = self._get(link)
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
            # TODO: need warnings but outsied the function
            pass
        else:
            raise_runtime_error(response)

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
