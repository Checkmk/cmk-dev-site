"""Path management utilities for relay working directories."""

from pathlib import Path

from cmk_dev_site.relay.types import Site


def get_site_workdir(site: Site) -> Path:
    return Path(f"/tmp/cmk-dev-relay/{site}")


def get_manifest_dir(site: Site) -> Path:
    return get_site_workdir(site) / "manifests"


def get_metadata_path(site: Site) -> Path:
    return get_site_workdir(site) / "metadata.json"
