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
| tests/ui/admin/test_admin_sites.py::test_search_inside_site | [DONE] | Rebuilt and green 08/12/2026 for the redesigned detail: cameras are name + IP rows and div.site-card is gone, so click_site's detail signal is now the Groups label with one retry (a click during list hydration is silently dropped - reproduced twice), and test_navigate_to_online_site's oracle moved off site-card too. The test searches the configured camera's full name and requires exactly one IP row, then clears and requires the full list back. _skip_if_redesigned_detail stays for camera sorting, but its 'Add Devices' marker no longer renders, so it never skips - the sorting test still exits honestly on its own sort-icon check. |
| tests/ui/admin/test_admin_rules wizard tests | [DONE] | All 6 types create rules end to end, green 08/12/2026 (up from zero since the redesign; canvas types came green 08/11). The walker: card picker modal, config camera on Select Devices, then per type - the canvas types (Entry-Exit, Intrusion Detection, Line Crossing) draw on the fabric upper-canvas ONLY (a bare header canvas also exists and clicking relative to it exits the wizard); the full-view types (Heat Map, Loitering, Occupancy) key on the rule type because their Set Rule modal shows BOTH the region prompt and the 'Use full view' switch, verify the switch actually turned on (Done arms on the snapshot load regardless, so an unverified toggle could walk through unconfigured), then JS-click the armed Done - the modal backdrop eats pointer clicks, and Next clicks fall back to JS the same way. Save then the 'Name the Rule' dialog (the name lives there - what rejected the old flow). A stalled walk raises; False only means the picker lacks the type. The create test searches the full unique name and requires exactly one matching row (the list truncates the Name cell in the DOM, so a full-name text match can never succeed), and created rules delete themselves by name at teardown. The 08/11-evening 'device tree never renders' observation is resolved: the wizard hides cameras at rule capacity and leaked pre-teardown Auto rules had capped them - see Known app behavior. |
| tests/ui/views/test_views_subtabs.py insights add-to-tile | [DONE] | Green 08/12/2026. The affordance is drag-to-tile: widget cards are draggable, and the drop lands as a forced drag with the tile pre-scrolled into view (the unforced drag completes without adding anything - measured on both the old test and the probe). The consumed empty tile is the ONLY oracle (sidebar previews match any content selector page-wide, so content-count checks can pass on a misdrop). The checkbox variant keeps an honest skip (insight widgets expose no hover checkbox, measured 08/07 and 08/12) and now fails loud instead of skipping if a checkbox ever appears and the add still does nothing. |
| tests/ui/admin/test_lpr_playback.py (12 tests) | [DONE] | Rebuilt and green 08/12/2026. The whole file asserted nothing: play failures, popup failures, and navigation failures all drowned in info prints while the suite stayed green (the baseline run passed 12/12 with both play tests broken underneath). All 12 tests now fail loud. The play flow matches the current page: the Locations & Cameras panel starts closed and open means a site row is visible (the old accordion-src check never matched, so a second open call closed the panel, and the sub-heading fallback confirmed panels that were shut; the header click now self-heals once because it is a toggle); the tree walks site > group > camera, all draggable rows; the camera drops on the LAST empty tile - the panel floats over the left tiles, so a drop on the first tile lands on the panel and does nothing (this cost three diagnosis rounds: unforced first-tile drags hung on actionability, forced ones dispatched into the panel); a new video past the baseline count is the played signal, with no loader wait (empty tiles keep placeholder spinners alive forever - the in-camera search trap again). The play-all oracle stays at one new stream by design: the shared tenant keeps offline cameras in the group. The timeout popup ('Set Timeout Duration') opens only over a playing stream - its icon tooltip 'Playback Auto-Timeout' shows on any click and satisfied text waits vacuously until 08/12 - Views is detected by its subtab bar because the app renders Views at the root URL, and tile activation waits for the player's live icon - the one element that shows only after the tile click (clicking the last video; a video-canvas union resolves .last to a hidden canvas). Dropped streams are session-scoped (verified: a fresh login shows all tiles empty), so runs leave no layout behind. |

## B. Skipping today - investigate whether the feature moved or died

| Test | Status | Detail |
|------|--------|--------|
| tests/ui/chats/test_chats.py (all 6) | [REDO] | Probed 08/13/2026: the chat panel is REDESIGNED into a search-first overlay - 'Chat' header, X close, one search bar, and an empty state ('Use the search bar to find and chat with the person you're looking for'). No Create Group button, no upfront group list, so every group CRUD flow automates controls that no longer exist, and open_chat_panel's open-marker (the dead Create Group locator) made its retry click toggle the panel SHUT every time - the reliable open marker now is input.chat-search-input. Group creation needs rediscovery (probe what affordances appear after searching a user). The two message tests gained a real oracle the same day (send_message waits for the sent text in the thread; tests send run-unique messages - the old fire-and-forget sends with static strings would have matched older runs' messages), unverified until the rebuild. Probe snaps: reports/probe_shots/chat_one_click_01.png. |
| tests/ui/media/test_media_operations.py destructive set (clip delete, folder delete, grouping, move to folder) | [INVESTIGATE] | Held as skips 08/12/2026: these operated on the team's clips (the old delete removed the first list item; grouping relocates team clips into a folder). Before activating, measure whether deleting a folder deletes the clips grouped into it and whether ungrouping exists - if folder delete only ungroups, the whole chain becomes safe own-data (group two clips, operate on the folder, delete it). Needs Justin's answer or a disposable measurement. The rest of the file is rebuilt on measured mechanisms: names are inline inputs (text engines cannot see them - the old rename typed into the SEARCH box because its locator matched that first), the rename success toast is the server ack (an optimistic rename can show in the DOM and never commit - measured), and vaulting MOVES the row between the list and the Vault tab. |
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
| tests/ui/admin/test_lpr_camera_selection.py | [VERIFY] | Uses the config camera name against the rebuilt lpr_page; run it (test_lpr_playback is done, see section A). |
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
| tests/ui/admin/test_admin_rules.py:16 SITE_NAME = "Driver Site" | [DATA] | Fixed 08/09/2026: now config.get("test_site_name"). In effect since 08/12/2026 - the rebuilt wizard path runs end to end and consumes it every run. |
| tests/ui/admin/test_admin_sites.py "Hanwha" search term | [DATA] | Fixed 08/09/2026: create_camera_group search term now comes from config test_camera_name. In effect since 08/11/2026 - the rebuilt group CRUD runs it every run. |
| tests/ui/admin/test_admin_sites.py test_search_site "Driver" | [DATA] | Fixed 08/09/2026: was typing the old site name and only asserting the input echoed it (vacuous). Now searches the configured site's first word. |
| tests/ui/search/test_search_categories.py step text 'Driver Site' | [DATA] | Fixed 08/09/2026: mark text and the limitation note no longer name the old site. The vehicle-detection premise stays open in section B. |
| tests/steps/manual/maps/maps.json and test_insights_navigation.json | [ARTIFACT] | Sidecar actions say "Driver Site"; update alongside the next sidecar sync. |
| tests/steps/ui/media/test_media_operations.json | [ARTIFACT] | Sidecar titles/steps describe the pre-rebuild flow (edit-form rename, hover icons); regenerate from the rebuilt tests at the next sidecar sync, case keys kept. |

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
| tests/ui/admin/test_lpr_events.py + test_lpr_grid_and_timer.py | [DONE] | Both rebuilt/verified green 08/12/2026. Events: eight of the nine tests keyed on a MuiPaper class that does not exist on the page (those runs took the empty-feed early return; the one assert in the file was tautological) and targeted the Lists page while the feed lives on the camera page. Rebuilt against the real feed - cards anchor on their timestamp line (no stable classes; plate texts end with a trailing space), a card click opens the inline clip player (video + position/duration strip), close verifies the video leaving, filter asserts Duration/Apply, details assert Share/Export/Create Link, fullscreen asserts document.fullscreenElement and exits via exitFullscreen (Escape does not release it headless), and the speed test skips with a measured reason but fails loud if a control appears. 8 passed + that skip. Grid and timer: rebuilt 08/13/2026 after a wrong turn - 'Set Timeout Duration' was never a dead title; it is the REAL popup title, and the popup opens only while a stream plays (the icon's tooltip reads 'Playback Auto-Timeout' and shows on any click, which made tooltip-text waits pass with the popup never opening - the morning retitle encoded exactly that trap). The timer tests now play the config camera first, assert the real popup, and the grid test drives the three layout buttons against visible tile counts (1/4/9) and the activeLayout class, restoring 2x2 - the layout the other LPR suites were measured on. |

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

- **The Media page serves stale state per page load.** Measured
  08/12/2026, two faces of one behavior: (1) only the FIRST rename
  in a page load commits - later ones are silently dropped, no
  toast, no error, no server change (retries at +0s through +180s
  all dropped; a hard reload re-arms the next rename); (2) the
  Vault tab's listing does not pick up items vaulted in the same
  page load - a fresh session or hard reload always shows them.
  Possibly an app defect worth reporting; until then, media tests
  hard-reload between mutations and before reading vault state.

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

- (retired 08/12/2026: the media vault and share warning prints are
  raises now - the media rebuild removed both watch items)
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
probe script. Use it for rebuilds instead of guessing selectors. Its
docstring carries the paid-for lessons (fixed-position modals dodge
offsetParent checks; probed state decays; close what you open), and
probe scripts now have `snap("label")` in scope - screenshots settle
layout questions (what covers what, where a panel floats) that DOM
dumps argue about; the first-tile-under-the-panel diagnosis cost three
rounds that one screenshot would have ended.

Discipline since 08/12/2026: the defect-class review runs on the
UNCOMMITTED diff before the first commit, and every class a review
finds becomes a convention_check rule so it cannot recur. Claims
about app mechanisms go in commit messages and this register only
when a probe measured them; anything extrapolated is written as
unmeasured. When a fix changes a shared fact (a title, a signal, a
helper's contract), the same batch greps every consumer of that fact
- the retitled popup silently disarming three checks in a sibling
file is the lesson.

On Playwright's official test agents (planner/generator/healer,
playwright.dev/docs/test-agents, checked 08/09/2026): they require the
Node.js Playwright Test runner (init-agents, seed tests,
playwright.config.ts, VS Code 1.105+) and offer no Python support, so
they do not plug into this pytest framework. The roles they automate
are covered here by trace-first triage, this register, the convention
checker, and the probe harness.

## G2. Oracle debt (08/12/2026 whole-repo sweep)

The new checker rules enumerate the standing versions of the classes
the recent repairs fixed (`python tools/convention_check.py --all`):

- **33 tests with no failure path** at sweep time (no assert/expect,
  no raising wait): test_media_operations.py carried 13 - fixed
  08/12/2026 (9 rebuilt with real oracles, 4 held as explicit skips,
  see section B). The rest spread over admin_general (3),
  lpr_grid_and_timer (3), chats (2), lpr_widgets (2),
  insights_widgets (2), and singles - re-run `--all` for the live
  count. These are the rebuild worklist, ordered with the section C
  verify rows - a test that cannot fail is not coverage.
- **110 except blocks that only print** - triage alongside each
  file's rebuild; cleanup paths may keep them with a why-comment.
- **4 .first/.last picks on union selectors**, the hidden-copy trap.

## G. Conversion debt (not broken, still on old sleeps)

Test FILES still carry ~380 uncommented sleeps (page objects are done):
views drag_drop/playback/bookmarks, chats, search suites, the LPR
test files not yet rebuilt (playback and events are sleep-free now),
notifications, c2c, insights dashboard/widgets test bodies,
license test bodies, sequences test body. Converted file by file with
its own verify run, same measure-convert-verify discipline. The
convention checker blocks NEW sleeps; this table is the old ones.
