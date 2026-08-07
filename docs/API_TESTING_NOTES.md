# API Testing Notes - Camera Discovery (QA)

> Auth and environment details moved to **`docs/API_SURFACES.md`**, which covers
> both the internal (`/v-apiserver`) and integration (`/v-integration-api`) APIs.
> This file now only covers camera/channel discovery.

## QA Environment Configuration

| Setting | Value |
|---------|-------|
| Base URL | https://qa.example.invalid |
| API Path | /v-apiserver |
| Site ID | 17 (`TEST_SITE_ID`) |

Updated 2026-08-05. The old host `qa.example.invalid` **no longer
resolves in DNS**, and site `110` returns 400 for the current account - its
valid sites are `16, 17, 105, 109, 111`. The camera inventory below was captured
against site 110 on the previous host and is retained only as a historical
reference; use `tools/discover_cameras.py` for the live topology.

## Authentication

- JSESSIONID cookie-based auth (not JWT)
- Obtained over HTTP with **no browser**: `POST /REST/central/user/login` with a
  SHA512-hashed password - see `docs/API_SURFACES.md` for the exact payload
- Session cached in `.session_cache` (8 hour TTL)

> **Correction (2026-08-05).** This file previously stated that "API login
> returns 400 for qa-lab account (expected)" and that the suite "falls back to UI
> login via Playwright". That was a bug being recorded as intended behaviour. The
> 400 was caused by calling the captcha-gated `/REST/central/user/auth/login`
> with a plaintext password. The UI fallback is now opt-in only
> (`ALLOW_UI_LOGIN_FALLBACK=1`) and API runs launch no browser at all.

## Camera API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| /REST/site/{site_id}/channel | GET | List all cameras/channels |
| /REST/site/{site_id}/channel/{channel_id}/snap | GET | Get camera snapshot |

### Snapshot Response Format

```json
{
  "status": 2000,
  "code": 200,
  "result": [
    {
      "content": [-1, -40, -1, -32, ...]
    }
  ]
}
```

- First two bytes `[-1, -40]` = `0xFF 0xD8` = JPEG signature

## Channel ID Assignment

Channel IDs appear to be assigned sequentially based on the order cameras are authenticated/added to the site.

## Camera Inventory (Site 110 - QA Lab)

| Channel | Name | Brand |
|---------|------|-------|
| 1 | Axis_3 | Axis |
| 2-4 | Avigilon-Multi_1.1-1.3 | Avigilon |
| 5 | Avigilon-Thermal | Avigilon |
| 6-8 | Hanwha_5, _6, _Encoder_27 | Hanwha |
| 9 | Advidia (Internal Audio) | ONVIF |
| 10 | Axis_4 | Axis |
| 11 | IPRO-Internal Mic | i-Pro |
| 12-15 | Hanwha_3, _2, _PTZ, _Fisheye | Hanwha |
| 16 | Vivotek_1 | ONVIF |
| 17-22 | Hanwha_7, _Multi_1.1-1.4, _8 | Hanwha |
| 23-24 | Axis_1, _2 | Axis |
| 25 | Avigilon Video Intercom | Avigilon |

## Discovery & Dynamic Environments

The test suite supports dynamic camera/site topologies via a `DiscoveryHelper`.
It attempts to discover sites and channels at session startup and prefers channels
that expose a `snapUrl` (snapshot-capable). Discovery is cached for the test
session to avoid repeated API calls.

CLI tool: `tools/discover_cameras.py` can be used to inspect a site's cameras and
their snapshot capability.

Usage:

```powershell
python tools/discover_cameras.py --env qa
python tools/discover_cameras.py --env staging --site 120
```

Tests adapt automatically when cameras are added/removed; the `test_channel_ids`
fixture picks snapshot-capable channels first, then falls back to any channel
ids discovered for the site.
