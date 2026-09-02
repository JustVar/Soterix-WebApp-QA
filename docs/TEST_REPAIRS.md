# Test repair register

What is broken, what needs fixing, what was done. Work top to bottom;
do not add new test files while an item is open. Rows stay short: a
row that needs a long note means a real lesson was found - it goes to
docs/FAILURE_TRIAGE.md (mechanisms and traps), docs/CONVENTIONS.md
(house rules), a page-object docstring, or a convention_check rule,
with a pointer here.

Status: [REDO] rebuild, [INVESTIGATE] feature moved or died?,
[VERIFY] not run since conversion, [DATA] stale tenant data,
[ARTIFACT] support files wrong, [BLOCKED] waiting outside the repo,
[DONE] repaired and verified green, [APP QUESTION] behaviour the app team
must answer, [SECURITY QUESTION] same, raised with the security owner.

## Open items (opened 08/14/2026, kept current)

| # | Item | Status | Needs |
|---|------|--------|-------|
| 1 | Event Wall display suite (tests/ui/event_wall/test_event_wall_display.py) | [BLOCKED] | Local-access wall user (Justin creating). Then: its own env vars in config/env, probe login + site-select, build the wall's markers. |
| 2 | Media destructive set (clip/folder delete, grouping, move) | [INVESTIGATE] | Answer: does deleting a folder delete the clips grouped into it? Or a disposable measurement. |
| 3 | Page-object sleeps | mostly [DONE] | Converted 08/14: search_page, incamera_search_page, fullscreen_page, maps_page, login_page (53 -> 11 commented pacing/poll settles, counted 08/25). Verified: maps 5/5, fullscreen 5/5, bookmarks 8/9 (setup flake), playback 9/10; search consumers verified NEUTRAL by A/B against HEAD (6 vs 7 fails on the same suite in the same window - the search endpoint was 400 again, see defects). camera_hardware_page (11) joins the c2c hold. 08/25 tranche: admin_page 11 -> 4, views_page 8 -> 3, insights_page 7 -> 2, search_page 5 -> 4 (kept ones are canvas pacing or poll ticks). Verified by baseline/after pairs: admin users 5/2 known defects both, rules 17 both, sites 10 both, insights 37 both, views dragdrop 10 -> 11, search 27 -> 24 with the 3 extra failures passing standalone (results endpoint flake). Review moved the favorites and bookmark signals to the network acks and the toast (a click flips the star ~300 ms before the save answers). |
| 4 | c2c sleeps (3) | [BLOCKED] | Hardware session to verify a conversion. |
| 5 | Sidecar step files: maps, media_operations, chats, events_search | [ARTIFACT] | Regenerate at next sidecar sync (case keys kept); events_search corrected steps need Justin's manual push to live QA Touch. |
| 6 | QA Touch gap analysis (coverage vs case mapping) | deferred | After the above, per Justin. Note: mapping metadata says 352 tests, collection says 819. |
| 7 | Tenant mop-up | [DONE] | 08/24: `python tools/tenant_cleanup.py` (dry run) / `--apply` deletes the automation's own leftovers by name pattern - two "2026*AutomationEdited" groups removed, no automation users left. Re-run it whenever a run dies mid-test. 08/25: `--delete-channel NAME` (repeatable, exact name, --apply to delete) removed the dummy channels "123" (two rows), "1234" and "Google"; BTM and Videonetics remain. |
| 8 | views bookmark export (test_export_bookmark) | [DONE] | Was intermittent in-suite, not a hang (passed standalone 71s; manual export works). Fixed 08/21 PM: completion accepts bar-hidden OR success toast (toast corroborated by the bar being gone), bound raised to 180s, greppable "[EXPORT] completed in Ns" line so a recurrence produces data. Watch the elapsed line in the next full views run. 08/24: two standalone runs died BEFORE the export - the player's 'camera failed to load' overlay intercepted the bookmarks toggle; open_bookmarks_panel now calls the existing recover_stream_if_failed first. 08/25 PM: export sat at 0% for the full 181 s twice on a live stream (screenshot shows the progress dialog at 0%); play_bookmark: the player's own spinner (named by the new [FULLSCREEN] diagnostic) stayed 30 s after the seek; delete_bookmark: the card stayed listed after Delete in the last two of three runs. The three held across three runs (12:54, 14:19, 14:50) while add/rename/share passed; player/backend behaviour on the QA tenant, not the page objects. Next: open the 14:50 traces for play and delete before raising them as app questions. |
| 9 | Sequence edit flow (sequence_page.change_timing / open_edit_dialog) | [DONE 09/01 - deleted] | Confirmed dead: no test calls open_sequences_panel / select_last_sequence / add_sequence_to_views / open_edit_dialog / change_timing (only stale .pyc matched). The live flow is already covered by test_edit_sequence + test_add_created_sequence_to_views, which use `_navigate_and_verify()` + `div.sidebarlist-item-button` on the current layout. Deleted the 5-method dead cluster (sequence_page.py, -14 ruff errors). Rebuild rejected: it would duplicate live coverage. |
| 10 | license_page.feature_rows / feature_toggle_switches | [DONE 09/01 - deleted] | Confirmed dead: no test calls feature_rows / feature_toggle_switches / get_feature_count / toggle_feature_enable / click_feature_device_link. The live layout is already covered read-only by test_expand_site_shows_features / test_site_enable_toggle_visible / test_available_tab_displays_feature_list. Deleted the 2 attrs + 3 methods (license_page.py, -5 ruff errors); kept _toggle_switch / site_toggle_switches / toggle_site_enable (live). Rebuild rejected: an active feature toggle mutates the shared tenant for every tester. |
| 11 | Leaked "AutoTest" users | [BLOCKED] | Each test_add_user run leaves one more (3 -> 4 on 08/24) because the tenant rejects user/remove (the 08/17 app defect). tools/tenant_cleanup.py will clear them once the app fix lands. |
| 12 | TEST_SITE_ID pointed at the wrong site | [DONE] | `.env` had 17 ("Example Corporate Office"); the configured test site "Newtown Action Area" is 16. Corrected 08/24; the `api` fixture skips with both values on a mismatch. Check any teammate `.env` copied from the old template. |
| 13 | test_drag_location_to_tile skipped vacuously | [DONE] | Passed None as the location, so the locator was `text=None` and the test had only ever skipped. Found 08/24 by the new skip-reason logs; now drags the configured site and passes (17 s). |
| 14 | drag_camera_to_tile_by_name lands the wrong camera | [FIXED 09/01] | Root cause: the thumbnail was found by `.cameraThumbnailWrapper:has-text('{name}')`, a case-insensitive substring, so 'test1' could land 'test10'. Switched both Python locators and the JS fallback to exact `span[title]` match (add_camera_via_checkbox, drag_camera_to_tile_by_name, _simulate_camera_drag_via_js). VERIFIED 09/01 on the US box (BOX=us, live streams, site Spartan0): a probe drove BOTH changed methods - drag_camera_to_tile_by_name('Soterix Multicam 1.15') and add_camera_via_checkbox('Soterix Multicam 1.16') - each landed the exact camera and passed assert_tile_streaming; real collision confirmed (has-text('Soterix Multicam 1.1')=4 vs exact span[title]=1). Permanent pytest for the drag path is test_drag_camera_by_name_to_tile (test_views_drag_drop.py). See item 17 for the checkbox-path coverage gap. |
| 15 | Audio delivered while audioGrabbing is false | [APP QUESTION] | Channel 97 streams a FLAC audio track (fragments flowing) although getCameraStreamingParameters/audio says audioGrabbing false. Ask the team whether the track is silence or a settings defect before any audio oracle. |
| 16 | Media socket not tied to the session | [SECURITY QUESTION] | The streaming socket (streaming2 /v3/api/ws) delivered a full stream with no session cookie; the `src=` parameter alone admits the connection (probed 08/25, tools/stream_probe.py --no-browser). Raise with the app/security team before any external exposure review. |
| 17 | add_camera_via_checkbox has no pytest coverage | [DONE 09/01] | The audit found the changed exact-match locator in add_camera_via_checkbox was exercised only by tools/stream_probe.py: test_devices_add_camera_via_checkbox was named for the method but reimplemented the flow inline. Repointed that test to call self.views.add_camera_via_checkbox(config test_camera_name); green on india (tile consumed) and verified live-streaming on US 09/01. Ruff net -2 on the file. |
| 18 | Interpolated name-into-selector locators (crash on quote / substring wrong-match) | [DONE 09/02] | views_page.py: all 10 title='{name}' locators + 2 JS fallbacks converted to get_by_title(exact=True) / getAttribute compare; audit 10 raw -> 0 confirmed. Residue sweep: lpr list rows (scoped to the NAME CELL - a list named 'Black List' must not land a row whose type column says the same), events rule/site/camera-menu, insights category, license modal site all converted to exact escaping forms, each grounded by a live DOM probe first (rows/options/items are bare names; camera-menu node text is name+count so the filter targets the inner exact-name element). Live proof of the old bug: `tr:has-text('ac')` matched every 'Black List' row. Verified green: events site/camera/rule, insights widget create, lpr plate-page + filter-panel (drive _open_list_by_name); license select_site_in_modal has NO test caller - probe-grounded only, same get_by_role form as the live-verified events select_site. Audit 2: 15 raw -> 0 confirmed. Also fixed: test_lpr_navigation sampled tr.all() before the table hydrated and skipped "No LPR lists" on a 107-row tenant; a suppressed 15s first-row wait now precedes all 4 samplings. |
| 19 | Same-class fuzzy identity lookups (audit residue, pre-existing) | [DONE 09/02] | Converted with the item-18 recipe, each probe-grounded first: admin rule-wizard DEVICE pick to exact (a substring could build the rule on the wrong camera; a rename now fails loud with the on-screen names), admin click_site, views drag_location + click_site, maps select_site (strictness kept), insights widget site pick (exact first, anchored escaped 10-char-prefix fallback because the dropdown ellipsizes long names IN THE DOM). Verified green: full rule-wizard creation, drag_location, admin navigate-to-site, maps select_site, insights widget create. Audit: 24 raw -> 1 confirmed (low) -> fixed: drag_location got the sibling drift guard so a case-only rename fails loud instead of skipping forever (its only caller wraps in skip). Left deliberately (uncalled-with-name paths): events select_camera location branch, views drag_map map_name branch - moved to item 20. |
| 20 | Fuzzy identity residue, round 3 | [INVESTIGATE] | Verified survivors of the 09/02 sweeps: search_page 113 `.dropdownItem:has-text('{text}')`, search_page 296 rows.filter(has_text=site_name) (substring), lpr_page 706 `text='{site_name}'` (quoted text engine - a quoted name breaks it), admin_page 302 get_by_text(user_text) fuzzy USER pick, events_page 286 duration option `:has-text('{duration_text}')`, tools/qatouch_browser 1613 `text="{target_value}"`, plus the two item-19 leaves (events location branch, views map_name branch - no caller passes either name today). Item-18 recipe when picked up. |

Quality gates, all zero as of 08/17/2026 and enforced by the checker
on every commit: no-oracle tests, early-exit passes, except-swallow
blocks, uncommented test-file sleeps (outside the c2c hold).

## Done - rebuilds and repairs (08/09-08/14/2026)

| Test / suite | Done | Lesson home |
|--------------|------|-------------|
| views grid stream oracle (drag_drop by-name + multiple cameras) | 08/25: `ViewsPage.assert_tile_streaming` - the tile's video at readyState >= 3 with currentTime moving between two samples 700 ms apart, else the painted picture hashing differently; a still (the snapshot under the spinner or the failure overlay) fails naming the camera. First-camera tests settle + advisory only (tenant has offline cameras). PASSED screenshots wait up to 5 s for spinners. Built during a streaming outage (every media socket one frame, then closed); dragdrop run green after recovery, 11/11, oracle passed on the video path in 8 s. | CONVENTIONS (Waits), QA_THINGS_TO_KNOW (Live stream delivery) |
| views drag-and-drop (drag_drop + subtabs, 11 tests) | Repaired 08/21. Drags gripped text labels and silently text-selected; grip re-aimed at the draggable ancestor (app is plain HTML5 DnD) and oracles made baseline-relative. The JS fallbacks had never run (evaluate two-arg bug). Saved-view drag additionally needs a reload + the My Views subtab surface. | views_page.mouse_drag docstring |
| views_favorites add/remove | Rebuilt 08/09; camera tree self-collapses, toggle re-expands. | FAILURE_TRIAGE |
| admin_sites group CRUD + search inside site + site detail | Rebuilt 08/11-12 for the redesigned detail; sorting keeps an honest skip (no sort control). | - |
| admin_rules wizard (6 types) | Rebuilt 08/12, all types create end to end; rules self-delete at teardown. | FAILURE_TRIAGE (canvas vs full-view types, JS-click armed Done) |
| views_subtabs insights add-to-tile | Rebuilt 08/12; drag-to-tile, consumed tile is the oracle. | FAILURE_TRIAGE (forced drag) |
| lpr_playback (12) | Rebuilt 08/12; whole file asserted nothing before. | FAILURE_TRIAGE (drop on LAST tile, new video = played) |
| lpr_widgets (3) | Rebuilt 08/13; old creation flow was dead code. Drag-to-tile, div.box[aria-label] oracle. | FAILURE_TRIAGE |
| lpr_camera_selection (3) | Rebuilt 08/13; old file early-exited on the wrong page (vacuous green). | checker rule early-exit-pass |
| lpr_grid_and_timer, lpr_events | Rebuilt 08/12-13. | Known app behavior (timeout popup needs a stream) |
| chats + chats_deeper (17) | Rebuilt 08/13 for the search-first panel; 12 green + 5 designed skips (group creation removed). Chat partner in config. | chat_page docstring |
| admin_general (11) | Oracle fixes 08/13. | - |
| admin_audit_trail (14) | Rebuilt 08/14 on the real table; 13 green + 1 skip. | FAILURE_TRIAGE (get_by_text substring trap) |
| event_wall config (14) | Rebuilt 08/13, moved to tests/ui/event_wall/ 08/13; 13 green + held display skip. | Known app behavior (two surfaces) |
| license_assignment assign modal (4) | Rebuilt 08/09. | - |
| search_categories vehicle tests | Un-skipped 08/09; filter helpers rebuilt for the 2026-08 sidebar. | search_page docstring |
| search_drawing (6), search_deeper, incamera_search | Verified/repaired 08/09-11. | Known app behavior (repeat search needs changed filters) |
| media_operations (non-destructive) | Rebuilt 08/12; inline-input names, toast = server ack. | Known app behavior (stale page state) |
| Oracle debt (33 no-oracle tests) | Cleared to zero 08/13. Notables: delete-user footgun (server-side filter race), insights report on the download event, license dedup on whole rows. | FAILURE_TRIAGE (filter races the action) |
| Early-exit passes (11) | Cleared to zero 08/13-14 with the new checker rule. | checker rule early-exit-pass |
| Except-swallow blocks (96) | Cleared to zero 08/17: each classified best-effort (why-comment), swallowed oracle (now raises), or redundant guard (removed), every site adversarially verified. The new raises immediately surfaced two app defects (users undeletable/unsuspendable, rule edit form gone) and rebuilt two vacuous lpr_views tests. | FAILURE_TRIAGE |
| Section C verify runs (views bookmarks/share/fullscreen/playback, insights widgets, lpr camera selection, headed parity) | All green 08/13; one fix (player failure overlay self-heal). | FAILURE_TRIAGE |
| Test-file sleep debt (~380) | Cleared 08/13-14 across every module; c2c hold and a few commented signal-less settles remain. Page-object sleeps are open item 3. | CONVENTIONS (Waits) |
| Tenant data (Driver Site, Hanwha) | Config-driven since 08/09; in effect. | - |
| events_search sidecar | Steps regenerated 08/09; push pending (open item 5). | - |

Baseline runs: full suite 4-worker 08/14 - 383 passed, 182 skipped;
all failures accounted for (c2c hardware hold, 3 xdist-contention
singles that pass serially, and the 08/14 search outage below).

## Known app behavior (confirmed, not bugs)

- Media page serves stale state per page load: only the first rename
  commits; Vault tab misses same-load vaulting. Hard-reload between
  mutations. (Possible defect - Justin's list.)
- Rule wizard hides cameras at rule capacity; a "missing" camera means
  leftover *_Auto_* rules on it.
- Repeat search clicks need changed filters (by design, Justin
  08/09); tests run each search on a fresh view.
- LPR timeout popup ('Set Timeout Duration') opens only over a playing
  stream.
- Event Wall is its own feature with two surfaces, never mixed with
  regular Views/Events: configuration via regular login (Admin >
  General > Event Wall card > View), display via a special
  local-access login (log in, select a site, wall appears).
- Admin > General is a card page: card titles are no-ops, View
  buttons navigate (retry once - hydration can drop the click), the
  breadcrumb returns, the section tab is a no-op inside its section.
- Chat panel is search-first; group creation has no entry point (the
  chats CRUD tests skip and fail loud if it returns).
- Views add (+) tab is also a button.tabItem (untitled tabInner);
  count view tabs by their titled tabInner.

## App defects (reported)

- 08/17/2026 users created via Admin > Users > Add New User cannot be
  suspended or deleted: POST /REST/central/user/suspend and
  /REST/central/user/remove both answer 400 for them (a real user
  answers 200), and the UI shows nothing (empty alert). Three
  'AutoTest Playwright' users are on the tenant as evidence
  (testuser_2026_08_17_*@example.com). test_toggle_user_status and
  test_delete_user now fail loud on exactly this; they stay red until
  the app fix. Report to the app team; needs a manual delete of the
  three users by an app admin if the API refuses everyone.
- 08/17/2026 the rules 'Edit' icon opens a read-only details drawer
  (devices, schedules, audit) - the notification-edit form is gone
  since the rules redesign. test_edit_rule_notification holds as an
  explicit skip with a tripwire. Confirm with the app team whether
  notification editing moved or was removed.
- 08/14/2026 ~19:30 search endpoint 400 AGAIN (probe-confirmed after the 17:00 recovery). Reopen with the app team: the fix was partial or the fault recurs. Search-family suites stay red until it holds.
- 08/14/2026 search outage ~13:45-17:00: POST /REST/site/search
  returned 400 (body message:'SUCCESS!') for valid payloads, taking
  down Global Search, in-camera search, and Events tab search (same
  endpoint). Justin filed it; working again by 17:00. 21 tests catch
  it. Reference case: whole family red = check the app first.
- Candidates on Justin's list: Media stale page state, one rename per
  load, chat group creation removed (confirm intentional), player
  overlay link label possibly misspelled ("Rafresh" - unconfirmed,
  frame at reports/probe_shots/player_failed_overlay_suspected_typo.jpeg).

## Watch items

Bounded waits that print instead of failing; chase any that appears
in run output (its premise is wrong):
- `[VIEWS] open saved view finished but the empty-tile count stayed`
  (legitimate when a saved view has the same tile count)
- `[SEQUENCE] Save/Update clicked but ... still visible`
- `[LICENSE] Feature row clicked but no breadcrumb appeared`
- `_appears`/`_appears_hidden` swallow PlaywrightError, so a
  strict-mode violation looks like a timeout.

## Tooling

- `tools/explore_app.py` - probe harness (REPL or script, `snap()` in
  scope). Use it for rebuilds instead of guessing selectors.
- `run.py health` (`tools/health_summary.py`) - product tiles, a verdict
  line and a row per module (the folder under `tests/`, every run of it
  pooled, runs of 1 test included), and the tests to watch (last-20
  strip, flaky rate, last failure) over the archived runs
  (`reports/runs/health.html`). Run folders carry `log/` (`run.log`
  with every test's output, a file per failed test) and per-test
  records in `summary.json` (title, QA Touch case, timing, error line).
  `run.html` opens with a verdict, groups failures by error and marks
  each new or seen before, and gives every test a history strip and a
  change label against the previous run of the same target.
- `tools/convention_check.py` - runs on every commit; `--all` for
  standing debt. Rules: uncommented sleeps, no-oracle tests,
  early-exit passes, except-swallows, absolute counts, union picks,
  img-src guesses, QA Touch marks in tests, tenant names.
- Discipline: review the uncommitted diff before the first commit;
  every review class becomes a checker rule; claims about app
  mechanisms come from probes, and a fix to a shared fact greps every
  consumer.
- Playwright's official test agents need the Node runner; they do not
  plug into this pytest framework (checked 08/09).
