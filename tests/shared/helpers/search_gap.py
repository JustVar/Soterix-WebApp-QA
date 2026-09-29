"""Space searches so the account's one search job has freed before the next.

The QA server runs ONE search job for the whole server (not per account: a
search from one account is refused while another account's job holds the
slot) and offers no cancel: not a REST call (14 shapes tried, all 404/400),
not a WebSocket frame (none sent around a search), and not logout (the job
outlives the session). The slot frees only about 16 s after the client stops
polling, or when the job completes, which is minutes for a 30-day analytics
scan on a busy site (all measured). So a test's search that lands inside the
16 s after the previous search test's page closed answers code 400, and the
collision is with the PRIOR test's job, not between concurrent workers: it
happened even in a single serial process.

This helper records when a searching test's page closed (its polling
stopped) and, before the next search click, waits only for the remainder
of the free window. The wait overlaps the next test's setup and navigation,
so the cost per search test is a few seconds, not the full window. The
timestamp is one file for the server (every account shares the slot) so it
holds across xdist workers and across accounts; the tests
that search also share the `account_search` xdist group (a static
`pytestmark` in every tests/ui/search and tests/ui/events module, with
`--dist loadgroup` in pytest.ini) so they run on one worker and two
workers never click inside one window. The marker must be static: a
marker added in a conftest collection hook lands after xdist's own
node-id rewrite and the group is silently ignored (measured).
"""
from __future__ import annotations

import os
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
STAMP_DIR = REPO_ROOT / "logs"
# measured: a fresh POST answered 400 at 5 s and 11 s after polling
# stopped, and 200 at 16 s; 17 gives one second of margin
GAP_S = 17.0
POLL_S = 0.5

_ran_this_test = False


def stamp_path() -> Path:
    # one stamp: the search slot is server-wide, shared by every account
    return STAMP_DIR / ".search_stopped.stamp"


def mark_ran() -> None:
    """Called by watch_search: this test ran a search job."""
    global _ran_this_test
    _ran_this_test = True


def ran_this_test() -> bool:
    return _ran_this_test


def note_stopped() -> None:
    """Record now as the moment this test's search polling stopped (its
    page has closed). Called from the root conftest after teardown, only
    for a test that ran a search; clears the flag."""
    global _ran_this_test
    STAMP_DIR.mkdir(parents=True, exist_ok=True)
    stamp_path().write_text(repr(time.time()), encoding="utf-8")
    _ran_this_test = False


def seconds_until_free() -> float:
    """How long until the previous search's job has freed the slot; 0
    when there was no previous search or the window has passed."""
    try:
        stopped = float(stamp_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):  # why: no stamp yet, or a stamp mid-write; no wait is the right answer
        return 0.0
    return max(0.0, stopped + GAP_S - time.time())


def wait_for_gap() -> float:
    """Sleep until the previous search test's job has freed the slot.
    Returns the seconds waited (0 when nothing to wait for)."""
    remaining = seconds_until_free()
    waited = 0.0
    while remaining > 0:
        step = min(POLL_S, remaining)
        time.sleep(step)  # the free window is a server-side timer with no signal to wait on
        waited += step
        remaining = seconds_until_free()
    return waited
