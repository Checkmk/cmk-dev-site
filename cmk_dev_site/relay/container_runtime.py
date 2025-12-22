"""Docker/Podman CLI wrapper functions.

This module uses subprocess calls to docker/podman CLI. It detects which
container runtime is available and uses that. Both docker and podman support
the docker-compose format via their respective compose commands.

Podman users can use podman-compose or the podman docker wrapper.
"""

import shutil
import subprocess
from functools import cache
from pathlib import Path


@cache
def _get_compose_command() -> list[str]:
    """Detect and return the appropriate compose command.

    Priority order:
    1. docker compose (Docker with built-in compose plugin)
    2. podman compose (Podman with built-in compose support)
    """
    if shutil.which("docker"):
        result = subprocess.run(
            ["docker", "compose", "version"],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return ["docker", "compose"]

    if shutil.which("podman"):
        result = subprocess.run(
            ["podman", "compose", "version"],
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return ["podman", "compose"]

    raise RuntimeError(
        "No container compose tool found. Please install one of:\n"
        "  - docker with compose plugin (docker compose)\n"
        "  - podman with compose support (podman compose)\n"
    )


def compose_up(compose_file: Path) -> subprocess.CompletedProcess[str]:
    cmd = _get_compose_command()
    return subprocess.run(
        [*cmd, "-f", str(compose_file), "up", "-d"],
        capture_output=True,
        text=True,
        check=False,
    )


def compose_down(compose_file: Path) -> subprocess.CompletedProcess[str]:
    """Stop and remove services defined in compose file."""
    cmd = _get_compose_command()
    return subprocess.run(
        [*cmd, "-f", str(compose_file), "down"],
        capture_output=True,
        text=True,
        check=False,
    )


def compose_ps(compose_file: Path) -> subprocess.CompletedProcess[str]:
    cmd = _get_compose_command()
    return subprocess.run(
        [*cmd, "-f", str(compose_file), "ps", "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )


def compose_logs(
    compose_file: Path, follow: bool = False, tail: int = 50, service: str | None = None
) -> None:
    """Show logs from containers in compose file.

    Streams logs directly to stdout/stderr. For follow mode, runs until interrupted.
    """
    cmd = _get_compose_command()
    args = [*cmd, "-f", str(compose_file), "logs", "--tail", str(tail)]
    if follow:
        args.append("--follow")
    if service:
        args.append(service)

    subprocess.run(args, check=False)


def pull_image(image: str) -> subprocess.CompletedProcess[str]:
    if shutil.which("docker"):
        cmd = ["docker", "pull", image]
    elif shutil.which("podman"):
        cmd = ["podman", "pull", image]
    else:
        raise RuntimeError("Neither docker nor podman found")

    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=False,
    )
