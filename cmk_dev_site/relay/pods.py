"""Pod deployment and management using YAML templates and podman."""

from collections.abc import Iterable
from pathlib import Path
from string import Template

from cmk_dev_site.relay.paths import get_manifest_dir
from cmk_dev_site.relay.podman import kill_pod, play_kube, pod_exists
from cmk_dev_site.relay.types import RelayConfig
from cmk_dev_site.utils.log import get_logger

logger = get_logger(__name__)

TEMPLATE_DIR = Path(__file__).parent


def stop_pods(pods: Iterable[str]) -> None:
    logger.debug("Stopping pods...")
    for pod_name in pods:
        if pod_exists(pod_name):
            logger.debug(f"Stopping pod: {pod_name}")
            kill_pod(pod_name)


def render_manifest(
    template_path: Path,
    relay: RelayConfig,
) -> str:
    template = Template(template_path.read_text())
    return template.substitute(
        image_registry=relay.container.registry,
        image_tag=relay.container.tag,
        site=str(relay.site),
        relay_alias=relay.alias,
        config_dir=str(relay.container.config_dir),
    )


def deploy_pod(
    pod_type: str,
    relay: RelayConfig,
) -> None:
    pod_name = f"relay-{pod_type}-pod-{relay.site}"
    logger.info("")
    logger.info(f"Deploying {pod_type.upper()} relay pod for site {relay.site}...")
    logger.info(f"Using image: {relay.container.image}")
    logger.info(f"Relay alias: {relay.alias}")

    manifest_dir = get_manifest_dir(relay.site)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    template_path = TEMPLATE_DIR / f"{pod_type}-pod.yaml"
    rendered = render_manifest(template_path, relay)

    manifest_file = manifest_dir / f"{pod_type}-pod.yaml"
    manifest_file.write_text(rendered)
    logger.debug(f"Wrote manifest to: {manifest_file}")

    logger.info(f"Deploying pod with YAML: {manifest_file}")
    result = play_kube(manifest_file)

    if result.returncode != 0:
        if "already exists" in result.stderr or "name is in use" in result.stderr:
            raise RuntimeError(
                f"Pod '{pod_name}' already exists. "
                "Please run 'cmk-dev-relay down' first to remove existing pods.\n"
                f"Error: {result.stderr}"
            )
        raise RuntimeError(
            f"Failed to deploy {pod_type.upper()} relay pod.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
