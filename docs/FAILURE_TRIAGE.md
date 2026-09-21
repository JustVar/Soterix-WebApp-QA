# Failure triage

This file tells you how to find the cause of a failed test. Start with the
table. It covers the failures that have one known cause.

## Start here

Open the run's `run.html` first. On your machine it is at
`reports/runs/<run>/run.html`. For a nightly run it is in the archive at
`https://10.2.0.2:8444/qa-runs/`.

| What you see | Check | Verdict | Action |
|---|---|---|---|
| A `read this first` section in the terminal summary, or a list below the verdict in `run.html` that starts with `One cause,` | The line names an error that 5 or more failures share, a skip reason that more than 20 skips share, or tests that did not run. | The run has 1 cause. | Correct that cause before you open a single failure. |
| The run stopped at once with a `PREFLIGHT:` line and exit code 7 | The line says if the tenant did not answer or if it refused the account. It quotes the tenant's message. | No test ran. The tests are not at fault. | Correct the tenant problem or the account pair in `.env`, then run again. `PREFLIGHT=off` skips the check. |
| A failure with a `[LOGIN]` line | The line quotes the text on the login form: an error, a captcha or a lockout. | The tenant refused the login. | Correct the account. The later tests in that process fail with the same line and do not submit the form again. |
| A locator timeout, and the FAILED screenshot shows the login form | The traceback ends with a `[SESSION]` section. | The server dropped the session. The locator is not at fault. | Run the test again. See register row 75. |
| `no search job was sent ... site/search answered HTTP 400` | Run the test alone. If it passes, a different search held the slot. | The server runs 1 search job at a time. | See register row 100. Do not change the test. |
| Livestream tests skipped, and the reason starts with `box <name> streams` or `box <name>: the media socket` | Read the reason. The terminal also has a `[STREAM]` line below `stream guard`. | The reason gives 1 of 3 causes: this browser cannot decode the codec, the camera sent 0 frames, or the decode check did not run. | For the browser on spartan1, read "A leg is missing" in `deploy/spartan1/README.md`. On a laptop, use Google Chrome, not Chromium. For 0 frames, check the camera in the app. |
| A locator timeout, and the screenshot shows the correct page | Open the trace and read the DOM snapshot at the failed action. | A renamed site or camera, or a changed control. | For renamed tenant data, correct `config/env/qa.py`. For a changed control, correct the page object. |
| A control shows a spinner that does not stop, and no request leaves | Open the Console tab of the trace. | A Content Security Policy refusal is an app defect. | Report it. See register row 56. |
| A failure whose error says `worker 'gwN' crashed while running` | Read `log/run.log` in the run folder for the last test on that worker. | The browser or the worker stopped. | See register row 91 for the known stall on the box. |
| A test failed in the nightly and passes on your machine | Open the "Tests to watch" table on the health page. | The test is intermittent if it passed and failed in its last 20 runs. | Add a register row. Do not add a rerun mark without a row. |
| `THIS RUN WAS NOT ARCHIVED` in the terminal | The line gives the error and the free disk space. | The run has no evidence folder. | Free disk space, then run again. |

If no row fits, open the trace. Then read "Traps" at the end of this file
before you change a wait.

## Where traces come from

Each failed UI test saves a Playwright trace. A trace holds a DOM snapshot
for each action, all network requests, the console messages and a timeline.
You do not need to run a test again to see what happened.

2 mechanisms record traces. Both keep a trace only when the test fails.

- The `--tracing=retain-on-failure` flag in `pytest.ini` covers tests that
  use the plugin's `page` fixture.
- The `authenticated_page` fixture in `conftest.py` records its own trace.
  It makes its own browser context, which the plugin flag does not see.
  Most UI tests use this fixture.

During a run, traces go to `reports/artifacts/` as `<test-id>-trace.zip`. A
failed login also saves a trace with the name
`<test-id>-login-failure-trace.zip`.

The `authenticated_page` fixture also records a video of each test and keeps
it only on failure, as `<test-id>-video.webm` in the same folder. Set
`RECORD_VIDEO=off` to skip the recording.

Each run empties `reports/artifacts/` at its start. You do not lose the
traces: at the end of each run the archive copies them to
`reports/runs/<run>/traces/`. Only a run with `RUN_ARCHIVE=off` leaves its
traces in `reports/artifacts/` alone.

A trace from a nightly run stays on spartan1. To get one, do the procedure
"Get a trace from a nightly run" in `deploy/spartan1/README.md`.

A trace holds a session cookie, and sometimes a password. Do not attach a
trace to a ticket or a chat.

## Where run outputs live

The live outputs hold only the latest run. Each run overwrites
`reports/report.html`, empties `reports/screenshots/`, and wipes
`reports/artifacts/`.

The archive keeps the evidence of past runs. After every run,
`plugins/run_archive.py` copies the report, the screenshots, the traces, the
videos, and the results JSON to `reports/runs/<start-time>__<target>/`. Open
`reports/runs/index.html` to browse the archived runs, newest first. The
archive keeps the newest 20 runs of each target, 100 runs in total, and
no more than 10 GB (`QA_ARCHIVE_MAX_GB` changes that). The oldest runs go
first. Repeated runs of one test do not push out a full-suite archive. Set
`RUN_ARCHIVE=off` to disable it.

Start a triage at the run's `run.html`. It opens with a one-sentence
verdict (`3 of 49 tests failed - 2 new failures, 1 still failing; 1 test skipped.`)
and lists the failures first. Failures that share an error sit
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

Each UI test that reaches its body gets 1 final screenshot with the label
PASSED or FAILED. A test whose setup failed with a page open gets the label
SETUP FAILED. A drag test also keeps up to 8 frames from the middle of the
drag. The files are in `reports/screenshots/` during the run and in
`reports/runs/<run>/screenshots/` after it. `run.html` shows them on each
test.

Set `REPORT_SCREENSHOTS=off` to stop the screenshots. The trace also holds a
screenshot of each action.

## Traps

The app taught us these. Each one cost a diagnosis round or more. Read
them before you blame the timing.

The table in "Start here" covers the run-level signals: "read this first",
`PREFLIGHT:`, `[LOGIN]`, `[SESSION]` and the stream guard. Without those signals, a
tenant that is down or a browser that is missing reads as hundreds of
timeouts that look unrelated.

### Locators

- **`get_by_text` matches a part of the text.** On the Admin > General
  cards it clicked the Audit text ("...re-VIEW all activities") and not the
  View button. Use `exact=True` for a short label.
- **Attribute matches are case-sensitive.** The icon for a muted
  notification is `UnMuteNotification`, with a capital M.
  `src*='MuteNotification'` matches the 2 states.
- **Some inputs share 1 class.** The chat panel has 4
  `input.chat-search-input` elements. Use the placeholder and the
  visibility, not the shared class alone.
- **The app keeps hidden copies in the DOM.** `.first` or `.last` on a union
  can give a hidden element in a different container. Filter on visibility,
  or start from the container.
- **A page-wide checkbox locator finds switches behind an open modal.** The
  backdrop stops the click for the full timeout. Start from the modal panel.
- **A name that you put into a selector fails in 2 ways.**
  - `:has-text('{name}')` ignores case and matches a part of the text.
    `tr:has-text('ac')` matched each "Black List" row. A row filter can also
    match the TYPE column and not the name cell. Give `has=` the name cell.
  - A name that contains a quote breaks the CSS parser.
  - The fix is `get_by_text(exact=True)`. Its only new failure is a loud
    timeout with 0 matches, not a wrong element. The recipe and the evidence
    are in TEST_REPAIRS rows 14 and 18 to 20.

### Waits and signals

- **A new login is not complete when the URL leaves /auth/login.** The
  landing page then runs its session check, the site tree and the status,
  approximately 3 s later. A `goto` in that time stops them. The app then
  goes back to /auth/login and drops its cookie. Wait for the nav and for
  the API to go quiet first. The `authenticated_page` fixture does this.
- **A control that shows a spinner, sends no request and does not finish is
  not a slow server.** Open the Console tab of the trace. A Content Security
  Policy refusal rejects the app's promise with no toast and no request. The
  view Save did this: the app fetched its own `data:image/png` thumbnail,
  and `connect-src` has no `data:`. Read the console before you blame the
  stream. TEST_REPAIRS row 56.
- **A locator timeout with the login form in the FAILED screenshot is a
  session drop.** The server answered 401 to a live session, for all the
  parallel calls of the page, and the app went to /auth/login. The traceback
  ends with a `[SESSION]` section when this occurs. The 401 responses in the
  trace give the exact moment. TEST_REPAIRS row 75.
- **`no search job was sent ... site/search answered HTTP 400` does not mean
  that the request is wrong.** The same request answers 200 when it runs
  alone. The server runs 1 search job for each account, so the search of a
  different worker held the slot. On the Videonetics site a job runs for
  minutes. TEST_REPAIRS row 100.
- **Empty video tiles keep their spinners.** Do not wait for
  `CircularProgress` to hide on a tile grid. The played signal is a new
  `video` element after the baseline.
- **Rows that render again and again do not pass Playwright's stability
  check.** Camera rows refresh their snapshot. Use a click with a short
  timeout, then a JS click as the fallback. For a MUI checkbox, click the
  inner input. For a custom checkbox, click the element.
- **The same is true for a control that those rows show on hover.** The
  Create Zone / Create Line link on the Search page showed, and then its
  click timed out for 30 s with the link on the screen. A hover that works
  does not prove that the click lands.
- **Those rows also break `filter(has=...)`.** Playwright evaluates the inner
  match again on each action, the repaint wins, and the child times out.
  Match the name one time, then use a positional `.nth(i)`. In an A/B test
  against HEAD, the filter failed 1 time and the positional form passed 2
  times, with the same names.
- **Toggle controls open and close with the same click.** The chat icon,
  the notification bell, the LPR panel header and the view tabs are toggles.
  Click only when the open marker is absent.
- **The chat search drops a single programmatic input event after it
  opens.** Type key by key with `press_sequentially`, and type again one
  time if the text is absent.
- **Search filters run on the server, and the old rows stay visible while
  they run.** Wait for the count to leave the unfiltered baseline before you
  use a "filtered" row. The delete-user test almost deleted a wrong user
  this way.
- **Tables show a placeholder row ("No data available") and empty spacer
  rows while they fetch.** The first-record wait ignores the two.
- **A View click on a card page during hydration does nothing.** Try one
  more time.
- **A drag that is not forced can complete and land nothing.** Try one more
  time with force. When a panel floats over the left tiles, drop on the last
  empty tile.
- **On spartan1, a pointer drag can stop Chrome for good.** Chrome on the
  Wayland display stops drawing in the middle of some drags. The drag call
  does not return, its timeout does not fire, and each later call on the
  page hangs, the after-test screenshot included. The sign is a test that
  ends at the run's per-test timeout with its last log line before a drag.
  Use `drop()` from `tests/shared/helpers/drag.py` for a drag that hung:
  on that display it fires the drag events from JavaScript. First make
  sure that the app accepts those events for that element. The LPR widget
  card does not. TEST_REPAIRS row 91.
- **The live player sometimes shows "The camera failed to load" over a frame
  that renders.** Click its refresh link one time
  (`recover_stream_if_failed`).
- **An action with no `timeout=` in a `try` that hides the failure costs a
  silent 30 s.** When the element is absent, the action waits the default
  time and the test passes. A test that takes the same long time each night
  is the sign. TEST_REPAIRS row 102.

### Tools

- **A probe that reads `QA_USER` directly ignores `BOX`.** It logs in to the
  default tenant, and its screenshot then shows the wrong box. Session
  caches have the same trap: 1 shared file lets an india session answer a us
  probe. The probes and the caches go through `tests/shared/auth_state.py`,
  which keys the cache on the base URL and the box. To check, read the login
  line that the tool prints.

### Oracles

- **A test that returns early passes, and its asserts do not run.** The
  checker rule `early-exit-pass` finds a bare `return`.
- **`expect.soft` is an oracle.** pytest-playwright raises the soft failures
  at the end of the test.
- **A toast wait that hides its own timeout lets a failed action pass.** Use
  the browser download event, the row count or the change of `src`.
- **Search results arrive in parts, and the grid moves as the cards land.**
  `SearchPage._results_settled` waits for 2 s with no change in the count
  before a test hovers a result.
- **A search is followed by its server job, not by the first thumbnail.**
  This applies to the Events page and to each Search category
  (`tests/shared/helpers/search_job.py`). Read the line that the helper
  writes:
  - `search job N (EVENT, 22 channels, 7.0 days): 12 polls in 14.2 s, 100%
    complete, 0 events counted` is a SKIP. The tenant has no such data.
  - `no search job was sent within 15 s` is a FAIL. The filters did not
    change, and the app ignores a search that repeats.
  - `never reported the job complete` is a FAIL on the server side.
  - Before this helper, each of these looked like `Locator.wait_for: Timeout
    60000ms`.
- **A pick in a Search dropdown applies at once.** The value text leaves
  "Select" and the item unmounts. No wait is necessary after a pick.
- **Verify a page-object change on a quiet tenant.** A run that timed out
  leaves Chrome processes that hold sessions, and each batch after it fails
  at setup. Close the Chrome windows that the run left before you verify
  again. If a full family of tests fails after a change, do an A/B test of
  the file against HEAD in the same time window before you change the code.
- **A login from a probe tool meets a period where the sidebar links have
  `pointer-events:none`.** The period can be 30 s or more. Tests do not see
  it, because `authenticated_page` uses the cached session. When the timing
  is important, probe through a temporary pytest test on the cached session.
- **When a new oracle fails, record the write responses before you blame
  the test.** Use `page.on('response')` for the `/REST/` calls that are not
  GET. The 2 `admin_users` failures were the server: it answered 400, and
  the UI showed an empty alert.
