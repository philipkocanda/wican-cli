"""wican reboot — reboot the WiCAN device."""

from __future__ import annotations

import argparse

from wican_cli.client import WiCANError, handle_client_error
from wican_cli.commands._common import confirm, get_client, resolve_address


def cmd_reboot(args: argparse.Namespace) -> None:
    """Reboot the WiCAN device."""
    base_url = resolve_address(args.wican)
    print(f"Rebooting WiCAN at {base_url}")
    if not args.yes and not confirm("Continue?"):
        print("Aborted.")
        return

    try:
        client = get_client(args)
        client.reboot()
    except WiCANError as e:
        handle_client_error(e)
        return
    print("Reboot command sent.")


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the reboot subcommand."""
    p = subparsers.add_parser("reboot", help="Reboot the device")
    p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    p.set_defaults(func=cmd_reboot)
