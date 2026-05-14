"""Run a Playwright suite into a freshly cloned QA Touch run.

Each invocation clones a template QA Touch run (smoke or sanity), gets a fresh
run key, then invokes pytest with --qatouch-upload --qatouch-run <new_key>.
Result: every execution lands in its own QA Touch run record, history is
preserved, and operators never need to know what the template keys are.

Usage:
  python tools/run_suite.py smoke
  python tools/run_suite.py sanity --env stage
  python tools/run_suite.py smoke -- -k test_login --headed   # pass-through pytest args

Flags:
  --env qa|stage|prod   Target environment (default: $ENV or qa)
  --name "<name>"       Override the auto-generated run name
  --run-key <KEY>       Skip clone and reuse this existing run key
  --dry-run             Clone + print the pytest command, don't execute

Templates resolved from env vars (with built-in fallbacks):
  QATOUCH_SMOKE_TEMPLATE_KEY  (default: vaXdn)
  QATOUCH_SANITY_TEMPLATE_KEY (default: zvXPw)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from tools.qatouch_client import QATouchClient
from tools.qatouch_run_manager import _extract_run_key

PROJECT_KEY = os.environ.get('QATOUCH_PROJECT_ID', 'JlW1')

SUITES = {
    'smoke': {
        'template_env': 'QATOUCH_SMOKE_TEMPLATE_KEY',
        'template_default': 'vaXdn',
        'marker': 'smoke',
    },
    'sanity': {
        'template_env': 'QATOUCH_SANITY_TEMPLATE_KEY',
        'template_default': 'zvXPw',
        'marker': 'sanity',
    },
}


def _resolve_template_key(suite: str) -> str:
    cfg = SUITES[suite]
    return os.environ.get(cfg['template_env'], cfg['template_default'])


def _build_run_name(suite: str, env: str) -> str:
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')
    return f'{suite.capitalize()} - {env} - {stamp}'


def _clone(suite: str, run_name: str) -> str:
    template_key = _resolve_template_key(suite)
    print(f'Cloning template run [{template_key}] -> "{run_name}"...')

    client = QATouchClient()
    result = client.clone_test_run(
        project_key=PROJECT_KEY,
        source_run_key=template_key,
        new_name=run_name,
    )
    new_key = _extract_run_key(result)
    if new_key == '?':
        msg = result.get('msg', '')
        raise SystemExit(
            f'Could not parse new run key from QA Touch response: {msg!r}\n'
            f'  Full response: {result}'
        )
    print(f'  New run key: {new_key}')
    return new_key


def _build_pytest_cmd(marker: str, run_key: str, extra: list[str]) -> list[str]:
    return [
        sys.executable, '-m', 'pytest',
        '-m', marker,
        '--qatouch-upload',
        '--qatouch-run', run_key,
        *extra,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(
        prog='run_suite',
        description='Clone a QA Touch run and execute the matching pytest suite.',
    )
    parser.add_argument('suite', choices=sorted(SUITES.keys()),
                        help='Which suite to run (drives both pytest marker and template).')
    parser.add_argument('--env', default=os.environ.get('ENV', 'qa'),
                        choices=['qa', 'stage', 'prod'],
                        help='Target environment (default: $ENV or qa).')
    parser.add_argument('--name', default=None,
                        help='Override the auto-generated run name.')
    parser.add_argument('--run-key', default=None,
                        help='Skip clone and use this existing run key instead.')
    parser.add_argument('--dry-run', action='store_true',
                        help='Print the pytest command without cloning or executing.')

    # parse_known_args puts unrecognized flags into `pytest_extra` so we can
    # forward arbitrary pytest args (-k, --headed, etc.) without an explicit `--`.
    args, pytest_extra = parser.parse_known_args()

    # Validate creds upfront so we fail before pytest spins up
    if not os.environ.get('QATOUCH_API_KEY') or not os.environ.get('QATOUCH_DOMAIN'):
        print('ERROR: QATOUCH_API_KEY and QATOUCH_DOMAIN must be set (see .env).',
              file=sys.stderr)
        return 2

    if args.run_key:
        run_key = args.run_key
        print(f'Reusing existing run key: {run_key}')
    elif args.dry_run:
        # Don't create a real QA Touch run record during a dry-run - print what
        # would be cloned and use a placeholder key in the pytest command.
        template_key = _resolve_template_key(args.suite)
        run_name = args.name or _build_run_name(args.suite, args.env)
        print(f'[dry-run] Would clone template [{template_key}] -> "{run_name}"')
        run_key = '<NEW_KEY>'
    else:
        run_name = args.name or _build_run_name(args.suite, args.env)
        run_key = _clone(args.suite, run_name)

    # Strip a leading '--' (some shells/users still pass it explicitly)
    extra = list(pytest_extra)
    if extra and extra[0] == '--':
        extra = extra[1:]

    cmd = _build_pytest_cmd(SUITES[args.suite]['marker'], run_key, extra)
    pretty = ' '.join(c if ' ' not in c else f'"{c}"' for c in cmd)

    print()
    print(f'Suite:     {args.suite}')
    print(f'Env:       {args.env}')
    print(f'Run key:   {run_key}')
    print(f'Command:   {pretty}')
    print()

    if args.dry_run:
        print('[dry-run - not executing pytest]')
        return 0

    env = dict(os.environ)
    env['ENV'] = args.env
    completed = subprocess.run(cmd, cwd=str(ROOT), env=env)
    return completed.returncode


if __name__ == '__main__':
    sys.exit(main())
