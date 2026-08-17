#!/usr/bin/env python3
"""Retry failed QA Touch uploads from the failure log.

When the reporter cannot upload results after its retries, it saves them to
logs/upload_failures.json. This replays them.

Usage:
  python tools/retry_uploads.py           # retry all pending
  python tools/retry_uploads.py --dry-run # show what would be retried
  python tools/retry_uploads.py --clear   # clear failure log without retrying

Every retry is read back from the run afterwards. QA Touch answers success
for uploads it silently discards, so an entry only leaves the log when the
run actually shows the status we sent.

Entries whose case identifiers are not case codes (TR0263) cannot be
replayed - the results API ignores case keys and per-run result keys and
reports success anyway. Those come from the reporter before 2026-08-17.
They are moved to logs/upload_failures_unreplayable.json rather than
silently "succeeding".
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(ROOT, '.env'))

FAILURE_LOG_PATH = Path(ROOT) / 'logs' / 'upload_failures.json'
UNREPLAYABLE_PATH = Path(ROOT) / 'logs' / 'upload_failures_unreplayable.json'

CASE_CODE_RE = re.compile(r'^TR\d+$')

PASS = '\033[92mPASS\033[0m'
FAIL = '\033[91mFAIL\033[0m'
WARN = '\033[93mWARN\033[0m'


def _replayable(entry: dict) -> bool:
    """True when every result identifies its case by code (TR0263)."""
    return all(CASE_CODE_RE.match(str(r.get('case', ''))) for r in entry.get('results', []))


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
        with open(FAILURE_LOG_PATH, encoding='utf-8') as f:
            failures = json.load(f)
    except (json.JSONDecodeError, ValueError):
        print(f'Failure log is malformed: {FAILURE_LOG_PATH}')
        return 2

    if not failures:
        print('Failure log is empty - nothing to retry.')
        return 0

    print('\n=== Upload Retry ===')
    print(f'  Pending: {len(failures)} failed upload(s)')
    print()

    if args.clear:
        FAILURE_LOG_PATH.unlink()
        print(f'  Cleared {len(failures)} entries from failure log.')
        return 0

    replayable = [e for e in failures if _replayable(e)]
    stale = [e for e in failures if not _replayable(e)]

    if args.dry_run:
        for i, entry in enumerate(failures, 1):
            tag = '' if _replayable(entry) else '  <- NOT replayable (case keys, not codes)'
            print(f'  {i}. Run {entry.get("run_key", "?")} - '
                  f'{entry.get("result_count", "?")} results - '
                  f'{entry.get("timestamp", "?")}{tag}')
        print('\n  Run without --dry-run to execute retries.')
        return 0

    if stale:
        UNREPLAYABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing = []
        if UNREPLAYABLE_PATH.exists():
            try:
                existing = json.loads(UNREPLAYABLE_PATH.read_text(encoding='utf-8'))
            except (json.JSONDecodeError, ValueError):
                existing = []
        UNREPLAYABLE_PATH.write_text(json.dumps(existing + stale, indent=2), encoding='utf-8')
        print(f'  [{WARN}] {len(stale)} entry(ies) use case keys instead of case codes and '
              f'cannot be replayed. Moved to {UNREPLAYABLE_PATH.name}.')
        print('         The results API ignores case keys and reports success anyway, so a')
        print('         "successful" retry of these would have written nothing.')
        print()

    if not replayable:
        FAILURE_LOG_PATH.unlink()
        print('  Nothing replayable remains. Failure log cleared.')
        return 1 if stale else 0

    try:
        from tools.qatouch_client import QATouchClient
        client = QATouchClient()
    except Exception as e:
        print(f'  [{FAIL}] Cannot initialize QA Touch client: {e}')
        return 2

    remaining = []
    succeeded = 0

    for i, entry in enumerate(replayable, 1):
        run_key = entry.get('run_key', '?')
        project_key = entry.get('project_key', 'JlW1')
        results = [{'case': r['case'], 'status': r['status']} for r in entry.get('results', [])]
        comment = entry.get('comment', 'Retry upload')

        print(f'  {i}. Retrying run {run_key} ({len(results)} results)... ', end='')
        try:
            client.update_test_run_results_by_code(
                project_key=project_key,
                test_run_key=run_key,
                results=results,
                comments=f'{comment} (retry)',
            )
            report = client.verify_results_landed(project_key, run_key, results)
        except Exception as e:
            print(f'[{FAIL}] {e}')
            remaining.append(entry)
            continue

        problems = report['mismatched'] + [f'{c}: not in run' for c in report['missing']]
        if problems:
            print(f'[{FAIL}] uploaded but {len(problems)} did not land: {problems[:3]}')
            remaining.append(entry)
        else:
            print(f'[{PASS}] verified {len(report["landed"])} in run')
            succeeded += 1

    if remaining:
        with open(FAILURE_LOG_PATH, 'w', encoding='utf-8') as f:
            json.dump(remaining, f, indent=2)
        print(f'\n  Retried: {succeeded} succeeded, {len(remaining)} still failing')
        return 1
    FAILURE_LOG_PATH.unlink()
    print(f'\n  All {succeeded} retries succeeded and verified. Failure log cleared.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
