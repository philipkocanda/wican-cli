"""wican profile — view or upload the vehicle profile (AutoPID configuration)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from wican_cli.client import WiCANError, handle_client_error
from wican_cli.commands._common import confirm, get_client, warn


class ProfileValidationError(Exception):
    """Raised when a profile JSON fails schema validation."""


def _validate_profile(data: dict) -> list[str]:
    """Validate a vehicle profile JSON structure.

    Accepts both formats:
      - Device format: {"cars": [<car>, ...]}
      - Bare car format: {"car_model": ..., "pids": [...]}

    Returns a list of validation error strings (empty = valid).
    """
    errors: list[str] = []

    # Determine which format we're dealing with
    if "cars" in data:
        cars = data["cars"]
        if not isinstance(cars, list):
            errors.append("'cars' must be an array")
            return errors
        if len(cars) == 0:
            errors.append("'cars' array is empty")
            return errors
    elif "car_model" in data or "pids" in data:
        # Bare car object — wrap it for uniform validation
        cars = [data]
    else:
        errors.append("Profile must have a 'cars' array or be a bare car object with 'pids'")
        return errors

    for i, car in enumerate(cars):
        prefix = f"cars[{i}]" if len(cars) > 1 else "car"
        if not isinstance(car, dict):
            errors.append(f"{prefix}: must be an object")
            continue

        # car_model — optional but recommended
        if "car_model" not in car:
            errors.append(f"{prefix}: missing 'car_model'")

        # init — optional (AT init commands)
        if "init" in car and not isinstance(car["init"], str):
            errors.append(f"{prefix}: 'init' must be a string")

        # pids — required
        if "pids" not in car:
            errors.append(f"{prefix}: missing 'pids' array")
            continue
        pids = car["pids"]
        if not isinstance(pids, list):
            errors.append(f"{prefix}: 'pids' must be an array")
            continue
        if len(pids) == 0:
            errors.append(f"{prefix}: 'pids' array is empty")
            continue

        for j, pid_group in enumerate(pids):
            pid_prefix = f"{prefix}.pids[{j}]"
            if not isinstance(pid_group, dict):
                errors.append(f"{pid_prefix}: must be an object")
                continue

            # pid field — required
            if "pid" not in pid_group:
                errors.append(f"{pid_prefix}: missing 'pid'")
            elif not isinstance(pid_group["pid"], str):
                errors.append(f"{pid_prefix}: 'pid' must be a string")

            # parameters — required (accepts dict or list format)
            if "parameters" not in pid_group:
                errors.append(f"{pid_prefix}: missing 'parameters'")
                continue
            params = pid_group["parameters"]
            if isinstance(params, dict):
                # Source format: {"NAME": "expression"}
                for name, expr in params.items():
                    if not isinstance(expr, str):
                        errors.append(
                            f"{pid_prefix}.parameters.{name}: expression must be a string"
                        )
            elif isinstance(params, list):
                # Device format: [{"name": ..., "expression": ...}, ...]
                for k, param in enumerate(params):
                    if not isinstance(param, dict):
                        errors.append(f"{pid_prefix}.parameters[{k}]: must be an object")
                        continue
                    if "name" not in param:
                        errors.append(f"{pid_prefix}.parameters[{k}]: missing 'name'")
                    if "expression" not in param:
                        errors.append(f"{pid_prefix}.parameters[{k}]: missing 'expression'")
            else:
                errors.append(f"{pid_prefix}: 'parameters' must be an object or array")

    return errors


def _normalize_to_device_format(data: dict) -> dict:
    """Ensure the profile is in device format (with 'cars' wrapper).

    If it's a bare car object, wraps it in {"cars": [...]}.
    """
    if "cars" in data:
        return data
    return {"cars": [data]}


def cmd_profile(args: argparse.Namespace) -> None:
    """Show or upload the vehicle profile."""
    if args.upload:
        _cmd_profile_upload(args)
    else:
        _cmd_profile_show(args)


def _cmd_profile_show(args: argparse.Namespace) -> None:
    """Download and display the current vehicle profile from the device."""
    try:
        client = get_client(args)
        profile = client.get_profile()
    except WiCANError as e:
        handle_client_error(e)
        return

    if args.json:
        print(json.dumps(profile, indent=2))
    else:
        _print_profile_summary(profile)


def _print_profile_summary(profile: dict) -> None:
    """Print a human-readable summary of the vehicle profile."""
    cars = profile.get("cars", [profile] if "pids" in profile else [])

    if not cars:
        print("No vehicle profile configured.")
        return

    for car in cars:
        model = car.get("car_model", "(unnamed)")
        init = car.get("init", "")
        pids = car.get("pids", [])

        print(f"Vehicle: {model}")
        if init:
            print(f"  Init: {init}")

        total_params = 0
        for pid_group in pids:
            params = pid_group.get("parameters", {})
            if isinstance(params, dict):
                total_params += len(params)
            elif isinstance(params, list):
                total_params += len(params)

        print(f"  PIDs: {len(pids)} groups, {total_params} parameters")
        print()

        for pid_group in pids:
            pid = pid_group.get("pid", "?")
            pid_init = pid_group.get("pid_init", "")
            enabled = pid_group.get("enabled", True)
            period = pid_group.get("period", "")
            params = pid_group.get("parameters", {})

            status = "" if enabled else " [disabled]"
            period_str = f" ({period}ms)" if period else ""
            header_str = f" [{pid_init.rstrip(';')}]" if pid_init else ""

            if isinstance(params, dict):
                param_names = sorted(params.keys())
            elif isinstance(params, list):
                param_names = [p.get("name", "?") for p in params]
            else:
                param_names = []

            print(f"  {pid}{header_str}{period_str}{status}")
            for name in param_names:
                print(f"    {name}")


def _cmd_profile_upload(args: argparse.Namespace) -> None:
    """Upload a vehicle profile to the device."""
    filepath = Path(args.upload)

    if not filepath.exists():
        print(f"ERROR: File not found: {filepath}", file=sys.stderr)
        sys.exit(1)

    if not filepath.suffix.lower() == ".json":
        warn(f"File does not have .json extension: {filepath.name}")

    # Load and parse
    try:
        raw = filepath.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in {filepath}: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict):
        print("ERROR: Profile must be a JSON object (not array or scalar)", file=sys.stderr)
        sys.exit(1)

    # Validate
    errors = _validate_profile(data)
    if errors:
        print("ERROR: Profile validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)

    # Normalize to device format
    payload = _normalize_to_device_format(data)

    # Count what we're uploading
    cars = payload["cars"]
    total_pids = sum(len(c.get("pids", [])) for c in cars)
    total_params = 0
    for car in cars:
        for pid_group in car.get("pids", []):
            params = pid_group.get("parameters", {})
            total_params += len(params) if isinstance(params, (dict, list)) else 0

    model = cars[0].get("car_model", "(unnamed)") if cars else "?"
    print(f"Uploading profile: {model}")
    print(f"  {total_pids} PID groups, {total_params} parameters")

    if not args.yes and not confirm("Upload to device?"):
        print("Aborted.")
        return

    # Upload
    try:
        client = get_client(args)
        client.store_profile(payload)
    except WiCANError as e:
        handle_client_error(e)
        return

    print("Profile uploaded successfully.")

    # Reboot if requested
    if args.reboot:
        print(f"Rebooting device ({client.base_url}) to apply changes...")
        try:
            client.reboot()
            print("Reboot initiated.")
        except WiCANError as e:
            handle_client_error(e)


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the profile subcommand."""
    p = subparsers.add_parser("profile", help="View or upload vehicle profile")
    p.add_argument("--json", action="store_true", help="Raw JSON output")
    p.add_argument(
        "--upload",
        metavar="FILE",
        help="Upload a profile JSON file to the device",
    )
    p.add_argument(
        "--reboot",
        action="store_true",
        help="Reboot device after upload to apply changes",
    )
    p.add_argument("-y", "--yes", action="store_true", help="Skip confirmation prompt")
    p.set_defaults(func=cmd_profile)
