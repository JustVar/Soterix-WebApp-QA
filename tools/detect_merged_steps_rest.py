"""
detect_merged_steps_rest.py
============================

Fast REST-only variant of ``detect_merged_steps.py``. Uses the public
QA Touch REST endpoint ``/api/v1/getAllTestCases/{projectKey}`` which
returns a ``Steps`` array per case - enough to classify without any
per-case ``/v1/case/edit`` fetch. Skips the internal-auth path entirely,
so no auth-death mid-run.

Classification (same semantics as detect_merged_steps.py):

    merged   - Steps array has 1 entry, and its step_description text
               contains >= 3 ``^\\s*Step\\s*\\d+\\s*[:.\\)]\\s*`` markers.
    split    - Steps array has > 1 entries. No action needed.
    empty    - Steps array has 0 entries.
    single   - Steps array has 1 entry, < 3 in-line "Step N:" markers.

The manifest output matches detect_merged_steps.py's schema so the
existing ``split_merged_steps.py`` can consume either file.

Auth
----
REST only: api-token + domain headers, loaded from env
(``QATOUCH_API_TOKEN`` / ``QATOUCH_API_KEY`` + ``QATOUCH_DOMAIN``) or
``~/.tooling.json``. The internal ``/v1/*`` path is not used.

Usage
-----
    python tools/detect_merged_steps_rest.py --project-key JlW1

    python tools/detect_merged_steps_rest.py --project-key JlW1 \\
        --out logs/merged_steps_JlW1_<TIMESTAMP>.json --limit 100

Why this exists
---------------
The original ``detect_merged_steps.py`` paginates via REST (works) but
then hits ``POST /v1/case/edit`` per case (internal auth) - which
auth-dies after ~50 cases unless the creds file is refreshed mid-run.
For a project the size of JlW1 (3,000+ cases) that's not viable.

This tool sidesteps the issue by classifying directly from the REST
list response (~62 pages for JlW1, ~2 minutes total).

Exit codes
----------
    0  scan completed
    1  scan interrupted (Ctrl-C)
    2  fatal pre-flight error (REST auth missing/stale, project not found)
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional, Tuple


# Canonical "Step N:" prefix (matches detect_merged_steps.py +
# qa_post_import_split_and_position.py:146)
STEP_PREFIX_RE = re.compile(r"(?im)^\s*Step\s*\d+\s*[:\.\)]\s*")
# Numbered-list prefix style ("1." / "2)" / "1: " at line start).
# Some authoring paths emit merged step bodies as a plain numbered list
# instead of "Step N:". The OTA / camera-firmware cases in 60W5 use this
# style (see memory: qa-touch-ota-cleanup-archived.md).
NUMBERED_PREFIX_RE = re.compile(r"(?m)^\s*\d+\s*[\.\):]\s+")
MERGED_THRESHOLD = 3
DEFAULT_REST_DOMAIN_SHORT = "soterixsystems"
DEFAULT_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


def load_rest_creds() -> Tuple[Optional[str], str]:
    """Load REST api-token + domain (short form, e.g. 'soterixsystems').

    Reads env first, then ~/.tooling.json. Same precedence as the existing
    tools so a working detect_merged_steps.py environment continues to work.
    """
    token = (
        os.environ.get("QATOUCH_API_TOKEN")
        or os.environ.get("QATOUCH_API_KEY")
    )
    domain = os.environ.get("QATOUCH_DOMAIN") or DEFAULT_REST_DOMAIN_SHORT
    if token:
        return token, domain

    tooling_json = Path.home() / ".tooling.json"
    if tooling_json.exists():
        try:
            env = json.loads(tooling_json.read_text(encoding="utf-8"))
            # The user's ~/.tooling.json may have either a flat env dict or
            # an mcpServers.qatouch.env shape. Try both.
            if isinstance(env, dict):
                token = env.get("QATOUCH_API_TOKEN") or env.get("QATOUCH_API_KEY")
                domain = env.get("QATOUCH_DOMAIN") or domain
                if not token:
                    api = env.get("mcpServers") or {}
                    qt = (api.get("qatouch") or {}).get("env") or {}
                    token = qt.get("QATOUCH_API_TOKEN") or qt.get("QATOUCH_API_KEY")
                    domain = qt.get("QATOUCH_DOMAIN") or domain
        except (OSError, json.JSONDecodeError):
            pass

    return token, domain


def rest_get_page(
    project_key: str,
    page: int,
    token: str,
    domain_short: str,
    max_retries: int = 4,
) -> dict:
    """REST GET /api/v1/getAllTestCases/{pid}?page=N with 429 backoff."""
    url = f"https://api.qatouch.com/api/v1/getAllTestCases/{project_key}?page={page}"
    req = urllib.request.Request(
        url,
        headers={
            "api-token": token,
            "domain": domain_short,
            "Accept": "application/json",
        },
        method="GET",
    )
    for attempt in range(max_retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read().decode("utf-8")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                wait = 2 ** (attempt + 1)
                print(f"  REST 429 on page {page} - sleeping {wait}s")
                time.sleep(wait)
                continue
            raise


def classify(case: dict) -> Tuple[str, int, int, str, str]:
    """Apply the merged/split/empty/single classification to a single case.

    Returns (classification, step_count, parsed_step_markers, step_excerpt,
    expected_result_excerpt).
    """
    steps = case.get("Steps") or []
    step_count = len(steps)
    if step_count == 0:
        return "empty", 0, 0, "", ""
    if step_count > 1:
        # Already split. Excerpts from the first step for context.
        first = steps[0]
        return (
            "split",
            step_count,
            0,
            (first.get("step_description") or "")[:200],
            (first.get("expected_result") or "")[:100],
        )
    # Exactly one step - count BOTH "Step N:" markers AND plain numbered-list
    # prefixes ("1." / "2)" / etc.). Either style indicates the body is
    # actually multiple steps that were collapsed into one row at import time.
    first = steps[0]
    body = first.get("step_description") or ""
    step_markers = len(STEP_PREFIX_RE.findall(body))
    num_markers = len(NUMBERED_PREFIX_RE.findall(body))
    # Use whichever style appears more (allows a passing mention of "Step 1"
    # inside a numbered list, or vice-versa, without double-counting).
    markers = max(step_markers, num_markers)
    excerpt_step = body[:200]
    excerpt_exp = (first.get("expected_result") or "")[:100]
    if markers >= MERGED_THRESHOLD:
        return "merged", 1, markers, excerpt_step, excerpt_exp
    return "single", 1, markers, excerpt_step, excerpt_exp


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--project-key", required=True,
                    help="QA Touch project key (e.g. JlW1).")
    ap.add_argument("--module-key", default=None,
                    help="Comma-separated module_key filter (optional).")
    ap.add_argument("--limit", type=int, default=0,
                    help="Audit at most N cases (0 = all).")
    ap.add_argument("--out", type=Path, default=None,
                    help="Manifest output path (default: logs/merged_steps_"
                         "manifest_{project}_{YYYYMMDD-HHMMSS}.json)")
    ap.add_argument("--rate-ms", type=int, default=400,
                    help="Inter-page delay in ms (default: 400, ~2.5 req/s).")
    args = ap.parse_args()

    token, domain_short = load_rest_creds()
    if not token:
        print(
            "ERROR: missing REST api-token. Set QATOUCH_API_TOKEN in env, or"
            " populate ~/.tooling.json.",
            file=sys.stderr,
        )
        return 2

    module_filter = None
    if args.module_key:
        module_filter = {m.strip() for m in args.module_key.split(",") if m.strip()}

    # Pre-flight: get page 1 to confirm auth + read total + last_page
    try:
        page1 = rest_get_page(args.project_key, 1, token, domain_short)
    except urllib.error.HTTPError as e:
        print(f"ERROR: REST pre-flight failed: HTTP {e.code} - {e.read()[:200]!r}",
              file=sys.stderr)
        return 2
    meta = page1.get("meta") or {}
    link = page1.get("link") or {}
    total = int(meta.get("total") or 0)
    last_page_url = link.get("last") or ""
    last_page = int(last_page_url.rsplit("=", 1)[-1]) if "page=" in last_page_url else 1
    print(f"  Project: {args.project_key}  Total cases: {total}  Pages: {last_page}")

    # Output path
    if args.out is None:
        ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        DEFAULT_LOG_DIR.mkdir(parents=True, exist_ok=True)
        out_path = DEFAULT_LOG_DIR / f"merged_steps_manifest_{args.project_key}_{ts}.json"
    else:
        out_path = args.out
        out_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"  Manifest: {out_path}")

    # Iterate pages
    all_results = []
    scanned = 0
    pages_to_scan = list(range(1, last_page + 1))

    try:
        for page_idx, page_num in enumerate(pages_to_scan, 1):
            if page_num == 1:
                page = page1  # reuse pre-flight call
            else:
                page = rest_get_page(args.project_key, page_num, token, domain_short)
            cases = page.get("data") or []

            for case in cases:
                if module_filter and case.get("module_key") not in module_filter:
                    continue
                cls, step_count, markers, step_excerpt, exp_excerpt = classify(case)
                all_results.append({
                    "case_key": case.get("case_key"),
                    "case_code": case.get("case_code"),
                    "case_title": case.get("case_title"),
                    "module_key": case.get("module_key"),
                    "module_name": case.get("module_name"),
                    "classification": cls,
                    "step_count": step_count,
                    "parsed_step_markers": markers,
                    "step_excerpt": step_excerpt,
                    "expected_result_excerpt": exp_excerpt,
                    "http_status": 200,
                    "error": None,
                })
                scanned += 1
                if args.limit and scanned >= args.limit:
                    raise StopIteration

            if page_num % 5 == 0 or page_num == last_page:
                print(f"  [{page_num}/{last_page}] scanned {scanned} cases so far")

            if page_num < last_page and args.rate_ms:
                time.sleep(args.rate_ms / 1000.0)
    except StopIteration:
        pass
    except KeyboardInterrupt:
        print(" Interrupted - flushing partial manifest...")
        # Fall through to save what we have
        rc = 1
    else:
        rc = 0

    # Summary
    by_class = {}
    for r in all_results:
        by_class[r["classification"]] = by_class.get(r["classification"], 0) + 1
    print()
    print(f"  Scanned: {len(all_results)} cases")
    for k in ("merged", "split", "empty", "single", "error"):
        if k in by_class:
            print(f"    {k:>7}: {by_class[k]}")

    manifest = {
        "project_key": args.project_key,
        "scanned_at": _dt.datetime.now().isoformat(),
        "module_filter": sorted(module_filter) if module_filter else None,
        "summary": by_class,
        "results": all_results,
    }
    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"  Manifest written: {out_path}")
    return rc if 'rc' in locals() else 0


if __name__ == "__main__":
    sys.exit(main())
