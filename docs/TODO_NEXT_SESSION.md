# TODO - Next Session

## Session Summary (2025-01-27)

### Completed This Session
- ✅ Fixed all 6 Views tests - now pass consistently (~4.5 min)
- ✅ Improved session validation with element-based checks
- ✅ Added robust navigation with retry mechanism
- ✅ Fixed viewport/scroll issues with JS click

## Immediate Tasks

### 1. Views Drag-and-Drop Tests (Priority)
Implement tests for dragging elements to view tiles:
- [ ] `test_drag_camera_to_tile` - Drag camera thumbnail to empty tile
- [ ] `test_drag_saved_view_to_tile` - Drag saved view from My Views to tile
- [ ] `test_drag_location_to_tile` - Drag location/site to tile (shows all cameras)
- [ ] `test_drag_map_to_tile` - Drag map element to tile

**Reference:** Legacy Selenium `test_vsaas_soterix.py`:
- Lines 179-186: Camera drag-drop pattern
- Lines 801-807: Location drag-drop
- Lines 872: Maps drag-drop
- Lines 913-916: Saved views drag-drop

### 2. ViewsPage Helper Methods for Drag-Drop
- [ ] `ViewsPage.drag_camera_to_tile(camera_name, tile_index=0)`
- [ ] `ViewsPage.drag_saved_view_to_tile(view_name, tile_index=0)`
- [ ] `ViewsPage.drag_location_to_tile(location_name, tile_index=0)`
- [ ] `ViewsPage.get_available_tiles()` - Returns list of empty "Drag & Drop" tiles

### 3. Clean Up Debug Code
- [ ] Extract JS hover+click pattern to ViewsPage helper method
- [ ] Create `ViewsPage.click_save_button()` using JS click

## Views Module - Legacy Selenium Migration

### Source File
`legacy-selenium-tests/test_vsaas_web/test_vsaas_soterix.py` (~375KB)

### Tests to Migrate
| Legacy Test | Playwright Status | Notes |
|-------------|-------------------|-------|
| `test_addtab_saveview_openview` | ✅ Migrated | Split into 6 tests |
| `test_share_live_view` | ⬜ TODO | Share functionality |
| `test_add_created_sequence_to_views` | ⬜ TODO | Sequence/playlist feature |
| `test_media_switch_to_grid_view` | ⬜ TODO | Grid layout switching |
| Drag camera to tile | ⬜ TODO | Lines 179-186 |
| Drag location to tile | ⬜ TODO | Lines 801-807 |
| Drag maps to tile | ⬜ TODO | Line 872 |
| Drag saved view to tile | ⬜ TODO | Lines 913-916 |

### Patterns Discovered in Legacy Code
```python
# Selenium drag-drop pattern (to migrate to Playwright)
actions = ActionChains(driver)
actions.move_to_element(camera).pause(1).drag_and_drop(camera, tile).perform()

# Tile selector
tile_elements = driver.find_elements(By.XPATH, "//div[text()='Drag & Drop Camera here']")
```

## Test Summary

| Category | Tests | Status |
|----------|-------|--------|
| API Smoke | 16 | ✅ All passing |
| Login UI | 10 | ✅ All passing |
| Views UI | 6 | ✅ All passing |
| **Total** | **32** | |

## Commands Reference
```powershell
# Activate environment
.\.venv\Scripts\Activate.ps1

# Run all tests
pytest tests/ -v

# Run Views tests only
pytest tests/ui/views/ -v

# Run with visible browser
pytest tests/ui/views/ -v --headed

# Clear session cache if auth expires
Remove-Item .auth_state.json
```

## Pending External Actions

### ReCAPTCHA Bypass
- [ ] Send request to tech team (see docs/RECAPTCHA_BYPASS_PLAN.md)
- [ ] Create automation accounts for all environments

### Tool Integration
- [ ] QA Touch - waiting for license
- [ ] Jira - setup in progress
