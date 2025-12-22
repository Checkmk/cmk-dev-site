"""Relay tool for cmk-dev-site.

Manage Checkmk relay containers for testing.

Creates docker/podman containers to simulate relay environments for testing.

Relay Setup:
  • SNMP Relay (podman-relay)
    - Isolated network environment with single test host (test.relay)
    - Runs snmpd daemon for SNMP monitoring
    - Network isolated from host system
    - Test host: snmp-test-host (only accessible via this relay)

  • Host Relay (host-relay)
    - Standard agent/API relay
    - Can access multiple hosts on host network
    - Used for agent-based monitoring

Directory Structure:
  /tmp/cmk-dev-relay/{site}/
    ├── snmp/
    │   ├── manifests/
    │   │   └── snmp-compose.yaml
    │   └── config/              Relay configuration files
    ├── host/
    │   ├── manifests/
    │   │   └── host-compose.yaml
    │   └── config/              Relay configuration files
    └── metadata.json            Deployment metadata

Containers Created:
  • relay-snmp-{site}       SNMP relay (network isolated)
  • relay-snmpd-{site}      snmpd daemon
  • relay-host-{site}       Host relay (agent/API)
"""

import argparse
import json
import logging
from typing import Literal, assert_never

from cmk_dev_site.relay.container_runtime import compose_logs, compose_ps
from cmk_dev_site.relay.images import build_image, pull_images
from cmk_dev_site.relay.metadata import (
    get_compose_files_from_metadata,
    read_metadata,
    write_metadata,
)
from cmk_dev_site.relay.paths import get_site_workdir
from cmk_dev_site.relay.pods import deploy_pod, get_compose_file_path, stop_compose_services
from cmk_dev_site.relay.site import (
    Site,
    Version,
    delete_deployed_relays,
    get_site_name,
    get_version,
)
from cmk_dev_site.relay.types import ContainerConfig, RelayConfig
from cmk_dev_site.utils.log import get_logger

logger = get_logger(__name__)

SNMP_RELAY_ALIAS = "podman-relay"
HOST_RELAY_ALIAS = "host-relay"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--site",
        help="Site name (defaults to SITE env var or auto-detected)",
    )
    parser.add_argument(
        "--url",
        default="http://localhost",
        help="Base URL of the Checkmk server (default: http://localhost)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase verbosity (can be used multiple times: -v, -vv, -vvv)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="count",
        default=0,
        help="Decrease verbosity (can be used multiple times)",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    up_parser = subparsers.add_parser(
        "up",
        help="Create and start relay services",
        description="Create and start relay services for testing",
    )
    image_group = up_parser.add_mutually_exclusive_group(required=True)
    image_group.add_argument(
        "-b",
        "--build",
        action="store_const",
        const="build",
        dest="image_source",
        help="Build the relay image locally before deploying",
    )
    image_group.add_argument(
        "-d",
        "--dockerhub",
        action="store_const",
        const="download",
        dest="image_source",
        help="Use the DockerHub image matching your site version",
    )
    up_parser.set_defaults(func=cmd_up)

    down_parser = subparsers.add_parser(
        "down",
        help="Stop and remove relay services",
        description="Stop and remove relay services (keeps configs)",
    )
    down_parser.set_defaults(func=cmd_down)

    restart_parser = subparsers.add_parser(
        "restart",
        help="Restart relay services",
        description="Stop and recreate relay services",
    )
    restart_image_group = restart_parser.add_mutually_exclusive_group(required=True)
    restart_image_group.add_argument(
        "-b",
        "--build",
        action="store_const",
        const="build",
        dest="image_source",
        help="Build the relay image locally before deploying",
    )
    restart_image_group.add_argument(
        "-d",
        "--dockerhub",
        action="store_const",
        const="download",
        dest="image_source",
        help="Use the DockerHub image matching your site version",
    )
    restart_parser.set_defaults(func=cmd_restart)

    kill_parser = subparsers.add_parser(
        "kill",
        help="Force remove everything",
        description="Force remove all relay services, configs, hosts, and relays (keeps images)",
    )
    kill_parser.set_defaults(func=cmd_kill)

    ps_parser = subparsers.add_parser(
        "ps",
        help="List relay services",
        description="Show status of relay services for the site",
    )
    ps_parser.set_defaults(func=cmd_ps)

    logs_parser = subparsers.add_parser(
        "logs",
        help="Show relay logs",
        description="Show logs from relay containers",
    )
    logs_parser.add_argument(
        "relay_type",
        choices=["snmp", "host"],
        help="Relay type to show logs for (snmp or host)",
    )
    logs_parser.add_argument(
        "container",
        nargs="?",
        help="Specific container to show logs for: relay (default), init, or snmpd",
    )
    logs_parser.add_argument(
        "-f",
        "--follow",
        action="store_true",
        help="Follow log output",
    )
    logs_parser.add_argument(
        "-t",
        "--tail",
        type=int,
        default=50,
        help="Number of lines to show from the end of the logs (default: 50)",
    )
    logs_parser.set_defaults(func=cmd_logs)

    return parser.parse_args()


def ensure_sudo() -> None:
    """Refresh sudo privileges for cleanup operations."""
    import subprocess

    try:
        subprocess.run(["sudo", "-v"], check=True, capture_output=True)
    except subprocess.CalledProcessError:
        raise RuntimeError("Failed to acquire sudo privileges")


def clean_configs(site: Site) -> None:
    logger.info("Cleaning relay site directory...")
    site_workdir = get_site_workdir(site)
    if site_workdir.exists():
        # Docker containers create files as root, need sudo to remove
        ensure_sudo()
        import subprocess

        result = subprocess.run(
            ["sudo", "rm", "-rf", str(site_workdir)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"Failed to remove site directory: {result.stderr}")
        logger.debug(f"Removed site directory: {site_workdir}")


def deploy_pods(image_registry: str, image_tag: str, site: Site, version: Version) -> None:
    snmp_container = ContainerConfig(registry=image_registry, tag=image_tag)
    host_container = ContainerConfig(registry=image_registry, tag=image_tag)

    snmp_relay = RelayConfig(site=site, alias=SNMP_RELAY_ALIAS, container=snmp_container)
    host_relay = RelayConfig(site=site, alias=HOST_RELAY_ALIAS, container=host_container)

    deploy_pod("snmp", snmp_relay)
    deploy_pod("host", host_relay)

    write_metadata(
        site,
        image_registry,
        image_tag,
        version,
        relays=[
            ("snmp", SNMP_RELAY_ALIAS),
            ("host", HOST_RELAY_ALIAS),
        ],
    )


def _prepare_and_deploy(site: Site, image_source: Literal["build", "download"]) -> None:
    version = get_version(site)
    logger.info(f"Detected site version: {version}")

    match image_source:
        case "build":
            build_image(version)
            image_registry = "localhost"
            image_tag = "latest"
        case "download":
            image_registry = "docker.io/checkmk"
            image_tag = str(version)
            pull_images(image_registry, image_tag)
        case _:
            assert_never(image_source)

    deploy_pods(image_registry, image_tag, site, version)


def cmd_up(args: argparse.Namespace) -> int:
    site = Site(args.site) if args.site else get_site_name()
    logger.info(f"Starting relay services for site: {site}")
    _prepare_and_deploy(site, args.image_source)
    logger.info("Relay services successfully deployed")
    return 0


def cmd_down(args: argparse.Namespace) -> int:
    site = Site(args.site) if args.site else get_site_name()
    logger.info("Stopping and removing relay services...")
    stop_compose_services(get_compose_files_from_metadata(site))
    logger.info("Relay services stopped and removed")
    return 0


def cmd_restart(args: argparse.Namespace) -> int:
    site = Site(args.site) if args.site else get_site_name()
    logger.info("Stopping relay services...")
    stop_compose_services(get_compose_files_from_metadata(site))
    _prepare_and_deploy(site, args.image_source)
    return 0


def cmd_kill(args: argparse.Namespace) -> int:
    site = Site(args.site) if args.site else get_site_name()
    logger.info(
        f"Force removing all relay services, configs, hosts, and relays for site: {site}..."
    )
    delete_deployed_relays(site)
    stop_compose_services(get_compose_files_from_metadata(site))
    clean_configs(site)
    logger.info("All relay configs, containers, hosts, and relays removed (images preserved)")
    return 0


def cmd_ps(args: argparse.Namespace) -> int:
    site = Site(args.site) if args.site else get_site_name()

    # Read metadata to get relay info
    metadata = read_metadata(site)
    if not metadata:
        logger.info(f"No relay deployments found for site: {site}")
        return 0

    logger.info(f"Relay services for site: {site}")
    logger.info(f"Version: {metadata.version}")
    logger.info(f"Deployed: {metadata.deployed_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info("")

    # Get compose files
    compose_files = get_compose_files_from_metadata(site)

    # Check status for each relay
    for relay_info, compose_file in zip(metadata.relays, compose_files):
        logger.info(f"Relay: {relay_info.alias} ({relay_info.pod_type})")

        if not compose_file.exists():
            logger.info("  Status: Not deployed (compose file missing)")
            continue

        result = compose_ps(compose_file)
        if result.returncode != 0:
            logger.info(f"  Status: Error checking status - {result.stderr.strip()}")
            continue

        # Parse JSONL output (one JSON object per line)
        try:
            lines = result.stdout.strip().split("\n")
            containers = [json.loads(line) for line in lines if line.strip()]

            if not containers:
                logger.info("  Status: No containers running")
                continue

            # Display container status
            for container in containers:
                name = container.get("Name", "unknown")
                state = container.get("State", "unknown")
                status = container.get("Status", "")
                logger.info(f"  - {name}: {state} ({status})")
        except json.JSONDecodeError as e:
            logger.info(f"  Status: Could not parse container status - {e}")

        logger.info("")

    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    site = Site(args.site) if args.site else get_site_name()

    metadata = read_metadata(site)
    if not metadata:
        logger.error(f"No relay deployments found for site: {site}")
        return 1

    relay_info = next((r for r in metadata.relays if r.pod_type == args.relay_type), None)
    if not relay_info:
        logger.error(f"Relay type '{args.relay_type}' not found for site: {site}")
        return 1

    compose_file = get_compose_file_path(args.relay_type, str(site))
    if not compose_file.exists():
        logger.error(f"Compose file not found: {compose_file}")
        return 1

    container = args.container or "relay"

    service_map = {
        "relay": f"{args.relay_type}-relay",
        "init": f"{args.relay_type}-init-configs",
        "snmpd": "snmpd",
    }

    service_name = service_map.get(container, container)

    logger.info(f"Showing logs for {args.relay_type} relay - {container} container...")
    compose_logs(compose_file, follow=args.follow, tail=args.tail, service=service_name)
    return 0


def main() -> int:
    args = parse_arguments()

    log_level = max(logging.INFO - ((args.verbose - args.quiet) * 10), logging.DEBUG)
    logging.getLogger("cmk_dev_site").setLevel(log_level)

    try:
        return args.func(args)
    except RuntimeError as e:
        # Show clean error message without traceback unless in verbose mode
        if args.verbose > 0:
            raise
        logger.error(str(e))
        return 1
    except Exception as e:
        # For unexpected exceptions, always show some info
        if args.verbose > 0:
            raise
        logger.error(f"Unexpected error: {e}")
        logger.error("Run with -v for more details")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
