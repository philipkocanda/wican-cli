"""Tests for wican_cli.config module."""

import os
from pathlib import Path
from unittest.mock import patch

from wican_cli.config import (
    DEFAULT_AP_ADDRESS,
    find_config_file,
    get_wican_addresses,
    load_config,
)


def test_get_wican_addresses_env_override():
    """WICAN_URL environment variable takes precedence."""
    with patch.dict(os.environ, {"WICAN_URL": "http://10.0.0.1"}):
        addresses, default = get_wican_addresses()
    assert addresses == {"env": "http://10.0.0.1"}
    assert default == "env"


def test_get_wican_addresses_env_strips_trailing_slash():
    """Trailing slash is stripped from WICAN_URL."""
    with patch.dict(os.environ, {"WICAN_URL": "http://10.0.0.1/"}):
        addresses, default = get_wican_addresses()
    assert addresses == {"env": "http://10.0.0.1"}


def test_get_wican_addresses_fallback():
    """Falls back to AP address when no config exists."""
    with patch.dict(os.environ, {}, clear=True):
        # Ensure WICAN_URL is not set
        os.environ.pop("WICAN_URL", None)
        with patch("wican_cli.config.find_config_file", return_value=None):
            addresses, default = get_wican_addresses()
    assert DEFAULT_AP_ADDRESS in addresses.values()


def test_find_config_file_returns_none(tmp_path):
    """Returns None when no config file exists."""
    with patch("wican_cli.config.Path.cwd", return_value=tmp_path):
        with patch("wican_cli.config.USER_CONFIG_PATH", tmp_path / "nonexistent.yaml"):
            result = find_config_file()
    assert result is None


def test_load_config_returns_empty_when_missing():
    """Returns empty dict when no config file exists."""
    with patch("wican_cli.config.find_config_file", return_value=None):
        result = load_config()
    assert result == {}


def test_load_config_parses_yaml(tmp_path):
    """Parses a valid YAML config file."""
    config_file = tmp_path / "wican-cli.yaml"
    config_file.write_text("wican_addresses:\n  home: '10.0.2.86'\ndefault_wican: home\n")
    with patch("wican_cli.config.find_config_file", return_value=config_file):
        result = load_config()
    assert result["wican_addresses"]["home"] == "10.0.2.86"
    assert result["default_wican"] == "home"
