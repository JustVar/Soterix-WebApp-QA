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
| tests/ui/admin/test_lpr_widgets.py (3 tests) | [DONE] | Rebuilt and green 08/13/2026 (3/3, drop test stable across 3 runs). The old file was dead code: the whole creation flow sat inside an except branch AFTER its return, so the test clicked Insights and passed vacuously, no widget ever existed, and the two dependent tests skipped forever. Rebuilt on the shared InsightsPage.create_widget with a new description_name parameter (Event descriptions are labeled checkboxes carrying the label in their name attribute; 'License Plate Recognition' makes the widget an LPR one). The LPR camera page lists LPR widgets in its Widgets panel (search_select_box_container, cards behind skeletons - the visible card is the open marker, fill() filters fine here unlike the chat search). There is NO checkbox on the panel - placing a widget is drag-to-tile like cameras: drop on the LAST empty tile, tile-count baseline plus div.box[aria-label=name] as the landed oracle (zero-data widgets render an EMPTY highcharts title, so the name-in-title check false-fails; the aria-label box renders for both, shortly after the tile is consumed, so the wait retries). An unforced drag can complete without landing anything (same flake the insights add-to-tile fix measured) - one forced retry self-heals. Placement is session-scoped (reload clears it, measured). Each test creates its own widget and deletes it in teardown; delete_widget verified working. Probe snaps: reports/probe_shots/lprw*_*.png. |
| tests/ui/admin/test_lpr_playback.py (12 tests) | [DONE] | Rebuilt and green 08/12/2026. The whole file asserted nothing: play failures, popup failures, and navigation failures all drowned in info prints while the suite stayed green (the baseline run passed 12/12 with both play tests broken underneath). All 12 tests now fail loud. The play flow matches the current page: the Locations & Cameras panel starts closed and open means a site row is visible (the old accordion-src check never matched, so a second open call closed the panel, and the sub-heading fallback confirmed panels that were shut; the header click now self-heals once because it is a toggle); the tree walks site > group > camera, all draggable rows; the camera drops on the LAST empty tile - the panel floats over the left tiles, so a drop on the first tile lands on the panel and does nothing (this cost three diagnosis rounds: unforced first-tile drags hung on actionability, forced ones dispatched into the panel); a new video past the baseline count is the played signal, with no loader wait (empty tiles keep placeholder spinners alive forever - the in-camera search trap again). The play-all oracle stays at one new stream by design: the shared tenant keeps offline cameras in the group. The timeout popup ('Set Timeout Duration') opens only over a playing stream - its icon tooltip 'Playback Auto-Timeout' shows on any click and satisfied text waits vacuously until 08/12 - Views is detected by its subtab bar because the app renders Views at the root URL, and tile activation waits for the player's live icon - the one element that shows only after the tile click (clicking the last video; a video-canvas union resolves .last to a hidden canvas). Dropped streams are session-scoped (verified: a fresh login shows all tiles empty), so runs leave no layout behind. |

## B. Skipping today - investigate whether the feature moved or died

| Test | Status | Detail |
|------|--------|--------|
| tests/ui/chats/test_chats.py (6) + test_chats_deeper.py (11) | [DONE] | Rebuilt and green 08/13/2026: 12 passed, 5 designed skips, zero sleeps left in either file. The panel is a search-first overlay; the open marker is the visible panel search (its 'Search1' twin is the mounted member-search view), the header icon is a toggle so the opener clicks only when the marker is absent, close is the popup-head X (the in-input search icon shares the same iconSmallCross alt - scope to popup-head). The search responds to real keystrokes ONLY: a lone programmatic fill after open is dropped every time (measured across four probes - fill produced zero results, key-by-key typing always landed by the second pass), so search_chat types with press_sequentially and retypes once; clears use real keys for the same reason. A result click behaves two ways, both measured: a first-ever contact lands a conversation row in the recent-chats list, an existing conversation opens its thread directly - start_conversation accepts either marker. Sent text renders as span.sentMsg in the thread, the panel-scoped delivered oracle (tests send run-unique text). Group creation has NO entry point in the redesigned panel (probed fresh, search, result-click, thread, and hover states; the mounted 'Add Members'/Update view serves group conversations this account cannot create), so the 4 group CRUD tests plus create_group_button_present skip honestly and fail loud via group_creation_affordance() the day a creation control returns. Chat partner moved to config (test_chat_user_search/test_chat_user_name). Probe snaps: reports/probe_shots/chat_probe*.png. |
| tests/ui/media/test_media_operations.py destructive set (clip delete, folder delete, grouping, move to folder) | [INVESTIGATE] | Held as skips 08/12/2026: these operated on the team's clips (the old delete removed the first list item; grouping relocates team clips into a folder). Before activating, measure whether deleting a folder deletes the clips grouped into it and whether ungrouping exists - if folder delete only ungroups, the whole chain becomes safe own-data (group two clips, operate on the folder, delete it). Needs Justin's answer or a disposable measurement. The rest of the file is rebuilt on measured mechanisms: names are inline inputs (text engines cannot see them - the old rename typed into the SEARCH box because its locator matched that first), the rename success toast is the server ack (an optimistic rename can show in the DOM and never commit - measured), and vaulting MOVES the row between the list and the Vault tab. |
| tests/ui/licenses/test_license_assignment.py TestLicenseAssignModal (4 tests) | [DONE] | Rebuilt, green and stable 08/09/2026. The button is 'Assign New', only on the Assigned Licenses tab (the old bare :has-text('Assign') clause clicked the tab itself). It opens a customMuiModal overlay; no Cancel control, Escape dismisses. A present-but-unresponsive button fails loud instead of skipping, and the Site assertion is scoped to the option list (the tab's table underneath also renders site names). |
| tests/ui/search/test_search_categories.py vehicle tests | [DONE] | Un-skipped and green 08/09/2026 - the 'no vehicle detections' premise was false. The SearchPage filter helpers went dead with the 2026-08 sidebar (the old code clicked the label, not the value control, and its JS fallbacks returned without error), so no filters applied and searches never dispatched. Rebuilt: _open_section clicks the value control with substring matching (labels carry zero-width spaces, so exact text never matches), site row + All Cameras via the scrollBarCustom panel, durations via .dropdownItem, and the section value leaving 'Select' as the applied signal. Categories 7/7 green. |

## C. Not run since the page-object conversion - verify before trusting

| Suite | Status | Detail |
|------|--------|--------|
| tests/ui/views/test_views_bookmarks.py | [DONE] | Verified 08/13/2026: 9/9 green first run, export and share flows included. |
| tests/ui/views/test_views_share.py | [DONE] | Verified 08/13/2026: 1/1 green first run. |
| tests/ui/views/test_views_fullscreen.py | [DONE] | Verified 08/13/2026: 5/5 green first run. |
| tests/ui/views/test_views_playback.py | [DONE] | Verified 08/13/2026: 10/10 green after one real fix - the second-tile fullscreen test failed three straight runs because the live player intermittently shows 'The camera failed to load. Please try again.' OVER a rendering live frame (trace-confirmed on Street#36). recover_stream_if_failed clicks the overlay's refresh link once (loose case-insensitive match - the link label reads 'Rafresh' on the current build), the user-path recovery, and is_streaming now checks the overlay's visibility instead of its count so a recovered-but-mounted overlay cannot false-fail it. |
| tests/ui/insights/test_insights_widgets.py | [DONE] | Verified 08/13/2026: Line_Person create ran green end to end (112s), and the rebuilt lpr_widgets suite now exercises create_widget (Event + LPR description) and delete_widget on every run. The two no-oracle tests in the file (view/report) stay on the G2 worklist. |
| tests/ui/admin/test_lpr_camera_selection.py | [DONE] | REBUILT 08/13/2026 - the same-day '3/3 green first run' note was wrong: those passes were vacuous. The old file navigated to Admin > LPR (the Lists page), failed to find the Locations & Cameras panel there, printed INFO, and returned early before any assert - the static no-oracle checker cannot see unreachable asserts. Rebuilt on the camera page's measured mechanics: group and camera rows show a hover checkbox (sidebar-custom-checkbox) that adds them to the grid - the group checkbox took the page from 0 to 4 streams, Reset View back to 0; a new video element past the baseline is the started signal. Camera rows re-render continuously (their snapshot refreshes), so their checkbox needs an input-targeted JS click - a pointer click never passes the stability check. The panel has no camera search box (the page's only Search belongs to the Widgets panel), so the old search step is gone. 3/3 green on the real flows. |
| Headed parity spot-check | [DONE] | Verified 08/13/2026: test_views_basic headed 6/6 green, and two tests headed with --slowmo 300 --verify-mode both green - one WITH step marks (lpr_playback navigation) so the injected overlay path itself ran and changed nothing. Evidence files landed in verification_output/. |

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
| tests/steps/ui/chats/test_chats.json + test_chats_deeper.json | [ARTIFACT] | Sidecar steps describe the pre-redesign panel (Create Group button, group CRUD, TAB-typing); regenerate from the rebuilt tests at the next sidecar sync, case keys kept. |

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

- **Event Wall is its own feature with two surfaces - never mix
  them, or with regular Views/Events.** Confirmed by Justin
  08/13/2026: the regular app keeps its normal Views and Events
  pages; the Event Wall is a separate item. Its CONFIGURATION is
  done by a regular login (Admin > General > Event Wall card >
  View: a configuration table plus the Add Configuration modal).
  Its DISPLAY is a separate UI experience behind a special user
  with local access enabled - that user logs in, selects a site,
  and the wall appears. Test structure mirrors this: the feature
  owns tests/ui/event_wall/ (test_event_wall_config.py runs today
  on the regular login; test_event_wall_display.py holds as
  explicit skips until the special account is provisioned for
  automation, with its own event_wall_display mark). The old
  admin_event_wall mark is a legacy alias; event_wall is the
  feature mark. QA Touch mapping keys re-pointed (13 config + 1
  display).
- **Admin > General is a card page; card titles are no-ops.** Each
  card (Deployment, Audit Trail, System Logs, Multi-Factor
  Authentication, Event Wall) navigates via its View link only, the
  breadcrumb ('General > X', one clickable p) navigates back, and
  the General section tab is a no-op while already inside the
  section (all measured 08/13/2026). A View click right after the
  cards page re-renders can be silently dropped - same hydration
  behavior the sites rebuild measured; retry once. Match the View
  label with exact=True: get_by_text's default substring matching
  clicked the Audit card's BLURB ('Monitor and re-VIEW-all
  activities...') instead of the button, which looked like
  View-does-not-navigate for two runs; the Event Wall card only
  worked because its blurb happens to contain no 'view'. With the
  exact match, Audit's View navigates in-page to 'General > Audit
  Trail'.

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
  see section B). **CLEARED to zero repo-wide 08/13/2026.**
  lpr_grid_and_timer (3) with the 08/13 rebuild, chats (2) with the
  panel rebuild, admin_general (3) same day (one checker false
  positive - expect.soft IS an oracle, pytest-playwright raises
  collected soft failures at test end, ORACLE_RE now knows; two were
  delegation to _open_general's expect, commented; 11/11 green),
  lpr_widgets (2) with the file rebuild (section A row), and the
  final 10 (insights view/report + 8 singles) on 08/13, all verified
  green except the two comment-only delegations (incamera play,
  bookmarks export - real raising waits already inside). Notables
  from the final batch: insights report now waits on the BROWSER
  DOWNLOAD event (the old toast wait swallowed its timeout, so a
  failed download passed silently; the download fires - measured);
  lpr_views close-all rebuilt on the real tab mechanics
  (div.tabInner[title] + closeTabIcon; closing the LAST view fires a
  native alert 'Action not permitted' and the view survives - the
  old code looked for nonexistent Close buttons and registered its
  dialog handler after the click); license dedup keys on WHOLE rows
  (feature names repeat by design); and the new post-delete oracle
  on test_delete_user caught a live footgun - the Users search
  filter is server-side and the pre-filter rows stay visible while
  it runs, so the instant row check handed delete_user the tenant's
  FIRST UNFILTERED user (the server refused, no harm done).
  delete_user now scopes to the .MuiPaper-root card matching the
  searched text and the test waits for the count to leave the
  unfiltered baseline before touching anything. The run also
  consumed one of the two leaked 'AutoTest Playwright' users from
  08/07; the next run consumes the other.
- **110 except blocks that only print** - triage alongside each
  file's rebuild; cleanup paths may keep them with a why-comment.
- **4 .first/.last picks on union selectors**, the hidden-copy trap.

## G. Conversion debt (not broken, still on old sleeps)

Test-file sleep debt CLEARED 08/14/2026 except two holds: the c2c
files (3 sleeps; converting them unverified would break the
measure-convert-verify discipline - they need a hardware session)
and a handful of comment-sanctioned settles for signal-less
premises (absence checks, no-op comparisons, rejected-login pacing,
post-URL-miss beats). The tail tranche: insights_dashboard (10),
media_deeper (6), lpr_views' old tests (4), events_filters (3),
incamera_search (3), search_deeper (3, two now sanctioned),
favorites (2), lpr_navigation (2), logout (2, one sanctioned),
insights_widgets (3), license_assignment leftovers (2), maps_deeper
(1), login_security (1, sanctioned).

CORRECTION to the old 'page objects are done' claim: the 08/14
sweep shows PAGE OBJECTS still carry ~53 uncommented sleeps
(search_page 15, incamera_search_page 10, camera_hardware_page 9,
fullscreen_page 8, maps_page 8, login_page 3). They are the
remaining conversion debt alongside the c2c hold.

lpr_operations (was 11) and the license family (navigation 5,
search 9, assignment 9, permissions 4) converted 08/14/2026 -
lpr_operations 10/10 green, licenses 34 green + 8 designed skips.
Two sanctioned commented settles remain in license_search (the
clear-restore and no-op-search premises have no completion signal).
The lpr_operations conversion exposed a render race its settles
had absorbed: an instant row read right after navigation sees the
table pre-render and mis-skips on 'no lists'; row reads now go
through a bounded render wait. The license drill-down and suspend
flows gained real arrival signals (breadcrumb, dialog) where they
had trailing sleeps.

sequences (was 20) converted 08/13/2026 by delegating the test
bodies to the already-signal-based SequencePage (7/7 green twice);
lpr_camera_selection (was 13) rebuilt the same day (see section C
row - its sleeps died with the vacuous early-exit flow);
admin_event_wall (was 12) REBUILT 08/13/2026 - the old suite
clicked the Event Wall card TITLE (a no-op, see Known app
behavior) and probed page-level dropdowns/images/grids that only
ever matched the General page around it. Now 13 green + 1 designed
skip on the measured config page: breadcrumb + Add Configuration
arrival, table headers, empty state, and the Add modal (name
input, site accordion expanding to camera groups then cameras,
Select Rule combobox, camera checkbox toggle, Save/Cancel).

New checker rule early-exit-pass (08/13/2026): a bare return in a
test body passes with everything after it unreachable - the class
static oracle checks cannot see. A why-comment on the return
excuses deliberate ones; returns inside functions NESTED in a test
body (response listeners, local helpers) are excluded as those
functions' own control flow (refined 08/14/2026 - events_search's
two were exactly that). Standing count: ZERO after the audit trail
rebuild.

notifications + notifications_deeper (were 10 + 11 sleeps)
converted 08/14/2026, 12/12 green. The bell is a toggle like the
chat icon, so the openers are toggle-safe on the mute/unmute
marker. The muted state's icon src is 'UnMuteNotification' -
capital M, so a lowercase 'Unmute' guess never matches (CSS src*=
is case-sensitive), and since 'UnMuteNotification' CONTAINS
'MuteNotification', the single substring img[src*='MuteNotification']
matches both states. The mute toggle tests now use the src FLIP as
the state-changed oracle and restore the shared account's state by
toggling back; the mute state read as session-scoped in probing
(a fresh login showed unmuted after a prior mute).

admin_audit_trail (was 7 early-exits + 6 sleeps) REBUILT
08/14/2026: the old setup clicked the Audit card TITLE (no-op) and
every test probed the General cards page through over-broad
unions. The card's View button (exact=True - see Known app
behavior for the substring trap) opens a real table (Username |
Role Type | Date & Time | IP | Action) with live records; tests
now assert the measured headers, dd-mm-yyyy/hh:mm timestamps,
populated user and action cells, breadcrumb return, and a
next-page oracle keyed on the first row changing. The table
renders a 'No data available' placeholder row while the fetch is
in flight and an empty spacer row besides (both caught live) - the
first-record wait filters to rows with non-whitespace text that
are not the placeholder. 13 green + 1 designed skip (no pagination
control at current record counts).

views drag_drop (was the largest at 36) converted 08/13/2026, 6
passed + 1 designed skip. The conversion surfaced a structural
fact the sleeps had hidden: the add (+) tab is ALSO a
button.tabItem (untitled tabInner), so any tab-count logic that
counts tabItems is off by one - the old cleanup loop always met
the iconless + tab first and broke without closing anything, a
silent no-op since conversion day. View tabs are now selected via
button.tabItem:has(div.tabInner[title]) and the renamed tab via
.active; drops wait on a bounded tile-consumed signal
(_wait_tile_consumed) with each test's union oracle unchanged. Sleep-free as of 08/13/2026: LPR playback/events/
grid_and_timer/widgets, both chat files, and the views
fullscreen/share/playback/bookmarks files plus views/conftest (27
sleeps converted to signal waits in one tranche, all four suites
25/25 green after conversion - the recurring patterns were settles
whose real signal already followed on the next line, async
bookmark-row renders now on bounded first-row waits, and instant
counts after clicks now on retrying expects). Converted file by file with
its own verify run, same measure-convert-verify discipline. The
convention checker blocks NEW sleeps; this table is the old ones.
