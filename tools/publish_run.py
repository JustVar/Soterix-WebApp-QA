#!/usr/bin/env python3
"""Publish a local run's evidence to the team archive on spartan1.

A manual run stays on your machine unless you decide it is worth sharing.
This is that decision, as one command:

  python tools/publish_run.py             # newest run under reports/runs
  python tools/publish_run.py 2026-09-01_10-39-03__tests-ui-licenses  # named
  python tools/publish_run.py --dry-run   # show what would be copied

What it copies: the run's folder, MINUS traces/ and videos. A Playwright
trace carries a live session cookie and, on a fresh-login test, the account
password, so it never leaves the machine that made it - keep it local for
`playwright show-trace`. The local index.html/health.html are not sent
either: each machine sees only its own runs, so they are partial. nginx
autoindex lists the runs on the host. Nothing is deleted on the host; the
30-day prune there is the only thing that removes runs. The full workflow:
docs/RUN_WORKFLOWS.md.

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


# Never leaves the machine that produced it. A Playwright trace records the
# full network log, so an authenticated request carries a live
# `Cookie: JSESSIONID=...` and a fresh-login test's trace carries the login
# POST body with the account password. Videos show the authenticated
# session. The shared host is for triage-by-glance (run.html, screenshots,
# logs); the trace stays local for `playwright show-trace`.
EXCLUDE_DIRS = {'traces'}
EXCLUDE_SUFFIXES = {'.webm'}


def _staged_copy(run_dir: Path) -> Path:
    """A copy of the run folder with traces and videos removed, in a temp
    dir. The caller scps this instead of the original."""
    import shutil
    import tempfile

    def ignore(_directory, names):
        drop = {n for n in names if n in EXCLUDE_DIRS}
        drop |= {n for n in names if Path(n).suffix in EXCLUDE_SUFFIXES}
        return drop

    tmp = Path(tempfile.mkdtemp(prefix='qa-publish-'))
    staged = tmp / run_dir.name
    shutil.copytree(run_dir, staged, ignore=ignore)
    return staged


def publish(run_dir: Path, host: str, dest: str,
            dry_run: bool = False, runner=None) -> int:
    """Copy a run folder to the host, minus the sensitive evidence.

    Only the run folder is sent, never the local index.html/health.html: each
    machine sees only its own runs, so a local index is always partial and
    would overwrite the host's fuller view. nginx autoindex lists the runs,
    and the host rebuilds the real index. `runner` is resolved at CALL time,
    not bound as a default, so a test's monkeypatch of subprocess.run
    actually intercepts.

    Atomic on the host: the folder is scp'd to a hidden `.pub-tmp-<name>`
    first, then moved into place with a single `mv`, which is atomic on one
    filesystem. An scp interrupted mid-transfer (a dropped WireGuard tunnel)
    therefore leaves only a hidden temp - never a partial run folder that
    the archive lists and a reviewer opens as if it were complete. The temp
    name starts with a dot, so nginx's dotfile-deny never serves it either.

    scp runs with BatchMode (never drops to an interactive password prompt on
    a revoked key) and a connect timeout (an unreachable-but-not-refusing
    host fails fast instead of hanging the publish).
    """
    opts = ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10']
    tmp = f'{dest}/.pub-tmp-{run_dir.name}'
    final = f'{dest}/{run_dir.name}'
    if dry_run:
        print(f'  would stage {run_dir.name} without traces/ or *.webm, scp it '
              f'to {host}:{tmp}, then mv it to {final}')
        return 0
    import shutil
    run = runner or subprocess.run
    staged = _staged_copy(run_dir)
    try:
        # Clear any leftover temp from a prior interrupted publish, copy, then
        # atomically swing it into place (removing an old copy first, since mv
        # onto a non-empty dir is not a replace).
        run(['ssh', *opts, host, f'rm -rf {tmp}'], check=False)
        scp = run(['scp', '-q', '-r', *opts, str(staged), f'{host}:{tmp}'], check=False)
        if scp.returncode != 0:
            run(['ssh', *opts, host, f'rm -rf {tmp}'], check=False)
            return 1
        mv = run(['ssh', *opts, host, f'rm -rf {final} && mv {tmp} {final}'], check=False)
        return 0 if mv.returncode == 0 else 1
    finally:
        shutil.rmtree(staged.parent, ignore_errors=True)


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

    print(f'  publishing {run_dir.name} (traces and videos stay local) '
          f'to {host}:{dest}')
    code = publish(run_dir, host, dest, dry_run=args.dry_run)
    if code == 0 and not args.dry_run:
        print(f'  done: {url}/{run_dir.name}/run.html')
    elif code != 0:
        print('  scp failed. Is the host reachable and your key installed? '
              'See docs/RUN_WORKFLOWS.md.')
    return code


if __name__ == '__main__':
    sys.exit(main())
