"""Pod deployment and management using docker-compose."""

from collections.abc import Iterable
from pathlib import Path
from string import Template

from cmk_dev_site.relay.container_runtime import compose_down, compose_up
from cmk_dev_site.relay.paths import get_config_dir, get_manifest_dir
from cmk_dev_site.relay.types import RelayConfig
from cmk_dev_site.utils.log import get_logger

logger = get_logger(__name__)

TEMPLATE_DIR = Path(__file__).parent


def stop_compose_services(compose_files: Iterable[Path]) -> None:
    """Stop all services defined in compose files."""
    logger.debug("Stopping compose services...")
    for compose_file in compose_files:
        if compose_file.exists():
            logger.debug(f"Stopping services from: {compose_file}")
            result = compose_down(compose_file)
            if result.returncode != 0:
                logger.warning(f"Failed to stop services: {result.stderr}")


def get_compose_file_path(pod_type: str, site: str) -> Path:
    from cmk_dev_site.relay.types import Site

    manifest_dir = get_manifest_dir(Site(site), pod_type)
    return manifest_dir / f"{pod_type}-compose.yaml"


def render_manifest(
    template_path: Path,
    relay: RelayConfig,
    pod_type: str,
) -> str:
    config_path = get_config_dir(relay.site, pod_type)

    template = Template(template_path.read_text())
    return template.substitute(
        image_registry=relay.container.registry,
        image_tag=relay.container.tag,
        site=str(relay.site),
        relay_alias=relay.alias,
        config_path=str(config_path),
    )


def deploy_pod(
    pod_type: str,
    relay: RelayConfig,
) -> None:
    """Deploy relay services using docker-compose."""
    logger.info("")
    logger.info(f"Deploying {pod_type.upper()} relay services for site {relay.site}...")
    logger.info(f"Using image: {relay.container.image}")
    logger.info(f"Relay alias: {relay.alias}")

    manifest_dir = get_manifest_dir(relay.site, pod_type)
    manifest_dir.mkdir(parents=True, exist_ok=True)

    template_path = TEMPLATE_DIR / f"{pod_type}-compose.yaml"
    rendered = render_manifest(template_path, relay, pod_type)

    compose_file = get_compose_file_path(pod_type, str(relay.site))
    compose_file.write_text(rendered)
    logger.debug(f"Wrote compose file to: {compose_file}")

    logger.info(f"Starting services with compose file: {compose_file}")
    result = compose_up(compose_file)

    if result.returncode != 0:
        if "already" in result.stderr.lower() or "exists" in result.stderr.lower():
            raise RuntimeError(
                f"Services for {pod_type} relay already exist. "
                "Please run 'cmk-dev-relay down' first to remove existing services.\n"
                f"Error: {result.stderr}"
            )
        raise RuntimeError(
            f"Failed to deploy {pod_type.upper()} relay services.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
