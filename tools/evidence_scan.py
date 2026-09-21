#!/usr/bin/env python3
"""Find, and with --redact remove, secrets in a run's evidence before it is published.

A run folder is read by the whole team, and the nightly's folders are served
over the network. On 09/14/2026 a pytest traceback printed the login fixture's
dict, and the account password sat in a per-test log on the served archive for
4 days. `config/secret.py` closed that one path. This tool is the net for the
next one. It reads every text file of a run folder for 2 things:

1. a value from .env whose key looks like a credential (the same rule as
   tools/secret_check.py), as it is and in the forms a report gives it:
   HTML-escaped, URL-encoded and JSON-escaped, and
2. text with the shape of a secret: a session cookie, a bearer or basic
   token, an integration key, a password in a URL, or a password key with a
   value. The quotes can be plain, HTML entities or JSON-escaped, because
   run.html and report.html hold tracebacks in those forms.

It never prints a value. A finding names the .env key or the pattern, and the
file and line. Trace zips are not read: they hold cookies by design and are
never published (tools/publish_run.py, deploy/spartan1/nightly.sh).

Usage:
  python tools/evidence_scan.py reports/runs/<run>            # report, exit 1 on a finding
  python tools/evidence_scan.py reports/runs/<run> --redact   # replace each secret with ***
  python tools/evidence_scan.py --runs-dir reports/runs --redact   # every run folder

With --runs-dir --redact, a folder that is clean at rest gets the marker file
`.evidence_scanned`, and the next pass skips it. A folder with a file that
could not be read or written gets no marker. The nightly publishes only
folders that have the marker.

Exit codes: 0 clean (or every finding redacted), 1 a secret found and not
redacted, 2 tool error (a bad argument, or a file that could not be read or
written).
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.secret_check import PLACEHOLDER_RE, secret_values

ENV_FILE = ROOT / '.env'
TEXT_SUFFIXES = {'.txt', '.log', '.json', '.jsonl', '.html', '.htm', '.xml', '.md', '.csv', '.yaml', '.yml'}
MASK = '***'
DONE_MARKER = '.evidence_scanned'   # a dotfile: nginx denies it, rsync copies it, nobody reads it

# A quote as a log, a JSON string or an HTML page writes it.
_Q = r'''(?:\\?["']|&quot;|&#34;|&#x27;|&#39;)'''
# name, pattern. The secret is the group named `s`. Each pattern keeps its
# prefix, so a redacted line still says what was there.
PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ('session cookie', re.compile(r'JSESSIONID' + _Q + r'?\s*[=:]\s*' + _Q + r'?(?P<s>[A-Za-z0-9._-]{8,})')),
    # Playwright's cookie dict: {'name': 'JSESSIONID', 'value': '...'}
    ('session cookie', re.compile(r'JSESSIONID' + _Q + r'\s*,\s*' + _Q + r'value' + _Q + r'\s*:\s*' + _Q
                                  + r'(?P<s>[A-Za-z0-9._-]{8,})')),
    ('bearer token', re.compile(r'Bearer\s+(?P<s>[A-Za-z0-9._~+/-]{20,}=*)', re.I)),
    ('basic auth', re.compile(r'Authorization' + _Q + r'?\s*[:=]\s*' + _Q + r'?Basic\s+(?P<s>[A-Za-z0-9+/]{8,}=*)', re.I)),
    ('integration key', re.compile(r'x-vsaas-key' + _Q + r'?\s*[:=]\s*' + _Q + r'?(?P<s>[A-Za-z0-9._-]{12,})', re.I)),
    # No scheme in the pattern. `[a-z][a-z0-9+.-]*://` made each start position of a long run of
    # letters scan to the end of the run (measured 09/21/2026: a 200 KB line took 110 s, and the
    # nightly runs this scan with no time limit before it publishes). A bounded scheme was fast and
    # missed `10.2.0.9-rtsp://user:pw@` and a token of 400 characters. The literal `://` is anchor
    # enough: 0.01 s on a 1 MB line of each character class.
    ('password in a URL', re.compile(r'://[^/\s:@]{1,200}:(?P<s>[^@\s/]{3,2000})@')),
    # a password key with a quoted value: 'password': 'x', "password":"x", &quot;password&quot;: &quot;x&quot;
    ('password value', re.compile(r'(?<![A-Za-z])(?:pass(?:word|wd)?|pwd)' + _Q + r'?\s*[:=]\s*(?P<q>' + _Q
                                  + r')(?P<s>(?:(?!(?P=q)).){4,}?)(?P=q)', re.I)),
    # a password key with a bare value: password=x in a URL, a form body or an env line
    ('password value', re.compile(r'(?<![A-Za-z])(?:pass(?:word|wd)?|pwd)=(?P<s>[^&\s"\'<>\\;,)}\]]{4,})', re.I)),
]


def _is_real(value: str) -> bool:
    """False for a mask, a placeholder, a template variable, or prose (the text of a form label has a space)."""
    v = value.strip()
    return (bool(v) and set(v) != {'*'} and not PLACEHOLDER_RE.match(v)
            and not any(c in v for c in '{<$ ') and not v.startswith('&lt;'))


def value_forms(secrets: dict[str, str]) -> list[tuple[str, str]]:
    """(key, text to find) for each secret, as it is and as a report writes it. Longest first."""
    forms: set[tuple[str, str]] = set()
    for key, value in secrets.items():
        escaped = html.escape(value, quote=True)
        for form in (value, escaped, escaped.replace('&#x27;', '&#39;'), escaped.replace('&quot;', '&#34;'),
                     html.escape(value, quote=False), urllib.parse.quote(value, safe=''),
                     urllib.parse.quote_plus(value), json.dumps(value)[1:-1]):
            forms.add((key, form))
    return sorted(forms, key=lambda kf: -len(kf[1]))


def scan_text(text: str, secrets: dict[str, str]) -> tuple[str, list[dict]]:
    """(text with each secret replaced by ***, findings). A finding holds the line and what matched, never the value."""
    findings: list[dict] = []
    forms = value_forms(secrets)
    out_lines = []
    for idx, line in enumerate(text.split('\n'), 1):
        named: set[str] = set()
        for key, form in forms:
            if form in line:
                if key not in named:
                    findings.append({'line': idx, 'what': f'.env value of {key}'})
                    named.add(key)
                line = line.replace(form, MASK)
        for name, pattern in PATTERNS:
            def mask(m: re.Match[str], name: str = name, idx: int = idx) -> str:
                if not _is_real(m.group('s')):
                    return m.group(0)
                findings.append({'line': idx, 'what': name})
                start, end = m.span('s')
                return m.group(0)[: start - m.start()] + MASK + m.group(0)[end - m.start():]
            line = pattern.sub(mask, line)
        out_lines.append(line)
    return '\n'.join(out_lines), findings


def scan_run(run_dir: Path, secrets: dict[str, str], redact: bool) -> tuple[list[dict], list[str]]:
    """(findings, errors) for one run folder. With redact, each file that holds a secret is written again without it.

    newline='' on both sides: a file keeps its own line endings, so the only
    bytes that change are the secret's. A file with no finding is not written.
    """
    findings: list[dict] = []
    errors: list[str] = []
    for path in sorted(run_dir.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        rel = path.relative_to(run_dir.parent).as_posix()
        try:
            with open(path, encoding='utf-8', errors='surrogateescape', newline='') as f:
                text = f.read()
        except OSError as e:
            errors.append(f'{rel}: could not read: {type(e).__name__}')
            continue
        clean, found = scan_text(text, secrets)
        if not found:
            continue
        for item in found:
            item['path'] = rel
        findings.extend(found)
        if redact:
            try:
                with open(path, 'w', encoding='utf-8', errors='surrogateescape', newline='') as f:
                    f.write(clean)
            except OSError as e:
                errors.append(f'{rel}: holds a secret and could not be written: {type(e).__name__}')
    return findings, errors


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
        print(f'evidence_scan: no secret values read from {args.env}; the scan uses the patterns only, '
              'and marks no folder as scanned (the nightly publishes only marked folders)', file=sys.stderr)

    if args.run_dir:
        run_dirs = [args.run_dir]
    else:
        run_dirs = sorted(d for d in args.runs_dir.iterdir() if d.is_dir() and d.name[:2] == '20')
    missing = [d for d in run_dirs if not d.is_dir()]
    if missing:
        print(f'evidence_scan: not a folder: {missing[0]}', file=sys.stderr)
        return 2

    all_findings: list[dict] = []
    all_errors: list[str] = []
    scanned = 0
    for run_dir in run_dirs:
        marker = run_dir / DONE_MARKER
        if args.runs_dir and marker.exists() and not args.rescan:
            continue
        found, errors = scan_run(run_dir, secrets, args.redact)
        scanned += 1
        all_findings.extend(found)
        all_errors.extend(errors)
        # Only a --redact pass with no error marks a folder: it is then clean
        # at rest and the next pass can skip it. A report pass writes nothing.
        # and only when the scan knew the secret values: a pass with no .env reads shapes only,
        # and a folder it marked would never be read again once the .env is back
        if args.runs_dir and args.redact and not errors and secrets:
            try:
                marker.write_text('scanned by tools/evidence_scan.py\n', encoding='utf-8')
            except OSError as e:
                all_errors.append(f'{run_dir.name}: could not write the marker: {type(e).__name__}')

    for f in all_findings:
        print(f"  {f['path']}:{f['line']}  {f['what']}")
    for e in all_errors:
        print(f'  ERROR {e}', file=sys.stderr)
    verb = 'redacted' if args.redact else 'found'
    print(f'evidence_scan: {scanned} run folder(s) read, {len(all_findings)} secret(s) {verb}, '
          f'{len(all_errors)} error(s).')
    if all_errors:
        return 2
    if all_findings and not args.redact:
        print('evidence_scan: run again with --redact before you publish this evidence.')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
