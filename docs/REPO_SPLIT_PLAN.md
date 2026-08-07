# Repo Split & Rename Plan

**Status: EXECUTED 2026-08-07.** Kept as the record of what moved and why.
The API suite now lives at https://github.com/Soterix-Systems/Soterix-API-QA.

## Decisions (locked)

| Decision | Choice |
|---|---|
| Current repo renames to | **`Soterix-WebApp-QA`** (webapp UI automation + manual test cases) |
| New API repo | **`Soterix-API-QA`** (all API testing: `/v-apiserver` + `/v-integration-api`) |
| API repo history | **Fresh start** - files copied in, one initial commit; old history stays viewable in the webapp repo |
| Remotes | Soterix-Systems is the canonical org for both repos |
| QA Touch | Single project `JlW1` for both repos; case mappings live only in each repo's `config/qatouch_case_mapping.json` (never in test files) |
| Browser policy | `Soterix-API-QA` has **no Playwright dependency at all** - API auth is pure HTTP (see `docs/API_SURFACES.md`) |

## Why (one paragraph, for future readers)

API tests used to fall back to driving a headed browser because the API login
path was broken (wrong endpoint, unhashed password - fixed 2026-08-05/06, see
`docs/API_SURFACES.md`). With that fixed, the API suite is verified to run with
zero browser launches and zero Playwright imports. Splitting gives API testing
its own repo with a seconds-long dependency install, no interference with the
webapp automation, and a clean home for the new integration-API surface. The
rename makes the webapp repo's scope obvious.

---

## Phase 0 - Freeze a known-good baseline

*Local and remote heads are in sync at `cf4238a` with one pending change set
on top.*

1. Review and commit the pending changes as logical commits:
   - browser-free API auth (`auth_helper.py`, `conftest.py`)
   - dead-host purge + doc corrections (docs/, tools/, `config/environments.yaml`)
   - `hardware-lab` prod box (`config/env/prod.py`)
   - this plan + `docs/API_SURFACES.md`
2. Push. Verify `git rev-parse HEAD origin/main` returns one SHA.
3. Tag the state: `git tag pre-split && git push origin --tags`.

**Gate:** sync confirmed, tag pushed.

---

## Phase 1 - Build `Soterix-API-QA` locally

Create `qa/Soterix-API-QA/` beside the current repo. Copy per the manifest,
restructure, then validate before anything touches GitHub.

### Manifest - what moves in (copies; source repo untouched until Phase 3)

| From (current repo) | To (`Soterix-API-QA`) | Notes |
|---|---|---|
| `tests/api/smoke/*` | `tests/smoke/` | **except** `test_qatouch_reporter.py` (plugin unit test - stays with the webapp repo's plugin) |
| `tests/shared/api_clients/*` | `api_clients/` | flatten; update imports `tests.shared.api_clients.X` -> `api_clients.X` across all files |
| `tests/shared/schemas/` | `schemas/` | OpenAPI specs + response schemas; update `base_api_client.load_schema()` path |
| `config/base_config.py`, `config/env/*.py` | same paths | duplicated deliberately (small, slow-drifting; a shared package = a third repo + install plumbing, rejected) |
| `config/qatouch_case_mapping.json` | same path | **only the 13 entries keyed by `tests/api/...`**, re-keyed to the new paths |
| `qa/doc_registry.yaml` | same path | only the "Section I. API" entries, re-pathed |
| `plugins/qatouch_reporter.py` (+ its unit test) | same layout | each repo tests its own plugin copy. **Dormant by default** - it only uploads when `--qatouch-upload --qatouch-run <KEY>` (or the env-var equivalents) are passed, so carrying it costs nothing at run time |
| `tools/qatouch_client.py` | `tools/` | **hard dependency of qatouch_reporter** (imported at upload time; needs only `requests`) |
| `tools/`: `discover_cameras.py`, `print_qa_lab_session.py`, `download_openapi_spec.py`, `probe_login.py` (+ `discover_apis.py`, `extract_schemas.py` if grep confirms they import api_clients) | `tools/` | the only non-test consumers of `api_clients` |
| `docs/API_SURFACES.md`, `docs/API_ENDPOINTS.md`, `docs/API_TESTING_NOTES.md`, `docs/BRUNO_GUIDE.md` | `docs/` | these are API docs; webapp repo keeps pointer stubs |
| `.gitignore` | `.gitignore` | trim to relevant entries |

**Deliberately NOT copied:** QA Touch snapshots (~8 MB), `master_test_repository.json`
(5.7 MB), hardware OEM docs, manual test steps, page objects, batch scripts -
fresh start means the API repo carries none of the webapp repo's weight.

### New files to write

- **`conftest.py`** - only the API fixtures extracted from the current root
  conftest (`env_config`, `base_url`, `login_data`, `api_*`, discovery fixtures).
  No `pytest_plugins` browser deps, no `authenticated_page`, no email hook
  (add later if wanted).
- **`pytest.ini`** - markers `api`, `smoke`, `env_qa/stage/prod`, `security`;
  html report; **no `--browser` addopts**.
- **`requirements.txt`** - `pytest`, `requests`, `python-dotenv`, `pytest-html`,
  `jsonschema`, `PyYAML`, `ruff`. **No `playwright`, no `pytest-playwright`.**
- **`.env.template`** - QA/stage/prod credentials (`QA_USER`, `QA_PASSWORD`,
  per-account password vars incl. `HARDWARE_LAB_PASSWORD`), `VSAAS_INTEGRATION_KEY`
  placeholder, `QATOUCH_*`. Document the `${VAR}` ordering rule.
- **`README.md`** - purpose, quickstart, auth contract pointer, env matrix,
  "how this relates to Soterix-WebApp-QA".
- **`tests/integration_api/`** - empty scaffold + README for the 14-endpoint
  `x-vsaas-key` surface (build-out later, per 2026-08-06 decision).

### Code changes during copy

- **`api_clients/auth_helper.py`: delete `login_via_ui()` entirely** (~290
  lines) and the `ALLOW_UI_LOGIN_FALLBACK` branch - raise the existing
  self-diagnosing errors instead. This repo has no browser; the fallback is
  webapp-repo history.
- Fix `base_api_client.py` `ROOT`/schema path for the new layout.

### Validation (the gate)

1. **Fresh venv**, `pip install -r requirements.txt` - must complete in seconds
   and must NOT install playwright.
2. `python -c "import playwright"` -> **ImportError expected.**
3. `pytest tests/ -q` -> expect **45 passed, 1 skipped, 1 failed** (the known
   pre-existing `test_event_search` contract bug - tracked in Backlog below).
4. Chrome process count unchanged across the run.

---

## Phase 2 - Publish `Soterix-API-QA`

1. `gh repo create Soterix-Systems/Soterix-API-QA --private` (needs org rights -
   verify `gh auth status` account can create in the org **before** starting)
2. `git init`, single initial commit, `git remote add origin
   https://github.com/Soterix-Systems/Soterix-API-QA.git`, push `main`.
3. Set the repo description: *"Soterix API - QA - API test automation (internal +
   integration APIs)"*.

**Gate:** the remote shows the pushed SHA; a teammate-visible README renders.

---

## Phase 3 - Clean the webapp repo

One commit, fully revertable, on the current repo:

1. `git rm -r tests/api tests/shared/api_clients tests/shared/schemas`
   - first `git mv tests/api/smoke/test_qatouch_reporter.py tests/plugins/`
   (adjust its `sys.path` shim).
2. `conftest.py`: delete the API fixture block (imports at ~145-152 and fixtures
   ~155-408). Keep browser fixtures untouched.
3. `git rm` the moved tools (`discover_cameras.py`, `print_qa_lab_session.py`,
   `download_openapi_spec.py`, `probe_login.py`, + confirmed others).
4. `config/qatouch_case_mapping.json`: remove the 13 `tests/api/...` entries.
5. `qa/doc_registry.yaml`: remove Section I. API entries.
6. Replace moved docs with pointer stubs ("moved to Soterix-API-QA"); update
   `README.md`, `docs/CREDENTIALS_SETUP.md`, `AGENTS.md` references.
7. `requirements.txt`: drop `jsonschema` if grep confirms nothing else uses it.
8. Cosmetic: trim `tests/api` glob in `tools/generate_step_stubs.py`; the
   `tests/api` count in `tools/qatouch_analytics.py` now reads 0 (harmless).

### Validation (the gate)

1. `pytest --collect-only -q` -> collects UI tests + relocated plugin test, zero
   errors.
2. Run one quick UI smoke test end-to-end (login flow) -> passes.
3. `ruff check .` -> no new errors vs. baseline.
4. `grep -rn "api_clients\|tests/api" --include="*.py"` -> zero hits.

---

## Phase 4 - Rename to `Soterix-WebApp-QA`

1. `gh repo rename Soterix-WebApp-QA -R Soterix-Systems/playwright-soterix-qa`
2. Update local remotes explicitly (GitHub redirects old URLs, but don't rely
   on redirects - half-renamed states hide breakage):
   `git remote set-url origin https://github.com/Soterix-Systems/Soterix-WebApp-QA.git`
3. Set description: *"Soterix WebApp - QA - UI automation + manual test cases"*.
4. `git push origin` - verify.

**Gate:** `git ls-remote` succeeds against both NEW urls; push works.

---

## Phase 5 - Workspace, docs, roadmap

1. **Workspace notes**: update the repo lists and project-structure notes kept
   outside this repo.
2. **Roadmap:** update
   `dashboards/soterix-internal-dashboards/docs/FUTURE_ROADMAP.md` - mark the
   split/rename done under Section 1, add a Soterix-API-QA row; regenerate with
   `tools/generate_dashboard.py --team qa --no-deploy`. (**Use `--no-deploy`:**
   the deploy step SSHes to the retired NUC - the git pushes still happen, only
   the dead SSH pull is skipped.)
3. **Local folder renames (optional, recommended for handoff):**
   `qa/playwright-soterix-qa` -> `qa/Soterix-WebApp-QA`. If done:
   - **recreate the venv** (Windows venv scripts embed absolute paths and break
     on folder rename),
   - refresh any local tooling that indexes by folder path,
   - update `.code-workspace`,
   - **update the dashboard generator's hardcoded path**:
     `dashboards/soterix-internal-dashboards/tools/generate_dashboard.py` (~line
     751) reads `qa/playwright-soterix-qa/config/qatouch_dashboard_metrics.json`
     by relative path - it breaks on folder rename (the GitHub rename alone does
     NOT affect it). Fix the path or set `QATOUCH_METRICS_PATH`.
   Doing this later is fine; nothing blocks on it.

---

## Phase 6 - Team handoff

- Announce both repos with their clone URLs and each repo's
  `.env.template`.
- QA Touch: agree a run-naming convention so the two suites' runs are
  distinguishable in project `JlW1` (e.g. `WebApp - <date>` / `API - <date>`).
- Existing clones of the old name keep working via GitHub redirect; teammates
  should still run `git remote set-url` at their convenience.
- **Credential rotation is now a two-repo action** - rotate in both `.env`s.
  Still pending from 2026-08-05: rotate `TEST_AUTO_QA_PASSWORD` and
  `JUSTIN_PROD_PASSWORD` (exposed in a debugging session).

---

## Verified non-couplings (audited 2026-08-07 - don't re-check, spot-check)

- **qa-ops-hub**: zero references to this repo (name or path) - its test runner
  is unaffected by split, rename, and folder rename.
- **No in-flight work**: no open PRs on either remote; `main` is the only branch
  on both.
- **Root-level scripts** (`check_cameras.py`, `compare_import.py`,
  `regenerate_import_csv.py`, `validate_qa_touch_import.py`): no `api_clients`
  or `tests.api` imports.
- **API tests** use nothing from `utils/`, `tests/shared/fixtures/`,
  `tests/shared/helpers/`, or `data/` (tenant login files) - none of those move.
- **`plugins/verification_runner.py`** is pure pytest/stdlib, self-contained.
  **Deliberately excluded** from the API repo (it serves the manual-verification
  workflow); trivial to add later if wanted.
- **Org permissions confirmed**: the maintainer's account is an active org
  member, `members_can_create_private_repositories: true`, and holds `admin` on
  the existing company repo - create + rename both verified possible.
- **Secrets**: `.env` and all auth/session caches were never tracked and are
  absent from the entire git history (audited 2026-08-05).

## Rollback

- `pre-split` tag marks the last unified state.
- Phase 3 is one commit - `git revert` restores the monorepo.
- `Soterix-API-QA` is fresh-start - deleting it loses nothing (source history
  is all in the webapp repo).
- Renames are reversible with the same `gh repo rename` command.

## Backlog (post-split, tracked here so it isn't lost)

| Item | Repo | Notes |
|---|---|---|
| Fix `test_event_search_returns_results_or_empty` | API | Done 08/08/2026: rewritten to the two-step job flow (submit a search for a jobId, then page its events); the suite is fully green |
| Integration-API test build-out | API | Blocked on `VSAAS_INTEGRATION_KEY` being issued |
| Verify prod login (`hardware-lab@`) | API | Done 08/08/2026: login verified against `app.example.invalid`, token validates |
| Plugins swallow pytest's final summary line | both | Closed 08/08/2026: not a plugin bug. `pytest.ini` already passes `-q`; a second `-q` on the command line hides the totals. A stale field in the reporter summary was fixed along the way |
| Route `login_data` through the box system | both | Done 08/08/2026: `BOX=<name>` selects the box account; `QA_USER`/`QA_PASSWORD` stays the default. Also fixed a stage-default and a silent-fallback bug in the box lookup |
| Add CI (GitHub Actions) | API first | No CI exists anywhere yet; API repo is the cheap place to start (no browser install) |
| `/REST/sso/login` contract unknown | API | Curiosity, not blocking |
