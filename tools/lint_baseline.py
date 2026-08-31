#!/usr/bin/env python3
"""Fail when a file gains lint findings. Ignore the ones it already had.

This repo carries 627 ruff findings. A gate that demands zero would fail
every pull request from day one and be switched off within a week, so it
would protect nothing. A gate that demands "no more than before" is one a
change can actually pass, and it stops the count growing.

The count is per file, not a repo total. A repo total lets a change fix five
findings in one file and add five in another and call it even, which is how
a number stays flat while the code gets worse in the place you were editing.

This is not hygiene. Ruff had been reporting the Jira create bug for months:

    tools/smart_jira_bug_creator.py:152:5: RET503 Missing explicit `return`
    at the end of function able to return non-None value

Nobody saw it, because that one file held 50 findings and the repo held 627.
The signal existed and drowned. Capping each file is what makes the next one
audible.

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
TARGETS = ['plugins', 'tools', 'tests', 'config', 'run.py']


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


def load_baseline() -> dict[str, int]:
    if not BASELINE.exists():
        return {}
    try:
        data = json.loads(BASELINE.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError, ValueError):
        return {}
    return data.get('files', {}) if isinstance(data, dict) else {}


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
    if not baseline:
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
        print('Rules: ruff.toml. A finding here is one that would have been '
              'visible in a file with a clean baseline.')
        return 1

    if better:
        total_fixed = sum(was - now for was, now in better.values())
        print(f'{total_fixed} finding(s) fixed across {len(better)} file(s). '
              f'Run --update to lock it in.')
    print(f'No file gained findings. Total: {sum(counts.values())}.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
