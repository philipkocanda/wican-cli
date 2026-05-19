"""Tests for wican_cli.client module."""

from unittest.mock import MagicMock, patch

import pytest

from wican_cli.client import ConnectionFailed, RequestTimeout, WiCANClient, make_client


def test_make_client_adds_scheme():
    """make_client adds http:// when no scheme is provided."""
    client = make_client("192.168.80.1")
    assert client.base_url == "http://192.168.80.1"


def test_make_client_preserves_scheme():
    """make_client preserves existing http:// scheme."""
    client = make_client("http://10.0.2.86")
    assert client.base_url == "http://10.0.2.86"


def test_make_client_strips_trailing_slash():
    """make_client strips trailing slash from URL."""
    client = make_client("http://10.0.2.86/")
    assert client.base_url == "http://10.0.2.86"


def test_get_config_success():
    """get_config returns parsed JSON on success."""
    client = WiCANClient("http://192.168.80.1", timeout=5)
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"sta_ssid": "test", "protocol": "auto_pid"}
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = client.get_config()

    mock_get.assert_called_once_with("http://192.168.80.1/load_config", timeout=5)
    assert result == {"sta_ssid": "test", "protocol": "auto_pid"}


def test_get_config_connection_error():
    """get_config raises ConnectionFailed on connection error."""
    import requests

    client = WiCANClient("http://192.168.80.1", timeout=5)

    with patch("requests.get", side_effect=requests.ConnectionError()):
        with pytest.raises(ConnectionFailed):
            client.get_config()


def test_get_config_timeout():
    """get_config raises RequestTimeout on timeout."""
    import requests

    client = WiCANClient("http://192.168.80.1", timeout=5)

    with patch("requests.get", side_effect=requests.Timeout()):
        with pytest.raises(RequestTimeout):
            client.get_config()


def test_store_config_posts_json():
    """store_config POSTs the config as JSON."""
    client = WiCANClient("http://192.168.80.1", timeout=5)
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()
    config = {"protocol": "slcan"}

    with patch("requests.post", return_value=mock_resp) as mock_post:
        client.store_config(config)

    mock_post.assert_called_once_with(
        "http://192.168.80.1/store_config", data=None, json=config, timeout=5
    )


def test_reboot_sends_post():
    """reboot sends POST to /system_reboot."""
    client = WiCANClient("http://192.168.80.1", timeout=5)
    mock_resp = MagicMock()
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.post", return_value=mock_resp) as mock_post:
        client.reboot()

    mock_post.assert_called_once_with(
        "http://192.168.80.1/system_reboot", data="reboot", json=None, timeout=5
    )
