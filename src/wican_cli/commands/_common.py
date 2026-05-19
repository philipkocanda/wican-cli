"""Shared CLI utilities, constants, and argparse helpers."""

from __future__ import annotations

import argparse
import sys

import requests

from wican_cli.client import ConnectionFailed, WiCANClient, make_client
from wican_cli.config import get_wican_addresses

DEFAULT_TIMEOUT = 10  # seconds
_PROBE_TIMEOUT = 2  # seconds — quick reachability check


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


def resolve_address(name: str) -> str:
    """Resolve a named address to a base URL (no fallback)."""
    addresses, _ = get_wican_addresses()
    if name in addresses:
        addr = addresses[name]
    else:
        addr = name
    if not addr.startswith(("http://", "https://")):
        return f"http://{addr}"
    return addr


def _is_reachable(url: str) -> bool:
    """Quick probe to check if a WiCAN device responds at the given URL."""
    try:
        requests.get(f"{url}/check_status", timeout=_PROBE_TIMEOUT)
        return True
    except (requests.ConnectionError, requests.Timeout):
        return False


def get_client(args: argparse.Namespace) -> WiCANClient:
    """Create a WiCANClient from parsed CLI arguments.

    If --use is explicit, connect to that address only (fail hard).
    If --use is omitted, try the default address first, then fall through
    to other configured addresses.
    """
    timeout = args.timeout

    if args.use is not None:
        # Explicit target — no fallback
        url = resolve_address(args.use)
        return make_client(url, timeout=timeout)

    # Auto-discovery: try default first, then others
    addresses, default = get_wican_addresses()

    # Build ordered list: default first, then the rest
    order = [default] + [k for k in addresses if k != default]

    for name in order:
        addr = addresses[name]
        url = f"http://{addr}" if not addr.startswith(("http://", "https://")) else addr
        if _is_reachable(url):
            if name != default:
                print(
                    f"NOTE: '{default}' unreachable, using '{name}' ({addr})",
                    file=sys.stderr,
                )
            return make_client(url, timeout=timeout)

    # Nothing reachable — fail with a helpful message listing what was tried
    tried = ", ".join(f"{k} ({addresses[k]})" for k in order)
    raise ConnectionFailed(f"Cannot reach any configured WiCAN device.\n  Tried: {tried}")


def flatten_config(config: dict) -> dict:
    """If config has a nested 'config' key, return that sub-dict."""
    if "config" in config and isinstance(config["config"], dict):
        return config["config"]
    return config
