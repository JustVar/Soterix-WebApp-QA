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
[DONE] repaired and verified green.

## Open items (08/14/2026)

| # | Item | Status | Needs |
|---|------|--------|-------|
| 1 | Event Wall display suite (tests/ui/event_wall/test_event_wall_display.py) | [BLOCKED] | Local-access wall user (Justin creating). Then: its own env vars in config/env, probe login + site-select, build the wall's markers. |
| 2 | Media destructive set (clip/folder delete, grouping, move) | [INVESTIGATE] | Answer: does deleting a folder delete the clips grouped into it? Or a disposable measurement. |
| 3 | Page-object sleeps | mostly [DONE] | Converted 08/14: search_page, incamera_search_page, fullscreen_page, maps_page, login_page (53 -> 8 commented signal-less settles). Verified: maps 5/5, fullscreen 5/5, bookmarks 8/9 (setup flake), playback 9/10; search consumers verified NEUTRAL by A/B against HEAD (6 vs 7 fails on the same suite in the same window - the search endpoint was 400 again, see defects). camera_hardware_page (9) joins the c2c hold. |
| 4 | c2c sleeps (3) | [BLOCKED] | Hardware session to verify a conversion. |
| 5 | Sidecar step files: maps, media_operations, chats, events_search | [ARTIFACT] | Regenerate at next sidecar sync (case keys kept); events_search corrected steps need Justin's manual push to live QA Touch. |
| 6 | QA Touch gap analysis (coverage vs case mapping) | deferred | After the above, per Justin. Note: mapping metadata says 352 tests, collection says 819. |
| 7 | Tenant mop-up | [DONE] | 08/24: `python tools/tenant_cleanup.py` (dry run) / `--apply` deletes the automation's own leftovers by name pattern - two "2026*AutomationEdited" groups removed, no automation users left. Re-run it whenever a run dies mid-test. The dummy channels ("123", "1234", "Google") are NOT ours to delete - confirm with the team first. |
| 8 | views bookmark export (test_export_bookmark) | [DONE] | Was intermittent in-suite, not a hang (passed standalone 71s; manual export works). Fixed 08/21 PM: completion accepts bar-hidden OR success toast (toast corroborated by the bar being gone), bound raised to 180s, greppable "[EXPORT] completed in Ns" line so a recurrence produces data. Watch the elapsed line in the next full views run. 08/24: two standalone runs died BEFORE the export - the player's 'camera failed to load' overlay intercepted the bookmarks toggle; open_bookmarks_panel now calls the existing recover_stream_if_failed first. |
| 9 | Sequence edit flow (sequence_page.change_timing / open_edit_dialog) | [INVESTIGATE] | Dead paths since the sidebar redesign: select_last_sequence hits a strict-mode violation, the sequence page's own modalBackdrop blocks open_sequences_panel, and the edit dialog shows no combobox/select at all. No test calls them (probed 08/24). |
| 10 | license_page.feature_rows / feature_toggle_switches | [INVESTIGATE] | Match nothing on the current expanded-site layout (nested switch rows are tr.parentRow > td > MuiBox); no caller. Rebuild or delete. |
| 11 | Leaked "AutoTest" users | [BLOCKED] | Each test_add_user run leaves one more (3 -> 4 on 08/24) because the tenant rejects user/remove (the 08/17 app defect). tools/tenant_cleanup.py will clear them once the app fix lands. |
| 12 | TEST_SITE_ID pointed at the wrong site | [DONE] | `.env` had 17 ("Example Corporate Office"); the configured test site "Newtown Action Area" is 16. Corrected 08/24; the `api` fixture skips with both values on a mismatch. Check any teammate `.env` copied from the old template. |

Quality gates, all zero as of 08/17/2026 and enforced by the checker
on every commit: no-oracle tests, early-exit passes, except-swallow
blocks, uncommented test-file sleeps (outside the c2c hold).

## Done - rebuilds and repairs (08/09-08/14/2026)

| Test / suite | Done | Lesson home |
|--------------|------|-------------|
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
- `run.py health` (`tools/health_summary.py`) - pass rates, flaky
  candidates, newly failing, and slowest tests over the archived runs
  (`reports/runs/health.html`). Run folders carry `log/` (captured
  output per test, `run.log`) and per-test records in `summary.json`
  (title, QA Touch case, timing); `run.html` shows titles and change
  chips against the previous run of the same target.
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
