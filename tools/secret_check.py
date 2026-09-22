#!/usr/bin/env python3
"""Refuse a commit that carries a secret value from .env into a tracked file.

The values in .env are the credentials: account passwords, API keys, the
lab camera login. None of them belongs in a file git tracks, and this repo
is pushed to two GitHub organisations. On 09/11/2026 two QA Touch cases
spelled the camera login out in their step text, the snapshot backups
carried it into git, and a later hand edit put it into a conftest. This
check is the gate that was missing: it reads the values of the secret-
looking keys in .env and refuses staged content that contains any of them.

It never prints a value; a finding names the .env KEY and the file:line.

Usage:
  python tools/secret_check.py            # staged changes (the pre-commit hook)
  python tools/secret_check.py --all      # every tracked file
  python tools/secret_check.py --env PATH # another env file (tests)

Exit codes: 0 clean, 1 a secret value found, 2 tool error.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = ROOT / '.env'
# A key whose value is a credential, by its name...
SECRET_KEY_RE = re.compile(r'(PASS|PASSWORD|SECRET|TOKEN|API_KEY|APIKEY|PRIVATE|CLIENT_SECRET)', re.I)
# ...unless the name says the value is a date, a URL, a host or an id
# (AZURE_SECRET_EXPIRES holds a date, and dates sit in docs legitimately).
NOT_SECRET_KEY_RE = re.compile(r'(_EXPIRES|_EXPIRY|_DATE|_URL|_HOST|_ID|_NAME|_PATH|_FILE)$', re.I)
MIN_LEN = 6   # shorter values match innocent text too often
# Values that are placeholders or dates, not secrets.
PLACEHOLDER_RE = re.compile(
    r'^(changeme|password|secret|xxx+|your[-_ ]|<.*>|\$\{.*\}|none|null|true|false|\d+|\d{4}-\d{2}-\d{2}.*)$', re.I)


# The last word of the key, not a part of it: PASSWORD_MIN_LENGTH, PASS_RATE_THRESHOLD and
# BYPASS_TIMEOUT_MS hold numbers that are not secrets, and the scan would mask each one in the logs.
DIGIT_SECRET_KEY_RE = re.compile(r'(?:^|_)(?:PASS|PASSWORD|PASSWD|PWD|PIN)$', re.I)


def secret_values(env_text: str) -> dict[str, str]:
    """{KEY: value} for the credential-looking keys in an env file's text."""
    # python-dotenv reads the text, as the suite does. A hand parser kept the inline comment of
    # `KEY=value # note` as a part of the value and kept the backslash of an escaped quote, so
    # such a secret never matched the evidence (audit 09/21/2026).
    import io

    from dotenv import dotenv_values
    found: dict[str, str] = {}
    # interpolate=False: with it on, ${HOME}/x resolves to a real path, stops matching the
    # placeholder rule, and the scan then masks that path in every published log (audit 09/22/2026)
    for key, value in dotenv_values(stream=io.StringIO(env_text), interpolate=False).items():
        value = (value or '').strip()
        if not SECRET_KEY_RE.search(key) or NOT_SECRET_KEY_RE.search(key):
            continue
        if len(value) < MIN_LEN:
            continue
        # a placeholder is not a secret. An all-digit value is one when its key says password:
        # a camera PIN of 8 digits was dropped as "a number".
        if PLACEHOLDER_RE.match(value) and not (value.isdigit() and DIGIT_SECRET_KEY_RE.search(key)):
            continue
        found[key] = value
    return found


def find_secrets(text: str, secrets: dict[str, str], path: str) -> list[dict]:
    """Findings for every line of `text` that contains a secret value."""
    findings = []
    for idx, line in enumerate(text.splitlines(), 1):
        for key, value in secrets.items():
            if value in line:
                findings.append({'path': path, 'line': idx, 'key': key})
    return findings


def _git(*args: str) -> str:
    result = subprocess.run(['git', '-C', str(ROOT), *args], capture_output=True,
                            text=True, encoding='utf-8', errors='replace', check=False)
    return result.stdout if result.returncode == 0 else ''


def staged_added_lines() -> dict[str, list[tuple[int, str]]]:
    """{path: [(line_no, text)]} for the lines a commit would add."""
    out: dict[str, list[tuple[int, str]]] = {}
    path, new_line = None, 0
    for line in _git('diff', '--cached', '-U0', '--no-color').splitlines():
        if line.startswith('+++ '):
            path = line[6:] if line.startswith('+++ b/') else None
        elif line.startswith('@@'):
            m = re.search(r'\+(\d+)', line)
            new_line = int(m.group(1)) if m else 0
        elif path and line.startswith('+') and not line.startswith('+++'):
            out.setdefault(path, []).append((new_line, line[1:]))
            new_line += 1
        elif path and not line.startswith('-'):
            new_line += 1
    return out


def check_staged(secrets: dict[str, str]) -> list[dict]:
    findings = []
    for path, lines in staged_added_lines().items():
        for line_no, text in lines:
            for key, value in secrets.items():
                if value in text:
                    findings.append({'path': path, 'line': line_no, 'key': key})
    return findings


def check_all(secrets: dict[str, str]) -> list[dict]:
    findings = []
    for path in _git('ls-files').splitlines():
        full = ROOT / path
        try:
            text = full.read_text(encoding='utf-8', errors='replace')
        except (OSError, UnicodeDecodeError):
            continue
        findings.extend(find_secrets(text, secrets, path))
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--all', action='store_true', help='scan every tracked file, not the staged diff')
    parser.add_argument('--env', type=Path, default=ENV_FILE, help='the env file whose values are the secrets')
    args = parser.parse_args(argv)
    if not args.env.exists():
        print(f'secret_check: no {args.env.name}; nothing to compare against.')
        return 0
    secrets = secret_values(args.env.read_text(encoding='utf-8', errors='replace'))
    if not secrets:
        print('secret_check: no credential-looking keys in the env file.')
        return 0
    findings = check_all(secrets) if args.all else check_staged(secrets)
    for f in findings:
        print(f"[SECRET] {f['path']}:{f['line']}  carries the value of {f['key']} from .env")
    scope = 'tracked files' if args.all else 'staged changes'
    if findings:
        print(f'\n{len(findings)} secret value(s) in {scope}. A credential lives in .env, never in a '
              f'tracked file; remove it (or reference the .env key) and commit again.')
        return 1
    print(f'secret_check: {scope} carry none of the {len(secrets)} credential values from .env.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
