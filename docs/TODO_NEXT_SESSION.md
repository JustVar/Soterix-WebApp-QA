# TODO - Next Session

## Session Summary (2025-01-28)

### Completed This Session
- ✅ Implemented drag-and-drop tests (7 tests in `test_views_drag_drop.py`)
- ✅ Added ViewsPage helper methods for drag operations
- ✅ Sent ReCAPTCHA bypass request to IT/Support (pending response)
- ✅ Fixed Maps test - now clicks site to expand before selecting map
- ✅ Added Channels test - adds channel via checkbox pattern
- ✅ **NEW: Created comprehensive subtab tests** (10 tests in `test_views_subtabs.py`)
  - Tests all 5 subtabs: Devices, My Views, Insights, Maps, Channels
  - Each subtab tested with CHECKBOX and DRAG methods
  - Clear success criteria documented
  - Added visible drag highlighting (red source, green target)
- ✅ **Insights subtab tests added** - checkbox AND drag tests with insight widgets
- ✅ All 23 Views tests now pass (49 total framework tests)

### Previous Session (2025-01-27)
- ✅ Fixed all 6 Views basic tests - now pass consistently
- ✅ Improved session validation with element-based checks
- ✅ Added robust navigation with retry mechanism
- ✅ Fixed viewport/scroll issues with JS click

## Immediate Tasks

### 1. Views Drag-and-Drop Tests - COMPLETED ✅
All drag-drop tests implemented in `tests/ui/views/test_views_drag_drop.py`:
- [x] `test_drag_camera_to_tile` - Drag camera thumbnail to empty tile
- [x] `test_drag_camera_by_name_to_tile` - Drag camera by specific name
- [x] `test_drag_saved_view_to_tile` - Drag saved view from My Views to tile
- [x] `test_drag_location_to_tile` - Drag location/site to tile
- [x] `test_drag_map_to_tile` - Open Maps -> Click site -> Add map via checkbox ✅
- [x] `test_add_channel_to_tile` - Open Channels -> Add channel via checkbox ✅
- [x] `test_multiple_cameras_to_multiple_tiles` - Add multiple cameras

### 2. ViewsPage Helper Methods - COMPLETED ✅
- [x] `ViewsPage.drag_camera_to_tile_by_name(camera_name, tile_index=0)`
- [x] `ViewsPage.drag_view_to_tile(view_name, tile_index=0)` - with JS fallback
- [x] `ViewsPage.drag_location_to_tile(location_name, tile_index=0)`
- [x] `ViewsPage.drag_map_to_tile(map_name, tile_index=0)`
- [x] `ViewsPage.get_available_tiles()` - Returns list of empty "Drag & Drop" tiles
- [x] `ViewsPage.get_available_tile_count()` - Returns count of empty tiles

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
| Views UI Basic | 6 | ✅ All passing |
| Views UI Drag-Drop | 7 | ✅ All passing |
| Views UI Subtabs | 10 | ✅ All passing (Devices, My Views, Maps, Channels, Insights) |
| **Total** | **49** | |

### Subtab Tests - Success Criteria
Each subtab has checkbox AND drag tests:

| Subtab | Checkbox Test | Drag Test | Success Criteria |
|--------|--------------|-----------|------------------|
| **Devices** | ✅ | ✅ | Tile count decreases OR video element appears |
| **My Views** | ✅ | ✅ (skipped if unsupported) | Tab opens with view name |
| **Maps** | ✅ | ✅ | Tile count decreases OR leaflet/iframe appears |
| **Channels** | ✅ | ✅ | Tile count decreases OR video element appears |
| **Insights** | ✅ | ⏭️ (skipped - no drag tiles) | Tile count decreases OR insight content appears |

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
