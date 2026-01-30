# TODO - Next Session

## Session Summary (2025-01-29)

### Completed This Session
- Registered 12 new pytest markers in pytest.ini
- Added prefixed markers for Views subtabs (views_devices, views_myviews, views_maps, views_channels, views_insights)
- Added markers to all 23 Views tests (3 files)
- Fixed norecursedirs to exclude legacy-selenium-tests folder
- Verified markers working with --collect-only

### Previous Sessions
- 49 tests passing (16 API + 10 Login + 23 Views)
- Session caching implemented (86% faster test setup)
- All Views subtab tests complete (Devices, My Views, Maps, Channels, Insights)

## Immediate Tasks

### 1. Add Markers to Login and API Tests
- [ ] Add markers to 10 Login tests (ui, smoke/sanity)
- [ ] Add markers to 16 API tests (api, smoke)

### 2. Continue Views Migration - Remaining Tests
- [ ] Share live view tests
- [ ] Sequence/playlist tests
- [ ] Grid layout switching tests

### 3. Events Module Migration (26 tests)
- [ ] Create EventsPage Page Object Model
- [ ] Migrate 26 events tests from legacy Selenium

## Test Summary

| Category | Tests | Markers Added |
|----------|-------|---------------|
| API Smoke | 16 | Not yet |
| Login UI | 10 | Not yet |
| Views Basic | 6 | Complete |
| Views Drag-Drop | 7 | Complete |
| Views Subtabs | 10 | Complete |
| **Total** | **49** | **23 of 49** |

## Commands Reference

```powershell
# Activate environment
.\.venv\Scripts\Activate.ps1

# Run all tests
pytest tests/ -v

# Run by marker
pytest -m views_devices -v
pytest -m "subtabs and checkbox" -v
pytest -m "not slow" -v

# Collect only (verify markers without running)
pytest --collect-only -m views_myviews -v

# Run with visible browser
pytest tests/ui/views/ -v --headed

# Clear session cache if auth expires
Remove-Item .auth_state.json
```

## Pending External Actions

- [ ] ReCAPTCHA bypass - request sent to IT/Support (pending response)
- [ ] QA Touch - waiting for yearly license
- [ ] Jira - company-managed instance in test phase

## Marker Naming Convention

Use prefixed names for module-specific markers to avoid conflicts:

| Module | Pattern | Examples |
|--------|---------|----------|
| Views | views_* | views_devices, views_maps |
| Admin | admin_* | admin_maps, admin_users |
| Nav | nav_* | nav_insights, nav_search |
