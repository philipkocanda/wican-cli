"""Shared CLI utilities, constants, and argparse helpers."""

from __future__ import annotations

import argparse
import sys

from wican_cli.client import WiCANClient, make_client
from wican_cli.config import get_wican_addresses

DEFAULT_TIMEOUT = 10  # seconds


def warn(msg: str) -> None:
    """Print a yellow warning message to stderr."""
    is_tty = hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    if is_tty:
        print(f"\033[1;33mWARNING:\033[0m {msg}", file=sys.stderr)
    else:
        print(f"WARNING: {msg}", file=sys.stderr)


def positive_int(value: str) -> int:
    """Argparse type: positive integer."""
    try:
        n = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid integer value: {value!r}") from None
    if n <= 0:
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {n}")
    return n


def voltage_range(value: str) -> float:
    """Argparse type: voltage in reasonable range (8.0-16.0 V)."""
    try:
        v = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"invalid float value: {value!r}") from None
    if not (8.0 <= v <= 16.0):
        raise argparse.ArgumentTypeError(f"voltage must be between 8.0 and 16.0, got {v}")
    return v


def confirm(prompt: str) -> bool:
    """Ask user for y/n confirmation."""
    try:
        answer = input(f"{prompt} [y/N] ").strip().lower()
        return answer in ("y", "yes")
    except (KeyboardInterrupt, EOFError):
        print()
        return False


def resolve_address(wican_arg: str) -> str:
    """Resolve a --wican argument to a base URL."""
    addresses, _ = get_wican_addresses()
    if wican_arg in addresses:
        addr = addresses[wican_arg]
    else:
        addr = wican_arg
    if not addr.startswith(("http://", "https://")):
        return f"http://{addr}"
    return addr


def get_client(args: argparse.Namespace) -> WiCANClient:
    """Create a WiCANClient from parsed CLI arguments."""
    url = resolve_address(args.wican)
    return make_client(url, timeout=args.timeout)


def flatten_config(config: dict) -> dict:
    """If config has a nested 'config' key, return that sub-dict."""
    if "config" in config and isinstance(config["config"], dict):
        return config["config"]
    return config
