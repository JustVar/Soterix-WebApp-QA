# Parallel test execution with pytest-xdist

pytest-xdist is installed but not enabled by default. This page records
what a parallel run needs, what already works, and the open risks.

## How to run

```
venv\Scripts\python.exe -m pytest tests/ui -n 4
```

Nothing else. `pytest.ini` carries `--dist loadgroup`, which schedules by
`xdist_group` mark: every module that writes this account's state (saved
views, rules, users, sites, LPR lists, chats, clips, sequences,
dashboards) declares one, so its tests run on 1 worker in their written
order. The search and events modules share `account_search` because the
server runs 1 search job at a time. Modules without a mark spread test by
test. Never add `--dist` on the command line: it overrides the ini
silently, and `conftest.pytest_configure` refuses the run. A pin
(`tests/plugins/test_xdist_groups.py`) fails when a module that writes
state lands without a group.

Do not use `-n auto`. QA Touch uploads and `--verify-mode` run serial.

## The groups

Give a new module the group of the data that it writes.

| Group | Data | Modules |
|---|---|---|
| `account_search` | The server's 1 search job | The modules in `search/`, and `events/` filters, playback and search |
| `account_views` | Saved views, favorites, bookmarks | `views/`: basic, bookmarks, drag_drop, favorites, subtabs |
| `account_rules` | Rules, notifications, sequences | `admin/test_admin_rules`, the modules in `notifications/`, `sequences/test_camera_sequences` |
| `account_users` | Users | `admin/test_admin_users` |
| `account_sites` | Sites | `admin/test_admin_sites` |
| `account_lpr` | Plate lists, and the layout of the LPR camera page (kept on the server for each user) | `admin/test_lpr_navigation`, `test_lpr_operations`, `test_lpr_views`, `test_lpr_grid_and_timer`, `test_lpr_camera_selection`, `test_lpr_playback` |
| `account_chats` | Chat groups and messages | `chats/test_chats` |
| `account_media` | Clips and folders | `media/test_media_operations` |
| `account_insights` | Dashboards and widgets | The modules in `insights/`, and `admin/test_lpr_widgets` |

To see the group of each module, run `grep -rn "xdist_group(" tests/ui`.

## What already works

- **Auth cache per worker.** `auth_state_path` in `conftest.py` returns
  `.auth_state.<worker>.json` under xdist, so workers do not race on 1
  cache file. Each worker logs in once, then reuses its own cached
  session.
- **Failure traces per test.** Trace files are named by test id, so
  parallel workers do not overwrite each other's traces.
- **Crashed workers.** `plugins/xdist_recovery.py` turns a worker that
  stopped into 1 failure with the test's name, and the run goes on.
- **Concurrent sessions on 1 account.** Runs with 2, 3 and 4 workers on
  the same account showed no session kick and no login failure.

## Open risks

- **Shared server data.** All workers sign in to the same account. Tests
  that create, rename, or delete views, users, rules, or groups interfere
  across workers, so their modules carry an `xdist_group`, and generated
  names carry milliseconds (`%H%M%S%f`), never seconds alone.
- **Higher worker counts are untested.** Think about `-n 6` only if the
  regression run becomes too slow and the account accepts more sessions.
- **Load.** Each worker is a full Chrome instance. Video-heavy suites
  multiply CPU and bandwidth per worker.
- **Opt-in plugins stay serial.** The QA Touch reporter
  (`--qatouch-upload`) batches uploads per pytest session, so each xdist
  worker would upload its own batch. Run uploads without `-n`.
  Verification mode (`--verify-mode`) is interactive and makes no sense
  parallel. Both plugins are off by default and register nothing when
  off, so plain parallel runs are unaffected.
