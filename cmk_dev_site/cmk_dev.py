"""
script entrypoint for cmk-dev
"""

import argparse

from .cmk_dev_install import execute as execute_install
from .cmk_dev_install import setup_parser as setup_parser_install
from .cmk_dev_site import execute as execute_site
from .cmk_dev_site import setup_parser as setup_parser_site
from .shortcut import execute as execute_shortcut
from .shortcut import setup_parser as setup_parser_shortcut
from .version import __version__


def cmk_dev_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collection of tools used by Checkmk developers",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=__version__)

    subparsers = parser.add_subparsers()

    parser_site = subparsers.add_parser(
        "site",
        description="Create a Checkmk site",
        help="Create a Checkmk site",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    setup_parser_site(parser_site)
    parser_site.set_defaults(func=execute_site)

    parser_install = subparsers.add_parser(
        "install",
        description="Download and install Checkmk package",
        help="Download and install Checkmk package",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    setup_parser_install(parser_install)
    parser_install.set_defaults(func=execute_install)

    parser_shortcut = subparsers.add_parser(
        "install-site",
        description="Shortcut for both installing and setting up the site",
        help="Run install and site in one command",
        aliases=["is"],
    )
    setup_parser_shortcut(parser_shortcut)
    parser_shortcut.set_defaults(func=execute_shortcut)

    return parser


def main() -> int:
    parser: argparse.ArgumentParser = cmk_dev_argument_parser()
    args = parser.parse_args()
    return args.func(args)
