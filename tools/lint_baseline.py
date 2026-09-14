#!/usr/bin/env python3
"""Fail when a file gains lint findings. Ignore the ones it already had.

The repo reached zero ruff findings on 09/14/2026 and the recorded
baseline is zero, so today any finding fails. The tool stays as the gate
because a per-file baseline is what got it there: a repo that held
several hundred findings could not have started at zero, and "no more than
before, per file" was a bar every change could pass while the count came
down. If the count ever has to go up, say why in the commit message and
run --update; the standard is zero, not "no more than before".

The count is per file, not a repo total. A repo total lets a change fix five
findings in one file and add five in another and call it even, which is how
a number stays flat while the code gets worse in the place you were editing.

This is not hygiene. Ruff had been reporting the Jira create bug for months:

    tools/smart_jira_bug_creator.py:152:5: RET503 Missing explicit `return`
    at the end of function able to return non-None value

Nobody saw it, because that one file held 50 findings and the repo held
hundreds. The signal existed and drowned. Capping each file is what makes
the next one audible.

Usage:
  python tools/lint_baseline.py            # check against the baseline
  python tools/lint_baseline.py --update   # record the current counts

The baseline lives in config/lint_baseline.json and is committed. Lowering
it is always safe; raising it needs a reason in the commit message.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BASELINE = ROOT / 'config' / 'lint_baseline.json'
# The whole tree, the same scope as `ruff check .`: the excludes live in
# pyproject.toml. A list of directories here once missed conftest.py and
# then a root script; the gate lints what ruff lints.
TARGETS = ['.']


def current_counts() -> tuple[Counter, str | None]:
    """{path: finding count} from ruff, and any error that stopped it."""
    try:
        proc = subprocess.run(
            [sys.executable, '-m', 'ruff', 'check', '--output-format', 'json',
             *TARGETS],
            cwd=str(ROOT), capture_output=True, text=True, timeout=300,
            check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return Counter(), f'could not run ruff: {exc}'
    # ruff exits 0 with no findings and 1 with findings, both with JSON on
    # stdout. Anything else is ruff failing (a broken pyproject, a missing
    # install), and at a zero baseline that used to read as a clean tree.
    if proc.returncode not in (0, 1):
        return Counter(), f'ruff exited {proc.returncode}: {proc.stderr.strip()[:200]}'
    try:
        findings = json.loads(proc.stdout or '[]')
    except (json.JSONDecodeError, ValueError):
        return Counter(), f'ruff produced no usable JSON: {proc.stderr[:200]}'

    counts: Counter = Counter()
    for f in findings:
        name = f.get('filename') or ''
        try:
            rel = Path(name).resolve().relative_to(ROOT).as_posix()
        except ValueError:
            rel = Path(name).as_posix()
        counts[rel] += 1
    return counts, None


def load_baseline() -> dict[str, int] | None:
    """The recorded per-file counts; None when nothing is recorded.

    An empty dict is a real baseline: zero findings everywhere, which the
    repo reached on 09/14/2026. Reading it as "no baseline" blocked the
    commit that got it there.
    """
    if not BASELINE.exists():
        return None
    try:
        data = json.loads(BASELINE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get('files'), dict):
        return None
    return data['files']


def save_baseline(counts: Counter) -> None:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE.write_text(json.dumps(
        {
            'comment': 'Per-file ruff finding counts. Lower is always fine; '
                       'higher needs a reason. See tools/lint_baseline.py.',
            'total': sum(counts.values()),
            'files': dict(sorted(counts.items())),
        },
        indent=2) + '\n', encoding='utf-8')


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--update', action='store_true',
                        help='record the current counts as the new baseline')
    args = parser.parse_args(argv)

    counts, error = current_counts()
    if error:
        print(f'lint baseline: {error}')
        return 2

    if args.update:
        save_baseline(counts)
        print(f'Recorded {sum(counts.values())} finding(s) across '
              f'{len(counts)} file(s) in {BASELINE.name}.')
        return 0

    baseline = load_baseline()
    if baseline is None:
        print('No baseline recorded. Run: python tools/lint_baseline.py --update')
        return 2

    worse = {path: (baseline.get(path, 0), n)
             for path, n in counts.items() if n > baseline.get(path, 0)}
    better = {path: (baseline[path], counts.get(path, 0))
              for path in baseline if counts.get(path, 0) < baseline[path]}

    for path, (was, now) in sorted(worse.items()):
        print(f'  {path}: {was} -> {now} findings')
    if worse:
        print(f'\n{len(worse)} file(s) gained lint findings. Fix them, or say '
              f'why in the commit message and run --update.')
        print('Rules: pyproject.toml, [tool.ruff]. A finding here is one that '
              'would have been visible in a file with a clean baseline.')
        return 1

    if better:
        total_fixed = sum(was - now for was, now in better.values())
        print(f'{total_fixed} finding(s) fixed across {len(better)} file(s). '
              f'Run --update to lock it in.')
    print(f'No file gained findings. Total: {sum(counts.values())}.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
