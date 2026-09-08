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

Numbers are stable references; a finished row moves to the Done
section below with its number.

| # | Item | Status | Needs |
|---|------|--------|-------|
| 1 | Event Wall display suite (tests/ui/event_wall/test_event_wall_display.py) | [BLOCKED] | Local-access wall user (Justin creating). Then: its own env vars in config/env, probe login + site-select, build the wall's markers. |
| 2 | Media destructive set (clip/folder delete, grouping, move) | [WIP 09/02] | Semantics answered (Justin): folder delete deletes contained clips permanently; "Remove From Folder" un-groups without deleting; destructive testing sanctioned on india. Tests built: lifecycle (group -> enter via thumbnail -> un-group -> delete tripwire -> outside-clips integrity), move+restore, clip delete with dialog contract. Live measurement: the server refuses BOTH clip and empty-folder deletes ("Data Not Deleted!" toast) - see App defects; move skipped ("no folder" in its dropdown despite folders existing - dropdown scope to probe when deletes heal). Lifecycle verified live 09/02: group, thumbnail entry, and Remove From Folder (clip returned un-deleted) all green, then the designed skip at the refused folder delete. Red clip-delete stands until the app fix; move stays skipped pending the dropdown-scope probe. |
| 3 | Page-object sleeps | mostly [DONE] | Converted 08/14-08/25 across every page object (53 -> 11 commented pacing/poll settles); each tranche verified by baseline/after pairs, search neutrality A/B'd against HEAD during the endpoint outage. Remaining: camera_hardware_page (11) on the c2c hold. Signal lessons: CONVENTIONS (Waits), FAILURE_TRIAGE. |
| 4 | c2c sleeps (3) | [BLOCKED] | Hardware session to verify a conversion. |
| 5 | Sidecar step files: maps, media_operations, chats, events_search | [DONE 09/08] (push to QA Touch is Justin's) | The sidecar (tests/steps/ui/*.json) is what `qatouch_browser.py sync-steps` writes INTO QA Touch, and the chats one held template garbage - test_delete_group said "Navigate to Media > Group Delete", the edit test "Navigate to Admin > Edit User" - code-translated lines of the kind the house rule forbids. The sync now has a real path: `generate_step_stubs.py --from-docstrings FILE` rebuilds title and steps from each test's Steps/Expected block (the human-written case), keeps every case_key, never invents a step, and names each test that has no Steps block. Pinned by tests/tools/test_generate_step_stubs.py. Run on chats: 4 rebuilt from the docstrings written for item 29, 2 kept as-is, keys unchanged and equal to the mapping file's. Dry-run on the other three: maps 5, media_operations 13, events_search 10 tests have NO Steps block, so the tool rightly left every entry alone (the corrected events_search steps included). Those 28 blocks are a writing job in tester language, not a regeneration - once written, one command syncs them. 09/08 later: maps done - 5 Steps blocks written in tester language and synced; media_operations (13) and events_search (10) still need theirs. The sync also found two faults of its own making: the sidecar carried two keys the mapping file did not, so it now takes every key from config/qatouch_case_mapping.json (canonical) and the sidecar's is only a fallback; and it now names every key claimed by more than one test, because sync-steps would write both tests' steps into that one case. Maps: 4 of 5 share a key with maps_deeper and dypNzZ has three claimants - do not sync those until item 6 splits them. events_search done the other way round (09/08): its sidecar already held the hand-corrected steps, so those went INTO the ten docstrings verbatim and the round trip back out reproduced them exactly (only a closing period added per line). One more stale key replaced by the canonical one (vanZlz -> 68lnPV). Shared keys are worse here: dypXRb is claimed by five tests across events_search, search_categories and search_deeper. media_operations done last: 13 Steps blocks written in tester language from the bodies (the sidecar had been pure template - 'Navigate to Events > Create Link' for a clip, 'Views > Live Playback Controls' for folder share) and synced, 515 template lines gone, all 13 keys equal to the mapping's; the two-class file is fine because the registry resolves by file and method name only. Shared key: test_folder_share's Nj3r6e is also claimed by two views tests. All four files are now docstring-sourced: one command re-syncs any of them, and the keys shared across files are the item 6 worklist. The push to live QA Touch stays Justin's. |
| 6 | QA Touch keys claimed by more than one test | [DONE 09/08] | Measured against the 08/28 snapshot: 378 mapping rows, 302 distinct keys, 38 keys claimed by 2-5 tests, 92 tests involved; a shared key reports whichever test uploaded last and carries whichever test synced its steps last. Cause: the bulk title match at extraction. Split with Justin's go in three imports (14, 40, 9): 63 cases created by API with the tags blanked (the project knows only smoke/sanity/regression, and unknown tag labels refuse the whole row), read back and re-mapped, sidecars re-synced; 47 Steps blocks written on the way. Shared keys now 0. The last 9 were the re-points: keys whose case no test in the suite performs - rGQDWk (Audio option per camera), B86ENR (Event Wall card on General), pDpmba (Open Select Rule dialog), Drd9a9 (Search Camera input), 0rzlE9 (search by site name), dypXww (All tab contents), vanZz1 (My Views highlighted), J8d9R1 (search by clip name), xm9jkm (audit entry for an LPR edit) - so each holder got its own case and those 9 keys left the mapping; the cases stay in QA Touch as manual cases. Three of them (B86ENR, 0rzlE9, J8d9R1) duplicate a case another test already automates: merge by hand in QA Touch when convenient, there is no delete API. 8V1bJr (audit pagination) kept: the low score was the case's 'general functionality' prefix, the holder is the right test. Tools left behind: `--shared-keys` (the worklist), `--weak-mappings` (a REVIEW ORDER by title similarity - the least-alike pairs were mostly the same case in other words, so it orders and a person decides), and the snapshot pull repaired (dropped keyword, list unpacked as two values, no pacing; now paged with a pause and a 429 retry, guard from page 1's meta.total). Later 09/08, once the rate window cleared: snapshot refreshed (+63 cases, exactly the three imports), the last 9 read back split, and the review list fell 160 -> 97 (8 of those 'not in snapshot' turned out to be item 33). One re-point went the other way on inspection: test_search_site filters sites by name, which is 0rzlE9 'Verify search by site name' - so it holds that key now and n8jQRg (TR0384, 'Select Site dropdown resets on Reset Search', a flow no test performs) is the orphan. Orphaned cases to delete by hand in QA Touch (no delete API): TR2105 B86ENR 'Event Wall card is displayed correctly on the General page' (twin TR2949 kept), TR0384 n8jQRg (see above), TR0918 J8d9R1 'search by clip name returns matching results' (twin TR0979 'search by title filters results' kept). Gap noted: the mapping metadata says 352 tests and the collection 819. |
| 8 | views bookmarks: rename oracle + suite isolation | [DONE 09/03] | The suite now creates, renames and deletes through the UI and takes its verdict from the panel - this is the UI repo, so a bookmark test does what a person does. (An API-oracle version was committed first and replaced: it proved server state, not what a user sees.) The two app behaviours live in the page object instead. (a) The panel does not repaint after a mutation and the change reaches the list a beat later, so rows are read only after `refresh_bookmarks_panel()` re-opens it - reading the open panel straight after a rename or delete shows the old state, which is why the rename oracle failed even on healthy US streams (NOT the stream). (b) Rows carry only a positional id, so each test holds its own bookmark by the playback stamp the app writes on creation and a rename leaves alone; the old suite drove index 0, where a rename/delete could land a real user's bookmark on a shared camera. test_add_bookmark also removes what it makes (it leaked one per run). Verified on US: 9 passed, gates 0/0, and the only live bookmarks left afterwards were the two a person had made on other cameras. Related: the `api` fixture is now box-aware (active box's account + default_site_id, india 16 / us 156), which unblocks API-built test data on the US box. Reporting trap that produced two wrong "all green" reads here: piping pytest through `tail` hides the failure summary AND masks the exit code - capture full output. |
| 22 | Three maps tests skipped on every run | [DONE 09/03] | Justin added a map to the US box and all three passed, so the skip was honest, not a mask. The noise was click_site: it proved a site had expanded by waiting for the Devices-panel "All Cameras", which the Maps panel has no reason to show, so it logged a failure advisory on green runs. It now accepts either that marker or thumbnails; advisories on the same set went 6 -> 1. |
| 24 | Media suite borrows the tenant's clips | [BLOCKED] | Every media operation test starts at `_first_clip_or_skip`, which takes the tenant's FIRST clip, so the suite skips on an empty tenant and runs rename/move/delete against whatever clip is there. The fix is for each test to make its own clip, and the UI can: the player's clip control exports with "Save a copy to Media". Blocked because a clip cannot be deleted back off the tenant (App defects), so every provisioned clip would be permanent. Unblocks with the delete fix. |
| 26 | Bookmark export and share leaked a permanent clip each | [DONE 09/03] | Both page-object methods ticked "Save a copy to Media" unconditionally, so every suite run wrote two clips into Media that no one can delete. All 12 clips on the US tenant were ours, six runs in one day, named with the tests' own %Y%m%d%H%M%S. The copy is now opt-in and off by default; the export oracle is the progress bar and never needed it. Verified: three runs after the change added none, and export still passes (bar hidden in 20s). |
| 27 | LPR tests ran on leaked lists | [DONE 09/03] | test_create_list's teardown tracked every list it made and deleted none - the body was a navigate under a docstring saying it deleted them - so each run left a Test_List_<HHMMSS> behind and 8 tests were green only because the leftovers were there. All three classes now make the list they use and delete it, and the teardown raises for any that survives. Verified on US against a tenant with no lists at all: 22 passed, 0 skipped, nothing left behind. Two of my own bugs on the way: delete_list called a row absent before the table hydrated (item 18's race again), and test_lpr_page_ui_elements needed its own list because the page renders an empty state instead of a table - it had been passing on another test's leftover. |
| 25 | Skip audit across the UI suite | [DONE 09/04] | 129 skips in tests/ui, sorted into: make the artifact, prove the surface before reporting absence, or let the failure fail. Now 58, and every one of those states what was measured. The class is closed at the checker: `skip-in-except` (HIGH, 21 -> 0) catches a handler that reports the app's own error as Blocked, and `speculative-skip-reason` (MEDIUM, 10 -> 0) catches a reason that guesses. `tests/shared/helpers/surface.py::require_items` is the shared "prove it first" check, and CONVENTIONS > Missing artifacts and skips grew from two rules to four. Worst finding: test_drag_map_to_tile and test_add_channel_to_tile ran their whole bodies - closing assert included - inside `except Exception: pytest.skip(...)`, so neither could ever go red. Rules and insight widgets now make their own artifact (item 27's shape): edit/mute/delete had driven index -1, a real user's rule on a busy tenant and a chronic skip on a clean one. Verified per module on US - admin_rules 12p/3s/1f -> 17p/1s, drag_drop 6p/1f -> 7p, views_playback and fullscreen 15p, maps 12p/1s, licenses 34p/8s (every skip proved), incamera_search 1p/1f -> 2p. Two of my own bugs on the way, both caught by the repo's own gates: the new rule fired on my helper, and ruff caught an F821 missing import.. 09/08: the insights_dashboard leftover is rebuilt - 14 skips -> 0, 15 passed on both boxes. Measured cause of the skips: every guard clicked .first of a union like `button:has-text('Create'), div:has-text('Create New')`, which matched 18 elements with an ancestor div first, so the click never left the landing and the creation tests skipped every run; one still passed because its oracle was `input count > 0`, which the landing's Search box satisfies (the union-first trap from CONVENTIONS, plus a vacuous oracle). The tests now use exact role/name locators, the URL and the name field as the opened signal, and assert what the page does: System Status is the only preset and is a link, there are no cards on this build, View All stays on the landing with no user dashboards, and Save stays disabled with a name until a widget is added. Nothing is saved, so nothing leaks. Steps written for all 15 and the sidecar synced. Skips left in tests/ui: 46, from 129. |
| 28 | One leftover rule hides the camera from the wizard | [DONE 09/04] | delete_rule_by_name returned True on a delete that never landed, so a run could leak one rule. That is not untidiness: the wizard hides a camera at rule capacity, and a single leftover Occupancy rule made the configured US camera vanish from Select Devices, so every later run died there. Measured by probe (21 cameras listed, 1.15 absent; delete the rule and it returns). The delete now has an oracle and raises naming the consequence; the rules teardown presses Escape first, because the details drawer's backdrop hides the search input. Do NOT add a reload to that teardown - reloading the Rules page leaves an overlay that eats the Admin nav click for 30s, which is what made the first fix fail. |
| 29 | Chat group CRUD rebuilt for the box that has it | [DONE 09/08] | Group creation is a box difference, both probed 09/04: US renders a real Create Group button, india has no such element. The four group tests and the deeper button test now prove the panel is open, skip with that proof on india, and run on US - each makes the group it acts on and the teardown deletes it and raises for a survivor (item 27's shape). Chats on US went 10 failures -> 5 (per-box chat partners, 09/04) -> 0. Rename stays a measured skip with a tripwire: the thread's edit icon is inert on this build (no input, textarea or contenteditable opens, probed 09/08), the same shape as the rules Edit icon. Page object: create_group, open_group, delete_group, group_rows, refresh_panel, group_rename_control. Verified US 16p/1s with zero leftovers, india 12p/5s. Two of my own bugs on the way, both caught by the loop and not by reading: the rename tripwire read editables page-wide with no baseline and fired on the Views page's own inputs behind the panel; and the first teardown gated its delete on an instant row count right after the panel re-opened, read 0 for three groups that were there, reported nothing, and left all three on the tenant - item 18's hydration race in a teardown, which is item 28's silent-success class. It waits 5s for the row now. The traps that cost a probe each live in the chat_page docstring: search never lists a group, the member popper covers Create until Escape, confirm controls are divs, and the list does not repaint after a delete. |
| 30 | tools/tenant_cleanup.py ignored BOX and under-reported | [DONE 09/04] | Two silent faults in a tool that DELETES. It read QA_USER directly, so `BOX=us ... --apply` logged into India and would have deleted from the wrong tenant (item 23's defect, second tool). And it cleaned whichever site the Sites page listed first rather than the box's configured one. Both fixed: the account now comes from get_credentials(), the site is test_site_name and a mismatch exits naming the sites that ARE listed, and the run prints `Tenant: box=... account=...` before it lists anything - read that line before passing --apply. Verified both ways: BOX=us reaches test-auto-qa/Spartan0, BOX=india reaches justin/Newtown Action Area. Third fault found on the way: the users step read only each card's FIRST line, which is the avatar's initials ("AP"), so it printed "0 automation leftover(s)" with ten on screen. It now reports them by e-mail, which is the unique handle - the display name is the same on all ten. Pinned by tests/tools/test_tenant_cleanup.py (8 tests, no browser needed). 09/08: it now clears rules (`<type>_Auto_<stamp>`, matched on the truncated name cell) and chat groups (`AutoGroup_<stamp>`), and runs those two steps BEFORE users, because the tenant refuses some user deletes and that must not abort the step that unbreaks later runs. A refused user delete is now reported and skipped, not fatal. Verified on US by leaking one rule and one group on purpose: dry run listed both and deleted nothing, --apply removed both, the next dry run was empty. Two placement bugs on the way: the top nav's Admin link is covered by a MuiBox overlay from inside Admin (the sidebar tab is the way), and the users step had been first. Not covered: favourites (item 32's cause is unknown) and Folder_* (deletes refused, App defects). |
| 31 | Commit messages carried AI attribution | [DONE 09/04] | The workspace CLAUDE.md forbids naming an AI tool, model or co-author in anything committed, and 14 commits from 09/03-09/04 carried the trailer to both remotes anyway. Justin authorised the rewrite: the 14 messages were stripped and force-pushed to both remotes, which now match at the same commit. Content was untouched - every tree hash matches the pre-rewrite backup and the diff between them is empty. The four dependabot co-author lines are legitimate and stayed. Anyone holding an older clone must `git fetch && git reset --hard origin/main`; a plain pull merges the old history back. Going forward the gate is tools/hooks/commit-msg - install it beside the pre-commit hook (COMMAND_SHEET section 8). It matches a co-author trailer only when the line names an AI vendor or model, so real bots still pass. |
| 32 | test_add_remove_favorites failed on 09/04 and the cause is not what was recorded | [INVESTIGATE] | It failed in the 09/04 full run and again alone: 15s with no favourite response after the star click. The star was ON at the time, clearing it made the test pass, and the row here first said a left-on star poisons every later run. That was correlation, and a reproduction disconfirmed it 09/08: with the star deliberately turned ON the test passed in 24s. So a left-on star is NOT the cause, and the real factor is unknown - the 09/04 trace was overwritten by later runs before anyone read it (reports/artifacts is per run, and the archive keeps screenshots, not traces). Not a mechanism to fix yet. Next time it fails: copy reports/artifacts/*favorites*trace.zip aside BEFORE the next run and read the network log around the click. |
| 33 | Nine tests mapped to cases that no longer exist in QA Touch | [DONE 09/08] | The 09/08 snapshot held 3164 cases and 9 mapped keys were not among them: cases deleted by hand at some point while the mapping kept pointing at them, so those tests' results had been uploading into nothing (test_delete_user, test_edit_group_name, test_close_system_status_tab, test_password_too_short, test_logout_from_different_pages, test_core_tabs_accessible, test_search_clear_and_retry, test_tab_round_trip_folders_to_shared, test_my_views_drag_saved_view_to_tile). `--dead-keys` finds them. With Justin's go: 9 cases created, read back, 11 rows re-mapped (two are parametrized), sidecars re-synced. Full audit afterwards against a fresh snapshot (+72 cases today = the four imports): 378 mapping rows, every mapped test in the suite, no empty key, no shared key, no dead key, each of the 72 references on exactly one case with as many steps as its docstring, every new case mapped back, every sidecar key equal to the mapping's, collection not shrunk, both remotes at HEAD, no attribution. The audit found one more pre-existing fault on the way: 21 sidecar keys in files never re-synced (admin_general, login, licenses and others) disagreed with the mapping - the maps/events stale-key defect suite-wide - so every sidecar is now synced from its docstrings and keyed from the mapping. Two tests map one case per parameter on purpose (test_create_rule_full_wizard, test_event_search_by_duration); untouched today. |
| 11 | Leaked "AutoTest" users | [BLOCKED] on india, narrower than filed | Each test_add_user run leaves one more because the tenant rejects user/remove (the 08/17 app defect). india, measured 09/04/2026: TEN, one per run day from 08/17 to 09/04 (testuser_2026_*@example.com) - the filed evidence, left in place; tenant_cleanup lists them and says up front the deletes will be refused. US, measured 09/08/2026 with tenant_cleanup --apply: five were leaked (one from 08/03, four from the 09/04 full runs) and FOUR deleted cleanly; only the 08/03 user survived - the tool could not reach a delete for it in 5s. So the refusal is not every AutoTest user: the four made on 09/04 via Add New User deleted, the old one did not. Whether that is the box, the user's age, or a fix that landed between 08/17 and 09/04 is unmeasured - re-test one india user by hand before re-filing. |
| 23 | tools/explore_app.py probed the wrong tenant | [DONE 09/03] | It logged in with QA_USER and cached every session in one .auth_state.json, so BOX=us quietly probed india and screenshotted india's sites. Caught live during item 22. It now uses the active box's account and the same per-tenant cache key the tests use; both call one helper (tests/shared/auth_state.py) so the tool and the fixture cannot drift again. |
| 15 | Audio delivered while audioGrabbing is false | [APP QUESTION] | Channel 97 streams a FLAC audio track (fragments flowing) although getCameraStreamingParameters/audio says audioGrabbing false. Ask the team whether the track is silence or a settings defect before any audio oracle. |
| 16 | Media socket not tied to the session | [SECURITY QUESTION] | The streaming socket (streaming2 /v3/api/ws) delivered a full stream with no session cookie; the `src=` parameter alone admits the connection (probed 08/25, tools/stream_probe.py --no-browser). Raise with the app/security team before any external exposure review. |

Quality gates, all zero as of 08/17/2026 and enforced by the checker
on every commit: no-oracle tests, early-exit passes, except-swallow
blocks, uncommented test-file sleeps (outside the c2c hold).

## Done - 08/24-09/02 repairs and the exact-name locator series

Full verification evidence lives in the commits (git log --grep by
keyword) and the lesson homes; rows here are the summary of record.

| # | What | Lesson home |
|---|------|-------------|
| 7 | Tenant mop-up: tools/tenant_cleanup.py clears automation leftovers (groups, users, --delete-channel). Re-run after any mid-test death. | Tooling |
| 9 | Deleted the dead sequence-edit method cluster (5 methods, no callers); live flow already covered by test_edit_sequence. | - |
| 10 | Deleted dead license feature_rows/toggles (no callers); read-only coverage already exists, and an active toggle would mutate the shared tenant. | - |
| 12 | TEST_SITE_ID corrected to the configured site (16); api fixture skips loud on mismatch. Check teammate .env copies. | - |
| 13 | test_drag_location_to_tile had only ever skipped (text=None locator); now drags the configured site. | checker skip-reason logs |
| 14 | drag_camera_to_tile_by_name landed the wrong camera: substring has-text -> exact span[title] in both camera methods + JS fallback; verified streaming on US (Spartan0). | CONVENTIONS (identity lookups), FAILURE_TRIAGE |
| 17 | test_devices_add_camera_via_checkbox now calls the page-object method it is named for (was inline; the method had zero pytest coverage). | - |
| 18 | Locator series round 1: all views_page title='{name}' + JS fallbacks, lpr list rows (name-cell scoped), events rule/site/camera-menu, insights category, license modal -> escaped exact forms, each DOM-probed first. Also fixed the "No LPR lists" hydration race. | CONVENTIONS (identity lookups), FAILURE_TRIAGE |
| 19 | Round 2: rule-wizard DEVICE pick, admin/views click_site, drag_location (+ drift guard), maps select_site, insights site pick (exact + ellipsis fallback). | same |
| 20 | Round 3: search category + both Locations-panel row picks, lpr wait_for_site_list, qatouch_browser fallback; select_duration and toggle_user_status documented fuzzy-by-design. Two uncalled name branches stay open by choice. | same |
| 21 | add_first_camera_via_checkbox matched by case-insensitive substring and, on a miss, silently fell back to the first thumbnail - whole suites ran against a camera nobody chose (a bookmark landed on a Uniview PTZ). Now exact on the title label, and absent means a loud raise listing what IS on screen. Verified US 2 passed; the india pair fails identically at HEAD (stream outage, not this change). | FAILURE_TRIAGE (re-render rows + filter) |

Series verification: three adversarial audits (10->0, 15->0, 24->1
fixed, 16->3 all addressed) plus live runs per row; US box (BOX=us,
Spartan0) proved the streaming paths end to end.

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
- Media folders: deleting a folder deletes the clips grouped in it
  (permanent - the Delete Clip dialog says "cannot be retrieved");
  "Remove From Folder" on a clip's row menu un-groups it back to the
  level above WITHOUT deleting (confirmed by Justin, 09/02/2026).
- Rule wizard hides cameras at rule capacity; a "missing" camera means
  leftover *_Auto_* rules on it. ONE leftover is enough: a single
  Occupancy rule on Soterix Multicam 1.15 removed it from the US
  wizard's 21-camera tree, and deleting that rule brought it straight
  back (probed 09/04/2026). So a leaked rule breaks every later run,
  not just the run that leaked it - register item 28.
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
- Chat panel is search-first. Group creation has no entry point on the
  INDIA box (probed 08/13 and again 09/04/2026), and the chats CRUD
  tests skip there. On the US box the Create Group button is present
  and the whole create/rename/delete flow works, so the tripwire fires
  and those tests go red until they are rebuilt - register item 29.
  The panel's search matches users only: a group never appears in
  search results, only in the conversation list.
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
- NC-20325 (P1, Ready for Dev 08/17): media folder grouped with notes
  and vaulted cannot be deleted. Confirmed broader 09/02 by probe: a
  plain empty folder AND a plain clip both get the server refusal
  toast "Error / Data Not Deleted!". Not one tenant's problem: the
  same refusal reproduces on the US box (09/03), on a clip our own
  tests made, after a confirm dialog that promises the clip "will be
  deleted permanently". The clip case is UNFILED - file it
  (test_clip_delete stays red on exactly this until the fix).
  Leftover automation folders on the tenant (undeletable until the
  fix): Folder_1788363244835, Folder_1788362955471,
  Folder_1788364176161, Folder_1788364279688. tenant_cleanup does not
  know the Folder_* pattern yet - extend it once folder delete heals.
- NC-19785 (P3, Ready for Dev 04/17): clips inside a folder are not
  searchable from Media > All.
- UNFILED (Justin, 09/02): deleting a media folder also deleted clips
  OUTSIDE it. Not covered by NC-20325/NC-19785 - file when folder
  delete works again; the destructive suite's outside-clip integrity
  check is the repro.
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
- test_rename_bookmark died once on `.edit-delete-option` with
  "element was detached from the DOM, retrying" (US, 09/03/2026).
  It did not reproduce: the same file passed 9/9 straight after,
  and the test passes alone on both HEAD and the change that ran
  with it. The bookmark row menu re-renders while the panel
  refreshes, so treat a repeat as that race, not a locator fault.

## Tooling

- `tools/explore_app.py` - probe harness (REPL or script, `snap()` in
  scope). Use it for rebuilds instead of guessing selectors.
- `tools/tenant_cleanup.py` - dry run by default, `--apply` to delete
  the automation's own leftovers by name pattern: camera groups, rules,
  chat groups, users (in that order - a leaked rule breaks later runs,
  a refused user delete is reported and skipped); `--delete-channel
  NAME` (repeatable, exact). BOX picks the tenant, and the first line
  it prints says which. Run it after any mid-test death.
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
  img-src guesses, QA Touch marks in tests, tenant names, ticket
  keys in code.
- Discipline: review the uncommitted diff before the first commit;
  every review class becomes a checker rule; claims about app
  mechanisms come from probes, and a fix to a shared fact greps every
  consumer.
- Playwright's official test agents need the Node runner; they do not
  plug into this pytest framework (checked 08/09).
