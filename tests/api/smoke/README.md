# API Smoke Tests

## Overview
This folder contains API smoke tests aimed at quickly validating core platform functionality across environments. The suite includes 16 tests covering user/session endpoints, platform-level dashboard and camera endpoints, and search APIs.

Scope:
- Lightweight smoke checks (status codes, basic response shape)
- Dynamic discovery of site and enterprise IDs via fixtures
- Tests intended to be fast and safe to run against test/QA environments

## Tests (16)
1. `test_get_user_session` - GET current user session; validate session response structure via `user_api.validate_session_response()`.
2. `test_get_user_roles` - GET user roles; assert response type (list/dict).
3. `test_get_enterprise_id_dynamic` - Validate dynamic enterprise ID derived from site status (fixture `test_enterprise_id`).
4. `test_get_roles_by_enterprise` - GET roles for dynamically discovered enterprise via `/REST/central/role/{enterpriseId}`; validate code/result and role fields.
5. `test_auto_discover_site_and_enterprise` - Ensure `discovered_site`, `discovered_site_id`, and `discovered_enterprise_id` fixtures return valid values.

6. `test_get_site_status` (platform) - GET `/REST/dashboard/site/{siteId}/status`; validate JSON response and presence of siteId.
7. `test_get_camera_tree` (platform) - GET `/REST/site/{siteId}/location/tree`; validate structure contains locations/devices.
8. `test_get_camera_snap` (platform) - GET `/REST/site/{siteId}/channel/{channelId}/snap`; accept binary image or JSON; validate JPEG/PNG magic bytes for images.
9. `test_get_widgets` (platform) - GET `/REST/dashboard/sharedwidgets/{customerId}/data`; validate result shape.
10. `test_search_person` (platform) - POST `/REST/site/search` with PERSON category payload for last hour; validate results structure.

11. `test_search_person_basic` - Search API helper for PERSON; basic type assertion for response.
12. `test_search_vehicle_basic` - Search API helper for VEHICLE; basic type assertion for response.

13. `test_get_site_status` (dashboard_api wrapper) - via `dashboard_api.get_site_status(test_site_id)` and `dashboard_api.validate_status_response()`.
14. `test_get_shared_widgets` (dashboard_api wrapper) - via `dashboard_api.get_shared_widgets(1)`; validate response shape.

15. `test_get_camera_tree` (camera_api wrapper) - `camera_api.get_camera_tree(test_site_id)` and validate via `camera_api.validate_camera_tree()`.
16. `test_get_camera_snapshot` (camera_api wrapper) - Discover a channel id and call `/REST/site/{siteId}/channel/{channelId}/snap`; validate response includes JPEG signature and expected content array.

## How to run
From repository root:

```bash
# Run API smoke tests
pytest tests/api/smoke/ -v
```

Target a specific environment by setting env variables or using the project's env config, e.g.: `ENV=qa BASE_URL=https://qa.example.invalid pytest tests/api/smoke/ -v`.

## API endpoints covered (examples)
- `/REST/auth/session` (user session)
- `/REST/central/role/{enterpriseId}` (roles)
- `/REST/dashboard/site/{siteId}/status` (site status)
- `/REST/site/{siteId}/location/tree` (camera/location tree)
- `/REST/site/{siteId}/channel/{channelId}/snap` (camera snapshot)
- `/REST/dashboard/sharedwidgets/{customerId}/data` (widgets)
- `/REST/site/search` (search)

## Fixtures used
- `api_base_url` - resolved API base URL for the active environment
- `api_auth_token` / `api_auth_helper` - provides auth token or helper for requests
- `user_api`, `dashboard_api`, `camera_api`, `search_api` - API client wrappers used by tests
- `discovered_site`, `discovered_site_id`, `discovered_enterprise_id`, `test_site_id`, `test_channel_ids` - auto-discovery fixtures to pick valid site/channel ids for tests

## Notes & Recommendations
- Some tests accept multiple valid shapes (JSON or binary) - assertions aim to be permissive to reduce false negatives.
- Consider centralizing magic values (e.g., default channel id `1`) into fixtures or config for clarity.

