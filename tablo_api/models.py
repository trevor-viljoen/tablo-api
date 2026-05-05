"""Pydantic models returned by the Tablo API."""

from typing import Optional
from pydantic import BaseModel, computed_field


class TabloDevice(BaseModel):
    """A Tablo 4th Gen device discovered via the cloud account endpoint."""

    sid: str
    """Server ID, e.g. ``SID_5087B8536004``."""

    name: str
    """Human-readable device name from the Tablo cloud account."""

    local_url: str
    """Local LAN URL, e.g. ``http://192.168.1.100:8885``."""

    lighthouse_token: str
    """Per-session token used for cloud guide requests and local auth."""


class TabloChannel(BaseModel):
    """An OTA or OTT channel available on a Tablo device."""

    identifier: str
    """Cloud identifier, e.g. ``S122912_503_01``."""

    call_sign: str
    major: int
    minor: int
    network: str = ""
    kind: str = "ota"  # "ota" | "ott"

    @computed_field
    @property
    def display_name(self) -> str:
        return f"{self.major}.{self.minor} {self.call_sign}"

    def __lt__(self, other: "TabloChannel") -> bool:
        return (self.major, self.minor) < (other.major, other.minor)


class TabloStream(BaseModel):
    """An active live-stream session."""

    channel_identifier: str
    playlist_url: str
    token: Optional[str] = None
    expires: Optional[str] = None
    keepalive: Optional[int] = None


# ------------------------------------------------------------------
# Internal models for parsing cloud API responses
# ------------------------------------------------------------------

class _LoginResponse(BaseModel):
    token_type: str
    access_token: str

    @computed_field
    @property
    def auth_header(self) -> str:
        return f"{self.token_type} {self.access_token}"


class _Profile(BaseModel):
    identifier: str
    name: Optional[str] = None


class _CloudDevice(BaseModel):
    name: str
    serverId: str
    url: str


class _AccountResponse(BaseModel):
    profiles: list[_Profile]
    devices: list[_CloudDevice]


class _SelectResponse(BaseModel):
    token: str


class _ChannelInfo(BaseModel):
    major: Optional[int] = None
    minor: Optional[int] = None
    callSign: Optional[str] = None
    network: Optional[str] = None


class _CloudChannel(BaseModel):
    identifier: str
    name: Optional[str] = None
    kind: str = "ota"
    ota: Optional[_ChannelInfo] = None
    ott: Optional[_ChannelInfo] = None


class _WatchResponse(BaseModel):
    playlist_url: Optional[str] = None
    token: Optional[str] = None
    expires: Optional[str] = None
    keepalive: Optional[int] = None
