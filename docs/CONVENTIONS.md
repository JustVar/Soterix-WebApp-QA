# Engineering conventions

House rules for writing and organizing tests in this repo. Writing style
for prose is separate: see [STYLE.md](STYLE.md).

## Adding a test

The steps, in order:

1. Look at the app first. `python tools/explore_app.py --headed` opens the
   app signed in, with the page objects in scope. Probe the panel before
   you write a locator.
2. Create the test file under `tests/ui/<module>/`. The module is the
   folder of the feature (views, admin, search, and the rest).
3. Write the title and the `Steps:` block in the docstring (below).
4. Add the applicable markers from `pytest.ini`.
5. Use the page objects in `tests/shared/pages/`. Add a page object only
   when none fits.
6. If the test changes the account's state (a saved view, a rule, a user,
   a widget), give the module its group:
   `pytestmark = pytest.mark.xdist_group("account_<family>")`. The table
   of families is in [PARALLEL_EXECUTION.md](PARALLEL_EXECUTION.md).
   Tests in 1 group run on 1 worker, so they do not change the same data
   at the same time.
7. Give each thing that the test creates a name that starts with
   `AutoTest` and ends in `%H%M%S%f`. With 4 workers, 2 tests can make a
   name in the same second.
8. Run the test on the QA server: `python run.py test <node id>`.
9. Stage the new file, then run `python tools/test_inventory.py`. It
   writes `docs/TEST_INVENTORY.md` again. The pre-commit hook refuses a
   commit when that file is stale.
10. If the team uploads results to QA Touch, make the case and the mapping
    row (below). The mapping is in `config/qatouch_case_mapping.json`,
    never in a marker in the test file.

**Branch, pull request, never force-push main.** Every change goes on a
branch and reaches main through a pull request. CI runs the collect gate
on the pull request. Nobody force-pushes main.

**First line of every test is its title.** The run report (`run.html`)
shows the docstring's first line as the readable test name, with the node
id smaller. Write 1 sentence that says what the test proves ("Verify a
saved view can be dragged to an empty tile"). Never rename test functions
for readability: the node id is the join key for the mapping, the archive
history, and `run.py rerun`. The checker flags a test without a docstring.

**The docstring is the QA Touch case.** A human writes the tester steps in
the docstring, and the case is generated from there. Never from code: a
step that names a locator or a method is not a step a tester can follow.
Write what the tester does and what they see, 1 short sentence each, in
this form:

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

The block starts at a line that reads `Steps:`. Each numbered line is a
step. An `Expected:` line belongs to the step above it. Give every step
with a visible result its own `Expected:`, and give the last step one
always. For a parametrized test, say the variant in words ("Repeat for the
Vehicle category"). The checker flags a new test with no `Steps:` block.

**A test lands with its QA Touch case and mapping row in the same
change**, when the team uploads results. Three commands:

```
python tools/qatouch_cases_from_tests.py --test tests/ui/{module}/test_x.py::TestX::test_y
python tools/qatouch_csv_import.py import logs/qatouch_new_cases_<date>.csv --project <key>
python tools/qatouch_cases_from_tests.py --after-import logs/qatouch_new_cases_<date>.csv
```

The first writes the case CSV and a Markdown preview under `logs/` from the
docstring. Read the preview, then run `preview` on the CSV. The second
creates the cases, and QA Touch has no delete API. The third reads the
cases back, matches the CSV's Reference column (the node id) to each new
case, and writes the mapping rows. `--unmapped` and `--dead-keys` select
the tests that still need a case across the tree. The checker warns on a
new test with no mapping row only when the mapping file already has rows.

**Build on the foundations, not beside them.** Each of these exists
because a class of tests failed or lied for weeks before it did. A new
test that needs one of them uses it. The checker flags the hand-rolled
version.

- **An artifact that may be absent:** `require_items` in
  `tests/shared/helpers/surface.py`. It proves the surface rendered, then
  skips with a measured reason or fails. Never `if count == 0: skip`.
- **A search or any server job:** `watch_search` and `require_results` in
  `tests/shared/helpers/search_job.py`, through the page object's
  `execute_search` / `search_events`. Never a minute-long wait on the
  first thumbnail.
- **Server data the test needs:** `test_site_name`, `test_camera_name`
  and the chat keys in `config/env/qa.py` (`config.get("test_site_name")`),
  never a literal site or camera name, and never a literal as the
  `config.get` default. When the file leaves the site or the camera blank,
  the session reads them from the server before any test runs, so the
  same reads work. Data the server lacks goes in its `without` map, by
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
  required it proves nothing.
- **Waits:** the DOM signal that means done, or the request behind it. A
  sleep needs its why. A wait over a minute needs its why too.
- **Failure paths:** let them raise. An except handler earns its place
  with a why-comment on the except line, or by re-raising.

Run `python tools/convention_check.py` before committing. The pre-commit
hook runs it on the added lines and blocks on HIGH.

## Page objects

- One page object per page in `tests/shared/pages/`.
- Naming: `{page_name}_page.py` holds class `{PageName}Page`.
- The constructor takes `page: Page` (the Playwright page instance).
- Selectors as `self.element = page.locator(...)`.
- Methods: `navigate_to_*()`, `click_*()`, `fill_*()`, `verify_*()`.
- Use `expect()` for assertions and `wait_for(state="visible")` for waits.

## Waits

Do not add `page.wait_for_timeout()` or `time.sleep()` to new code. A
fixed sleep is too long on a fast run and too short on a slow one. Wait
for the signal instead:

- Actions (`click`, `fill`, `hover`) wait for the element on their own. Do
  not sleep before them. A hover-revealed icon needs no sleep either,
  because the click on the icon waits for it to appear.
- After an action, wait for the element the next step needs:
  `locator.wait_for(state="visible")` or an `expect()` assertion.
- `count()`, `get_attribute()`, and `is_visible()` read once and do not
  retry. Do not assert on them right after an action. Use
  `expect(...).to_have_count()` or `expect(...).to_have_value()`, which
  retry until the timeout.
- For an optional element, use `ViewsPage._appears(locator, timeout)`: it
  returns True when the element shows and False on timeout, and it returns
  as soon as the element appears.
- If a transition has no DOM signal, keep a short sleep and add a comment
  that says why. These should stay rare.

**Soft assertions.** `expect.soft()` collects every failure and reports
them together at the end of the test. Use it when 1 test makes 3 or more
independent checks on 1 screen, and no check depends on an earlier one
(the 4 controls of the full screen player, the 3 fields of the login
form). Keep a check hard when the next step needs it: a toggle that must
show before its click, a row that must exist before its count. Never
soften a check that guards an action.

**Stream oracle.** The loader clearing only proves the spinner left. In
the full screen player, `FullScreenPage.assert_stream_playing()` is the
oracle: the `<video>` reports `readyState >= 3` and its `currentTime`
advances between 2 samples. The shared setups call it right after
`wait_for_stream_loaded`, so a dead stream fails at setup with "stream
never played" and the camera's name, not later at a click. In the Views
grid, `ViewsPage.assert_tile_streaming(tile_index)` is the oracle for the
configured camera: the same rule on the tile's `<video>`, and when that
video never reports, the picture the tile paints must hash differently
between the samples (the tile keeps the camera's last snapshot on screen
while it loads, so a still is not a stream). Tests that add whichever
camera the server lists first, which may be offline, use
`wait_for_tiles_settled()` plus the advisory content-health layer instead.
That layer never decides a test.

**Reruns.** pytest-rerunfailures is installed for 1 case only.
`run.py --retry-streams` appends `--reruns 1 --only-rerun "failed to
load"`: a test that failed on the server's stream-failure message runs
once more, and nothing else does. The flag is opt-in, never the default,
and the match is never widened. A rerun hides a broken wait, a wrong
locator, or a server that needs a fix. Fix first. The label for a test
that fails now and then is `intermittent`, never `flaky`: that name is
pytest-rerunfailures' own, and the plugin retries it on ANY failure, once
even with no `reruns=`. The checker refuses `@pytest.mark.flaky` in any
form.

For clicks that a sticky header or a lazy-loaded overlay intercepts, try
`click(scroll="none")` before you reach for `force=True` or a JS click.

Failed tests save a Playwright trace. See
[FAILURE_TRIAGE.md](FAILURE_TRIAGE.md).

## Locators and scoping

- **MUI dropdowns:** the option list is `li[role='option']` inside a
  `[role='listbox']` portal. Wait for the listbox to appear, click the
  option plainly (no hover chain, no force), then wait for the listbox to
  become **hidden**. That is the selection-applied signal
  (`events_page.select_site`, `admin_page.select_site_for_rule`).
- **Scope before .first:** when an icon or switch exists once per row or
  card, find the row by its text and locate the control inside it. A
  page-global `.first` can pick another row's control while a filter or
  hover is still applying.
- **Two kinds of icon, two locators.** Where the app renders a MUI icon
  (Events, Admin), `svg[data-testid='ExpandMoreIcon']`, `SearchIcon`,
  `RefreshIcon` exist. Use them. The Views surface and the player use
  Next.js image assets instead, and their alt text is unreliable (empty
  on some icons, wrong on others). For those, `img[src*='media/<basename>']`
  is the sanctioned locator, never `img[alt=...]` without probing the live
  page, and the line carries a why-comment, which the checker accepts the
  same way it accepts a commented sleep. The login form has custom test
  ids (`[data-testid='email']`). Check for a test id before a CSS guess.
- **MUI controls by role.** Select is `role=combobox` with `role=option`
  items in a `listbox`. Menu items are `menuitem`. Switch is
  `role=switch`. Checkbox is `role=checkbox`. Dialog is `role=dialog`.
  Prefer `get_by_role` over `.MuiSwitch-root`-style class selectors.
- **Counting oracles compare against a baseline** taken before the action
  (`expanded_rows > initial_rows`, `_content_added`). An absolute
  `count() > 0` passes on pre-existing elements and can never fail.
- **Server data names come from config**, never hardcoded in tests
  (`test_site_name`, `test_camera_name` in `config/env/qa.py`). The shared
  server renames things. A hardcoded name is a delayed test failure.
- **A name the app shows cut short is matched as shown.** Several panels
  cut a long name in the DOM and append an ellipsis with no title
  attribute ('Example Corporate Off...'), so neither an exact nor a
  substring match reaches the row. `tests/shared/helpers/shown_name.py`
  (`shown_as` for a locator, `is_shown_as` for an assertion) accepts the
  name or a cut of it with the ellipsis, and nothing else.
- **The server runs 1 search job at a time.** A second
  `POST /REST/site/search` answers code 400 while one is being polled,
  from any session and for any site. Two tests or 2 workers that both
  search collide, and the second reads 'no search job was sent ... HTTP
  400'. A search over a busy site runs for minutes. The searching tests
  (Search, Events, drawing) share the `account_search` xdist group so they
  run on 1 worker, and `tests/shared/helpers/search_gap.py` spaces them.
- **Identity lookups match the exact name, escaped.** Finding a specific
  camera, site, list or view by its name uses `get_by_text`,
  `get_by_title`, `get_by_role(..., exact=True)` (or `.filter(has=...)`
  scoped to the name cell), never an interpolated `:has-text('{name}')`,
  `text={name}` or `[title='{name}']`: those are case-insensitive
  substrings that land the wrong entity (`tr:has-text('ac')` matched every
  'Black List' row. 'test1' lands 'test10'), and a quoted name crashes the
  selector parser. Probe the panel's DOM before converting. The name may
  sit in an inner element beside a count, or render ellipsized. A
  deliberate prefix over a fixed vocabulary ('Last 7', generated
  `AutoTest<ts>` names) stays fuzzy WITH a why-comment. Pair every exact
  identity wait with a loud drift guard that names the on-screen entries.
  This is for identity. Label matching on fixed UI strings keeps
  `:has-text` (zero-width-space caveat below).
- **Every selection needs an applied signal.** After picking a site,
  duration, or option, wait for state the page shows: the control stops
  reading Select, the listbox hides, a count changes. A helper that never
  observes its own effect goes silently dead when the DOM drifts: the
  search filter helpers died with a sidebar redesign and nothing noticed
  until a live probe, because their JS fallbacks returned without error.
  Never wrap a selection in JS that returns silently when the panel is
  missing, and make the applied-signal check RAISE, not print: a selection
  that did not apply invalidates everything after it.
- **`has_text` reads textContent, not the screen.** A regex passed to
  `.filter(has_text=...)` runs against the element's textContent with
  whitespace collapsed: hidden entries are in it, and block boundaries add
  no space. Anchor at the start (`^\s*[>v]?\s*NAME`) on a container and
  use `^...$` only on a leaf whose whole text is the label. A line-end
  anchor (`\n|$`) never matches and the click waits out its timeout.
  Measure the text with `evaluate("e => e.textContent")` before writing
  the pattern.
- **Some labels carry zero-width spaces** (seen on the search sidebar
  section labels), so `:text-is()` can fail while the text looks identical
  on screen. Prefer `:has-text()` with a distinctive substring for label
  matching. Exact matching is fine where a run proves the text is clean.

## Auth and session caching

- The `authenticated_page` fixture loads a cached storage state (2 to 3 s
  instead of a 65 s login).
- First run: logs in through the UI and saves browser storage state.
- Later runs: reload the cached state, validate it, log in again if
  expired.
- `tests/shared/auth_state.py` names the cache file by server and xdist
  worker (`.auth_state.<worker>.json`), so workers never race on 1 file.

## Environment config

- `ENV` selects `config/env/<ENV>.py`. The default is `qa`. Every env file
  has the same flat shape: `base_url`, `media_host`, `allow_write`,
  `default_site_id`, `test_site_name`, `test_camera_name`,
  `test_chat_user_search`, `test_chat_user_name`, `camera_capabilities`
  and `without`. `get_credentials()` reads `QA_USER` and `QA_PASSWORD`
  from `.env`.
- `media_host` is the wss host the app's live player opens. The stream
  guard and `tools/stream_probe.py` open it to count frames. Read it from
  the browser's network tab on a playing tile (the request whose path is
  `/v3/api/ws`).
- The site and the camera may stay blank. At session start the run then
  reads them from the server (`tests/shared/api/discovery.py`): the first
  site by name that is registered and has a camera, and the first camera
  of that site by name. By name, never by the server's order, which
  changes when a camera is added. A configured name is checked at session
  start, and a name the server does not know stops the run with the names
  it does know, exit code 7, like the preflight. The run record and the
  run page name the site and the camera either way.
- `allow_write` is the env guard. Where it is False, the create and delete
  suites (`admin_users`, `admin_rules`, `admin_sites`, `bookmark`,
  `sequences`) skip. The skip reason names the flag. The guard reads a
  test's markers, never its keywords, because a parametrize id that spells
  a marker name is not a marker.
- `without` maps a marker to the reason this server cannot run it
  (`"lpr": "no plate camera on this server"`). The collection hook skips
  those tests with that reason, in 0.2 s and without a browser. Fill it
  only after you measured what the server lacks.
- `camera_capabilities` maps a marker (`lpr`, `audio`, `thermal`, `ptz`)
  to the camera it needs. A run selected by that marker (`-m lpr`) drives
  that camera. Empty means the run's camera serves every marker.
- These 3 (the env guard, `without`, `camera_capabilities`) and the
  measured skips below are the only sources of a skip. A test never skips
  on a guess.

## Test data through the API

Build the data a test needs but does not prove through the internal API,
not through the browser. `test_delete_camera_group` gets its group from
the API and proves only the delete. `test_create_camera_group` keeps the
UI path because the create is what it proves.

The client and fixtures live in `tests/shared/api/`. `conftest.py`
registers them. They sign in with `QA_USER` and `QA_PASSWORD` and write to
`default_site_id`, the site that `test_site_name` names, or the site the
session read from the server when that key is blank. The API test repo is
a separate project. Never import from it.

- `api`: a logged-in session for the test site. It fails, with the key
  named, when `QA_USER`, `QA_PASSWORD` or `default_site_id` is missing,
  when the login fails, or when `default_site_id` is not the site that
  `test_site_name` names.
- `api_camera_group`: `make(name=None, channel_ids=None)` returns the
  created group. The default holds the configured test camera.
- `api_bookmark`: `make(comment=None, camera_id=None, ...)` returns the
  created bookmark.
- `api_saved_view`: `make(name=None, channel_ids=None, grid="2x2")` returns
  the created My Views card. `test_drag_saved_view_to_tile` uses it and
  proves only the drag.

Rules for any new fixture:

1. Every name starts with `AutoTest ` so a leftover on the shared server
   is recognisable. The fixtures refuse other names.
2. Verify the write with a read before the test gets it. The envelope
   text is not a signal: `addgroup` answers `Successfully Retrieved!`,
   and a bookmark `DELETE` answers `Successfully deleted!` while the row
   stays in the list with `deletedAt` above 0 (a live row holds -1).
   Check `code`, then confirm in `location/tree` or the list.
3. The fixture deletes what it made at teardown and confirms the removal.
   A survivor fails the test with its id.
4. Read what the UI reads. A camera group in Admin > Sites is a *location*
   in the API (`site/config/{site}/location`, `location/tree`,
   `deletelocation`). The API's groups (`addgroup`, `grouptree`) are a
   different entity the Admin UI never shows. A saved view in Views > My
   Views is a *preset* (`GET/POST /REST/preset`, `DELETE /REST/preset/{id}`).
   The spec's UserViewLayouts endpoints are never called by the web
   client.
5. Create the data before the page renders so the UI shows it without a
   reload, and open the site the API wrote to by name.

## Missing artifacts and skips

A test whose artifact is absent has proved nothing, so it must never
report green. A skip uploads to QA Touch as Blocked, never Passed. Skip is
still the weakest outcome, and 4 rules keep it honest.

1. Create what the UI can create. A clip, folder, bookmark, user or saved
   view the test could have made is not a reason to skip. Make it, prove
   the behaviour, remove it. Owning the artifact also keeps rename, move
   and delete off a real user's data on the shared server.
2. A skip must prove its precondition first. "No maps found" and "the
   panel never loaded" read the same in a report, and yellow gets scrolled
   past. Prove the surface loaded, then report absence. If it did not
   load, fail. `tests/shared/helpers/surface.py` is that check in 1 call:
   `require_items` waits for the rows, then decides between an empty
   surface (skip) and a surface that never rendered (fail).
   When the artifact comes from a server job rather than a panel, the
   proof is the job's own answer: `tests/shared/helpers/search_job.py`
   follows the Events and Search pages' search job (start, polls,
   completion) and `require_results` skips only on a job that reached
   100% with nothing, naming the job, its scope and its counts. A click
   that sent no job, a job that never finished, or a bad response fails.
   When the artifact is the stream itself, the proof is a measurement
   made once per session: `tests/shared/helpers/stream_health.py` opens 1
   media socket to the test camera and counts the frames.
   `conftest.stream_guard` skips the tests marked `livestream` with the
   count when it is 0, or with the codec and browser when this browser
   cannot decode what the channel streams (the server streams H.265.
   Chrome on Linux decodes it only through a GPU's VA-API on a Wayland
   display: `docs/LINUX_H265.md`), and skips nothing when the measurement
   itself failed. Mark a test `livestream` when it needs frames on a tile
   (Save on a view, a drag onto a tile, the player, the bookmarks panel).
3. A skip is never a failure handler. `except Exception: pytest.skip(...)`
   reports the app's own error as Blocked, and it catches the test's
   asserts too. Let the failure raise. The checker rule is
   `skip-in-except`. A why-comment on the handler excuses the case where
   the exception really does mean absence.
4. A skip reason states a measurement, not a guess. "may not be supported
   in current app version" is a hypothesis written into a green run, and
   it stays there for months because nobody reads a skip. Probe the
   surface (`tools/explore_app.py`), then write what is on screen. The
   checker rule is `speculative-skip-reason`.

A test that skips on every run is dead coverage, not a passing test. Check
the run record for skips that never turn green.

## Markers

Defined in `pytest.ini`. The main groups:

- **Type:** `smoke`, `sanity`, `ui`
- **Feature:** `admin`, `views_devices`, `events`, `search`, `media`,
  `maps`, `chats`, `licenses`, and the rest
- **Meta:** `slow` (over 30 s), `intermittent` (fails now and then. Never
  `flaky`, see Reruns), `livestream` (needs frames on a tile, the stream
  guard decides)

Run examples: `pytest -m smoke`, `pytest -m "admin and not slow"`.

## QA Touch mapping

Nothing uploads unless you pass `--qatouch-upload --qatouch-run <key>`.
The rules that hold whether or not the team uploads:

- **Mapping lives in `config/qatouch_case_mapping.json` only** (node id to
  case key). The reporter also honors a `@pytest.mark.qatouch("KEY")`
  marker, but the test files carry none, and the checker refuses one. Add
  new mappings to the JSON, never to a test file.
- **Unmapped tests still run.** Mapping affects result reporting only,
  never pass or fail.
- **A mapping row is a proposal until a human reviews it.** The reporter
  uses only rows with `"reviewed": true`.
  `python tools/qatouch_mapping.py list-unreviewed` lists the rest.

The upload path and the API traps are in
[QA_TOUCH_INTEGRATION.md](QA_TOUCH_INTEGRATION.md).

## Code notes

- **No ticket keys in code.** Jira numbers change and go stale. Code
  outlives them. Comments, docstrings, and skip or error messages
  describe the BEHAVIOR ("folder delete does not apply on the server").
- **Comments follow the code's writing principles**: concise, direct,
  nothing twice. Keep the why and the measured fact. Drop history
  narration and anything the code already says.
- A tool parameter that callers pass and the body never reads is marked
  `# noqa: ARG001 - <why>`, never renamed away.

## Step capture (optional, for a headed review)

`step_capture.mark()` marks the logical steps of a test. A headed run with
`--verify-mode` then captures a screenshot after each step into
`verification_output/screenshots/`, and `--step-review` asks for a verdict
in the terminal after each step. Both are off by default.

It is **opt-in, not universal**: about a third of the test files wire it
up. A test without it runs normally and is invisible to `--verify-mode`.
Do not retrofit it across the suite for consistency alone.

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
```

**Rules:**

- Write descriptions for QA reviewers, not developers. Present tense.
- One mark per logical step, not per line of code.
- Call mark AFTER the action completes, so it captures the resulting
  state.
- Step numbers are sequential and start at 1.
- The step text in `.mark()` must match the `action` text in the JSON
  sidecar under `tests/steps/ui/{module}/`, when one exists.

**Review run:** `pytest --headed --slowmo 300 --verify-mode -k "test_name"`

## Drag and drop

All drag-and-drop tests must use the visible-drag helper, never raw
`drag_to()`. It highlights the source (red border) and target (green
border) so testers can see the drag in headed mode. The current
implementation is `_visible_drag()` in
`tests/ui/views/test_views_subtabs.py`. Promote it to `ViewsPage` when a
second module needs it. For a drag that hangs under headed Chrome on a
Wayland display, `drop()` in `tests/shared/helpers/drag.py` fires the
drag events from JavaScript.

## Critical rules

- Never hardcode URLs or credentials. Use `config/env/qa.py` and `.env`.
- Always use page objects. Centralize selectors.
- Never add `-q` to a pytest command. `pytest.ini` already has one, and
  2 make `-qq`, which hides the pass count. See `tools/collect_floor.py`.
- Never add `--dist` on the command line. `pytest.ini` sets `loadgroup`,
  and the run refuses to start with another.

## Linting (ruff)

- Config: `pyproject.toml`. Playwright and pytest-aware rule families (PT,
  T20, ARG, B, UP, SIM, RUF, I, RET, LOG, ASYNC, plus pycodestyle and
  pyflakes).
- `python -m ruff check .` must find nothing. The pre-commit hook and CI
  run it.
- Not BLE (blind except): the rule on `except Exception` is a why comment,
  inline or on the line above, and the convention checker enforces it
  (`except-without-why`). Not SIM105 (`contextlib.suppress`), which would
  hide that comment, and not SIM102, where a nested if carries its own
  comment.
- Per-file ignores live in `pyproject.toml`: tests/ allow unused imports,
  unused variables and arguments, `print()`, `assert False` and 3
  pytest-style rules (PT004, PT005, PT012). tools/ and run.py allow
  `print()`, and tools/ imports after the path shim. conftest.py allows
  `print()`. conftest.py and plugins/ allow the unused arguments pytest
  hook signatures name.

## Convention checker

Ruff checks Python style. `tools/convention_check.py` checks the rules on
this page that ruff cannot see. Run both before every commit:

```
python -m ruff check .
python tools/convention_check.py
```

- **HIGH, blocks the commit:** a sleep (`wait_for_timeout` or
  `time.sleep`) with no why-comment. `@pytest.mark.qatouch` in a test
  file. A `pytest.skip` raised from an except handler. An except handler
  with no why-comment that neither re-raises nor fails
  (`except-without-why`). And, on added lines, a new UI test without a
  `Steps:` block.
- **HIGH on added lines:** a test whose checks only say that something is
  there (`presence-only-oracle`). `count() > 0` is presence, and the words
  of an assert message do not count. Say what the action changed: a
  value, a count against a baseline, a text, a state, or that the other
  page's marker is gone. If the check is in a page-object call that
  raises, write a comment with the word "oracle" that names the call.
- **HIGH on added lines:** an action that waits for its element (`click`,
  `fill`, `hover`, `wait_for`, `inner_text` and the like) with no
  `timeout=`, in a `try` whose handlers do not raise
  (`swallowed-default-timeout`). When the element is absent, the action
  waits 30 s, the handler hides the timeout, and the test passes. Ask
  first with `is_visible()` or `count()`, or give the action a short
  `timeout=`.
- **MEDIUM, warns:** absolute `count() > 0` oracles, `img[src]` icon
  locator guesses, hardcoded site or camera names (the ones
  `config/env/qa.py` holds), a skip reason that guesses at the app, a test
  body with no oracle, a DOM wait of a minute or more
  (`long-blind-wait`), `.first` on a text lookup
  (`first-on-text-lookup`), `.first`/`.last` on a union selector, bare
  early returns, Jira keys in code, and a new test without a title or
  without a mapping row.

The default mode checks only the lines added since HEAD, so debt in files
you did not touch never blocks you. `--base <ref>` widens the diff (use it
before pushing a branch: `--base origin/main`). `--all` scans every test
file and reports the standing debt.

Every rule started as a defect found in review or in a run. When a review
finds a new class, it gets a rule the same day, so the class cannot recur
in new code while the old instances are worked down.

A sleep earns its comment by naming the missing signal ("canvas pacing",
"server ack has no DOM signal"), not by restating the sleep.
