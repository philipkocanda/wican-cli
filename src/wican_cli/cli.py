"""WiCAN CLI — command-line interface for managing WiCAN Pro devices.

Entry point: `wican` (installed via pip) or `python -m wican_cli`.
"""

from __future__ import annotations

import argparse

import argcomplete

from wican_cli.commands import ALL_REGISTERS
from wican_cli.commands._common import DEFAULT_TIMEOUT
from wican_cli.config import get_wican_addresses


def main() -> None:
    """CLI entry point."""
    try:
        addresses, default = get_wican_addresses()
    except ValueError as e:
        import sys

        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        prog="wican",
        description="WiCAN CLI — manage WiCAN Pro OBD-II devices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--use",
        default=None,
        metavar="ADDR",
        help=f"Device address: {', '.join(addresses.keys())} or IP/URL (default: {default})",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Request timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    for register in ALL_REGISTERS:
        register(sub)

    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    args.func(args)


def _get_version() -> str:
    """Return package version."""
    from wican_cli import __version__

    return __version__
