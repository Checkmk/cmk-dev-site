"""Tests for relay metadata management."""

from pathlib import Path

import pytest

from cmk_dev_site.relay.metadata import (
    DeploymentMetadata,
    get_pod_names_from_metadata,
    read_metadata,
    write_metadata,
)
from cmk_dev_site.relay.types import Site, Version


@pytest.fixture
def mock_metadata_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    def mock_get_metadata_path(site: Site) -> Path:
        return tmp_path / str(site) / "metadata.json"

    monkeypatch.setattr("cmk_dev_site.relay.metadata.get_metadata_path", mock_get_metadata_path)
    return tmp_path


def test_deployment_metadata_create() -> None:
    metadata = DeploymentMetadata.create(
        site=Site("v250"),
        image_registry="docker.io/checkmk",
        image_tag="2.5.0",
        version=Version("2.5.0"),
        relays=[("snmp", "test-snmp"), ("host", "test-host")],
    )

    assert metadata.site == "v250"
    assert metadata.version == "2.5.0"
    assert len(metadata.relays) == 2
    assert metadata.relays[0].pod_name == "relay-snmp-pod-v250"
    assert metadata.relays[0].alias == "test-snmp"
    assert metadata.relays[1].pod_name == "relay-host-pod-v250"
    assert metadata.relays[1].alias == "test-host"


def test_write_and_read_metadata(mock_metadata_path: Path) -> None:
    write_metadata(
        site=Site("v250"),
        image_registry="docker.io/checkmk",
        image_tag="2.5.0",
        version=Version("2.5.0"),
        relays=[("snmp", "podman-relay"), ("host", "host-relay")],
    )

    metadata = read_metadata(Site("v250"))
    assert metadata is not None
    assert metadata.site == "v250"
    assert metadata.version == "2.5.0"
    assert len(metadata.relays) == 2
    assert metadata.relays[0].alias == "podman-relay"
    assert metadata.relays[1].alias == "host-relay"


def test_read_metadata_nonexistent(mock_metadata_path: Path) -> None:
    assert read_metadata(Site("nonexistent")) is None


def test_get_pod_names_from_metadata(mock_metadata_path: Path) -> None:
    write_metadata(
        site=Site("v250"),
        image_registry="docker.io/checkmk",
        image_tag="2.5.0",
        version=Version("2.5.0"),
        relays=[("snmp", "podman-relay"), ("host", "host-relay")],
    )

    pod_names = get_pod_names_from_metadata(Site("v250"))
    assert pod_names == ["relay-snmp-pod-v250", "relay-host-pod-v250"]


def test_get_pod_names_from_metadata_no_metadata(mock_metadata_path: Path) -> None:
    pod_names = get_pod_names_from_metadata(Site("nonexistent"))
    assert pod_names == []
