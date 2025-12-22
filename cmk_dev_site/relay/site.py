"""Site detection and version utilities."""

import os
from pathlib import Path

from cmk_dev_site.cmk.rest_api import APIClient
from cmk_dev_site.omd import omd_sites, omd_version
from cmk_dev_site.relay.metadata import read_metadata
from cmk_dev_site.relay.types import Site, Version
from cmk_dev_site.utils.log import get_logger

logger = get_logger(__name__)


def _parse_version_output(output: str) -> str:
    if "Version " not in output:
        raise RuntimeError(f"Could not parse version from output: {output}")

    version_part = output.split("Version ", 1)[1].strip()

    for suffix in (".ultimate", ".cee", ".cre"):
        if version_part.endswith(suffix):
            return version_part[: -len(suffix)]

    return version_part


def _get_site_from_env() -> Site | None:
    if site := os.environ.get("SITE"):
        logger.debug(f"Found site name from SITE environment variable: {site}")
        return Site(site)
    logger.debug("SITE environment variable not set")
    return None


def _get_site_from_file(start_dir: Path | None = None) -> Site | None:
    current_dir = start_dir or Path.cwd()
    logger.debug(f"Searching for .site file starting from: {current_dir}")

    for parent in [current_dir, *current_dir.parents]:
        site_file = parent / ".site"
        logger.debug(f"Checking for .site file at: {site_file}")
        if site_file.exists():
            site = site_file.read_text().strip()
            logger.debug(f"Found site name from .site file: {site}")
            return Site(site)

    logger.debug("No .site file found in directory tree")
    return None


def _get_site_from_omd() -> Site | None:
    logger.debug("Attempting to get site from 'omd sites --bare'")
    sites = omd_sites()
    if sites:
        site = sites[0]
        logger.debug(f"Found site name from omd: {site}")
        return Site(site)
    logger.debug("omd command returned no sites")
    return None


def get_site_name() -> Site:
    if site := _get_site_from_env():
        return site

    if site := _get_site_from_file():
        return site

    if site := _get_site_from_omd():
        return site

    raise RuntimeError(
        "Could not determine site name. "
        "Please set SITE environment variable, create a .site file, or use --site option."
    )


def get_version(site: Site) -> Version:
    output = omd_version(str(site))
    logger.debug(f"omd version output: {output}")

    version = _parse_version_output(output)
    logger.debug(f"Extracted version: {version}")
    return Version(version)


def delete_deployed_relays(site: Site, username: str = "cmkadmin", password: str = "cmk") -> None:
    logger.info("Deleting test relays from Checkmk...")

    metadata = read_metadata(site)
    if not metadata:
        logger.info("  (no metadata found, skipping relay deletion)")
        return

    relay_aliases = {relay.alias for relay in metadata.relays}

    client = APIClient(site_name=str(site), username=username, password=password)
    relays = client.list_relays()

    found_relays = [r for r in relays if r["alias"] in relay_aliases]

    if not found_relays:
        logger.info("  (no test relays found)")
        return

    for relay in found_relays:
        relay_id = relay["id"]
        logger.info(f"  - {relay['alias']} (id: {relay_id})")

        etag = client.get_relay_etag(relay_id)
        if not etag:
            logger.warning("    (failed to get ETag)")
            continue

        success = client.delete_relay(relay_id, etag)
        if not success:
            logger.warning("    (failed to delete)")
