"""Unit tests for plugins/qatouch_reporter.py.

These are not API smoke tests against the live system - they exercise the
plugin's pure-Python resolution logic so the Phase 2 hygiene patches
(RUN_RESULTS_PATH, per-test project marker) don't
regress silently.

Living under tests/plugins/ to be picked up by the default discovery without
needing to add a new test root or update pytest collection config. The tests
do not require playwright, network, or QA Touch credentials.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Ensure the repo root is importable so `plugins.qatouch_reporter` resolves
# the same way pytest itself loads it during a real run.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins import qatouch_reporter as qr  # noqa: E402


# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

def test_run_results_path_is_defined_under_logs():
    """RUN_RESULTS_PATH must exist (was the NameError fix) and live under logs/."""
    assert hasattr(qr, 'RUN_RESULTS_PATH'), \
        'RUN_RESULTS_PATH constant missing - _write_run_results will NameError'
    assert qr.RUN_RESULTS_PATH.name == 'last_run_results.json'
    assert qr.RUN_RESULTS_PATH.parent.name == 'logs'


def test_run_results_path_shares_dir_with_failure_log():
    """Sanity: bug filer reads RUN_RESULTS_PATH; we keep it next to the failure log."""
    assert qr.RUN_RESULTS_PATH.parent == qr.FAILURE_LOG_DIR


# ---------------------------------------------------------------------------
# Marker resolution
# ---------------------------------------------------------------------------

def _make_item(case_key=None, project_key=None):
    """Build a minimal stand-in for a pytest Item exposing get_closest_marker."""
    item = MagicMock()

    def fake_get_closest_marker(name):
        if name == 'qatouch' and case_key is not None:
            m = MagicMock()
            m.args = (case_key,)
            return m
        if name == 'qatouch_project' and project_key is not None:
            m = MagicMock()
            m.args = (project_key,)
            return m
        return None

    item.get_closest_marker.side_effect = fake_get_closest_marker
    return item


def test_get_marker_project_key_returns_marker_value():
    item = _make_item(case_key='ABCD', project_key='OTHER')
    assert qr.QATouchReporter._get_marker_project_key(item) == 'OTHER'


def test_get_marker_project_key_returns_none_when_absent():
    item = _make_item(case_key='ABCD')
    assert qr.QATouchReporter._get_marker_project_key(item) is None


def test_get_marker_project_key_handles_none_item():
    assert qr.QATouchReporter._get_marker_project_key(None) is None


def test_resolve_project_key_marker_wins(monkeypatch):
    monkeypatch.delenv('QATOUCH_PROJECT_ID', raising=False)
    r = qr.QATouchReporter(run_key='rk1')
    item = _make_item(case_key='C1', project_key='PROJ_B')
    assert r._resolve_project_key(item) == 'PROJ_B'


def test_resolve_project_key_falls_back_to_default(monkeypatch):
    monkeypatch.delenv('QATOUCH_PROJECT_ID', raising=False)
    r = qr.QATouchReporter(run_key='rk1')
    item = _make_item(case_key='C1')  # no project marker
    assert r._resolve_project_key(item) == qr.DEFAULT_PROJECT_KEY


def test_resolve_project_key_falls_back_to_env(monkeypatch):
    monkeypatch.setenv('QATOUCH_PROJECT_ID', 'ENV_PROJ')
    r = qr.QATouchReporter(run_key='rk1')
    item = _make_item(case_key='C1')
    assert r._resolve_project_key(item) == 'ENV_PROJ'


# ---------------------------------------------------------------------------
# Per-project grouping
# ---------------------------------------------------------------------------

def test_group_results_by_project_single_default(monkeypatch):
    monkeypatch.delenv('QATOUCH_PROJECT_ID', raising=False)
    r = qr.QATouchReporter(run_key='rk1')
    r.results = {'C1': qr.STATUS_PASSED, 'C2': qr.STATUS_FAILED}
    # No case_projects entries => fall back to default
    groups = r._group_results_by_project()
    assert groups == {qr.DEFAULT_PROJECT_KEY: ['C1', 'C2']} or \
        groups == {qr.DEFAULT_PROJECT_KEY: ['C2', 'C1']}


def test_group_results_by_project_splits_by_marker(monkeypatch):
    monkeypatch.delenv('QATOUCH_PROJECT_ID', raising=False)
    r = qr.QATouchReporter(run_key='rk1')
    r.results = {'C1': qr.STATUS_PASSED, 'C2': qr.STATUS_FAILED, 'C3': qr.STATUS_PASSED}
    r.case_projects = {'C1': 'JlW1', 'C2': 'OTHER', 'C3': 'JlW1'}
    groups = r._group_results_by_project()
    assert set(groups.keys()) == {'JlW1', 'OTHER'}
    assert sorted(groups['JlW1']) == ['C1', 'C3']
    assert groups['OTHER'] == ['C2']


# ---------------------------------------------------------------------------
# Upload path label
# ---------------------------------------------------------------------------

def test_upload_path_used_defaults_to_none():
    r = qr.QATouchReporter(run_key='rk1')
    assert r._upload_path_used == '(none)'


# ---------------------------------------------------------------------------
# Upload path - pins for the 2026-08-17 silent-no-op fix
#
# The results API accepts a case key or a per-run result key, answers
# {"success": true}, and writes nothing. Only the case CODE lands. These
# tests make sure the reporter resolves codes, never sends a form the API
# ignores, and verifies by read-back after every upload.
# ---------------------------------------------------------------------------

def _reporter(monkeypatch):
    monkeypatch.delenv('QATOUCH_PROJECT_ID', raising=False)
    r = qr.QATouchReporter(run_key='RUN1')
    r.project_key = 'JlW1'
    return r


def test_run_key_mapping_resolves_case_codes_not_result_keys(monkeypatch):
    r = _reporter(monkeypatch)
    client = MagicMock()
    client.get_all_test_run_results.return_value = [
        {'case_id': 'B869bm', 'run_key': 'w5BNkb', 'code': 'TR0262', 'status': 'Untested'},
        {'case_id': '8V1vw1', 'run_key': 'y5MNkx', 'code': 'TR0263', 'status': 'Untested'},
    ]
    r._build_run_key_mapping(client)
    # The value must be the case CODE - the per-run result key is a silent no-op.
    assert r.case_to_run_key == {'B869bm': 'TR0262', '8V1vw1': 'TR0263'}
    assert 'w5BNkb' not in r.case_to_run_key.values()


def test_build_payload_uses_codes_and_skips_unresolved(monkeypatch):
    r = _reporter(monkeypatch)
    r.results = {'B869bm': 1, '8V1vw1': 5, 'NOMAP1': 1}
    r.case_to_run_key = {'B869bm': 'TR0262', '8V1vw1': 'TR0263'}
    payload = r._build_payload(['B869bm', '8V1vw1', 'NOMAP1'])
    assert payload == [{'case': 'TR0262', 'status': 1}, {'case': 'TR0263', 'status': 5}]
    # An unresolved case must be dropped, not sent as a case key the API ignores.
    assert all(e['case'].startswith('TR') for e in payload)


def test_verify_upload_uses_shared_client_check_and_fails_on_mismatch(monkeypatch):
    r = _reporter(monkeypatch)
    client = MagicMock()
    client.verify_results_landed.return_value = {
        'checked': 2, 'landed': ['TR0262'], 'mismatched': ['TR0263: sent Failed, run shows Untested'],
        'missing': []}
    ok = r._verify_upload(client, [{'case': 'TR0262', 'status': 1}, {'case': 'TR0263', 'status': 5}])
    assert ok is False
    client.verify_results_landed.assert_called_once_with(
        'JlW1', 'RUN1', [{'case': 'TR0262', 'status': 1}, {'case': 'TR0263', 'status': 5}])


def test_verify_upload_passes_when_everything_landed(monkeypatch):
    r = _reporter(monkeypatch)
    client = MagicMock()
    client.verify_results_landed.return_value = {
        'checked': 1, 'landed': ['TR0262'], 'mismatched': [], 'missing': []}
    assert r._verify_upload(client, [{'case': 'TR0262', 'status': 1}]) is True


def test_verify_upload_does_not_fail_the_run_on_readback_error(monkeypatch):
    """A read-back problem is not evidence the upload failed - warn, do not block."""
    r = _reporter(monkeypatch)
    client = MagicMock()
    client.verify_results_landed.side_effect = RuntimeError('429')
    assert r._verify_upload(client, [{'case': 'TR0262', 'status': 1}]) is True


def test_client_has_no_update_playwright_results():
    """The playwright branch used to call a method that never existed."""
    from tools.qatouch_client import QATouchClient
    assert not hasattr(QATouchClient, 'update_playwright_results')
    assert hasattr(QATouchClient, 'update_test_run_results_by_code')
