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

import logging
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
    """The qatouch_project marker's value is read off the item."""
    item = _make_item(case_key='ABCD', project_key='OTHER')
    assert qr.QATouchReporter._get_marker_project_key(item) == 'OTHER'


def test_get_marker_project_key_returns_none_when_absent():
    """An item without a qatouch_project marker yields no project key."""
    item = _make_item(case_key='ABCD')
    assert qr.QATouchReporter._get_marker_project_key(item) is None


def test_get_marker_project_key_handles_none_item():
    """A missing item yields no project key instead of an error."""
    assert qr.QATouchReporter._get_marker_project_key(None) is None


def test_resolve_project_key_marker_wins(monkeypatch):
    """A per-test project marker outranks the default project."""
    monkeypatch.delenv('QATOUCH_PROJECT_ID', raising=False)
    r = qr.QATouchReporter(run_key='rk1')
    item = _make_item(case_key='C1', project_key='PROJ_B')
    assert r._resolve_project_key(item) == 'PROJ_B'


def test_resolve_project_key_falls_back_to_default(monkeypatch):
    """Without a marker or env override, the default project key applies."""
    monkeypatch.delenv('QATOUCH_PROJECT_ID', raising=False)
    r = qr.QATouchReporter(run_key='rk1')
    item = _make_item(case_key='C1')  # no project marker
    assert r._resolve_project_key(item) == qr.DEFAULT_PROJECT_KEY


def test_resolve_project_key_falls_back_to_env(monkeypatch):
    """QATOUCH_PROJECT_ID supplies the project key when no marker is set."""
    monkeypatch.setenv('QATOUCH_PROJECT_ID', 'ENV_PROJ')
    r = qr.QATouchReporter(run_key='rk1')
    item = _make_item(case_key='C1')
    assert r._resolve_project_key(item) == 'ENV_PROJ'


# ---------------------------------------------------------------------------
# Per-project grouping
# ---------------------------------------------------------------------------

def test_group_results_by_project_single_default(monkeypatch):
    """Results with no project entries group under the default project."""
    monkeypatch.delenv('QATOUCH_PROJECT_ID', raising=False)
    r = qr.QATouchReporter(run_key='rk1')
    r.results = {'C1': qr.STATUS_PASSED, 'C2': qr.STATUS_FAILED}
    # No case_projects entries => fall back to default
    groups = r._group_results_by_project()
    assert groups == {qr.DEFAULT_PROJECT_KEY: ['C1', 'C2']} or \
        groups == {qr.DEFAULT_PROJECT_KEY: ['C2', 'C1']}


def test_group_results_by_project_splits_by_marker(monkeypatch):
    """Results split into one group per marked project."""
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
    """Before any upload, the path label reads '(none)'."""
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
    """The run mapping stores case codes, never the per-run result keys."""
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
    """The payload carries case codes and drops cases with no code."""
    r = _reporter(monkeypatch)
    r.results = {'B869bm': 1, '8V1vw1': 5, 'NOMAP1': 1}
    r.case_to_run_key = {'B869bm': 'TR0262', '8V1vw1': 'TR0263'}
    payload = r._build_payload(['B869bm', '8V1vw1', 'NOMAP1'])
    assert payload == [{'case': 'TR0262', 'status': 1}, {'case': 'TR0263', 'status': 5}]
    # An unresolved case must be dropped, not sent as a case key the API ignores.
    assert all(e['case'].startswith('TR') for e in payload)


def test_verify_upload_uses_shared_client_check_and_fails_on_mismatch(monkeypatch):
    """A read-back mismatch fails the upload check through the shared client verify."""
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
    """The upload check passes when read-back shows every result landed."""
    r = _reporter(monkeypatch)
    client = MagicMock()
    client.verify_results_landed.return_value = {
        'checked': 1, 'landed': ['TR0262'], 'mismatched': [], 'missing': []}
    assert r._verify_upload(client, [{'case': 'TR0262', 'status': 1}]) is True


def test_verify_upload_does_not_fail_the_run_on_readback_error(monkeypatch):
    """A read-back problem is not evidence the upload failed - warn, do not block.

    A 429 is retried (sleep no-oped here) and then conceded; the retries are
    exhausted and the upload still counts as unverified-but-not-failed.
    """
    monkeypatch.setattr(qr.time, 'sleep', lambda _s: None)
    r = _reporter(monkeypatch)
    client = MagicMock()
    client.verify_results_landed.side_effect = RuntimeError('429')
    assert r._verify_upload(client, [{'case': 'TR0262', 'status': 1}]) is True
    assert client.verify_results_landed.call_count == 3  # retried before conceding


def test_client_has_no_update_playwright_results():
    """The playwright branch used to call a method that never existed."""
    from tools.qatouch_client import QATouchClient
    assert not hasattr(QATouchClient, 'update_playwright_results')
    assert hasattr(QATouchClient, 'update_test_run_results_by_code')


# ---------------------------------------------------------------------------
# M1 pin (2026-08-20): "no case codes resolved" is a FAILURE, not an empty
# success. Before this pin the reporter POSTed an empty payload, verified
# trivially, and printed "Successfully uploaded 0 results" with no failure-log
# entry - the silent-no-op class, on the edge the main fix missed.
# ---------------------------------------------------------------------------

def _wire_tmp_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(qr, 'FAILURE_LOG_DIR', tmp_path)
    monkeypatch.setattr(qr, 'FAILURE_LOG_PATH', tmp_path / 'upload_failures.json')
    monkeypatch.setattr(qr, 'RUN_RESULTS_PATH', tmp_path / 'last_run_results.json')
    # The 429 backoff sleeps 30s per attempt; a unit test must not.
    monkeypatch.setattr(qr.time, 'sleep', lambda _s: None)


def test_sessionfinish_with_unresolvable_codes_fails_loud(monkeypatch, tmp_path):
    """No resolvable case codes counts as an error and lands in the failure log."""
    import json as _json

    import tools.qatouch_client as tqc

    _wire_tmp_paths(monkeypatch, tmp_path)
    fake_client = MagicMock()
    fake_client.get_all_test_run_results.side_effect = RuntimeError('HTTP 429')
    monkeypatch.setattr(tqc, 'QATouchClient', MagicMock(return_value=fake_client))

    r = _reporter(monkeypatch)
    r.results = {'B869bm': 1, '8V1vw1': 5}
    r.pytest_sessionfinish(session=None, exitstatus=0)

    # Nothing was sent in a form the API would ignore, and nothing "succeeded".
    fake_client.update_test_run_results_by_code.assert_not_called()
    assert r.stats['errors'] == 1
    assert r.stats['uploaded'] == 0

    # The failure log carries the case keys so retry_uploads can resolve them.
    saved = _json.loads((tmp_path / 'upload_failures.json').read_text())
    assert len(saved) == 1
    assert {e['case'] for e in saved[0]['results']} == {'B869bm', '8V1vw1'}
    assert 'No case codes resolved' in saved[0]['error']


def test_sessionfinish_uploads_normally_when_codes_resolve(monkeypatch, tmp_path):
    """With resolvable codes, session finish uploads once and logs no failure."""
    import tools.qatouch_client as tqc

    _wire_tmp_paths(monkeypatch, tmp_path)
    fake_client = MagicMock()
    fake_client.get_all_test_run_results.return_value = [
        {'case_id': 'B869bm', 'code': 'TR0262', 'status': 'Untested'}]
    fake_client.verify_results_landed.return_value = {
        'checked': 1, 'landed': ['TR0262'], 'mismatched': [], 'missing': []}
    monkeypatch.setattr(tqc, 'QATouchClient', MagicMock(return_value=fake_client))

    r = _reporter(monkeypatch)
    r.results = {'B869bm': 1}
    r.pytest_sessionfinish(session=None, exitstatus=0)

    fake_client.update_test_run_results_by_code.assert_called_once()
    sent = fake_client.update_test_run_results_by_code.call_args.kwargs['results']
    assert sent == [{'case': 'TR0262', 'status': 1}]
    assert r.stats['uploaded'] == 1
    assert r.stats['errors'] == 0
    assert not (tmp_path / 'upload_failures.json').exists()


# ---------------------------------------------------------------------------
# Attachments (2026-08-21): failure screenshots and timing ride on the result
# upload as multipart file[] + comments. Pins: the multipart request shape,
# the 2 MB whole-file skip, byte-compatible plain requests when nothing was
# captured, timing lines bounded to the attached cases, and degrade-to-plain
# when the multipart request fails - by raising OR by being accepted and
# ignored (the read-back catches the second shape).
# ---------------------------------------------------------------------------

def _client_with_mock_session():
    """QATouchClient with a mocked requests session - no network, ever."""
    from tools.qatouch_client import QATouchClient
    c = QATouchClient(api_key='k', domain='d')
    c.session = MagicMock()
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {'success': True, 'msg': 'TR0262 - Updated Successfully'}
    c.session.post.return_value = resp
    return c


def test_client_plain_upload_request_shape_unchanged():
    """No attachments => the exact pre-attachment request: no files, no
    per-request headers. This is the byte-compatibility pin."""
    c = _client_with_mock_session()
    c.update_test_run_results_by_code(
        'JlW1', 'RUN1', [{'case': 'TR0262', 'status': 1}], comments='hello')
    args, kwargs = c.session.post.call_args
    assert args == ('https://api.qatouch.com/api/v1/testRunResults/testrun/code',)
    assert set(kwargs) == {'params', 'timeout'}
    assert kwargs['params']['project'] == 'JlW1'
    assert kwargs['params']['test_run'] == 'RUN1'
    assert kwargs['params']['comments'] == 'hello'


def test_client_attachment_upload_posts_multipart_file_parts():
    """An attachment posts as a multipart file[] part with the JSON header dropped."""
    c = _client_with_mock_session()
    png = b'\x89PNG-bytes'
    c.update_test_run_results_by_code(
        'JlW1', 'RUN1', [{'case': 'TR0262', 'status': 5}],
        comments='TR0262 execution: 1.2s',
        attachments=[('TR0262-failure.png', png, 'image/png')])
    kwargs = c.session.post.call_args.kwargs
    assert kwargs['files'] == [('file[]', ('TR0262-failure.png', png, 'image/png'))]
    # The session pins Content-Type: application/json; a multipart body needs
    # the boundary header requests generates, so the JSON one must be dropped.
    assert kwargs['headers'] == {'Content-Type': None}
    assert kwargs['params']['comments'] == 'TR0262 execution: 1.2s'


def _playwright_session(monkeypatch, tmp_path):
    """Reporter on the playwright path + a fake client with one resolvable case."""
    import tools.qatouch_client as tqc

    _wire_tmp_paths(monkeypatch, tmp_path)
    fake_client = MagicMock()
    fake_client.get_all_test_run_results.return_value = [
        {'case_id': 'B869bm', 'code': 'TR0262', 'status': 'Untested'}]
    fake_client.verify_results_landed.return_value = {
        'checked': 1, 'landed': ['TR0262'], 'mismatched': [], 'missing': []}
    monkeypatch.setattr(tqc, 'QATouchClient', MagicMock(return_value=fake_client))

    r = _reporter(monkeypatch)
    r.use_playwright_endpoint = True
    return r, fake_client


def test_sessionfinish_attaches_screenshot_and_timing(monkeypatch, tmp_path):
    """A failed case uploads with its screenshot named by code and a timing line."""
    r, fake_client = _playwright_session(monkeypatch, tmp_path)
    r.results = {'B869bm': qr.STATUS_FAILED}
    r.durations = {'B869bm': 1.23}
    r.screenshots = {'B869bm': b'\x89PNG-bytes'}
    r.pytest_sessionfinish(session=None, exitstatus=0)

    fake_client.update_test_run_results_by_code.assert_called_once()
    kwargs = fake_client.update_test_run_results_by_code.call_args.kwargs
    assert kwargs['results'] == [{'case': 'TR0262', 'status': 5}]
    # File is named by case CODE so a reader of the run can match it.
    assert kwargs['attachments'] == [('TR0262-failure.png', b'\x89PNG-bytes', 'image/png')]
    assert 'TR0262 execution: 1.2s' in kwargs['comments']
    assert r.stats['uploaded'] == 1
    assert r.stats['errors'] == 0


def test_sessionfinish_skips_oversized_screenshot_whole(monkeypatch, tmp_path, caplog):
    """A screenshot over 2 MB is skipped whole and the upload goes plain."""
    r, fake_client = _playwright_session(monkeypatch, tmp_path)
    r.results = {'B869bm': qr.STATUS_FAILED}
    r.screenshots = {'B869bm': b'x' * (qr.MAX_ATTACHMENT_BYTES + 1)}
    with caplog.at_level(logging.WARNING, logger='qatouch_reporter'):
        r.pytest_sessionfinish(session=None, exitstatus=0)

    # Skipped whole, with a log line - and with nothing left to attach the
    # request falls back to the plain shape (no attachments kwarg at all).
    assert 'over the 2 MB attachment cap' in caplog.text
    fake_client.update_test_run_results_by_code.assert_called_once()
    kwargs = fake_client.update_test_run_results_by_code.call_args.kwargs
    assert 'attachments' not in kwargs
    assert 'execution' not in kwargs['comments']
    assert r.stats['uploaded'] == 1


def test_sessionfinish_without_screenshots_sends_plain_request(monkeypatch, tmp_path):
    """Timing rides only with attachments - a run with durations but no
    screenshots must produce the same request as before this feature."""
    r, fake_client = _playwright_session(monkeypatch, tmp_path)
    r.results = {'B869bm': qr.STATUS_PASSED}
    r.durations = {'B869bm': 0.45}
    r.pytest_sessionfinish(session=None, exitstatus=0)

    fake_client.update_test_run_results_by_code.assert_called_once()
    kwargs = fake_client.update_test_run_results_by_code.call_args.kwargs
    assert 'attachments' not in kwargs
    assert kwargs['comments'].startswith('Automated upload from Playwright run at')
    assert 'execution' not in kwargs['comments']


def test_sessionfinish_attachment_failure_degrades_to_plain_upload(monkeypatch, tmp_path):
    """A rejected multipart upload falls back to the plain request and still lands."""
    r, fake_client = _playwright_session(monkeypatch, tmp_path)
    calls = []

    def fake_update(**kwargs):
        calls.append(kwargs)
        if kwargs.get('attachments'):
            raise RuntimeError('multipart rejected')
        return {'success': True}

    fake_client.update_test_run_results_by_code.side_effect = fake_update
    r.results = {'B869bm': qr.STATUS_FAILED}
    r.screenshots = {'B869bm': b'\x89PNG-bytes'}
    r.pytest_sessionfinish(session=None, exitstatus=0)

    # First try carried the attachment; the fallback is today's plain request
    # and the statuses still land - never hostage to a screenshot.
    assert len(calls) == 2
    assert calls[0].get('attachments')
    assert 'attachments' not in calls[1]
    assert calls[1]['results'] == [{'case': 'TR0262', 'status': 5}]
    assert calls[1]['comments'].startswith('Automated upload from Playwright run at')
    assert r.stats['uploaded'] == 1
    assert r.stats['errors'] == 0


def test_collect_attachment_parts_skips_unresolved_and_non_failed(monkeypatch):
    """No file for a case whose result was dropped (no code) or is not FAILED -
    an attachment with no uploaded result has nothing to hang on. Keyed by
    case_key so the timing comment can cover exactly the attached cases."""
    r = _reporter(monkeypatch)
    r.results = {'B869bm': qr.STATUS_FAILED, '8V1vw1': qr.STATUS_PASSED,
                 'NOMAP1': qr.STATUS_FAILED}
    r.screenshots = {'B869bm': b'ok', '8V1vw1': b'passed-anyway', 'NOMAP1': b'no-code'}
    r.case_to_run_key = {'B869bm': 'TR0262', '8V1vw1': 'TR0263'}
    parts = r._collect_attachment_parts(['B869bm', '8V1vw1', 'NOMAP1'])
    assert parts == {'B869bm': ('TR0262-failure.png', b'ok', 'image/png')}


def test_timing_lines_cover_only_attached_cases(monkeypatch, tmp_path):
    """The comment rides the URL query string, so a timing line for every
    uploaded case would grow the URL with run size - the most likely part of
    the feature to be rejected on exactly the large runs it targets. Only
    the attached (failed) cases get a line."""
    import tools.qatouch_client as tqc

    _wire_tmp_paths(monkeypatch, tmp_path)
    fake_client = MagicMock()
    fake_client.get_all_test_run_results.return_value = [
        {'case_id': 'B869bm', 'code': 'TR0262', 'status': 'Untested'},
        {'case_id': '8V1vw1', 'code': 'TR0263', 'status': 'Untested'},
    ]
    fake_client.verify_results_landed.return_value = {
        'checked': 2, 'landed': ['TR0262', 'TR0263'], 'mismatched': [], 'missing': []}
    monkeypatch.setattr(tqc, 'QATouchClient', MagicMock(return_value=fake_client))

    r = _reporter(monkeypatch)
    r.use_playwright_endpoint = True
    r.results = {'B869bm': qr.STATUS_FAILED, '8V1vw1': qr.STATUS_PASSED}
    r.durations = {'B869bm': 1.23, '8V1vw1': 0.45}
    r.screenshots = {'B869bm': b'\x89PNG-bytes'}
    r.pytest_sessionfinish(session=None, exitstatus=0)

    kwargs = fake_client.update_test_run_results_by_code.call_args.kwargs
    assert 'TR0262 execution: 1.2s' in kwargs['comments']
    # The passed case uploaded a status but no attachment - no timing line.
    assert 'TR0263' not in kwargs['comments']
    assert {e['case'] for e in kwargs['results']} == {'TR0262', 'TR0263'}


def test_sessionfinish_accepted_but_ignored_multipart_degrades_to_plain(monkeypatch, tmp_path):
    """The API's measured failure class: the multipart request answers
    {"success": true} but the statuses never apply. The read-back catches
    it, and the reporter re-sends the plain pre-attachment request
    in-session instead of conceding to the failure log."""
    r, fake_client = _playwright_session(monkeypatch, tmp_path)
    calls = []

    def fake_update(**kwargs):
        calls.append(kwargs)
        return {'success': True, 'msg': 'TR0262 - Updated Successfully'}

    fake_client.update_test_run_results_by_code.side_effect = fake_update
    # First read-back: nothing landed (multipart accepted-but-ignored).
    # Second read-back, after the plain re-send: landed.
    fake_client.verify_results_landed.side_effect = [
        {'checked': 1, 'landed': [],
         'mismatched': ['TR0262: sent Failed, run shows Untested'], 'missing': []},
        {'checked': 1, 'landed': ['TR0262'], 'mismatched': [], 'missing': []},
    ]
    r.results = {'B869bm': qr.STATUS_FAILED}
    r.screenshots = {'B869bm': b'\x89PNG-bytes'}
    r.pytest_sessionfinish(session=None, exitstatus=0)

    # First try carried the attachment; the re-send is today's plain request.
    assert len(calls) == 2
    assert calls[0].get('attachments')
    assert 'attachments' not in calls[1]
    assert calls[1]['results'] == [{'case': 'TR0262', 'status': 5}]
    assert calls[1]['comments'].startswith('Automated upload from Playwright run at')
    assert r.stats['uploaded'] == 1
    assert r.stats['errors'] == 0
    assert not (tmp_path / 'upload_failures.json').exists()


def test_sessionfinish_plain_verify_failure_still_saves_for_retry(monkeypatch, tmp_path):
    """The degrade loop must not spin: when the plain request itself does not
    land (no attachments were sent), the failure goes to the log for
    tools/retry_uploads.py - one plain send, no re-send."""
    r, fake_client = _playwright_session(monkeypatch, tmp_path)
    fake_client.verify_results_landed.return_value = {
        'checked': 1, 'landed': [],
        'mismatched': ['TR0262: sent Passed, run shows Untested'], 'missing': []}
    r.results = {'B869bm': qr.STATUS_PASSED}  # no screenshot => plain upload
    r.pytest_sessionfinish(session=None, exitstatus=0)

    fake_client.update_test_run_results_by_code.assert_called_once()
    assert r.stats['errors'] == 1
    assert (tmp_path / 'upload_failures.json').exists()
