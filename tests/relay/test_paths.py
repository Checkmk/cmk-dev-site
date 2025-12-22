"""Tests for relay path management utilities."""

from pathlib import Path

from cmk_dev_site.relay.paths import (
    get_config_dir,
    get_manifest_dir,
    get_metadata_path,
    get_site_workdir,
)
from cmk_dev_site.relay.types import Site


def test_get_site_workdir() -> None:
    assert get_site_workdir(Site("v250")) == Path("/tmp/cmk-dev-relay/v250")


def test_get_manifest_dir() -> None:
    assert get_manifest_dir(Site("v250"), "snmp") == Path("/tmp/cmk-dev-relay/v250/snmp/manifests")
    assert get_manifest_dir(Site("v250"), "host") == Path("/tmp/cmk-dev-relay/v250/host/manifests")


def test_get_config_dir() -> None:
    assert get_config_dir(Site("v250"), "snmp") == Path("/tmp/cmk-dev-relay/v250/snmp/config")
    assert get_config_dir(Site("v250"), "host") == Path("/tmp/cmk-dev-relay/v250/host/config")


def test_get_metadata_path() -> None:
    assert get_metadata_path(Site("v250")) == Path("/tmp/cmk-dev-relay/v250/metadata.json")
