"""Tests for relay compose deployment."""

from pathlib import Path

from cmk_dev_site.relay.pods import render_manifest
from cmk_dev_site.relay.types import ContainerConfig, RelayConfig, Site


def test_render_manifest(tmp_path: Path) -> None:
    template_content = """services:
  relay:
    image: $image_registry/check-mk-relay:$image_tag
    container_name: relay-$site
    command: ["cmk-relay", "register", "-n", "$relay_alias"]
    volumes:
      - $config_path:/opt/check-mk-relay/workdir
"""
    template_file = tmp_path / "compose.yaml"
    template_file.write_text(template_content)

    container = ContainerConfig(registry="docker.io/checkmk", tag="2.5.0")
    relay = RelayConfig(site=Site("v250"), alias="test-relay", container=container)

    rendered = render_manifest(template_path=template_file, relay=relay, pod_type="snmp")

    assert "container_name: relay-v250" in rendered
    assert "image: docker.io/checkmk/check-mk-relay:2.5.0" in rendered
    assert 'command: ["cmk-relay", "register", "-n", "test-relay"]' in rendered
    assert "/tmp/cmk-dev-relay/v250/snmp/config" in rendered


def test_container_config_image_property() -> None:
    container = ContainerConfig(registry="docker.io/checkmk", tag="2.5.0-latest")
    assert container.image == "docker.io/checkmk/check-mk-relay:2.5.0-latest"
