"""Pins for tools/qatouch_mapping_audit.py.

The web-app tests map into the project of their root (config/products.py).
A second product root maps into its own project, with its own snapshot
folder. An audit that read only the top folder once called every row of the
second project dead. These pins hold the per-project read, with a second
root supplied by the fixture so no pin depends on the live product list.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import products  # noqa: E402
from tools import qatouch_mapping_audit as qm  # noqa: E402

CORE = qm.DEFAULT_PROJECT


def _snapshot(path: Path, cases: list[tuple[str, str, str]], stamp: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"snapshot_time": stamp, "cases": [
        {"case_key": k, "case_title": t, "module_name": m} for k, t, m in cases]}), encoding="utf-8")


@pytest.fixture
def two_roots(monkeypatch):
    """The web-app root plus a second product root that reports to project ZZ99."""
    monkeypatch.setattr(products, "PRODUCT_ROOTS", {products.SHARED_ROOT: CORE, "tests/other/": "ZZ99"})
    return "ZZ99"


@pytest.fixture
def snapshots(tmp_path, monkeypatch, two_roots):
    """A web-app snapshot at the top and the second project's in ZZ99/, older files beside them."""
    monkeypatch.setattr(qm, "SNAPSHOTS_DIR", tmp_path)
    _snapshot(tmp_path / "snapshot_2026-09-01.json", [("old1", "Old core case", "Views")], "old")
    _snapshot(tmp_path / "snapshot_2026-09-08.json", [("core1", "Verify a view saves", "Views")], "core")
    _snapshot(tmp_path / "ZZ99" / "snapshot_2026-09-11.json", [("oth1", "Verify device web UI login", "Authentication")], "oth")
    return tmp_path


def test_project_follows_the_test_root(two_roots):
    """A test under the second root belongs to its project; everything else to the web-app project."""
    assert qm.project_for("tests/other/test_auth.py::TestAuth::test_login") == "ZZ99"
    assert qm.project_for("tests\\other\\test_auth.py") == "ZZ99"
    assert qm.project_for("tests/ui/views/test_views_basic.py") == CORE
    assert qm.project_for("tests/other_extra/test_x.py") == CORE
    assert qm.other_projects() == ["ZZ99"]


def test_latest_snapshots_picks_the_newest_per_project(snapshots):
    """The top folder's newest file for the web-app project, the ZZ99 folder's for the second."""
    paths = qm.latest_snapshots()
    assert paths[CORE].name == "snapshot_2026-09-08.json"
    assert paths["ZZ99"].name == "snapshot_2026-09-11.json"
    (snapshots / "ZZ99" / "snapshot_2026-09-11.json").unlink()
    assert "ZZ99" not in qm.latest_snapshots()


def test_load_all_cases_merges_and_tags_each_project(snapshots):
    """One dict holds both projects' cases, each tagged with its project, under one label."""
    cases, label = qm.load_all_cases(qm.latest_snapshots())
    assert cases["core1"]["project"] == CORE
    assert cases["oth1"]["project"] == "ZZ99"
    assert f"{CORE}: snapshot_2026-09-08.json (core)" in label
    assert "ZZ99: snapshot_2026-09-11.json (oth)" in label


def test_a_row_keyed_in_its_own_snapshot_is_not_dead(snapshots):
    """Read against the web-app snapshot alone the second project's row is dead; read per project it is live."""
    tests = {"tests/other/test_auth.py::TestAuth::test_login": {"title": "Device login", "area": "other",
                                                                "file": "tests/other/test_auth.py", "project": "ZZ99"}}
    mappings = {"tests/other/test_auth.py::TestAuth::test_login": {"case_key": "oth1"}}
    core_only, _ = qm.load_cases(qm.latest_snapshot())
    assert qm.dead_key_nodeids(tests, mappings, core_only) == ["tests/other/test_auth.py::TestAuth::test_login"]
    merged, _ = qm.load_all_cases(qm.latest_snapshots())
    assert qm.dead_key_nodeids(tests, mappings, merged) == []


def test_candidates_come_from_the_tests_own_project(snapshots):
    """A test of the second project is offered its own cases only, whatever the titles say."""
    cases, _ = qm.load_all_cases(qm.latest_snapshots())
    other_test = {"title": "Verify device web UI login", "area": "other", "file": "tests/other/x.py", "project": "ZZ99"}
    core_test = {"title": "Verify device web UI login", "area": "views", "file": "tests/ui/x.py", "project": CORE}
    assert [c["key"] for c in qm.candidates(other_test, cases, 5)] == ["oth1"]
    assert "oth1" not in [c["key"] for c in qm.candidates(core_test, cases, 5)]


def test_with_one_root_there_is_one_project(monkeypatch, tmp_path):
    """One product root: no second project, and the audit reads the top folder only."""
    monkeypatch.setattr(products, "PRODUCT_ROOTS", {products.SHARED_ROOT: CORE})
    monkeypatch.setattr(qm, "SNAPSHOTS_DIR", tmp_path)
    _snapshot(tmp_path / "snapshot_2026-09-08.json", [("core1", "Verify a view saves", "Views")], "core")
    assert qm.other_projects() == []
    assert list(qm.latest_snapshots()) == [CORE]
