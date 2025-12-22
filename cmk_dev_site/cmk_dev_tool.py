"""Wrapper tool that provides access to all cmk-dev-* tools."""

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass
from typing import NoReturn

from cmk_dev_site.cmk_dev_install import main as install_main
from cmk_dev_site.cmk_dev_install_site import main as install_site_main
from cmk_dev_site.cmk_dev_site import main as site_main
from cmk_dev_site.saas.oidc_service import run as mock_auth_run


@dataclass(frozen=True)
class ToolInfo:
    description: str
    main: Callable[[], int | None]


TOOLS: dict[str, ToolInfo] = {
    "install": ToolInfo(
        description="Download and install Checkmk versions",
        main=install_main,
    ),
    "site": ToolInfo(
        description="Create and configure Checkmk sites",
        main=site_main,
    ),
    "install-site": ToolInfo(
        description="Install Checkmk and create a site in one step",
        main=install_site_main,
    ),
    "site-mock-auth": ToolInfo(
        description="Run mock OIDC authentication service",
        main=mock_auth_run,
    ),
}


def main() -> NoReturn:
    """Main entrypoint for cmk-dev wrapper."""
    parser = argparse.ArgumentParser(
        prog="cmk-dev",
        description="Wrapper tool for all cmk-dev-* utilities",
    )
    subparsers = parser.add_subparsers(
        dest="tool",
        required=True,
        help="Available tools",
    )

    for name, info in TOOLS.items():
        subparsers.add_parser(
            name,
            help=info.description,
            add_help=False,  # Let the actual tool handle --help
        )

    # Parse only the tool name, keep remaining args for the tool
    args, remaining = parser.parse_known_args()

    # Replace argv with the tool's arguments
    sys.argv = [f"cmk-dev-{args.tool}", *remaining]

    # Run the selected tool
    result = TOOLS[args.tool].main()
    sys.exit(result if result is not None else 0)


def get_all_tools() -> dict[str, ToolInfo]:
    """Return all available tools (used for testing)."""
    return TOOLS


if __name__ == "__main__":
    main()
