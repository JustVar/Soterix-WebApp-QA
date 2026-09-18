# Failure triage with Playwright traces

Every failed UI test now saves a Playwright trace. A trace holds a DOM snapshot
for each action, all network requests, console messages, and a timeline. You no
longer need to rerun a flaky test to see what happened.

## Where traces come from

Two mechanisms record traces. Both keep a trace only when the test fails.

- The `--tracing=retain-on-failure` flag in `pytest.ini` covers tests that use
  the plugin's `page` fixture.
- The `authenticated_page` fixture in `conftest.py` records its own trace,
  because it creates its own browser context and the plugin flag does not see
  it. Most UI tests use this fixture.

Traces land in `reports/artifacts/` as `<test-id>-trace.zip`. A failed login
also saves a trace, named `<test-id>-login-failure-trace.zip`.

The `authenticated_page` fixture also records a video of every test and keeps
it only on failure, as `reports/artifacts/<test-id>-video.webm` next to the
trace. Set `RECORD_VIDEO=off` to skip the recording.

**Each pytest run clears `reports/artifacts/` at start.** Copy a trace out of
the folder before you start the next run if you want to keep it.

## Where run outputs live

The live outputs hold only the latest run. Each run overwrites
`reports/report.html`, empties `reports/screenshots/`, and wipes
`reports/artifacts/`.

The archive keeps the evidence of past runs. After every run,
`plugins/run_archive.py` copies the report, the screenshots, the traces, the
videos, and the results JSON to `reports/runs/<start-time>__<target>/`. Open
`reports/runs/index.html` to browse the archived runs, newest first. The
archive keeps the newest 20 runs of each target, and 100 runs in total, so
repeated runs of one test do not push out a full-suite archive. Set
`RUN_ARCHIVE=off` to disable it.

Start a triage at the run's `run.html`. It opens with a one-sentence
verdict ("3 of 49 tests failed - 2 new failures, 1 still failing; 1 test
skipped.") and lists the failures first. Failures that share an error sit
together under "N tests share this error". The error's first line is
compared with numbers, quoted values, hex addresses, and locator text
reduced, so a 30000 ms and a 15000 ms timeout on the same step are one
error. Each failure says "New error" when that error appeared in none of
the previous 20 runs of these tests, or "Seen before (last on <date>)"
with a link to that run. Each failure shows the error message, the failing
Playwright action with its call log, the 15 actions before it, the console
errors, every screenshot of the test (final and mid-drag), the video clip,
and the exact `show-trace` command for its trace. Passed and skipped tests
sit below in collapsed lists with their final screenshots, grouped by
module. Mid-drag frames stay on disk and show only on a failure card.

Every test shows its readable title, its QA Touch case when the node id is
mapped, its duration, a history strip, and a change label. The strip is
one colored block per archived run of these tests, up to 20, oldest left
and newest right. Hover a block for the run's date and outcome, click it
to open that run. "passed 17/20" follows, and "flaky 15%" when the test
both passed and failed in that window. The flaky rate is failures / runs
the test was present in. The change label compares with the previous run
of these tests, named by date under the header: New failure, Fixed, Still
failing, or New test. The filter box at the top narrows the page to the
tests that match a word. `python -m plugins.run_report latest` rebuilds
the page for the newest run, or pass a run folder. `--all` builds the
page of every archived run that has none.

The run's `log/` folder holds `run.log`, with the session's logging and
then the output pytest captured for every passed and skipped test, one
section per test. Each failed test has its own file beside it with its
captured output and traceback. When a page object printed something a
screenshot cannot show, it is there.

`python run.py health` builds `reports/runs/health.html` from the archived
summaries. It opens with one tile per product: runs in the window, pass
rate, tests to watch, modules, and the last run, linked. The modules
follow, grouped under their product. A module is the folder under
`tests/` (Views, Admin, Tools), and every run that touched it counts
toward it, a run of 1 test included. Each group opens with one verdict
line per module ("Views: 96% pass rate over 20 runs, 1 test to watch."),
then a table with the pass rate over test outcomes, the mean duration of
a full-module run, the notes count (the advisory lines, linked to the
newest run's), and the newest run as a date with its outcome in words.
"Show runs" under a module lists its runs: the date, what ran, and the
outcome. Then a "Tests to watch" table: every test that failed at least
once in its last 20 results, with its strip, its flaky rate, and the
date of its last failure, sorted by flaky rate. Check it before you call
a failure new. A run that recorded no product is named by its targets,
so every line carries one.

## View a trace in the GUI

```
venv\Scripts\playwright show-trace reports\artifacts\<name>-trace.zip
```

This opens the trace viewer with the timeline, DOM snapshots, network tab, and
console tab.

## Inspect a trace from the terminal

The `playwright trace` command reads a trace without a GUI. This works in
scripts and in AI-assisted triage.

```
playwright trace open <name>-trace.zip   # extract the trace for inspection
playwright trace errors                  # errors with stack traces
playwright trace actions                 # every action with timing
playwright trace snapshot <id> snapshot  # DOM snapshot at one action
playwright trace requests                # network requests
playwright trace console                 # console messages
playwright trace close                   # remove the extracted data
```

A useful sequence: `errors` tells you what failed, `actions` shows the timing
and the last steps, and `snapshot` shows the DOM at the moment of failure.

Example: on 2026-08-07 the Views suite failed on a site click. The `snapshot`
command showed the site list in the picker. The site was renamed from
"Newtown ActionArea" to "Newtown Action Area". The fix was one line in
`config/env/qa.py`. No rerun was needed.

## Screenshots

`--screenshot=only-on-failure` in `pytest.ini` saves a screenshot for failed
tests that use the plugin's `page` fixture. For `authenticated_page` tests, use
the trace instead. The trace contains a screenshot of every action.

## Traps this app has taught us (check these before blaming timing)

- **The run ended at once with a `PREFLIGHT:` line and exit code 7.** No test
  ran, on purpose: the tenant did not answer, or it refused the account,
  and the line says which, quoting the tenant's own message. Fix the cause
  (the tenant, the account pair in `.env`) and run again; `PREFLIGHT=off`
  skips the check when you need the old behaviour.
- **A test failed with a `[LOGIN]` line.** The form stayed up after submit
  with an error, a captcha or a lockout text on it; the line quotes what
  was on screen. Every later test in that process fails with the same
  line in a second and does not submit the form again, so one refused
  login is one failed attempt, not four hundred.

Measured mechanisms from the 08/2026 rebuilds. Each one cost at least
one diagnosis round; check the list before opening a trace.

Locators
- `get_by_text` matches substrings by default. On the Admin > General
  cards it clicked the Audit blurb ("...re-VIEW all activities")
  instead of the View button. Use `exact=True` for short labels.
- Attribute matching is case-sensitive: the muted-notification icon
  is `UnMuteNotification` (capital M); `src*='MuteNotification'`
  matches both states.
- Several inputs share one class (chat panel: four
  `input.chat-search-input`). Scope by placeholder + visibility,
  never by the shared class alone.
- Hidden mounted copies: `.first`/`.last` on a union can resolve to a
  hidden element in another container. Filter by visibility or scope
  to the container.
- Page-wide checkbox locators inside an open modal resolve to
  switches BEHIND the modal; the backdrop intercepts the click for
  the full timeout. Scope to the modal panel.
- Interpolated identity selectors bite twice: `:has-text('{name}')`
  is a case-insensitive substring (`tr:has-text('ac')` matched every
  'Black List' row, and a row filter can match the TYPE column, not
  the name cell - scope `has=` to the name cell), and a name holding
  a quote crashes the CSS parser mid-selector. The quoted `text='...'`
  engine also matches a bare name text node with sibling content, so
  replacing it with get_by_text(exact=True) narrows: the only new
  failure mode is a loud 0-match timeout, never a wrong pick. Recipe
  and verification evidence: TEST_REPAIRS items 14, 18-20.

Waits and signals
- A fresh login is not over when the URL leaves /auth/login: the
  landing page then runs its session check, site tree and status,
  about 3 s later. A goto in that window aborts them and the app
  bounces to /auth/login and drops its cookie (india traces 09/12 and
  09/14/2026). Wait for the nav and for the API to go quiet first;
  the authenticated_page fixture does.
- A control that turns into a spinner, sends no request and never
  resolves is not a slow server. Open the trace's console (the Console
  tab in the GUI, or the `console` events in trace.trace): a Content
  Security Policy refusal ('Refused to connect because it violates the
  document's Content Security Policy') rejects the app's promise with
  no toast and no request. The view Save did this on 09/12/2026: the
  app fetched its own data:image/png thumbnail and connect-src has no
  data:. Read the console before blaming the stream (TEST_REPAIRS 56).
- A locator timeout whose FAILED screenshot shows the login form is a
  session drop, not the locator. The server answered 401 to a live
  session, in a burst across the page's parallel calls, and the app
  bounced to /auth/login (nightly traces 09/16/2026: india 09:12:24
  and 09:13:17 UTC, us 09:47:54 UTC). The traceback now ends with a
  [SESSION] section when this happened; the trace's 401 responses
  give the exact moment. TEST_REPAIRS 75.
- 'no search job was sent ... site/search answered HTTP 400' on a box
  whose searches are real (cameras online, data to scan) is not the
  request: the same request answers 200 when run alone. The server runs
  ONE search job per account, so another worker's search held it
  (measured 09/16/2026: the API refuses a second POST /REST/site/search
  with code 400 from any session while one is polled). It surfaced when
  india moved to the Videonetics site, where a job runs for minutes; the
  serialisation fix is open (TEST_REPAIRS 78).
- Empty video tiles keep placeholder spinners alive forever - never
  wait for CircularProgress hidden on tile grids; a new `video`
  element past the baseline is the played signal.
- Rows that re-render continuously (camera rows refresh their
  snapshot) never pass Playwright's stability check; use a bounded
  pointer click with a JS-click fallback (on the inner input for MUI
  checkboxes, on the element itself for custom ones).
  The same holds for a control those rows reveal on hover: the Search
  page's Create Zone / Create Line link showed and then timed out its own
  click for 30 s on india (09/15/2026), with the link on screen the whole
  time. A reveal that works is not a click that lands.
- Those same rows break `filter(has=...)`: its inner match is
  re-evaluated on every action, races the repaint, and the child
  (a reveal-on-hover checkbox) times out unreachable. Match the
  name once, then act through a positional `.nth(i)`. Exact naming
  and stability are not in conflict. A/B'd against HEAD 09/03/2026:
  filter 1 failed, positional 2 passed, same names.
- Toggle controls (chat icon, notification bell, LPR panel header,
  view tabs): open only when the open marker is absent, or the
  "open" click closes it.
- The chat search drops a lone programmatic input event after open;
  type key by key (`press_sequentially`) and retype once.
- Search filters run server-side and the pre-filter rows stay
  visible while they run: wait for the count to LEAVE the unfiltered
  baseline before acting on "filtered" rows (the delete-user
  near-miss).
- Tables render a placeholder row ("No data available") and empty
  spacer rows while fetching; the first-record wait filters past
  both.
- Card-page View clicks during hydration are silently dropped; retry
  once.
- Unforced drags can complete without landing anything; retry once
  forced. Drop on the LAST empty tile when a panel floats over the
  left ones.
- The live player intermittently shows "The camera failed to load"
  over a rendering frame; click its refresh link once
  (`recover_stream_if_failed`).

Tooling
- A probe that reads QA_USER directly ignores BOX and logs into the
  default tenant whatever you asked for; its screenshot then argues
  about the wrong box. tools/explore_app.py did this until
  09/03/2026. Session caches have the same trap: one shared file
  lets an India session answer a US probe. Both now go through
  tests/shared/auth_state.py, which keys the cache on base_url AND
  box - the check is the login line the tool prints.

Oracles
- A test that `return`s early passes with its asserts unreachable;
  the checker's early-exit-pass rule flags bare returns.
- `expect.soft` IS an oracle (pytest-playwright raises collected soft
  failures at test end).
- Toast waits that swallow their own timeout let failed actions pass;
  prefer the browser download event, the row count, or the src flip.
- Search results stream in and the grid reflows as cards land;
  `SearchPage._results_settled` waits for two seconds of unchanged
  count before anyone hovers a result.
- A search (Events page, or any Search category) is followed by its
  server job, not by the first thumbnail (tests/shared/helpers/
  search_job.py). Read the line it leaves: "search job N (EVENT, 22
  channels, 7.0 days): 12 polls in 14.2 s, 100% complete, 0 events
  counted" is a SKIP and means the tenant has no such data; "no search
  job was sent within 15 s" is a FAIL and means the filters did not
  change (the app ignores a repeat search); "never reported the job
  complete" is a FAIL on the server side. A "Locator.wait_for: Timeout
  60000ms" on a search is what this looked like before 09/08/2026.
- Search dropdown picks apply on the same tick (value text flips off
  'Select', item unmounts); no settle is needed after a pick.
- Verify page-object conversions on a QUIET tenant: a timed-out run
  leaves orphaned Chrome processes holding sessions (33 found on
  08/14), and every batch after it fails at setup. `taskkill /IM
  chrome.exe` before re-verifying. When a whole family fails after a
  conversion, A/B the file against HEAD in the same window before
  touching the code - the search endpoint's second 400 outage cost
  two hours of chasing a conversion that was neutral.
- Probe harness logins hit a fresh-login window where the sidebar
  anchors carry pointer-events:none for a variable stretch (30s+
  seen); tests never see it because authenticated_page uses the
  cached session. Probe via a throwaway pytest test on the cached
  session when timing matters.
- When a newly un-swallowed oracle fires, capture the write responses
  (page.on('response') for non-GET /REST/ calls) BEFORE blaming the
  test: on 08/17 both admin_users failures were the server answering
  400 with an empty UI alert.
