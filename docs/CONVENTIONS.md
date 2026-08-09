# Engineering conventions

House rules for writing and organizing tests in this repo. Writing style for
prose is separate: see [STYLE.md](STYLE.md).

## Stack

- **Framework:** Playwright (Python) + pytest
- **Target:** the NexaiQ-Core web app (qa/stage/prod, customer/partner)
- **Reporting:** QA Touch integration via a custom pytest plugin (in development)
- **Auth:** cached browser state (see Session caching below)
- **API testing** lives in the sibling repo Soterix-API-QA and is browser-free.

## Page objects

- One page object per page in `tests/shared/pages/`.
- Naming: `{page_name}_page.py` holds class `{PageName}Page`.
- The constructor takes `page: Page` (the Playwright page instance).
- Selectors as `self.element = page.locator(...)`.
- Methods: `navigate_to_*()`, `click_*()`, `fill_*()`, `verify_*()`.
- Use `expect()` for assertions and `wait_for(state="visible")` for waits.

## Waits

Do not add `page.wait_for_timeout()` or `time.sleep()` to new code. A fixed
sleep is too long on a fast run and too short on a slow one. Wait for the
signal instead:

- Actions (`click`, `fill`, `hover`) wait for the element on their own. Do not
  sleep before them. A hover-revealed icon needs no sleep either, because the
  click on the icon waits for it to appear.
- After an action, wait for the element the next step needs:
  `locator.wait_for(state="visible")` or an `expect()` assertion.
- `count()`, `get_attribute()`, and `is_visible()` read once and do not retry.
  Do not assert on them right after an action. Use `expect(...).to_have_count()`
  or `expect(...).to_have_value()`, which retry until the timeout.
- For an optional element, use `ViewsPage._appears(locator, timeout)`:
  it returns True when the element shows and False on timeout, and it returns
  as soon as the element appears.
- If a transition has no DOM signal, keep a short sleep and add a comment that
  says why. These should stay rare.

For assertion-dense tests, `expect.soft()` collects all assertion failures and
reports them together at the end of the test instead of stopping at the first.
For clicks that a sticky header or a lazy-loaded overlay intercepts, try
`click(scroll="none")` before you reach for `force=True` or a JS click.

Failed tests save a Playwright trace. See
[FAILURE_TRIAGE.md](FAILURE_TRIAGE.md).

## Locators and scoping

Patterns validated twice over - once in the team's fixes (July 2026) and
once independently in the wait conversion (August 2026). Use them:

- **MUI dropdowns:** the option list is `li[role='option']` inside a
  `[role='listbox']` portal. Wait for the listbox to appear, click the
  option plainly (no hover chain, no force), then wait for the listbox to
  become **hidden** - that is the selection-applied signal
  (`events_page.select_site`, `admin_page.select_site_for_rule`).
- **Scope before .first:** when an icon or switch exists once per row or
  card, find the row by its text and locate the control inside it. A page
  -global `.first` can pick another row's control while a filter or hover
  is still applying (`events_page` pin fix, `admin_page.toggle_user_status`).
- **MUI ships data-testid on icons.** `svg[data-testid='ExpandMoreIcon']`,
  `SearchIcon`, `CloseIcon` work today, no frontend change needed - prefer
  them over `img[src*=...]` guesses for MUI icon buttons. The login form
  also has custom test ids (`[data-testid='email']`). Check for a test id
  before writing a CSS guess.
- **Counting oracles compare against a baseline** taken before the action
  (`expanded_rows > initial_rows`, `_content_added`). An absolute
  `count() > 0` passes on pre-existing elements and can never fail.
- **Tenant data names come from config**, never hardcoded in tests
  (`test_site_name`, `test_camera_name` in `config/env/`). The shared
  tenant renames things; a hardcoded name is a delayed test failure.

## Auth and session caching

- The `authenticated_page` fixture loads cached `.auth_state.json` (2-3 s
  instead of a 65 s login).
- First run: logs in through the UI and saves browser storage state.
- Later runs: reload the cached state, validate it, log in again if expired.

## Environment config

- The `ENV` var selects `config/env/{qa,stage,prod}.py`.
- `APP_TYPE=partner` appends `_pat` to the module path.
- The config dict holds `base_url`, `api_base_url`, `default_user`,
  `default_password`, `allow_write`, `allow_delete`.

## Markers

Defined in `pytest.ini`. The main groups:

- **Type:** `smoke`, `sanity`, `regression`, `ui`
- **Environment:** `env_qa`, `env_stage`, `env_preprod`, `env_prod`
- **Feature:** `admin`, `views_devices`, `events`, `search`, `media`, `maps`,
  `chats`, `licenses`, and the rest
- **Meta:** `slow` (over 30 s), `flaky` (intermittent), `wip` (skip in CI)

Run examples: `pytest -m smoke`, `pytest -m "admin and not slow"`.

## QA Touch integration (work in progress, not the current process)

Today the process is: run pytest, read `reports/report.html`, report results
manually. Nothing below runs unless you opt in. Treat it as in development.

- **Mapping lives in `config/qatouch_case_mapping.json` only** (nodeid to
  case_key). The reporter also honors a `@pytest.mark.qatouch("KEY")` marker,
  but the shared test files deliberately carry none: QA Touch reporting is not
  part of the team's automation flow, so it stays out of the test code. Add new
  mappings to the JSON, never to a test file.
- **Coverage is minimal for now.** The JSON holds a small set of entries. A
  larger extracted mapping is held back until duplicate case claims are
  resolved (results would overwrite each other).
- **Unmapped tests still run.** Mapping affects result reporting only, never
  pass or fail. Unmapped tests land in the reporter's `unmapped` count.
- The reporter posts results with `pytest --qatouch-upload --qatouch-run <KEY>`
  and retries 3 times with exponential backoff.
- Current template runs (cloned on each execution): Smoke=vaXdn, Sanity=zvXPw.
- **Orchestrated entry point (WIP):** `python tools/run_suite.py smoke` clones
  the template into a fresh QA Touch run so history is preserved. Use
  `--run-key <KEY>` to reuse an existing run. Plain `pytest` remains the
  everyday command.
- **Post-run loop (WIP, off by default):** `run_suite.py` reads
  `logs/last_run_results.json`, updates `flaky_tests.json`, then feeds each
  failed nodeid through `smart_jira_bug_creator.multi_gate_validation()`.
  - Intended model once enabled: each suite runs once per release per env, and
    every failure files a Jira bug directly. RTM linkage back to the QA Touch
    case is wired automatically. Not in effect while `BUG_CREATION_ENABLED` is
    false.
  - The one suppression is the env-health gate: if the target env's base_url is
    unreachable, the run counts as infrastructure-broken and no bugs are filed.
  - The step is gated by `BUG_CREATION_ENABLED=true` in `.env`. Until then it
    dry-runs and returns a fake `AUTO-XXXX` issue dict for inspection.
  - Use `--no-bug-filing` to skip the step entirely.
- **Reporter endpoint:** defaults to the legacy status-only PATCH. Set
  `QATOUCH_USE_PLAYWRIGHT_ENDPOINT=1` for the bulk endpoint (per-result
  execution time plus failure screenshots captured from the live page). Set
  `QATOUCH_CAPTURE_SCREENSHOTS=0` to turn off screenshots there.

## Verification steps

- JSON sidecars in `tests/steps/` define step-by-step verification.
- Tests call `step_capture.mark(step_num, description)` between steps.
- `--verify-mode` captures screenshots into `verification_output/`.
- QA Ops Hub consumes the evidence JSONs for async review.

## Adding a test

1. Create the test file in `tests/ui/{module}/`.
2. Add the relevant markers from `pytest.ini`.
3. Use existing page objects, or create new ones in `tests/shared/pages/`.
4. If the test belongs in the QA verification pipeline, wire up `step_capture`
   in the setup fixture and add `.mark()` calls (see below). Optional otherwise.
5. Create the matching JSON sidecar in `tests/steps/ui/{module}/` (only if the
   test uses step capture).
6. Map to QA Touch through `config/qatouch_case_mapping.json`, never with an
   in-test marker.
7. Sync steps to QA Touch: `python tools/qatouch_step_api.py sync --cases KEY`.

## Step capture (for tests in the verification pipeline)

`step_capture.mark()` feeds the QA verification pipeline. Those tests run
headed with step overlays so QA testers can check each step visually.

It is **opt-in, not universal**: roughly a third of the test files wire it up.
A test without it runs normally and is invisible to `--verify-mode`. Add it
when a test is meant for QA visual review. Do not retrofit it across the suite
for consistency alone.

**Setup fixture.** Accept `step_capture` and wire it to the page:

```python
@pytest.fixture(autouse=True)
def setup(self, authenticated_page, step_capture):
    self.page = authenticated_page
    self.step_capture = step_capture
    step_capture.set_page(self.page)
    self.views = ViewsPage(self.page)
    yield
```

**Test method.** Call `.mark()` AFTER each logical action:

```python
def test_export_clip(self):
    self.step_capture.mark(1, "Navigate to Views and load camera into tile")
    self.views.navigate()
    self.views.add_first_camera_via_checkbox()

    self.step_capture.mark(2, "Click Clip icon to enter timeline selection mode")
    self.views.click_clip_icon()

    self.step_capture.mark(3, "Check Save to Media and click Export")
    self.views.check_save_to_media()
    self.views.click_export_button()

    self.step_capture.mark(4, "Verify Export Successful toast appears")
    self.views.wait_for_export_success()
```

**Function-based tests** (login, logout) accept it as a parameter:

```python
def test_valid_login(authenticated_page, step_capture):
    step_capture.set_page(authenticated_page)
    step_capture.mark(1, "Navigate to login page")
    # ...
```

**Rules:**

- Write descriptions for QA reviewers, not developers.
- Present tense. Describe what the tester sees and does.
- One mark per logical step, not per line of code.
- Call mark AFTER the action completes, so it captures the resulting state.
- Step numbers are sequential and start at 1.
- The step text in `.mark()` must match the `action` text in the JSON sidecar.

**JSON sidecar.** Create `tests/steps/ui/{module}/test_{name}.json`:

```json
{
  "test_file": "tests/ui/views/test_views_export_clip.py",
  "class": "TestViewsExportClip",
  "tests": {
    "test_export_clip": {
      "title": "Verify clip export saves to Media page",
      "case_key": "ABC123",
      "steps": [
        {"n": 1, "action": "Navigate to Views and load camera into tile", "expected": "Camera stream visible in tile"},
        {"n": 2, "action": "Click Clip icon to enter timeline selection mode", "expected": "Timeline selection activates"},
        {"n": 3, "action": "Check Save to Media and click Export", "expected": "Export starts processing"},
        {"n": 4, "action": "Verify Export Successful toast appears", "expected": "Toast shows Export Successful"}
      ]
    }
  }
}
```

**QA verification run:** `pytest --headed --slowmo 300 --verify-mode -k "test_name"`

## Drag and drop

All drag-and-drop tests must use the visible-drag helper, never raw
`drag_to()`. It highlights the source (red border) and target (green border)
so testers can see the drag in headed mode. The current implementation is
`_visible_drag()` in `tests/ui/views/test_views_subtabs.py`; promote it to
`ViewsPage` when a second module needs it.

## Critical rules

- Never hardcode URLs or credentials. Use env vars and config.
- Always use page objects. Centralize selectors.
- Reuse the cached auth state in `.auth_state.json`.
- `legacy/` and `legacy-selenium-tests/` are excluded from test runs.

## Linting (ruff)

- Config: `pyproject.toml`. Playwright/pytest-aware rule families (PT, BLE,
  T20, ARG, B, UP, SIM, RUF, I, plus pycodestyle and pyflakes).
- Run `python -m ruff check .` before commits. `--fix` applies only safe
  transforms.
- Per-file ignores live in `pyproject.toml`: tests/ allow unused-import,
  unused-arg, and `assert False`; tools/ allow `print()` and broad except;
  plugins/ allow unused-arg (pytest hook signatures).
- `docs/archive/`, `config/audit_reports/`, `config/qatouch_snapshots/`,
  `legacy/`, `verification_output/`, and `logs/` are excluded entirely.

## Convention checker

Ruff checks Python style; `tools/convention_check.py` checks the rules on
this page that ruff cannot see. Run both before every commit:

```
python -m ruff check .
python tools/convention_check.py
```

- **HIGH, blocks the commit:** a sleep (`wait_for_timeout` or `time.sleep`)
  with no why-comment, and `@pytest.mark.qatouch` in a test file.
- **MEDIUM, warns:** absolute `count() > 0` oracles, `img[src]` icon locator
  guesses, and hardcoded tenant data names.

The default mode checks only the lines added since HEAD, so debt in files
you did not touch never blocks you. `--base <ref>` widens the diff (use it
before pushing a branch: `--base origin/main`). `--all` scans every test
file and reports the standing debt.

A sleep earns its comment by naming the missing signal ("canvas pacing",
"server ack has no DOM signal"), not by restating the sleep.
