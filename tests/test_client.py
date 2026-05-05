"""Tests for TabloClient — channel listing and stream start (mocked)."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from tablo_api.client import TabloClient, TabloStreamError
from tablo_api.models import TabloDevice, TabloChannel


DEVICE = TabloDevice(
    sid="SID_ABC",
    name="Living Room Tablo",
    local_url="http://10.0.0.5:8885",
    lighthouse_token="lh_token_xyz",
)

CHANNEL_LIST = [
    {
        "identifier": "S122912_503_01",
        "name": "KFOR",
        "kind": "ota",
        "ota": {"major": 4, "minor": 1, "callSign": "KFOR", "network": "NBC"},
    },
    {
        "identifier": "S999_01",
        "name": "KOCO",
        "kind": "ota",
        "ota": {"major": 5, "minor": 1, "callSign": "KOCO", "network": "ABC"},
    },
    {
        "identifier": "OTT_001",
        "name": "Peacock",
        "kind": "ott",
        "ott": {"major": 100, "minor": 1, "callSign": "PEACOCK", "network": "Peacock"},
    },
]

WATCH_RESP = {
    "playlist_url": "http://10.0.0.5:8885/stream/abc.m3u8",
    "token": "stream_tok",
    "expires": "2026-05-05T13:00:00Z",
    "keepalive": 30,
}


def _resp(data, status_code: int = 200) -> MagicMock:
    m = MagicMock(spec=requests.Response)
    m.ok = 200 <= status_code < 300
    m.status_code = status_code
    m.text = str(data)
    m.json.return_value = data
    m.raise_for_status = MagicMock()
    if not m.ok:
        m.raise_for_status.side_effect = requests.HTTPError(response=m)
    return m


class TestTabloClientChannels:
    def _client(self) -> TabloClient:
        return TabloClient(DEVICE)

    def test_returns_sorted_ota_channels(self):
        client = self._client()
        with patch.object(client._session, "get", return_value=_resp(CHANNEL_LIST)):
            channels = client.channels()

        assert len(channels) == 2  # OTT excluded by default
        assert channels[0].major == 4
        assert channels[0].call_sign == "KFOR"
        assert channels[1].major == 5

    def test_include_ott(self):
        client = self._client()
        with patch.object(client._session, "get", return_value=_resp(CHANNEL_LIST)):
            channels = client.channels(include_ott=True)
        assert len(channels) == 3

    def test_channel_display_name(self):
        client = self._client()
        with patch.object(client._session, "get", return_value=_resp(CHANNEL_LIST)):
            channels = client.channels()
        assert channels[0].display_name == "4.1 KFOR"

    def test_cloud_url_uses_lighthouse_token(self):
        client = self._client()
        with patch.object(client._session, "get", return_value=_resp([])) as mock_get:
            client.channels()
        url = mock_get.call_args[0][0]
        assert "lh_token_xyz" in url

    def test_empty_lineup(self):
        client = self._client()
        with patch.object(client._session, "get", return_value=_resp([])):
            assert client.channels() == []


class TestTabloClientWatch:
    def _client(self) -> TabloClient:
        return TabloClient(DEVICE)

    def test_returns_stream_with_playlist_url(self):
        client = self._client()
        channel = TabloChannel(identifier="S122912_503_01", call_sign="KFOR",
                               major=4, minor=1, network="NBC")
        with patch.object(client._session, "post", return_value=_resp(WATCH_RESP)):
            stream = client.watch(channel)

        assert stream.playlist_url == WATCH_RESP["playlist_url"]
        assert stream.channel_identifier == "S122912_503_01"
        assert stream.token == "stream_tok"

    def test_accepts_raw_identifier_string(self):
        client = self._client()
        with patch.object(client._session, "post", return_value=_resp(WATCH_RESP)):
            stream = client.watch("S122912_503_01")
        assert stream.channel_identifier == "S122912_503_01"

    def test_401_raises_stream_error(self):
        client = self._client()
        with patch.object(client._session, "post", return_value=_resp({}, 401)):
            with pytest.raises(TabloStreamError, match="401"):
                client.watch("S122912_503_01")

    def test_missing_playlist_url_raises(self):
        client = self._client()
        with patch.object(client._session, "post", return_value=_resp({"token": "x"})):
            with pytest.raises(TabloStreamError, match="playlist_url"):
                client.watch("S122912_503_01")

    def test_local_device_url_used(self):
        client = self._client()
        with patch.object(client._session, "post", return_value=_resp(WATCH_RESP)) as mock_post:
            client.watch("S122912_503_01")
        url = mock_post.call_args[0][0]
        assert url.startswith("http://10.0.0.5:8885")

    def test_hmac_auth_header_included(self):
        client = self._client()
        with patch.object(client._session, "post", return_value=_resp(WATCH_RESP)) as mock_post:
            client.watch("S122912_503_01")
        headers = mock_post.call_args[1]["headers"]
        assert headers["Authorization"].startswith("tablo:")


class TestTabloClientPing:
    def test_ping_returns_sid(self):
        client = TabloClient(DEVICE)
        with patch.object(client._session, "get", return_value=_resp({"sid": "SID_ABC"})):
            assert client.ping() == "SID_ABC"
