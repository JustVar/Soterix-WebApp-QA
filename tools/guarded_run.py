"""Guarded test run - chains all guardrails into a single command.

Orchestrates: pre-run check -> lock -> timeout -> pytest -> validate -> unlock

Usage:
  # Smoke run on QA environment
  python tools/guarded_run.py --env qa --type smoke

  # Regression with QA Touch upload
  python tools/guarded_run.py --env qa --type regression --qatouch-run d6pw

  # Custom pytest args
  python tools/guarded_run.py --env qa --type sanity -- -k "login" --headed

  # Skip specific gates
  python tools/guarded_run.py --env qa --type smoke --skip-health --skip-lock

Guardrail chain:
  1. Pre-run health gate (target env + QA Touch + QA Ops Hub)
  2. Run lock acquisition (prevent concurrent runs)
  3. Timeout wrapper (hard kill if exceeded)
  4. pytest execution (with QA Touch upload if --qatouch-run)
  5. Post-run validation (compare local vs QA Touch counts)
  6. Lock release (always, even on failure)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Import guardrail modules
sys.path.insert(0, str(ROOT))


TIMEOUT_PRESETS = {
    'smoke': 30,
    'sanity': 60,
    'regression': 180,
    'full': 240,
}


def main():
    parser = argparse.ArgumentParser(
        description='Guarded test run with all safety guardrails',
        usage='%(prog)s --env ENV --type TYPE [options] [-- pytest args]',
    )
    parser.add_argument('--env', required=True,
                        help='Target environment (qa, stage, prod)')
    parser.add_argument('--type', choices=list(TIMEOUT_PRESETS.keys()),
                        default='regression', help='Run type (sets timeout)')
    parser.add_argument('--qatouch-run', default=None,
                        help='QA Touch run key for result upload')
    parser.add_argument('--timeout', type=int, default=None,
                        help='Override timeout in minutes')
    parser.add_argument('--skip-health', action='store_true',
                        help='Skip pre-run health gate')
    parser.add_argument('--skip-lock', action='store_true',
                        help='Skip run lock')
    parser.add_argument('--skip-validate', action='store_true',
                        help='Skip post-run validation')
    parser.add_argument('--skip-qatouch-check', action='store_true',
                        help='Skip QA Touch connectivity check in health gate')
    parser.add_argument('--skip-qa-ops-check', action='store_true',
                        help='Skip QA Ops Hub check in health gate')
    parser.add_argument('pytest_args', nargs=argparse.REMAINDER,
                        help='Additional pytest arguments (after --)')
    args = parser.parse_args()

    # Parse extra pytest args
    extra_args = args.pytest_args
    if extra_args and extra_args[0] == '--':
        extra_args = extra_args[1:]

    timeout_min = args.timeout or TIMEOUT_PRESETS[args.type]
    run_type = args.type

    print(f'\n{"=" * 60}')
    print('  GUARDED TEST RUN')
    print(f'  Env: {args.env} | Type: {run_type} | Timeout: {timeout_min}m')
    if args.qatouch_run:
        print(f'  QA Touch run: {args.qatouch_run}')
    print(f'  Time: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'{"=" * 60}')

    # Set ENV for downstream tools
    os.environ['ENV'] = args.env

    # ── Step 1: Pre-run health gate ──────────────────────────
    if not args.skip_health:
        print('\n[1/5] Pre-run health gate...')
        health_cmd = [sys.executable, str(ROOT / 'tools' / 'pre_run_check.py'),
                      '--env', args.env]
        if args.skip_qatouch_check:
            health_cmd.append('--skip-qatouch')
        if args.skip_qa_ops_check:
            health_cmd.append('--skip-qa-ops')

        result = subprocess.run(health_cmd)
        if result.returncode != 0:
            print('\n  ABORT: Health gate failed. Fix issues above before running.')
            return 1
    else:
        print('\n[1/5] Pre-run health gate... SKIPPED')

    # ── Step 2: Acquire run lock ─────────────────────────────
    lock_acquired = False
    if not args.skip_lock:
        print('\n[2/5] Acquiring run lock...')
        from tools.run_lock import _remove_lock, acquire
        lock_acquired = acquire(args.env, run_type=run_type)
        if not lock_acquired:
            print(f'\n  ABORT: Could not acquire lock for env={args.env}.')
            return 1
    else:
        print('\n[2/5] Run lock... SKIPPED')

    # ── Step 3+4: Run pytest with timeout ────────────────────
    try:
        print(f'\n[3/5] Starting pytest (timeout: {timeout_min}m)...\n')

        pytest_cmd = [sys.executable, '-m', 'pytest']

        # Add QA Touch upload flags if run key provided
        if args.qatouch_run:
            pytest_cmd.extend(['--qatouch-upload', '--qatouch-run', args.qatouch_run])

        # Add extra pytest args
        pytest_cmd.extend(extra_args)

        # Run with timeout
        start_time = time.time()
        try:
            result = subprocess.run(pytest_cmd, timeout=timeout_min * 60,
                                    cwd=str(ROOT))
            pytest_exit = result.returncode
        except subprocess.TimeoutExpired:
            elapsed = (time.time() - start_time) / 60
            print(f'\n  TIMEOUT: pytest exceeded {timeout_min}m limit '
                  f'(ran for {elapsed:.1f}m)')
            pytest_exit = 124

        elapsed = (time.time() - start_time) / 60
        print(f'\n[4/5] pytest finished (exit={pytest_exit}, {elapsed:.1f}m)')

        # ── Step 5: Post-run validation ──────────────────────
        if args.qatouch_run and not args.skip_validate and pytest_exit != 124:
            print('\n[5/5] Post-run validation...')
            validate_cmd = [sys.executable, str(ROOT / 'tools' / 'validate_run.py'),
                            args.qatouch_run, '--project',
                            os.environ.get('QATOUCH_PROJECT_ID', 'JlW1')]
            subprocess.run(validate_cmd)
        else:
            reason = 'no QA Touch run' if not args.qatouch_run else \
                     'skipped' if args.skip_validate else 'timed out'
            print(f'\n[5/5] Post-run validation... SKIPPED ({reason})')

        return pytest_exit

    finally:
        # ── Always release lock ──────────────────────────────
        if lock_acquired:
            from tools.run_lock import _remove_lock
            _remove_lock(args.env)
            print(f'\n  Lock released for env={args.env}')

        print(f'\n{"=" * 60}')
        print('  RUN COMPLETE')
        print(f'  Time: {time.strftime("%Y-%m-%d %H:%M:%S")}')
        print(f'{"=" * 60}\n')


if __name__ == '__main__':
    sys.exit(main())
