"""Credential redaction for WiCAN device configurations.

When saving config snapshots to disk, sensitive fields (passwords, SSIDs,
MQTT credentials) can be replaced with a placeholder to prevent accidental
exposure in version control.
"""

from __future__ import annotations

import copy

# Fields that contain sensitive credentials.
REDACT_KEYS = frozenset({
    "sta_ssid",
    "sta_pass",
    "ap_pass",
    "ble_pass",
    "batt_alert_ssid",
    "batt_alert_pass",
    "batt_mqtt_pass",
    "batt_mqtt_user",
    "mqtt_pass",
    "mqtt_user",
    "home_password",
    "drive_password",
})

REDACTED_PLACEHOLDER = "*** REDACTED ***"


def redact_config(config: dict, *, placeholder: str = REDACTED_PLACEHOLDER) -> dict:
    """Return a deep copy of config with sensitive fields replaced.

    Handles both flat configs (keys at root level) and nested configs
    (keys under a "config" sub-dict). Also redacts "ssid" and "pass"
    fields in sta_fallbacks arrays.
    """
    redacted = copy.deepcopy(config)

    def _redact_obj(obj: dict) -> None:
        for key in REDACT_KEYS:
            if key in obj:
                obj[key] = placeholder
        # Handle sta_fallbacks entries
        if "sta_fallbacks" in obj and isinstance(obj["sta_fallbacks"], list):
            for entry in obj["sta_fallbacks"]:
                if isinstance(entry, dict):
                    if "pass" in entry:
                        entry["pass"] = placeholder
                    if "ssid" in entry:
                        entry["ssid"] = placeholder

    # Nested structure: {"config": {...}, "auto_pid_car_data": {...}, ...}
    if "config" in redacted and isinstance(redacted["config"], dict):
        _redact_obj(redacted["config"])
    else:
        # Flat structure: sensitive keys at root level
        _redact_obj(redacted)

    return redacted
