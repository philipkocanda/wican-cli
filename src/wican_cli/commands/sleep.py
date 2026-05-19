"""wican sleep — view or modify sleep/power saving settings."""

from __future__ import annotations

import argparse
import json

from wican_cli.client import WiCANError, handle_client_error
from wican_cli.commands._common import (
    confirm,
    flatten_config,
    get_client,
    positive_int,
    resolve_address,
    voltage_range,
)

SLEEP_KEYS = [
    "sleep_status",
    "sleep_disable_agree",
    "periodic_wakeup",
    "sleep_volt",
    "sleep_time",
    "wakeup_interval",
]

SLEEP_LABELS = {
    "sleep_status": "Sleep mode",
    "sleep_disable_agree": "Sleep disable confirmed",
    "periodic_wakeup": "Periodic wakeup",
    "sleep_volt": "Voltage threshold (V)",
    "sleep_time": "Sleep delay (min)",
    "wakeup_interval": "Wakeup interval (min)",
}


def cmd_sleep(args: argparse.Namespace) -> None:
    """View or modify sleep/power saving settings."""
    try:
        client = get_client(args)
        config = client.get_config()
    except WiCANError as e:
        handle_client_error(e)
        return

    flat = flatten_config(config)

    # Determine modifications
    changes: dict[str, str] = {}

    if args.enable:
        changes["sleep_status"] = "enable"
        changes["sleep_disable_agree"] = "no"
    elif args.disable:
        changes["sleep_status"] = "disable"
        changes["sleep_disable_agree"] = "yes"

    if args.voltage is not None:
        changes["sleep_volt"] = str(args.voltage)

    if args.time is not None:
        changes["sleep_time"] = str(args.time)

    if args.wakeup_interval is not None:
        changes["periodic_wakeup"] = "enable"
        changes["wakeup_interval"] = str(args.wakeup_interval)

    if args.no_wakeup:
        changes["periodic_wakeup"] = "disable"

    # JSON output mode
    if args.json:
        sleep_data = {k: flat.get(k, None) for k in SLEEP_KEYS}
        if changes:
            sleep_data["pending_changes"] = changes
        print(json.dumps(sleep_data, indent=2))
        if not changes:
            return
    else:
        # Display current status
        print("Sleep configuration:")
        max_label = max(len(v) for v in SLEEP_LABELS.values())
        for key in SLEEP_KEYS:
            label = SLEEP_LABELS.get(key, key)
            current = flat.get(key, "?")
            if key in changes and changes[key] != str(current):
                print(f"  {label:<{max_label}}  {current} -> {changes[key]}")
            else:
                print(f"  {label:<{max_label}}  {current}")

    if not changes:
        return

    # Check if anything actually changed
    effective_changes = {k: v for k, v in changes.items() if str(flat.get(k)) != v}
    if not effective_changes:
        if not args.json:
            print("\nNo changes needed — config already matches.")
        return

    if args.dry_run:
        if not args.json:
            print("\n[dry-run] Would apply changes and reboot device.")
        return

    # Confirm and apply
    base_url = resolve_address(args.wican)
    if not args.json:
        print(f"\nSaving config will reboot the device ({base_url})")
    if not args.yes and not confirm("Apply changes?"):
        print("Aborted.")
        return

    # Apply changes to full config and POST
    for key, val in effective_changes.items():
        flat[key] = val

    try:
        client.store_config(config)
    except WiCANError as e:
        handle_client_error(e)
        return
    if not args.json:
        print("Config saved. Device is rebooting...")


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the sleep subcommand."""
    p = subparsers.add_parser("sleep", help="View or modify sleep settings")
    p.add_argument("--json", action="store_true", help="JSON output")
    grp = p.add_mutually_exclusive_group()
    grp.add_argument("--enable", action="store_true", help="Enable sleep mode")
    grp.add_argument("--disable", action="store_true", help="Disable sleep mode")
    p.add_argument(
        "--voltage", type=voltage_range, metavar="V", help="Sleep voltage threshold (8.0-16.0 V)"
    )
    p.add_argument("--time", type=positive_int, metavar="MIN", help="Sleep delay in minutes")
    p.add_argument(
        "--wakeup-interval",
        type=positive_int,
        metavar="MIN",
        help="Periodic wakeup interval in minutes",
    )
    p.add_argument("--no-wakeup", action="store_true", help="Disable periodic wakeup")
    p.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    p.set_defaults(func=cmd_sleep)
