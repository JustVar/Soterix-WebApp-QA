# Test repair register

Tests that need reinvestigation, repair, or a verification run before we
write any new tests. Work this list top to bottom; do not add new test
files while an item here is open. Sourced from the 08/08/2026 conversion
tranche, its two-agent adversarial audit, and the live verify runs.

Status tokens: [REDO] rebuild against the current app, [INVESTIGATE]
find out whether the feature moved or died, [VERIFY] suite not run since
the page-object conversion, [DATA] stale tenant data in the test,
[ARTIFACT] test support files wrong, [WATCH] warning print to chase.

## A. Broken or never-worked - needs a rebuild

| Test | Status | Detail |
|------|--------|--------|
| tests/ui/views/test_views_favorites.py::test_add_remove_favorites | [DONE] | Green 08/09/2026 - first time since the test was written (locator was XPath-in-CSS and never parsed since 03/2026). Full repair: parseable row-scoped locator, config camera name, clean-start toggle, and the real blocker: the camera tree collapses itself a few seconds after expansion, so toggle_favorite now re-runs the full expansion when the row is not reachable and the test acts without a settling sleep. |
| tests/ui/admin/test_admin_sites site detail tests | [REDO] | Skip with drift message since 08/07/2026: detail page redesigned (breadcrumb, Groups, Add Devices layout). |
| tests/ui/admin/test_admin_rules wizard tests | [REDO] | complete_rule_wizard returns False on the redesigned Select Devices step tabs; tests skip. Need the new step flow and where the rule name lives. |
| tests/ui/views/test_views_subtabs.py insights add-to-tile | [REDO] | Skips honestly: insights widgets expose no hover checkbox and direct click adds nothing. Find the real affordance. |

## B. Skipping today - investigate whether the feature moved or died

| Test | Status | Detail |
|------|--------|--------|
| tests/ui/licenses/test_license_assignment.py TestLicenseAssignModal (4 tests) | [DONE] | Rebuilt and green 08/09/2026 (4/4). Probes found: the button is labeled 'Assign New' and exists only on the Assigned Licenses tab (the old bare :has-text('Assign') clause clicked the tab itself); it opens a customMuiModal overlay whose position:fixed root made offsetParent-based visibility probes miss it; the modal has no Cancel and dismisses on Escape; its backdrop blocks the whole page, so tests must close it before ending (session-scoped page). Site select verified listing all five real sites. |
| tests/ui/search/test_search_categories.py vehicle tests | [DONE] | Un-skipped and GREEN 08/09/2026 - the 'no vehicle detections' premise was false all along. Justin's correction exposed it: the SearchPage filter helpers were silently dead against the 2026-08 sidebar (label + value-control pairs; the old code clicked the label and its JS fallbacks returned without error), so NO search test was applying Locations or Duration filters and searches never dispatched - my own first probe measured a search that never ran and misread it as missing data. Rebuilt: _open_section clicks the value control (substring match - the app salts labels with zero-width spaces, so :text-is never matches), site row + All Cameras via the scrollBarCustom panel, durations via .dropdownItem with the current option order documented, and the section value leaving 'Select' as the applied signal. Categories suite 7/7 green including both vehicle tests. |

## C. Not run since the page-object conversion - verify before trusting

| Suite | Status | Detail |
|------|--------|--------|
| tests/ui/views/test_views_bookmarks.py | [VERIFY] | Exercises the converted add_bookmark_on_tile (fullscreen + timeline hover chain). |
| tests/ui/views/test_views_share.py | [VERIFY] | Exercises the converted share_live_view_on_tile hover chains and copy flow. |
| tests/ui/views/test_views_fullscreen.py | [VERIFY] | Exercises the converted enter_fullscreen_on_tile zoom-control wait. |
| tests/ui/views/test_views_playback.py | [VERIFY] | Player controls on tiles; page-object hover paths changed. |
| tests/ui/insights/test_insights_widgets.py | [VERIFY] | The heavily converted create_widget flow (accordion survivors, dropdownItem-hidden signals) ran 0 times since conversion. Run at least the Line_Person parametrization end to end. |
| tests/ui/admin/test_lpr_camera_selection.py and test_lpr_playback.py | [VERIFY] | lpr_page play_camera gained the site-click retry; only test_lpr_navigation ran. |
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
- test_search_deeper: 14/14 green after a fresh-view fixture fix - a
  search view that already ran a search does not dispatch the next one
  (SPA nav clicks are no-ops on the same route), proven by the failing
  tests passing in isolation. The fixture reloads before each test.
- test_incamera_search: 2/2 green after bounding the loader wait (the
  page keeps tile-placeholder spinners alive forever, so waiting for
  CircularProgress hidden can never finish; results are the signal).
- test_search_drawing: 8 tests SKIPPED with a precise reason (below).

| Test | Status | Detail |
|------|--------|--------|
| tests/ui/search/test_search_drawing.py (8 tests) | [REDO] | Mechanics repaired 08/09/2026 (panel opener, site + All Cameras expansion to render camera containers, config camera name replacing hardcoded 'Hanwha_6'), but the hover-revealed Create Zone / Create Line links no longer appear on camera containers: the drawing entry point moved in the 2026-08 redesign. Explore its new home with tools/explore_app.py, rebuild open_zone_drawing / open_line_drawing, then remove the module skip. |

## E. Test-artifact defects

| Artifact | Status | Detail |
|------|--------|--------|
| tests/steps/ui/events/test_events_search.json | [ARTIFACT] | Fixed 08/09/2026: steps regenerated from the real test flows (the old ones were unrelated imported templates), case keys kept. Follow-up for Justin: push the corrected steps with `python tools/qatouch_step_api.py sync --cases 8V1vJn,0rzlE9,M73wak,gQxXwN,pDpmba,dypXRb,vanZlz,M73wxx,lR2lkQ,Drd9a9` when ready - it writes to live QA Touch, so it stays a manual step. |

## F. Watch items from the audit (bounded waits with unproven premises)

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
