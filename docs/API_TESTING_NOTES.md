# API Testing Notes - Camera Discovery (QA)
# API Testing Notes

## QA Environment Configuration

| Setting | Value |
|---------|-------|
| Base URL | https://qa.example.invalid |
| API Path | /v-apiserver |
| Site ID | 110 |
| Total Cameras | 25 |
| Channel IDs | 1-25 (sequential) |

## Authentication

- Uses JSESSIONID cookie-based auth (not JWT)
- API login returns 400 for qa-lab account (expected)
- Falls back to UI login via Playwright
- Session cached in `.session_cache` (8 hour TTL)

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
