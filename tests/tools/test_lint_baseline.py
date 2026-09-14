"""Pins for tools/lint_baseline.py.

The gate compares per-file ruff counts with a recorded baseline. On
09/14/2026 the repo reached zero findings, and the tool read the recorded
empty baseline as "no baseline recorded" and blocked the commit. These
pins hold the three states apart: nothing recorded, zero recorded, and a
file that gained a finding.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import lint_baseline as lb  # noqa: E402


@pytest.fixture
def baseline_file(tmp_path, monkeypatch):
    path = tmp_path / "lint_baseline.json"
    monkeypatch.setattr(lb, "BASELINE", path)
    return path


def _counts(monkeypatch, counts: dict[str, int]):
    monkeypatch.setattr(lb, "current_counts", lambda: (Counter(counts), None))


def test_nothing_recorded_asks_for_an_update(baseline_file, monkeypatch, capsys):
    """With no baseline file the gate exits 2 and names the way out."""
    _counts(monkeypatch, {})
    assert lb.main([]) == 2
    assert "No baseline recorded" in capsys.readouterr().out


def test_a_recorded_zero_baseline_passes_a_clean_tree(baseline_file, monkeypatch, capsys):
    """A recorded zero is a baseline: a clean tree passes with total 0."""
    baseline_file.write_text(json.dumps({"total": 0, "files": {}}), encoding="utf-8")
    _counts(monkeypatch, {})
    assert lb.main([]) == 0
    assert "Total: 0" in capsys.readouterr().out


def test_a_recorded_zero_baseline_fails_any_finding(baseline_file, monkeypatch, capsys):
    """At a zero baseline any finding is a gain and fails, naming the file."""
    baseline_file.write_text(json.dumps({"total": 0, "files": {}}), encoding="utf-8")
    _counts(monkeypatch, {"tools/x.py": 1})
    assert lb.main([]) == 1
    assert "tools/x.py: 0 -> 1" in capsys.readouterr().out


def test_a_file_under_its_recorded_count_passes_and_says_so(baseline_file, monkeypatch, capsys):
    """A file below its recorded count passes and the gate says how many were fixed."""
    baseline_file.write_text(json.dumps({"total": 3, "files": {"tools/x.py": 3}}), encoding="utf-8")
    _counts(monkeypatch, {"tools/x.py": 1})
    assert lb.main([]) == 0
    assert "2 finding(s) fixed" in capsys.readouterr().out


def test_an_unreadable_baseline_reads_as_none(baseline_file):
    """Unreadable JSON is no baseline; an empty files map is a real one."""
    baseline_file.write_text("{not json", encoding="utf-8")
    assert lb.load_baseline() is None
    baseline_file.write_text(json.dumps({"files": {}}), encoding="utf-8")
    assert lb.load_baseline() == {}


def test_a_failed_ruff_run_is_an_error_not_a_clean_tree(baseline_file, monkeypatch, capsys):
    """ruff exiting with anything but 0 or 1 stops the gate with its stderr; at a zero baseline that used to read as clean."""
    baseline_file.write_text(json.dumps({"total": 0, "files": {}}), encoding="utf-8")

    class Dead:
        returncode = 2
        stdout = ""
        stderr = "error: bad pyproject"

    monkeypatch.setattr(lb.subprocess, "run", lambda *a, **k: Dead())
    assert lb.main([]) == 2
    assert "ruff exited 2: error: bad pyproject" in capsys.readouterr().out


def test_a_recorded_baseline_round_trips(baseline_file):
    """What --update writes is what the next run reads, zero included."""
    lb.save_baseline(Counter({"tools/x.py": 2}))
    assert lb.load_baseline() == {"tools/x.py": 2}
    lb.save_baseline(Counter())
    assert lb.load_baseline() == {}
