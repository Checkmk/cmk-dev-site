"""Tests for relay pod deployment."""

from pathlib import Path

from cmk_dev_site.relay.pods import render_manifest
from cmk_dev_site.relay.types import ContainerConfig, RelayConfig, Site


def test_render_manifest(tmp_path: Path) -> None:
    template_content = """apiVersion: v1
kind: Pod
metadata:
  name: relay-pod-$site
spec:
  containers:
    - name: relay
      image: $image_registry/check-mk-relay:$image_tag
      command: ["cmk-relay", "register", "-n", "$relay_alias"]
  volumes:
    - hostPath:
        path: /tmp/cmk-dev-relay/$site/configs/$config_dir
"""
    template_file = tmp_path / "pod.yaml"
    template_file.write_text(template_content)

    container = ContainerConfig(registry="docker.io/checkmk", tag="2.5.0", config_dir="test-config")
    relay = RelayConfig(site=Site("v250"), alias="test-relay", container=container)

    rendered = render_manifest(template_path=template_file, relay=relay)

    assert "name: relay-pod-v250" in rendered
    assert "image: docker.io/checkmk/check-mk-relay:2.5.0" in rendered
    assert 'command: ["cmk-relay", "register", "-n", "test-relay"]' in rendered
    assert "/tmp/cmk-dev-relay/v250/configs/test-config" in rendered


def test_container_config_image_property() -> None:
    container = ContainerConfig(
        registry="docker.io/checkmk", tag="2.5.0-latest", config_dir="/tmp/config"
    )
    assert container.image == "docker.io/checkmk/check-mk-relay:2.5.0-latest"
