"""wican autopid — show latest AutoPID cached values."""

from __future__ import annotations

import argparse
import json

from wican_cli.client import WiCANError, handle_client_error
from wican_cli.commands._common import get_client


def cmd_autopid(args: argparse.Namespace) -> None:
    """Show latest AutoPID cached values."""
    try:
        client = get_client(args)
        values = client.get_autopid_values()
    except WiCANError as e:
        handle_client_error(e)
        return

    # Filter if requested
    if args.filter:
        pattern = args.filter.lower()
        values = {k: v for k, v in values.items() if pattern in k.lower()}

    if args.json:
        print(json.dumps(values, indent=2))
    else:
        if not values:
            print("No AutoPID values available.")
        else:
            max_key = max(len(k) for k in values)
            for key, value in sorted(values.items()):
                print(f"  {key:<{max_key}}  {value}")


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the autopid subcommand."""
    p = subparsers.add_parser(
        "autopid", aliases=["pids"], help="Show latest AutoPID cached values"
    )
    p.add_argument("--json", action="store_true", help="Raw JSON output")
    p.add_argument("--filter", "-f", metavar="PATTERN", help="Filter parameters by name")
    p.set_defaults(func=cmd_autopid)
