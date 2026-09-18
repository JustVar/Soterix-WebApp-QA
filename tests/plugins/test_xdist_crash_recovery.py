"""Pins for plugins/xdist_recovery.py (register row 89): under --dist
loadgroup a worker that dies costs the run one failure, the test it died
on, and nothing else. Without the patch xdist 3.8.0 replays the crash on
every replacement worker until its restart cap, and two replacements in a
row end the session with a KeyError (the 09/18/2026 india leg). The
scenario runs for real in a subprocess."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins import xdist_recovery  # noqa: E402

SCENARIO = REPO_ROOT / "tests" / "plugins" / "xdist_crash_scenario.py"


def _run(tmp_path: Path, two_deaths: bool) -> tuple[int, str]:
    (tmp_path / "pytest.ini").write_text(
        "[pytest]\naddopts = -p no:cacheprovider --dist loadgroup\nmarkers =\n    xdist_group: scope\n",
        encoding="utf-8")
    env = {**os.environ, "RUN_GUARD": "off", "RUN_ARCHIVE": "off", "REPORT_SCREENSHOTS": "off",
           "PYTHONPATH": str(REPO_ROOT)}
    if two_deaths:
        env["XDIST_SCENARIO_TWO_DEATHS"] = "1"
    else:
        env.pop("XDIST_SCENARIO_TWO_DEATHS", None)
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", str(SCENARIO), "-n", "2", "-p", "plugins.xdist_recovery",
         "-c", str(tmp_path / "pytest.ini"), "--rootdir", str(tmp_path), "-rfE", "-v"],
        cwd=str(REPO_ROOT), env=env, capture_output=True, text=True, timeout=180, check=False)
    return proc.returncode, proc.stdout + proc.stderr


def _outcomes(out: str) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {"PASSED": [], "FAILED": []}
    # node ids print relative to the temp rootdir, so only the test name is matched
    for m in re.finditer(r"\b(PASSED|FAILED)\s+\S*::(\w+)", out):
        found[m.group(1)].append(m.group(2))
    return found


def test_a_dead_worker_costs_one_failure_and_nothing_else(tmp_path):
    """One worker dies on test_a2: that test fails once as a crash, the other
    eight pass, no replacement replays it, the session ends by itself."""
    rc, out = _run(tmp_path, two_deaths=False)
    got = _outcomes(out)
    assert got["FAILED"] == ["test_a2_dies"], out[-2000:]
    assert sorted(got["PASSED"]) == sorted(["test_a1", "test_b1", "test_b2_dies_when_asked", "test_c1",
                                            "test_d1", "test_e1", "test_ungrouped_1", "test_ungrouped_2"]), out[-2000:]
    assert "maximum crashed workers" not in out
    assert "INTERNALERROR" not in out
    assert rc == 1


def test_two_dead_workers_in_a_row_still_end_the_session_cleanly(tmp_path):
    """Both workers die early: two crash failures, the remaining seven pass on
    the replacements, no KeyError from a replacement that has not collected."""
    rc, out = _run(tmp_path, two_deaths=True)
    got = _outcomes(out)
    assert sorted(got["FAILED"]) == ["test_a2_dies", "test_b2_dies_when_asked"], out[-2000:]
    assert len(got["PASSED"]) == 7, out[-2000:]
    assert "INTERNALERROR" not in out
    assert "KeyError" not in out
    assert rc == 1


def test_hardening_is_idempotent():
    """A second call changes nothing, and the class carries the mark."""
    assert xdist_recovery.harden_loadscope() is True
    from xdist.scheduler import loadscope
    first = loadscope.LoadScopeScheduling.remove_node
    assert xdist_recovery.harden_loadscope() is True
    assert loadscope.LoadScopeScheduling.remove_node is first
    assert loadscope.LoadScopeScheduling._qa_hardened is True
