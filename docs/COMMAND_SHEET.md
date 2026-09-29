# Command and reference sheet

Everything you type to install, run, and read the results of this suite,
on 1 page. The longer guides are linked at the end.

Commands are written for Windows PowerShell or cmd. In Git Bash, write
`./venv/Scripts/python.exe` instead of `venv\Scripts\python.exe`. On Linux
or Mac, write `venv/bin/python`.

## 1. Tools and links

| Tool | What it is for | Where |
|------|----------------|-------|
| Python 3.14 | Runs pytest and Playwright | python.org |
| Google Chrome | The browser the suite drives (`--browser-channel chrome`) | google.com/chrome |
| Git | Gets the repo and pushes your changes | git-scm.com |
| Visual Studio Code + the Python extension | Editing and running single tests from the editor | code.visualstudio.com |
| Playwright for Python docs | API reference for `page`, `locator`, `expect` | playwright.dev/python |
| The QA server | The app under test | `config/env/qa.py` |

The VS Code extension named "Playwright Test for VS Code" is for the
Node.js version of Playwright. It does not run this suite. Use the Python
extension and its test explorer.

## 2. Check your setup

```
venv\Scripts\python.exe --version
venv\Scripts\python.exe -m playwright --version
venv\Scripts\python.exe -m pytest --version
```

A version number from each command means the setup is ready.

## 3. Install and configure

The full walkthrough is "Day one" in the README. The commands:

```
git clone https://github.com/Soterix-Systems/Soterix-WebApp-QA.git C:\qa\webapp-qa
cd C:\qa\webapp-qa
python -m venv venv
venv\Scripts\python.exe -m pip install -r requirements.txt
git config core.hooksPath tools/hooks
copy .env.template .env
```

Clone into a short path. A deep path pushes Windows past its path cap, and
evidence file names get shortened to fit. There is no `Activate.ps1` step.
PowerShell's default policy blocks it, so every command here calls the
venv's `python.exe` by path.

The install takes the shared package from the wheel in `vendor/`. It asks
for no credential. No browser downloads: the suite drives the Google Chrome
on the machine.

Then open `.env` and fill `QA_USER` and `QA_PASSWORD`, the account that
signs in. That is all a run needs. The server, the test site and the test
camera are in `config/env/qa.py`. The other lines in `.env.template` are
run switches, one per line, each with the file that reads it.

## 4. Key settings

`pytest.ini` applies these options to every run:

| Option | Effect |
|--------|--------|
| `--browser chromium --browser-channel chrome` | Drives your installed Google Chrome |
| `--html=reports/report.html --self-contained-html` | Writes one HTML report per run (the next run writes over it, the archive keeps a copy) |
| `--tracing=retain-on-failure` | Saves a Playwright trace for each failed test |
| `--screenshot=only-on-failure --output=reports/artifacts` | Saves Playwright's own failure screenshots under `reports/artifacts/` |
| `--dist loadgroup` | Under `-n`, keeps every module that writes account state on 1 worker |
| `--timeout=600` | Ends a test that runs past 10 minutes |

`ENV` selects `config/env/<ENV>.py`. The default is `qa`. Test data names
(site, camera, chat partner) live in that file, never in test files.

## 5. Run tests

`run.py` runs pytest for you, prints the command it used, and ends with
the path of the run's `run.html` and of the archive index.

```
venv\Scripts\python.exe run.py smoke                                # every test marked smoke
venv\Scripts\python.exe run.py module views                         # tests/ui/views
venv\Scripts\python.exe run.py test "tests/ui/views/test_views_basic.py::TestViewsBasic::test_open_my_views[chromium]"
venv\Scripts\python.exe run.py rerun latest                         # the failed tests of the newest archived run
venv\Scripts\python.exe run.py open latest                          # that run's run.html in your browser
venv\Scripts\python.exe run.py list                                 # the last 10 archived runs
venv\Scripts\python.exe run.py health                               # pass rates per module, tests to watch (reports/runs/health.html)
venv\Scripts\python.exe run.py module views -- --headed -s          # anything after -- goes to pytest
venv\Scripts\python.exe run.py smoke --check                        # ask first whether the server answers
venv\Scripts\python.exe run.py module views --retry-streams         # rerun once a test that failed on the stream-failure message
```

`rerun` and `open` also take a run folder name from `run.py list`.

`--retry-streams` is the 1 rerun the suite allows. It adds
`--reruns 1 --only-rerun "failed to load"` to the pytest command and prints
that it did. A test that failed on the server's stream-failure message
("The camera failed to load") runs 1 more time. Every other failure stays a
failure. The flag is never the default. A rerun hides a broken wait or a
server that needs a fix. Fix first.

The raw pytest forms do the same work without the wrapper:

```
venv\Scripts\python.exe -m pytest tests/ui/views                 # one module
venv\Scripts\python.exe -m pytest tests/ui/views/test_views_basic.py
venv\Scripts\python.exe -m pytest -m smoke                        # by marker
venv\Scripts\python.exe -m pytest -m dragdrop tests/ui/views      # marker inside a module
venv\Scripts\python.exe -m pytest -k "bookmark"                   # by name pattern
venv\Scripts\python.exe -m pytest tests/ui/views --headed         # watch the browser
venv\Scripts\python.exe -m pytest tests/ui/views --headed --slowmo 500
venv\Scripts\python.exe -m pytest tests/ui/views -s               # see page-object output live
venv\Scripts\python.exe -m pytest -n 4 tests/ui                   # parallel. Never add --dist (pytest.ini sets it)
venv\Scripts\python.exe -m pytest --collect-only tests/ui         # list tests, run nothing
```

Never add `-q`. `pytest.ini` has one, and 2 make `-qq`, which hides the
pass count.

Two switches in `config/env/qa.py` add skips: `allow_write` and
`allow_delete`. Where `allow_delete` is False, tests marked `destructive`
or `mutating` skip. Where `allow_write` is False, the create and delete
suites (`admin_users`, `admin_rules`, `admin_sites`, `bookmark`,
`sequences`) skip too. The skip reason names the flag. No command line
flag lifts these. Tests marked `destructive` also need `--run-destructive`.

Only 1 run can be active at a time. A second run stops at once with a
message that names the run that holds the lock.

## 6. Read the results

| Where | What |
|-------|------|
| `reports/runs/<start>__<target>/run.html` | Start here for a run. A 1-sentence verdict, then the failures, grouped when they share an error, each with its error, call log, screenshots, video, and the show-trace command. Then the notes (the advisory lines), the slowest 5, passed, and skipped. Every test carries a strip of its last 20 outcomes and a label for what changed since the previous run |
| `reports/runs/index.html` | One row for each run on this machine, newest first. See "How to read the archive index" below |
| `reports/runs/health.html` | Test Health, built by `run.py health`. One tile per product, then one row per module with its runs, pass rate, mean duration and newest run. Then the tests to watch, each with its last 20 outcomes |
| `reports/runs/<start>__<target>/` | That run's report, screenshots, traces, videos, results JSON, and `advisories.txt` |
| `reports/report.html` | The latest run's report (failures show their screenshot and a trace link) |
| `reports/screenshots/<test>__PASSED.png` | The latest run's labeled end-state screenshots. Drags also keep a `__mid-drag-1.png` frame |
| `reports/artifacts/*-trace.zip` | The latest run's failure traces |
| The end of the console output | A `run advisories` section: the `[VIEWS]`, `[LPR]`, and `[EXPORT]` lines the page objects printed |

### The lines a run prints first

The terminal summary carries these lines before the test list. Read them
before you read a single failure.

| Line | When it prints | What it means |
|------|----------------|---------------|
| `PREFLIGHT:` | The server did not answer, or refused the account, or the site id does not match. | No test ran. Exit code 7. Correct `.env` or `config/env/qa.py`. `PREFLIGHT=off` skips the check. |
| `[STREAM]` | Every run that can collect a `livestream` test. | What the guard measured on the test camera: the codec, the frames, and whether this Chrome decodes it. A second `[STREAM]` line is a second measurement after a 0-frame window. |
| `[CAMERA]` | Only when the run drove a camera other than `test_camera_name`. | `TEST_CAMERA` pinned one, or a marker in `-m` selected the camera `camera_capabilities` lists for it. |
| `[LOGIN]` | A browser login kept the form on screen. | The line quotes the message, and says whether a captcha or a lockout showed. Later tests in that process fail with the same line and do not submit the form again. |
| `[SESSION]` | A test failed with the login screen open. | The server dropped the session mid-test. The locator is not at fault. |

### How to read the archive index

The index is local to this machine. It lists the runs under
`reports/runs/`, and nothing else.

- **The target** is what the run was asked to test, for example `tests/ui`.
- **The counts** are passed, failed, skipped and errors.
- **The outcome** is Passed, Failed, Interrupted, Error or No tests. Hold
  the pointer on it to see the exit code.
- **Notes** is the number of advisory lines in the run.
- **The links** are `Run Report` (`run.html`, start here), `Raw pytest-html`
  (`report.html`) and `Folder`.

The filter box keeps the rows that contain the text you type. It also
searches words that the row does not show: the account, the operator (the
user who started the run) and the Chrome version.

Open a trace:

```
venv\Scripts\python.exe -m playwright show-trace reports\artifacts\<name>-trace.zip
```

Rebuild a run's page after a hand edit of its folder, or build the page of
every run that has none:

```
venv\Scripts\python.exe -m plugins.run_report latest
venv\Scripts\python.exe -m plugins.run_report --all
```

Each run folder also holds `log/`. `run.log` has the session's logging and
then, 1 section per test, the output pytest captured for every passed and
skipped test. Each failed test has its own file beside it with its captured
output and traceback.

Before you share a run folder with anyone, remove the secrets from it. A
trace holds a session cookie, and a traceback can hold a password.

```
venv\Scripts\python.exe tools/evidence_scan.py reports\runs\<run> --redact
```

`docs/FAILURE_TRIAGE.md` explains how to read a trace and lists the traps
this app has taught us. Check that list before you blame timing.

### One question, one place

| Question | Where the answer is |
|----------|---------------------|
| Did the run pass? | The verdict line of `run.html` |
| Why did this test fail? | The test's Error and Evidence tabs in `run.html` |
| Has this test failed before? | The test's History tab, or `run.py health` |
| What ran on this machine? | `reports/runs/index.html` |
| What changed since the previous run? | The change line under the tabs in `run.html` |
| Is this failure a known app defect? | The "Known defect" label, from `config/known_defects.yaml` |
| What does the suite cover? | `docs/TEST_INVENTORY.md` |

## 7. Switches

Set these in `.env` or in the shell for 1 run. `.env.template` lists the
same ones with the file that reads each.

| Variable | Values | Effect |
|----------|--------|--------|
| `ENV` | a name under `config/env/` | The env file to load. Default `qa` |
| `REPORT_SCREENSHOTS` | `all`, `off` | `all` embeds passed-test screenshots in the report too. `off` disables screenshots |
| `RUN_ARCHIVE` | `off` | Disables the per-run archive |
| `RECORD_VIDEO` | `off` | Disables the per-test video. Default: record every test, keep the clip only on failure |
| `RUN_GUARD` | `off` | Disables the one-run-at-a-time guard. A second run beside a live one wipes the first run's evidence |
| `STREAM_GUARD` | `off` | Runs the `livestream` tests without the stream measurement |
| `PREFLIGHT` | `off` | Skips the session preflight (1 captcha-free sign-in before any browser opens) |
| `TEST_CAMERA` | a camera name | Drives this camera instead of `test_camera_name` |
| `TEST_WALL_CAP` | seconds | The cap after which the run ends a test that never returns. 0 turns it off |
| `CHROME_ARGS` | Chrome flags | Extra flags for the test browser, the stream guard and the probe. For Linux, see `docs/LINUX_H265.md` |
| `PWDEBUG` | `1` | Opens the Playwright Inspector and steps through the test |

## 8. Before you commit

The pre-commit hook runs 6 checks, cheapest first, and stops at the first
that fails:

1. `tools/secret_check.py`: no staged line carries a value from `.env`.
2. `tools/convention_check.py`: the house conventions hold on the lines
   the commit adds. A HIGH finding blocks. A MEDIUM finding prints and
   passes.
3. `tools/test_inventory.py --check`: `docs/TEST_INVENTORY.md` matches
   the tests on disk.
4. `ruff check .`: the Python style rules in `pyproject.toml`.
5. `tools/collect_floor.py`: the whole repo and the offline suites still
   collect, and no suite shrank.
6. The offline suites (`tests/plugins`, `tests/tools`, `tests/helpers`)
   pass. Their run writes to `logs/`, not to `reports/`.

Ten to thirty seconds in all, most of it the last 2. CI runs the same
checks on every push (`docs/CI.md`). To run them by hand:

```
venv\Scripts\python.exe tools/secret_check.py
venv\Scripts\python.exe tools/convention_check.py
venv\Scripts\python.exe tools/test_inventory.py --check
venv\Scripts\python.exe -m ruff check .
venv\Scripts\python.exe tools/collect_floor.py
venv\Scripts\python.exe -m pytest tests/plugins tests/tools tests/helpers --html=logs/scratch.html
```

The recovery for each check that fails:

| Check | What you do |
|-------|-------------|
| Secret | Remove the value from the staged line. Never commit `.env`. |
| Conventions | Correct the line. The message names the rule and the fix. |
| Inventory | `venv\Scripts\python.exe tools/test_inventory.py` writes the page again. Commit it. |
| Ruff | `venv\Scripts\python.exe -m ruff check --fix .` for the safe fixes, then correct the rest by hand. |
| Collect floor | If you removed tests on purpose, `venv\Scripts\python.exe tools/collect_floor.py --update` and say why in the commit message. If you did not, a merge lost files. Find them. |
| Offline suites | Run the same command and read the failure. |

The `commit-msg` hook refuses a message that carries an attribution or a
co-author trailer. Write what the change does and why, nothing else.

`git config core.hooksPath tools/hooks` points git at the tracked hooks,
once per clone. A change to a hook then reaches you with the next pull.

## 9. Quick fixes

| Symptom | Cause and fix |
|---------|---------------|
| "Another test run is already active" | A run holds the lock. Wait for it. If it is dead: `venv\Scripts\python.exe tools/run_lock.py release --env qa --force` |
| `[AUTH] Cached session unusable` then a fresh login | Normal. The cached session expired and the suite logged in again |
| "The camera failed to load" in a screenshot | The server's stream failed, not the test. The page objects click the refresh link once. A stream that stays down fails loud |
| The browser never appears | Add `--headed` |
| No tests collected | The file must be under `tests/` and be named `test_*.py`. Tests marked `destructive` need `--run-destructive` |
| A site or camera name is not found | The server renamed it. Update `config/env/qa.py`. See `docs/FAILURE_TRIAGE.md` |
| `reports/report.html` looks stale | The run used `--html=<other path>`. The archive under `reports/runs/` has every run |
| `[TRACE] Could not finalize trace` or `[VIDEO] Could not finalize video`, or a failed test has no trace, video or screenshot | The file path is too long. Windows refuses a path past 260 characters unless long paths are on. Enable them (registry key `HKLM\SYSTEM\CurrentControlSet\Control\FileSystem`, value `LongPathsEnabled` = 1, needs admin) or clone the repo closer to the drive root |
| The livestream tests skip on Linux | Chrome on Linux has no software H.265 decoder. See `docs/LINUX_H265.md` |
| Leftover `AutoTest` data on the server | `venv\Scripts\python.exe tools/tenant_cleanup.py` lists it. `--apply` deletes it |

## 10. Read next

1. `README.md`: what the repo is and the day-one walkthrough
2. `docs/CONVENTIONS.md`: how we write tests and page objects
3. `docs/FAILURE_TRIAGE.md`: how to chase a failure
4. `docs/QA_THINGS_TO_KNOW.md`: the facts the app taught us
5. `docs/PARALLEL_EXECUTION.md`: before you use `-n`
6. `docs/QA_TOUCH_INTEGRATION.md`: result uploads, if the team uses QA Touch
7. `docs/ARCHIVE.md`: what left the main branch, and how to get it back
