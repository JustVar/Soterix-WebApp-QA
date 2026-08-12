# Test repair register

Tests that need reinvestigation, repair, or a verification run before we
write any new tests. Work this list top to bottom; do not add new test
files while an item here is open. Sourced from the 08/08-08/11/2026 conversion and repair work and the
live verify runs, extended through the 08/12/2026 repairs.

Status tokens: [REDO] rebuild against the current app, [INVESTIGATE]
find out whether the feature moved or died, [VERIFY] suite not run since
the page-object conversion, [DATA] stale tenant data in the test,
[ARTIFACT] test support files wrong, [WATCH] warning print to chase,
[WIP] rebuild underway, [DONE] repaired and verified green.

## A. Broken or never-worked - needs a rebuild

| Test | Status | Detail |
|------|--------|--------|
| tests/ui/views/test_views_favorites.py::test_add_remove_favorites | [DONE] | Green 08/09/2026 - first time since the test was written (locator was XPath-in-CSS and never parsed since 03/2026). Full repair: parseable row-scoped locator, config camera name, clean-start toggle, and the real blocker: the camera tree collapses itself a few seconds after expansion, so toggle_favorite now re-runs the full expansion when the row is not reachable and the test acts without a settling sleep. |
| tests/ui/admin/test_admin_sites site detail tests | [DONE] | Group CRUD rebuilt and green 08/11/2026: group management lives in the Groups dropdown (Create New opens a modal with name input, camera search, and checkboxes; delete confirms in a customMuiModal whose Delete control needed modal-scoped matching; the old accordion is gone). Camera sorting keeps its honest skip: no sort control exists on the current detail page. |
| tests/ui/admin/test_admin_sites.py::test_search_inside_site | [REDO] | Still skips through the redesign guard on the current detail page; it automates the old camera-search layout. Rebuild against the current detail view (camera cards + per-camera panel), then retire _skip_if_redesigned_detail if nothing else uses it. |
| tests/ui/admin/test_admin_rules wizard tests | [DONE] | All 6 types create rules end to end, green 08/12/2026 (up from zero since the redesign). The full-view types (Heat Map, Loitering, Occupancy) closed last: their Set Rule modal shows BOTH the region prompt and the 'Use full view' switch, so the walker kept taking the region branch that never arms the step - the branch now keys on the rule type, switches full view on, waits for Done to arm (it enables only after the snapshot loads), and clicks it through JS because the modal backdrop eats pointer clicks; Next clicks fall back to JS the same way (safe: a disabled Next ignores them). Rebuilt 08/11/2026; the canvas types (Entry-Exit, Intrusion Detection, Line Crossing) came green first. The walker: card picker modal, config camera on Select Devices, region drawn on the fabric upper-canvas ONLY (a bare header canvas also exists and clicking relative to it exits the wizard), Done button, steps to Notification, Save, then the 'Name the Rule' dialog - the name lives there, which is what rejected the old flow. Remaining: Heat Map / Loitering / Occupancy use a 'Use full view' Set Rule variant that stays gated after both label and JS-input clicks; needs a live look at that step. Rule cleanup now exists (created rules delete themselves by name at teardown) and the create test asserts the rule exists after the wizard closes - by searching the full unique name and matching the row on a prefix, because the list truncates the Name cell in the DOM ('Entry-Exit_Auto_202608...'), so a full-name text match can never succeed. RESOLVED 08/12/2026, the 08/11-evening 'device tree never renders' observation: the tree was rendering fine but showed one camera, because the wizard hides cameras that are at rule capacity, and the leaked pre-teardown Auto rules (3 on the config camera alone) had capped them. Deleting the leaked rules restored the device list from 1 camera to 4 in the same session, and Entry-Exit went green again on the config camera. Not load, not a redesign, not a rename - self-inflicted, and the teardown now prevents recurrence. |
| tests/ui/views/test_views_subtabs.py insights add-to-tile | [DONE] | Green 08/12/2026. The affordance is drag-to-tile: widget cards are draggable, and the drop lands as a forced drag with the tile pre-scrolled into view (the unforced drag completes without adding anything - measured on both the old test and the probe). The consumed empty tile is the ONLY oracle (sidebar previews match any content selector page-wide, so content-count checks can pass on a misdrop). The checkbox variant keeps an honest skip (insight widgets expose no hover checkbox, measured 08/07 and 08/12) and now fails loud instead of skipping if a checkbox ever appears and the add still does nothing. |
| tests/ui/admin/test_lpr_playback.py (12 tests) | [DONE] | Rebuilt and green 08/12/2026. The whole file asserted nothing: play failures, popup failures, and navigation failures all drowned in info prints while the suite stayed green (the baseline run passed 12/12 with both play tests broken underneath). All 12 tests now fail loud. The play flow matches the current page: the Locations & Cameras panel starts closed and open means a site row is visible (the old accordion-src check never matched, so a second open call closed the panel, and the sub-heading fallback confirmed panels that were shut; the header click now self-heals once because it is a toggle); the tree walks site > group > camera, all draggable rows; the camera drops on the LAST empty tile - the panel floats over the left tiles, so a drop on the first tile lands on the panel and does nothing (this cost three diagnosis rounds: unforced first-tile drags hung on actionability, forced ones dispatched into the panel); a new video past the baseline count is the played signal, with no loader wait (empty tiles keep placeholder spinners alive forever - the in-camera search trap again). The play-all oracle stays at one new stream by design: the shared tenant keeps offline cameras in the group. The timeout popup title is 'Playback Auto-Timeout' now, Views is detected by its subtab bar because the app renders Views at the root URL, and tile activation waits for the player's live icon - the one element that shows only after the tile click (clicking the last video; a video-canvas union resolves .last to a hidden canvas). Dropped streams are session-scoped (verified: a fresh login shows all tiles empty), so runs leave no layout behind. |

## B. Skipping today - investigate whether the feature moved or died

| Test | Status | Detail |
|------|--------|--------|
| tests/ui/licenses/test_license_assignment.py TestLicenseAssignModal (4 tests) | [DONE] | Rebuilt, green and stable 08/09/2026. The button is 'Assign New', only on the Assigned Licenses tab (the old bare :has-text('Assign') clause clicked the tab itself). It opens a customMuiModal overlay; no Cancel control, Escape dismisses. A present-but-unresponsive button fails loud instead of skipping, and the Site assertion is scoped to the option list (the tab's table underneath also renders site names). |
| tests/ui/search/test_search_categories.py vehicle tests | [DONE] | Un-skipped and green 08/09/2026 - the 'no vehicle detections' premise was false. The SearchPage filter helpers went dead with the 2026-08 sidebar (the old code clicked the label, not the value control, and its JS fallbacks returned without error), so no filters applied and searches never dispatched. Rebuilt: _open_section clicks the value control with substring matching (labels carry zero-width spaces, so exact text never matches), site row + All Cameras via the scrollBarCustom panel, durations via .dropdownItem, and the section value leaving 'Select' as the applied signal. Categories 7/7 green. |

## C. Not run since the page-object conversion - verify before trusting

| Suite | Status | Detail |
|------|--------|--------|
| tests/ui/views/test_views_bookmarks.py | [VERIFY] | Exercises the converted add_bookmark_on_tile (fullscreen + timeline hover chain). |
| tests/ui/views/test_views_share.py | [VERIFY] | Exercises the converted share_live_view_on_tile hover chains and copy flow. |
| tests/ui/views/test_views_fullscreen.py | [VERIFY] | Exercises the converted enter_fullscreen_on_tile zoom-control wait. |
| tests/ui/views/test_views_playback.py | [VERIFY] | Player controls on tiles; page-object hover paths changed. |
| tests/ui/insights/test_insights_widgets.py | [VERIFY] | The heavily converted create_widget flow (accordion survivors, dropdownItem-hidden signals) ran 0 times since conversion. Run at least the Line_Person parametrization end to end. |
| tests/ui/admin/test_lpr_camera_selection.py | [VERIFY] | Uses the config camera name against the rebuilt lpr_page; run it (test_lpr_playback is done, see B2). |
| Headed parity spot-check | [VERIFY] | All verify runs this tranche were headless. Tests must behave identically headed: the viewport is pinned to 1280x720 in both modes (no override in conftest), but the QA team runs headed with --slowmo 300 --verify-mode, and the rebuilt step overlay now injects on every mark() in headed mode. Run test_views_basic headed, and one test headed with --verify-mode, to prove the overlay changes nothing. |

Verified green 08/08-08/09: events (28/28 over three files), licenses
(31 passed, designed skips restored), media deeper (14/14), camera
sequences (7/7), insights navigation + dashboard (18 passed, 4 skips),
LPR navigation (10 passed), views basic/subtabs/drag_drop, admin
users/rules/sites (with honest redesign skips), 4-worker xdist run
(42/42).

## D. Stale tenant data still hardcoded

| Test | Status | Detail |
|------|--------|--------|
| tests/ui/admin/test_admin_rules.py:16 SITE_NAME = "Driver Site" | [DATA] | Fixed 08/09/2026: now config.get("test_site_name"). The only consumer is the wizard path, which skips on the redesigned wizard, so the fix takes effect at rebuild time. |
| tests/ui/admin/test_admin_sites.py "Hanwha" search term | [DATA] | Fixed 08/09/2026: create_camera_group search term now comes from config test_camera_name. Path currently skips on the redesigned detail page, so the fix takes effect at rebuild time. |
| tests/ui/admin/test_admin_sites.py test_search_site "Driver" | [DATA] | Fixed 08/09/2026: was typing the old site name and only asserting the input echoed it (vacuous). Now searches the configured site's first word. |
| tests/ui/search/test_search_categories.py step text 'Driver Site' | [DATA] | Fixed 08/09/2026: mark text and the limitation note no longer name the old site. The vehicle-detection premise stays open in section B. |
| tests/steps/manual/maps/maps.json and test_insights_navigation.json | [ARTIFACT] | Sidecar actions say "Driver Site"; update alongside the next sidecar sync. |

## B2. Search suites - revalidated with the rebuilt filter helpers

Every Global Search suite ran with silently dead filter helpers until
08/09/2026 (see the vehicle row above). Revalidation results:

- test_search_categories: 7/7 green, both vehicle tests un-skipped.
- test_search_filters: 6/6 green.
- test_search_deeper: reworked 08/09/2026 after an unstable rerun. The
  contexts are function-scoped (fresh page per test), so the earlier
  fixture-reload "fix" was a coincidence and is removed. The real
  mechanism: searches run as async server jobs whose latency grows
  when runs hammer the tenant, so the heavy tests (Event over 30 days,
  re-searches) blow a 60s budget late in long chains - those four
  tests now carry a 120s budget. The two re-search tests are also
  dispatch-verified (execute_search_dispatched): stale results from
  the first search satisfy a visibility wait, so only the outgoing
  request proves the second search ran.
- test_incamera_search: 2/2 green after bounding the loader wait (the
  page keeps tile-placeholder spinners alive forever, so waiting for
  CircularProgress hidden can never finish; results are the signal).
- test_search_drawing: 6/6 green (row below).

| Test | Status | Detail |
|------|--------|--------|
| tests/ui/search/test_search_drawing.py (6 tests) | [DONE] | Green 08/11/2026. The Create Zone / Create Line links never moved: they render inside each camera container on hover once a Zone or Line category is selected (an earlier probe used the wrong category). Fixes: panel opener, site + All Cameras expansion, config camera name (was 'Hanwha_6'), and the action link scoped to the hovered container - every container holds its own always-mounted copy, so a page-wide .first grabbed another container's hidden one. |
| tests/ui/admin/test_lpr_events.py | [REDO] | Ran 9/9 green 08/12/2026 and the green is vacuous: every test is find-the-control-else-print with an early return, and the file's only assert is inside `if visible_count > 0:` - a tautology. Same pattern test_lpr_playback had before its rebuild. The tests also target the LPR Lists page (navigate_to_lpr) while the live event feed renders on the LPR camera page, so they may be probing the wrong page entirely. Needs the playback treatment: probe the event feed, real oracles, loud failures. test_lpr_grid_and_timer is done: its three checks keyed to the dead 'Set Timeout Duration' title now use 'Playback Auto-Timeout' (the retitle had silently disarmed them, including the cancel test's only real assertion) and the file ran green 08/12/2026 (4 passed, 1 designed skip). |

## Tenant mop-up (manual pass for Justin)

The repair runs left test artifacts on the shared tenant before the
teardowns landed. Remaining manual pass:
- Site detail > Groups dropdown: delete anything named
  "AutoTest Group *", "Edited Group *", or the
  "20260507163515AutomationEdited *" / "20260707153125AutomationEdited *"
  pair visible in the Newtown Action Area group list.
- DONE 08/12/2026 - Admin > Rules: all 6 leaked "*_Auto_2026*" rules
  deleted (each row name-verified against the automation prefixes
  before deletion; zero rows match "Auto" now). Test teardown deletes
  new ones as they are created.

## Known app behavior (confirmed, not bugs)

- **The rule wizard hides cameras at rule capacity.** Measured
  08/12/2026: with 6 leftover automation rules on the site, Select
  Devices listed 1 of the site's 5 cameras; deleting the rules brought
  the list to 4 in the same session. A camera "missing from the device
  tree" means its rule slots are full (or it is otherwise ineligible),
  not that the tree failed to render. First check Admin > Rules for
  leftover *_Auto_* rules on that camera. The config note on
  test_camera_name records the same remedy.
- **Repeat search clicks need changed filters.** By design (confirmed
  by Justin, 08/09/2026): a user must change filters or settings
  before a search re-runs; clicking Search again on an unchanged (or
  partially re-set) view dispatches no request. Our dispatch probe
  measured that even a category change alone did not re-arm the click,
  which fits the design if the category switch resets the dependent
  filters. Tests therefore run each search on a fresh view with all
  filters re-applied (events channel test, search deeper re-search
  tests), and execute_search_dispatched exists to tell an armed click
  from a dead one when a test genuinely needs a warm re-search.

## E. Test-artifact defects

| Artifact | Status | Detail |
|------|--------|--------|
| tests/steps/ui/events/test_events_search.json | [ARTIFACT] | Fixed 08/09/2026: steps regenerated from the real test flows (the old ones were unrelated imported templates), case keys kept. Follow-up for Justin: push the corrected steps with `python tools/qatouch_step_api.py sync --cases 8V1vJn,0rzlE9,M73wak,gQxXwN,pDpmba,dypXRb,vanZlz,M73wxx,lR2lkQ,Drd9a9` when ready - it writes to live QA Touch, so it stays a manual step. |

## F. Watch items (bounded waits with unproven premises)

These do not fail tests; they print a warning and continue. Chase any
that appears in run output, because it means the wait premise is wrong
and the call is burning its full timeout. Swept all 08/08-08/09 run
outputs: zero occurrences, so every premise that ran held. Keep
sweeping future runs:

- `[MEDIA] Add to Vault clicked but the icon is still visible` /
  `no success panel appeared` (media_page vault + share signals)
- `[EVENTS] Review Pinned Clips clicked but the button is still visible`
  (method currently unused by tests)
- `[VIEWS] open saved view finished but the empty-tile count stayed`
  (fires legitimately when a saved view has the same tile count)
- `[SEQUENCE] Save/Update clicked but ... still visible`
- `[LICENSE] Feature row clicked but no breadcrumb appeared`
- `_appears`/`_appears_hidden` swallow PlaywrightError, so a strict-mode
  violation looks like a timeout; if a bounded wait misses persistently,
  check the selector for multi-match before blaming timing.

## Tooling

`tools/explore_app.py` is the probe harness that closed the assign and
favorites items: it opens the app logged in (cached state or fresh
login) with the repo's page objects importable, as a REPL or running a
probe script. Use it for the remaining section A rebuilds instead of
guessing selectors. Its docstring carries the paid-for lessons
(fixed-position modals dodge offsetParent checks; probed state decays;
close what you open).

On Playwright's official test agents (planner/generator/healer,
playwright.dev/docs/test-agents, checked 08/09/2026): they require the
Node.js Playwright Test runner (init-agents, seed tests,
playwright.config.ts, VS Code 1.105+) and offer no Python support, so
they do not plug into this pytest framework. The roles they automate
are covered here by trace-first triage, this register, the convention
checker, and the probe harness.

## G. Conversion debt (not broken, still on old sleeps)

Test FILES still carry ~380 uncommented sleeps (page objects are done):
views drag_drop/playback/bookmarks, chats, search suites, LPR test
files, notifications, c2c, insights dashboard/widgets test bodies,
license test bodies, sequences test body. Converted file by file with
its own verify run, same measure-convert-verify discipline. The
convention checker blocks NEW sleeps; this table is the old ones.
