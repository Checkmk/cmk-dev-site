"""Podman CLI wrapper functions.

Implementation Note - Why subprocess instead of podman-py library:
=================================================================
This module uses subprocess calls to the podman CLI rather than the podman-py
Python library for the following reasons:

1. **Daemonless Operation**: The podman-py library requires a running podman
   socket service (podman.socket) which must be explicitly enabled via systemd.
   On Ubuntu and many other distributions, podman runs in daemonless mode by
   default, and enabling the socket defeats this design philosophy.

2. **Default Ubuntu Configuration**: Ubuntu's packaged podman does not start
   the socket by default. Requiring users to run
   `systemctl --user enable --now podman.socket` adds unnecessary setup steps.

3. **CLI is Always Available**: The podman CLI is the primary interface and
   works out of the box without any additional services or configuration.

4. **Simplicity**: Using subprocess with the CLI is more straightforward and
   has fewer failure modes than managing socket connections and API versioning.

If you're considering switching back to podman-py in the future, be aware that
you'll need to either:
  - Document that users must enable podman.socket first
  - Auto-detect and start the socket (which requires systemd on the host)
  - Handle both socket and non-socket modes gracefully
"""

import subprocess
from pathlib import Path


def pod_exists(pod_name: str) -> bool:
    result = subprocess.run(
        ["podman", "pod", "exists", pod_name],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def kill_pod(pod_name: str) -> None:
    subprocess.run(["podman", "pod", "stop", pod_name], check=False)
    subprocess.run(["podman", "pod", "rm", pod_name], check=False)


def play_kube(manifest_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["podman", "play", "kube", str(manifest_path)],
        capture_output=True,
        text=True,
        check=False,
    )


def pull_image(image: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["podman", "pull", image],
        capture_output=True,
        text=True,
        check=False,
    )
