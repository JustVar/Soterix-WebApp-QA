# Playwright Soterix QA

End-to-end test suite for **NexaiQ-Core** (Soterix's cloud video platform), with built-in result reporting to QA Touch and auto-bug filing into Jira.

- **Framework:** Playwright (Python) + pytest + pytest-playwright
- **Targets:** `qa`, `stage`, `prod` environments, customer or partner app type
- **Test management:** QA Touch (project key `JlW1`)
- **Bug tracking:** Jira (project key `NC`)
- **~502 tests** across UI and API, with `legacy/` and `legacy-selenium-tests/` excluded from CI

## Quick Setup

Prereqs: Python 3.11+, Git. (Node.js not required - the Playwright browsers installer is bundled with the Python package.)

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

Copy the env template and fill in secrets:

```powershell
copy .env.template .env
# edit .env: set AUTO_USER, AUTO_PASSWORD, QATOUCH_API_KEY, JIRA_API_TOKEN, etc.
```

## Environment Config

| Var | Required | Purpose |
|---|---|---|
| `ENV` | yes | `qa` \| `stage` \| `prod` - selects `config/env/{name}.py` |
| `APP_TYPE` | no | `customer` (default) \| `partner` - appends `_pat` to module path |
| `AUTO_USER` / `AUTO_PASSWORD` | yes | Automation credentials |
| `QATOUCH_API_KEY` / `QATOUCH_DOMAIN` | yes | QA Touch API auth |
| `QATOUCH_PROJECT_ID` | no | Defaults to `JlW1` (NexaiQ-Core) |
| `QATOUCH_SMOKE_TEMPLATE_KEY` / `QATOUCH_SANITY_TEMPLATE_KEY` | no | Templates cloned per execution (defaults: `vaXdn` / `zvXPw`) |
| `QATOUCH_USE_PLAYWRIGHT_ENDPOINT` | no | `1` to send results with `execution_time` + failure screenshots via the new Playwright endpoint |
| `QATOUCH_CAPTURE_SCREENSHOTS` | no | `0` to disable failure-screenshot capture (only relevant when Playwright endpoint is on) |
| `JIRA_URL` / `JIRA_EMAIL` / `JIRA_API_TOKEN` | yes (for bug filing) | Jira basic auth |
| `JIRA_PROJECT_KEY` | yes (for bug filing) | Defaults to `NC` |
| `BUG_CREATION_ENABLED` | no | `true` to file real bugs. Default `false` keeps the bug filer in dry-run |

See `.env.template` for the complete list with examples.

## Running Tests

### Preferred entry point - full pipeline

```powershell
# Clone the smoke template run in QA Touch, execute pytest, upload results, file Jira bugs on failure
python tools/run_suite.py smoke

# Sanity, targeting stage
python tools/run_suite.py sanity --env stage

# Pass extra pytest args through
python tools/run_suite.py smoke -k test_login --headed

# Dry-run (skip clone + skip pytest, just print what would happen)
python tools/run_suite.py smoke --dry-run

# Skip the post-run bug-filing step
python tools/run_suite.py smoke --no-bug-filing
```

What this does on every invocation:
1. Clones the QA Touch template run (`vaXdn` for smoke, `zvXPw` for sanity) into a **fresh run key** so historical results are preserved.
2. Runs `pytest -m <suite> --qatouch-upload --qatouch-run <new_key>`.
3. The reporter plugin uploads pass/fail to QA Touch and writes per-nodeid outcomes to `logs/last_run_results.json`.
4. Post-run, `run_suite.py` updates `flaky_tests.json` and feeds failed nodeids to `smart_jira_bug_creator.multi_gate_validation()`. The only gate is env health; every other failure becomes a Jira bug directly with QA Touch RTM linkage (label + remote link to the case).
5. Whole bug-filing step is gated by `BUG_CREATION_ENABLED=true`. Until that's set, the filer dry-runs and returns fake `AUTO-XXXX` issue dicts so you can inspect the payload.

### Raw pytest (no orchestration)

```powershell
pytest tests/api/smoke/ -v                 # API smoke tests
pytest -m smoke                            # by marker
pytest -m "admin and not slow"             # combined markers
pytest tests/ui/login/test_login_valid.py -v --headed
pytest --qatouch-upload --qatouch-run vaXdn   # upload to an existing run
```

### Verification mode (QA reviewer flow)

```powershell
# Captures per-step screenshots into verification_output/screenshots/
pytest --headed --slowmo 300 --verify-mode -k "test_export_clip"

# Interactive: pauses after each step for QA to approve/flag/quit
pytest --headed --slowmo 300 --verify-mode --step-review -k "test_export_clip"
```

## Project Structure

```
conftest.py                # Root fixtures (browser, auth, env, API clients)
pytest.ini                 # 51 markers; norecursedirs excludes legacy
.env / .env.template       # Per-user secrets (gitignored) / template
config/
├── base_config.py         # ENV resolution + APP_TYPE
├── env/{qa,stage,prod}.py # Environment-specific configs
├── qatouch_case_mapping.json  # nodeid -> QA Touch case_key
├── jira_field_mapping.py  # QA Touch -> Jira Bug field mapping
└── qatouch_snapshots/     # Historical case snapshots
tests/
├── ui/                    # 43 test files organized by module
│   ├── admin/   chats/   c2c/   events/   insights/   licenses/
│   ├── login/   maps/    media/  notifications/   search/
│   ├── sequences/   views/
├── api/smoke/             # 5 files, ~16 API smoke tests
├── shared/
│   ├── pages/             # 15 Page Object Models
│   ├── api_clients/       # 9 API client helpers (extend BaseAPIClient)
│   ├── helpers/           # Role helper
│   └── schemas/           # JSON schemas for API response validation
├── steps/                 # JSON sidecars defining per-step verification text
└── data/                  # Test data files
plugins/
├── qatouch_reporter.py    # --qatouch-upload --qatouch-run <KEY>
└── verification_runner.py # --verify-mode + --step-review
tools/                     # 30+ utility scripts
├── run_suite.py           # PREFERRED ENTRY: clone + pytest + bug filing
├── qatouch_*.py           # QA Touch CRUD, scaffolding, audits, analytics
├── smart_jira_bug_creator.py  # Auto-file Jira bugs on failure with RTM linkage
├── update_failure_history.py  # JUnit XML -> flaky_tests.json (used in CI paths)
├── discover_*.py          # API / camera / Jira discovery scripts
└── email_client.py        # Azure OAuth email sender
docs/                      # Setup guides, integration plans, maintenance reminders
```

`legacy/` and `legacy-selenium-tests/` exist for reference but are excluded from test collection via `pytest.ini`'s `norecursedirs`.

## QA Touch Integration

- **Case mapping:** every pytest test maps to a QA Touch case via either `config/qatouch_case_mapping.json` (nodeid -> case_key) or the `@pytest.mark.qatouch("KEY")` marker on the test itself. Mappings are kept current via `tools/qatouch_mapper.py` and `tools/qatouch_sync_check.py`.
- **Run cloning:** `tools/run_suite.py` clones the per-suite template run on every invocation, so smoke run #1 and smoke run #2 land in distinct QA Touch run records and history is queryable.
- **Result upload:** the `qatouch_reporter` pytest plugin batches all results into a single API call at session-end. Two endpoints supported:
  - **Legacy (default):** `PATCH /api/v1/testRunResults/status/multiple` - status only.
  - **Playwright (opt-in via `QATOUCH_USE_PLAYWRIGHT_ENDPOINT=1`):** `POST /api/v1/testRunResults/playwright/status/multiple` - adds `execution_time` per test and base64-encoded failure screenshots captured live from the Playwright page object.
- **Retry:** 3 attempts with exponential backoff (2s, 4s, 8s). On final failure, results are saved to `logs/upload_failures.json` for manual retry via `tools/retry_uploads.py`.
- **Scaffolding new cases:** `python tools/qatouch_run_manager.py scaffold <NODEID> <MODULE> <TITLE>` or batch via `scaffold-new --dry-run` to scaffold all unmapped tests at once.

## Jira Integration

- **Auto-bug filing:** Playwright failure -> run_suite.py post-run step -> `smart_jira_bug_creator.multi_gate_validation()` -> Jira bug. The bug includes:
  - QA Touch RTM linkage: a `qatouch-<CASE_KEY>` label, a remote link to the QA Touch case URL, and the case key prefixed onto the Bug Overview field. This populates QA Touch's RTM panel when JIRA App 2.0 is enabled on the case.
  - All 8 NC mandatory Bug fields auto-populated from QA Touch test case data (module, steps, expected, actual, environment, severity, build, title) via `config/jira_field_mapping.py`.
- **Single gate:** env-health probe. If `base_url` is unreachable, no bugs file (suppress infrastructure-broken floods). Every other failure becomes a bug directly.
- **Dry-run safety:** `BUG_CREATION_ENABLED=false` (default) returns fake `AUTO-XXXX` issue dicts without touching Jira. Flip to `true` in `.env` when you're ready to file real bugs.
- **Review queue dormant:** the `tools/review_queue.json` + `--review` / `--list` CLI commands still exist but are unreachable from the default flow. Pass `auto_create=False` to `multi_gate_validation` to reinstate the human-disposition gate.

## Step Capture & Verification

Every test wires up the `step_capture` fixture to mark logical steps (one `.mark(n, "description")` call after each action). Two consumers:

1. **JSON sidecars** under `tests/steps/` define the step text + expected outcomes per test.
2. **`--verify-mode`** captures per-step screenshots into `verification_output/screenshots/` for asynchronous QA review.

Convention details + examples in `NOTES.md` under "Step Capture Convention".

## Markers (51 defined in `pytest.ini`)

- **Type:** `smoke`, `sanity`, `regression`, `api`, `ui`
- **Environment:** `env_qa`, `env_stage`, `env_preprod`, `env_prod`
- **Feature:** `admin`, `views_devices`, `events`, `search`, `media`, `maps`, `chats`, `licenses`, `insights`, `notifications`, `sequences`, etc.
- **Meta:** `slow` (>30s), `flaky` (intermittent), `wip` (skip in CI)
- **Mapping:** `qatouch(case_key)` - maps a test to a QA Touch case directly without touching the JSON mapping file

Run examples: `pytest -m smoke`, `pytest -m "admin and not slow"`, `pytest -m "regression and env_stage"`.

## Auth & Session Caching

- `authenticated_page` fixture: loads cached `.auth_state.json` (~2-3s) instead of a full UI login (~65s).
- First run logs in via UI and saves browser storage state; subsequent runs reload + validate it; re-login fires only if the cached state expired.
- API auth: `AuthHelper.login()` prefers OAuth bearer tokens with UI fallback. Tokens are reused across the entire pytest session.

## CI Notes

- `python -m playwright install chromium` must run in CI before pytest.
- All secrets (`AUTO_USER`, `AUTO_PASSWORD`, `QATOUCH_API_KEY`, `JIRA_API_TOKEN`) come from CI secrets, not `.env`.
- Leave `BUG_CREATION_ENABLED` unset in CI until you've validated the bug filer end-to-end with one real failure.
- Lab servers handle the actual smoke/sanity execution; CI is for syntax + smoke validation, not full runs.

## More Documentation

- `NOTES.md` - engineering conventions, page-object patterns, step-capture rules, marker definitions
- `docs/CREDENTIALS_SETUP.md` - credential configuration walkthrough
- `docs/MAINTENANCE_REMINDERS.md` - OAuth expirations, recurring tasks
- `docs/SESSION_CACHING_IMPLEMENTATION.md` - auth state cache details
- `docs/VERIFICATION_WORKFLOW.md` - QA review flow for verification mode
- `IMPLEMENTATION_ROADMAP.md` - historical roadmap; live tracking lives in the workspace `FUTURE_ROADMAP.md`
