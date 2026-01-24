# API Testing Status

## Current Test Results (QA Environment)

| Test | Status | Notes |
|------|--------|-------|
| test_get_user_session | ✅ PASS | |
| test_get_user_roles | ⏭️ SKIP | No roles endpoint |
| test_get_camera_tree | ✅ PASS | |
| test_get_camera_snapshot | ✅ PASS | Returns JSON with byte array |
| test_get_site_status | ✅ PASS | |
| test_get_shared_widgets | ✅ PASS | |
| test_search_person_basic | ⏭️ SKIP | Needs HAR capture |
| test_search_vehicle_basic | ⏭️ SKIP | Needs HAR capture |

## Running Tests

```powershell
# Set environment
$env:ENV="qa"

# Run all API smoke tests
python -m pytest tests/api/smoke/ -v -s

# Run specific test file
python -m pytest tests/api/smoke/test_camera_apis.py -v -s

# Run single test
python -m pytest tests/api/smoke/test_camera_apis.py::test_get_camera_snapshot -v -s
```

## Session Caching

- Token cached in `.session_cache`
- Valid for 8 hours
- Delete file to force re-authentication:

```powershell
Remove-Item .session_cache
```
