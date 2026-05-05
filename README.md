# tablo-api

[![PyPI version](https://badge.fury.io/py/tablo-api.svg)](https://pypi.org/project/tablo-api/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![CI](https://github.com/trevor-viljoen/tablo-api/actions/workflows/ci.yml/badge.svg)](https://github.com/trevor-viljoen/tablo-api/actions)

> **Unofficial** Python wrapper for the undocumented Tablo 4th Gen (LighthouseTV) API. Use at your own risk — Nuvyyo may change endpoints without notice.

---

## Features

- Cloud authentication via `lighthousetv.ewscloud.com`
- Local device discovery (IP + port returned by cloud)
- OTA/OTT channel listing from the cloud guide
- Live-stream URLs via HMAC-MD5 signed local device requests
- Fully typed with [Pydantic v2](https://docs.pydantic.dev/) models

## Supported Hardware

| Device | Supported |
|--------|-----------|
| Tablo 4th Gen (2023+) | ✅ |
| Tablo 2nd / 3rd Gen | ❌ (different API, no auth required) |

---

## Installation

```bash
pip install tablo-api
```

Requires Python 3.11+.

---

## Quick Start

```python
from tablo_api import TabloAuth, TabloClient

# 1. Authenticate and discover local devices
auth = TabloAuth("you@example.com", "your-password")
devices = auth.discover()
print(devices)
# [TabloDevice(sid='SID_5087B8536004', name='Living Room Tablo', ...)]

# 2. Connect to the first device
client = TabloClient(devices[0])

# 3. List OTA channels
channels = client.channels()
for ch in channels:
    print(ch.display_name, "-", ch.network)
# 4.1 KFOR - NBC
# 5.1 KOCO - ABC

# 4. Start a live stream (returns HLS playlist URL)
stream = client.watch(channels[0])
print(stream.playlist_url)
# http://192.168.1.100:8885/stream/abc.m3u8

# 5. Feed to ffmpeg
import subprocess
subprocess.run(["ffmpeg", "-i", stream.playlist_url, "-c", "copy", "out.ts"])
```

---

## API Reference

### `TabloAuth(email, password, timeout=15)`

Authenticates with the Tablo cloud.

| Method | Returns | Description |
|--------|---------|-------------|
| `discover()` | `list[TabloDevice]` | Log in and return all linked devices |
| `make_device_auth(method, path, body="")` | `(auth_header, date_header)` | HMAC-MD5 auth for local requests |
| `device_date()` | `str` | RFC 1123 UTC timestamp |

### `TabloClient(device, timeout=15)`

Interacts with a single device.

| Method | Returns | Description |
|--------|---------|-------------|
| `channels(include_ott=False)` | `list[TabloChannel]` | OTA channel listing from cloud guide |
| `watch(channel)` | `TabloStream` | Start live stream, returns HLS URL |
| `ping()` | `str` | Device SID via unauthenticated `/ping` |
| `server_info()` | `dict` | Raw `/server/info` (requires auth) |

### Models

```python
TabloDevice(sid, name, local_url, lighthouse_token)
TabloChannel(identifier, call_sign, major, minor, network, kind)
TabloStream(channel_identifier, playlist_url, token, expires, keepalive)
```

---

## How It Works

Tablo 4th Gen dropped the open local API used by earlier hardware. All auth now goes through Nuvyyo's cloud (`lighthousetv.ewscloud.com`):

1. `POST /api/v2/login/` — email + password → Bearer token  
2. `GET /api/v2/account/` — device list with local IP/port  
3. `POST /api/v2/account/select/` — device-scoped Lighthouse token  
4. `GET /api/v2/account/{lighthouse_token}/guide/channels/` — channel guide  
5. `POST http://{local_ip}:8885/guide/channels/{id}/watch` — HMAC-MD5 signed → HLS URL

The HMAC-MD5 signing scheme was reverse-engineered from the Tablo iOS app by the [tablo2plex](https://github.com/hearhellacopters/tablo2plex) project.

---

## Security Notes

- Credentials are **never** stored by this library. Cache or store them yourself using a secure mechanism (e.g. system keychain).  
- All cloud traffic uses HTTPS.  
- Local device traffic uses plain HTTP (port 8885) — do not use over untrusted networks.
- The HMAC signing keys are static values embedded in the official Tablo app. They are **not** secret in the cryptographic sense; they only prevent trivially unauthenticated local requests.

---

## Contributing

Bug reports and PRs are welcome! Please open an issue before starting large changes.

```bash
git clone https://github.com/trevor-viljoen/tablo-api
pip install -e ".[dev]"
pytest
```

---

## Support

If this saves you time, consider buying me a coffee:

[![PayPal](https://img.shields.io/badge/PayPal-Donate-blue?logo=paypal)](https://paypal.me/trevorviljoen)
[![GitHub Sponsors](https://img.shields.io/badge/GitHub-Sponsor-ea4aaa?logo=github)](https://github.com/sponsors/trevor-viljoen)

---

## License

MIT — see [LICENSE](LICENSE).

> This project is not affiliated with Nuvyyo Inc. or Tablo. "Tablo" is a trademark of Nuvyyo Inc.
