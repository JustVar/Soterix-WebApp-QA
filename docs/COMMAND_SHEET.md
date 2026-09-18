# Command and reference sheet

Everything you type to install, run, and read the results of this
suite, on one page. Keep it open while you work. The longer guides are
linked at the end.

Commands are written for Windows PowerShell or cmd. In Git Bash, write
`./venv/Scripts/python.exe` instead of `venv\Scripts\python.exe`.

## 1. Tools and links

| Tool | What it is for | Where |
|------|----------------|-------|
| Python (the version in `venv/`, 3.14 at the time of writing) | Runs pytest and Playwright | python.org |
| Google Chrome | The browser the suite drives (`--browser-channel chrome`) | google.com/chrome |
| Git | Gets the repo and pushes your changes | git-scm.com |
| Visual Studio Code + the Python extension | Editing and running single tests from the editor | code.visualstudio.com |
| Playwright for Python docs | API reference for `page`, `locator`, `expect` | playwright.dev/python |
| QA tenant | The app under test | `config/environments.yaml` (`qa` is the default) |

The VS Code extension named "Playwright Test for VS Code" is for the
Node.js version of Playwright. It does not run this suite. Use the
Python extension and its test explorer.

## 2. Check your setup

```
venv\Scripts\python.exe --version
venv\Scripts\python.exe -m playwright --version
venv\Scripts\python.exe -m pytest --version
```

A version number from each command means the setup is ready.

## 3. Install and configure

```
git clone https://github.com/Soterix-Systems/Soterix-WebApp-QA.git
cd Soterix-WebApp-QA
python -m venv venv
```

Clone near the drive root (`C:\qa\Soterix-WebApp-QA`, say): a deep path
pushes Windows past its path cap, git then needs `-c core.longpaths=true`
just to clone, and evidence file names get shortened to fit. No
`Activate.ps1`: PowerShell's default policy blocks it, so every command
here calls the venv's `python.exe` by path.

```
venv\Scripts\python.exe -m pip install -r requirements.txt
git config core.hooksPath tools/hooks
copy .env.template .env
```

No browser download: the suite drives the Google Chrome already on the
machine (section 1). The `git config` line turns on the repo's git hooks
for this clone (section 8).

Then open `.env`: `BOX` names the tenant (`india` by default) and that
box's pair, `QA_INDIA_USER` and `QA_INDIA_PASSWORD`, is what signs in.
That is all a test run needs. The other variables are optional
integrations; the comments in `.env.template` explain each one.

## 4. Key settings

`pytest.ini` applies these options to every run:

| Option | Effect |
|--------|--------|
| `--browser chromium --browser-channel chrome` | Drives your installed Google Chrome |
| `--html=reports/report.html --self-contained-html` | Writes one HTML report per run (overwritten each run; the archive keeps a copy) |
| `--tracing=retain-on-failure` | Saves a Playwright trace for each failed test |
| `--screenshot=only-on-failure --output=reports/artifacts` | Saves Playwright's own failure screenshots under `reports/artifacts/` |

`ENV` selects the environment (`qa` is the default; `stage` and `prod`
exist). `APP_TYPE=partner` switches to the partner configuration. Test
data names (site, camera) live in `config/env/<env>.py`, never in test
files.

## 5. Run tests

`run.py` is the recommended entry point. It runs pytest for you, prints
the command it used, and ends with the path of the run's `run.html` and
of the archive index.

```
venv\Scripts\python.exe run.py smoke                                # every test marked smoke
venv\Scripts\python.exe run.py module views                         # tests/ui/views
venv\Scripts\python.exe run.py test "tests/ui/views/test_views_basic.py::TestViewsBasic::test_open_my_views[chromium]"
venv\Scripts\python.exe run.py rerun latest                         # the failed tests of the newest archived run
venv\Scripts\python.exe run.py open latest                          # that run's run.html in your browser
venv\Scripts\python.exe run.py list                                 # the last 10 archived runs
venv\Scripts\python.exe run.py health                               # pass rates per product and module, tests to watch (reports/runs/health.html)
venv\Scripts\python.exe run.py module views -- --headed -s          # anything after -- goes to pytest
venv\Scripts\python.exe run.py smoke --check                        # confirm the environment answers first
venv\Scripts\python.exe run.py module views --retry-streams        # rerun once a test that failed on the tenant stream failure
```

`rerun` and `open` also take a run folder name from `run.py list`.

`--retry-streams` is the one rerun the suite allows. It adds
`--reruns 1 --only-rerun "failed to load"` to the pytest command and
prints that it did. A test that failed on the tenant's stream-failure
message ("The camera failed to load") runs one more time. Every other
failure stays a failure. The flag is never the default, and the match
is never widened. A rerun hides a broken wait or a tenant that needs
a fix. Fix first.

The raw pytest forms below do the same work without the wrapper:

```
venv\Scripts\python.exe -m pytest tests/ui/views                 # one module
venv\Scripts\python.exe -m pytest tests/ui/views/test_views_basic.py
venv\Scripts\python.exe -m pytest "tests/ui/views/test_views_basic.py::TestViewsBasic::test_open_my_views[chromium]"
venv\Scripts\python.exe -m pytest -m smoke                        # by marker (110 collected 09/14/2026)
venv\Scripts\python.exe -m pytest -m dragdrop tests/ui/views      # marker inside a module
venv\Scripts\python.exe -m pytest -k "bookmark"                   # by name pattern
venv\Scripts\python.exe -m pytest tests/ui/views --headed         # watch the browser
venv\Scripts\python.exe -m pytest tests/ui/views --headed --slowmo 500
venv\Scripts\python.exe -m pytest tests/ui/views -s               # see page-object output live
venv\Scripts\python.exe -m pytest -n 4 tests/ui                   # parallel; never add --dist (pytest.ini groups tenant-state modules)
venv\Scripts\python.exe -m pytest --collect-only tests/ui         # list tests, run nothing
```

Hardware-disrupting tests skip unless you pass `--run-destructive`.
The environment adds its own skips: `config/env/<env>.py` carries
`allow_write` and `allow_delete`. Where `allow_delete` is False (stage,
prod), tests marked `destructive` or `mutating` skip. Where `allow_write`
is False (prod), the create and delete suites (`admin_users`,
`admin_rules`, `admin_sites`, `bookmark`, `sequences`) skip too. The skip
reason names the environment and the flag. No flag lifts these.

To upload results to QA Touch, use the runner instead of bare pytest:

```
venv\Scripts\python.exe tools/run_suite.py smoke --env qa
venv\Scripts\python.exe tools/run_suite.py tests/ui/views --dry-run
```

Only one run can be active at a time. A second run stops at once with
a message that names the run that holds the lock.

## 6. Read the results

| Where | What |
|-------|------|
| `reports/runs/<start>__<target>/run.html` | Start here for a run. A one-sentence verdict, then the failures, grouped when they share an error, each with its error, call log, screenshots, video, and the show-trace command. Then the notes (the advisory lines), the slowest 5, passed, and skipped. Every test carries a strip of its last 20 outcomes and a label for what changed since the previous run |
| `reports/runs/index.html` | One row for each run, newest first. See "How to read the archive index" below |
| `reports/runs/health.html` | Test Health, built by `run.py health`. One tile per product: runs, pass rate, tests to watch, modules, last run. Then one row per module (the folder under `tests/`: Views, Admin, Tools) with its runs, pass rate over test outcomes, passed and failed counts, mean full-module run, notes, and newest run as a date with its outcome. Every run of a module counts toward it, a run of 1 test included. `Show runs` under a module lists its runs: the date, what ran (whole module, a marker, or 1 test by its title), and the outcome. Then the tests to watch, each with its last 20 outcomes |
| `reports/runs/<start>__<target>/` | That run's report, screenshots, traces, videos, results JSON, and `advisories.txt` |
| `reports/report.html` | The latest run's report (failures show their screenshot and a trace link) |
| `reports/screenshots/<test>__PASSED.png` | The latest run's labeled end-state screenshots; drags also keep a `__mid-drag-1.png` frame |
| `reports/artifacts/*-trace.zip` | The latest run's failure traces |
| The end of the console output | A `run advisories` section: the `[VIEWS]`, `[LPR]`, and `[EXPORT]` lines the page objects printed |

### How to read the archive index

The same page is on your machine (`reports/runs/index.html`) and on spartan1
(`http://10.2.0.2/qa-runs/`).

- **The Runners line** at the top shows each machine and the Chrome version
  of its newest run. `(stable X is out: update it)` after a machine means
  that its Chrome is behind Google's stable version. For spartan1, do the
  procedure "Update Chrome on the box" in `deploy/spartan1/README.md`.
- **The target** is what the run was asked to test, for example `tests/ui`.
- **The box badge** after the target is the tenant: `india` or `us`.
- **The machine badge** after the box is the computer that ran the tests.
  `spartan1` is the nightly. A different name is a laptop.
- **The counts** are passed, failed, skipped and errors.
- **The outcome** is Passed, Failed, Interrupted, Error or No tests. Hold the
  pointer on it to see the exit code.
- **Notes** is the number of advisory lines in the run.
- **The links** are `Run Report` (`run.html`, start here), `Raw pytest-html`
  (`report.html`) and `Folder`.

The filter box keeps the rows that contain the text you type. It also
searches words that the row does not show: the account, the operator (the
user who started the run) and the Chrome version. For example, type
`india` to see one tenant, or type a machine name to see the runs of one
laptop. Short text such as `us` also matches inside names.

Open a trace:

```
venv\Scripts\python.exe -m playwright show-trace reports\artifacts\<name>-trace.zip
```

Rebuild a run's page (after a hand edit of its folder), or build the page
of every run archived before the page existed:

```
venv\Scripts\python.exe -m plugins.run_report latest
venv\Scripts\python.exe -m plugins.run_report --all
```

Each run folder also holds `log/`. `run.log` has the session's logging
and then, one section per test, the output pytest captured for every
passed and skipped test. Each failed test has its own file beside it
with its captured output and traceback. `run.html` links a failed
test's file from its card, and `run.log` from the header and the Passed
section.

`docs/FAILURE_TRIAGE.md` explains how to read a trace and lists the
traps this app has taught us. Check that list before you blame timing.

## 7. Switches

Set these in `.env` or in the shell for one run.

| Variable | Values | Effect |
|----------|--------|--------|
| `ENV` | `qa`, `stage`, `prod` | Environment under test |
| `REPORT_SCREENSHOTS` | `all`, `off` | `all` embeds passed-test screenshots in the report too; `off` disables screenshots |
| `RUN_ARCHIVE` | `off` | Disables the per-run archive |
| `RECORD_VIDEO` | `off` | Disables the per-test video. Default: record every test, keep the clip only on failure |
| `RUN_GUARD` | `off` | Disables the one-run-at-a-time guard |
| `STREAM_GUARD` | `off` | Runs the `livestream` tests without the stream measurement (its line is in the summary under `stream guard`) |
| `PREFLIGHT` | `off` | Skips the session preflight (one captcha-free sign-in before any browser opens; a refusal ends the run with exit code 7 and one `PREFLIGHT:` line) |
| `SEND_TEST_REPORT` + `REPORT_RECIPIENT` | `1` + an address | Emails the report after the run |
| `PWDEBUG` | `1` | Opens the Playwright Inspector and steps through the test |
| `TEST_SITE_ID` | a site id | Site that API-built test data goes to. Must be the site that `test_site_name` in `config/env/` names. When they differ, the `api` fixture skips and its message gives the right id |

## 8. Before you commit

```
venv\Scripts\python.exe -m ruff check .
venv\Scripts\python.exe tools/convention_check.py
venv\Scripts\python.exe -m pytest tests/plugins tests/tools tests/helpers --html=logs/scratch.html
venv\Scripts\python.exe tools/test_inventory.py --check
```

The last line fails when `docs/TEST_INVENTORY.md` no longer matches the
tests: after adding, renaming or mapping a test, run
`venv\Scripts\python.exe tools/test_inventory.py --record` to rewrite the
page and append the day's counts to the growth ledger
(`history/test_counts.jsonl`); it appends only when the counts moved.
The QA Touch side has its own ledger, `history/qatouch_counts.jsonl`:
`qatouch_analytics.py snapshot` appends a row per project it snapshots,
and `tools/qatouch_ledger.py --backfill` rebuilds it from the snapshots
on disk. Both ledgers render on the inventory page under Growth.

Two hooks live in `tools/hooks/`. One command, once per clone, points git
at that folder, so the hooks are the tracked files themselves and a change
to them reaches you with the next pull:

```
git config core.hooksPath tools/hooks
```

(Older clones copied the two files into `.git/hooks/`; that still works,
but those copies do not follow the tracked ones.)

`pre-commit` runs the four checks of CI's collect gate that fit in
seconds, plus two of its own, so a commit that would fail the gate
fails on the laptop first: no staged line may
carry a credential value from `.env`; the convention checker reads the
lines the commit adds (a HIGH finding blocks); `docs/TEST_INVENTORY.md`
must match the tests on disk (regenerate with
`python tools/test_inventory.py`); no file may gain lint findings; the
collected-test floor holds; and the offline suites (`tests/plugins`,
`tests/tools`, `tests/helpers`) pass. Ten to thirty seconds, most of it the
last two steps (measured 09/18/2026). The offline run
changes nothing a live UI run writes: archive, run record, run guard and
screenshots are off and its reports go to `logs/`. CI alone keeps
`pytest --setup-plan` (fixture wiring, 25 s).
`commit-msg` rejects any message naming an AI
tool, model or co-author - the workspace CLAUDE.md forbids it and the
rule had been broken 14 times before the gate existed. Read
`docs/CONVENTIONS.md` for the rules and `docs/TEAM_CHANGES.md` before you
review a teammate's change.

## 9. Quick fixes

| Symptom | Cause and fix |
|---------|---------------|
| "Another test run is already active" | A run holds the lock. Wait for it, or if it is dead: `venv\Scripts\python.exe tools/run_lock.py release --env qa --force` |
| `[AUTH] Cached session unusable` then a fresh login | Normal. The cached session expired and the suite logged in again |
| "The camera failed to load" in a screenshot | The tenant stream failed, not the test. The page objects click the refresh link once; a stream that stays down fails loud |
| The browser never appears | Add `--headed` |
| No tests collected | The file must be under `tests/` and be named `test_*.py`; hardware tests need `--run-destructive` |
| A site or camera name is not found | The shared tenant renamed it. Update `config/env/qa.py`; see `docs/FAILURE_TRIAGE.md` |
| `reports/report.html` looks stale | The run used `--html=<other path>`; the archive under `reports/runs/` has every run |
| `[TRACE] Could not finalize trace` or `[VIDEO] Could not finalize video`, or a failed test has no trace, video, or screenshot | The file path is too long. Windows refuses a path past 260 characters unless long paths are on. Enable them (registry key `HKLM\SYSTEM\CurrentControlSet\Control\FileSystem`, value `LongPathsEnabled` = 1, needs admin) or clone the repo closer to the drive root. The reports shorten a file name that is longer than 250 characters, so only a deep checkout has this problem |

## 10. Read next

1. `README.md` - project overview and structure
2. `docs/CONVENTIONS.md` - how we write tests and page objects
3. `docs/FAILURE_TRIAGE.md` - how to chase a failure
4. `docs/TEST_REPAIRS.md` - what is broken, what was repaired
5. `docs/QA_TOUCH_INTEGRATION.md` - result uploads
