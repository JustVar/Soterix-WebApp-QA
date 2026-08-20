#!/usr/bin/env python3
"""Run a Playwright suite and land the results in a fresh QA Touch run.

One command. It works out which QA Touch cases the tests map to, creates a
run holding exactly those cases, runs pytest with upload switched on, then
reads the run back and reconciles it against what pytest recorded.

    python tools/run_suite.py smoke --env qa --version 1.8.0
    python tools/run_suite.py tests/ui/views --env qa
    python tools/run_suite.py smoke -k login --headed          # extra args go to pytest
    python tools/run_suite.py smoke --run-key vaQly            # reuse an existing run
    python tools/run_suite.py smoke --dry-run                  # plan only, no run created

The target is either a suite name (smoke, sanity, regression - a pytest
marker) or anything pytest accepts as a target: a path, a file, a node id.

Why the run is built from the mapping, not cloned from a template
    A cloned template drags in whatever cases the template had. Building the
    run from the cases the collected tests actually map to means the run
    holds exactly what is about to execute - nothing lands Untested because
    no test exists for it, and pass rates mean something.

Needs (see docs/QA_TOUCH_INTEGRATION.md)
    QATOUCH_API_KEY, QATOUCH_DOMAIN, QATOUCH_PROJECT_ID   in .env
    QATOUCH_ASSIGN_TO      user key the run is assigned to   (or --assign)
    QATOUCH_MILESTONE_KEY  release the run belongs to        (or --milestone)
    Find them:  python tools/qatouch_run_manager.py users
                python tools/qatouch_run_manager.py milestone <NAME>

After pytest
    1. validate - reads the run back and reconciles every local result against
       it. QA Touch reports success for uploads it discards, so this is the
       step that proves the results are really there.
    2. flaky history - logs/last_run_results.json feeds flaky_tests.json.
    3. bug filing - OFF unless BOTH --file-bugs is passed AND
       BUG_CREATION_ENABLED=true in .env. Failures going straight to Jira is
       not the intended end state; the plan is a review queue first. Until
       that exists this stays a deliberate, double-opted-in action.

Exit code is pytest's exit code, or 1 if validation failed, or 2 for setup
problems (missing keys, nothing mapped).
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

_print = print
print = functools.partial(_print, flush=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / '.env')

from tools.qatouch_client import QATouchClient  # noqa: E402
from tools.qatouch_run_manager import _extract_run_key  # noqa: E402

PROJECT_KEY = os.environ.get('QATOUCH_PROJECT_ID', 'JlW1')
MAPPING_PATH = ROOT / 'config' / 'qatouch_case_mapping.json'
RUN_RESULTS_PATH = ROOT / 'logs' / 'last_run_results.json'

# Suite name -> pytest marker. Anything else is passed to pytest as a target.
SUITE_MARKERS = {'smoke': 'smoke', 'sanity': 'sanity', 'regression': 'regression'}

# pytest outcome name -> flaky_tests.json result keyword
_OUTCOME_TO_RESULT = {'passed': 'pass', 'failed': 'fail', 'skipped': 'skip'}


# ---------------------------------------------------------------- planning

def _pytest_target_args(target: str) -> list[str]:
    """Turn the CLI target into pytest arguments."""
    if target in SUITE_MARKERS:
        return ['-m', SUITE_MARKERS[target]]
    return [target]


def _collect_nodeids(target_args: list[str], extra: list[str]) -> list[str]:
    """Ask pytest which tests it would run. No browser is started."""
    # pytest.ini already carries -q, which prints one node id per line. Adding
    # another -q would make it -qq and print per-file counts instead.
    #
    # pytest.ini also carries --html=reports/report.html, and pytest-html
    # writes unconditionally - so without an override this planning pass
    # replaces the last real report with an empty "0 tests" one (audit S6).
    # The later --html wins, so point it at a scratch file under logs/.
    # SEND_TEST_REPORT is stripped so conftest's mailer can never fire on a
    # collect run.
    cmd = [sys.executable, '-m', 'pytest', '--collect-only',
           '-p', 'no:cacheprovider',
           '--html', str(ROOT / 'logs' / 'collect_scratch.html'),
           *target_args, *extra]
    collect_env = {k: v for k, v in os.environ.items() if k != 'SEND_TEST_REPORT'}
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                          env=collect_env)
    nodeids = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        # Collected node ids look like tests/ui/x.py::Class::test[chromium].
        if '::' in line and not line.startswith(('=', '-', 'ERROR', 'WARN')):
            nodeids.append(line)
    if proc.returncode not in (0, 5) and not nodeids:  # 5 = nothing collected
        print(proc.stdout[-1500:], file=sys.stderr)
        print(proc.stderr[-1500:], file=sys.stderr)
        raise SystemExit(f'pytest --collect-only failed (exit {proc.returncode})')
    return nodeids


def _load_mapping() -> dict[str, str]:
    """nodeid -> case_key from config/qatouch_case_mapping.json."""
    if not MAPPING_PATH.exists():
        raise SystemExit(f'Mapping file missing: {MAPPING_PATH}\n'
                         f'  Build it: python tools/qatouch_mapper.py build')
    data = json.loads(MAPPING_PATH.read_text(encoding='utf-8'))
    return {nodeid: info['case_key'] for nodeid, info in data.get('mappings', {}).items()}


def _map_nodeids(nodeids: list[str], mapping: dict[str, str]) -> tuple[dict[str, str], list[str]]:
    """Resolve each nodeid to a case key the way the reporter does.

    Exact match first, then with the [chromium] / [param] suffix stripped.
    Returns (mapped {nodeid: case_key}, unmapped [nodeid]).
    """
    mapped: dict[str, str] = {}
    unmapped: list[str] = []
    for nodeid in nodeids:
        candidates = [nodeid]
        if '[' in nodeid:
            candidates.append(nodeid.split('[')[0])
        for c in candidates:
            if c in mapping:
                mapped[nodeid] = mapping[c]
                break
        else:
            unmapped.append(nodeid)
    return mapped, unmapped


def _build_run_name(target: str, env: str, version: str | None) -> str:
    """Follow the team convention: [Type] - [Env] - [Version] - [Date]."""
    label = target.capitalize() if target in SUITE_MARKERS else Path(target).name or target
    stamp = datetime.now(UTC).strftime('%Y-%m-%d %H:%M')
    parts = [f'Automation {label}', env.upper()]
    if version:
        parts.append(version)
    parts.append(stamp)
    return ' - '.join(parts)


def _create_run(name: str, case_keys: list[str], assign_to: str, milestone: str) -> str:
    client = QATouchClient()
    result = client.create_test_run(
        project_key=PROJECT_KEY, name=name, assign_to=assign_to,
        milestone_key=milestone, case_ids=case_keys)
    key = _extract_run_key(result)
    if key == '?':
        raise SystemExit(f'Could not read the new run key from QA Touch: {result}')
    return key


# ---------------------------------------------------------------- post-run

def _update_flaky_history(env_name: str) -> None:
    """Feed the per-nodeid outcomes into flaky_tests.json."""
    if not RUN_RESULTS_PATH.exists():
        print(f'[post-run] No {RUN_RESULTS_PATH.name} - skipping flaky history.')
        return
    try:
        payload = json.loads(RUN_RESULTS_PATH.read_text(encoding='utf-8'))
    except Exception as e:
        print(f'[post-run] Could not read run results: {e}', file=sys.stderr)
        return
    from tools.update_failure_history import load_db, save_db, update_history
    ts = datetime.now(UTC).isoformat()
    history = {}
    for rec in payload.get('results') or []:
        nodeid, outcome = rec.get('nodeid'), rec.get('outcome')
        if nodeid and outcome in _OUTCOME_TO_RESULT:
            history[nodeid] = {'result': _OUTCOME_TO_RESULT[outcome], 'ts': ts, 'env': env_name}
    db = update_history(load_db(), history)
    save_db(db)
    print(f'[post-run] flaky_tests.json updated with {len(history)} outcome(s).')


def _file_bugs() -> None:
    """Walk failures through the Jira bug filer. Double-gated - see module doc."""
    enabled = os.environ.get('BUG_CREATION_ENABLED', 'false').lower() in ('1', 'true', 'yes')
    if not enabled:
        print('[post-run] --file-bugs given but BUG_CREATION_ENABLED is not true in .env - '
              'not filing.')
        return
    if not RUN_RESULTS_PATH.exists():
        return
    payload = json.loads(RUN_RESULTS_PATH.read_text(encoding='utf-8'))
    failed = [r['nodeid'] for r in payload.get('results') or [] if r.get('outcome') == 'failed']
    if not failed:
        print('[post-run] No failures - nothing to file.')
        return
    from tools.smart_jira_bug_creator import multi_gate_validation
    print(f'[post-run] Filing {len(failed)} failure(s) through the bug filer...')
    summary: dict[str, int] = {}
    for nodeid in failed:
        try:
            result = multi_gate_validation(nodeid)
            action = result.get('action', 'unknown')
        except Exception as e:
            action = 'error'
            print(f'[post-run]   {nodeid}: {e}', file=sys.stderr)
        summary[action] = summary.get(action, 0) + 1
        print(f'[post-run]   {nodeid}: {action}')
    print(f'[post-run] Bug filer summary: {summary}')


# ---------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(
        prog='run_suite',
        description='Run a Playwright suite into a fresh QA Touch run and verify the results landed.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split('Why the run')[0].split('One command.')[-1],
    )
    parser.add_argument('target',
                        help='Suite name (smoke, sanity, regression) or any pytest target')
    parser.add_argument('--env', default=os.environ.get('ENV', 'qa'),
                        choices=['qa', 'stage', 'prod'])
    parser.add_argument('--version', default=None, help='Release version for the run name')
    parser.add_argument('--name', default=None, help='Override the run name')
    parser.add_argument('--run-key', default=None, help='Reuse this run instead of creating one')
    parser.add_argument('--assign', default=os.environ.get('QATOUCH_ASSIGN_TO'),
                        help='User key to assign the run to (default: $QATOUCH_ASSIGN_TO)')
    parser.add_argument('--milestone', default=os.environ.get('QATOUCH_MILESTONE_KEY'),
                        help='Release key for the run (default: $QATOUCH_MILESTONE_KEY)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show the plan and the pytest command; create and run nothing')
    parser.add_argument('--file-bugs', action='store_true',
                        help='After the run, file Jira bugs for failures (also needs '
                             'BUG_CREATION_ENABLED=true)')
    parser.add_argument('--no-validate', action='store_true',
                        help='Skip the post-run read-back check (not recommended)')
    args, pytest_extra = parser.parse_known_args()

    extra = [a for a in pytest_extra if a != '--']

    if not os.environ.get('QATOUCH_API_KEY') or not os.environ.get('QATOUCH_DOMAIN'):
        print('ERROR: QATOUCH_API_KEY and QATOUCH_DOMAIN must be set in .env', file=sys.stderr)
        return 2

    target_args = _pytest_target_args(args.target)

    # 1. Plan: which tests, which cases.
    print(f'Collecting tests for target: {args.target} ...')
    nodeids = _collect_nodeids(target_args, extra)
    mapped, unmapped = _map_nodeids(nodeids, _load_mapping())
    case_keys = sorted(set(mapped.values()))
    print(f'  {len(nodeids)} test(s) collected, {len(mapped)} mapped to '
          f'{len(case_keys)} QA Touch case(s), {len(unmapped)} unmapped')
    if unmapped:
        print('  Unmapped tests will run but nothing is uploaded for them:')
        for n in unmapped[:8]:
            print(f'    - {n}')
        if len(unmapped) > 8:
            print(f'    ... and {len(unmapped) - 8} more')
        print('  Map them: python tools/qatouch_mapper.py build')
    if not case_keys and not args.run_key:
        print('ERROR: none of the collected tests map to a QA Touch case - '
              'a run would be empty. Nothing created.', file=sys.stderr)
        return 2

    # 2. Run record.
    run_name = args.name or _build_run_name(args.target, args.env, args.version)
    if args.run_key:
        run_key = args.run_key
        print(f'  Reusing run: {run_key}')
    elif args.dry_run:
        run_key = '<NEW_KEY>'
        print(f'  [dry-run] would create run "{run_name}" with {len(case_keys)} case(s)')
    else:
        if not args.assign or not args.milestone:
            print('ERROR: a run needs an assignee and a milestone.\n'
                  '  Set QATOUCH_ASSIGN_TO and QATOUCH_MILESTONE_KEY in .env, or pass\n'
                  '  --assign <USER_KEY> --milestone <RELEASE_KEY>.\n'
                  '  Find them: python tools/qatouch_run_manager.py users\n'
                  '             python tools/qatouch_run_manager.py milestone <NAME>',
                  file=sys.stderr)
            return 2
        print(f'  Creating run "{run_name}" with {len(case_keys)} case(s)...')
        run_key = _create_run(run_name, case_keys, args.assign, args.milestone)
        print(f'  Run key: {run_key}')

    # 3. Execute.
    cmd = [sys.executable, '-m', 'pytest', *target_args,
           '--qatouch-upload', '--qatouch-run', run_key, *extra]
    pretty = ' '.join(c if ' ' not in c else f'"{c}"' for c in cmd)
    print()
    print(f'Target:    {args.target}')
    print(f'Env:       {args.env}')
    print(f'Run:       {run_key}  "{run_name}"')
    print(f'Command:   {pretty}')
    print()
    if args.dry_run:
        print('[dry-run - nothing executed]')
        return 0

    env = dict(os.environ)
    env['ENV'] = args.env
    completed = subprocess.run(cmd, cwd=str(ROOT), env=env)
    rc = completed.returncode

    # 4. Prove the results are really in QA Touch.
    if not args.no_validate:
        print()
        from tools.validate_run import validate_run
        vrc = validate_run(run_key, PROJECT_KEY, local_count=None)
        if vrc != 0:
            print('[post-run] Validation FAILED - the run does not match the local results. '
                  'Check logs/upload_failures.json and run tools/retry_uploads.py.')
            rc = rc or 1

    # 5. History and (opt-in) bugs.
    print()
    _update_flaky_history(args.env)
    if args.file_bugs:
        _file_bugs()

    print()
    print(f'Done. Run {run_key}: "{run_name}"')
    return rc


if __name__ == '__main__':
    sys.exit(main())
