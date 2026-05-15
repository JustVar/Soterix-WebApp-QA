**Overview**
- Why migrate: Move from Selenium to Playwright for faster, more reliable, and easier-to-maintain UI tests.

# Selenium to Playwright Migration

## Current Status

**Migration Progress: 82% complete (173 of ~212 tests)**

| Metric | Value |
|--------|-------|
| Playwright Tests Passing | 173 |
| API Smoke Tests | 16 |
| Login UI Tests | 10 |
| Views UI Tests | 22 |
| Events UI Tests | 15 |
| Search UI Tests | 19 |
| Media UI Tests | 23 |
| Insights UI Tests | 26 |
| Maps UI Tests | 5 |
| Notifications UI Tests | 3 |
| Admin Users UI Tests | 7 |
| Admin Rules UI Tests | 12 |
| Admin Sites UI Tests | 9 |
| Chats UI Tests | 6 |
| Selenium Tests to Migrate | ~39 remaining |

## File Structure

### Legacy Selenium (Reference Only)
legacy-selenium-tests/test_vsaas_web/
├── test_vsaas_soterix.py (7,569 lines - main test file)
├── test_login_validator.py (487 lines)
├── test_login_webclient.py (585 lines)
└── conftest.py

### New Playwright Structure
tests/
├── api/
│   └── smoke/
│       ├── test_user_apis.py (5 tests)
│       ├── test_platform_apis.py (5 tests)
│       ├── test_camera_apis.py
│       ├── test_dashboard_apis.py
│       └── test_search_api.py
├── ui/
│   ├── login/
│   │   ├── test_login_valid.py (2 tests)
│   │   ├── test_login_invalid.py (5 tests)
│   │   ├── test_login_security.py (3 tests)
│   │   └── README.md
│   ├── views/
│   │   ├── conftest.py (shared fullscreen fixtures)
│   │   ├── test_views_basic.py (6 tests)
│   │   ├── test_views_drag_drop.py (7 tests)
│   │   ├── test_views_subtabs.py (10 tests)
│   │   ├── test_views_fullscreen.py (5 tests)
│   │   └── test_views_bookmarks.py (8 tests)
│   ├── events/
│   │   ├── test_events_search.py (10 tests)
│   │   └── test_events_playback.py (5 tests)
│   ├── search/
│   │   ├── test_search_filters.py (6 tests)
│   │   ├── test_search_categories.py (7 tests)
│   │   └── test_search_drawing.py (6 tests)
│   ├── media/
│   │   ├── conftest.py (media_page fixture)
│   │   ├── test_media_navigation.py (10 tests)
│   │   └── test_media_operations.py (13 tests)
│   ├── insights/
│   │   ├── conftest.py (insights fixtures)
│   │   ├── test_insights_navigation.py (7 tests)
│   │   └── test_insights_widgets.py (19 tests)
│   ├── maps/
│   │   └── test_maps.py (5 tests)
│   ├── notifications/
│   │   └── test_notifications.py (3 tests)
│   ├── admin/
│   │   ├── test_admin_users.py (7 tests)
│   │   ├── test_admin_rules.py (12 tests)
│   │   └── test_admin_sites.py (9 tests)
│   └── chats/
│       └── test_chats.py (6 tests)
└── shared/
    ├── pages/
    │   ├── login_page.py
    │   ├── views_page.py
    │   ├── fullscreen_page.py
    │   ├── events_page.py
    │   ├── search_page.py
    │   ├── media_page.py
    │   ├── insights_page.py
    │   ├── maps_page.py
    │   ├── admin_page.py
    │   └── chat_page.py
    ├── api_clients/
    │   ├── base_api_client.py
    │   ├── auth_helper.py
    │   └── site_discovery.py
    └── helpers/
        └── role_helper.py

## Migration Status by Module

| Module | Selenium Tests | Migrated | Net-New | Total Playwright | Status |
|--------|---------------:|--------:|--------:|-----------------:|--------|
| Login | 14 | 10 | 0 | 10 | ✅ DONE |
| API Tests | N/A | 0 | 16 | 16 | ✅ DONE (new) |
| Views - Thumbnail | 27 | 3 | 6 | 9 | ✅ DONE |
| Views - Full Screen | 13 | 13 | 0 | 13 | ✅ DONE |
| Events | 26 | 14 | 1 | 15 | ✅ DONE |
| Search | 24 | 13 | 6 | 19 | ✅ DONE |
| Media | 30 | 19 | 4 | 23 | ✅ DONE |
| Insights | 26 | 19 | 7 | 26 | ✅ DONE |
| Maps | 4 | 2 | 3 | 5 | ✅ DONE |
| Notifications | 3 | 2 | 1 | 3 | ✅ DONE |
| Admin Users | 9 | 5 | 2 | 7 | ✅ DONE |
| Chats | 12 | 5 | 1 | 6 | ✅ DONE |
| Admin Rules | 14 | 6 | 6 | 12 | ✅ DONE |
| Admin Sites | 9 | 9 | 0 | 9 | ✅ DONE |
| LPR | 0 | 0 | 0 | 0 | NOT STARTED |
| Admin - Other | 0 | 0 | 0 | 0 | NOT STARTED |
| **TOTAL** | **212** | **120** | **53** | **173** | **82%** |

## What's Been Migrated

### Login Module (COMPLETE)
- Login Page Object Model with ReCAPTCHA handling
- 10 login UI tests:
  - test_valid_credentials - Login with valid credentials
  - test_logout - Logout via profile menu
  - test_empty_fields - Validation for empty form
  - test_empty_username - Validation for missing email
  - test_empty_password - Validation for missing password
  - test_wrong_credentials - Invalid credentials handling
  - test_invalid_email_format - Email format validation
  - test_sql_injection_attempt - SQL injection protection
  - test_xss_attempt - XSS protection
  - test_password_too_short - Password length validation

### API Tests (NEW - Not in Selenium)
- 16 API smoke tests covering top platform APIs:
  - User Session API
  - User Roles API
  - Site Status API
  - Camera Tree API
  - Camera Snap API
  - Widgets API
  - Search API
  - Site/Enterprise auto-discovery

### Views Module (COMPLETE)
**Migrated from Selenium (3 tests):**
- test_camera_thumbnails_visible - Expand site, show camera thumbnails
- test_add_new_tab - Add tab, verify 4 new tiles created
- test_close_tab - Add tab, close it, verify removed

**Net-New Coverage (6 tests):**
- test_add_multiple_tabs - Verify multiple tabs can be created
- test_tab_naming_sequence - Verify tabs increment: View 1 -> View 2 -> View 3
- test_tab_naming_after_delete - Delete View 2, next tab is View 3
- test_cannot_delete_last_tab - Shows alert when deleting only tab
- test_rename_tab - Rename a tab to custom name
- test_rename_does_not_affect_sequence - Renamed tab doesn't break sequence

### Views - Full Screen Module (COMPLETE)
**Migrated from Selenium (13 tests) - originally 1 monolithic test decomposed:**

Core Full Screen (5 tests):
- test_enter_fullscreen - Enter full screen via zoom icon, verify stream loads
- test_exit_fullscreen - Enter and exit full screen, verify return to views grid
- test_fullscreen_pause_play - Pause and resume video in full screen
- test_fullscreen_controls_visible - Verify player controls visible (play, bookmarks, exit)
- test_fullscreen_video_streaming - Verify active streaming (no loader, no error)

Bookmark Operations (8 tests):
- test_open_bookmarks_panel - Open bookmarks panel via dots icon
- test_close_bookmarks_panel - Toggle bookmarks panel closed
- test_play_bookmark - Play first bookmark, verify playback
- test_bookmark_options_menu - Open 3-dot menu, verify 4 options
- test_export_bookmark - Export bookmark (dialog flow completes)
- test_share_bookmark - Share bookmark with email (success message)
- test_rename_bookmark - Rename bookmark, verify new name visible
- test_delete_bookmark - Delete bookmark with confirmation, verify removed

### Events Module (COMPLETE)
**Migrated from Selenium (3 monolithic tests decomposed into 15 focused tests):**

Event Search & Filtering (10 tests):
- test_navigate_to_events - Events nav link loads events page
- test_select_site - Site dropdown opens and site is selectable
- test_select_camera - Camera dropdown with location/camera selection
- test_select_duration - Duration filter changes from default
- test_select_rule - Rule type filter opens and rule is selectable
- test_search_events - Search returns event results
- test_event_snapshots_valid - Event thumbnails have valid images (not placeholders)
- test_pin_event - Pin icon works, pinned counter increments
- test_review_pinned_clips_button - "Review Pinned Clips" button appears
- test_search_with_specific_camera - Single-camera search via route intercept (CH 14 = Hanwha_6)

Event Playback & Export (5 tests):
- test_play_event_inline - Clicking Play Video loads inline player
- test_player_controls_visible - All player controls visible (play/pause, backward, forward, volume)
- test_event_action_toolbar - Action toolbar buttons visible (share, export, lightbox)
- test_close_event_player - Closing player returns to event results
- test_export_event - Export dialog flow completes (progress bar appears)

Note: Remaining 12 of the 26 Selenium "Events" tests belong to other modules
(Insights widgets, Global Search, Notifications, Admin) and will be migrated
with those modules.

**Camera checkbox workaround (02/08/2026):** MUI Checkbox has zero-dimension elements
that cannot be toggled via Playwright or JS. `search_events_for_channels()` uses
Playwright route interception to modify the API channelList, enabling per-camera
search testing at the API level. UI checkbox still requires an app-side fix.

### Search Module (COMPLETE)
**Migrated from Selenium (5 monolithic tests decomposed into 19 focused tests):**

Search Page Navigation & Filters (6 tests):
- test_navigate_to_search - Search nav link loads the Global Search page
- test_search_page_filters_visible - All filter dropdowns present (Category, Locations, Duration)
- test_select_category - Category dropdown opens and category is selectable
- test_select_duration - Duration dropdown opens and duration is selectable
- test_select_locations_cameras - Locations dropdown, site expand, All Cameras checkbox
- test_search_button_visible - Search execution button is visible on page load

Category Searches (7 tests):
- test_person_search - Person category with Male description returns results
- test_person_search_results_valid - Person results contain valid images
- test_person_search_play_result - Play Person result clip (flaky reruns=1: MediaSource stream intermittent)
- test_vehicle_search - Vehicle search returns results (skip: no vehicle data in Driver Site)
- test_vehicle_search_play_result - Play Vehicle result (skip: no vehicle data)
- test_event_search - Event category search returns results
- test_event_search_play_result - Play Event result clip (flaky reruns=1: MediaSource stream intermittent)

Zone & Line Drawing (6 tests):
- test_zone_search_draw_zone - Draw rectangular zone on camera canvas
- test_zone_search_returns_results - Zone search returns results after drawing
- test_zone_search_play_result - Play Zone search result clip
- test_line_search_draw_line - Draw line on camera canvas
- test_line_search_returns_results - Line search returns results after drawing
- test_line_search_play_result - Play Line search result clip

**Key discoveries (02/08/2026):**
- Search page button: `search-disable.svg` (disabled) -> `search-active.svg` (enabled)
- Scoped selector: `.search_container_search img[src*='search']` avoids nav sidebar match
- All Cameras checkbox: `input.click()` via JS on `.PrivateSwitchBase-input` works (unlike Events)
- Duration indices: [0]=Last 1 Hour, [1]=Last 2 Hours, [2]=Today, [3]=Yesterday, [4]=Last 7 Days, [5]=Last 30 Days, [6]=Custom
- Zone/Line camera selection: Dropdown search field (`.sidebarSearch input`) filters cameras; hover container shows "Create Zone"/"Create Line" link
- Vehicle search: No vehicle detections in Driver Site environment; needs different account/site
- Video playback: MediaSource blob URLs with `duration=Infinity`; stream loading intermittent (`readyState=0, duration=NaN`); Zone/Line more reliable than Person/Event (specific camera vs all cameras); all play_result tests use `@flaky(reruns=1)`

### Media Module (COMPLETE)
**Migrated from Selenium (19 tests from lines 5827-6452, decomposed into 23 focused tests):**

Media Navigation & Browsing (10 tests):
- test_navigate_to_media_page - Navigate to Media via sidebar
- test_select_date_filter - Select "Last 30 Days" filter
- test_switch_to_grid_view - Toggle from list to grid view
- test_all_tab - Verify All tab loads
- test_my_media_tab - Verify My Media tab loads
- test_shared_with_me_tab - Verify Shared with me tab loads
- test_clips_tab - Verify Clips tab loads
- test_folders_tab - Verify Folders tab loads
- test_vault_tab - Verify Vault tab loads
- test_search_media - Search by title/tags

Media Clip Operations (7 tests):
- test_clip_grouping - Select clip, group into folder
- test_clip_rename - Rename a clip via options menu
- test_clip_delete - Delete a clip via options menu
- test_clip_move_to_folder - Move clip to existing folder (skip: needs folder to exist)
- test_clip_create_link - Create shareable link for clip
- test_add_clip_to_vault - Add clip to Vault
- test_remove_clip_from_vault - Remove clip from Vault

Media Folder Operations (6 tests):
- test_folder_delete - Delete folder via options menu
- test_folder_create_link - Create shareable link for folder
- test_add_folder_to_vault - Add folder to Vault
- test_remove_folder_from_vault - Remove folder from Vault
- test_folder_share - Share folder via email
- test_folder_export - Export folder

**Key discoveries (02/09/2026):**
- Media nav: `a[href*='media']` sidebar link
- Date filter: `[role='combobox']` with MUI listbox option pattern
- Tabs: MUI Tab buttons `button:has-text('tab-name')`, Clips/Folders/Vault use `span:has-text()`
- Options menu: `img[src*='icon-options']` opens context menu with `li[role='menuitem']` items
- Move to folder: Native `<select>` dropdown (not MUI); use `select_option()` or JS; returns empty when no folders exist
- Create Link: Clicking menu item may not show a dialog (link created immediately)
- Vault icons: `img[alt='Add to Vault']` / `img[alt='Remove from Vault']`
- Confirm buttons: `.btn-modalForm` for delete/group; `button:has-text('Yes')` for vault removal
- Clip checkboxes: `.PrivateSwitchBase-input` (same MUI pattern as Events, but click works here)
- Empty state detection: `p:has-text('No results found for selected criteria')` with timeout-based check

### Insights Module (COMPLETE)
**Migrated from Selenium (13 tests from lines 2147-2290, decomposed into 26 focused tests):**

Insights Navigation & System Status (7 tests):
- test_navigate_to_insights - Navigate to Insights via sidebar
- test_system_status_link_visible - System Status link visible
- test_open_system_status_dashboard - Open dashboard, select site, verify Devices grid
- test_close_system_status_tab - Close System Status tab
- test_switch_to_widgets_tab - Switch from Dashboard to Widgets
- test_create_widget_button_visible - Create New Widget button visible
- test_widget_search_input_visible - Widget search input visible

Widget Create (11 parametrized tests):
- test_widget_create[Line_Person] through [Heat_Vehicle]
- All 4 graph types (Line, Bar, Pie, Heat) x 3 categories (Person, Vehicle, Event)
- minus Heat_Event (not in original Selenium tests)

Widget Operations (8 parametrized tests):
- test_widget_view[Line_Person, Bar_Person, Pie_Person] - View widget via three-dot menu
- test_widget_report[Line_Person, Bar_Event] - Download report, verify success
- test_widget_delete[Line_Person, Pie_Vehicle, Heat_Person] - Delete widget, verify removal

**Key discoveries (02/09/2026):**
- `.MuiPaper-root` index shifting: Camera expansion adds extra MuiPaper-root elements, shifting Duration/Size indices. Use label-based `_find_section_index()` helper
- `.PrivateSwitchBase-input` scope: Description section (Vehicle/Event) creates invisible checkboxes that persist in DOM. Use `_click_first_visible_checkbox()` to skip them
- Heat map camera: "All Cameras" is a header, not a selectable option. Must select an individual camera via JS traversal
- Widget creation form: 7 accordion sections (Graph, Category, Description, Site, Camera, Duration, Size)
- Graph type indices in dropdown: Line=0, Bar=1, Pie=4, Heat=5
- Strict mode: `p:text('Devices')` matches "Devices" and "Offline Devices". Use `p.grid-title:text-is('Devices')` for exact match
- Report download: MUI Popover/Backdrop can block `.save_button`. Wait for popover dismissal + force click fallback
- Widget success toast: `p:has-text('Widget created successfully')` - wait up to 60s for slow widget generation

**Run commands:**
```powershell
pytest tests/ui/insights/ -v --headed
pytest -m insights -v --headed
pytest tests/ui/insights/test_insights_widgets.py -k "Line_Person" -v --headed
```

### Maps Module (COMPLETE)
**Migrated from Selenium (2 tests decomposed into 5 focused tests):**

Maps Page (5 tests):
- test_navigate_to_maps - Navigate to Maps page, site dropdown visible
- test_select_site - Select site from dropdown, map cards appear
- test_map_cards_have_cameras - At least one map card has device count > 0
- test_open_map_with_cameras - Click map card, camera icons appear on map overlay
- test_play_online_camera - Click green camera icon, stream loads without failure

**Key discoveries (02/09/2026):**
- Maps is a standalone top-level page (`a[href*='maps']`), NOT the Views > Maps subtab
- Site dropdown: `.dropdown-box` with `.optionsdataDiv` options container
- Dropdown loading state: `.dropdown_text` title contains "sites" while loading
- Map cards: `.grid-cards` with `.icon-text-aligner` / `.icon-text-alinger` (typo in app) for device counts
- Camera icons: `img[src*='media/cameraIcon']` (all), `img[src*='media/cameraIconGreen']` (online)
- Stream failure: `text=failed to load` indicates playback error

### Notifications Module (COMPLETE)
**Migrated from Selenium (2 tests + 1 net-new = 3 focused tests):**

Notification Tests (3 tests):
- test_open_notification_panel - Click notification bell, panel opens with mute button visible
- test_mute_notifications - Click mute button, notification mute toggles
- test_admin_mute_rule_notification - Navigate Admin > General > Rules, click mute icon on last rule

**Key discoveries (02/09/2026):**
- Notification icons: `.header-right-group .icon` - second icon (index 1) opens panel
- Mute button: `img[src*='media/MuteNotification']` (may toggle to UnmuteNotification)
- Admin navigation: `a[href*='admin']` then `p:text-is('General')` then `p:text-is('Rules')`
- Rule mute icons: `img[aria-label='Mute Notification']` - click last one (same as Selenium pattern)
- No page object needed - simple enough for inline selectors

### Admin Users Module (COMPLETE)
**Migrated from Selenium (5 tests from lines 6455-6794, decomposed into 7 focused tests):**

Admin User Management (7 tests):
- test_navigate_to_admin_users - Navigate to Admin > Users section, user list visible
- test_add_user - Fill Add User form (name, email, role), save
- test_search_user - Search by name, results filter
- test_toggle_user_status - Toggle active/suspended switch
- test_role_filter_options - Role dropdown has 4 expected roles (Admin, Operator, Supervisor, Enterprise Super Admin)
- test_select_role_filter - Select a role from filter, verify selection displayed
- test_delete_user - Search user, click options > delete, confirm deletion

**Key discoveries (02/09/2026):**
- Admin nav: `a[href*='admin']` then `p:text-is('Users')` for Users tab
- Add User button: `button.add-btn` (same class used for Save: `button.add-btn.save-btn`)
- Form fields: `input[name='name'].modalForm-input`, `input[name='lastName'].modalForm-input`, `input[name='mailId'].modalForm-input`
- Role dropdown in form: `div.MuiStack-root.modalForm-input`, options in `#sitesBox li`
- User options menu: `img[src*='optionIcon']` opens menu, `img[src*='delete-icon']` for delete
- Delete confirmation: `div.MuiBox-root:has-text('Delete')` (shared pattern across Admin)
- Status toggle: `.MuiSwitch-root` (MUI Switch component)
- Role filter: `div[role='combobox']` with `li.MuiMenuItem-root` options
- Shared page object: `admin_page.py` will be reused by Admin Rules and Admin Sites

### Chats Module (COMPLETE)
**Migrated from Selenium (5 tests from lines 7394-7707, decomposed into 6 focused tests):**

Chat Panel Tests (6 tests):
- test_open_chat_panel - Click chat icon, panel opens with Create Group button visible
- test_create_group - Create group with name + member, group appears in list
- test_search_and_send_group_message - Open group, send message
- test_send_individual_message - Search individual user, send message
- test_edit_group_name - Edit group name via edit icon, verify updated
- test_delete_group - Delete group with confirmation, verify removed

**Key discoveries (02/09/2026):**
- Chat icon: `.header-right-group .icon` index 0 (NOT index 1 like notifications)
- Double-click pattern: Panel requires click-wait-click to open reliably
- Create Group button: `button.add-btn.save-btn:has-text('Create Group')`
- Group name input: `input[placeholder='Enter Group Name']`
- Member autocomplete: TAB to member field, type partial name, `ul.MuiAutocomplete-listbox li` for options
- Create submit: TAB+TAB+ENTER from member field (no explicit Create button after form)
- Chat search: `input.chat-search-input[placeholder='Search']` with `.related-result-item` results
- Group operations: `img[alt='Edit icon']`, `img[alt='Delete icon']`
- Message input: Reached via TAB from group conversation view
- Delete confirm: `div.MuiBox-root:has-text('Delete')` (same as Admin)

### Admin Rules Module (COMPLETE)
**Migrated from Selenium (14 tests from lines 3335-5797, collapsed into 12 focused tests):**

The Selenium suite had 5 nearly identical edit tests (one per rule type) and 6 identical delete tests. These were collapsed using pytest.parametrize for rule type selection, plus single edit/delete tests that work on pre-existing rules.

Admin Rule Tests (12 tests):
- test_navigate_to_rules - Navigate Admin > General > Rules, rule list visible
- test_add_new_rule_wizard_opens - Click Add New Rule, wizard opens with rule type options
- test_select_rule_type[Entry-Exit] - Select rule type, wizard advances (parametrized x6)
- test_select_rule_type[Heat Map]
- test_select_rule_type[Loitering]
- test_select_rule_type[Occupancy]
- test_select_rule_type[Intrusion Detection]
- test_select_rule_type[Line Crossing]
- test_search_rule - Search for rule by name
- test_edit_rule_notification - Edit rule notification settings (popUp + push toggle)
- test_delete_rule - Delete last rule with confirmation
- test_mute_rule_notification - Mute a rule's notification icon

**Key discoveries (02/09/2026):**
- Rules navigation: General tab > Rules tab (two clicks, not direct)
- Add New Rule button: `button:has-text('Add New Rule')`
- Rule types: `p:text-is('Entry-Exit')` etc. - 6 types available in wizard
- Wizard flow: Select type > Next > Select site > Next > Configure > Save
- Edit icons: `img[aria-label='Edit']` with negative index for last rule
- Delete icons: `img[aria-label='Delete']` with `button.btn-primary:has-text('Delete')` confirm
- Notification tab in edit modal: `button.btn-modalTab:has-text('Notification')`
- popUp/push checkboxes: `input[name='popUp']`, `input[name='push']` - need `force=True` click
- Update & Close: `button.btn-primary:has-text('Update & Close')`
- Mute icons: `img[aria-label='Mute Notification']` (same as Notifications module)
- Canvas drawing: `canvas.upper-canvas` with `page.mouse` for Entry-Exit/Line Crossing rules
- Rule search: `input.input-search-bar` (different from Users search `input[placeholder='Search']`)

### Admin Sites Module (COMPLETE)
**Migrated from Selenium (9 tests from lines 6797-7294, 1:1 mapping):**

Admin Site Management (9 tests):
- test_navigate_to_admin_sites - Navigate Admin > Sites, site list visible
- test_search_site - Search by site name
- test_toggle_grid_list_view - Toggle between grid and list view
- test_check_site_status - Sites display Online/Offline status indicators
- test_site_versions - Sites display version information
- test_navigate_to_online_site - Click site card to enter site detail
- test_camera_sorting - Sort cameras A-Z and Z-A within site
- test_create_camera_group - Create camera group with camera selection
- test_edit_camera_group - Edit camera group name

**Key discoveries (02/09/2026):**
- Sites tab: `p:text-is('Sites')` - direct click from Admin section
- View toggles: `img[alt='tableIcon']` (list), `img[src*='icon-grid']` (grid)
- Status icons: `img[alt='Online']`, `img[alt='Offline']`
- Version text: `p:has-text('Version:')` elements near site cards
- Sort icons: `img[src*='a-to-z-sort']`, `img[src*='z-to-a-sort']`
- Camera names in site detail: `div.site-card .MuiTypography-root`
- Camera groups accordion: `img[src*='downAccordionIcon']`
- Create New button: `div.MuiBox-root:has-text('Create New')`
- Group name input: `input[placeholder='Type here...']`
- Camera search in group: `input#outlined-adornment-search`
- Camera checkbox: `input.PrivateSwitchBase-input[type='checkbox']` with `force=True`
- Group edit icons: `img[alt='edit'].edit-icon` (different from rule edit icons)

## Key Improvements Over Selenium

| Feature | Selenium | Playwright |
|---------|----------|------------|
| Auto-wait | Manual WebDriverWait | Built-in auto-wait |
| Selectors | XPath heavy, brittle IDs | Stable name/data-testid |
| ReCAPTCHA | Ad-hoc workarounds | Retry logic with verification |
| Session reuse | Browser profile | Cookie + localStorage injection |
| Test speed | ~5-10 min | ~3-5 min |
| Debugging | Screenshots only | Traces, videos, screenshots |

## Migration Lessons Learned (by module)

### Common Patterns Across All Modules
| Pattern | Approach |
|---------|----------|
| MUI CircularProgress loader | Wait for `.MuiCircularProgress-root` visible then hidden |
| MUI Select dropdown | Click trigger, wait for `[role='listbox']`, click `li[role='option']` |
| MUI Checkbox (zero-dimension) | Use JS `input.click()` on `.PrivateSwitchBase-input` (works on Search/Media, NOT Events) |
| Element covered by overlay | Use `hover(force=True)` to bypass interception checks |
| `get_by_text()` matches toasts | Scope to panel container with JS `document.querySelector('.scrollBarCustom')` |
| Session caching | `authenticated_page` fixture with storage state; `conftest.py` handles fresh login fallback |
| MediaSource video streams | `duration=Infinity`, `readyState=0` means not loaded; use `@flaky(reruns=1)` for intermittent failures |
| Test data cleanup (yield fixtures) | All create/modify tests use `yield` in setup fixture with cleanup lists (`_created_widgets`, `_saved_view_names`, `_cleanup_actions`). Teardown runs even on assertion failure. Non-reversible ops documented with `# Cleanup: N/A` |

### Selector Strategy (Selenium XPath to Playwright CSS)
| Selenium XPath | Playwright Equivalent | Notes |
|---------------|----------------------|-------|
| `//button[contains(@class, "sidenavItem")]//span[text()="X"]` | `a[href*='x']` | Use nav link href over class+text |
| `//div[@role="combobox"]` | `[role='combobox']` | Direct CSS attribute match |
| `//img[contains(@src, "icon-options")]` | `img[src*='icon-options']` | CSS `*=` replaces XPath `contains()` |
| `//li[@role='menuitem' and contains(text(), 'X')]` | `li[role='menuitem']:has-text('X')` | Playwright `:has-text()` pseudo-class |
| `//button[normalize-space()='X']` | `button:has-text('X')` | Playwright auto-normalizes whitespace |
| `//p[contains(text(), 'X')]` | `p:has-text('X')` | Same pattern |
| `By.CLASS_NAME, 'PrivateSwitchBase-input'` | `.PrivateSwitchBase-input` | Direct class selector |

### Module-Specific Issues to Watch

| Module | Issue | Workaround | Status |
|--------|-------|------------|--------|
| Events | Camera checkbox zero-dimension | Route intercept `search_events_for_channels()` | Workaround in place; needs app fix |
| Search | Video stream fails to load | `@flaky(reruns=1)` - fresh page gets new stream | Stable |
| Search | Vehicle search no data | `@pytest.mark.skip` | Needs different account/site |
| Views | Bookmark tests need archive data | `@pytest.mark.skip` | Needs archive/timeline module first |
| Media | Move-to-folder needs existing folder | `pytest.skip()` at runtime if no folders | Check before asserting |
| Media | Create Link has no confirm dialog | Try-except around dialog wait (3s timeout) | Works - link created immediately |
| Media | Native `<select>` vs MUI | Check `el.tagName == 'SELECT'`, use JS `dispatchEvent('change')` | Different from all other dropdowns |
| Insights | `.MuiPaper-root` index shifting | `_find_section_index(label)` JS helper finds section by header text | Required for Duration/Size after camera expansion |
| Insights | Description checkboxes persist in DOM | `_click_first_visible_checkbox()` skips invisible description checkboxes | Affects Vehicle/Event categories |
| Insights | Heat map camera "All Cameras" not selectable | JS traversal to click first individual camera element | "All Cameras" is header only for Heat map |
| Insights | Report download button blocked by overlay | Wait for `.MuiPopover-root` hidden + force click fallback | Intermittent - three-dot menu popover may linger |

### Performance Observations
| Module | Tests | Avg Time | Notes |
|--------|-------|----------|-------|
| Login | 10 | ~30s | Session cache eliminates repeat logins |
| Views | 22 | ~180s | Drag-drop and fullscreen tests are slowest |
| Events | 15 | ~200s | Search + playback; route intercept adds ~2s |
| Search | 19 | ~300s | Zone/line drawing + play_result with flaky reruns |
| Media | 23 | ~630s | Tab navigation and CRUD operations; many `wait_for_timeout` calls |
| Insights | 26 | ~1700s | Widget creation is slow (~30-60s each); 11 parametrized creates dominate runtime |

## Syntax Quick Reference

| Selenium | Playwright |
|----------|------------|
| `driver.get(url)` | `page.goto(url)` |
| `driver.find_element(By.CSS, sel)` | `page.locator(sel)` |
| `element.click()` | `locator.click()` |
| `element.send_keys(text)` | `locator.fill(text)` |
| `WebDriverWait(...).until(...)` | `page.wait_for_selector(...)` |
| `driver.execute_script(js)` | `page.evaluate(js)` |

## How to Run Tests
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run all tests
pytest tests/ -v

# Run API tests only
pytest tests/api/smoke/ -v

# Run Login UI tests only
pytest tests/ui/login/ -v

# Run Media tests
pytest tests/ui/media/ -v --headed

# Run a specific module by marker
pytest -m media -v --headed
pytest -m search -v --headed
pytest -m events -v --headed
pytest -m insights -v --headed

# Run with visible browser
pytest tests/ui/login/ -v --headed
```

## How to Contribute to Migration

1. Pick a module from the "PENDING" list
2. Read the Selenium tests in `legacy-selenium-tests/`
3. Create Page Object Model in `tests/shared/pages/`
4. Create test file in appropriate `tests/ui/` subfolder
5. Run and validate tests
6. Update this migration status table
7. Commit and push

## Next Steps

1. ~~Migrate Search module (24 tests)~~ DONE (19 tests)
2. ~~Migrate Media module (30 tests)~~ DONE (23 tests)
3. ~~Migrate Insights module (26 tests)~~ DONE (26 tests)
4. ~~Migrate Maps module (4 tests)~~ DONE (5 tests)
5. ~~Migrate Notifications module (3 tests)~~ DONE (3 tests)
6. ~~Migrate Admin Users module (9 tests)~~ DONE (7 tests)
7. ~~Migrate Chats module (12 tests)~~ DONE (6 tests)
8. ~~Migrate Admin Rules module (14 tests)~~ DONE (12 tests)
9. ~~Migrate Admin Sites module (12 tests)~~ DONE (9 tests)
10. Revisit bookmark tests (6 skipped) - need archive/timeline tests to create bookmarks first
9. Manual vs automation gap analysis for bookmark coverage (QA Touch manual cases exist)
10. Fix SSL verification issue in base_api_client.py
11. Request ReCAPTCHA bypass for automation accounts

---

## QA Operations Hub - Test Execution & Debugging

> This section documents the QA Ops Hub architecture and how it integrates with the Playwright migration work. The QA Ops Hub is a FastAPI + HTMX web application deployed on the NUC server at `http://192.168.1.174/qa-ops/`. It serves as the central control plane for running, reviewing, and debugging automated tests.

### What It Does Today (v2.0)

| Feature | Description |
|---------|-------------|
| **Bug review queue** | Automated bug detections queued for QA approval before Jira filing |
| **Approve/Reject workflow** | HTMX-powered inline approve/reject with severity editing |
| **Jira bug creation** | "Create in Jira" button on approved items - all 8 NC mandatory fields populated |
| **PostgreSQL storage** | Full audit trail, query capability, concurrent-write safety (migrated from JSON) |
| **CLI integration** | `smart_jira_bug_creator.py` POSTs to web API; falls back to local JSON if NUC unreachable |
| **QA Touch pipeline** | pytest plugin uploads results to QA Touch test runs (`--qatouch-upload --qatouch-run <KEY>`) |

**Source:** `qa-ops/qa-ops-hub/` (separate repo) | **Dashboard:** `http://192.168.1.174/qa-ops/`

### Planned: Test Runner Architecture

The test runner enables QA team members to trigger and monitor automated test runs directly from the web dashboard, across all environments (QA, Staging, Production), with full auditing.

#### Multi-Runner Model

```
                    +---------------------------+
                    |   QA Ops Hub Dashboard    |
                    |   (NUC - 192.168.1.174)   |
                    |   FastAPI + HTMX + SSE    |
                    +-------------+-------------+
                                  |
                    +-------------+-------------+
                    |                           |
              +-----v------+            +------v------+
              | NUC Runner |            | Local Agent |
              | (Primary)  |            | (Fallback)  |
              +-----+------+            +------+------+
                    |                          |
          +---------+---------+        +-------+-------+
          |         |         |        |               |
       QA Env   Stage Env  Prod Env  QA Env        Stage Env
      (nightly)  (nightly)  (smoke)  (on-demand)   (on-demand)
```

**NUC as Primary Runner:**
- Intel i7-13700H (14 cores, 28 threads, 5GHz max), 64GB RAM, 233GB NVMe
- Currently ~1.3GB used / 62GB total - ample headroom for test runner + other services
- Scheduled nightly runs (QA regression 2 AM, Stage smoke 4 AM)
- Runs alongside: Asset Tracker scanner, Nginx, PostgreSQL, dashboards

**Local Dev Machine as Agent:**
- Lightweight Python agent registers with NUC via periodic heartbeat
- User triggers runs from the dashboard; NUC dispatches to available runner
- If NUC is unreachable, local agent serves a mini-dashboard at `localhost` for direct test triggering

#### Graceful Degradation

| Scenario | What Happens |
|----------|-------------|
| **NUC online + local agent** | Full dashboard: trigger runs, view live progress, browse artifacts |
| **NUC offline + local agent** | Local mini-dashboard: trigger runs locally, results stored until NUC reconnects |
| **NUC offline + no agent** | Raw `pytest` CLI with `--json-report` + `--tracing=retain-on-failure`; upload results later |
| **NUC online + no agent** | Dashboard read-only for run history; NUC handles scheduled runs only |

#### Environment Safety Gates

| Environment | Allowed Suites | Confirmation Required | Notes |
|-------------|---------------|----------------------|-------|
| QA | All (smoke, regression, module-specific) | No | Default target for all runs |
| Staging | All | Yes (one-click confirm) | Requires ReCAPTCHA bypass (pending) |
| Production | Smoke only | Yes + reason required | Read-only tests only; no mutations |

#### Run History & Audit

Every test run is logged in PostgreSQL:
- **Who** triggered it (username from HTTP Basic Auth)
- **What** suite and environment were selected
- **When** it started and finished
- **Results**: pass/fail/skip counts, duration, individual test outcomes
- **Artifacts**: links to traces, screenshots, and video recordings

### Planned: Playwright Trace Viewer Integration

The Trace Viewer enables debugging test failures directly from the dashboard, without requiring local Playwright installation or CLI access. This is critical for the India QA team (QA Engineer B, QA Engineer A) who access everything via browser.

#### How It Works

1. **Trace capture:** pytest configured with `--tracing=retain-on-failure` - saves `.zip` trace archives only for failed tests
2. **Artifact storage:** Traces stored on NUC in `/var/lib/qa-ops/artifacts/<run-id>/` - Nginx serves the directory
3. **Dashboard integration:** Run history page shows failed tests with clickable "View Trace" links
4. **Trace Viewer app:** Playwright's static Trace Viewer JS app loads in-browser, pointed at the stored trace URL
5. **No local setup needed:** Team members open trace in any browser - see DOM snapshots, network requests, action timeline, console logs

#### Additional Debugging Tools (Planned)

| Tool | Description |
|------|-------------|
| **Screenshot gallery** | Grid of failure screenshots per run; click to expand with test name, error message, and stack trace |
| **Video playback** | Playwright video recording on failure - playable inline from the dashboard |
| **Console log viewer** | Browser console output captured during test; searchable from dashboard |
| **Shareable trace links** | Generate a URL to a specific trace for pasting into Slack or Jira bug tickets |

### How This Fits With the Migration

The QA Ops Hub is the operational layer that makes the migrated Playwright tests actionable for the whole team:

| Migration Work | QA Ops Hub Enhancement |
|---------------|----------------------|
| 173 Playwright tests migrated | Dashboard "Run Tests" page triggers them across environments |
| QA Touch case mapping (87%) | Results auto-uploaded to QA Touch test runs; 2,874 total test cases in QA Touch |
| Smart bug detection | Bugs queued in dashboard, approved with one click, filed to Jira |
| Trace Viewer | Failed tests debuggable from browser - no local Playwright needed |
| Run history + analytics | Track pass/fail trends over time as migration adds more tests |

### Team Workflow (Future State)

**Daily workflow for QA team members:**

1. **Morning:** Check QA Ops Hub dashboard - review overnight NUC run results
2. **Review failures:** Click failed tests to view Trace Viewer, screenshots, video
3. **Bug filing:** Approve real bugs (one-click Jira creation), reject flakes/known issues
4. **On-demand runs:** Trigger smoke/regression from dashboard against QA or Stage
5. **New tests:** Write Playwright tests locally, push to git; NUC picks them up on next scheduled run
6. **Debugging:** Use Trace Viewer from dashboard, or run locally with `--headed` for visual debugging

**For India team (browser-only access):**
- All the above via `http://192.168.1.174/qa-ops/` - no local Python/Playwright setup required
- Trace Viewer, screenshots, and run history all accessible from the web dashboard

### Multi-User Sync

When multiple QA team members run tests concurrently:

| Concern | Solution |
|---------|----------|
| **Concurrent NUC runs** | Run queue - sequential per environment to avoid test interference |
| **Local + NUC runs** | Independent - local runs don't conflict with NUC; results sync to dashboard via API |
| **Result uploads** | Atomic per-run - each run gets a unique ID; no merge conflicts |
| **QA Touch uploads** | One run = one upload; concurrent uploads to different test runs are safe |
| **Git conflicts** | Tests are code - standard git workflow (branch, PR, merge); no test data in git |

### Creating New Automation Tests

QA team members who want to add new tests follow this workflow:

1. **Pick a module** from the pending migration list (Maps, Chats, Notifications, Admin)
2. **Read the Selenium tests** in `legacy-selenium-tests/` for reference
3. **Create a Page Object** in `tests/shared/pages/` following existing patterns
4. **Write tests** in `tests/ui/<module>/` using pytest + Playwright
5. **Run locally** with `pytest tests/ui/<module>/ -v --headed` to verify
6. **Push to git** - NUC picks up new tests on the next scheduled run
7. **Update this doc** - add module to migration status table

### CI/CD Coexistence (Post Engineer Hire)

When a CI/CD engineer is onboarded, the QA Ops Hub and CI/CD pipeline serve complementary roles using the **same test library** (`tests/`).

#### Two Systems, One Test Suite

```
Developer pushes code
        |
        v
  +---------------------+
  | CI/CD Pipeline       |  <-- Engineer's domain (gatekeeper)
  | (GitHub Actions)     |
  |  - Lint / static     |
  |  - Smoke suite       |
  |    (@ci_smoke, <2m)  |
  |  - PR gate (block)   |
  +----------+-----------+
             | passes --> merge & deploy
             v
  +---------------------+
  | QA Ops Hub           |  <-- QA team's domain (investigator)
  | (NUC Runner)         |
  |  - Post-deploy smoke |
  |    (webhook trigger) |
  |  - Nightly full      |
  |    regression (~50m) |
  |  - Bug detection +   |
  |    Jira filing       |
  |  - Trace Viewer      |
  +---------------------+
```

#### Role Separation

| Concern | CI/CD Pipeline | QA Ops Hub |
|---------|---------------|------------|
| **Triggered by** | Code push, PR merge, release tag | Human (dashboard), schedule (cron), deploy webhook |
| **Question it answers** | "Did this code change break anything?" | "Is this environment healthy right now?" |
| **Runs against** | Build artifacts / ephemeral environments | Live deployed environments (QA, Stage, Prod) |
| **Speed** | Fast - smoke only, fail-fast (<2 min) | Thorough - full regression, all modules |
| **Blocks deployment?** | Yes - PR gate | No - advisory, investigative |
| **Bug filing** | None - just pass/fail | Full pipeline: detection, review, Jira creation |
| **Debugging** | GitHub Actions logs | Trace Viewer, screenshots, video in dashboard |

#### Integration Points

1. **Deploy webhook:** CI/CD completes a deploy -> POSTs to QA Ops Hub `/api/webhook/deploy` -> auto-triggers post-deploy smoke on the target environment
2. **Shared markers:** `@pytest.mark.ci_smoke` (fast subset for pipeline gate) and `@pytest.mark.regression` (full suite for QA Ops Hub nightly) - same tests, different scopes
3. **Result aggregation:** QA Ops Hub dashboard pulls CI/CD results via GitHub API alongside its own runs - one unified view of all test activity
4. **Known-failure feed:** When QA Ops Hub confirms a test is a real bug (Jira created), it feeds back to CI as `@pytest.mark.xfail` - prevents blocking the pipeline on known issues

#### What QA Ops Hub Uniquely Handles (Even With Full CI/CD)

- Bug review queue with human-in-the-loop approval before Jira filing
- Trace Viewer for browser-based debugging (critical for India team)
- On-demand environment runs ("check if Events works on Stage right now")
- Nightly deep regression (too slow for CI/CD gates)
- Cross-environment comparison (same tests against QA vs Stage vs Prod)
- Run history, analytics, and long-term pass/fail trends
- Artifact storage with persistent traces, screenshots, and video

#### What the QA Ops Hub Provides the CI/CD Engineer

Having the QA Ops Hub already built when the CI/CD engineer starts means:
- **Test library is ready** - 173+ Playwright tests, organized by module, with pytest markers
- **No test infra to build** - the engineer focuses on pipeline config, not test execution tooling
- **Result reporting exists** - QA Touch upload, Jira bug creation, and dashboard analytics are pre-built
- **Environment config is solved** - multi-env support (QA/Stage/Prod) with safety gates already designed
- **Debugging is covered** - Trace Viewer and artifact storage handle failure investigation
