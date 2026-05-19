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
    "fw_version": "3.55",
    "protocol": "auto_pid",
    "ssid": "MyNetwork",
    "rssi": "-42",
    "ip": "192.168.1.100",
    "mac": "AA:BB:CC:DD:EE:FF",
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
    with patch("wican_cli.cli.get_wican_addresses") as mock:
        mock.return_value = ({"ap": "192.168.80.1"}, "ap")
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
        """status shows device info."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_STATUS)

        with patch("sys.argv", ["wican", "status"]):
            main()

        out = capsys.readouterr().out
        assert "fw_version" in out
        assert "3.55" in out
        assert "auto_pid" in out

    def test_status_json_output(self, mock_config, mock_requests_get, capsys):
        """status --json outputs valid JSON."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_STATUS)

        with patch("sys.argv", ["wican", "status", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed["fw_version"] == "3.55"

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


# ── logs subcommand ───────────────────────────────────────────────────────────


class TestCmdLogs:
    """Tests for `wican logs`."""

    def test_logs_list(self, mock_config, mock_requests_get, capsys):
        """logs lists available files."""
        mock_requests_get.return_value = _make_response(data=["obd_2026-01.db", "obd_2026-02.db"])

        with patch("sys.argv", ["wican", "logs"]):
            main()

        out = capsys.readouterr().out
        assert "obd_2026-01.db" in out
        assert "obd_2026-02.db" in out

    def test_logs_list_json(self, mock_config, mock_requests_get, capsys):
        """logs --json outputs file list as JSON."""
        files = ["obd_2026-01.db", "obd_2026-02.db"]
        mock_requests_get.return_value = _make_response(data=files)

        with patch("sys.argv", ["wican", "logs", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert parsed == files

    def test_logs_list_empty(self, mock_config, mock_requests_get, capsys):
        """logs shows message when no files found."""
        mock_requests_get.return_value = _make_response(data=[])

        with patch("sys.argv", ["wican", "logs"]):
            main()

        out = capsys.readouterr().out
        assert "no log files" in out.lower()

    def test_logs_download(self, mock_config, mock_requests_get, capsys, tmp_path):
        """logs --download downloads files to logs/ directory."""
        # First call: list_files, second call: download_file
        list_resp = _make_response(data=["test.db"])
        download_resp = _make_response(content=b"sqlite3 data here")

        mock_requests_get.side_effect = [list_resp, download_resp]

        logs_dir = tmp_path / "logs"
        with patch("sys.argv", ["wican", "logs", "--download"]):
            with patch("wican_cli.cli.Path.cwd", return_value=tmp_path):
                main()

        out = capsys.readouterr().out
        assert "OK" in out
        assert (logs_dir / "test.db").exists()

    def test_logs_download_skip_existing(self, mock_config, mock_requests_get, capsys, tmp_path):
        """logs --download skips existing files without --force."""
        list_resp = _make_response(data=["test.db"])
        mock_requests_get.return_value = list_resp

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "test.db").write_bytes(b"old data")

        with patch("sys.argv", ["wican", "logs", "--download"]):
            with patch("wican_cli.cli.Path.cwd", return_value=tmp_path):
                main()

        out = capsys.readouterr().out
        assert "exists" in out.lower()

    def test_logs_download_force(self, mock_config, mock_requests_get, capsys, tmp_path):
        """logs --download --force overwrites existing files."""
        list_resp = _make_response(data=["test.db"])
        download_resp = _make_response(content=b"new data")
        mock_requests_get.side_effect = [list_resp, download_resp]

        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "test.db").write_bytes(b"old data")

        with patch("sys.argv", ["wican", "logs", "--download", "--force"]):
            with patch("wican_cli.cli.Path.cwd", return_value=tmp_path):
                main()

        assert (logs_dir / "test.db").read_bytes() == b"new data"

    def test_logs_download_unsafe_path(self, mock_config, mock_requests_get, capsys, tmp_path):
        """logs --download rejects filenames with path traversal."""
        list_resp = _make_response(data=["../evil.db"])
        mock_requests_get.return_value = list_resp

        with patch("sys.argv", ["wican", "logs", "--download"]):
            with patch("wican_cli.cli.Path.cwd", return_value=tmp_path):
                # download_file raises on path traversal, but _cmd_logs_download
                # also checks containment. The WiCANError from client is caught.
                main()

        err = capsys.readouterr().err
        # Should either skip or report error
        assert "unsafe" in err.lower() or "FAILED" in capsys.readouterr().out

    def test_logs_query(self, mock_config, mock_requests_get, capsys):
        """logs --query retrieves data from a log database."""
        # Create a real SQLite DB in memory then get its bytes
        db_bytes = _make_test_db([("2026-01-01 10:00:00", "78"), ("2026-01-01 10:01:00", "79")])

        list_resp = _make_response(data=["obd.db"])
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--query", "SOC_BMS"]):
            main()

        out = capsys.readouterr().out
        assert "SOC_BMS" in out
        assert "78" in out or "79" in out

    def test_logs_query_json(self, mock_config, mock_requests_get, capsys):
        """logs --query --json outputs structured JSON."""
        db_bytes = _make_test_db([("2026-01-01 10:00:00", "78")])

        list_resp = _make_response(data=["obd.db"])
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--query", "SOC_BMS", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert len(parsed) == 1
        assert parsed[0]["value"] == "78"

    def test_logs_query_no_results(self, mock_config, mock_requests_get, capsys):
        """logs --query with unknown param shows no data message."""
        db_bytes = _make_test_db([("2026-01-01 10:00:00", "78")])

        list_resp = _make_response(data=["obd.db"])
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--query", "NONEXISTENT"]):
            main()

        out = capsys.readouterr().out
        assert "no data" in out.lower()

    def test_logs_params(self, mock_config, mock_requests_get, capsys):
        """logs --params lists distinct parameter names."""
        db_bytes = _make_test_db(
            [("2026-01-01 10:00:00", "78")],
            extra_params=[("Battery_Voltage", "356.2"), ("Speed", "60")],
        )

        list_resp = _make_response(data=["obd.db"])
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--params"]):
            main()

        out = capsys.readouterr().out
        assert "SOC_BMS" in out
        assert "Battery_Voltage" in out

    def test_logs_params_json(self, mock_config, mock_requests_get, capsys):
        """logs --params --json outputs parameter list as JSON."""
        db_bytes = _make_test_db([("2026-01-01 10:00:00", "78")])

        list_resp = _make_response(data=["obd.db"])
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--params", "--json"]):
            main()

        out = capsys.readouterr().out
        parsed = json.loads(out)
        assert "SOC_BMS" in parsed

    def test_logs_limit(self, mock_config, mock_requests_get, capsys):
        """logs --query --limit restricts row count."""
        rows = [(f"2026-01-01 10:{i:02d}:00", str(70 + i)) for i in range(20)]
        db_bytes = _make_test_db(rows)

        list_resp = _make_response(data=["obd.db"])
        download_resp = _make_response(content=db_bytes)
        mock_requests_get.side_effect = [list_resp, download_resp]

        with patch("sys.argv", ["wican", "logs", "--query", "SOC_BMS", "--limit", "5"]):
            main()

        out = capsys.readouterr().out
        assert "last 5" in out

    def test_logs_db_not_found(self, mock_config, mock_requests_get, capsys):
        """logs --download --db nonexistent.db exits with error."""
        list_resp = _make_response(data=["real.db"])
        mock_requests_get.return_value = list_resp

        with patch("sys.argv", ["wican", "logs", "--download", "--db", "nonexistent.db"]):
            with pytest.raises(SystemExit, match="1"):
                main()


# ── autopid subcommand ────────────────────────────────────────────────────────


class TestCmdAutopid:
    """Tests for `wican autopid`."""

    def test_autopid_displays_values(self, mock_config, mock_requests_get, capsys):
        """autopid shows all cached values."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_AUTOPID)

        with patch("sys.argv", ["wican", "autopid"]):
            main()

        out = capsys.readouterr().out
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
        """--wican passes custom address to client."""
        mock_requests_get.return_value = _make_response(data=SAMPLE_STATUS)

        with patch("sys.argv", ["wican", "--wican", "10.0.0.99", "status"]):
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
        """--wican home resolves to configured address."""
        with patch("wican_cli.cli.get_wican_addresses") as mock_addr:
            mock_addr.return_value = ({"home": "192.168.1.100", "ap": "192.168.80.1"}, "home")
            mock_requests_get.return_value = _make_response(data=SAMPLE_STATUS)

            with patch("sys.argv", ["wican", "--wican", "home", "status"]):
                main()

        call_url = mock_requests_get.call_args[0][0]
        assert "192.168.1.100" in call_url


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_test_db(
    rows: list[tuple[str, str]],
    param_name: str = "SOC_BMS",
    extra_params: list[tuple[str, str]] | None = None,
) -> bytes:
    """Create a minimal SQLite database with obd_data table and return as bytes."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    conn = sqlite3.connect(tmp_path)
    conn.execute("CREATE TABLE obd_data (timestamp TEXT, name TEXT, value TEXT)")
    for ts, val in rows:
        conn.execute("INSERT INTO obd_data VALUES (?, ?, ?)", (ts, param_name, val))
    if extra_params:
        for name, val in extra_params:
            conn.execute(
                "INSERT INTO obd_data VALUES (?, ?, ?)", ("2026-01-01 10:00:00", name, val)
            )
    conn.commit()
    conn.close()

    data = Path(tmp_path).read_bytes()
    Path(tmp_path).unlink()
    return data
