"""wican protocol — view or switch CAN protocol mode."""

from __future__ import annotations

import argparse
import json
import sys

from wican_cli.client import WiCANError, handle_client_error
from wican_cli.commands._common import confirm, flatten_config, get_client

# Protocol modes supported by WiCAN firmware.
PROTOCOLS = {
    "auto_pid": "AutoPID — automated parameter polling via MQTT/HA",
    "slcan": "SLCAN — serial CAN interface (SavvyCAN, canutils)",
    "elm327": "ELM327 — OBD-II terminal (Torque, Car Scanner)",
    "savvycan": "SavvyCAN GVRET — native SavvyCAN protocol",
    "realdash66": "RealDash Protocol 66 — RealDash CAN connection",
}

# Aliases for convenience (alias -> canonical name).
PROTOCOL_ALIASES = {
    "autopid": "auto_pid",
    "realdash": "realdash66",
}

# Per-protocol warnings shown when switching away from or to a protocol.
PROTOCOL_WARNINGS = {
    "auto_pid": "AutoPID will STOP — no more automated MQTT/Home Assistant data.",
    "slcan": "SLCAN uses a raw TCP socket (default port 3333).",
    "elm327": "ELM327 exposes an OBD-II terminal (TCP or UDP, default port 35000).",
    "savvycan": "SavvyCAN GVRET mode — only compatible with SavvyCAN client.",
    "realdash66": "RealDash Protocol 66 — only compatible with RealDash app.",
}


def _resolve_protocol(name: str) -> str:
    """Resolve a protocol name or alias to its canonical name."""
    lower = name.lower()
    return PROTOCOL_ALIASES.get(lower, lower)


def cmd_protocol(args: argparse.Namespace) -> None:
    """View or switch CAN protocol mode."""
    try:
        client = get_client(args)
        config = client.get_config()
    except WiCANError as e:
        handle_client_error(e)
        return

    flat = flatten_config(config)
    current = flat.get("protocol", "unknown")

    if not args.set:
        # Display current protocol
        if args.json:
            data = {
                "current": current,
                "description": PROTOCOLS.get(current, "unknown"),
                "available": list(PROTOCOLS.keys()),
                "aliases": PROTOCOL_ALIASES,
            }
            print(json.dumps(data, indent=2))
        else:
            print(f"Current protocol: {current}")
            if current in PROTOCOLS:
                print(f"  {PROTOCOLS[current]}")
            print()
            print("Available protocols:")
            for proto, desc in PROTOCOLS.items():
                marker = " *" if proto == current else "  "
                port_info = (
                    f"  (port {flat.get('port', '?')}/{flat.get('port_type', '?')})"
                    if proto == current
                    else ""
                )
                print(f"  {marker} {proto:<12} {desc}{port_info}")
            aliases_str = ", ".join(f"{a}->{c}" for a, c in PROTOCOL_ALIASES.items())
            print(f"\n  Aliases: {aliases_str}")
            if current in PROTOCOLS:
                can_mode = flat.get("can_mode", "?")
                print(f"\n  CAN mode: {can_mode}")
        return

    target = _resolve_protocol(args.set)
    if target not in PROTOCOLS:
        print(f"ERROR: Unknown protocol '{args.set}'", file=sys.stderr)
        all_names = list(PROTOCOLS.keys()) + list(PROTOCOL_ALIASES.keys())
        print(f"  Available: {', '.join(all_names)}", file=sys.stderr)
        sys.exit(1)

    if target == current:
        if args.json:
            print(json.dumps({"status": "no_change", "protocol": current}))
        else:
            print(f"Already in {target} mode — no change needed.")
        return

    # Build changes
    changes: dict[str, str] = {"protocol": target}

    if args.port:
        changes["port"] = str(args.port)
    if args.port_type:
        changes["port_type"] = args.port_type
    if args.can_mode:
        changes["can_mode"] = args.can_mode

    if not args.json:
        print(f"Switching protocol: {current} -> {target}")
        print(f"  {PROTOCOLS[target]}")
        print()
        # Show per-protocol warnings
        if current in PROTOCOL_WARNINGS:
            print(f"  ⚠ Leaving {current}: {PROTOCOL_WARNINGS[current]}")
        if target in PROTOCOL_WARNINGS:
            print(f"  → Entering {target}: {PROTOCOL_WARNINGS[target]}")
        print()
        print("  Note: Protocols are mutually exclusive — only one can be active.")
        print("  Device will reboot to apply the change.")
        print()

        # Show diff
        print("Changes:")
        for key, new_val in changes.items():
            old_val = flat.get(key, "")
            if str(old_val) != new_val:
                print(f"  {key}: {old_val} -> {new_val}")

    if args.dry_run:
        if args.json:
            print(json.dumps({"status": "dry_run", "changes": changes}))
        else:
            print("\n(dry run — no changes applied)")
        return

    if not args.json:
        print()
    if not args.yes and not confirm("Apply and reboot?"):
        print("Cancelled.")
        return

    # Apply
    for key, val in changes.items():
        flat[key] = val

    if not args.json:
        print("Storing config...", end=" ", flush=True)
    try:
        client.store_config(config)
    except WiCANError as e:
        handle_client_error(e)
        return
    if args.json:
        print(json.dumps({"status": "applied", "protocol": target}))
    else:
        print("device is rebooting.")


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the protocol subcommand."""
    p = subparsers.add_parser("protocol", help="View or switch CAN protocol mode")
    p.add_argument("--json", action="store_true", help="JSON output")
    p.add_argument(
        "--set",
        metavar="MODE",
        help="Switch to protocol: "
        f"{', '.join(PROTOCOLS.keys())} (aliases: {', '.join(PROTOCOL_ALIASES.keys())})",
    )
    p.add_argument("--port", type=int, metavar="PORT", help="TCP/UDP port number")
    p.add_argument("--port-type", choices=["tcp", "udp"], help="Port type: tcp or udp")
    p.add_argument(
        "--can-mode",
        choices=["normal", "silent"],
        help="CAN mode: normal (read/write) or silent (read-only)",
    )
    p.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    p.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    p.set_defaults(func=cmd_protocol)
