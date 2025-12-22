"""Metadata management for relay deployments."""

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from cmk_dev_site.relay.paths import get_metadata_path
from cmk_dev_site.relay.types import Site, Version


class RelayInfo(BaseModel):
    pod_name: str
    alias: str


class DeploymentMetadata(BaseModel):
    site: str
    version: str
    deployed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    image_registry: str
    image_tag: str
    relays: list[RelayInfo]

    @classmethod
    def create(
        cls,
        site: Site,
        image_registry: str,
        image_tag: str,
        version: Version,
        relays: list[tuple[str, str]],
    ) -> "DeploymentMetadata":
        """relays: List of (pod_type, alias) e.g. [("snmp", "podman-relay")]"""
        return cls(
            site=str(site),
            version=str(version),
            image_registry=image_registry,
            image_tag=image_tag,
            relays=[
                RelayInfo(
                    pod_name=f"relay-{pod_type}-pod-{site}",
                    alias=alias,
                )
                for pod_type, alias in relays
            ],
        )


def write_metadata(
    site: Site,
    image_registry: str,
    image_tag: str,
    version: Version,
    relays: list[tuple[str, str]],
) -> None:
    metadata_path = get_metadata_path(site)
    metadata_path.parent.mkdir(parents=True, exist_ok=True)

    metadata = DeploymentMetadata.create(site, image_registry, image_tag, version, relays)
    metadata_path.write_text(metadata.model_dump_json(indent=2) + "\n")


def read_metadata(site: Site) -> DeploymentMetadata | None:
    metadata_path = get_metadata_path(site)
    if not metadata_path.exists():
        return None

    return DeploymentMetadata.model_validate_json(metadata_path.read_text())


def read_metadata_from_file(path: Path) -> DeploymentMetadata:
    return DeploymentMetadata.model_validate_json(path.read_text())


def get_pod_names_from_metadata(site: Site) -> list[str]:
    metadata = read_metadata(site)
    if not metadata:
        return []
    return [relay.pod_name for relay in metadata.relays]
