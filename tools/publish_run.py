#!/usr/bin/env python3
"""Publish a local run's evidence to the team archive on spartan1.

A manual run stays on your machine unless you decide it is worth sharing.
This is that decision, as one command:

  python tools/publish_run.py             # newest run under reports/runs
  python tools/publish_run.py 2026-09-01_10-39-03__tests-ui-licenses  # named
  python tools/publish_run.py --dry-run   # show what would be copied

What it copies: the run's folder, MINUS the trace zips. A Playwright trace
carries a live session cookie and, on a fresh-login test, the account
password, so it never leaves the machine that made it - keep it local for
`playwright show-trace`. The failure videos beside the traces are copied:
run.html links them. The local index.html/health.html are not sent
either: each machine sees only its own runs, so they are partial. nginx
autoindex lists the runs on the host. Nothing is deleted on the host; the
30-day prune there is the only thing that removes runs. The full workflow:
docs/RUN_WORKFLOWS.md.

The destination defaults to the publish account, qa-publish@10.2.0.2, and
its folder /runs. It can be overridden with QA_RUNS_HOST / QA_RUNS_DIR. Copying uses sftp, which every
QA machine already has (Windows ships OpenSSH), authenticated by whatever
key reaches the host. sftp and nothing else, on purpose: the publish account
on the box (qa-publish, deploy/spartan1/README.md) has no shell, so a laptop
key that can publish cannot read the box's .env or touch the nightly. If the
copy fails on the key, ask for your key to be added to the box.

Exit codes: 0 published, 1 the copy failed, 2 nothing valid to publish.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / 'reports' / 'runs'
RUN_DIR_RE = re.compile(r'^20\d{2}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}__')

DEFAULT_HOST = 'qa-publish@10.2.0.2'
DEFAULT_DIR = '/data/qa/runs'
PUBLISH_USER_DIR = '/runs'   # what the jailed qa-publish account sees (deploy/spartan1/setup-publish-user.sh)
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
# POST body with the account password. The trace stays local for
# `playwright show-trace`. The failure VIDEO beside it does travel: it shows
# the screen (a password field shows dots), and run.html links it. Until
# 09/11/2026 the whole traces/ folder was held back and every video link on
# the shared host was dead.
EXCLUDE_DIRS: set[str] = set()
EXCLUDE_SUFFIXES = {'.zip'}


def _staged_copy(run_dir: Path) -> Path:
    """A copy of the run folder with the trace zips removed, in a temp
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
    try:
        _redact_staged(staged)
    except BaseException:
        # an unmasked copy must not stay in the temp folder
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return staged


def _redact_staged(staged: Path) -> None:
    """Mask secrets in the copy that travels. The local original stays as it
    is, for the person who is debugging with it. A password reached the served
    archive through a per-test log on 09/14/2026 (tools/evidence_scan.py)."""
    if str(ROOT) not in sys.path:   # run as a script, sys.path[0] is tools/, not the repo
        sys.path.insert(0, str(ROOT))
    from tools import evidence_scan
    from tools.secret_check import secret_values

    env = evidence_scan.ENV_FILE
    secrets = secret_values(env.read_text(encoding='utf-8')) if env.is_file() else {}
    if not secrets:
        # The nightly publishes nothing in this case. A person who publishes 1 run by hand is
        # told, and decides: the patterns still mask a cookie, a token and a password in a URL.
        print(f'WARNING: no secret values read from {env}. The copy is checked for the shapes of a '
              'secret only, not for the values of this machine.', file=sys.stderr)
    found, errors = evidence_scan.scan_run(staged, secrets, redact=True)
    if errors:
        # The copy could not be made clean, so it must not travel.
        raise RuntimeError('evidence_scan could not clean the copy to publish: ' + '; '.join(errors))
    if found:
        print(f'  evidence_scan: masked {len(found)} secret(s) in the published copy:')
        for f in found:
            print(f"    {f['path']}:{f['line']}  {f['what']}")


def _q(path: str) -> str:
    """A path for an sftp batch line: double-quoted, forward slashes."""
    if any(c in path for c in '"\n*?['):
        # sftp expands * ? [ in a local path, in quotes too
        raise ValueError(f'a path with a quote, a newline or one of * ? [ cannot be published: {path!r}')
    return '"' + path.replace('\\', '/') + '"'


def sftp_batch(staged: Path, dest: str, stamp: str) -> str:
    """The batch that publishes one staged run folder.

    Atomic on the host: the folder goes to a hidden `.pub-tmp-<name>-<stamp>`
    first and one `rename` moves it into place. A copy that drops mid-way (a
    lost tunnel) leaves only the hidden temp, never a partial run folder that
    the archive lists. A run that is published again moves the old copy to
    `.pub-old-...` first, because sftp cannot delete a folder tree. nginx
    never serves a dot name, and the box's prune removes both kinds after 2
    days. A leading `-` lets a line fail: the old copy is usually not there.
    """
    name = staged.name
    tmp = f'{dest}/.pub-tmp-{name}-{stamp}'
    final = f'{dest}/{name}'
    # `put -r` carries the LOCAL directory modes, and a Windows publisher's map
    # to 0700, so nginx could not traverse into the published folder and the
    # archive served nothing (first sftp publish from spartan20, 09/23/2026).
    # The files were fine: the account's umask reached those, not these. So the
    # directories are set here rather than hoped for, shallowest first so a
    # parent is never left locking its children out.
    dirs = sorted(d.relative_to(staged).as_posix() for d in staged.rglob('*') if d.is_dir())
    chmods = [f'chmod 775 {_q(final)}'] + [f'chmod 775 {_q(final + "/" + d)}' for d in dirs]
    return '\n'.join([
        f'mkdir {_q(tmp)}',
        f'put -r {_q(str(staged))} {_q(tmp + "/")}',
        f'-rename {_q(final)} {_q(f"{dest}/.pub-old-{name}-{stamp}")}',
        f'rename {_q(tmp + "/" + name)} {_q(final)}',
        *chmods,
        f'rmdir {_q(tmp)}',
    ]) + '\n'


def publish(run_dir: Path, host: str, dest: str,
            dry_run: bool = False, runner=None) -> int:
    """Copy a run folder to the host, minus the sensitive evidence.

    Only the run folder is sent, never the local index.html/health.html: each
    machine sees only its own runs, so a local index is always partial and
    would overwrite the host's fuller view. nginx autoindex lists the runs,
    and the host rebuilds the real index. `runner` is resolved at CALL time,
    not bound as a default, so a test's monkeypatch of subprocess.run
    actually intercepts.

    sftp runs with BatchMode (never drops to an interactive password prompt on
    a revoked key) and a connect timeout (an unreachable-but-not-refusing
    host fails fast instead of hanging the publish).
    """
    opts = ['-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10']
    if dry_run:
        print(f'  would stage {run_dir.name} without the trace zips, mask any secret in '
              f'the copy, and sftp it to {host}:{dest}/{run_dir.name}')
        return 0
    import shutil
    run = runner or subprocess.run
    staged = _staged_copy(run_dir)
    try:
        batch = sftp_batch(staged, dest, stamp=str(int(time.time())))
        done = run(['sftp', '-q', '-b', '-', *opts, host], input=batch, text=True,
                   capture_output=True, check=False)
        # sftp echoes each line, and the old-copy rename fails on a first
        # publish by design: its output is shown only when the copy failed.
        if done.returncode != 0:
            print((getattr(done, 'stderr', '') or '').strip())
        return 0 if done.returncode == 0 else 1
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

    # QA_RUNS_HOST lives in .env with the other per-person settings. A value
    # already in the environment wins (load_dotenv does not override).
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
    host = (os.environ.get('QA_RUNS_HOST') or '').strip() or DEFAULT_HOST   # a blank line in .env is not a host
    # The publish account lives in a jail where the served directory is /runs.
    dest = os.environ.get('QA_RUNS_DIR') or (PUBLISH_USER_DIR if host.startswith('qa-publish@') else DEFAULT_DIR)
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

    print(f'  publishing {run_dir.name} (trace zips stay local, videos travel) '
          f'to {host}:{dest}')
    code = publish(run_dir, host, dest, dry_run=args.dry_run)
    if code == 0 and not args.dry_run:
        print(f'  done: {url}/{run_dir.name}/run.html')
    elif code != 0:
        print('  the copy failed. Is the host reachable and your key installed? '
              'See docs/RUN_WORKFLOWS.md.')
    return code


if __name__ == '__main__':
    sys.exit(main())
