"""wican status — show device status summary."""

from __future__ import annotations

import argparse
import json

from wican_cli.client import WiCANError, handle_client_error
from wican_cli.commands._common import get_client


def _format_status(status: dict) -> str:
    """Format device status into grouped, human-readable sections."""

    def _get(key: str, fallback: str = "-") -> str:
        val = status.get(key, "")
        return val if val else fallback

    def _wifi_mode(raw: str) -> str:
        modes = {"1": "Station", "2": "AP", "3": "AP+Station"}
        return modes.get(raw, raw)

    def _with_suffix(val: str, suffix: str) -> str:
        if val == "-" or val.endswith(suffix):
            return val
        return f"{val}{suffix}"

    # Build computed fields
    firmware = _get("fw_version")
    git = _get("git_version", "")
    firmware_display = f"{firmware} ({git})" if git and git != "-" else firmware

    mqtt_url = _get("mqtt_url", "")
    mqtt_port = _get("mqtt_port", "")
    if mqtt_url and mqtt_port:
        if "://" in mqtt_url:
            broker_display = f"{mqtt_url}:{mqtt_port}"
        else:
            broker_display = f"mqtt://{mqtt_url}:{mqtt_port}"
    elif mqtt_url:
        broker_display = mqtt_url
    else:
        broker_display = "-"

    sleep_volt = _get("sleep_volt")
    sleep_volt_display = _with_suffix(sleep_volt, "V")

    sleep_time = _get("sleep_time")
    sleep_time_display = _with_suffix(sleep_time, " min")

    wakeup_interval = _get("wakeup_interval")
    wakeup_interval_display = _with_suffix(wakeup_interval, " min")

    wakeup_volt = _get("wakeup_volt")
    wakeup_volt_display = _with_suffix(wakeup_volt, "V")

    batt_voltage = _get("batt_voltage")
    batt_display = _with_suffix(batt_voltage, "V")

    log_period = _get("log_period")
    log_period_display = _with_suffix(log_period, "s")

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        (
            "Device",
            [
                ("Hardware", _get("hw_version")),
                ("Firmware", firmware_display),
                ("Device ID", _get("device_id")),
                ("Uptime", _get("uptime")),
                ("Battery", batt_display),
            ],
        ),
        (
            "Network",
            [
                ("WiFi mode", _wifi_mode(_get("wifi_mode"))),
                ("WiFi status", _get("sta_status")),
                ("IP address", _get("sta_ip")),
                ("mDNS", _get("mdns")),
                ("VPN status", _get("vpn_status")),
                ("VPN IP", _get("vpn_ip")),
            ],
        ),
        (
            "CAN / OBD",
            [
                ("Protocol", _get("protocol")),
                ("CAN datarate", _get("can_datarate")),
                ("CAN mode", _get("can_mode")),
                ("OBD chip", _get("obd_chip_status")),
                ("ECU status", _get("ecu_status")),
            ],
        ),
        (
            "Power",
            [
                ("Sleep mode", _get("sleep_status")),
                ("Sleep voltage", sleep_volt_display),
                ("Sleep delay", sleep_time_display),
                ("Periodic wakeup", _get("periodic_wakeup")),
                ("Wakeup interval", wakeup_interval_display),
                ("Wakeup voltage", wakeup_volt_display),
            ],
        ),
        (
            "MQTT",
            [
                ("Enabled", _get("mqtt_en")),
                ("Broker", broker_display),
                ("Status topic", _get("mqtt_status_topic")),
            ],
        ),
        (
            "Logging",
            [
                ("SD logging", _get("logger_status")),
                ("Period", log_period_display),
                ("IMU threshold", _get("imu_threshold")),
            ],
        ),
    ]

    lines: list[str] = []
    for i, (title, fields) in enumerate(sections):
        if i > 0:
            lines.append("")
        lines.append(f"  {title}")
        max_label = max(len(label) for label, _ in fields)
        for label, value in fields:
            lines.append(f"    {label:<{max_label}}  {value}")
    return "\n".join(lines)


def cmd_status(args: argparse.Namespace) -> None:
    """Show device status summary."""
    try:
        client = get_client(args)
        status = client.get_status()
    except WiCANError as e:
        handle_client_error(e)
        return

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print(_format_status(status))


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the status subcommand."""
    p = subparsers.add_parser("status", help="Device status summary")
    p.add_argument("--json", action="store_true", help="Raw JSON output")
    p.set_defaults(func=cmd_status)
