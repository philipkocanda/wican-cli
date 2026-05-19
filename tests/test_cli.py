"""Integration tests for wican_cli.cli module.

Tests all CLI subcommands with mocked HTTP responses, verifying
output, exit codes, and side effects.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from wican_cli.cli import main

# ── Fixtures ──────────────────────────────────────────────────────────────────


SAMPLE_CONFIG = {
    "sta_ssid": "MyNetwork",
    "sta_pass": "secret123",
    "ap_pass": "ap_secret",
    "protocol": "auto_pid",
    "sleep_status": "enable",
    "sleep_disable_agree": "no",
    "periodic_wakeup": "enable",
    "sleep_volt": "12.3",
    "sleep_time": "60",
    "wakeup_interval": "30",
    "mqtt_en": "1",
    "mqtt_url": "mqtt://192.168.1.10",
    "mqtt_port": "1883",
    "mqtt_user": "mqtt",
    "mqtt_pass": "mqtt_secret",
    "mqtt_tx_topic": "wican/tx",
    "mqtt_rx_topic": "wican/rx",
    "mqtt_status_topic": "wican/status",
    "port": "3333",
    "port_type": "tcp",
}

SAMPLE_STATUS = {
    "hw_version": "WiCAN Pro",
    "fw_version": "4.48",
    "git_version": "v4.48p",
    "device_id": "wican_abc123",
    "uptime": "2h 15m",
    "batt_voltage": "13.8",
    "wifi_mode": "1",
    "sta_status": "Connected",
    "sta_ip": "192.168.1.100",
    "sta_ssid": "MyNetwork",
    "mdns": "wican",
    "vpn_status": "Disconnected",
    "vpn_ip": "",
    "protocol": "auto_pid",
    "can_datarate": "500",
    "can_mode": "normal",
    "obd_chip_status": "ready",
    "ecu_status": "connected",
    "sleep_status": "enabled",
    "sleep_volt": "12.3",
    "sleep_time": "5",
    "periodic_wakeup": "enabled",
    "wakeup_interval": "120",
    "wakeup_volt": "12.5",
    "mqtt_en": "true",
    "mqtt_url": "10.0.1.114",
    "mqtt_port": "1883",
    "mqtt_status_topic": "wican/status",
    "logger_status": "disabled",
    "log_period": "60",
    "imu_threshold": "5",
}

SAMPLE_AUTOPID = {
    "SOC_BMS": "78",
    "SOC_Display": "76",
    "Battery_Voltage": "356.2",
    "Tyre_FL_Pressure": "2.3",
    "Tyre_FR_Pressure": "2.3",
}


@pytest.fixture
def mock_config():
    """Mock get_wican_addresses to return a simple default config."""
    ret = ({"ap": "192.168.80.1"}, "ap")
    with (
        patch("wican_cli.cli.get_wican_addresses", return_value=ret),
        patch("wican_cli.commands._common.get_wican_addresses", return_value=ret) as mock,
        patch("wican_cli.commands._common._is_reachable", return_value=True),
    ):
        yield mock


@pytest.fixture
def mock_requests_get():
    """Mock requests.get for all tests."""
    with patch("requests.get") as mock:
        yield mock


@pytest.fixture
def mock_requests_post():
    """Mock requests.post for all tests."""
    with patch("requests.post") as mock:
        yield mock


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path):
    """Redirect Path.home() to tmp_path so log cache doesn't pollute the real home."""
    with patch("wican_cli.commands.logs.Path.home", return_value=tmp_path):
        yield


def _make_response(data=None, content=None, status_code=200):
    """Create a mock response object."""
    resp = MagicMock()
    resp.status_code = status_code
    resp.raise_for_status = MagicMock()
    if data is not None:
        resp.json.return_value = data
    if content is not None:
        resp.content = content
    return resp


# ── config subcommand ─────────────────────────────────────────────────────────


class TestCmdConfig:
    """Tests for `wican config`."""

    def test_config_displays_all_keys(self, mock_config, mock_requests_get, capsys):
        """config shows all key-value pairs."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG)

        with patch("sys.argv", ["wican", "config"]):
            main()

        out = capsys.readouterr().out
        assert "sta_ssid" in out
        assert "MyNetwork" in out
        assert "protocol" in out
        assert "auto_pid" in out

    def test_config_json_output(self, mock_config, mock_requests_get, capsys):
        """config --json outputs valid JSON."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG)

        with patch("sys.argv", ["wican", "config", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["sta_ssid"] == "MyNetwork"
        assert parsed["protocol"] == "auto_pid"

    def test_config_section_filter(self, mock_config, mock_requests_get, capsys):
        """config --section mqtt shows only MQTT keys."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG)

        with patch("sys.argv", ["wican", "config", "--section", "mqtt"]):
            main()

        out = capsys.readouterr().out
        assert "mqtt_en" in out
        assert "mqtt_url" in out
        assert "sta_ssid" not in out

    def test_config_section_filter_json(self, mock_config, mock_requests_get, capsys):
        """config --section mqtt --json returns filtered JSON."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG)

        with patch("sys.argv", ["wican", "config", "--section", "mqtt", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "mqtt_en" in parsed
        assert "sta_ssid" not in parsed

    def test_config_invalid_section(self, mock_config, mock_requests_get):
        """config --section bogus exits with error."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG)

        with patch("sys.argv", ["wican", "config", "--section", "bogus"]):
            with pytest.raises(SystemExit, match="1"):
                main()

    def test_config_save(self, mock_config, mock_requests_get, capsys, tmp_path):
        """config --save writes a config JSON file."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG)

        with patch("sys.argv", ["wican", "config", "--save", "-o", str(tmp_path)]):
            main()

        out = capsys.readouterr().out
        assert "Saved to" in out
        # Find the saved file
        saved_files = list(tmp_path.glob("config_*.json"))
        assert len(saved_files) == 1
        content = json.loads(saved_files[0].read_text())
        assert content["sta_pass"] == "secret123"  # Not redacted

    def test_config_save_redact(self, mock_config, mock_requests_get, capsys, tmp_path):
        """config --save --redact strips credentials."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG)

        with patch("sys.argv", ["wican", "config", "--save", "--redact", "-o", str(tmp_path)]):
            main()

        out = capsys.readouterr().out
        assert "redacted" in out.lower()
        saved_files = list(tmp_path.glob("config_*.json"))
        assert len(saved_files) == 1
        content = json.loads(saved_files[0].read_text())
        assert content["sta_pass"] != "secret123"

    def test_config_save_no_overwrite(self, mock_config, mock_requests_get, capsys, tmp_path):
        """config --save appends -2 if file already exists."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG.copy())
        # Create first file
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y-%m-%d")
        (tmp_path / f"config_{timestamp}.json").write_text("{}")

        with patch("sys.argv", ["wican", "config", "--save", "-o", str(tmp_path)]):
            main()

        saved_files = list(tmp_path.glob("config_*-2.json"))
        assert len(saved_files) == 1

    def test_config_nested_config(self, mock_config, mock_requests_get, capsys):
        """config handles nested 'config' key structure."""
        nested = {"config": SAMPLE_CONFIG, "auto_pid": []}
        mock_requests_get.return_value = _make_response(data=nested)

        with patch("sys.argv", ["wican", "config", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["sta_ssid"] == "MyNetwork"

    def test_config_connection_error(self, mock_config, mock_requests_get, capsys):
        """config exits cleanly on connection error."""
        import requests

        mock_requests_get.side_effect = requests.ConnectionError()

        with patch("sys.argv", ["wican", "config"]):
            with pytest.raises(SystemExit, match="1"):
                main()

        err = capsys.readouterr().err
        assert "ERROR" in err


# ── status subcommand ─────────────────────────────────────────────────────────


class TestCmdStatus:
    """Tests for `wican status`."""

    def test_status_displays_info(self, mock_config, mock_requests_get, capsys):
        """status shows device info in grouped sections."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_STATUS)

        with patch("sys.argv", ["wican", "status"]):
            main()

        out = capsys.readouterr().out
        # Section headers
        assert "Device" in out
        assert "Network" in out
        assert "CAN / OBD" in out
        assert "Power" in out
        assert "MQTT" in out
        assert "Logging" in out
        # Computed values
        assert "4.48 (v4.48p)" in out
        assert "Station" in out
        assert "mqtt://10.0.1.114:1883" in out
        assert "12.3V" in out
        assert "5 min" in out
        assert "120 min" in out
        assert "60s" in out

    def test_status_mqtt_url_with_scheme(self, mock_config, mock_requests_get, capsys):
        """status does not double-prefix mqtt:// when url already has scheme."""
        status = {**SAMPLE_STATUS, "mqtt_url": "mqtt://10.0.1.114"}
        mock_requests_get.return_value = _make_response(data=status)

        with patch("sys.argv", ["wican", "status"]):
            main()

        out = capsys.readouterr().out
        assert "mqtt://10.0.1.114:1883" in out
        assert "mqtt://mqtt://" not in out

    def test_status_json_output(self, mock_config, mock_requests_get, capsys):
        """status --json outputs valid JSON."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_STATUS)

        with patch("sys.argv", ["wican", "status", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["fw_version"] == "4.48"

    def test_status_connection_error(self, mock_config, mock_requests_get, capsys):
        """status exits on connection error."""
        import requests

        mock_requests_get.side_effect = requests.ConnectionError()

        with patch("sys.argv", ["wican", "status"]):
            with pytest.raises(SystemExit, match="1"):
                main()


# ── sleep subcommand ──────────────────────────────────────────────────────────


class TestCmdSleep:
    """Tests for `wican sleep`."""

    def test_sleep_display_only(self, mock_config, mock_requests_get, capsys):
        """sleep with no flags just displays current settings."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG)

        with patch("sys.argv", ["wican", "sleep"]):
            main()

        out = capsys.readouterr().out
        assert "Sleep mode" in out
        assert "enable" in out
        assert "12.3" in out

    def test_sleep_enable_dry_run(self, mock_config, mock_requests_get, capsys):
        """sleep --enable --dry-run shows preview without applying."""
        config = {**SAMPLE_CONFIG, "sleep_status": "disable", "sleep_disable_agree": "yes"}
        mock_requests_get.return_value = _make_response(data=config)

        with patch("sys.argv", ["wican", "sleep", "--enable", "--dry-run"]):
            main()

        out = capsys.readouterr().out
        assert "dry-run" in out.lower() or "dry_run" in out.lower()

    def test_sleep_enable_applies(self, mock_config, mock_requests_get, mock_requests_post, capsys):
        """sleep --enable -y applies changes and posts config."""
        config = {**SAMPLE_CONFIG, "sleep_status": "disable", "sleep_disable_agree": "yes"}
        mock_requests_get.return_value = _make_response(data=config)
        mock_requests_post.return_value = _make_response()

        with patch("sys.argv", ["wican", "sleep", "--enable", "-y"]):
            main()

        out = capsys.readouterr().out
        assert "rebooting" in out.lower()
        mock_requests_post.assert_called_once()
        posted = mock_requests_post.call_args
        assert posted.kwargs.get("json") or posted[1].get("json")

    def test_sleep_no_change_needed(self, mock_config, mock_requests_get, capsys):
        """sleep --enable when already enabled reports no change."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG)

        with patch("sys.argv", ["wican", "sleep", "--enable"]):
            main()

        out = capsys.readouterr().out
        assert "no changes" in out.lower()

    def test_sleep_voltage_validation(self, mock_config):
        """sleep --voltage with out-of-range value fails."""
        with patch("sys.argv", ["wican", "sleep", "--voltage", "5.0"]):
            with pytest.raises(SystemExit):
                main()

    def test_sleep_time_validation(self, mock_config):
        """sleep --time with negative value fails."""
        with patch("sys.argv", ["wican", "sleep", "--time", "-1"]):
            with pytest.raises(SystemExit):
                main()

    def test_sleep_json_output(self, mock_config, mock_requests_get, capsys):
        """sleep --json outputs structured JSON."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG.copy())

        with patch("sys.argv", ["wican", "sleep", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["sleep_status"] == "enable"
        assert parsed["sleep_volt"] == "12.3"
        assert "pending_changes" not in parsed

    def test_sleep_json_with_changes(self, mock_config, mock_requests_get, capsys):
        """sleep --json with --disable shows pending_changes."""
        config = {**SAMPLE_CONFIG, "sleep_status": "enable"}
        mock_requests_get.return_value = _make_response(data=config)

        with patch("sys.argv", ["wican", "sleep", "--disable", "--dry-run", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["pending_changes"]["sleep_status"] == "disable"


# ── reboot subcommand ─────────────────────────────────────────────────────────


class TestCmdReboot:
    """Tests for `wican reboot`."""

    def test_reboot_with_yes_flag(self, mock_config, mock_requests_post, capsys):
        """reboot -y sends reboot command without prompting."""
        mock_requests_post.return_value = _make_response()

        with patch("sys.argv", ["wican", "reboot", "-y"]):
            main()

        out = capsys.readouterr().out
        assert "reboot" in out.lower()
        mock_requests_post.assert_called_once()

    def test_reboot_aborted(self, mock_config, capsys):
        """reboot without -y aborts when user says no."""
        with patch("sys.argv", ["wican", "reboot"]):
            with patch("builtins.input", return_value="n"):
                main()

        out = capsys.readouterr().out
        assert "abort" in out.lower()


# ── protocol subcommand ───────────────────────────────────────────────────────


class TestCmdProtocol:
    """Tests for `wican protocol`."""

    def test_protocol_display(self, mock_config, mock_requests_get, capsys):
        """protocol with no --set shows current protocol."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG)

        with patch("sys.argv", ["wican", "protocol"]):
            main()

        out = capsys.readouterr().out
        assert "auto_pid" in out
        assert "Available" in out or "available" in out

    def test_protocol_set_dry_run(self, mock_config, mock_requests_get, capsys):
        """protocol --set elm327 --dry-run previews without applying."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG)

        with patch("sys.argv", ["wican", "protocol", "--set", "elm327", "--dry-run"]):
            main()

        out = capsys.readouterr().out
        assert "elm327" in out.lower()
        assert "dry run" in out.lower()

    def test_protocol_set_applies(self, mock_config, mock_requests_get, mock_requests_post, capsys):
        """protocol --set slcan -y applies the change."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG.copy())
        mock_requests_post.return_value = _make_response()

        with patch("sys.argv", ["wican", "protocol", "--set", "slcan", "-y"]):
            main()

        out = capsys.readouterr().out
        assert "rebooting" in out.lower()

    def test_protocol_set_same_protocol(self, mock_config, mock_requests_get, capsys):
        """protocol --set auto_pid when already auto_pid reports no change."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG.copy())

        with patch("sys.argv", ["wican", "protocol", "--set", "auto_pid"]):
            main()

        out = capsys.readouterr().out
        assert "no change" in out.lower()

    def test_protocol_set_invalid(self, mock_config, mock_requests_get, capsys):
        """protocol --set bogus exits with error."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG)

        with patch("sys.argv", ["wican", "protocol", "--set", "bogus"]):
            with pytest.raises(SystemExit, match="1"):
                main()

    def test_protocol_json_display(self, mock_config, mock_requests_get, capsys):
        """protocol --json shows current protocol as JSON."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG.copy())

        with patch("sys.argv", ["wican", "protocol", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["current"] == "auto_pid"
        assert "available" in parsed
        assert "elm327" in parsed["available"]

    def test_protocol_set_json_dry_run(self, mock_config, mock_requests_get, capsys):
        """protocol --set elm327 --dry-run --json outputs structured JSON."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG.copy())

        with patch("sys.argv", ["wican", "protocol", "--set", "elm327", "--dry-run", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["status"] == "dry_run"
        assert parsed["changes"]["protocol"] == "elm327"

    def test_protocol_set_same_json(self, mock_config, mock_requests_get, capsys):
        """protocol --set auto_pid --json reports no_change."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG.copy())

        with patch("sys.argv", ["wican", "protocol", "--set", "auto_pid", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["status"] == "no_change"

    def test_protocol_alias_autopid(self, mock_config, mock_requests_get, capsys):
        """protocol --set autopid resolves to auto_pid."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG.copy())

        with patch("sys.argv", ["wican", "protocol", "--set", "autopid"]):
            main()

        out = capsys.readouterr().out
        # autopid -> auto_pid, which is already the current protocol
        assert "no change" in out.lower()

    def test_protocol_alias_realdash(self, mock_config, mock_requests_get, capsys):
        """protocol --set realdash resolves to realdash66 and shows dry-run."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG.copy())

        with patch("sys.argv", ["wican", "protocol", "--set", "realdash", "--dry-run"]):
            main()

        out = capsys.readouterr().out
        assert "realdash66" in out.lower()

    def test_protocol_display_shows_marker(self, mock_config, mock_requests_get, capsys):
        """protocol display shows * marker on active protocol."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG.copy())

        with patch("sys.argv", ["wican", "protocol"]):
            main()

        out = capsys.readouterr().out
        # Active protocol should have a marker
        assert "* auto_pid" in out or "*  auto_pid" in out

    def test_protocol_display_shows_aliases(self, mock_config, mock_requests_get, capsys):
        """protocol display lists aliases."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG.copy())

        with patch("sys.argv", ["wican", "protocol"]):
            main()

        out = capsys.readouterr().out
        assert "autopid" in out
        assert "realdash" in out

    def test_protocol_switch_shows_warnings(self, mock_config, mock_requests_get, capsys):
        """protocol --set elm327 --dry-run shows per-protocol warnings."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_CONFIG.copy())

        with patch("sys.argv", ["wican", "protocol", "--set", "elm327", "--dry-run"]):
            main()

        out = capsys.readouterr().out
        # Should warn about leaving auto_pid
        assert "AutoPID will STOP" in out


# ── logs subcommand ───────────────────────────────────────────────────────────


class TestCmdLogs:
    """Tests for `wican logs`."""

    def test_logs_list(self, mock_config, mock_requests_get, capsys):
        """logs lists available files."""
        mock_requests_get.return_value = _make_response(
            data={
                "current_db": "obd_2026-02.db",
                "databases": [
                    {
                        "filename": "obd_2026-01.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 1024,
                        "status": "closed",
                    },
                    {
                        "filename": "obd_2026-02.db",
                        "created": "2026-02-01T00:00:00",
                        "size": 512,
                        "status": "active",
                    },
                ],
            }
        )

        with patch("sys.argv", ["wican", "logs"]):
            main()

        out = capsys.readouterr().out
        assert "obd_2026-01.db" in out
        assert "obd_2026-02.db" in out
        # Human-readable sizes
        assert "1.0 KB" in out
        assert "512 B" in out
        # Active marker on current_db
        assert "(active)" in out

    def test_logs_list_json(self, mock_config, mock_requests_get, capsys):
        """logs --json outputs full response as JSON."""
        response_data = {
            "current_db": "obd_2026-02.db",
            "databases": [
                {
                    "filename": "obd_2026-01.db",
                    "created": "2026-01-01T00:00:00",
                    "size": 1024,
                    "status": "closed",
                },
                {
                    "filename": "obd_2026-02.db",
                    "created": "2026-02-01T00:00:00",
                    "size": 512,
                    "status": "active",
                },
            ],
        }
        mock_requests_get.return_value = _make_response(data=response_data)

        with patch("sys.argv", ["wican", "logs", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed == response_data

    def test_logs_list_empty(self, mock_config, mock_requests_get, capsys):
        """logs shows message when no files found."""
        mock_requests_get.return_value = _make_response(data={"current_db": "", "databases": []})

        with patch("sys.argv", ["wican", "logs"]):
            main()

        out = capsys.readouterr().out
        assert "no log files" in out.lower()

    def test_logs_download(self, mock_config, mock_requests_get, capsys, tmp_path):
        """logs --download downloads files to logs/ directory."""
        # First call: list_logs, second call: download_log
        list_resp = _make_response(
            data={
                "current_db": "test.db",
                "databases": [
                    {
                        "filename": "test.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 100,
                        "status": "active",
                    }
                ],
            }
        )
        download_resp = _make_response(content=b"sqlite3 data here")

        mock_requests_get.side_effect = [list_resp, download_resp]

        logs_dir = tmp_path / "logs"
        with patch("sys.argv", ["wican", "logs", "--download"]):
            with patch("wican_cli.commands.logs.Path.cwd", return_value=tmp_path):
                main()

        out = capsys.readouterr().out
        assert "OK" in out
        assert (logs_dir / "test.db").exists()

    def test_logs_download_skip_existing(self, mock_config, mock_requests_get, capsys, tmp_path):
        """logs --download skips existing files without --force."""
        list_resp = _make_response(
            data={
                "current_db": "test.db",
                "databases": [
                    {
                        "filename": "test.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 100,
                        "status": "active",
                    }
                ],
            }
        )
        mock_requests_get.return_value = list_resp

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "test.db").write_bytes(b"old data")

        with patch("sys.argv", ["wican", "logs", "--download"]):
            with patch("wican_cli.commands.logs.Path.cwd", return_value=tmp_path):
                main()

        out = capsys.readouterr().out
        assert "exists" in out.lower()

    def test_logs_download_force(self, mock_config, mock_requests_get, capsys, tmp_path):
        """logs --download --force overwrites existing files."""
        list_resp = _make_response(
            data={
                "current_db": "test.db",
                "databases": [
                    {
                        "filename": "test.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 100,
                        "status": "active",
                    }
                ],
            }
        )
        download_resp = _make_response(content=b"new data")
        mock_requests_get.side_effect = [list_resp, download_resp]

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "test.db").write_bytes(b"old data")

        with patch("sys.argv", ["wican", "logs", "--download", "--force"]):
            with patch("wican_cli.commands.logs.Path.cwd", return_value=tmp_path):
                main()

        assert (logs_dir / "test.db").read_bytes() == b"new data"

    def test_logs_download_unsafe_path(self, mock_config, mock_requests_get, capsys, tmp_path):
        """logs --download rejects filenames with path traversal."""
        list_resp = _make_response(
            data={
                "current_db": "../evil.db",
                "databases": [
                    {
                        "filename": "../evil.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 100,
                        "status": "active",
                    }
                ],
            }
        )
        mock_requests_get.return_value = list_resp

        with patch("sys.argv", ["wican", "logs", "--download"]):
            with patch("wican_cli.commands.logs.Path.cwd", return_value=tmp_path):
                # download_log raises on path traversal, but _cmd_logs_download
                # also checks containment. The WiCANError from client is caught.
                main()

        err = capsys.readouterr().err
        # Should either skip or report error
        assert "unsafe" in err.lower() or "FAILED" in capsys.readouterr().out

    def test_logs_query(self, mock_config, mock_requests_get, capsys):
        """logs --query retrieves data from a log database."""
        # Create a real SQLite DB with the firmware schema
        db_bytes = _make_test_db([(1735689600, 78.0), (1735689660, 79.0)])

        list_resp = _make_response(
            data={
                "current_db": "obd.db",
                "databases": [
                    {
                        "filename": "obd.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 4096,
                        "status": "active",
                    }
                ],
            }
        )
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--query", "SOC_BMS"]):
            main()

        out = capsys.readouterr().out
        assert "SOC_BMS" in out
        assert "78" in out or "79" in out

    def test_logs_query_json(self, mock_config, mock_requests_get, capsys):
        """logs --query --json outputs structured JSON."""
        db_bytes = _make_test_db([(1735689600, 78.0)])

        list_resp = _make_response(
            data={
                "current_db": "obd.db",
                "databases": [
                    {
                        "filename": "obd.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 4096,
                        "status": "active",
                    }
                ],
            }
        )
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--query", "SOC_BMS", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert len(parsed) == 1
        assert parsed[0]["value"] == 78.0

    def test_logs_query_no_results(self, mock_config, mock_requests_get, capsys):
        """logs --query with unknown param shows no data message."""
        db_bytes = _make_test_db([(1735689600, 78.0)])

        list_resp = _make_response(
            data={
                "current_db": "obd.db",
                "databases": [
                    {
                        "filename": "obd.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 4096,
                        "status": "active",
                    }
                ],
            }
        )
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--query", "NONEXISTENT"]):
            main()

        out = capsys.readouterr().out
        assert "no data" in out.lower()

    def test_logs_params(self, mock_config, mock_requests_get, capsys):
        """logs --params lists distinct parameter names."""
        db_bytes = _make_test_db(
            [(1735689600, 78.0)],
            extra_params=[("Battery_Voltage", 356.2), ("Speed", 60.0)],
        )

        list_resp = _make_response(
            data={
                "current_db": "obd.db",
                "databases": [
                    {
                        "filename": "obd.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 4096,
                        "status": "active",
                    }
                ],
            }
        )
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--params"]):
            main()

        out = capsys.readouterr().out
        assert "SOC_BMS" in out
        assert "Battery_Voltage" in out

    def test_logs_params_json(self, mock_config, mock_requests_get, capsys):
        """logs --params --json outputs parameter list as JSON."""
        db_bytes = _make_test_db([(1735689600, 78.0)])

        list_resp = _make_response(
            data={
                "current_db": "obd.db",
                "databases": [
                    {
                        "filename": "obd.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 4096,
                        "status": "active",
                    }
                ],
            }
        )
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--params", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "SOC_BMS" in parsed

    def test_logs_limit(self, mock_config, mock_requests_get, capsys):
        """logs --query --limit restricts row count."""
        rows = [(1735689600 + i * 60, 70.0 + i) for i in range(20)]
        db_bytes = _make_test_db(rows)

        list_resp = _make_response(
            data={
                "current_db": "obd.db",
                "databases": [
                    {
                        "filename": "obd.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 4096,
                        "status": "active",
                    }
                ],
            }
        )
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--query", "SOC_BMS", "--limit", "5"]):
            main()

        out = capsys.readouterr().out
        assert "last 5" in out

    def test_logs_db_not_found(self, mock_config, mock_requests_get, capsys):
        """logs --download --db nonexistent.db exits with error."""
        list_resp = _make_response(
            data={
                "current_db": "real.db",
                "databases": [
                    {
                        "filename": "real.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 4096,
                        "status": "active",
                    }
                ],
            }
        )
        mock_requests_get.return_value = list_resp

        with patch("sys.argv", ["wican", "logs", "--download", "--db", "nonexistent.db"]):
            with pytest.raises(SystemExit, match="1"):
                main()

    def test_logs_query_corrupt_fallback(self, mock_config, mock_requests_get, capsys):
        """logs --query falls back to unordered scan when JOIN query fails."""
        db_bytes = _make_test_db_corrupt_index(
            [(1735689600, 78.0), (1735689660, 79.0)], param_name="SOC_BMS"
        )

        list_resp = _make_response(
            data={
                "current_db": "obd.db",
                "databases": [
                    {
                        "filename": "obd.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 4096,
                        "status": "active",
                    }
                ],
            }
        )
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--query", "SOC_BMS"]):
            main()

        captured = capsys.readouterr()
        assert "partially corrupt" in captured.err
        # With ORDER BY DESC, we get newest values (from the 2000 padding rows)
        assert "199.9" in captured.out or "199.8" in captured.out

    def test_logs_query_totally_corrupt(self, mock_config, mock_requests_get, capsys):
        """logs --query exits gracefully when DB is completely unreadable."""
        # A file that isn't even a valid SQLite DB
        db_bytes = b"this is not a sqlite database at all" * 100

        list_resp = _make_response(
            data={
                "current_db": "obd.db",
                "databases": [
                    {
                        "filename": "obd.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 4096,
                        "status": "active",
                    }
                ],
            }
        )
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--query", "SOC_BMS"]):
            with pytest.raises(SystemExit, match="1"):
                main()

        err = capsys.readouterr().err
        assert "too corrupt" in err

    def test_logs_params_corrupt_fallback(self, mock_config, mock_requests_get, capsys):
        """logs --params still works when index is corrupt (param_info intact)."""
        db_bytes = _make_test_db_corrupt_index([(1735689600, 78.0)], param_name="SOC_BMS")

        list_resp = _make_response(
            data={
                "current_db": "obd.db",
                "databases": [
                    {
                        "filename": "obd.db",
                        "created": "2026-01-01T00:00:00",
                        "size": 4096,
                        "status": "active",
                    }
                ],
            }
        )
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--params"]):
            main()

        out = capsys.readouterr().out
        # param_info is intact so should list the param
        assert "SOC_BMS" in out


# ── autopid subcommand ────────────────────────────────────────────────────────


class TestCmdAutopid:
    """Tests for `wican autopid`."""

    def test_autopid_displays_values(self, mock_config, mock_requests_get, capsys):
        """autopid shows header and all cached values."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_AUTOPID)

        with patch("sys.argv", ["wican", "autopid"]):
            main()

        out = capsys.readouterr().out
        assert "AutoPID data" in out
        assert "SOC_BMS" in out
        assert "78" in out
        assert "Battery_Voltage" in out

    def test_autopid_json_output(self, mock_config, mock_requests_get, capsys):
        """autopid --json outputs valid JSON."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_AUTOPID)

        with patch("sys.argv", ["wican", "autopid", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["SOC_BMS"] == "78"

    def test_autopid_filter(self, mock_config, mock_requests_get, capsys):
        """autopid --filter limits output to matching keys."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_AUTOPID)

        with patch("sys.argv", ["wican", "autopid", "-f", "tyre"]):
            main()

        out = capsys.readouterr().out
        assert "Tyre_FL" in out
        assert "SOC_BMS" not in out

    def test_autopid_filter_no_match(self, mock_config, mock_requests_get, capsys):
        """autopid --filter with no matches shows empty message."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_AUTOPID)

        with patch("sys.argv", ["wican", "autopid", "-f", "nonexistent"]):
            main()

        out = capsys.readouterr().out
        assert "no autopid" in out.lower()

    def test_autopid_alias_pids(self, mock_config, mock_requests_get, capsys):
        """'pids' alias works the same as 'autopid'."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_AUTOPID)

        with patch("sys.argv", ["wican", "pids", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "SOC_BMS" in parsed


# ── Global flags ──────────────────────────────────────────────────────────────


class TestGlobalFlags:
    """Tests for global CLI flags."""

    def test_version_flag(self, mock_config, capsys):
        """--version prints version and exits."""
        with patch("sys.argv", ["wican", "--version"]):
            with pytest.raises(SystemExit, match="0"):
                main()

        out = capsys.readouterr().out
        assert "0.1.0" in out

    def test_custom_wican_address(self, mock_config, mock_requests_get, capsys):
        """--use passes custom address to client."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_STATUS)

        with patch("sys.argv", ["wican", "--use", "10.0.0.99", "status"]):
            main()

        # Verify the request was made to the custom address
        call_url = mock_requests_get.call_args[0][0]
        assert "10.0.0.99" in call_url

    def test_custom_timeout(self, mock_config, mock_requests_get, capsys):
        """--timeout sets request timeout."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_STATUS)

        with patch("sys.argv", ["wican", "--timeout", "30", "status"]):
            main()

        call_kwargs = mock_requests_get.call_args[1]
        assert call_kwargs["timeout"] == 30

    def test_named_address_resolution(self, mock_requests_get, capsys):
        """--use home resolves to configured address."""
        ret = ({"home": "192.168.1.100", "ap": "192.168.80.1"}, "home")
        with (
            patch("wican_cli.cli.get_wican_addresses", return_value=ret),
            patch("wican_cli.commands._common.get_wican_addresses", return_value=ret),
        ):
            mock_requests_get.return_value = _make_response(data=SAMPLE_STATUS)

            with patch("sys.argv", ["wican", "--use", "home", "status"]):
                main()

        call_url = mock_requests_get.call_args[0][0]
        assert "192.168.1.100" in call_url

    def test_fallback_to_second_address(self, mock_requests_get, capsys):
        """When default address is unreachable, falls back to next configured address."""
        ret = ({"home": "192.168.1.100", "vpn": "192.168.3.2"}, "home")
        with (
            patch("wican_cli.cli.get_wican_addresses", return_value=ret),
            patch("wican_cli.commands._common.get_wican_addresses", return_value=ret),
            patch(
                "wican_cli.commands._common._is_reachable",
                side_effect=lambda url: "192.168.3.2" in url,
            ),
        ):
            mock_requests_get.return_value = _make_response(data=SAMPLE_STATUS)

            with patch("sys.argv", ["wican", "status"]):
                main()

        err = capsys.readouterr().err
        assert "home" in err and "vpn" in err  # NOTE message about fallback
        call_url = mock_requests_get.call_args[0][0]
        assert "192.168.3.2" in call_url

    def test_no_fallback_when_use_explicit(self, mock_config, mock_requests_get, capsys):
        """--use with unreachable address fails hard, no fallback."""
        from requests import ConnectionError as ReqConnError

        mock_requests_get.side_effect = ReqConnError("connection refused")

        with patch("sys.argv", ["wican", "--use", "10.0.0.99", "status"]):
            with pytest.raises(SystemExit):
                main()

        err = capsys.readouterr().err
        assert "Cannot connect" in err


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_test_db(
    rows: list[tuple[int, float]],
    param_name: str = "SOC_BMS",
    extra_params: list[tuple[str, float]] | None = None,
) -> bytes:
    """Create a minimal SQLite database with param_info/param_data tables and return as bytes.

    The schema matches the actual WiCAN firmware OBD logger:
      - param_info(Id INTEGER PK, Name VARCHAR, Type VARCHAR, Data JSON)
      - param_data(timestamp INTEGER, param_id INTEGER, value REAL)
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    conn = sqlite3.connect(tmp_path)
    conn.execute(
        "CREATE TABLE param_info "
        "(Id INTEGER PRIMARY KEY AUTOINCREMENT, Name VARCHAR(50) UNIQUE, Type VARCHAR(50), Data JSON)"
    )
    conn.execute("CREATE TABLE param_data (timestamp INTEGER, param_id INTEGER, value REAL)")

    # Insert the primary param
    conn.execute(
        "INSERT INTO param_info (Name, Type, Data) VALUES (?, 'NUMERIC', '{}')", (param_name,)
    )
    primary_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    for ts, val in rows:
        conn.execute("INSERT INTO param_data VALUES (?, ?, ?)", (ts, primary_id, val))

    # Insert extra params (each gets one data point at timestamp 1735689600)
    if extra_params:
        for name, val in extra_params:
            conn.execute(
                "INSERT INTO param_info (Name, Type, Data) VALUES (?, 'NUMERIC', '{}')", (name,)
            )
            pid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute("INSERT INTO param_data VALUES (?, ?, ?)", (1735689600, pid, val))

    conn.commit()
    conn.close()

    data = Path(tmp_path).read_bytes()
    Path(tmp_path).unlink()
    return data


def _make_test_db_corrupt_index(
    rows: list[tuple[int, float]],
    param_name: str = "SOC_BMS",
) -> bytes:
    """Create a SQLite database with a corrupt param_data index.

    The param_info table and param_data leaf pages remain readable, but the
    idx_param_data_id index is corrupted so queries using ORDER BY or the
    index will fail, triggering the NOT INDEXED fallback path.

    Page layout (4096-byte pages):
      1: sqlite_master + header
      2: param_info table
      3: param_info UNIQUE index
      4: sqlite_sequence
      5: param_data table root
      6: idx_param_data_id  <-- corrupted
    """
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    conn = sqlite3.connect(tmp_path)
    conn.execute(
        "CREATE TABLE param_info "
        "(Id INTEGER PRIMARY KEY AUTOINCREMENT, Name VARCHAR(50) UNIQUE, Type VARCHAR(50), Data JSON)"
    )
    conn.execute("CREATE TABLE param_data (timestamp INTEGER, param_id INTEGER, value REAL)")
    conn.execute("CREATE INDEX idx_param_data_id ON param_data(param_id, timestamp)")

    conn.execute(
        "INSERT INTO param_info (Name, Type, Data) VALUES (?, 'NUMERIC', '{}')", (param_name,)
    )
    primary_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Insert the requested rows plus padding to ensure multi-page usage
    for ts, val in rows:
        conn.execute("INSERT INTO param_data VALUES (?, ?, ?)", (ts, primary_id, val))
    for i in range(2000):
        conn.execute(
            "INSERT INTO param_data VALUES (?, ?, ?)", (1735689600 + i, primary_id, i * 0.1)
        )

    conn.commit()
    conn.close()

    # Corrupt only the index root page (page 6) cell content area,
    # leaving param_info (page 2) and param_data leaf pages intact.
    data = bytearray(Path(tmp_path).read_bytes())
    page_size = 4096
    idx_offset = (6 - 1) * page_size
    data[idx_offset + 8 : idx_offset + 300] = b"\xde\xad" * 146

    Path(tmp_path).unlink()
    return bytes(data)
