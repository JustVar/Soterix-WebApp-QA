#!/usr/bin/env python3
"""Post-run result validator - compare local results vs QA Touch.

After a test run with QA Touch upload, this verifies that what QA Touch
shows matches what pytest recorded locally. Catches:
  - Uploads that reported success but wrote nothing (the API does this)
  - Partial uploads (network dropped mid-upload)
  - Mapping gaps (tests that ran but had no case to report into)
  - Failed uploads sitting in the retry log

Usage:
  python tools/validate_run.py <RUN_KEY>                  # validate a run
  python tools/validate_run.py <RUN_KEY> --local-count 45 # also compare a known count
  python tools/validate_run.py --check-failures           # pending retry uploads only

When logs/last_run_results.json exists and belongs to the same run, every
recorded test is reconciled case by case against the run. That is the check
that matters: it is how a silent no-op upload gets caught.

Exit codes:
  0 - validation passed
  1 - validation failed (mismatch or missing results)
  2 - unable to validate (API error, missing data)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, '.env'))

from tools.qatouch_client import (
    PYTEST_TO_QATOUCH,
    STATUS_NAMES,
    normalize_status_name,
)

FAILURE_LOG_PATH = Path(ROOT) / 'logs' / 'upload_failures.json'
RUN_RESULTS_PATH = Path(ROOT) / 'logs' / 'last_run_results.json'

PASS = '\033[92mPASS\033[0m'
FAIL = '\033[91mFAIL\033[0m'
WARN = '\033[93mWARN\033[0m'

# Statuses that mean somebody ran the case. Not Applicable is a deliberate
# exclusion, not an execution; In Progress and Hold are not finished.
EXECUTED = {'passed', 'failed', 'blocked', 'retest'}


def _count_statuses(rows: list[dict]) -> Counter:
    return Counter(normalize_status_name(r.get('status')) for r in rows)


def _reconcile_local(rows: list[dict], run_key: str) -> tuple[int, list[str]]:
    """Compare last_run_results.json against the run, case by case.

    Returns (records_checked, problems). Empty problems = every recorded
    test that mapped to a case shows the status pytest produced.
    """
    if not RUN_RESULTS_PATH.exists():
        return 0, []
    try:
        local = json.loads(RUN_RESULTS_PATH.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, ValueError):
        return 0, [f'{RUN_RESULTS_PATH.name} is malformed']
    if local.get('run_key') != run_key:
        print(f'  [{WARN}] {RUN_RESULTS_PATH.name} is for run {local.get("run_key")}, '
              f'not {run_key} - skipping per-case reconciliation')
        return 0, []

    by_case = {r.get('case_id'): normalize_status_name(r.get('status')) for r in rows}

    # Fold to the WORST outcome per case first. 42 case keys are shared by
    # more than one node id, and the upload sends the worst of them (a fail
    # wins over a pass). Comparing each record on its own therefore flagged
    # a false FAIL: the passing test that shares a case with a failing one
    # saw the run's (correct) Failed and reported a mismatch. Reconcile the
    # case the way it was uploaded.
    rank = {'passed': 0, 'skipped': 1, 'failed': 2}
    worst: dict[str, str] = {}
    unmapped = 0
    for rec in local.get('results') or []:
        outcome = rec.get('outcome')
        case_key = rec.get('case_key')
        if outcome not in PYTEST_TO_QATOUCH:
            continue
        if not case_key:
            unmapped += 1
            continue
        if rank.get(outcome, -1) > rank.get(worst.get(case_key), -1):
            worst[case_key] = outcome

    problems: list[str] = []
    for case_key, outcome in worst.items():
        want = normalize_status_name(STATUS_NAMES[PYTEST_TO_QATOUCH[outcome]])
        got = by_case.get(case_key)
        if got is None:
            problems.append(f'{case_key}: ran locally ({outcome}) but is not in the run')
        elif got != want:
            problems.append(f'{case_key}: local {outcome} -> expected {want}, run shows {got}')
    if unmapped:
        print(f'  [{WARN}] {unmapped} local result(s) had no QA Touch case - '
              f'nothing was uploaded for them (mapping gap)')
    return len(worst), problems


def validate_run(run_key: str, project_key: str, local_count: int | None = None) -> int:
    """Validate uploaded results for a QA Touch test run."""
    try:
        from tools.qatouch_client import QATouchClient
        client = QATouchClient()
    except Exception as e:
        print(f'  [{FAIL}] Cannot initialize QA Touch client: {e}')
        return 2

    print('\n=== Post-Run Validation ===')
    print(f'  Run key:     {run_key}')
    print(f'  Project:     {project_key}')
    print()

    try:
        rows = client.get_all_test_run_results(project_key, run_key)
    except Exception as e:
        print(f'  [{FAIL}] Failed to fetch run results: {e}')
        return 2

    counts = _count_statuses(rows)
    total = len(rows)
    executed = sum(n for st, n in counts.items() if st in EXECUTED)
    not_applicable = counts.get('not applicable', 0)
    untested = counts.get('untested', 0)

    print('  QA Touch results:')
    print(f'    Total cases:    {total}')
    print(f'    Executed:       {executed}  ('
          + ', '.join(f'{st}={counts.get(st, 0)}' for st in ('passed', 'failed', 'blocked', 'retest'))
          + ')')
    print(f'    Untested:       {untested}')
    print(f'    Not Applicable: {not_applicable}')
    other = {st: n for st, n in counts.items()
             if st not in EXECUTED and st not in ('untested', 'not applicable')}
    if other:
        print(f'    Other:          {dict(other)}')
    print()

    exit_code = 0

    if local_count is not None:
        diff = abs(executed - local_count)
        if diff == 0:
            print(f'  [{PASS}] Count match: local={local_count}, uploaded={executed}')
        elif diff <= 2:
            print(f'  [{WARN}] Minor mismatch: local={local_count}, uploaded={executed} '
                  f'(diff={diff}, within tolerance)')
        else:
            print(f'  [{FAIL}] Count mismatch: local={local_count}, uploaded={executed} '
                  f'(diff={diff})')
            exit_code = 1

    # The check that catches a silent no-op upload.
    checked, problems = _reconcile_local(rows, run_key)
    if checked:
        if problems:
            print(f'  [{FAIL}] {len(problems)} of {checked} local result(s) do not match the run:')
            for p in problems[:10]:
                print(f'          {p}')
            if len(problems) > 10:
                print(f'          ... and {len(problems) - 10} more')
            exit_code = 1
        else:
            print(f'  [{PASS}] All {checked} local result(s) reconcile with the run')

    if executed == 0 and (total - not_applicable) > 0:
        print(f'  [{FAIL}] No results uploaded - {total - not_applicable} runnable cases all untested')
        exit_code = 1

    if FAILURE_LOG_PATH.exists():
        try:
            failures = json.loads(FAILURE_LOG_PATH.read_text(encoding='utf-8'))
            pending = [f for f in failures if f.get('run_key') == run_key]
            if pending:
                n = sum(f.get('result_count', 0) for f in pending)
                print(f'  [{WARN}] {len(pending)} failed upload(s) pending retry '
                      f'({n} results in {FAILURE_LOG_PATH.name}) - run tools/retry_uploads.py')
                exit_code = max(exit_code, 1)
        except (json.JSONDecodeError, ValueError):
            pass

    print()
    print('  Validation: ' + ('\033[92mPASSED\033[0m' if exit_code == 0 else '\033[91mFAILED\033[0m'))
    return exit_code


def check_failures() -> int:
    """Report pending upload failures without validating a run."""
    if not FAILURE_LOG_PATH.exists():
        print('No pending upload failures.')
        return 0
    try:
        failures = json.loads(FAILURE_LOG_PATH.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, ValueError):
        print(f'Failure log is malformed: {FAILURE_LOG_PATH}')
        return 2
    if not failures:
        print('No pending upload failures.')
        return 0
    print(f'\n  {len(failures)} pending upload failure(s):')
    for i, f in enumerate(failures, 1):
        print(f'    {i}. run {f.get("run_key", "?")} - {f.get("result_count", "?")} results - '
              f'{f.get("timestamp", "?")}')
    print('\n  Retry with: python tools/retry_uploads.py')
    return 1


def main():
    parser = argparse.ArgumentParser(description='Validate QA Touch upload results')
    parser.add_argument('run_key', nargs='?', help='QA Touch test run key')
    parser.add_argument('--project', default=os.environ.get('QATOUCH_PROJECT_ID', 'JlW1'))
    parser.add_argument('--local-count', type=int, default=None,
                        help='Number of results uploaded locally, for a count check')
    parser.add_argument('--check-failures', action='store_true',
                        help='Only report pending upload failures')
    args = parser.parse_args()

    if args.check_failures:
        return check_failures()
    if not args.run_key:
        parser.error('run_key is required unless --check-failures is given')
    return validate_run(args.run_key, args.project, args.local_count)


if __name__ == '__main__':
    sys.exit(main())
