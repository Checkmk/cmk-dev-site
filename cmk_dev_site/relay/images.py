"""Image building and pulling operations."""

import subprocess

from cmk_dev_site.relay.podman import pull_image
from cmk_dev_site.relay.types import Version
from cmk_dev_site.utils.log import get_logger

logger = get_logger(__name__)


def build_image(version: Version) -> None:
    # Check if the relay image target exists in the Checkmk repository
    logger.debug("Checking if relay image target exists...")
    result = subprocess.run(
        ["bazel", "query", "//omd/non-free/relay:image_podman"],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Cannot build image: not in a Checkmk repository or relay target not found.\n"
            "Please run this command from the Checkmk repository root, "
            "or use --dockerhub instead.\n"
            f"Bazel error: {result.stderr.strip()}"
        )

    logger.info(f"Building relay image for version {version}...")
    subprocess.run(
        ["bazel", "run", f"--cmk_version={version}", "//omd/non-free/relay:image_podman"],
        check=True,
    )


def pull_images(image_registry: str, image_tag: str) -> None:
    relay_image = f"{image_registry}/check-mk-relay:{image_tag}"
    logger.info(f"Pulling image: {relay_image}")
    result = pull_image(relay_image)
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to pull relay image '{relay_image}'. "
            f"Please check if the image exists or use --build to build locally. "
            f"Error: {result.stderr}"
        )

    logger.info("Pulling image: docker.io/polinux/snmpd")
    result = pull_image("docker.io/polinux/snmpd")
    if result.returncode != 0:
        raise RuntimeError(
            f"Failed to pull SNMP daemon image 'docker.io/polinux/snmpd'. Error: {result.stderr}"
        )
