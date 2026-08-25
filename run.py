#!/usr/bin/env python3
"""Run the suite from one front door.

    python run.py smoke                       # every test marked smoke
    python run.py module views                # tests/ui/views
    python run.py test tests/ui/views/test_views_basic.py::TestViewsBasic::test_open_my_views
    python run.py rerun latest                # the failed tests of the newest archived run
    python run.py open latest                 # that run's run.html in the browser
    python run.py list                        # the last 10 archived runs
    python run.py health                      # pass rates per product and module, tests to watch
                                              # over the newest 20 runs of each module (or: health 50)

Anything after `--` goes to pytest unchanged:

    python run.py module views -- --headed -s

Each run prints the pytest command it starts and, at the end, the run's
run.html and the archive index (reports/runs/). `--check` runs
tools/pre_run_check.py against the target environment first.
`--retry-streams` reruns once, and only, a test that failed on the
tenant's stream-failure message. One run at a time:
plugins/single_run_guard.py refuses a second one.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from plugins.paths import long_root_warning  # noqa: E402
from plugins.run_archive import RUN_DIR_RE, RUNS_DIR  # noqa: E402
from plugins.run_report import (  # noqa: E402
    FAILURE_OUTCOMES,
    build_run_report,
    collect_tests,
    load_summary,
)

PYTEST = [sys.executable, '-m', 'pytest']
MODULES_DIR = Path('tests') / 'ui'
LIST_MAX = 10
NEEDS_TARGET = ('module', 'test')
# The one rerun the suite allows, and only on request: the tenant's
# live stream fails intermittently with 'The camera failed to load',
# and that message class is the whole match. Never the default, never
# broadened - a wider match hides a broken wait or a tenant that
# needs a fix (house rule: fix first).
STREAM_RERUN_ARGS = ['--reruns', '1', '--only-rerun', 'failed to load']


def _run_dirs() -> list[Path]:
    """Archived run folders, newest first (their names sort by start time)."""
    if not RUNS_DIR.is_dir():
        return []
    return sorted((p for p in RUNS_DIR.iterdir() if p.is_dir() and RUN_DIR_RE.match(p.name)),
                  reverse=True)


def _resolve(arg: str) -> Path:
    """'latest', a folder name from `run.py list`, or a path."""
    if arg == 'latest':
        runs = _run_dirs()
        if not runs:
            sys.exit('No archived runs under reports/runs/. Run the suite once.')
        return runs[0]
    for candidate in (Path(arg), RUNS_DIR / arg):
        if candidate.is_dir():
            return candidate
    sys.exit(f'No run folder at {arg}. Use latest, a folder name from "run.py list", or a path.')


def _failed_nodeids(run_dir: Path) -> list[str]:
    """The failed and errored tests of an archived run, as pytest node ids."""
    tests, _unattached = collect_tests(run_dir)
    failed = sorted(t.nodeid for t in tests.values() if t.outcome in FAILURE_OUTCOMES)
    runnable = []
    for nodeid in failed:
        # A test known only from a file name has a sanitized name, not a
        # node id, and pytest cannot select it.
        if '::' in nodeid:
            runnable.append(nodeid)
        else:
            print(f'Cannot rerun {nodeid}: only a file name records it. Pass its node id to run.py test.')
    return runnable


def _pytest_target(args: argparse.Namespace) -> list[str]:
    if args.verb == 'smoke':
        return ['-m', 'smoke']
    if args.verb == 'module':
        folder = MODULES_DIR / args.target
        if not folder.is_dir():
            names = ', '.join(sorted(p.name for p in MODULES_DIR.iterdir() if p.is_dir()))
            sys.exit(f'No module folder at {folder}. Modules: {names}')
        return [folder.as_posix()]
    if args.verb == 'test':
        return [args.target]
    run_dir = _resolve(args.target or 'latest')
    failed = _failed_nodeids(run_dir)
    if not failed:
        sys.exit(f'{run_dir.name} has no failed test to rerun.')
    print(f'Rerunning {len(failed)} failed test(s) from {run_dir.name}')
    return failed


def _pretty(cmd: list[str]) -> str:
    return ' '.join(f'"{c}"' if ' ' in c or '[' in c else c for c in cmd)


def _check() -> None:
    """The reachability gate. QA Touch and QA Ops Hub stay out: both are
    optional integrations a test run does not need."""
    env = (os.environ.get('ENV') or 'qa').strip().lower()
    cmd = [sys.executable, str(ROOT / 'tools' / 'pre_run_check.py'), '--env', env,
           '--skip-qatouch', '--skip-qa-ops']
    if subprocess.run(cmd, cwd=ROOT).returncode != 0:
        sys.exit('The pre-run check failed. Fix what it reports, then run again.')


def build_command(target: list[str], extra: list[str],
                  retry_streams: bool = False) -> list[str]:
    """The pytest command a run starts. Pure, so a test can check it."""
    cmd = [*PYTEST, *target, *extra]
    if retry_streams:
        cmd += STREAM_RERUN_ARGS
    return cmd


def _run(target: list[str], extra: list[str], check: bool,
         retry_streams: bool = False) -> int:
    if check:
        _check()
    cmd = build_command(target, extra, retry_streams)
    if retry_streams:
        print('Retry policy: a test that failed on "failed to load" (the tenant '
              'stream failure) reruns once. No other failure reruns.')
    # flush: when stdout is a pipe, pytest's output would otherwise land first
    print(f'Command: {_pretty(cmd)}\n', flush=True)
    before = _run_dirs()[:1]
    rc = subprocess.run(cmd, cwd=ROOT).returncode
    newest = _run_dirs()[:1]
    print()
    if newest and newest != before:
        print(f'Run report:    {(newest[0] / "run.html").resolve()}')
    else:
        print('Run report:    none (no test ran, the guard refused the run, or RUN_ARCHIVE=off)')
    print(f'Archive index: {(RUNS_DIR / "index.html").resolve()}')
    return rc


def _open(arg: str) -> int:
    run_dir = _resolve(arg)
    page = run_dir / 'run.html'
    if not page.is_file():
        # Runs archived before run.html existed still have their evidence.
        page.write_text(build_run_report(run_dir), encoding='utf-8')
    print(f'Opening {page.resolve()}')
    webbrowser.open(page.resolve().as_uri())
    return 0


def _list() -> int:
    runs = _run_dirs()[:LIST_MAX]
    if not runs:
        print('No archived runs under reports/runs/. Run the suite once.')
        return 0
    for run_dir in runs:
        s = load_summary(run_dir)
        counts = s.get('counts') or {}
        target = ' '.join(s.get('target') or []) or 'all'
        if s.get('markexpr'):
            target += f' -m "{s["markexpr"]}"'
        tally = '  '.join(f'{k} {counts.get(k, "-")}' for k in ('passed', 'failed', 'skipped', 'errors'))
        print(run_dir.name)
        print(f'    {s.get("started", "-")}  {tally}  exit {s.get("exitstatus", "-")}  {target}')
    print(f'\nArchive index: {(RUNS_DIR / "index.html").resolve()}')
    return 0


def _health(last: str | None) -> int:
    """Aggregate the archived runs into reports/runs/health.html."""
    from tools.health_summary import main as health_main
    if last is not None and not last.isdigit():
        sys.exit(f'health takes a number of runs per module, not {last!r}.')
    return health_main(['--last', last] if last else [])


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    extra: list[str] = []
    if '--' in argv:
        cut = argv.index('--')
        argv, extra = argv[:cut], argv[cut + 1:]
    parser = argparse.ArgumentParser(
        prog='run.py', formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__.split('\n\n', 1)[1])
    parser.add_argument('verb', choices=['smoke', 'module', 'test', 'rerun', 'open', 'list', 'health'])
    parser.add_argument('target', nargs='?',
                        help='module name, test node id or path, a run folder (default latest), '
                             'or for health the runs per module (default 20)')
    parser.add_argument('--check', action='store_true',
                        help='run tools/pre_run_check.py against the target environment first')
    parser.add_argument('--retry-streams', action='store_true',
                        help='rerun once a test that failed on the tenant stream-failure '
                             'message ("failed to load"); no other failure reruns')
    args = parser.parse_args(argv)
    if args.verb in NEEDS_TARGET and not args.target:
        parser.error(f'{args.verb} needs a target')

    os.chdir(ROOT)  # the plugins address reports/ and tests/ from the repo root
    # A deep checkout makes the evidence names shorten on every run, and
    # past the cap Windows refuses the write. Said once, before any output.
    warning = long_root_warning(ROOT)
    if warning:
        print(warning)
    if args.verb == 'list':
        return _list()
    if args.verb == 'health':
        return _health(args.target)
    if args.verb == 'open':
        return _open(args.target or 'latest')
    return _run(_pytest_target(args), extra, args.check, args.retry_streams)


if __name__ == '__main__':
    sys.exit(main())
