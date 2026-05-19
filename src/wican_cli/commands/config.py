"""wican config — download and display device configuration."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from wican_cli.client import WiCANError, handle_client_error
from wican_cli.commands._common import flatten_config, get_client, warn
from wican_cli.redact import redact_config

# Config sections for --section filter.
CONFIG_SECTIONS = {
    "sleep": [
        "sleep_status",
        "sleep_disable_agree",
        "periodic_wakeup",
        "sleep_volt",
        "sleep_time",
        "wakeup_interval",
    ],
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


def cmd_config(args: argparse.Namespace) -> None:
    """Download and display device configuration."""
    try:
        client = get_client(args)
        config = client.get_config()
    except WiCANError as e:
        handle_client_error(e)
        return

    flat = flatten_config(config)

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
            warn(
                "Saving config with plaintext credentials. Use --redact to strip sensitive fields."
            )
        with open(path, "w") as f:
            json.dump(output, f, indent=2)
            f.write("\n")
        print(f"\nSaved to {path}{suffix}")


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the config subcommand."""
    p = subparsers.add_parser("config", help="View device configuration")
    p.add_argument(
        "--section",
        metavar="NAME",
        help=f"Filter to section: {', '.join(CONFIG_SECTIONS.keys())}",
    )
    p.add_argument("--json", action="store_true", help="Raw JSON output")
    p.add_argument("--save", action="store_true", help="Save snapshot to configs/ directory")
    p.add_argument(
        "--redact", action="store_true", help="Redact credentials in saved snapshot"
    )
    p.add_argument(
        "--output-dir",
        "-o",
        metavar="DIR",
        help="Directory for saved snapshots (default: ./configs)",
    )
    p.set_defaults(func=cmd_config)
