# Soterix WebApp QA

**Start here:** `python run.py smoke` runs the smoke suite and prints where the report is. [docs/COMMAND_SHEET.md](docs/COMMAND_SHEET.md) has every command to install, run, and read results, on one page.

End-to-end UI test suite for **NexaiQ-Core** (Soterix's cloud video platform).
The repo was renamed from `playwright-soterix-qa` on 2026-08-07; the local
folder name may still be the old one.

- **Framework:** Playwright (Python) + pytest + pytest-playwright
- **Targets:** `qa`, `stage`, `prod` environments, customer or partner app type
- **435 product test functions in 60 suite files** (09/18/2026): 402 NexaiQ-Core tests under `tests/ui/` and 33 Camera 2 Cloud tests under `tests/c2c/` (the cameras' own web UIs, run serially against the lab registry `tests/data/c2c_cameras.yaml`). pytest collects them as 762 items: the Core tests carry the browser parameter (432), and the c2c tests parametrize over the 10 enabled cameras into 330. The other 533 collected items are pins for the framework's own tools and plugins (`tests/tools`, `tests/plugins`, `tests/helpers`); a further 669 pins live in the shared package. Whole repo: 1295. API tests live in Soterix-API-QA; `legacy/` and `legacy-selenium-tests/` are excluded from collection. `config/collect_floor.json` records the counts and `tools/collect_floor.py` fails a run that collects fewer; a drop needs a reason in the commit message. `docs/TEST_INVENTORY.md` lists every product test by product and module, with its growth week by week since 02/2026 (`history/test_counts.jsonl`, appended by `tools/test_inventory.py --record`).

## How We Run Today

**Run the tests, read the report, report results manually.** That's the current process.

```powershell
pytest -m smoke                 # or any subset - see Running Tests below
```

QA Touch result upload and automatic Jira bug filing are **built but not in active use.**
They are opt-in, off by default, and still being fine-tuned - treat them as
work-in-progress rather than part of the workflow. Nothing in the default test run
touches QA Touch or Jira. See [Optional integrations](#optional-integrations-work-in-progress)
if you're working on them.

## Quick Setup

Prereqs: Python 3.11+, Git, Google Chrome. The suite drives branded Chrome
(`--browser-channel chrome` in pytest.ini), so Chrome must be installed on
the machine; Playwright's own Chromium is not used and not downloaded.
Node.js is not required.

```powershell
python -m venv venv
venv\Scripts\python.exe -m pip install --upgrade pip
venv\Scripts\python.exe -m pip install -r requirements.txt
git config core.hooksPath tools/hooks
```

No activation step on purpose: PowerShell's default execution policy
blocks `Activate.ps1`, and a `pip` that is not the venv's installs into the
global Python without a word (measured on a fresh clone, 09/18/2026).
Calling the venv's `python.exe` by path sidesteps both, so every command
in this repo's docs is written that way. Clone near the drive root
(`C:\qa\...`): a deep path pushes Windows past its path cap, git then needs
`-c core.longpaths=true` to clone, and evidence file names get shortened.

The last line turns on the repo's two git hooks (the pre-commit gates and
the commit-message check) for this clone; see docs/COMMAND_SHEET.md.

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
| `BOX` + `QA_<BOX>_USER` / `QA_<BOX>_PASSWORD` | yes | The tenant to test and its account pair (`login_data` in conftest.py); the legacy `QA_USER` / `QA_PASSWORD` pair signs in only when `BOX` is unset |

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

An HTML report is written to `reports/report.html` on every run (configured in
`pytest.ini`). Open it, review pass/fail, and report results manually.

Every failed test also saves a Playwright trace (DOM snapshots per action,
network, console, timeline) to `reports/artifacts/`. View one with
`playwright show-trace <file>` or inspect it from the terminal with
`playwright trace`. The folder is cleared at the start of each run, so copy a
trace out before the next run if you want to keep it. Full guide:
[docs/FAILURE_TRIAGE.md](docs/FAILURE_TRIAGE.md).

To email the HTML report to someone, see `docs/EMAIL_REPORTS.md`.

### Parallel Runs (Experimental)

`pytest tests/ui -n 4` runs four workers; pytest.ini's `--dist loadgroup`
keeps every module that writes tenant state (its `xdist_group` mark) on one
worker and serialises the searches. Never add your own `--dist`: it
overrides the ini and the run refuses to start. Read
[docs/PARALLEL_EXECUTION.md](docs/PARALLEL_EXECUTION.md) before using `-n`.

### Verification Mode (QA Reviewer Flow)

```powershell
# Captures per-step screenshots into verification_output/screenshots/
pytest --headed --slowmo 300 --verify-mode -k "test_export_clip"
```

> **Rebuilt (2026-08-08):** the interactive `--step-review` flag was lost
> in the July branch reconciliation and has been rebuilt in
> `plugins/verification_runner.py` from the contract in
> `docs/VERIFICATION_WORKFLOW.md`: per-step terminal prompts, safety
> guards, `step_verdicts` in the evidence JSON, and the headed step
> overlay. Add it to a headed `--verify-mode` run to review step by step.

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
fresh run key so history is preserved; `--dry-run` prints what would happen).

- **Case mapping** lives in `config/qatouch_case_mapping.json` (nodeid -> case_key). The
  reporter also honours a `@pytest.mark.qatouch("KEY")` marker, but **the test files
  deliberately carry none** - the whole QA team runs these scripts and QA Touch reporting
  is not part of their flow, so mapping is kept out of test code entirely. Add new
  mappings to the JSON, never to a test. Checked with `tools/qatouch_mapper.py` and
  `tools/qatouch_sync_check.py`.
- **Mapping coverage is currently minimal**, and affects reporting only. An unmapped test
  runs and passes/fails exactly as normal; only its upload is skipped.
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
- `--no-bug-filing` skips the step entirely.
- The review queue (`tools/review_queue.json`, `--review` / `--list`) still exists but is
  unreachable from the default flow; pass `auto_create=False` to reinstate the
  human-disposition gate.

## Step Capture & Verification

Tests may opt into the `step_capture` fixture to mark logical steps (one `.mark(n, "description")` call after each action). Roughly 20 test files currently use it; it is optional, and a test without it runs normally. Two consumers:

1. **JSON sidecars** under `tests/steps/` define the step text + expected outcomes per test.
2. **`--verify-mode`** captures per-step screenshots into `verification_output/screenshots/` for asynchronous QA review - only for tests that request the fixture.

Convention details + examples: `docs/CONVENTIONS.md` under Step capture.

## Markers (64 Defined in `pytest.ini`)

- **Type:** `smoke`, `sanity`, `regression`, `api`, `ui`
- **Feature:** `admin`, `views_devices`, `events`, `search`, `media`, `maps`, `chats`, `licenses`, `insights`, `notifications`, `sequences`, etc.
- **Meta:** `slow` (>30s), `intermittent` (fails now and then; never `flaky`, which reruns), `wip` (skip in CI)
- **Mapping:** `qatouch(case_key)` / `qatouch_project(project_key)` - recognised by the reporter but intentionally unused in the shared test files; keep mappings in `config/qatouch_case_mapping.json` instead

Run examples: `pytest -m smoke`, `pytest -m "admin and not slow"`.

## Auth & Session Caching

- `authenticated_page` fixture: loads cached `.auth_state.json` (~2-3s) instead of a full UI login (~65s).
- First run logs in via UI and saves browser storage state; subsequent runs reload + validate it; re-login fires only if the cached state expired.
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

The Playwright/pytest-aware rule set is the headline difference from a generic ruff config: `PT` enforces fixture conventions (`@pytest.fixture` not `@pytest.fixture()`, parametrize value style, etc.), `BLE` flags blind `except Exception` in test code where it usually hides real problems, and `T20` catches leftover `print()` statements in test bodies. Tools and discovery scripts keep their `print()` usage by per-file-ignore. New code should aim for zero new lints; existing remaining issues are tracked for incremental cleanup.

Ruff cannot see the house testing rules, so a second gate does:

```powershell
# Check the lines you added since HEAD against docs/CONVENTIONS.md
python tools/convention_check.py

# Whole-repo standing debt report
python tools/convention_check.py --all
```

HIGH findings (uncommented sleeps, QA Touch markers in test files) block
the commit; MEDIUM findings (absolute count oracles, `img[src]` icon
guesses, hardcoded tenant names) warn. The default mode diffs against
HEAD, so debt in files you did not touch never blocks you. Run both
gates before every commit.

## CI Notes

- Google Chrome must be on the runner before pytest: the suite drives branded Chrome (`--browser-channel chrome`); the smoke workflow installs it with `python -m playwright install chrome`.
- The smoke workflow signs in with the legacy `QA_USER` / `QA_PASSWORD` secrets (no `BOX`), from CI secrets, not `.env`.
- Leave `BUG_CREATION_ENABLED` unset in CI - the bug filer is still WIP and must not file real bugs from an automated run.
- Lab servers handle the actual smoke/sanity execution; CI is for syntax + smoke validation, not full runs.

## More Documentation

- `docs/RUN_WORKFLOWS.md` - what happens after a run: the pane of glass, triage, hosting plan
- `docs/AUDIT_FINDINGS.md` - the 2026-09 adversarial audit: 30 findings with disposition (fixed/deferred)
- `docs/CONVENTIONS.md` - engineering conventions: page objects, waits, step capture, markers, adding tests
- `docs/FAILURE_TRIAGE.md` - reading failure traces (GUI + terminal)
- `docs/TEAM_CHANGES.md` - reviewing teammates' script changes before refactors (`tools/team_changes.py`)
- `docs/TEST_REPAIRS.md` - register of tests needing repair, reinvestigation, or a verify run; work it before writing new tests
- `docs/PARALLEL_EXECUTION.md` - pytest-xdist status, risks, experiment log
- `docs/STYLE.md` - writing style for docs, comments, and commit messages
- `docs/CREDENTIALS_SETUP.md` - credential configuration walkthrough
- `MAINTENANCE_REMINDERS.md` - OAuth expirations, recurring tasks
- `docs/CONVENTIONS.md` - auth state cache behaviour (the original write-up is archived at `docs/archive/SESSION_CACHING_IMPLEMENTATION.md`)
- `docs/VERIFICATION_WORKFLOW.md` - QA review flow for verification mode
- `docs/EMAIL_REPORTS.md` - emailing the HTML run report via Microsoft Graph
- `docs/API_ENDPOINTS.md` - REST endpoint catalog + coverage status
- `docs/BRUNO_GUIDE.md` - interactive API exploration with Bruno
- QA roadmap: `dashboards/soterix-internal-dashboards/docs/QA_ROADMAP.md` (single source of truth for all QA work; split from the old unified roadmap 2026-08-08)
