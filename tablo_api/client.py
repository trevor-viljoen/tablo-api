"""Tablo 4th Gen API client — channel listing and live streaming."""

import json
import uuid

import requests

from .auth import TabloAuth
from .models import (
    TabloChannel,
    TabloDevice,
    TabloStream,
    _CloudChannel,
    _WatchResponse,
)

_CLOUD_HOST = "https://lighthousetv.ewscloud.com"
_LOCAL_USER_AGENT = "Tablo-FAST/1.7.0 (Mobile; iPhone; iOS 18.4)"
_CLOUD_USER_AGENT = "Tablo-FAST/2.0.0 (Mobile; iPhone; iOS 16.6)"


class TabloClient:
    """High-level client for a single Tablo 4th Gen device.

    Obtain a :class:`~tablo_api.models.TabloDevice` from
    :class:`~tablo_api.auth.TabloAuth` first::

        from tablo_api import TabloAuth, TabloClient

        devices = TabloAuth("you@example.com", "secret").discover()
        client = TabloClient(devices[0])

        channels = client.channels()
        stream = client.watch(channels[0])
        print(stream.playlist_url)   # HLS manifest → feed to ffmpeg or AVPlayer
    """

    def __init__(self, device: TabloDevice, timeout: int = 15) -> None:
        self.device = device
        self.timeout = timeout
        self._session = requests.Session()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def channels(self, include_ott: bool = False) -> list[TabloChannel]:
        """Return channels from the Tablo cloud guide for this device."""
        path = f"/api/v2/account/{self.device.lighthouse_token}/guide/channels/"
        resp = self._session.get(
            f"{_CLOUD_HOST}{path}",
            headers={
                "Authorization": f"Bearer {self.device.account_token}",
                "Lighthouse": self.device.lighthouse_token,
                "Accept": "*/*",
                "User-Agent": _CLOUD_USER_AGENT,
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()

        out: list[TabloChannel] = []
        for raw in resp.json():
            ch = _CloudChannel.model_validate(raw)
            if not include_ott and ch.kind == "ott":
                continue
            info = ch.ota or ch.ott
            call_sign = (info and info.callSign) or ch.name or ch.identifier
            major = (info and info.major) or 0
            minor = (info and info.minor) or 0
            out.append(
                TabloChannel(
                    identifier=ch.identifier,
                    call_sign=call_sign,
                    major=major,
                    minor=minor,
                    network=(info and info.network) or "",
                    kind=ch.kind,
                )
            )

        return sorted(out)

    def watch(self, channel: "TabloChannel | str") -> TabloStream:
        """Start a live stream and return the HLS playlist URL.

        ``channel`` may be a :class:`TabloChannel` or a raw identifier string.
        """
        identifier = channel.identifier if isinstance(channel, TabloChannel) else channel
        path = f"/guide/channels/{identifier}/watch"

        body = json.dumps(
            {
                "bandwidth": None,
                "extra": {
                    "limitedAdTracking": 1,
                    "deviceOSVersion": "16.6",
                    "lang": "en_US",
                    "height": 1080,
                    "deviceId": "00000000-0000-0000-0000-000000000000",
                    "width": 1920,
                    "deviceModel": "iPhone10,1",
                    "deviceMake": "Apple",
                    "deviceOS": "iOS",
                },
                "device_id": self.device.client_id,
                "platform": "ios",
            }
        )

        auth_header, date_header = TabloAuth.make_device_auth("POST", path, body)

        resp = self._session.post(
            self.device.local_url.rstrip("/") + path,
            data=body.encode(),
            headers={
                "Authorization": auth_header,
                "Date": date_header,
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "*/*",
                "Connection": "keep-alive",
                "User-Agent": _LOCAL_USER_AGENT,
            },
            timeout=self.timeout,
        )

        if resp.status_code == 401:
            raise TabloStreamError(
                "Device rejected the request (401). "
                "Ensure TabloAuth.discover() was called before creating this client — "
                "the device must be registered via cloud auth before it accepts local requests."
            )
        resp.raise_for_status()

        watch = _WatchResponse.model_validate(resp.json())
        if not watch.playlist_url:
            raise TabloStreamError(f"No playlist_url in response: {resp.text}")

        return TabloStream(
            channel_identifier=identifier,
            playlist_url=watch.playlist_url,
            token=watch.token,
            expires=watch.expires,
            keepalive=watch.keepalive,
        )

    def ping(self) -> str:
        """Return the device SID via the unauthenticated ``/ping`` endpoint."""
        resp = self._session.get(
            self.device.local_url.rstrip("/") + "/ping",
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json().get("sid", "")

    def server_info(self) -> dict:
        """Return raw ``/server/info`` (requires prior cloud auth)."""
        path = "/server/info"
        auth_header, date_header = TabloAuth.make_device_auth("GET", path)
        resp = self._session.get(
            self.device.local_url.rstrip("/") + path,
            headers={
                "Authorization": auth_header,
                "Date": date_header,
                "Accept": "*/*",
                "Connection": "keep-alive",
                "User-Agent": _LOCAL_USER_AGENT,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()


class TabloStreamError(Exception):
    """Raised when a live stream cannot be started."""
