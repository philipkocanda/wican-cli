"""HTTP client for WiCAN device API.

All communication with the WiCAN device happens over HTTP REST endpoints:
  - GET  /load_config    — download full device configuration
  - POST /store_config   — upload configuration (triggers reboot)
  - GET  /check_status   — device status summary
  - POST /system_reboot  — reboot the device
  - GET  /obd_logs       — list OBD log databases on SD card
  - GET  /obd_logs/<file> — download a specific log database
  - GET  /autopid_data   — current AutoPID cached values

Note: WiCAN devices only support HTTP (no TLS). Communication is
typically over a local network or AP mode, not over the internet.
"""

from __future__ import annotations

import sys
from typing import Any, NoReturn
from urllib.parse import quote

import requests


class WiCANError(Exception):
    """Base exception for WiCAN communication errors."""


class ConnectionFailed(WiCANError):
    """Cannot reach the device."""


class RequestTimeout(WiCANError):
    """Request timed out."""


class DeviceError(WiCANError):
    """Device returned an HTTP error status."""


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
        except requests.ConnectionError as e:
            raise ConnectionFailed(
                f"Cannot connect to WiCAN at {self.base_url}\n"
                "  Is the device powered on and reachable?"
            ) from e
        except requests.Timeout as e:
            raise RequestTimeout(f"Timeout connecting to {self.base_url}") from e
        except requests.HTTPError as e:
            raise DeviceError(f"Device returned error: {e.response.status_code} on {path}") from e

    def _post(
        self,
        path: str,
        data: Any = None,
        json: Any = None,
        *,
        expect_timeout: bool = False,
    ) -> requests.Response | None:
        """Perform a POST request.

        Parameters
        ----------
        expect_timeout : bool
            If True, a timeout is treated as success (device rebooted).
            If False, a timeout raises RequestTimeout.
        """
        url = f"{self.base_url}{path}"
        try:
            resp = requests.post(url, data=data, json=json, timeout=self.timeout)
            resp.raise_for_status()
            return resp
        except requests.ConnectionError as e:
            if expect_timeout:
                return None
            raise ConnectionFailed(f"Cannot connect to WiCAN at {self.base_url}") from e
        except requests.Timeout as e:
            if expect_timeout:
                return None
            raise RequestTimeout(f"Timeout on POST to {self.base_url}{path}") from e
        except requests.HTTPError as e:
            raise DeviceError(f"Device returned error: {e.response.status_code} on {path}") from e

    def get_config(self) -> dict:
        """Download the full device configuration."""
        return self._get("/load_config")

    def store_config(self, config: dict) -> None:
        """Upload configuration to the device. Triggers an automatic reboot."""
        self._post("/store_config", json=config, expect_timeout=True)

    def get_status(self) -> dict:
        """Get device status summary."""
        return self._get("/check_status")

    def reboot(self) -> None:
        """Reboot the device."""
        self._post("/system_reboot", data="reboot", expect_timeout=True)

    def list_logs(self) -> dict:
        """List OBD log databases on the SD card.

        Returns the raw API response dict with keys:
          - current_db: filename of the currently active database
          - databases: list of dicts with filename, created, size, status
        """
        return self._get("/obd_logs")

    def download_log(self, filename: str) -> bytes:
        """Download a log database from the SD card.

        Raises WiCANError if the filename contains path traversal sequences.
        """
        # Reject path traversal attempts
        if "/" in filename or "\\" in filename or ".." in filename:
            raise WiCANError(f"Invalid filename (path traversal rejected): {filename}")
        url = f"{self.base_url}/obd_logs/{quote(filename)}"
        try:
            resp = requests.get(url, timeout=self.timeout * 3)  # Large files need more time
            resp.raise_for_status()
            return resp.content
        except requests.ConnectionError as e:
            raise ConnectionFailed(f"Cannot connect to WiCAN at {self.base_url}") from e
        except requests.Timeout as e:
            raise RequestTimeout(f"Timeout downloading {filename}") from e
        except requests.HTTPError as e:
            raise DeviceError(
                f"Device returned error {e.response.status_code} downloading {filename}"
            ) from e

    def get_autopid_values(self) -> dict:
        """Get current AutoPID cached parameter values."""
        return self._get("/autopid_data")


def make_client(address: str, timeout: int = 10) -> WiCANClient:
    """Create a WiCANClient, adding http:// scheme if needed."""
    if not address.startswith(("http://", "https://")):
        address = f"http://{address}"
    return WiCANClient(address, timeout=timeout)


def handle_client_error(e: WiCANError) -> NoReturn:
    """Print a user-friendly error message and exit."""
    print(f"ERROR: {e}", file=sys.stderr)
    sys.exit(1)
