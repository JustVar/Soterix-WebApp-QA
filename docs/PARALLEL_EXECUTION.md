# Parallel test execution with pytest-xdist

pytest-xdist is installed but not enabled by default. This page records what
parallel runs need, what already works, and what still blocks a full rollout.

## How to run

```
pytest tests/ui -n 4
```

Nothing else. pytest.ini carries `--dist loadgroup`, which schedules by
`xdist_group` mark: every module that writes this account's state (saved
views, rules, users, sites, LPR lists, chats, clips, sequences, dashboards)
declares one, so its tests run on one worker in their written order, and
the search and events modules share `account_search` because the server
runs one search job at a time (register row 78). Modules without a mark
spread test by test. Never add `--dist` on the command line: it overrides
the ini silently, and `conftest.pytest_configure` refuses the run. A pin
(`tests/plugins/test_xdist_groups.py`) fails when a module that writes
state lands without a group.

**History.** From 2026-08-08 to 09/17 the recommended command was
`-n 4 --dist loadfile` (one file per worker). The nightly ran `loadgroup`
from 09/16, so the doc and the box disagreed, and `loadfile` on a laptop
undid the search grouping (audit 09/17/2026, row 86). The experiment log
below is from the loadfile period and still holds for what it measured:
concurrent sessions on one account.

Do not use `-n auto`. QA Touch uploads and `--verify-mode` run serial.

## What already works

- **Auth cache per worker.** `auth_state_path` in `conftest.py` returns
  `.auth_state.<worker>.json` under xdist, so workers do not race on one
  cache file. Each worker logs in once, then reuses its own cached session.
- **Failure traces per test.** Trace files are named by test id, so parallel
  workers do not overwrite each other's traces.

## Open risks

- **Shared tenant data.** All workers sign in to the same QA tenant. Tests
  that create, rename, or delete views, users, rules, or groups interfere
  across workers, so their modules carry an `xdist_group` (How to run) and
  generated names carry milliseconds (`%H%M%S%f`), never seconds alone.
- **Concurrent sessions on one account.** The experiment below ran 2 sessions
  on the same account without a kick-out. Higher worker counts are untested.
- **Hardware tests stay serial.** Never run `tests/c2c/` (its own product root
  since 09/11/2026; the nightly runs it without `-n`) or anything marked
  `destructive` or `mutating` with `-n`. These touch real cameras.
- **Load.** Each worker is a full Chrome instance. Video-heavy suites
  multiply CPU and bandwidth per worker.
- **Opt-in plugins stay serial.** The QA Touch reporter
  (`--qatouch-upload`) batches uploads per pytest session, so each xdist
  worker would upload its own batch - untested; run uploads without `-n`.
  Verification mode (`--verify-mode`) is interactive and makes no sense
  parallel. Both plugins are off by default and register nothing when off,
  so plain parallel runs are unaffected.

## Experiment log

### 2026-08-07: 2 workers, loadfile, same account

Command: `pytest tests/ui/views/test_views_basic.py
tests/ui/admin/test_admin_general.py -n 2 --dist loadfile`

Result: 16 passed, 1 error, in 183 s.

- Both workers signed in to the same account at the same time. Neither
  session got kicked. All tests that reached the app passed.
- The 1 error was `net::ERR_NAME_NOT_RESOLVED` during one login: a local DNS
  blip, not an app or parallelism failure. The login-failure trace in
  `reports/artifacts/` shows the navigation failing before the app was ever
  reached.
- Timing was not conclusive. Both workers did a fresh login (first parallel
  run, so no per-worker cache existed) and the DNS failure burned its
  timeouts. Expect real speedup only on longer suites with warm caches.

### 2026-08-07 (later): 3 workers, loadfile, same account

Command: `pytest tests/ui/views/test_views_basic.py
tests/ui/admin/test_admin_general.py tests/ui/views/test_views_subtabs.py
-n 3 --dist loadfile`

Result: 27 passed, 0 failed. Three concurrent sessions on one account, no
session kicks, no login failures. This includes the subtabs suite with
drags and video tiles, so moderate per-worker load is fine on this machine.

### 2026-08-08: 4 workers, loadfile, same account

Command: `pytest tests/ui/views/test_views_basic.py
tests/ui/admin/test_admin_general.py tests/ui/events/test_events_filters.py
tests/ui/licenses/test_license_navigation.py -n 4 --dist loadfile`

Result: 42 passed, 0 failed, in 630 s.

- Four concurrent sessions on one account: no session kicks, no login
  failures, all four per-worker auth caches created and reused.
- Four modules at once (views video tiles, admin, events searches,
  licenses) confirms moderate mixed load is fine on this machine.
- Wall clock tracks the slowest file (events filters, with its long
  server-side searches), which is the expected loadfile behavior: the
  longest file sets the floor.

Decision recorded above: `-n 4 --dist loadfile` is the recommended
regression command; mutating, hardware, upload, and verify-mode runs
stay serial. Revisit `-n 6`/`-n auto` only if regression wall-clock
becomes a problem and the account survives more concurrent sessions.
