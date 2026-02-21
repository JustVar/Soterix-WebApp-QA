"""Post-run result validator - compare local results vs QA Touch.

After a test run with QA Touch upload, this script verifies that the
uploaded results match what was collected locally. Catches:
  - Partial uploads (network dropped mid-upload)
  - Mismatched counts (mapping issues)
  - Failed uploads (results saved to failure log but never uploaded)

Usage:
  python tools/validate_run.py <RUN_KEY>                  # validate specific run
  python tools/validate_run.py <RUN_KEY> --local-count 45 # compare against known count
  python tools/validate_run.py --check-failures           # check for pending retry uploads

Exit codes:
  0 - validation passed (counts match or within tolerance)
  1 - validation failed (mismatch detected)
  2 - unable to validate (API error, missing data)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(ROOT, '.env'))

FAILURE_LOG_PATH = Path(ROOT) / 'logs' / 'upload_failures.json'

PASS = '\033[92mPASS\033[0m'
FAIL = '\033[91mFAIL\033[0m'
WARN = '\033[93mWARN\033[0m'


def validate_run(run_key: str, project_key: str, local_count: int | None = None) -> int:
    """Validate uploaded results for a QA Touch test run."""
    try:
        from tools.qatouch_client import QATouchClient
        client = QATouchClient()
    except Exception as e:
        print(f'  [{FAIL}] Cannot initialize QA Touch client: {e}')
        return 2

    print(f'\n=== Post-Run Validation ===')
    print(f'  Run key:     {run_key}')
    print(f'  Project:     {project_key}')
    print()

    # Fetch all results from QA Touch
    try:
        all_results = client.get_all_test_run_results(project_key, run_key)
    except Exception as e:
        print(f'  [{FAIL}] Failed to fetch run results: {e}')
        return 2

    total = len(all_results)
    passed = sum(1 for r in all_results if r.get('status') == '1' or r.get('code') == 'pass')
    failed = sum(1 for r in all_results if r.get('status') == '5' or r.get('code') == 'fail')
    blocked = sum(1 for r in all_results if r.get('status') == '3' or r.get('code') == 'blocked')
    untested = sum(1 for r in all_results if r.get('status') == '2' or r.get('code') == 'untested')
    executed = passed + failed + blocked

    print(f'  QA Touch results:')
    print(f'    Total cases:  {total}')
    print(f'    Executed:     {executed} (passed={passed}, failed={failed}, blocked={blocked})')
    print(f'    Untested:     {untested}')
    print()

    exit_code = 0

    # Compare against local count if provided
    if local_count is not None:
        diff = abs(executed - local_count)
        if diff == 0:
            print(f'  [{PASS}] Count match: local={local_count}, uploaded={executed}')
        elif diff <= 2:
            # Small tolerance for timing/skip differences
            print(f'  [{WARN}] Minor mismatch: local={local_count}, uploaded={executed} '
                  f'(diff={diff}, within tolerance)')
        else:
            print(f'  [{FAIL}] Count mismatch: local={local_count}, uploaded={executed} '
                  f'(diff={diff})')
            exit_code = 1

    # Check for zero uploads (likely upload failure)
    if executed == 0 and total > 0:
        print(f'  [{FAIL}] No results uploaded - {total} cases all untested')
        exit_code = 1

    # Check for pending failure retries
    if FAILURE_LOG_PATH.exists():
        try:
            with open(FAILURE_LOG_PATH) as f:
                failures = json.load(f)
            pending = [f for f in failures if f.get('run_key') == run_key]
            if pending:
                total_failed_results = sum(f.get('result_count', 0) for f in pending)
                print(f'  [{WARN}] {len(pending)} failed upload(s) pending retry '
                      f'({total_failed_results} results in {FAILURE_LOG_PATH})')
                exit_code = max(exit_code, 1)
        except (json.JSONDecodeError, ValueError):
            pass

    print()
    if exit_code == 0:
        print(f'  Validation: \033[92mPASSED\033[0m')
    else:
        print(f'  Validation: \033[91mFAILED\033[0m')

    return exit_code


def check_failures() -> int:
    """Check for any pending upload failures across all runs."""
    print(f'\n=== Upload Failure Check ===')

    if not FAILURE_LOG_PATH.exists():
        print(f'  [{PASS}] No failure log found - all uploads succeeded')
        return 0

    try:
        with open(FAILURE_LOG_PATH) as f:
            failures = json.load(f)
    except (json.JSONDecodeError, ValueError):
        print(f'  [{WARN}] Failure log exists but is malformed: {FAILURE_LOG_PATH}')
        return 2

    if not failures:
        print(f'  [{PASS}] Failure log is empty - all retries completed')
        return 0

    print(f'  [{FAIL}] {len(failures)} pending upload failure(s):')
    for i, f in enumerate(failures, 1):
        print(f'    {i}. Run {f.get("run_key", "?")} - '
              f'{f.get("result_count", "?")} results - '
              f'{f.get("timestamp", "?")}')
        print(f'       Error: {f.get("error", "unknown")}')

    print(f'\n  To retry: python tools/retry_uploads.py')
    print(f'  To clear: rm {FAILURE_LOG_PATH}')
    return 1


def main():
    parser = argparse.ArgumentParser(description='Post-run result validator')
    parser.add_argument('run_key', nargs='?', default=None,
                        help='QA Touch test run key to validate')
    parser.add_argument('--project', default=os.environ.get('QATOUCH_PROJECT_ID', 'JlW1'),
                        help='QA Touch project key (default: from env)')
    parser.add_argument('--local-count', type=int, default=None,
                        help='Expected number of executed tests from local run')
    parser.add_argument('--check-failures', action='store_true',
                        help='Check for pending upload failures (no run_key needed)')
    args = parser.parse_args()

    if args.check_failures:
        return check_failures()

    if not args.run_key:
        parser.error('run_key is required (or use --check-failures)')

    return validate_run(args.run_key, args.project, args.local_count)


if __name__ == '__main__':
    sys.exit(main())
