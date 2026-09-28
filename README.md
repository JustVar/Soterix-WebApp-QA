# Soterix WebApp QA

## What this repo does

This repo tests the Soterix web application, NexaiQ-Core, through the
browser, the same way a user operates it. It also tests the web pages of the
Camera 2 Cloud cameras in the lab. Each night the tests run on the 2 QA
tenants (`india` and `us`), and a report shows what failed and why.

The API tests are in a different repo, Soterix-API-QA.

## How it works

1. The tests are Python. Playwright operates Google Chrome, and pytest runs
   the tests. Page objects in `tests/shared/pages/` hold the locators, so a
   change in the app is corrected in 1 place.
2. `BOX` in your `.env` selects the tenant. The account and the test data
   (site, camera) come from `config/env/`, not from the tests.
3. Each run keeps its evidence in `reports/runs/<run>/`: a report page
   (`run.html`), a screenshot of each test, and a video and a Playwright
   trace of each failure.
4. A machine in the lab, spartan1, runs all the tests each night and serves
   the reports at `http://10.2.0.2/qa-runs/`.
5. Git hooks and a CI gate check each change without a browser: imports,
   lint, the house conventions and the number of collected tests.
6. The upload of results to QA Touch and the automatic Jira bugs are
   optional and off by default. Today the team reads the report and reports
   the results by hand.

## Start here

- To run something now: `python run.py smoke` runs the smoke suite and
  prints where the report is.
- All commands on 1 page: [docs/COMMAND_SHEET.md](docs/COMMAND_SHEET.md).
- A test failed: [docs/FAILURE_TRIAGE.md](docs/FAILURE_TRIAGE.md).
- What is broken and who owns it: [docs/TEST_REPAIRS.md](docs/TEST_REPAIRS.md).
- Which machine runs the browser, and why: [docs/BROWSER_TOPOLOGY.md](docs/BROWSER_TOPOLOGY.md).
- Concurrency and load work, planned: [docs/CONCURRENCY_PLAN.md](docs/CONCURRENCY_PLAN.md).
- What CI costs and how to move it in-house: [docs/CI_ON_SPARTAN1.md](docs/CI_ON_SPARTAN1.md).
- Before you write a test: [docs/CONVENTIONS.md](docs/CONVENTIONS.md), section "Adding a test".
- The list of all tests, by product and module:
  [docs/TEST_INVENTORY.md](docs/TEST_INVENTORY.md). The README gives no
  counts, because they go stale. `config/collect_floor.json` records the
  number of collected tests, and `tools/collect_floor.py` fails a run that
  collects fewer.

The local folder can still have the old repo name, `playwright-soterix-qa`.

## Quick Setup

Prereqs: Python 3.11+, Git, Google Chrome. The suite drives branded Chrome
(`--browser-channel chrome` in pytest.ini), so Chrome must be installed on
the machine. Playwright's own Chromium is not used and not downloaded.
Node.js is not required.

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
git config core.hooksPath tools/hooks
```

No activation step on purpose: PowerShell's default execution policy
blocks `Activate.ps1`, and a `pip` that is not the venv's installs into the
global Python without a word.
Calling the venv's `python.exe` by path sidesteps both, so every command
in this repo's docs is written that way. Clone near the drive root
(`C:\qa\...`): a deep path pushes Windows past its path cap, git then needs
`-c core.longpaths=true` to clone, and evidence file names get shortened.

The last line turns on the repo's two git hooks (the pre-commit gates and
the commit-message check) for this clone. See docs/COMMAND_SHEET.md.

That is the whole setup. `requirements.txt` pulls in the shared QA pipeline
(`soterix-qa-shared`) for you, over HTTPS, using the same GitHub login your
`git clone` used. You need read access to that repo, which is granted
separately from this one: if pip reports a 404, ask for it rather than
hunting for a token.

`requirements.txt` pins exact versions (playwright 1.62.0, pytest-playwright
0.9.0), so a fresh clone installs the same set the suite was verified against.
Upgrade deliberately: change the pin, run a suite, then commit.

`requirements.txt` pins the shared pipeline to a TAG, so everyone runs the
same reporter and the same client. `plugins/` and `tools/` here are thin
shims over it, which is why nothing collects without it.

**Only if you need to change the shared package**, clone it beside this repo
and install it editable. That overrides the pinned copy until you reinstall,
so you can test a package change here before tagging it:

```powershell
cd ..
git clone https://github.com/Soterix-Systems/SOTERIX-QA-SHARED.git soterix-qa-shared
cd playwright-soterix-qa
pip install -e ../soterix-qa-shared
```

Most people never need this.

Copy the env template and fill in the automation credentials:

```powershell
copy .env.template .env
# edit .env: BOX names the tenant (india by default); fill that box's pair,
# QA_INDIA_USER and QA_INDIA_PASSWORD - that's all you need to run tests
```

## Environment Config

Only these are needed to run tests:

| Var | Required | Purpose |
|---|---|---|
| `ENV` | no (defaults to `qa`) | `qa` \| `stage` \| `prod` - selects `config/env/{name}.py` |
| `APP_TYPE` | no | `customer` (default) \| `partner` - appends `_pat` to module path |
| `BOX` + `QA_<BOX>_USER` / `QA_<BOX>_PASSWORD` | yes | The tenant to test and its account pair (`login_data` in conftest.py). The legacy `QA_USER` / `QA_PASSWORD` pair signs in only when `BOX` is unset |

The QA Touch and Jira variables (`QATOUCH_*`, `JIRA_*`, `BUG_CREATION_ENABLED`) are only
read by the optional integrations and can be left unset - see
[Optional integrations](#optional-integrations-work-in-progress).

See `.env.template` for the complete list with examples.

## Running Tests

```powershell
# API smoke tests moved to the Soterix-API-QA repo
pytest -m smoke                            # by marker
pytest -m "admin and not slow"             # combined markers
pytest tests/ui/login/test_login_valid.py -v --headed
```

Each run keeps its evidence in its own folder, `reports/runs/<run>/`. Open
`reports/runs/<run>/run.html` first. It gives the verdict in 1 sentence and
shows the failures first, each with its error, screenshots, video and trace
command. `reports/runs/index.html` lists the runs on your machine, newest
first. The nightly runs are at `http://10.2.0.2/qa-runs/`.

`reports/report.html` and `reports/artifacts/` hold the newest run only. The
next run writes over them. The run folder keeps a copy, so you do not need
to save a trace by hand.

To find the cause of a failure, start at the table in
[docs/FAILURE_TRIAGE.md](docs/FAILURE_TRIAGE.md).

To email the HTML report to someone, see `docs/EMAIL_REPORTS.md`.

### Parallel Runs

`pytest tests/ui -n 4` runs 4 workers. `--dist loadgroup` in pytest.ini
keeps every module that writes tenant state (its `xdist_group` mark) on one
worker and serialises the searches. Never add your own `--dist`: it
overrides the ini and the run refuses to start. Read
[docs/PARALLEL_EXECUTION.md](docs/PARALLEL_EXECUTION.md) before using `-n`.

### Verification Mode (QA Reviewer Flow)

```powershell
# Captures per-step screenshots into verification_output/screenshots/
pytest --headed --slowmo 300 --verify-mode -k "test_export_clip"
```

Add `--step-review` to a headed `--verify-mode` run to review a test step
by step: the terminal asks for a verdict after each step, and the verdicts
go into the evidence JSON. The contract is in
`docs/VERIFICATION_WORKFLOW.md`.

## Project Structure

```
conftest.py                # Root fixtures (browser, auth, env, API clients)
pytest.ini                 # 65 markers; norecursedirs excludes legacy
.env / .env.template       # Per-user secrets (gitignored) / template
config/
├── base_config.py         # ENV resolution + APP_TYPE
├── env/{qa,stage,prod}.py # Environment-specific configs
├── qatouch_case_mapping.json  # nodeid -> QA Touch case_key
├── jira_field_mapping.py  # QA Touch -> Jira Bug field mapping
└── qatouch_snapshots/     # Historical case snapshots
tests/
├── ui/                    # NexaiQ-Core: 52 test files by module (config/products.py)
│   ├── admin/ (incl. LPR)   chats/   events/   insights/
│   ├── licenses/   login/   maps/    media/   notifications/
│   ├── search/   sequences/   views/
├── c2c/                   # Camera 2 Cloud: 7 files against the cameras' own web UIs
├── shared/
│   ├── pages/             # 17 Page Object Models
│   ├── helpers/           # Role helper
│   └── schemas/           # JSON schemas for API response validation
├── steps/                 # JSON sidecars defining per-step verification text
└── data/                  # Test data files
plugins/
├── qatouch_reporter.py    # --qatouch-upload --qatouch-run <KEY>
└── verification_runner.py # --verify-mode + --step-review
tools/                     # about 70 utility scripts (one-offs under tools/archive/)
├── tools/run_suite.py     # WIP orchestration: clone + pytest + bug filing
├── qatouch_*.py           # WIP: QA Touch CRUD, scaffolding, audits, analytics
├── smart_jira_bug_creator.py  # WIP: auto-file Jira bugs on failure
├── update_failure_history.py  # JUnit XML -> flaky_tests.json (used in CI paths)
├── discover_*.py          # API / camera / Jira discovery scripts
├── send_test_report.py    # Email the HTML report (see docs/EMAIL_REPORTS.md)
└── email_client.py        # Azure OAuth email sender
docs/                      # Setup guides, integration plans, maintenance reminders
```

`legacy-selenium-tests/` exists for reference but is excluded from test collection via `pytest.ini`'s `norecursedirs`, which also still names `legacy/` from before that directory was removed.

## Optional Integrations (Work in Progress)

> **Not part of the current workflow.** Everything below is built but still being fine-tuned.
> None of it runs unless you explicitly opt in - a plain `pytest` run never contacts QA
> Touch or Jira. Results are reported manually today.

### QA Touch Result Upload - WIP

Opt in with `pytest --qatouch-upload --qatouch-run <KEY>`, or run the orchestrated
pipeline with `python tools/run_suite.py smoke` (clones the per-suite template into a
fresh run key so history is preserved, and `--dry-run` prints what would happen).

- **Case mapping** lives in `config/qatouch_case_mapping.json` (nodeid -> case_key). The
  reporter also honours a `@pytest.mark.qatouch("KEY")` marker, but **the test files
  deliberately carry none** - the whole QA team runs these scripts and QA Touch reporting
  is not part of their flow, so mapping is kept out of test code entirely. Add new
  mappings to the JSON, never to a test. Checked with `tools/qatouch_mapper.py` and
  `tools/qatouch_sync_check.py`.
- **Mapping coverage is currently minimal**, and affects reporting only. An unmapped test
  runs and passes or fails as normal. Only its upload is skipped.
- **Two endpoints:** legacy `PATCH .../status/multiple` (status only, default), or the
  Playwright endpoint via `QATOUCH_USE_PLAYWRIGHT_ENDPOINT=1` (adds per-test
  `execution_time` and failure screenshots).
- **Retry:** 3 attempts with exponential backoff. On final failure results land in
  `logs/upload_failures.json` for retry via `tools/retry_uploads.py`.

### Automatic Jira Bug Filing - WIP, Off by Default

Gated by `BUG_CREATION_ENABLED`, which defaults to `false`. In that state the filer
dry-runs and returns fake `AUTO-XXXX` issue dicts so payloads can be inspected without
touching Jira. Do not flip it to `true` until the flow has been validated end to end.

- Failures flow from `run_suite.py` into `smart_jira_bug_creator.multi_gate_validation()`.
- Bugs carry QA Touch RTM linkage (a `qatouch-<CASE_KEY>` label + remote link) and the 8
  mandatory NC Bug fields via `config/jira_field_mapping.py`.
- Only suppression is an env-health probe: if `base_url` is unreachable the run is treated
  as infrastructure-broken and nothing is filed.
- The step is opt-in: it runs only with `--file-bugs` on `tools/run_suite.py`. Without the flag, no bug is filed.
- The review queue (`tools/review_queue.json`, `--review` / `--list`) still exists but is
  unreachable from the default flow. Pass `auto_create=False` to reinstate the
  human-disposition gate.

## Step Capture & Verification

Tests may opt into the `step_capture` fixture to mark logical steps (one `.mark(n, "description")` call after each action). Approximately 20 test files use it. It is optional, and a test without it runs normally. Two consumers:

1. **JSON sidecars** under `tests/steps/` define the step text + expected outcomes per test.
2. **`--verify-mode`** captures per-step screenshots into `verification_output/screenshots/` for asynchronous QA review - only for tests that request the fixture.

Convention details + examples: `docs/CONVENTIONS.md` under Step capture.

## Markers (64 Defined in `pytest.ini`)

- **Type:** `smoke`, `sanity`, `regression`, `api`, `ui`
- **Feature:** `admin`, `views_devices`, `events`, `search`, `media`, `maps`, `chats`, `licenses`, `insights`, `notifications`, `sequences`, etc.
- **Meta:** `slow` (>30s), `intermittent` (fails now and then. Do not use `flaky`, which reruns the test), `wip` (skip in CI)
- **Mapping:** `qatouch(case_key)` / `qatouch_project(project_key)` - recognised by the reporter but intentionally unused in the shared test files. Keep mappings in `config/qatouch_case_mapping.json`

Run examples: `pytest -m smoke`, `pytest -m "admin and not slow"`.

## Auth & Session Caching

- `authenticated_page` fixture: loads cached `.auth_state.json` (~2-3s) instead of a full UI login (~65s).
- The first run logs in through the UI and saves the browser storage state. Later runs load it and validate it. A new login occurs only if the cached state expired.
- Under pytest-xdist each worker gets its own cache file (`.auth_state.<worker>.json`), so workers never race on one file.
- The fixture also records a Playwright trace for every test and keeps it only on failure - this is what makes the traces in `reports/artifacts/` work for the ~90% of UI tests that use `authenticated_page` (the plugin's `--tracing` flag only covers its own `page` fixture).
- API auth: `AuthHelper.login()` prefers OAuth bearer tokens with UI fallback. Tokens are reused across the entire pytest session.

## Linting

Configured via [`pyproject.toml`](pyproject.toml). Ruff is the only linter - it covers what flake8 / isort / pyupgrade / pep8 do separately, plus pytest-style checks via the `PT` rule family. Pre-tuned with per-file ignores so tests, plugins, and CLI tools don't trigger false positives for their normal idioms.

```powershell
# Check the whole repo
python -m ruff check .

# Auto-fix safe issues
python -m ruff check --fix .

# Format
python -m ruff format .

# Focus on a single area
python -m ruff check tests/ui/login
python -m ruff check plugins/
```

The rule set knows pytest and Playwright. `PT` enforces the fixture conventions. `BLE` finds a blind `except Exception` in test code, where it usually hides a real problem. `T20` finds a `print()` left in a test body. Tools and discovery scripts keep their `print()` calls through a per-file ignore. The repo has 0 findings, and `tools/lint_baseline.py` fails the commit and the CI gate on a new one.

Ruff cannot see the house testing rules, so a second gate does:

```powershell
# Check the lines you added since HEAD against docs/CONVENTIONS.md
python tools/convention_check.py

# Whole-repo standing debt report
python tools/convention_check.py --all
```

HIGH findings (uncommented sleeps, QA Touch markers in test files) block
the commit. MEDIUM findings (absolute count oracles, `img[src]` icon
guesses, hardcoded tenant names) warn. The default mode diffs against
HEAD, so debt in files you did not touch never blocks you. Run both
gates before every commit.

## CI Notes

- Google Chrome must be on the runner before pytest: the suite drives branded Chrome (`--browser-channel chrome`). The smoke workflow installs it with `python -m playwright install chrome`.
- The smoke workflow signs in with the legacy `QA_USER` / `QA_PASSWORD` secrets (no `BOX`), from CI secrets, not `.env`.
- Leave `BUG_CREATION_ENABLED` unset in CI - the bug filer is still WIP and must not file real bugs from an automated run.
- spartan1 runs the full suite each night (`deploy/spartan1/README.md`). CI checks each change without a browser. It does not run the suite.

## More Documentation

- `docs/QA_THINGS_TO_KNOW.md` - patterns and workarounds for this app's UI: each entry gives the problem, the cause and the fix
- `docs/CI.md` - the checks that run on each push, and what to do when one fails
- `deploy/spartan1/README.md` - the nightly machine: access, the log, how to get a trace, how to install a change
- `docs/RUN_WORKFLOWS.md` - what happens after a run: the pane of glass, triage, hosting plan
- `docs/AUDIT_FINDINGS.md` - the adversarial audit: 30 findings, each fixed or deferred
- `docs/CONVENTIONS.md` - engineering conventions: page objects, waits, step capture, markers, adding tests
- `docs/FAILURE_TRIAGE.md` - reading failure traces (GUI + terminal)
- `docs/TEAM_CHANGES.md` - reviewing teammates' script changes before refactors (`tools/team_changes.py`)
- `docs/TEST_REPAIRS.md` - the register of what is broken, with an owner and a next action for each open item. Work it before you write new tests
- `docs/PARALLEL_EXECUTION.md` - pytest-xdist status, risks, experiment log
- `docs/STYLE.md` - writing style for docs, comments, and commit messages
- `docs/CREDENTIALS_SETUP.md` - credential configuration walkthrough
- `MAINTENANCE_REMINDERS.md` - OAuth expirations, recurring tasks
- `docs/CONVENTIONS.md` - auth state cache behaviour (the original write-up is archived at `docs/archive/SESSION_CACHING_IMPLEMENTATION.md`)
- `docs/VERIFICATION_WORKFLOW.md` - QA review flow for verification mode
- `docs/EMAIL_REPORTS.md` - emailing the HTML run report via Microsoft Graph
- API endpoints, surfaces, testing notes and the Bruno guide live in the API repo, `Soterix-API-QA/docs/`, since the split of 08/07/2026
- QA roadmap: `dashboards/soterix-internal-dashboards/docs/QA_ROADMAP.md` (the single source of truth for all QA work)
