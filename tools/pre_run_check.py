"""Ask whether the QA server answers before a run starts.

One check: the base_url of the active env file (config/env/<ENV>.py)
returns an HTTP status below 500 within the timeout. run.py --check
runs this first. Nothing else is checked here. QA Touch is an optional
upload, and a run needs no other service.

Usage:
  python tools/pre_run_check.py                 # the default env (qa)
  python tools/pre_run_check.py --env qa        # a named env file
  python tools/pre_run_check.py --timeout 30    # seconds to wait (default 15)

Exit codes:
  0 - the server answered, safe to run
  1 - no answer, do not run
"""
from __future__ import annotations

import argparse
import os
import sys
import time

# Ensure repo root is on sys.path
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(ROOT, '.env'))

import requests

PASS = '\033[92mPASS\033[0m'
FAIL = '\033[91mFAIL\033[0m'


def check_target_env(timeout: int = 15) -> bool:
    """True when the active env file's base_url answers."""
    try:
        from config.base_config import config
        base_url = config.get('base_url', '')
    except Exception as e:
        print(f'  [{FAIL}] Target env: the env file did not load ({e})')
        return False

    if not base_url:
        print(f'  [{FAIL}] Target env: no base_url in the env file (check ENV)')
        return False

    try:
        resp = requests.get(base_url, timeout=timeout, allow_redirects=True)
        if resp.status_code < 500:
            print(f'  [{PASS}] Target env: {base_url} (HTTP {resp.status_code}, '
                  f'{resp.elapsed.total_seconds():.1f}s)')
            return True
        print(f'  [{FAIL}] Target env: {base_url} returned HTTP {resp.status_code}')
        return False
    except requests.ConnectionError:
        print(f'  [{FAIL}] Target env: {base_url} - connection refused')
        return False
    except requests.Timeout:
        print(f'  [{FAIL}] Target env: {base_url} - timed out after {timeout}s')
        return False
    except Exception as e:
        print(f'  [{FAIL}] Target env: {base_url} - {e}')
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Ask whether the QA server answers')
    parser.add_argument('--env', default=None,
                        help='the env file to read the server address from (default: ENV, else qa)')
    parser.add_argument('--timeout', type=int, default=15,
                        help='seconds to wait for an answer (default: 15)')
    args = parser.parse_args(argv)

    if args.env:
        os.environ['ENV'] = args.env

    print('\n=== Pre-run check ===')
    print(f'  Time:  {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'  ENV:   {os.environ.get("ENV", "qa")}')
    print()

    ok = check_target_env(args.timeout)
    print()
    if not ok:
        print('  Result: \033[91mBLOCKED\033[0m - the server did not answer. Fix that, then run again.')
        print()
        return 1
    print('  Result: \033[92mCLEAR\033[0m - the server answers. Safe to run.')
    print()
    return 0


if __name__ == '__main__':
    sys.exit(main())
