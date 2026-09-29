"""Pins for plugins/wall_clock.py: a test that never ends costs the run 1 failure and its cap, not the night.

On 09/20/2026 two full UI runs sat in a teardown on a dead browser
until the 4 hour run cap. The scenario runs for real in a subprocess.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins import wall_clock  # noqa: E402

SCENARIO = REPO_ROOT / "tests" / "plugins" / "wall_clock_scenario.py"


@pytest.mark.parametrize(("timeout_s", "environ", "cap"), [
    (600, {}, 1320.0),                       # 2 x 600 + 120: pytest-timeout gets its chance first
    (0, {}, 0.0),                            # --timeout=0 is a debug run: no cap
    (600, {"TEST_WALL_CAP": "45"}, 45.0),
    (600, {"TEST_WALL_CAP": "0"}, 0.0),      # off
    (600, {"TEST_WALL_CAP": "soon"}, 1320.0),
])
def test_the_cap_follows_the_timeout_unless_the_environment_sets_it(timeout_s, environ, cap):
    """Twice the per-test timeout plus 120 s, or TEST_WALL_CAP, and 0 turns it off."""
    assert wall_clock.wall_cap(timeout_s, environ) == cap


def test_a_plain_session_gets_the_message_and_keeps_running(monkeypatch, capsys, tmp_path):
    """A person at the keyboard is not ended: the line goes to stderr and no exit is called."""
    exits = []
    monkeypatch.setattr(wall_clock, "_exit", exits.append)
    monkeypatch.setenv("WALL_CLOCK_LOG", str(tmp_path / "wall_clock.log"))
    wall_clock._expire("tests/ui/x/test_x.py::test_y", 30, in_worker=False)
    assert exits == []
    assert "[WALL-CLOCK] tests/ui/x/test_x.py::test_y did not end in 30 s" in capsys.readouterr().err
    wall_clock._expire("tests/ui/x/test_x.py::test_y", 30, in_worker=True)
    assert exits == [wall_clock.EXIT_CODE]


def test_a_teardown_that_never_returns_costs_one_failure_and_the_cap(tmp_path):
    """Under -n 2 with a 5 s cap: the stuck test fails once as a crash, the 6 others pass, and the run ends by itself."""
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\naddopts = -p no:cacheprovider --dist loadgroup\n", encoding="utf-8")
    env = {**os.environ, "RUN_GUARD": "off", "RUN_ARCHIVE": "off", "REPORT_SCREENSHOTS": "off",
           "PREFLIGHT": "off", "PYTHONPATH": str(REPO_ROOT), "TEST_WALL_CAP": "5",
           "WALL_CLOCK_LOG": str(tmp_path / "wall_clock.log")}
    start = time.monotonic()
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(SCENARIO), "-n", "2", "-p", "plugins.xdist_recovery", "-p", "plugins.wall_clock",
         "-c", str(tmp_path / "pytest.ini"), "--rootdir", str(tmp_path), "--timeout=0", "-rfE", "-v"],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=150, check=False)
    took = time.monotonic() - start
    out = proc.stdout + proc.stderr
    # the worker's stderr is captured and lost with the worker: the log file holds the reason
    logged = (tmp_path / "wall_clock.log").read_text(encoding="utf-8")
    assert "test_stuck_in_teardown did not end in 5 s" in logged
    assert "crashed while running" in out, out[-2000:]
    assert "test_stuck_in_teardown" in out, out[-2000:]
    # 7 passed: the 6 ordinary tests, and the body of the stuck one, which passed before its teardown hung
    assert "1 failed, 7 passed" in out, out[-1500:]
    assert took < 120, f"the run took {took:.0f} s: the cap did not end the stuck test"
