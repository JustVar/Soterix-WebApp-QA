"""Regression pins for tools/qatouch_client.py.

Every test here pins a QA Touch API behaviour that was measured on
2026-08-17 and that failed SILENTLY before it was found - the API answered
success and did nothing. None of these needs network, credentials or a
browser: the HTTP session is a mock and each test asserts on the exact
request the client sends or the exact way it reads a response.

If one of these fails, either the client regressed or somebody "cleaned up"
a deliberate oddity. Read docs/QA_TOUCH_INTEGRATION.md, "Four traps", before
changing the expectation.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import qatouch_client as qc  # noqa: E402

# ---------------------------------------------------------------- helpers

def _resp(payload, status=200):
    """A fake requests.Response with the bits the client reads."""
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload
    r.text = json.dumps(payload)
    return r


@pytest.fixture
def client():
    c = qc.QATouchClient(api_key='test-key', domain='testdomain')
    c.session = MagicMock()
    return c


# ---------------------------------------------------------------- trap 1: field rename

def test_legacy_aliases_added_for_renamed_fields():
    """The public API renamed case fields; readers of the old names must still work."""
    case = {'module_name': 'PTZ Tours', 'Tags': ['regression', 'smoke'],
            'created_date': '2026-01-01', 'updated_date': '2026-02-02', 'created_by': 'x'}
    out = qc.add_legacy_case_aliases(dict(case))
    assert out['module name'] == 'PTZ Tours'
    assert out['NewTags'] == 'regression, smoke'
    assert out['created date'] == '2026-01-01'
    assert out['updated date'] == '2026-02-02'
    assert out['created by'] == 'x'
    # New names are still there - readers of either spelling work.
    assert out['module_name'] == 'PTZ Tours'
    assert out['Tags'] == ['regression', 'smoke']


def test_legacy_aliases_do_not_clobber_existing_old_names():
    """An old-name field already on a case keeps its value when aliases are added."""
    case = {'module name': 'KEEP', 'module_name': 'new'}
    assert qc.add_legacy_case_aliases(dict(case))['module name'] == 'KEEP'


def test_newtags_alias_is_empty_string_when_no_tags():
    """A case with no tags gets an empty NewTags alias rather than a missing key."""
    assert qc.add_legacy_case_aliases({'Tags': []})['NewTags'] == ''
    assert qc.add_legacy_case_aliases({})['NewTags'] == ''


def test_list_test_cases_applies_aliases_to_every_row(client):
    """Every row from list_test_cases carries the legacy field aliases."""
    client.session.get.return_value = _resp({'data': [
        {'case_key': 'A', 'module_name': 'M1', 'Tags': ['smoke']},
        {'case_key': 'B', 'module_name': 'M2', 'Tags': []},
    ]})
    rows = client.list_test_cases('JlW1', page=1)['data']
    assert [r['module name'] for r in rows] == ['M1', 'M2']
    assert [r['NewTags'] for r in rows] == ['smoke', '']


def test_module_key_filter_is_sent_as_query(client):
    """Server-side filtering is what stops the 429s; make sure it is really sent."""
    client.session.get.return_value = _resp({'data': []})
    client.list_test_cases('JlW1', page=1, module_key='DglWL')
    url = client.session.get.call_args.args[0]
    assert 'getAllTestCases/JlW1' in url
    assert 'moduleKey=DglWL' in url


# ---------------------------------------------------------------- trap 3: result identifiers

@pytest.mark.parametrize('code,ref', [
    ('TR0262', '262'), ('TR0028', '28'), ('TR1234', '1234'), ('TR0001', '1'), ('TR0000', '0'),
])
def test_case_code_to_ref_strips_prefix_and_leading_zeros(code, ref):
    """status/multiple only honours the bare number - 'TR0262' and 'B869bm' no-op."""
    assert qc.case_code_to_ref(code) == ref


def test_update_by_code_sends_full_codes_as_indexed_dict(client):
    """testrun/code wants {"0": {...}, "1": {...}} with FULL codes, via POST."""
    client.session.post.return_value = _resp({'success': True, 'msg': 'TR0263 - Updated Successfully'})
    client.update_test_run_results_by_code(
        'JlW1', 'vaQly', [{'case': 'TR0263', 'status': 1}, {'case': 'TR0264', 'status': 6}],
        comments='hello')
    call = client.session.post.call_args
    assert call.args[0].endswith('/api/v1/testRunResults/testrun/code')
    params = call.kwargs['params']
    assert params['project'] == 'JlW1'
    assert params['test_run'] == 'vaQly'
    assert params['comments'] == 'hello'
    sent = json.loads(params['result'])
    assert sent == {'0': {'case': 'TR0263', 'status': 1}, '1': {'case': 'TR0264', 'status': 6}}


def test_update_by_code_raises_on_success_false(client):
    """A success:false reply from testrun/code raises QATouchError instead of passing silently."""
    client.session.post.return_value = _resp({'success': False, 'error_msg': 'nope'})
    with pytest.raises(qc.QATouchError):
        client.update_test_run_results_by_code('JlW1', 'vaQly', [{'case': 'TR1', 'status': 1}])


# ---------------------------------------------------------------- trap 4: status spellings

@pytest.mark.parametrize('spelling', [
    'Not Applicable', 'Not-Applicable', 'not applicable', 'NOT-APPLICABLE', ' Not  Applicable ',
])
def test_status_spellings_normalise_to_one_form(spelling):
    """getAvailableStatuses says Not-Applicable; result reads say Not Applicable."""
    assert qc.normalize_status_name(spelling) == qc.normalize_status_name('Not Applicable')
    assert qc.status_code_for(spelling) == 6


def test_status_names_cover_all_eight_codes():
    """The status table covers all eight QA Touch codes with the right constants."""
    assert set(qc.STATUS_NAMES) == {1, 2, 3, 4, 5, 6, 7, 8}
    assert qc.STATUS_NOT_APPLICABLE == 6
    assert qc.STATUS_IN_PROGRESS == 7
    assert qc.STATUS_HOLD == 8


# ---------------------------------------------------------------- read-back verification

def _run_rows(*pairs):
    return [{'code': c, 'status': s, 'case_id': f'key-{c}'} for c, s in pairs]


def _paged(rows):
    """get_all_test_run_results pages until an empty page. A mock that returns
    the same rows on every call would loop forever, so give one page then none."""
    return [_resp({'data': rows}), _resp({'data': []})]


def test_verify_results_landed_reports_landed_missing_and_mismatched(client):
    """Read-back verification sorts sent results into landed, missing and mismatched."""
    client.session.get.side_effect = _paged(_run_rows(
        ('TR0001', 'Passed'), ('TR0002', 'Untested'), ('TR0004', 'Not-Applicable')))
    report = client.verify_results_landed('JlW1', 'vaQly', [
        {'case': 'TR0001', 'status': 1},   # landed
        {'case': 'TR0002', 'status': 5},   # sent Failed, run says Untested -> mismatch
        {'case': 'TR0003', 'status': 1},   # not in run
        {'case': 'TR0004', 'status': 6},   # landed, hyphenated spelling in run
    ])
    assert report['checked'] == 4
    assert report['landed'] == ['TR0001', 'TR0004']
    assert report['missing'] == ['TR0003']
    assert len(report['mismatched']) == 1
    assert 'TR0002' in report['mismatched'][0]


def test_verify_treats_hyphen_and_space_spellings_as_equal(client):
    """Read-back verification accepts a hyphenated status spelling as a match."""
    client.session.get.side_effect = _paged(_run_rows(('TR0009', 'In-Progress')))
    report = client.verify_results_landed('JlW1', 'r', [{'case': 'TR0009', 'status': 7}])
    assert report['mismatched'] == []
    assert report['landed'] == ['TR0009']


# ---------------------------------------------------------------- public case update

def test_update_test_case_sends_only_given_fields_as_query(client):
    """Partial update - only what you send changes."""
    client.session.post.return_value = _resp({'success': True})
    client.update_test_case('JlW1', 'B869bm', precondition='PRE', priority='Low')
    call = client.session.post.call_args
    assert call.args[0].endswith('/api/v1/testcase/update')
    assert call.kwargs['params'] == {
        'projectKey': 'JlW1', 'caseKey': 'B869bm', 'precondition': 'PRE', 'priority': 'Low'}


@pytest.mark.parametrize('field', ['tags', 'newtags', 'sectionKey', 'module_key'])
def test_update_test_case_refuses_fields_the_api_silently_ignores(client, field):
    """Tags have no parameter; sectionKey is accepted and does nothing. Refuse both."""
    with pytest.raises(qc.QATouchError) as exc:
        client.update_test_case('JlW1', 'B869bm', **{field: 'x'})
    assert field in str(exc.value)
    client.session.post.assert_not_called()


def test_update_test_case_refuses_empty_update(client):
    """A case update with no fields to change raises QATouchError."""
    with pytest.raises(qc.QATouchError):
        client.update_test_case('JlW1', 'B869bm')


# ---------------------------------------------------------------- run membership

def test_get_case_test_runs_flattens_nested_list(client):
    """getTestRunlist nests the list one level deeper than everything else."""
    client.session.get.return_value = _resp({'testrundetail': [[
        {'testrunkey': 'vaQly', 'resultKey': 'w5BNkb', 'status': 'Passed'},
        {'testrunkey': 'Gd4Rz', 'resultKey': 'abc', 'status': 'Failed'},
    ]]})
    runs = client.get_case_test_runs('B869bm')
    assert [r['testrunkey'] for r in runs] == ['vaQly', 'Gd4Rz']
    assert client.session.get.call_args.args[0].endswith('/api/v1/getTestRunlist/B869bm')


# ---------------------------------------------------------------- create endpoints (paths)

def test_create_module_uses_singular_path_and_query_params(client):
    """/api/v1/modules returns 404 - the real path is /api/v1/module with query params."""
    client.session.post.return_value = _resp({'success': True})
    client.create_module('JlW1', 'New Module', parent_key='PARENT')
    call = client.session.post.call_args
    assert call.args[0].endswith('/api/v1/module')
    assert call.kwargs['params'] == {'projectKey': 'JlW1', 'moduleName': 'New Module',
                                     'parentKey': 'PARENT'}


def test_create_project_uses_singular_path(client):
    """create_project posts to the singular /api/v1/project path with the name as a query."""
    client.session.post.return_value = _resp({'success': True})
    client.create_project('Probe')
    call = client.session.post.call_args
    assert call.args[0].endswith('/api/v1/project')
    assert call.kwargs['params'] == {'name': 'Probe'}
