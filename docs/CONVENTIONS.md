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

**Soft assertions.** `expect.soft()` collects every failure and reports
them together at the end of the test. Use it when one test makes three or
more independent checks on one screen, and no check depends on an earlier
one (the four controls of the full screen player, the three fields of the
login form). Keep a check hard when the next step needs it: a toggle that
must show before its click, a row that must exist before its count. A hard
check stops the test at the first missing thing; a soft check lets the
others report too. Never soften a check that guards an action.

**Stream oracle.** The loader clearing only proves the spinner left. In
the full screen player, `FullScreenPage.assert_stream_playing()` is the
oracle: the `<video>` reports `readyState >= 3` and its `currentTime`
advances between two samples. The shared setups call it right after
`wait_for_stream_loaded`, so a dead stream fails at setup with "stream
never played" and the camera's name, not later at a click. In the
Views grid, `ViewsPage.assert_tile_streaming(tile_index)` is the oracle
for the configured camera: the same rule on the tile's `<video>`
(readyState >= 3, currentTime moving between two samples 700 ms
apart), and when that video never reports, the picture the tile
paints must hash differently between the samples (the tile keeps the
camera's last snapshot on screen while it loads and under the failure
overlay, so a still is not a stream). Tests that add
whichever camera the tenant lists first, which may be offline, use
`wait_for_tiles_settled()` plus the advisory content-health layer
instead; that layer never decides a test.

**Reruns.** pytest-rerunfailures is installed for one case only.
`run.py --retry-streams` appends `--reruns 1 --only-rerun "failed to
load"`: a test that failed on the tenant's stream-failure message runs
once more, and nothing else does. The flag is opt-in, never the default,
and the match is never widened. A rerun hides a broken wait, a wrong
locator, or a tenant that needs a fix. Fix first.

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
- **Two kinds of icon, two locators.** Where the app renders a MUI icon
  (Events, Admin), `svg[data-testid='ExpandMoreIcon']`, `SearchIcon`,
  `RefreshIcon` exist - use them. The Views surface and the player use
  Next.js image assets instead, and their alt text is unreliable
  (measured 08/24/2026: empty on closeIcon, editIcon, addIcon,
  favoriteIcon, Zoom; wrong on editIcon, alt="delete Icon"). For those,
  `img[src*='media/<basename>']` is the sanctioned locator - never
  `img[alt=...]` without probing the live page - and the line carries a
  why-comment, which the checker accepts the same way it accepts a
  commented sleep. The login form has custom test ids
  (`[data-testid='email']`). Check for a test id before a CSS guess.
- **MUI controls by role.** Select is `role=combobox` with `role=option`
  items in a `listbox`; Menu items are `menuitem`; Switch is
  `role=switch`; Checkbox `role=checkbox`; Dialog `role=dialog`. Prefer
  `get_by_role` over `.MuiSwitch-root`-style class selectors.
- **Counting oracles compare against a baseline** taken before the action
  (`expanded_rows > initial_rows`, `_content_added`). An absolute
  `count() > 0` passes on pre-existing elements and can never fail.
- **Tenant data names come from config**, never hardcoded in tests
  (`test_site_name`, `test_camera_name` in `config/env/`). The shared
  tenant renames things; a hardcoded name is a delayed test failure.
  Config test data is per-box: `config/env/qa.py` boxes carry a
  `test_data` overlay, so `config.get("test_site_name")` is always the
  ACTIVE box's site (BOX=us resolves Spartan0) and tests stay box-agnostic.
- **Identity lookups match the exact name, escaped** (locator series
  09/2026, TEST_REPAIRS items 14 and 18-20). Finding a specific
  camera/site/list/view by its name uses `get_by_text` / `get_by_title` /
  `get_by_role(..., exact=True)` (or `.filter(has=...)` scoped to the
  name cell), never an interpolated `:has-text('{name}')`, `text={name}`
  or `[title='{name}']`: those are case-insensitive substrings that land
  the wrong entity (`tr:has-text('ac')` matched every 'Black List' row;
  'test1' lands 'test10') and a quoted name crashes the selector parser.
  Probe the panel's DOM before converting - the name may sit in an inner
  element beside a count, or render ellipsized. A deliberate prefix over
  a fixed vocabulary ('Last 7', generated 'AutoTest<ts>' names) stays
  fuzzy WITH a why-comment. Pair every exact identity wait with a loud
  drift guard that names the on-screen entries. This is for identity;
  label matching on fixed UI strings keeps `:has-text` (zero-width-space
  caveat below).
- **Every selection needs an applied signal.** After picking a site,
  duration, or option, wait for state the page shows: the control stops
  reading Select, the listbox hides, a count changes. A helper that
  never observes its own effect goes silently dead when the DOM drifts:
  the search filter helpers died with the 2026-08 sidebar redesign and
  nothing noticed until a live probe (08/09/2026), because their JS
  fallbacks returned without error and the suites had not run since
  the redesign. Never wrap a selection in JS that returns silently
  when the panel is missing, and make the applied-signal check RAISE,
  not print: a selection that did not apply invalidates everything
  after it.
- **Some labels carry zero-width spaces** (seen on the search sidebar
  section labels), so `:text-is()` can fail while the text looks
  identical on screen. Prefer `:has-text()` with a distinctive
  substring for label matching; exact matching is fine where a run
  proves the text is clean.

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
- `BOX` selects a tenant inside the env (`boxes` in `config/env/qa.py`:
  `india`, `us`). A box names its account variables, its site id, and the
  `test_data` overlay, so `config.get("test_site_name")` is always the
  active box's site and no test carries box logic.
- A box that lacks a feature says so in its `without` map, by pytest
  marker and with the measured or stated reason
  (`"lpr": "Spartan0 has no LPR cameras ... (Justin, 09/08/2026)"`). The
  collection hook skips those tests on that box with that reason, in
  0.2 s and without a browser, and runs them on the boxes that have the
  feature. Before this the nine LPR tests failed on the US box every
  night for a data fact. The env guard (`allow_write`, `allow_delete`)
  speaks first; the box guard second.

## Test data through the API

Build the data a test needs but does not prove through the internal API,
not through the browser. `test_delete_camera_group` gets its group from
the API and proves only the delete. `test_create_camera_group` keeps the
UI path because the create is what it proves.

The client and fixtures live in `tests/shared/api/`. `conftest.py`
registers them. They need `QA_USER`, `QA_PASSWORD` and `TEST_SITE_ID` in
`.env`. The API test repo is a separate project. Never import from it.

- `api`: a logged-in session for the test site. It skips when a variable
  is missing, and when `TEST_SITE_ID` is not the site that
  `test_site_name` names (the skip message gives the right id).
- `api_camera_group`: `make(name=None, channel_ids=None)` returns the
  created group. The default holds the configured test camera.
- `api_bookmark`: `make(comment=None, camera_id=None, ...)` returns the
  created bookmark.
- `api_saved_view`: `make(name=None, channel_ids=None, grid="2x2")` returns
  the created My Views card. `test_drag_saved_view_to_tile` uses it and
  proves only the drag.

Rules for any new fixture:

1. Every name starts with `AutoTest ` so a leftover on the shared tenant
   is recognisable. The fixtures refuse other names.
2. Verify the write with a read before the test gets it. The envelope
   text is not a signal: `addgroup` answers "Successfully Retrieved!",
   and a bookmark `DELETE` answers "Successfully deleted!" while the row
   stays in the list with `deletedAt` above 0 (a live row holds -1).
   Check `code`, then confirm in `location/tree` or the list.
3. The fixture deletes what it made at teardown and confirms the
   removal. A survivor fails the test with its id.
4. Read what the UI reads. A camera group in Admin > Sites is a
   *location* in the API (`site/config/{site}/location`,
   `location/tree`, `deletelocation`). The API's groups (`addgroup`,
   `grouptree`) are a different entity the Admin UI never shows. A saved
   view in Views > My Views is a *preset* (`GET/POST /REST/preset`,
   `DELETE /REST/preset/{id}`); the spec's UserViewLayouts endpoints are
   never called by the web client.
5. Create the data before the page renders so the UI shows it without a
   reload, and open the site the API wrote to by name.

## Missing artifacts and skips

A test whose artifact is absent has proved nothing, so it must never
report green. It does not today: a skip uploads to QA Touch as Blocked,
never Passed. Skip is still the weakest outcome, and four rules keep
it honest.

1. Create what the UI can create. A clip, folder, bookmark, user or
   saved view the test could have made is not a reason to skip. Make it,
   prove the behaviour, remove it. Owning the artifact also keeps rename,
   move and delete off a real user's data on the shared tenant.
2. A skip must prove its precondition first. "No maps found" and "the
   panel never loaded" read the same in a report, and yellow gets
   scrolled past. Prove the surface loaded, then report absence; if it
   did not load, fail. test_drag_location_to_tile had only ever skipped
   (register item 13), and three maps tests skipped on every run until a
   map existed (item 22).
   `tests/shared/helpers/surface.py` is that check in one call:
   `require_items` waits for the rows, then decides between an empty
   surface (skip) and a surface that never rendered (fail).
   When the artifact comes from a server job rather than a panel, the
   proof is the job's own answer: `tests/shared/helpers/search_job.py`
   follows the Events and Search pages' search job (start, polls,
   completion) and `require_results` skips only on a job that reached
   100% with nothing, naming the job, its scope and its counts; a click
   that sent no job, a job that never finished, or a bad response fails.
   Before it, 24 of the 49 failures in the 09/04/2026 full run were
   "Timeout 60000ms" on a box that simply had no events.
3. A skip is never a failure handler. `except Exception: pytest.skip(...)`
   reports the app's own error as Blocked, and it catches the test's
   asserts too - test_drag_map_to_tile ran its closing assert inside one,
   so the test could pass or skip but never fail. Let the failure raise.
   The checker rule is `skip-in-except`; a why-comment on the handler
   excuses the case where the exception really does mean absence.
4. A skip reason states a measurement, not a guess. "may not be supported
   in current app version" is a hypothesis written into a green run, and
   it stays there for months because nobody reads a skip. Probe the
   surface (`tools/explore_app.py`), then write what is on screen. The
   checker rule is `speculative-skip-reason`.

A test that skips on every run is dead coverage, not a passing test.
Check the run record for skips that never turn green. Register item 25
is the audit of every skip in the UI suite against these four rules.

## Markers

Defined in `pytest.ini`. The main groups:

- **Type:** `smoke`, `sanity`, `regression`, `ui`
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

## Code notes

- **No ticket keys in code.** Jira numbers change and go stale; code
  outlives them. Comments, docstrings, and skip/error messages describe
  the BEHAVIOR ("folder delete does not apply on the tenant") and point
  at the register when a maintainer needs more; TEST_REPAIRS' App
  defects section maps behavior to the current ticket.
- **Comments follow the code's writing principles**: concise, direct,
  nothing twice. Keep the why and the measured fact with its probe
  date; drop history narration and anything the code already says.

## Verification steps

- JSON sidecars in `tests/steps/` define step-by-step verification.
- Tests call `step_capture.mark(step_num, description)` between steps.
- `--verify-mode` captures screenshots into `verification_output/`.
- QA Ops Hub consumes the evidence JSONs for async review.

## Adding a test

- **First line of every test is its title.** The run report (`run.html`)
  shows the docstring's first line as the readable test name and the
  QA Touch case title beneath it, with the node id smaller. Write one
  sentence that says what the test proves ("Verify a saved view can be
  dragged to an empty tile"). Never rename test functions for
  readability: the node id is the join key for the mapping, the archive
  history, and `run.py rerun`. The checker flags a test without a
  docstring.

- **The docstring is the QA Touch case.** A human writes the tester
  steps in the docstring, and the case is generated from there. Never
  from code: a step that names a locator or a method is not a step a
  tester can follow. Write what the tester does and what they see, one
  short sentence each, in this form:

  ```python
  def test_favorite_camera(self):
      """Verify the star adds the camera to the Favorites panel.

      Steps:
      1. Open Views and expand the configured test site.
         Expected: The camera list shows.
      2. Click the star on the configured test camera.
         Expected: The star fills and the camera appears in the Favorites panel.
      """
  ```

  The block starts at a line that reads `Steps:`. Each numbered line is
  a step. An `Expected:` line belongs to the step above it. Give every
  step with a visible result its own `Expected:`, and give the last
  step one always. For a parametrized test, say the variant in words
  ("Repeat for the Vehicle category"). The checker flags a new test
  with no `Steps:` block.

- **A test lands with its QA Touch case and mapping row in the same
  change.** Three commands:

  ```
  python tools/qatouch_cases_from_tests.py --test tests/ui/{module}/test_x.py::TestX::test_y
  python tools/qatouch_csv_import.py import logs/qatouch_new_cases_<date>.csv --project JlW1
  python tools/qatouch_cases_from_tests.py --after-import logs/qatouch_new_cases_<date>.csv
  ```

  The first writes the case CSV and a Markdown preview under `logs/`
  from the docstring. Read the preview, then run `preview` on the CSV.
  The second is the owner's command: it creates the cases, and there is
  no delete API. The third reads the cases back, matches the CSV's
  Reference column (the node id) to each new case, and writes the
  mapping rows. The checker flags a new test with no mapping row.
  `--unmapped` and `--dead-keys` select the tests that still need a
  case across the tree.

1. Create the test file in `tests/ui/{module}/`.
2. Write the title and the `Steps:` block in the docstring.
3. Add the relevant markers from `pytest.ini`.
4. Use existing page objects, or create new ones in `tests/shared/pages/`.
5. If the test belongs in the QA verification pipeline, wire up `step_capture`
   in the setup fixture and add `.mark()` calls (see below). Optional otherwise.
6. Create the matching JSON sidecar in `tests/steps/ui/{module}/` (only if the
   test uses step capture).
7. Generate, import, and map the QA Touch case with the three commands
   above. The mapping lives in `config/qatouch_case_mapping.json`, never
   in an in-test marker.

**Build on the foundations, not beside them.** Each of these exists because
a class of tests failed or lied for weeks before it did (register items 14,
21, 25, 28, 29, 35, 37; docs/TEST_COVERAGE_ASSESSMENT.md). A new test that
needs one of them uses it; the checker flags the hand-rolled version.

- **An artifact that may be absent:** `require_items` in
  `tests/shared/helpers/surface.py`. It proves the surface rendered, then
  skips with a measured reason or fails. Never `if count == 0: skip`.
- **A search or any server job:** `watch_search` and `require_results` in
  `tests/shared/helpers/search_job.py`, through the page object's
  `execute_search` / `search_events`. Never a minute-long wait on the first
  thumbnail.
- **Tenant data the test needs:** the active box's `test_data` in
  `config/env/qa.py` (`config.get("test_site_name")`), never a literal
  site or camera name. Data a box lacks goes in its `without` map, by
  marker, with the reason.
- **Data the test creates:** own it and delete it, and let the teardown
  raise when the thing survives (`_own_a_rule`, `_own_a_group`,
  `_own_a_widget` in the admin, chats and views suites are the pattern).
  One leftover rule hides a camera from the wizard for every later test.
- **Identity:** exact matches (`exact=True`, `title=`, `span[title=]`,
  scoped to the row), never `.first` on a substring.
- **The oracle:** say what the action changed. A count against a baseline
  taken before the action, a name that appears or disappears, a URL, a
  state, a negative expectation. "It is visible" after a wait that already
  required it proves nothing; the assessment graded 294 of 508 tests that
  way.
- **Waits:** the DOM signal that means done, or the request behind it;
  a sleep needs its why. A wait over a minute needs its why too.
- **Failure paths:** let them raise. An except handler earns its place
  with a why-comment on the except line, or by re-raising.

Run `python tools/convention_check.py` before committing; the pre-commit
hook runs it on the added lines and blocks on HIGH.

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
- Never add `-q` to a pytest command. `pytest.ini` already has one, and
  two make `-qq`, which hides the pass count. See `tools/collect_floor.py`.

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
  with no why-comment; `@pytest.mark.qatouch` in a test file; a
  `pytest.skip` raised from an except handler; an except handler with no
  why-comment that neither re-raises nor fails (`except-without-why`); and,
  on added lines, a new UI test without a `Steps:` block.
- **MEDIUM, warns:** absolute `count() > 0` oracles, `img[src]` icon locator
  guesses, hardcoded tenant data names, a skip reason that guesses at the
  app, a test body with no oracle or with presence-only oracles
  (`presence-only-oracle`: every check is "visible" or "attached"), a DOM
  wait of a minute or more (`long-blind-wait`), `.first` on a text lookup
  (`first-on-text-lookup`), `.first`/`.last` on a union selector, bare
  early returns, Jira keys in code, and a new test without a title or
  without a mapping row.

The default mode checks only the lines added since HEAD, so debt in files
you did not touch never blocks you. `--base <ref>` widens the diff (use it
before pushing a branch: `--base origin/main`). `--all` scans every test
file and reports the standing debt; on 09/11/2026 that was 190
presence-only oracles, 90 uncommented except handlers, 82 `.first` text
lookups and 15 minute-long waits, the worklist the coverage assessment
left behind (docs/TEST_COVERAGE_ASSESSMENT.md).

Every rule started as a defect found in review or in a run. When a review
finds a new class, it gets a rule the same day, so the class cannot recur
in new code while the old instances are worked down.

A sleep earns its comment by naming the missing signal ("canvas pacing",
"server ack has no DOM signal"), not by restating the sleep.
