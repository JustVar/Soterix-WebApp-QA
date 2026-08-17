#!/usr/bin/env python3
"""Launch the QA Touch MCP server with credentials from .env.

The MCP server (`qatouch-mcp-server` on npm) wants QATOUCH_DOMAIN and
QATOUCH_API_TOKEN in its environment. Our credentials live in the repo's
gitignored `.env` under QATOUCH_API_KEY, and `.env` is not exported into the
shell. This bridges the two so `.mcp.json` never has to hold a token.

Deliberately stdlib-only, so ANY python on the machine can run it. Do not add
imports that need installing - the MCP client may not use the repo venv.

Nothing here needs configuring. If `.env` works for the other QA Touch tools,
it works for this.

To check it starts:
    python tools/qatouch_mcp_launch.py
It will sit waiting for MCP traffic on stdin, which means it is healthy.
Press Ctrl+C to stop.

Normally your MCP client starts it for you. See `.mcp.json`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / ".env"


def read_env_file(path: Path) -> dict[str, str]:
    """Read a .env file into a dict. Ignores comments and blank lines."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def fail(message: str) -> None:
    """Report a setup problem on stderr and stop.

    stdout is the MCP channel, so nothing but protocol traffic may go there.
    """
    sys.stderr.write(f"qatouch-mcp: {message}\n")
    sys.exit(1)


def main() -> int:
    file_env = read_env_file(ENV_PATH)

    def setting(*names: str) -> str | None:
        for name in names:
            value = os.environ.get(name) or file_env.get(name)
            if value:
                return value
        return None

    domain = setting("QATOUCH_DOMAIN")
    token = setting("QATOUCH_API_TOKEN", "QATOUCH_API_KEY")

    if not domain or not token:
        fail(f"QATOUCH_DOMAIN and QATOUCH_API_KEY must be set in {ENV_PATH}. "
             f"See docs/CREDENTIALS_SETUP.md.")

    # npx is a .cmd shim on Windows, so resolve the real file.
    npx = shutil.which("npx") or shutil.which("npx.cmd")
    if not npx:
        fail("npx not found. Install Node.js 18 or newer, then retry.")

    env = dict(os.environ)
    env["QATOUCH_DOMAIN"] = domain
    env["QATOUCH_API_TOKEN"] = token

    # Hand stdio straight to the server: MCP is JSON-RPC over stdin/stdout.
    return subprocess.call([npx, "-y", "qatouch-mcp-server"], env=env)


if __name__ == "__main__":
    sys.exit(main())
