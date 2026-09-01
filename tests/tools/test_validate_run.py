"""Local reconciliation in validate_run.

The one that matters: a case key shared by several tests uploads the WORST
of their outcomes, so reconciliation must fold to the worst per case before
comparing - or a passing test that shares a case with a failing one reports
a false FAIL against the run's (correct) Failed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import validate_run as vr  # noqa: E402


def _local(tmp_path, results, run_key='R'):
    p = tmp_path / 'last_run_results.json'
    p.write_text(json.dumps({'run_key': run_key, 'results': results}), encoding='utf-8')
    return p


def test_a_shared_case_with_mixed_outcomes_is_not_a_false_fail(tmp_path):
    """test_a passed, test_b failed, both on K1. The run shows Failed (the
    worst, as uploaded). No mismatch."""
    p = _local(tmp_path, [
        {'nodeid': 't::a', 'outcome': 'passed', 'case_key': 'K1'},
        {'nodeid': 't::b', 'outcome': 'failed', 'case_key': 'K1'}])
    with patch.object(vr, 'RUN_RESULTS_PATH', p):
        checked, problems = vr._reconcile_local([{'case_id': 'K1', 'status': 'Failed'}], 'R')
    assert checked == 1
    assert problems == []


def test_a_genuine_mismatch_is_still_caught(tmp_path):
    """The fold must not hide a real drift: a case that ran failed while the
    run shows Passed is still a problem."""
    p = _local(tmp_path, [{'nodeid': 't::a', 'outcome': 'failed', 'case_key': 'K1'}])
    with patch.object(vr, 'RUN_RESULTS_PATH', p):
        _, problems = vr._reconcile_local([{'case_id': 'K1', 'status': 'Passed'}], 'R')
    assert len(problems) == 1
    assert 'K1' in problems[0]


def test_a_case_that_ran_but_is_not_in_the_run_is_flagged(tmp_path):
    p = _local(tmp_path, [{'nodeid': 't::a', 'outcome': 'passed', 'case_key': 'K9'}])
    with patch.object(vr, 'RUN_RESULTS_PATH', p):
        _, problems = vr._reconcile_local([], 'R')
    assert any('not in the run' in x for x in problems)


def test_unmapped_records_are_counted_not_reconciled(tmp_path):
    p = _local(tmp_path, [{'nodeid': 't::a', 'outcome': 'passed', 'case_key': None}])
    with patch.object(vr, 'RUN_RESULTS_PATH', p):
        checked, problems = vr._reconcile_local([], 'R')
    assert checked == 0
    assert problems == []
