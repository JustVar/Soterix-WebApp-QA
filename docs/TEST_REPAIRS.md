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
| tests/ui/views/test_views_favorites.py::test_add_remove_favorites | [REDO] | Narrowed 08/09/2026 by DOM probe. Fixed already: locator (was XPath-in-CSS, never parsed since 03/2026), row scoping (span[title] grandparent, button:has(img[alt='favorite'])), config camera name, clean-start toggle. Remaining: the sidebar tree rows that hold the star stay mounted but HIDDEN after expand_site_and_show_cameras closes the panel, so the star is never visible when the test acts. Rebuild = find the panel state that shows the tree rows, then remove the skip. Beware: 'main gate' may be left favorited by earlier iterations. |
| tests/ui/admin/test_admin_sites site detail tests | [REDO] | Skip with drift message since 08/07/2026: detail page redesigned (breadcrumb, Groups, Add Devices layout). |
| tests/ui/admin/test_admin_rules wizard tests | [REDO] | complete_rule_wizard returns False on the redesigned Select Devices step tabs; tests skip. Need the new step flow and where the rule name lives. |
| tests/ui/views/test_views_subtabs.py insights add-to-tile | [REDO] | Skips honestly: insights widgets expose no hover checkbox and direct click adds nothing. Find the real affordance. |

## B. Skipping today - investigate whether the feature moved or died

| Test | Status | Detail |
|------|--------|--------|
| tests/ui/licenses/test_license_assignment.py TestLicenseAssignModal (3 tests) | [REDO] | Resolved to a rebuild 08/09/2026. DOM probe found the old locator's bare :has-text('Assign') clause was clicking the 'Assigned Licenses' TAB (fixed: clause removed, open_assign_modal no longer raises). With the correct button found and clicked, still no dialog appears: the assign flow no longer opens a modal. Explore what it opens now (full page or drawer) and rebuild the three modal tests against it. |
| tests/ui/search/test_search_categories.py vehicle tests (2 skips) | [INVESTIGATE] | Skip reason says the old site has no vehicle detections. Premise predates the tenant rename; recheck against the current tenant before trusting the skips. |

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

## G. Conversion debt (not broken, still on old sleeps)

Test FILES still carry ~380 uncommented sleeps (page objects are done):
views drag_drop/playback/bookmarks, chats, search suites, LPR test
files, notifications, c2c, insights dashboard/widgets test bodies,
license test bodies, sequences test body. Converted file by file with
its own verify run, same measure-convert-verify discipline. The
convention checker blocks NEW sleeps; this table is the old ones.
