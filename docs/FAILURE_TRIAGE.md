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

**Each pytest run clears `reports/artifacts/` at start.** Copy a trace out of
the folder before you start the next run if you want to keep it.

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
