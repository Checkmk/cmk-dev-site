"""Image building and pulling operations."""

import shutil
import subprocess

from cmk_dev_site.relay.container_runtime import pull_image
from cmk_dev_site.relay.types import Version
from cmk_dev_site.utils.log import get_logger

logger = get_logger(__name__)


def _get_bazel_image_target() -> str:
    """Detect which bazel image target to use based on available container runtime."""
    if shutil.which("docker"):
        return "image_docker"
    elif shutil.which("podman"):
        return "image_podman"
    else:
        raise RuntimeError("Neither docker nor podman found")


def build_image(version: Version) -> None:
    target = _get_bazel_image_target()
    target_path = f"//omd/non-free/relay:{target}"

    logger.debug(f"Checking if relay image target exists: {target_path}")
    result = subprocess.run(
        ["bazel", "query", target_path],
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

    logger.info(f"Building relay image for version {version} using {target}...")
    subprocess.run(
        ["bazel", "run", f"--cmk_version={version}", target_path],
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
