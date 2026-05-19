"""HTTP client for WiCAN device API.

All communication with the WiCAN device happens over HTTP REST endpoints:
  - GET  /load_config    — download full device configuration
  - POST /store_config   — upload configuration (triggers reboot)
  - GET  /check_status   — device status summary
  - POST /system_reboot  — reboot the device
  - GET  /list_files     — list SD card log files
  - GET  /download_file  — download a specific file
  - GET  /check_autopids — current AutoPID cached values
"""

from __future__ import annotations

import sys
from typing import Any

import requests


class WiCANError(Exception):
    """Base exception for WiCAN communication errors."""


class ConnectionFailed(WiCANError):
    """Cannot reach the device."""


class RequestTimeout(WiCANError):
    """Request timed out."""


class WiCANClient:
    """HTTP client for a WiCAN device.

    Parameters
    ----------
    base_url : str
        Device URL including scheme, e.g. "http://192.168.80.1".
    timeout : int
        Request timeout in seconds.
    """

    def __init__(self, base_url: str, timeout: int = 10) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str) -> Any:
        """Perform a GET request and return parsed JSON."""
        url = f"{self.base_url}{path}"
        try:
            resp = requests.get(url, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.ConnectionError:
            raise ConnectionFailed(
                f"Cannot connect to WiCAN at {self.base_url}\n"
                "  Is the device powered on and reachable?"
            )
        except requests.Timeout:
            raise RequestTimeout(f"Timeout connecting to {self.base_url}")

    def _post(self, path: str, data: Any = None, json: Any = None) -> requests.Response | None:
        """Perform a POST request. Returns response or None on expected timeout."""
        url = f"{self.base_url}{path}"
        try:
            resp = requests.post(url, data=data, json=json, timeout=self.timeout)
            resp.raise_for_status()
            return resp
        except requests.ConnectionError:
            raise ConnectionFailed(f"Cannot connect to WiCAN at {self.base_url}")
        except requests.Timeout:
            # Expected for operations that trigger a reboot
            return None

    def get_config(self) -> dict:
        """Download the full device configuration."""
        return self._get("/load_config")

    def store_config(self, config: dict) -> None:
        """Upload configuration to the device. Triggers an automatic reboot."""
        self._post("/store_config", json=config)

    def get_status(self) -> dict:
        """Get device status summary."""
        return self._get("/check_status")

    def reboot(self) -> None:
        """Reboot the device."""
        self._post("/system_reboot", data="reboot")

    def list_files(self) -> list[str]:
        """List available log files on the SD card."""
        data = self._get("/list_files")
        if isinstance(data, list):
            return data
        # Some firmware versions return {"files": [...]}
        return data.get("files", [])

    def download_file(self, filename: str) -> bytes:
        """Download a file from the SD card."""
        url = f"{self.base_url}/download_file?name={filename}"
        try:
            resp = requests.get(url, timeout=self.timeout * 3)  # Large files need more time
            resp.raise_for_status()
            return resp.content
        except requests.ConnectionError:
            raise ConnectionFailed(f"Cannot connect to WiCAN at {self.base_url}")
        except requests.Timeout:
            raise RequestTimeout(f"Timeout downloading {filename}")

    def get_autopid_values(self) -> dict:
        """Get current AutoPID cached parameter values."""
        return self._get("/check_autopids")


def make_client(address: str, timeout: int = 10) -> WiCANClient:
    """Create a WiCANClient, adding http:// scheme if needed."""
    if not address.startswith(("http://", "https://")):
        address = f"http://{address}"
    return WiCANClient(address, timeout=timeout)


def handle_client_error(e: WiCANError) -> None:
    """Print a user-friendly error message and exit."""
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
