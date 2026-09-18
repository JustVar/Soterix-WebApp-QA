#!/usr/bin/env python3
"""Replace the /qa-runs/ blocks of the port 80 nginx site with one redirect to the HTTPS site.

Used by setup-https-archive.sh. stdlib only: the box runs it with the system
python3. It edits the file in place, and only when it finds what it expects:

  location ~ ^/qa-runs/... { ... }      the dotfile rule        -> removed
  location /qa-runs/ { ... alias ... }  the archive over HTTP   -> the redirect

A file that already holds the redirect is left as it is (exit 0). A file with
no /qa-runs/ block, or with a nested block inside one, is not touched (exit 1).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REDIRECT = (
    "\t# The archive moved to HTTPS (deploy/spartan1/nginx-qa-runs-site.conf):\n"
    "\t# basic auth over plain HTTP sent the password in clear text.\n"
    "\tlocation /qa-runs/ {\n"
    "\t\treturn 301 https://$host:8444$request_uri;\n"
    "\t}\n"
)
BLOCK_RE = re.compile(r'^[ \t]*location\s+(?:~\s+)?\^?/qa-runs/[^\n{]*\{[^{}]*\}[ \t]*\n', re.M)


def rewrite(text: str) -> str | None:
    """The new file text, the same text when the redirect is already there, or None when the file is not as expected."""
    blocks = list(BLOCK_RE.finditer(text))
    if not blocks:
        return None
    if len(blocks) == 1 and 'return 301 https://$host:8444' in blocks[0].group(0):
        return text
    if not any('alias' in b.group(0) for b in blocks):
        return None
    out = text[: blocks[0].start()] + REDIRECT
    cursor = blocks[0].end()
    for block in blocks[1:]:
        out += text[cursor: block.start()]
        cursor = block.end()
    return out + text[cursor:]


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        sys.stderr.write('usage: nginx_port80_redirect.py <nginx site file>' + '\n')
        return 2
    path = Path(argv[1])
    text = path.read_text(encoding='utf-8')
    new = rewrite(text)
    if new is None:
        sys.stderr.write(f'{path}: the /qa-runs/ blocks are not as expected. The file was not changed' + '\n')
        return 1
    if new == text:
        sys.stdout.write(f'{path}: the redirect is already there' + '\n')
        return 0
    path.write_text(new, encoding='utf-8')
    sys.stdout.write(f'{path}: the /qa-runs/ blocks now redirect to the HTTPS site' + '\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
