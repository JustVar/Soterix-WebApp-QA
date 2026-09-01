#!/usr/bin/env python3
"""Publish a local run's evidence to the team archive on spartan1.

A manual run stays on your machine unless you decide it is worth sharing.
This is that decision, as one command:

  python tools/publish_run.py             # newest run under reports/runs
  python tools/publish_run.py 2026-09-01_10-39-03__tests-ui-licenses  # named
  python tools/publish_run.py --dry-run   # show what would be copied

What it copies: the run's folder, plus the archive's index.html and
health.html when they exist, so the front door on the host stays current.
Nothing is deleted on the host; the 30-day prune there is the only thing
that removes runs. The full workflow: docs/RUN_WORKFLOWS.md.

The destination defaults to soterix@10.2.0.2:/data/qa/runs and can be
overridden with QA_RUNS_HOST / QA_RUNS_DIR. Copying uses scp, which every
QA machine already has (Windows ships OpenSSH), authenticated by whatever
key reaches the host. If scp asks for a password, ask for your key to be
added to the box rather than typing one every time.

Exit codes: 0 published, 1 scp failed, 2 nothing valid to publish.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'reports' / 'runs'
RUN_DIR_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}__')

DEFAULT_HOST = 'soterix@10.2.0.2'
DEFAULT_DIR = '/data/qa/runs'
DEFAULT_URL = 'http://10.2.0.2/qa-runs'


def newest_run(runs_dir: Path | None = None) -> Path | None:
    """The most recent archived run folder, or None.

    The default is resolved at CALL time (rule 6 of the shared package's
    RULES.md: read module globals at call time). Bound in the signature,
    a test's monkeypatch of RUNS is invisible and the test reads the real
    archive - which is exactly how the first version failed.
    """
    runs_dir = RUNS if runs_dir is None else runs_dir
    candidates = [p for p in runs_dir.iterdir()
                  if p.is_dir() and RUN_DIR_RE.match(p.name)] if runs_dir.is_dir() else []
    return max(candidates, key=lambda p: p.name) if candidates else None


def sources(run_dir: Path, runs_dir: Path | None = None) -> list[Path]:
    """The run folder plus the front-door pages that exist."""
    runs_dir = RUNS if runs_dir is None else runs_dir
    out = [run_dir]
    for name in ('index.html', 'health.html'):
        page = runs_dir / name
        if page.exists():
            out.append(page)
    return out


def publish(paths: list[Path], host: str, dest: str,
            dry_run: bool = False, runner=None) -> int:
    """scp each source to the host. Returns the exit code.

    `runner` is resolved at CALL time, not bound as a default, so a test's
    monkeypatch of subprocess.run actually intercepts. The first version
    bound it in the signature, and two "offline" tests fired real scp.
    """
    cmd = ['scp', '-q', '-r', *[str(p) for p in paths], f'{host}:{dest}/']
    if dry_run:
        print('  would run: ' + ' '.join(cmd))
        return 0
    proc = (runner or subprocess.run)(cmd, check=False)
    return 0 if proc.returncode == 0 else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('run', nargs='?', default=None,
                        help='run folder name under reports/runs '
                             '(default: the newest)')
    parser.add_argument('--dry-run', action='store_true',
                        help='print the copy command without running it')
    args = parser.parse_args(argv)

    host = os.environ.get('QA_RUNS_HOST', DEFAULT_HOST)
    dest = os.environ.get('QA_RUNS_DIR', DEFAULT_DIR)
    url = os.environ.get('QA_RUNS_URL', DEFAULT_URL)

    if args.run:
        run_dir = RUNS / args.run
        if not run_dir.is_dir():
            print(f'No such run folder: {run_dir}')
            print(f'Available: {", ".join(sorted(p.name for p in RUNS.iterdir() if p.is_dir())[-5:]) if RUNS.is_dir() else "(no archive yet)"}')
            return 2
        if not RUN_DIR_RE.match(run_dir.name):
            print(f'{run_dir.name} is not a run folder (expected '
                  f'<timestamp>__<target>). Refusing to publish it.')
            return 2
    else:
        found = newest_run()
        if found is None:
            print('No archived runs under reports/runs. Run some tests first.')
            return 2
        run_dir = found

    paths = sources(run_dir)
    print(f'  publishing {run_dir.name} (+{len(paths) - 1} front-door page(s)) '
          f'to {host}:{dest}')
    code = publish(paths, host, dest, dry_run=args.dry_run)
    if code == 0 and not args.dry_run:
        print(f'  done: {url}/{run_dir.name}/run.html')
    elif code != 0:
        print('  scp failed. Is the host reachable and your key installed? '
              'See docs/RUN_WORKFLOWS.md.')
    return code


if __name__ == '__main__':
    sys.exit(main())
