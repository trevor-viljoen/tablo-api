"""Cloud authentication for the Tablo 4th Gen (LighthouseTV)."""

import hashlib
import hmac
import uuid
from datetime import datetime, timezone
from email.utils import format_datetime

import requests

from .models import (
    TabloDevice,
    _AccountResponse,
    _LoginResponse,
    _SelectResponse,
)

_CLOUD_HOST = "https://lighthousetv.ewscloud.com"
_USER_AGENT = "Tablo-FAST/2.0.0 (Mobile; iPhone; iOS 16.6)"

# HMAC-MD5 signing keys extracted from the Tablo iOS app
_HASH_KEY = "6l8jU5N43cEilqItmT3U2M2PFM3qPziilXqau9ys"
_DEVICE_KEY = "ljpg6ZkwShVv8aI12E2LP55Ep8vq1uYDPvX0DdTB"


class TabloAuth:
    """Authenticates with the Tablo cloud and discovers local devices.

    Usage::

        auth = TabloAuth("you@example.com", "password")
        devices = auth.discover()          # list[TabloDevice]
        client = TabloClient(devices[0])
    """

    def __init__(self, email: str, password: str, timeout: int = 15) -> None:
        self.email = email
        self.password = password
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers["User-Agent"] = _USER_AGENT
        self._login_resp: _LoginResponse | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover(self) -> list[TabloDevice]:
        """Log in to the Tablo cloud and return all linked devices."""
        login = self._login()
        account = self._get_account(login.auth_header)

        if not account.profiles:
            raise TabloAuthError("No profiles found on this Tablo account.")
        if not account.devices:
            raise TabloAuthError("No devices found on this Tablo account.")

        pid = account.profiles[0].identifier
        client_id = str(uuid.uuid4())
        devices: list[TabloDevice] = []

        for dev in account.devices:
            token = self._select_account(pid, dev.serverId, login.auth_header)
            devices.append(
                TabloDevice(
                    sid=dev.serverId,
                    name=dev.name,
                    local_url=dev.url,
                    lighthouse_token=token,
                    account_token=login.access_token,
                    client_id=client_id,
                )
            )

        return devices

    # ------------------------------------------------------------------
    # HMAC-MD5 signing for local device requests
    # ------------------------------------------------------------------

    @staticmethod
    def device_date() -> str:
        """RFC 1123 / HTTP-date string in GMT, required for device auth."""
        return format_datetime(datetime.now(timezone.utc), usegmt=True)

    @staticmethod
    def make_device_auth(method: str, path: str, body: str = "") -> tuple[str, str]:
        """Return ``(Authorization, Date)`` headers for a local device request.

        Implements ``Encryption.makeDeviceAuth`` from the tablo2plex project.
        """
        date = TabloAuth.device_date()
        msg_hash = hashlib.md5(body.encode()).hexdigest() if body else ""
        payload = f"{method}\n{path}\n{msg_hash}\n{date}"
        sig = hmac.new(_HASH_KEY.encode(), payload.encode(), hashlib.md5).hexdigest()
        return f"tablo:{_DEVICE_KEY}:{sig}", date

    # ------------------------------------------------------------------
    # Private cloud calls
    # ------------------------------------------------------------------

    def _login(self) -> _LoginResponse:
        resp = self._session.post(
            f"{_CLOUD_HOST}/api/v2/login/",
            json={"email": self.email, "password": self.password},
            timeout=self.timeout,
        )
        if not resp.ok:
            raise TabloAuthError(f"Login failed ({resp.status_code}): {resp.text}")
        self._login_resp = _LoginResponse.model_validate(resp.json())
        return self._login_resp

    def _get_account(self, auth_header: str) -> _AccountResponse:
        resp = self._session.get(
            f"{_CLOUD_HOST}/api/v2/account/",
            headers={"Authorization": auth_header},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return _AccountResponse.model_validate(resp.json())

    def _select_account(self, pid: str, sid: str, auth_header: str) -> str:
        resp = self._session.post(
            f"{_CLOUD_HOST}/api/v2/account/select/",
            json={"pid": pid, "sid": sid},
            headers={"Authorization": auth_header},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return _SelectResponse.model_validate(resp.json()).token


class TabloAuthError(Exception):
    """Raised when authentication with the Tablo cloud fails."""
