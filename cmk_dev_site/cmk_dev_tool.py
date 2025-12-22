"""Wrapper tool that provides access to all cmk-dev-* tools."""

import argparse
import sys
from collections.abc import Callable
from typing import NoReturn

from cmk_dev_site.cmk_dev_install import main as install_main
from cmk_dev_site.cmk_dev_install_site import main as install_site_main
from cmk_dev_site.cmk_dev_site import main as site_main
from cmk_dev_site.saas.oidc_service import run as mock_auth_run

ToolInfo = dict[str, Callable[[], int | None] | str]

TOOLS: dict[str, ToolInfo] = {
    "install": {
        "main": install_main,
        "description": "Download and install Checkmk versions",
    },
    "site": {
        "main": site_main,
        "description": "Create and configure Checkmk sites",
    },
    "install-site": {
        "main": install_site_main,
        "description": "Install Checkmk and create a site in one step",
    },
    "site-mock-auth": {
        "main": mock_auth_run,
        "description": "Run mock OIDC authentication service",
    },
}


def main() -> NoReturn:
    """Main entrypoint for cmk-dev wrapper."""
    parser = argparse.ArgumentParser(
        prog="cmk-dev",
        description="Wrapper tool for all cmk-dev-* utilities",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=_build_tools_help(),
    )
    parser.add_argument(
        "tool",
        choices=list(TOOLS.keys()),
        help="The tool to run",
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to the tool",
    )

    args = parser.parse_args()

    # Replace argv with the tool's arguments
    sys.argv = [f"cmk-dev-{args.tool}", *args.args]

    # Run the selected tool
    tool_main = TOOLS[args.tool]["main"]
    assert callable(tool_main)
    result = tool_main()
    sys.exit(result if result is not None else 0)


def _build_tools_help() -> str:
    """Build the tools help section."""
    lines = ["Available tools:"]
    for name, info in TOOLS.items():
        lines.append(f"  {name:15} {info['description']}")
    return "\n".join(lines)


def get_all_tools() -> dict[str, ToolInfo]:
    """Return all available tools (used for testing)."""
    return TOOLS


if __name__ == "__main__":
    main()
