"""Run a Playwright suite into a freshly cloned QA Touch run.

Each invocation clones a template QA Touch run (smoke or sanity), gets a fresh
run key, then invokes pytest with --qatouch-upload --qatouch-run <new_key>.
Result: every execution lands in its own QA Touch run record, history is
preserved, and operators never need to know what the template keys are.

After pytest exits, this wrapper also:
  1. Updates `flaky_tests.json` from the per-nodeid records the reporter dumps
     to `logs/last_run_results.json` so failure-rate / last-failure history
     stays current for downstream tooling.
  2. Walks failed nodeids and files a Jira bug for each via
     `smart_jira_bug_creator.multi_gate_validation()`. The review queue is
     disabled - failures go straight to Jira, with RTM linkage back to the
     QA Touch case. Whole step gated by `BUG_CREATION_ENABLED=true` in `.env`
     (dry-run until explicitly enabled).

Usage:
  python tools/run_suite.py smoke
  python tools/run_suite.py sanity --env stage
  python tools/run_suite.py smoke -- -k test_login --headed   # pass-through pytest args
  python tools/run_suite.py smoke --no-bug-filing            # skip post-run bug step

Flags:
  --env qa|stage|prod      Target environment (default: $ENV or qa)
  --name "<name>"          Override the auto-generated run name
  --run-key <KEY>          Skip clone and reuse this existing run key
  --dry-run                Print the pytest command without cloning or executing
  --no-bug-filing          Skip the post-run history-update + bug-filer step

Templates resolved from env vars (with built-in fallbacks):
  QATOUCH_SMOKE_TEMPLATE_KEY  (default: vaXdn)
  QATOUCH_SANITY_TEMPLATE_KEY (default: zvXPw)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

from tools.qatouch_client import QATouchClient
from tools.qatouch_run_manager import _extract_run_key

PROJECT_KEY = os.environ.get('QATOUCH_PROJECT_ID', 'JlW1')
RUN_RESULTS_PATH = ROOT / 'logs' / 'last_run_results.json'

# pytest outcome name -> flaky_tests.json result keyword
_OUTCOME_TO_RESULT = {'passed': 'pass', 'failed': 'fail', 'skipped': 'skip'}

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
    stamp = datetime.now(UTC).strftime('%Y-%m-%dT%H:%MZ')
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


def _resolve_env_base_url(env_name: str) -> str | None:
    """Best-effort base_url lookup for the env-health gate in the bug filer.

    Returns None when config can't be loaded - the bug creator treats None as
    "skip the env-health check" so this stays non-fatal.
    """
    prev_env = os.environ.get('ENV')
    os.environ['ENV'] = env_name
    try:
        from config.base_config import load_config
        cfg = load_config()
        return getattr(cfg, 'base_url', None) or (
            cfg.get('base_url') if isinstance(cfg, dict) else None)
    except Exception:
        return None
    finally:
        if prev_env is None:
            os.environ.pop('ENV', None)
        else:
            os.environ['ENV'] = prev_env


def _post_run_bug_filing(suite: str, env_name: str) -> None:
    """Read last_run_results.json, update flaky history, file Jira bugs for failures.

    Every failure becomes a bug directly (review queue disabled). The only
    suppression is the env-health gate in the bug creator - a dead env skips
    filing to avoid floods. Whole step is gated by BUG_CREATION_ENABLED in
    .env (dry-run until explicitly enabled).
    """
    if not RUN_RESULTS_PATH.exists():
        print(f'[post-run] No {RUN_RESULTS_PATH.name} found - skipping bug filing.')
        return

    try:
        with open(RUN_RESULTS_PATH, encoding='utf-8') as f:
            payload = json.load(f)
    except Exception as e:
        print(f'[post-run] Failed to read run results: {e}', file=sys.stderr)
        return

    records = payload.get('results') or []
    if not records:
        print('[post-run] Run results file has no entries - skipping bug filing.')
        return

    # 1. Update flaky_tests.json so the bug creator's confidence/consecutive
    #    gates see the latest run in history.
    from tools.update_failure_history import load_db, save_db, update_history
    ts = datetime.now(UTC).isoformat()
    history_input = {}
    for rec in records:
        nodeid = rec.get('nodeid')
        outcome = rec.get('outcome')
        if not nodeid or outcome not in _OUTCOME_TO_RESULT:
            continue
        history_input[nodeid] = {
            'result': _OUTCOME_TO_RESULT[outcome],
            'ts': ts,
            'env': env_name,
        }
    db = load_db()
    db = update_history(db, history_input)
    save_db(db)
    print(f'[post-run] Updated flaky_tests.json with {len(history_input)} outcomes.')

    # 2. Walk failures through the multi-gate validator.
    failed_nodeids = [r['nodeid'] for r in records if r.get('outcome') == 'failed']
    if not failed_nodeids:
        print('[post-run] No failures - skipping bug filer.')
        return

    base_url = _resolve_env_base_url(env_name)
    bug_enabled = os.environ.get('BUG_CREATION_ENABLED', 'false').lower() in ('1', 'true', 'yes')
    print(f'[post-run] Processing {len(failed_nodeids)} failure(s) through bug filer '
          f'(BUG_CREATION_ENABLED={bug_enabled}).')

    from tools.smart_jira_bug_creator import multi_gate_validation
    actions: dict[str, int] = {}
    for nodeid in failed_nodeids:
        try:
            # auto_create=True (default) -> direct Jira bug creation; review
            # queue is intentionally disabled.
            result = multi_gate_validation(
                nodeid,
                env_base_url=base_url,
            )
        except Exception as e:
            print(f'[post-run]   {nodeid}: bug filer error: {e}', file=sys.stderr)
            actions['error'] = actions.get('error', 0) + 1
            continue
        action = result.get('action', 'unknown')
        actions[action] = actions.get(action, 0) + 1
        details = result.get('details') or {}
        reason = details.get('reason', '')
        print(f'[post-run]   {nodeid}: {action}'
              + (f' ({reason})' if reason else ''))

    print(f'[post-run] Bug-filer summary: {dict(actions)}')


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
    parser.add_argument('--no-bug-filing', action='store_true',
                        help='Skip the post-run history-update and bug-filer step.')

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

    if not args.no_bug_filing:
        print()
        _post_run_bug_filing(args.suite, args.env)

    return completed.returncode


if __name__ == '__main__':
    sys.exit(main())
