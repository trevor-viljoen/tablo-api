"""Tests for TabloAuth — HMAC signing and cloud auth flow (mocked)."""

import hashlib
import hmac
import re
from email.utils import parsedate_to_datetime
from unittest.mock import MagicMock, patch

import pytest
import requests

from tablo_api.auth import TabloAuth, TabloAuthError, _HASH_KEY, _DEVICE_KEY


# ---------------------------------------------------------------------------
# HMAC-MD5 signing (pure, no network)
# ---------------------------------------------------------------------------

class TestMakeDeviceAuth:
    def test_format(self):
        auth, date = TabloAuth.make_device_auth("GET", "/server/info")
        assert auth.startswith(f"tablo:{_DEVICE_KEY}:")
        assert len(auth.split(":")) == 3

    def test_signature_matches_reference(self):
        # Freeze date so we can reproduce the expected signature.
        fixed_date = "Mon, 05 May 2026 12:00:00 GMT"
        with patch.object(TabloAuth, "device_date", return_value=fixed_date):
            auth, date = TabloAuth.make_device_auth("GET", "/server/info")

        payload = f"GET\n/server/info\n\n{fixed_date}"
        expected_sig = hmac.new(_HASH_KEY.encode(), payload.encode(), hashlib.md5).hexdigest()
        assert auth == f"tablo:{_DEVICE_KEY}:{expected_sig}"
        assert date == fixed_date

    def test_body_is_md5_hashed(self):
        body = '{"foo":"bar"}'
        fixed_date = "Mon, 05 May 2026 12:00:00 GMT"
        with patch.object(TabloAuth, "device_date", return_value=fixed_date):
            auth, _ = TabloAuth.make_device_auth("POST", "/guide/channels/X/watch", body)

        body_hash = hashlib.md5(body.encode()).hexdigest()
        payload = f"POST\n/guide/channels/X/watch\n{body_hash}\n{fixed_date}"
        expected_sig = hmac.new(_HASH_KEY.encode(), payload.encode(), hashlib.md5).hexdigest()
        assert auth.endswith(f":{expected_sig}")

    def test_empty_body_produces_empty_hash_component(self):
        """An empty body must produce an empty string in the payload, not an MD5 of ''."""
        fixed_date = "Mon, 05 May 2026 12:00:00 GMT"
        with patch.object(TabloAuth, "device_date", return_value=fixed_date):
            auth_empty_body, _ = TabloAuth.make_device_auth("GET", "/ping")

        payload = f"GET\n/ping\n\n{fixed_date}"
        expected_sig = hmac.new(_HASH_KEY.encode(), payload.encode(), hashlib.md5).hexdigest()
        assert auth_empty_body.endswith(f":{expected_sig}")

    def test_date_is_rfc1123_gmt(self):
        _, date = TabloAuth.make_device_auth("GET", "/ping")
        # Must be parseable and in GMT
        parsed = parsedate_to_datetime(date)
        assert parsed.tzname() in ("UTC", "GMT", "+00:00")


# ---------------------------------------------------------------------------
# Cloud auth flow (mocked HTTP)
# ---------------------------------------------------------------------------

LOGIN_OK = {"token_type": "Bearer", "access_token": "tok123"}
ACCOUNT_OK = {
    "profiles": [{"identifier": "prof_abc", "name": "Home"}],
    "devices": [{"name": "Living Room Tablo", "serverId": "SID_ABC", "url": "http://10.0.0.5:8885"}],
}
SELECT_OK = {"token": "lh_token_xyz"}


def _mock_session(responses: list[dict]) -> MagicMock:
    """Return a mock requests.Session that replays given responses in order."""
    session = MagicMock(spec=requests.Session)
    mocks = []
    for r in responses:
        m = MagicMock()
        m.ok = r.get("ok", True)
        m.status_code = r.get("status_code", 200)
        m.text = str(r.get("json", {}))
        m.json.return_value = r.get("json", {})
        m.raise_for_status = MagicMock()
        mocks.append(m)
    session.post.side_effect = [m for m in mocks if True]  # patched below
    session.get.side_effect = []
    return session


class TestTabloAuthDiscover:
    def _make_auth(self) -> TabloAuth:
        auth = TabloAuth("user@example.com", "secret")
        return auth

    def test_happy_path_returns_device(self):
        auth = self._make_auth()

        post_responses = iter([
            _resp(LOGIN_OK),
            _resp(SELECT_OK),
        ])
        get_responses = iter([_resp(ACCOUNT_OK)])

        with patch.object(auth._session, "post", side_effect=post_responses), \
             patch.object(auth._session, "get",  side_effect=get_responses):
            devices = auth.discover()

        assert len(devices) == 1
        d = devices[0]
        assert d.sid == "SID_ABC"
        assert d.name == "Living Room Tablo"
        assert d.local_url == "http://10.0.0.5:8885"
        assert d.lighthouse_token == "lh_token_xyz"

    def test_login_failure_raises(self):
        auth = self._make_auth()
        bad = _resp({"message": "wrong password"}, ok=False, status_code=401)
        with patch.object(auth._session, "post", return_value=bad):
            with pytest.raises(TabloAuthError, match="Login failed"):
                auth.discover()

    def test_no_profiles_raises(self):
        auth = self._make_auth()
        account_no_profiles = {"profiles": [], "devices": ACCOUNT_OK["devices"]}
        post_r = iter([_resp(LOGIN_OK)])
        get_r = iter([_resp(account_no_profiles)])
        with patch.object(auth._session, "post", side_effect=post_r), \
             patch.object(auth._session, "get", side_effect=get_r):
            with pytest.raises(TabloAuthError, match="No profiles"):
                auth.discover()

    def test_no_devices_raises(self):
        auth = self._make_auth()
        account_no_devices = {"profiles": ACCOUNT_OK["profiles"], "devices": []}
        post_r = iter([_resp(LOGIN_OK)])
        get_r = iter([_resp(account_no_devices)])
        with patch.object(auth._session, "post", side_effect=post_r), \
             patch.object(auth._session, "get", side_effect=get_r):
            with pytest.raises(TabloAuthError, match="No devices"):
                auth.discover()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resp(data: dict, ok: bool = True, status_code: int = 200) -> MagicMock:
    m = MagicMock(spec=requests.Response)
    m.ok = ok
    m.status_code = status_code
    m.text = str(data)
    m.json.return_value = data
    m.raise_for_status = MagicMock()
    if not ok:
        m.raise_for_status.side_effect = requests.HTTPError(response=m)
    return m
