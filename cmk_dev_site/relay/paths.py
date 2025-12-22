"""Path management utilities for relay working directories."""

from pathlib import Path

from cmk_dev_site.relay.types import Site


def get_site_workdir(site: Site) -> Path:
    return Path(f"/tmp/cmk-dev-relay/{site}")


def _get_relay_workdir(site: Site, relay_type: str) -> Path:
    return get_site_workdir(site) / relay_type


def get_manifest_dir(site: Site, relay_type: str) -> Path:
    return _get_relay_workdir(site, relay_type) / "manifests"


def get_config_dir(site: Site, relay_type: str) -> Path:
    return _get_relay_workdir(site, relay_type) / "config"


def get_metadata_path(site: Site) -> Path:
    return get_site_workdir(site) / "metadata.json"
