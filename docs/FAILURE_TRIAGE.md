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

Start a triage at the run's `run.html`. It lists the failures first. Each
failure shows the error message, the failing Playwright action with its call
log, the 15 actions before it, the console errors, every screenshot of the
test (final and mid-drag), the video clip, and the exact `show-trace`
command for its trace. Passed and skipped tests sit below in collapsed lists
with their screenshots. `python -m plugins.run_report latest` rebuilds the
page for the newest run, or pass a run folder.

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

Waits and signals
- Empty video tiles keep placeholder spinners alive forever - never
  wait for CircularProgress hidden on tile grids; a new `video`
  element past the baseline is the played signal.
- Rows that re-render continuously (camera rows refresh their
  snapshot) never pass Playwright's stability check; use a bounded
  pointer click with a JS-click fallback (on the inner input for MUI
  checkboxes, on the element itself for custom ones).
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
