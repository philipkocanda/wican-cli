"""WiCAN CLI — command-line interface for managing WiCAN Pro devices.

Entry point: `wican` (installed via pip) or `python -m wican_cli`.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from wican_cli.client import WiCANClient, WiCANError, handle_client_error, make_client
from wican_cli.config import get_wican_addresses
from wican_cli.redact import redact_config

# ── Constants ──────────────────────────────────────────────────────────────

DEFAULT_TIMEOUT = 10  # seconds

# Protocol modes supported by WiCAN firmware.
PROTOCOLS = {
    "auto_pid": "AutoPID — automated parameter polling via MQTT/HA",
    "slcan": "SLCAN — serial CAN interface (SavvyCAN, canutils)",
    "elm327": "ELM327 — OBD-II terminal (Torque, Car Scanner)",
    "savvycan": "SavvyCAN GVRET — native SavvyCAN protocol",
    "realdash66": "RealDash Protocol 66 — RealDash CAN connection",
}

# Sleep-related config keys.
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

# Config sections for --section filter.
CONFIG_SECTIONS = {
    "sleep": SLEEP_KEYS,
    "battery_alert": [
        "batt_alert",
        "batt_alert_ssid",
        "batt_alert_pass",
        "batt_alert_volt",
        "batt_alert_protocol",
        "batt_alert_url",
        "batt_alert_port",
        "batt_alert_topic",
        "batt_alert_time",
        "batt_mqtt_user",
        "batt_mqtt_pass",
    ],
    "mqtt": [
        "mqtt_en",
        "mqtt_url",
        "mqtt_port",
        "mqtt_user",
        "mqtt_pass",
        "mqtt_tx_topic",
        "mqtt_rx_topic",
        "mqtt_status_topic",
    ],
    "wifi": [
        "sta_ssid",
        "sta_pass",
        "ap_pass",
        "ble_pass",
        "sta_fallbacks",
    ],
    "protocol": [
        "protocol",
        "port",
        "port_type",
    ],
}


# ── Utilities ──────────────────────────────────────────────────────────────


def _warn(msg: str) -> None:
    """Print a yellow warning message to stderr."""
    is_tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    if is_tty:
        print(f"\033[1;33mWARNING:\033[0m {msg}", file=sys.stderr)
    else:
        print(f"WARNING: {msg}", file=sys.stderr)


def _confirm(prompt: str) -> bool:
    """Ask user for y/n confirmation."""
    try:
        answer = input(f"{prompt} [y/N] ").strip().lower()
        return answer in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        print()
        return False


def _resolve_address(wican_arg: str) -> str:
    """Resolve a --wican argument to a base URL."""
    addresses, _ = get_wican_addresses()
    if wican_arg in addresses:
        addr = addresses[wican_arg]
    else:
        addr = wican_arg
    if not addr.startswith(("http://", "https://")):
        return f"http://{addr}"
    return addr


def _get_client(args: argparse.Namespace) -> WiCANClient:
    """Create a WiCANClient from parsed CLI arguments."""
    url = _resolve_address(args.wican)
    return make_client(url, timeout=args.timeout)


def _flatten_config(config: dict) -> dict:
    """If config has a nested 'config' key, return that sub-dict."""
    if "config" in config and isinstance(config["config"], dict):
        return config["config"]
    return config


# ── Subcommands ────────────────────────────────────────────────────────────


def cmd_config(args: argparse.Namespace) -> None:
    """Download and display device configuration."""
    try:
        client = _get_client(args)
        config = client.get_config()
    except WiCANError as e:
        handle_client_error(e)
        return

    flat = _flatten_config(config)

    # Filter to section if requested
    if args.section:
        section = args.section.lower()
        if section not in CONFIG_SECTIONS:
            print(f"ERROR: Unknown section '{section}'", file=sys.stderr)
            print(f"  Available: {', '.join(CONFIG_SECTIONS.keys())}", file=sys.stderr)
            sys.exit(1)
        keys = CONFIG_SECTIONS[section]
        flat = {k: v for k, v in flat.items() if k in keys}

    if args.json:
        print(json.dumps(flat, indent=2))
    else:
        if not flat:
            print("  (empty)")
        else:
            max_key = max(len(k) for k in flat)
            for key, value in flat.items():
                print(f"  {key:<{max_key}}  {value}")

    # Save snapshot
    if args.save:
        save_dir = Path(args.output_dir) if args.output_dir else Path.cwd() / "configs"
        save_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d")
        path = save_dir / f"config_{timestamp}.json"
        # Never overwrite — add incremental suffix if file exists
        if path.exists():
            n = 2
            while True:
                path = save_dir / f"config_{timestamp}-{n}.json"
                if not path.exists():
                    break
                n += 1
        if args.redact:
            output = redact_config(config)
            suffix = " (credentials redacted)"
        else:
            output = config
            suffix = ""
            _warn(
                "Saving config with plaintext credentials. "
                "Use --redact to strip sensitive fields."
            )
        with open(path, "w") as f:
            json.dump(output, f, indent=2)
            f.write("\n")
        print(f"\nSaved to {path}{suffix}")


def cmd_sleep(args: argparse.Namespace) -> None:
    """View or modify sleep/power saving settings."""
    try:
        client = _get_client(args)
        config = client.get_config()
    except WiCANError as e:
        handle_client_error(e)
        return

    flat = _flatten_config(config)

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
        print("\nNo changes needed — config already matches.")
        return

    if args.dry_run:
        print("\n[dry-run] Would apply changes and reboot device.")
        return

    # Confirm and apply
    base_url = _resolve_address(args.wican)
    print(f"\nSaving config will reboot the device ({base_url})")
    if not args.yes and not _confirm("Apply changes?"):
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
    print("Config saved. Device is rebooting...")


def cmd_status(args: argparse.Namespace) -> None:
    """Show device status summary."""
    try:
        client = _get_client(args)
        status = client.get_status()
    except WiCANError as e:
        handle_client_error(e)
        return

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        max_key = max(len(k) for k in status) if status else 0
        for key, value in status.items():
            print(f"  {key:<{max_key}}  {value}")


def cmd_reboot(args: argparse.Namespace) -> None:
    """Reboot the WiCAN device."""
    base_url = _resolve_address(args.wican)
    print(f"Rebooting WiCAN at {base_url}")
    if not args.yes and not _confirm("Continue?"):
        print("Aborted.")
        return

    try:
        client = _get_client(args)
        client.reboot()
    except WiCANError as e:
        handle_client_error(e)
        return
    print("Reboot command sent.")


def cmd_protocol(args: argparse.Namespace) -> None:
    """View or switch CAN protocol mode."""
    try:
        client = _get_client(args)
        config = client.get_config()
    except WiCANError as e:
        handle_client_error(e)
        return

    flat = _flatten_config(config)
    current = flat.get("protocol", "unknown")

    if not args.set:
        # Display current protocol
        print(f"Current protocol: {current}")
        if current in PROTOCOLS:
            print(f"  {PROTOCOLS[current]}")
        print(f"\nAvailable: {', '.join(PROTOCOLS.keys())}")
        return

    target = args.set.lower()
    if target not in PROTOCOLS:
        print(f"ERROR: Unknown protocol '{target}'", file=sys.stderr)
        print(f"  Available: {', '.join(PROTOCOLS.keys())}", file=sys.stderr)
        sys.exit(1)

    if target == current:
        print(f"Already in {target} mode — no change needed.")
        return

    # Build changes
    changes: dict[str, str] = {"protocol": target}
    port = flat.get("port", "3333")

    if args.port:
        changes["port"] = str(args.port)
    if args.port_type:
        changes["port_type"] = args.port_type
    if args.can_mode:
        changes["can_mode"] = args.can_mode

    print(f"Switching protocol: {current} -> {target}")
    print(f"  {PROTOCOLS[target]}")
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
        print("\n(dry run — no changes applied)")
        return

    print()
    if not args.yes and not _confirm("Apply and reboot?"):
        print("Cancelled.")
        return

    # Apply
    for key, val in changes.items():
        flat[key] = val

    print("Storing config...", end=" ", flush=True)
    try:
        client.store_config(config)
    except WiCANError as e:
        handle_client_error(e)
        return
    print("device is rebooting.")


def cmd_logs(args: argparse.Namespace) -> None:
    """List, download, or query OBD log databases."""
    try:
        client = _get_client(args)
    except WiCANError as e:
        handle_client_error(e)
        return

    if args.download:
        _cmd_logs_download(client, args)
    elif args.query:
        _cmd_logs_query(client, args)
    elif args.params:
        _cmd_logs_params(client, args)
    else:
        _cmd_logs_list(client, args)


def _cmd_logs_list(client: WiCANClient, args: argparse.Namespace) -> None:
    """List available log databases."""
    try:
        files = client.list_files()
    except WiCANError as e:
        handle_client_error(e)
        return

    if args.json:
        print(json.dumps(files, indent=2))
    else:
        if not files:
            print("No log files found on device.")
        else:
            print(f"Log files ({len(files)}):")
            for f in files:
                print(f"  {f}")


def _cmd_logs_download(client: WiCANClient, args: argparse.Namespace) -> None:
    """Download log databases from the device."""
    logs_dir = Path.cwd() / "logs"
    logs_dir.mkdir(exist_ok=True)

    try:
        files = client.list_files()
    except WiCANError as e:
        handle_client_error(e)
        return

    if args.db:
        files = [f for f in files if f == args.db]
        if not files:
            print(f"ERROR: File '{args.db}' not found on device.", file=sys.stderr)
            sys.exit(1)

    for filename in files:
        dest = logs_dir / filename
        if dest.exists() and not args.force:
            print(f"  Skip {filename} (exists, use --force to overwrite)")
            continue
        print(f"  Downloading {filename}...", end=" ", flush=True)
        try:
            data = client.download_file(filename)
        except WiCANError as e:
            print(f"FAILED: {e}")
            continue
        with open(dest, "wb") as f:
            f.write(data)
        print(f"OK ({len(data)} bytes)")


def _cmd_logs_query(client: WiCANClient, args: argparse.Namespace) -> None:
    """Query a parameter from the latest log database."""
    try:
        files = client.list_files()
    except WiCANError as e:
        handle_client_error(e)
        return

    db_files = [f for f in files if f.endswith(".db")]
    if not db_files:
        print("No .db files found on device.", file=sys.stderr)
        sys.exit(1)

    # Use specified DB or latest
    target = args.db if args.db else db_files[-1]

    # Download to temp file
    try:
        data = client.download_file(target)
    except WiCANError as e:
        handle_client_error(e)
        return

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        conn = sqlite3.connect(tmp_path)
        cursor = conn.execute(
            "SELECT timestamp, value FROM obd_data WHERE name = ? ORDER BY timestamp DESC LIMIT ?",
            (args.query, args.limit),
        )
        rows = cursor.fetchall()
        conn.close()
    except sqlite3.Error as e:
        print(f"ERROR: Database query failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if not rows:
        print(f"No data found for parameter '{args.query}' in {target}")
        return

    if args.json:
        print(json.dumps([{"timestamp": ts, "value": val} for ts, val in rows], indent=2))
    else:
        print(f"Parameter: {args.query} (from {target}, last {len(rows)} values)")
        for ts, val in rows:
            print(f"  {ts}  {val}")


def _cmd_logs_params(client: WiCANClient, args: argparse.Namespace) -> None:
    """List all logged parameter names."""
    try:
        files = client.list_files()
    except WiCANError as e:
        handle_client_error(e)
        return

    db_files = [f for f in files if f.endswith(".db")]
    if not db_files:
        print("No .db files found on device.", file=sys.stderr)
        sys.exit(1)

    target = args.db if args.db else db_files[-1]

    try:
        data = client.download_file(target)
    except WiCANError as e:
        handle_client_error(e)
        return

    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        conn = sqlite3.connect(tmp_path)
        cursor = conn.execute("SELECT DISTINCT name FROM obd_data ORDER BY name")
        params = [row[0] for row in cursor.fetchall()]
        conn.close()
    except sqlite3.Error as e:
        print(f"ERROR: Database query failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    if args.json:
        print(json.dumps(params, indent=2))
    else:
        print(f"Logged parameters ({len(params)}, from {target}):")
        for p in params:
            print(f"  {p}")


def cmd_autopid(args: argparse.Namespace) -> None:
    """Show latest AutoPID cached values."""
    try:
        client = _get_client(args)
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


# ── Argument parsing ──────────────────────────────────────────────────────


def main() -> None:
    """CLI entry point."""
    addresses, default = get_wican_addresses()

    parser = argparse.ArgumentParser(
        prog="wican",
        description="WiCAN CLI — manage WiCAN Pro OBD-II devices",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--wican",
        default=default,
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

    # ── config ──
    p_config = sub.add_parser("config", help="View device configuration")
    p_config.add_argument(
        "--section",
        metavar="NAME",
        help=f"Filter to section: {', '.join(CONFIG_SECTIONS.keys())}",
    )
    p_config.add_argument("--json", action="store_true", help="Raw JSON output")
    p_config.add_argument(
        "--save", action="store_true", help="Save snapshot to configs/ directory"
    )
    p_config.add_argument(
        "--redact", action="store_true", help="Redact credentials in saved snapshot"
    )
    p_config.add_argument(
        "--output-dir", "-o", metavar="DIR", help="Directory for saved snapshots (default: ./configs)"
    )
    p_config.set_defaults(func=cmd_config)

    # ── sleep ──
    p_sleep = sub.add_parser("sleep", help="View or modify sleep settings")
    grp = p_sleep.add_mutually_exclusive_group()
    grp.add_argument("--enable", action="store_true", help="Enable sleep mode")
    grp.add_argument("--disable", action="store_true", help="Disable sleep mode")
    p_sleep.add_argument(
        "--voltage", type=float, metavar="V", help="Sleep voltage threshold (e.g. 12.5)"
    )
    p_sleep.add_argument("--time", type=int, metavar="MIN", help="Sleep delay in minutes")
    p_sleep.add_argument(
        "--wakeup-interval", type=int, metavar="MIN", help="Periodic wakeup interval in minutes"
    )
    p_sleep.add_argument("--no-wakeup", action="store_true", help="Disable periodic wakeup")
    p_sleep.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    p_sleep.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    p_sleep.set_defaults(func=cmd_sleep)

    # ── status ──
    p_status = sub.add_parser("status", help="Device status summary")
    p_status.add_argument("--json", action="store_true", help="Raw JSON output")
    p_status.set_defaults(func=cmd_status)

    # ── reboot ──
    p_reboot = sub.add_parser("reboot", help="Reboot the device")
    p_reboot.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    p_reboot.set_defaults(func=cmd_reboot)

    # ── logs ──
    p_logs = sub.add_parser("logs", help="List, download, or query OBD log databases")
    p_logs.add_argument(
        "--download", action="store_true", help="Download log databases to logs/ directory"
    )
    p_logs.add_argument("--db", metavar="FILE", help="Specific database filename")
    p_logs.add_argument(
        "--force", action="store_true", help="Overwrite existing files on download"
    )
    p_logs.add_argument("--params", action="store_true", help="List all logged parameters")
    p_logs.add_argument("--query", metavar="PARAM", help="Query a parameter (e.g. SOC_BMS)")
    p_logs.add_argument(
        "--limit", type=int, default=10, help="Number of rows to return (default: 10)"
    )
    p_logs.add_argument("--json", action="store_true", help="JSON output")
    p_logs.set_defaults(func=cmd_logs)

    # ── protocol ──
    p_proto = sub.add_parser("protocol", help="View or switch CAN protocol mode")
    p_proto.add_argument(
        "--set", metavar="MODE", help=f"Switch to protocol: {', '.join(PROTOCOLS.keys())}"
    )
    p_proto.add_argument(
        "--port", type=int, metavar="PORT", help="TCP/UDP port number"
    )
    p_proto.add_argument("--port-type", choices=["tcp", "udp"], help="Port type: tcp or udp")
    p_proto.add_argument(
        "--can-mode",
        choices=["normal", "silent"],
        help="CAN mode: normal (read/write) or silent (read-only)",
    )
    p_proto.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    p_proto.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompt")
    p_proto.set_defaults(func=cmd_protocol)

    # ── autopid ──
    p_autopid = sub.add_parser(
        "autopid", aliases=["pids"], help="Show latest AutoPID cached values"
    )
    p_autopid.add_argument("--json", action="store_true", help="Raw JSON output")
    p_autopid.add_argument(
        "--filter", "-f", metavar="PATTERN", help="Filter parameters by name"
    )
    p_autopid.set_defaults(func=cmd_autopid)

    args = parser.parse_args()
    args.func(args)


def _get_version() -> str:
    """Return package version."""
    from wican_cli import __version__

    return __version__
