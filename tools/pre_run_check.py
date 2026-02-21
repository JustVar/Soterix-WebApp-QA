"""Pre-run health gate - verify all dependencies before starting a test run.

Checks:
  1. Target environment reachable (base_url responds)
  2. QA Touch API reachable (list projects call succeeds)
  3. QA Ops Hub healthy (GET /health/smoke on NUC)

Usage:
  python tools/pre_run_check.py                    # check all, default env
  python tools/pre_run_check.py --env qa           # specific environment
  python tools/pre_run_check.py --skip-qatouch     # skip QA Touch check
  python tools/pre_run_check.py --skip-qa-ops      # skip QA Ops Hub check

Exit codes:
  0 - all checks passed, safe to run
  1 - one or more checks failed, do NOT run

Integration:
  python tools/pre_run_check.py && pytest tests/ ...
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


# QA Ops Hub on NUC
QA_OPS_SMOKE_URL = os.environ.get(
    'QA_OPS_SMOKE_URL', 'http://192.168.1.174:8082/health/smoke')

PASS = '\033[92mPASS\033[0m'
FAIL = '\033[91mFAIL\033[0m'
SKIP = '\033[93mSKIP\033[0m'


def check_target_env(timeout: int = 15) -> bool:
    """Check that the target test environment is reachable."""
    # Load config dynamically based on ENV
    try:
        from config.base_config import config
        base_url = config.get('base_url', '')
    except Exception:
        base_url = os.environ.get('BASE_URL', '')

    if not base_url:
        print(f'  [{FAIL}] Target env: no base_url configured (check ENV var)')
        return False

    try:
        resp = requests.get(base_url, timeout=timeout, allow_redirects=True)
        if resp.status_code < 500:
            print(f'  [{PASS}] Target env: {base_url} (HTTP {resp.status_code}, '
                  f'{resp.elapsed.total_seconds():.1f}s)')
            return True
        else:
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


def check_qatouch(timeout: int = 15) -> bool:
    """Check that QA Touch API is reachable and credentials work."""
    api_key = os.environ.get('QATOUCH_API_KEY', '')
    domain = os.environ.get('QATOUCH_DOMAIN', '')

    if not api_key or not domain:
        print(f'  [{FAIL}] QA Touch: QATOUCH_API_KEY or QATOUCH_DOMAIN not set')
        return False

    try:
        resp = requests.get(
            'https://api.qatouch.com/api/v1/getAllProjects',
            headers={'api-token': api_key, 'domain': domain},
            timeout=timeout,
        )
        if resp.status_code == 200:
            projects = resp.json()
            count = len(projects) if isinstance(projects, list) else '?'
            print(f'  [{PASS}] QA Touch: API reachable ({count} projects, '
                  f'{resp.elapsed.total_seconds():.1f}s)')
            return True
        elif resp.status_code == 429:
            print(f'  [{FAIL}] QA Touch: rate limited (429) - wait and retry')
            return False
        elif resp.status_code == 401:
            print(f'  [{FAIL}] QA Touch: unauthorized (401) - check API key/domain')
            return False
        else:
            print(f'  [{FAIL}] QA Touch: HTTP {resp.status_code}')
            return False
    except requests.Timeout:
        print(f'  [{FAIL}] QA Touch: timed out after {timeout}s')
        return False
    except Exception as e:
        print(f'  [{FAIL}] QA Touch: {e}')
        return False


def check_qa_ops(timeout: int = 10) -> bool:
    """Check that QA Ops Hub on NUC is healthy."""
    url = QA_OPS_SMOKE_URL
    try:
        resp = requests.get(url, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            pending = data.get('pending', 0)
            uptime = data.get('uptime', 0)
            uptime_h = uptime / 3600 if uptime else 0
            print(f'  [{PASS}] QA Ops Hub: healthy ({pending} pending, '
                  f'uptime {uptime_h:.1f}h)')
            return True
        else:
            print(f'  [{FAIL}] QA Ops Hub: HTTP {resp.status_code}')
            return False
    except requests.ConnectionError:
        print(f'  [{FAIL}] QA Ops Hub: {url} - connection refused (NUC down?)')
        return False
    except requests.Timeout:
        print(f'  [{FAIL}] QA Ops Hub: {url} - timed out after {timeout}s')
        return False
    except Exception as e:
        print(f'  [{FAIL}] QA Ops Hub: {e}')
        return False


def main():
    parser = argparse.ArgumentParser(description='Pre-run health gate')
    parser.add_argument('--env', default=None,
                        help='Override ENV for target environment check')
    parser.add_argument('--skip-qatouch', action='store_true',
                        help='Skip QA Touch API check')
    parser.add_argument('--skip-qa-ops', action='store_true',
                        help='Skip QA Ops Hub check')
    parser.add_argument('--timeout', type=int, default=15,
                        help='HTTP timeout per check (default: 15s)')
    args = parser.parse_args()

    if args.env:
        os.environ['ENV'] = args.env

    print(f'\n=== Pre-Run Health Gate ===')
    print(f'  Time:  {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'  ENV:   {os.environ.get("ENV", "qa")}')
    print()

    results = []

    # 1. Target environment
    results.append(('Target Env', check_target_env(args.timeout)))

    # 2. QA Touch
    if args.skip_qatouch:
        print(f'  [{SKIP}] QA Touch: skipped (--skip-qatouch)')
    else:
        results.append(('QA Touch', check_qatouch(args.timeout)))

    # 3. QA Ops Hub
    if args.skip_qa_ops:
        print(f'  [{SKIP}] QA Ops Hub: skipped (--skip-qa-ops)')
    else:
        results.append(('QA Ops Hub', check_qa_ops(min(args.timeout, 10))))

    print()

    # Summary
    failed = [name for name, ok in results if not ok]
    if failed:
        print(f'  GATE: \033[91mBLOCKED\033[0m - {len(failed)} check(s) failed: '
              f'{", ".join(failed)}')
        print(f'  Action: Fix the issues above before starting the test run.')
        print()
        return 1
    else:
        passed = len(results)
        print(f'  GATE: \033[92mCLEAR\033[0m - all {passed} checks passed')
        print(f'  Action: Safe to proceed with test run.')
        print()
        return 0


if __name__ == '__main__':
    sys.exit(main())
