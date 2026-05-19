"""Configuration file resolution and loading.

Config search order:
  1. WICAN_URL environment variable (overrides all file-based config)
  2. ./config.yaml (project-local)
  3. ~/.config/wican-cli/config.yaml (user-global, XDG-compliant)

If none found, defaults to WiCAN AP mode address (192.168.80.1).
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

# WiCAN's built-in Access Point address (factory default).
DEFAULT_AP_ADDRESS = "192.168.80.1"

# Config file name for project-local config.
LOCAL_CONFIG_NAME = "config.yaml"

# XDG-compliant user config path.
_xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
USER_CONFIG_PATH = Path(_xdg_config) / "wican-cli" / "config.yaml"


def find_config_file() -> Path | None:
    """Find the first available config file, or None."""
    # Project-local
    local = Path.cwd() / LOCAL_CONFIG_NAME
    if local.is_file():
        return local
    # User-global
    if USER_CONFIG_PATH.is_file():
        return USER_CONFIG_PATH
    return None


def load_config() -> dict:
    """Load configuration from file or return empty dict.

    Returns the parsed YAML dict, or {} if no config file exists.
    Raises ValueError if the file content is not a dict.
    """
    path = find_config_file()
    if path is None:
        return {}
    with open(path) as f:
        data = yaml.safe_load(f)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(
            f"Invalid config format in {path}: expected a YAML mapping, got {type(data).__name__}"
        )
    return data


def get_wican_addresses() -> tuple[dict[str, str], str]:
    """Return (addresses_dict, default_key) from config or environment.

    If WICAN_URL is set, it takes precedence as the sole address.
    Otherwise, loads from config.yaml. Falls back to AP mode default.
    """
    env_url = os.environ.get("WICAN_URL")
    if env_url:
        # Environment override — single address keyed as "env"
        return {"env": env_url.rstrip("/")}, "env"

    cfg = load_config()
    addresses = cfg.get("wican_addresses", {"ap": DEFAULT_AP_ADDRESS})
    if not isinstance(addresses, dict):
        raise ValueError(
            f"Invalid config: 'wican_addresses' must be a mapping, got {type(addresses).__name__}"
        )
    default = cfg.get("default_wican", next(iter(addresses)))
    # Ensure all values are plain strings (no scheme prefix — callers add it)
    addresses = {k: str(v).rstrip("/") for k, v in addresses.items()}
    if default not in addresses:
        raise ValueError(
            f"Invalid config: default_wican '{default}' not found in wican_addresses "
            f"(available: {', '.join(addresses.keys())})"
        )
    return addresses, default
