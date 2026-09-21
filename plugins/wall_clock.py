"""A hard wall-clock cap on one test: setup, call and teardown together.

pytest-timeout arms one timer for a test. When a browser stops answering, that
timer ends the call, and then the teardown asks the same dead browser to close a
tab or stop a trace. That second call never returns, and no timer is left to
end it. On 09/20/2026 the us leg of the nightly sat in such a teardown
for 3.5 hours, until the 4 hour run cap, and the india leg did the same after 6
workers had died on the same cause (register row 91, a pointer drag that stops
Chrome on the box's display).

This plugin starts one timer when a test starts. If the test has not ended
after the cap, the plugin says so on stderr and ends the process:

- In an xdist worker, the process is the worker. plugins/xdist_recovery.py
  then makes that 1 failed test, and a new worker takes the rest of the run.
- In a plain session, the message is all it does: a person is at the
  keyboard, and a debugger that holds a test open is not a fault.

The cap is 2 times the per-test timeout plus 120 s, so a test that pytest-timeout
can end by itself always gets that chance first. `TEST_WALL_CAP=<seconds>`
sets it, and 0 turns the plugin off. A run with `--timeout=0` has no cap.

The message also goes to `logs/wall_clock.log`: a worker's stderr is
captured, and what it holds is lost when the worker ends. xdist's own failure
text names the test ("worker 'gw0' crashed while running ..."), and the log
file says why.
"""
from __future__ import annotations

import os
import sys
import threading
import time
from collections.abc import Mapping
from pathlib import Path

import pytest

CAP_ENV = "TEST_WALL_CAP"
LOG_ENV = "WALL_CLOCK_LOG"   # the pins point this at a temp file
LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "wall_clock.log"
SLACK_S = 120.0
EXIT_CODE = 3   # the same code as the screenshot watchdog: a worker that was ended on purpose


def _exit(code: int) -> None:   # a seam for the pins
    os._exit(code)


def wall_cap(timeout_s: float, environ: Mapping[str, str]) -> float:
    """Seconds one test may take in total. 0 means no cap."""
    raw = (environ.get(CAP_ENV) or "").strip()
    if raw:
        try:
            return max(float(raw), 0.0)
        except ValueError:
            pass   # a bad value falls back to the rule below
    return 2 * timeout_s + SLACK_S if timeout_s > 0 else 0.0


def _item_timeout(item: pytest.Item) -> float:
    """The per-test timeout that pytest-timeout uses for this item: the marker, else the option or ini value."""
    marker = item.get_closest_marker("timeout")
    value = None
    if marker is not None:
        value = marker.args[0] if marker.args else marker.kwargs.get("timeout")
    if value is None:
        value = item.config.getoption("timeout", None)
    if value is None:
        try:
            value = item.config.getini("timeout")
        except (KeyError, ValueError):
            value = None
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _expire(nodeid: str, cap_s: float, in_worker: bool) -> None:
    msg = (f"[WALL-CLOCK] {nodeid} did not end in {cap_s:g} s (setup, call and teardown together). "
           "A call that does not return keeps a test alive after its timeout was used, or with no timeout set"
           + (": ending this worker so the run goes on." if in_worker
              else ". This is a plain session, so it is left to the person who runs it."))
    print("\n" + msg, file=sys.stderr, flush=True)  # noqa: T201 - the one line a person must see when a test is ended
    try:
        log_file = Path(os.environ.get(LOG_ENV) or LOG_FILE)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}\n")
    except OSError:
        pass   # the log is a second copy of the message; the exit below is what matters
    if in_worker:
        _exit(EXIT_CODE)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_protocol(item: pytest.Item, nextitem: pytest.Item | None):
    # each rerun is one more full attempt inside this same protocol call
    reruns = int(item.config.getoption("reruns", None) or 0)
    cap_s = wall_cap(_item_timeout(item), os.environ) * (reruns + 1)
    timer = None
    if cap_s > 0:
        # workerinput, not PYTEST_XDIST_WORKER: a plain pytest that a worker started as a
        # subprocess inherits that variable, and it is not a worker
        in_worker = hasattr(item.config, "workerinput")
        timer = threading.Timer(cap_s, _expire, args=(item.nodeid, cap_s, in_worker))
        timer.daemon = True
        timer.start()
    try:
        yield
    finally:
        if timer is not None:
            timer.cancel()
