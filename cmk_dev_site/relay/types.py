"""Configuration types for relay deployment."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class Site:
    site: str

    def __repr__(self) -> str:
        return self.site

    def __str__(self) -> str:
        return self.site


@dataclass(frozen=True, slots=True)
class Version:
    _v: str

    def __repr__(self) -> str:
        return self._v

    def __str__(self) -> str:
        return self._v


@dataclass(frozen=True, slots=True)
class ContainerConfig:
    """Container deployment configuration."""

    registry: str
    tag: str
    config_dir: Path | str

    @property
    def image(self) -> str:
        """Full container image reference."""
        return f"{self.registry}/check-mk-relay:{self.tag}"


@dataclass(frozen=True, slots=True)
class RelayConfig:
    """Configuration for a single relay instance."""

    site: Site
    alias: str
    container: ContainerConfig
