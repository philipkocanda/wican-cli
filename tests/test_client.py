"""Tests for wican_cli.client module."""

from unittest.mock import MagicMock, patch

import pytest

from wican_cli.client import (
    ConnectionFailed,
    DeviceError,
    RequestTimeout,
    WiCANClient,
    WiCANError,
    make_client,
)


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


def test_download_file_rejects_path_traversal():
    """download_file raises WiCANError on path traversal attempts."""
    client = WiCANClient("http://192.168.80.1", timeout=5)

    with pytest.raises(WiCANError, match="path traversal"):
        client.download_file("../../../etc/passwd")

    with pytest.raises(WiCANError, match="path traversal"):
        client.download_file("foo/bar.db")

    with pytest.raises(WiCANError, match="path traversal"):
        client.download_file("..\\windows\\system32")


def test_download_file_url_encodes_filename():
    """download_file URL-encodes the filename parameter."""
    client = WiCANClient("http://192.168.80.1", timeout=5)
    mock_resp = MagicMock()
    mock_resp.content = b"data"
    mock_resp.raise_for_status = MagicMock()

    with patch("requests.get", return_value=mock_resp) as mock_get:
        result = client.download_file("log 2026-01-01.db")

    # Space should be encoded as %20
    mock_get.assert_called_once_with(
        "http://192.168.80.1/download_file?name=log%202026-01-01.db", timeout=15
    )
    assert result == b"data"


def test_get_raises_device_error_on_http_error():
    """_get wraps HTTPError into DeviceError."""
    import requests

    client = WiCANClient("http://192.168.80.1", timeout=5)
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.raise_for_status.side_effect = requests.HTTPError(response=mock_resp)

    with patch("requests.get", return_value=mock_resp):
        with pytest.raises(DeviceError):
            client.get_config()


def test_post_raises_timeout_when_not_expected():
    """_post raises RequestTimeout when expect_timeout is False."""
    import requests

    client = WiCANClient("http://192.168.80.1", timeout=5)

    with patch("requests.post", side_effect=requests.Timeout()):
        with pytest.raises(RequestTimeout):
            client._post("/some_path", expect_timeout=False)


def test_post_returns_none_when_timeout_expected():
    """_post returns None when timeout occurs and expect_timeout is True."""
    import requests

    client = WiCANClient("http://192.168.80.1", timeout=5)

    with patch("requests.post", side_effect=requests.Timeout()):
        result = client._post("/store_config", expect_timeout=True)
    assert result is None


def test_list_files_handles_unexpected_response():
    """list_files returns empty list for non-list, non-dict responses."""
    client = WiCANClient("http://192.168.80.1", timeout=5)

    with patch.object(client, "_get", return_value="unexpected"):
        result = client.list_files()
    assert result == []


def test_list_files_handles_dict_response():
    """list_files extracts files from dict response."""
    client = WiCANClient("http://192.168.80.1", timeout=5)

    with patch.object(client, "_get", return_value={"files": ["a.db", "b.db"]}):
        result = client.list_files()
    assert result == ["a.db", "b.db"]
