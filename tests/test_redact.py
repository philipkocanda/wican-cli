"""Tests for wican_cli.redact module."""

from wican_cli.redact import REDACTED_PLACEHOLDER, redact_config


def test_redact_flat_config():
    """Redacts sensitive fields in a flat config structure."""
    config = {
        "sta_ssid": "MyNetwork",
        "sta_pass": "secret123",
        "ap_pass": "appass",
        "mqtt_pass": "mqttpass",
        "mqtt_user": "admin",
        "sleep_status": "enable",
    }
    result = redact_config(config)
    assert result["sta_ssid"] == REDACTED_PLACEHOLDER
    assert result["sta_pass"] == REDACTED_PLACEHOLDER
    assert result["ap_pass"] == REDACTED_PLACEHOLDER
    assert result["mqtt_pass"] == REDACTED_PLACEHOLDER
    assert result["mqtt_user"] == REDACTED_PLACEHOLDER
    # Non-sensitive field should be unchanged
    assert result["sleep_status"] == "enable"
    # Original should be unmodified
    assert config["sta_pass"] == "secret123"


def test_redact_nested_config():
    """Redacts sensitive fields in a nested config structure."""
    config = {
        "config": {
            "sta_ssid": "MyNetwork",
            "sta_pass": "secret123",
            "sleep_status": "enable",
        },
        "auto_pid": {"some_key": "value"},
    }
    result = redact_config(config)
    assert result["config"]["sta_ssid"] == REDACTED_PLACEHOLDER
    assert result["config"]["sta_pass"] == REDACTED_PLACEHOLDER
    assert result["config"]["sleep_status"] == "enable"
    assert result["auto_pid"]["some_key"] == "value"


def test_redact_sta_fallbacks():
    """Redacts ssid and pass in sta_fallbacks array."""
    config = {
        "sta_ssid": "Primary",
        "sta_pass": "pass1",
        "sta_fallbacks": [
            {"ssid": "Fallback1", "pass": "fb1pass"},
            {"ssid": "Fallback2", "pass": "fb2pass"},
        ],
    }
    result = redact_config(config)
    assert result["sta_fallbacks"][0]["ssid"] == REDACTED_PLACEHOLDER
    assert result["sta_fallbacks"][0]["pass"] == REDACTED_PLACEHOLDER
    assert result["sta_fallbacks"][1]["ssid"] == REDACTED_PLACEHOLDER
    assert result["sta_fallbacks"][1]["pass"] == REDACTED_PLACEHOLDER


def test_redact_custom_placeholder():
    """Supports a custom placeholder string."""
    config = {"sta_pass": "secret"}
    result = redact_config(config, placeholder="[HIDDEN]")
    assert result["sta_pass"] == "[HIDDEN]"


def test_redact_missing_keys():
    """Does not fail when sensitive keys are absent."""
    config = {"sleep_status": "enable", "protocol": "auto_pid"}
    result = redact_config(config)
    assert result == config
