"""Retry failed QA Touch uploads from the failure log.

When the QA Touch reporter fails to upload results (after 3 retries),
it saves them to logs/upload_failures.json. This script retries those uploads.

Usage:
  python tools/retry_uploads.py           # retry all pending
  python tools/retry_uploads.py --dry-run # show what would be retried
  python tools/retry_uploads.py --clear   # clear failure log without retrying
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


def main():
    parser = argparse.ArgumentParser(description='Retry failed QA Touch uploads')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show pending retries without executing')
    parser.add_argument('--clear', action='store_true',
                        help='Clear failure log without retrying')
    args = parser.parse_args()

    if not FAILURE_LOG_PATH.exists():
        print('No failure log found - nothing to retry.')
        return 0

    try:
        with open(FAILURE_LOG_PATH) as f:
            failures = json.load(f)
    except (json.JSONDecodeError, ValueError):
        print(f'Failure log is malformed: {FAILURE_LOG_PATH}')
        return 2

    if not failures:
        print('Failure log is empty - nothing to retry.')
        return 0

    print(f'\n=== Upload Retry ===')
    print(f'  Pending: {len(failures)} failed upload(s)')
    print()

    if args.clear:
        FAILURE_LOG_PATH.unlink()
        print(f'  Cleared {len(failures)} entries from failure log.')
        return 0

    if args.dry_run:
        for i, entry in enumerate(failures, 1):
            print(f'  {i}. Run {entry.get("run_key", "?")} - '
                  f'{entry.get("result_count", "?")} results - '
                  f'{entry.get("timestamp", "?")}')
        print(f'\n  Run without --dry-run to execute retries.')
        return 0

    # Retry each failed upload
    try:
        from tools.qatouch_client import QATouchClient
        client = QATouchClient()
    except Exception as e:
        print(f'  [{FAIL}] Cannot initialize QA Touch client: {e}')
        return 2

    remaining = []
    succeeded = 0

    for i, entry in enumerate(failures, 1):
        run_key = entry.get('run_key', '?')
        project_key = entry.get('project_key', 'JlW1')
        results = entry.get('results', [])
        comment = entry.get('comment', 'Retry upload')

        print(f'  {i}. Retrying run {run_key} ({len(results)} results)... ', end='')

        try:
            client.update_test_run_results(
                project_key=project_key,
                test_run_key=run_key,
                results=results,
                comment=f'{comment} (retry)',
            )
            print(f'[{PASS}]')
            succeeded += 1
        except Exception as e:
            print(f'[{FAIL}] {e}')
            remaining.append(entry)

    # Update failure log
    if remaining:
        with open(FAILURE_LOG_PATH, 'w') as f:
            json.dump(remaining, f, indent=2)
        print(f'\n  Retried: {succeeded} succeeded, {len(remaining)} still failing')
        return 1
    else:
        FAILURE_LOG_PATH.unlink()
        print(f'\n  All {succeeded} retries succeeded. Failure log cleared.')
        return 0


if __name__ == '__main__':
    sys.exit(main())
