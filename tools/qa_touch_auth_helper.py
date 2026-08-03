#!/usr/bin/env python3
"""Extract XSRF token + session Cookie header from a Playwright auth-state file.

Reads a Playwright `storage_state` JSON (the same format produced by
`context.storage_state(path=...)`) and writes a small JSON file containing just
the XSRF token and the Cookie header string needed by
`tools/backfill_qa_touch_metadata.py`.

This decouples the headless API caller from Playwright entirely - once the
auth-state has been written by a browser login (see tools/qatouch_browser.py
or tools/qatouch_api_mode_update.py), this helper produces a tiny credentials
file that any plain HTTP client can use.

Output JSON shape:
    {
      "xsrf_token": "<URL-decoded XSRF-TOKEN cookie value>",
      "cookie_header": "name=value; name=value; ...",
      "domain": "soterixsystems.qatouch.com",
      "source_state_file": "<absolute path>",
      "extracted_at": "<ISO-8601 timestamp>"
    }

Staleness check:
    If --verify is passed, the helper performs a single authenticated GET to
    QA Touch (default: /v2#/new-projects via the same Cookie header) and:
      - 200/3xx  -> writes the output file, exits 0
      - 401/403  -> prints clear refresh instructions, exits 2
      - other    -> warns but still writes the file, exits 0

Usage (PowerShell):

    # Default: read tools/.qatouch_auth_state.json, write tools/.qatouch_creds.json
    python tools/qa_touch_auth_helper.py

    # Custom paths
    python tools/qa_touch_auth_helper.py `
        --auth-state tools/.qatouch_auth_state.json `
        --out tools/.qatouch_creds.json

    # Verify the session is still alive before writing
    python tools/qa_touch_auth_helper.py --verify

How to refresh a stale auth state:

    1. Run any of the browser-based tools that prompt for login, e.g.:
           python tools/qatouch_browser.py explore --case <key>
       or
           python tools/qatouch_api_mode_update.py test
    2. Log in manually when the browser opens.
    3. The tool saves a fresh tools/.qatouch_auth_state.json.
    4. Re-run this helper to produce a fresh creds file.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_AUTH_STATE = REPO / "tools" / ".qatouch_auth_state.json"
DEFAULT_OUT = REPO / "tools" / ".qatouch_creds.json"
DEFAULT_DOMAIN = "soterixsystems.qatouch.com"
DEFAULT_VERIFY_PATH = "/v2"  # cheap GET; SPA shell returns 200 when session is alive


# ---------------------------------------------------------------------------
# Refresh instructions (printed when auth is stale)
# ---------------------------------------------------------------------------
REFRESH_INSTRUCTIONS = """
============================================================
  QA TOUCH AUTH STATE IS STALE
============================================================

The cookies in {state_file} no longer authenticate. QA Touch
returned HTTP {status} on the verify request.

To refresh:

  1. Run a browser-based QA Touch tool that prompts for login,
     e.g. one of these:

         python tools/qatouch_api_mode_update.py test
         python tools/qatouch_browser.py explore --case 0rzJ8Q

  2. When the Chromium window opens, log in to QA Touch manually.
     The tool will detect the successful login and save a fresh
     {state_file} automatically.

  3. Re-run this helper:

         python tools/qa_touch_auth_helper.py --verify

  4. Once it exits 0, you can run the backfill:

         python tools/backfill_qa_touch_metadata.py \\
             --project-key <KEY> --csv <FILE> \\
             --auth-state-file {out_file}
============================================================
"""


# ---------------------------------------------------------------------------
# Storage-state parsing
# ---------------------------------------------------------------------------
def load_storage_state(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(
            f"Auth state file not found: {path}\n"
            f"Run one of the browser-based tools first to generate it "
            f"(see --help for refresh instructions)."
        )
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise SystemExit(f"Auth state file is not valid JSON: {path}\n{e}")


def cookies_for_domain(state: dict, domain: str) -> list[dict]:
    """Return cookies in `state` whose `domain` matches `domain` (suffix match).

    Playwright stores cookies as a flat list under state["cookies"]. Each
    cookie has at minimum: name, value, domain, path. The domain often has a
    leading dot (e.g. ".qatouch.com"); we strip it for comparison.
    """
    out = []
    for c in state.get("cookies", []) or []:
        cd = (c.get("domain") or "").lstrip(".").lower()
        if not cd:
            continue
        if cd == domain.lower() or domain.lower().endswith("." + cd):
            out.append(c)
    return out


def extract_xsrf_and_cookie_header(
    state: dict, domain: str
) -> tuple[str, str, list[str]]:
    """Pull the XSRF-TOKEN value and build a Cookie header string.

    Returns (xsrf_token, cookie_header, all_cookie_names).

    The XSRF token value is URL-decoded - QA Touch URL-encodes the cookie value
    on the wire, and the X-XSRF-TOKEN header expects the decoded form (this is
    exactly what the in-browser fetch in qatouch_api_mode_update.py does via
    `decodeURIComponent`).
    """
    cookies = cookies_for_domain(state, domain)
    if not cookies:
        raise SystemExit(
            f"No cookies for domain '{domain}' in storage state. "
            f"Is the domain correct? Found domains: "
            f"{sorted({(c.get('domain') or '').lstrip('.') for c in state.get('cookies', [])})}"
        )

    xsrf_raw = None
    parts = []
    names = []
    for c in cookies:
        name = c.get("name")
        value = c.get("value", "")
        if not name:
            continue
        names.append(name)
        # Cookie header uses raw (URL-encoded) form as-is - that is what the
        # browser sends back to the server.
        parts.append(f"{name}={value}")
        if name == "XSRF-TOKEN":
            xsrf_raw = value

    if xsrf_raw is None:
        raise SystemExit(
            "XSRF-TOKEN cookie not found in storage state. Auth state may be "
            "incomplete or from an unrelated domain.\n"
            f"Cookies present: {names}"
        )

    # Decode the token value for the X-XSRF-TOKEN header. Laravel/QA Touch
    # URL-encodes the value when setting the cookie; the in-page JS in
    # qatouch_api_mode_update.py does the same `decodeURIComponent` step.
    xsrf_decoded = urllib.parse.unquote(xsrf_raw)

    cookie_header = "; ".join(parts)
    return xsrf_decoded, cookie_header, names


# ---------------------------------------------------------------------------
# Staleness check
# ---------------------------------------------------------------------------
def verify_session(
    domain: str, cookie_header: str, xsrf_token: str, path: str = DEFAULT_VERIFY_PATH
) -> tuple[int, str]:
    """Perform a single GET to check the session is alive.

    Returns (status_code, short_body_snippet). Network errors raise
    urllib.error.URLError; let the caller handle.
    """
    url = f"https://{domain}{path}"
    req = urllib.request.Request(
        url,
        headers={
            "Cookie": cookie_header,
            "X-XSRF-TOKEN": xsrf_token,
            "Accept": "text/html,application/json",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
            ),
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, (r.read(200).decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        body = b""
        try:
            body = e.read(200)
        except Exception:
            pass
        return e.code, body.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--auth-state",
        type=Path,
        default=DEFAULT_AUTH_STATE,
        help=f"Playwright storage_state JSON (default: {DEFAULT_AUTH_STATE})",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Output creds JSON (default: {DEFAULT_OUT})",
    )
    ap.add_argument(
        "--domain",
        default=DEFAULT_DOMAIN,
        help=f"QA Touch domain (default: {DEFAULT_DOMAIN})",
    )
    ap.add_argument(
        "--verify",
        action="store_true",
        help="Verify session is alive against QA Touch before writing output",
    )
    ap.add_argument(
        "--print-only",
        action="store_true",
        help="Print result to stdout instead of writing --out (for piping)",
    )
    args = ap.parse_args()

    state = load_storage_state(args.auth_state)
    xsrf, cookie_header, names = extract_xsrf_and_cookie_header(state, args.domain)

    print(f"  Auth state: {args.auth_state}")
    print(f"  Domain:     {args.domain}")
    print(f"  Cookies:    {len(names)} ({', '.join(sorted(names))})")
    print(f"  XSRF len:   {len(xsrf)} chars")

    if args.verify:
        print(f"  Verifying session against https://{args.domain}{DEFAULT_VERIFY_PATH} ...")
        try:
            status, _ = verify_session(args.domain, cookie_header, xsrf)
        except urllib.error.URLError as e:
            print(f"  Network error during verify: {e}", file=sys.stderr)
            return 3
        print(f"  Verify status: {status}")
        if status in (401, 403):
            print(
                REFRESH_INSTRUCTIONS.format(
                    state_file=args.auth_state,
                    status=status,
                    out_file=args.out,
                ),
                file=sys.stderr,
            )
            return 2
        if status >= 400 and status not in (404,):
            # 404 on /v2 path is unexpected but not a fatal auth signal.
            print(
                f"  WARNING: verify returned {status}; cookies may still work "
                f"for /v1/case/* endpoints. Proceeding.",
                file=sys.stderr,
            )

    out_obj = {
        "xsrf_token": xsrf,
        "cookie_header": cookie_header,
        "domain": args.domain,
        "source_state_file": str(args.auth_state.resolve()),
        "extracted_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }

    if args.print_only:
        json.dump(out_obj, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out_obj, indent=2), encoding="utf-8")
    print(f"  OK wrote -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
