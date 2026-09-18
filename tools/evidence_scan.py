#!/usr/bin/env python3
"""Find, and with --redact remove, secrets in a run's evidence before it is published.

A run folder is read by the whole team, and the nightly's folders are served
over the network. On 09/14/2026 a pytest traceback printed the login fixture's
dict, and the account password sat in a per-test log on the served archive for
4 days. `config/secret.py` closed that one path. This tool is the net for the
next one. It reads every text file of a run folder for 2 things:

1. a value from .env whose key looks like a credential (the same rule as
   tools/secret_check.py), and
2. text with the shape of a secret: a session cookie, a bearer token, an
   integration key, or a password key with a quoted value.

It never prints a value. A finding names the .env key or the pattern, and the
file and line. Trace zips are not read: they hold cookies by design and are
never published (tools/publish_run.py, deploy/spartan1/nightly.sh).

Usage:
  python tools/evidence_scan.py reports/runs/<run>            # report, exit 1 on a finding
  python tools/evidence_scan.py reports/runs/<run> --redact   # replace each secret with ***
  python tools/evidence_scan.py --runs-dir reports/runs --redact   # every run folder

Exit codes: 0 clean (or every finding redacted), 1 a secret found, 2 tool error.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.secret_check import PLACEHOLDER_RE, secret_values

ENV_FILE = ROOT / '.env'
TEXT_SUFFIXES = {'.txt', '.log', '.json', '.jsonl', '.html', '.htm', '.xml', '.md', '.csv', '.yaml', '.yml'}
MASK = '***'
DONE_MARKER = '.evidence_scanned'   # a dotfile: nginx denies it, rsync copies it, nobody reads it

# name, pattern, the group that holds the secret. Each pattern keeps its
# prefix, so a redacted line still says what was there.
PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    ('session cookie', re.compile(r'(JSESSIONID["\']?\s*[=:]\s*["\']?)([A-Za-z0-9._-]{16,})'), 2),
    ('bearer token', re.compile(r'((?:Authorization["\']?\s*[:=]\s*["\']?)?Bearer\s+)([A-Za-z0-9._~+/-]{20,}=*)', re.I), 2),
    ('integration key', re.compile(r'(x-vsaas-key["\']?\s*[:=]\s*["\']?)([A-Za-z0-9._-]{12,})', re.I), 2),
    ('password value', re.compile(r'(["\']?\bpass(?:word|wd)?["\']?\s*[:=]\s*)(["\'])([^"\'\n]{4,})\2', re.I), 3),
]


def _is_real(value: str) -> bool:
    """False for a mask, a placeholder or a template variable."""
    v = value.strip()
    return bool(v) and set(v) != {'*'} and not PLACEHOLDER_RE.match(v) and '{' not in v and '<' not in v


def scan_text(text: str, secrets: dict[str, str]) -> tuple[str, list[dict]]:
    """(text with each secret replaced by ***, findings). A finding holds the line and what matched, never the value."""
    findings: list[dict] = []
    out_lines = []
    for idx, line in enumerate(text.split('\n'), 1):
        for key, value in secrets.items():
            if value in line:
                findings.append({'line': idx, 'what': f'.env value of {key}'})
                line = line.replace(value, MASK)
        for name, pattern, group in PATTERNS:
            def mask(m: re.Match[str], name: str = name, group: int = group, idx: int = idx) -> str:
                if not _is_real(m.group(group)):
                    return m.group(0)
                findings.append({'line': idx, 'what': name})
                start, end = m.span(group)
                return m.group(0)[: start - m.start()] + MASK + m.group(0)[end - m.start():]
            line = pattern.sub(mask, line)
        out_lines.append(line)
    return '\n'.join(out_lines), findings


def scan_run(run_dir: Path, secrets: dict[str, str], redact: bool) -> list[dict]:
    """Findings for one run folder. With redact, each file that holds a secret is written again without it."""
    findings: list[dict] = []
    for path in sorted(run_dir.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding='utf-8', errors='surrogateescape')
        except OSError as e:
            print(f'evidence_scan: could not read {path}: {e}', file=sys.stderr)
            continue
        clean, found = scan_text(text, secrets)
        if not found:
            continue
        for f in found:
            f['path'] = path.relative_to(run_dir.parent).as_posix()
        findings.extend(found)
        if redact:
            path.write_text(clean, encoding='utf-8', errors='surrogateescape')
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('run_dir', nargs='?', type=Path, help='one run folder')
    parser.add_argument('--runs-dir', type=Path, help='scan every run folder below this directory')
    parser.add_argument('--redact', action='store_true', help='replace each secret with *** in the file')
    parser.add_argument('--env', type=Path, default=ENV_FILE, help='env file with the secret values (default: .env)')
    parser.add_argument('--rescan', action='store_true', help='with --runs-dir: also scan folders that were scanned before')
    args = parser.parse_args(argv)
    if bool(args.run_dir) == bool(args.runs_dir):
        print('evidence_scan: give one run folder, or --runs-dir', file=sys.stderr)
        return 2

    secrets = secret_values(args.env.read_text(encoding='utf-8')) if args.env.is_file() else {}
    if not secrets:
        print(f'evidence_scan: no secret values read from {args.env}; the scan uses the patterns only', file=sys.stderr)

    if args.run_dir:
        run_dirs = [args.run_dir]
    else:
        run_dirs = sorted(d for d in args.runs_dir.iterdir() if d.is_dir() and d.name[:2] == '20')
    missing = [d for d in run_dirs if not d.is_dir()]
    if missing:
        print(f'evidence_scan: not a folder: {missing[0]}', file=sys.stderr)
        return 2

    all_findings: list[dict] = []
    scanned = 0
    for run_dir in run_dirs:
        marker = run_dir / DONE_MARKER
        if args.runs_dir and marker.exists() and not args.rescan:
            continue
        found = scan_run(run_dir, secrets, args.redact)
        scanned += 1
        all_findings.extend(found)
        # Only a --redact pass marks a folder: after it the folder is clean at
        # rest, and the next pass can skip it. A report pass writes nothing.
        if args.runs_dir and args.redact:
            marker.write_text('scanned by tools/evidence_scan.py\n', encoding='utf-8')

    for f in all_findings:
        print(f"  {f['path']}:{f['line']}  {f['what']}")
    verb = 'redacted' if args.redact else 'found'
    print(f'evidence_scan: {scanned} run folder(s) read, {len(all_findings)} secret(s) {verb}.')
    if all_findings and not args.redact:
        print('evidence_scan: run again with --redact before you publish this evidence.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
