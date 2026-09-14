"""Pins for tools/qatouch_mapping_audit.py.

The web-app tests map into NexaiQ-Core and the Camera 2 Cloud tests into
project 60W5, each with its own snapshot folder. Until 09/14/2026 the audit
read only the NexaiQ-Core snapshot and called every c2c row dead. These
pins hold the per-project read.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import qatouch_mapping_audit as qm  # noqa: E402


def _snapshot(path: Path, cases: list[tuple[str, str, str]], stamp: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"snapshot_time": stamp, "cases": [
        {"case_key": k, "case_title": t, "module_name": m} for k, t, m in cases]}), encoding="utf-8")


@pytest.fixture
def snapshots(tmp_path, monkeypatch):
    """A NexaiQ-Core snapshot at the top and a Camera 2 Cloud one in 60W5/, older files beside them."""
    monkeypatch.setattr(qm, "SNAPSHOTS_DIR", tmp_path)
    _snapshot(tmp_path / "snapshot_2026-09-01.json", [("old1", "Old core case", "Views")], "old")
    _snapshot(tmp_path / "snapshot_2026-09-08.json", [("core1", "Verify a view saves", "Views")], "core")
    _snapshot(tmp_path / "60W5" / "snapshot_2026-09-11.json", [("cam1", "Verify camera web UI login", "Authentication")], "cam")
    return tmp_path


def test_project_follows_the_test_root():
    """c2c tests belong to 60W5; everything else to NexaiQ-Core."""
    assert qm.project_for("tests/c2c/test_c2c_auth.py::TestC2CAuth::test_login") == "60W5"
    assert qm.project_for("tests\\c2c\\test_c2c_auth.py") == "60W5"
    assert qm.project_for("tests/ui/views/test_views_basic.py") == "JlW1"
    assert qm.project_for("tests/c2c_extra/test_x.py") == "JlW1"


def test_latest_snapshots_picks_the_newest_per_project(snapshots):
    """The top folder's newest file for NexaiQ-Core, the 60W5 folder's for Camera 2 Cloud."""
    paths = qm.latest_snapshots()
    assert paths["JlW1"].name == "snapshot_2026-09-08.json"
    assert paths["60W5"].name == "snapshot_2026-09-11.json"
    (snapshots / "60W5" / "snapshot_2026-09-11.json").unlink()
    assert "60W5" not in qm.latest_snapshots()


def test_load_all_cases_merges_and_tags_each_project(snapshots):
    """One dict holds both projects' cases, each tagged with its project, under one label."""
    cases, label = qm.load_all_cases(qm.latest_snapshots())
    assert cases["core1"]["project"] == "JlW1"
    assert cases["cam1"]["project"] == "60W5"
    assert "JlW1: snapshot_2026-09-08.json (core)" in label
    assert "60W5: snapshot_2026-09-11.json (cam)" in label


def test_a_c2c_row_keyed_in_its_own_snapshot_is_not_dead(snapshots):
    """The 09/14 finding: read against NexaiQ-Core alone the c2c row is dead; read per project it is live."""
    tests = {"tests/c2c/test_c2c_auth.py::TestC2CAuth::test_login": {"title": "Camera login", "area": "c2c",
                                                                      "file": "tests/c2c/test_c2c_auth.py", "project": "60W5"}}
    mappings = {"tests/c2c/test_c2c_auth.py::TestC2CAuth::test_login": {"case_key": "cam1"}}
    core_only, _ = qm.load_cases(qm.latest_snapshot())
    assert qm.dead_key_nodeids(tests, mappings, core_only) == ["tests/c2c/test_c2c_auth.py::TestC2CAuth::test_login"]
    merged, _ = qm.load_all_cases(qm.latest_snapshots())
    assert qm.dead_key_nodeids(tests, mappings, merged) == []


def test_candidates_come_from_the_tests_own_project(snapshots):
    """A c2c test is offered 60W5 cases only, whatever the titles say."""
    cases, _ = qm.load_all_cases(qm.latest_snapshots())
    c2c_test = {"title": "Verify camera web UI login", "area": "c2c", "file": "tests/c2c/x.py", "project": "60W5"}
    core_test = {"title": "Verify camera web UI login", "area": "views", "file": "tests/ui/x.py", "project": "JlW1"}
    assert [c["key"] for c in qm.candidates(c2c_test, cases, 5)] == ["cam1"]
    assert "cam1" not in [c["key"] for c in qm.candidates(core_test, cases, 5)]
