#!/usr/bin/env python3
"""Phase A polish - move the real "Expected Result" content from whichever
step currently holds it (typically step 1) to the LAST step on each of the
214 Partner Portal target cases in 70l1, replacing the original location
with "-".

urllib refactor (2026-06-25)
============================
This script was originally driven by Playwright, reusing the
migrate_pp_cases_phase_a_steps.py helpers (open_browser + page.evaluate
fetch). That worked at small scale, but on the full 214-case run the
QA Touch laravel_session was invalidated after roughly 8 cases of
heavy /v1/steps/delete + /v1/steps/save churn. Every subsequent
/v1/case/edit read returned HTTP 500, every save returned 401, and the
operator had to re-login by hand and resume - repeatedly.

The Partner Admin metadata backfill (run_partner_admin_backfill.py)
hit the same vendor surface at higher volume (422 cases, ~3700
internal calls) using plain stdlib urllib + a small creds JSON
(tools/.qatouch_creds.json) extracted from the storage state. That
run did NOT lose auth. The browser-side Playwright path is what
attracts the CSRF-rotation defense; a direct cookie + XSRF replay
behaves like a normal SPA tab and survives.

This file is the urllib version of the same logic. It is stdlib-only
(no playwright, no requests, no httpx), reads .qatouch_creds.json,
pre-flights against GET /v2, and detects 401 on every internal call
with the same AuthDied sentinel + clean resume hint as the original.

Why this script exists (logic unchanged)
========================================
The Phase A migration (`migrate_pp_cases_phase_a_steps.py`) replicated
source step rows verbatim from JlW1 onto the 214 target shells in 70l1.
The source convention (carried over by the prior copy) puts the overall
"Expected Result" text on step 1, with steps 2..N populated as a literal
"-" (DASH_FALLBACK). The desired UI convention for the Partner Portal
target cases is the inverse - the real expected text belongs on the LAST
step, with the earlier rows showing "-".

This script walks each target case, locates the "carrier" step (the row
whose expected_result is non-empty AND not "-"), and moves that text to
the last step.

Strategy (per recon - PRIMARY PATH only)
========================================
/v1/steps/update was probed once with an empty body and never confirmed.
We treat it as not-available and use the proven REBUILD-FROM-CUT-POINT
pattern from migrate_pp_cases_phase_a_steps.py, qatouch_step_api.py,
qatouch_c2c_step_split.py, and cleanup_ota_steps.py:

  1. POST /v1/case/edit/p/{pid}/cid/{caseKey} (empty body). Read
     data.caseStep[] in order; capture .id, .step, .description for
     every row.
  2. Locate the carrier_step. If none -> status 'no_expected_to_move'.
     If carrier_step IS already the last row -> status 'already_at_last'.
  3. Determine the cut point = position of carrier_step. Delete every
     row from cut point to end via GET /v1/steps/delete/mid/{id}?type=true,
     tolerating individual delete failures.
  4. Re-save the tail in order:
       - rows BETWEEN cut and last: step text preserved, expected = "-"
       - last row: step text preserved, expected = carrier_step's
         original real_expected
     Each /v1/steps/save returns 200; new rows append at position N+1.
  5. Re-fetch /v1/case/edit and verify (a) len(caseStep) == original
     count, (b) the last row's description matches real_expected, and
     (c) the carrier_step position now shows "-".

Idempotency
===========
- carrier_step already last -> status 'already_at_last' (no writes).
- No carrier_step anywhere -> status 'no_expected_to_move' (no writes).
- Crash mid-rebuild: resume re-reads, finds no carrier_step (all "-"),
  and reports 'no_expected_to_move'. The case must be hand-fixed; this
  script will NOT regenerate missing rows because it does not have the
  source-of-truth step text for rows that were already wiped.

Auth refresh
============
If a 401 fires, refresh creds (interactive headed-browser login):

    python tools/qatouch_api_mode_update.py test

That rewrites both tools/.qatouch_auth_state.json AND
tools/.qatouch_creds.json. Then re-run with --resume-from.

CLI
===
  python tools/migrate_pp_cases_phase_a_expected_to_last.py
      [--input PATH]              resume manifest (default:
                                  logs/pp_migration_phase_a_resume_20260625-091616.json)
      [--limit N]                 process only first N records
      [--dry-run]                 print plan, no writes
      [--resume-from N]           skip first N records of input
      [--auth-state-file PATH]    IGNORED - kept for CLI compat with old runs
      [--creds-file PATH]         override .qatouch_creds.json path
      [--rate-ms 1300]            inter-case pause (ms)
      [--inter-call-ms 800]       inter-internal-call pause (ms)

Outputs
=======
  logs/pp_expected_to_last_{YYYYmmdd-HHMMSS}.json - per-case record:
    {source_key, target_key, target_module, status, original_position,
     real_expected_excerpt, errors[]}

  status values:
    moved                 - carrier step's expected moved to last row, "-" stamped on original.
    already_at_last       - carrier step was already the last row; no writes.
    no_expected_to_move   - no non-empty, non-"-" expected_result found on any step.
    dry_run               - --dry-run; printed the plan only.
    failed                - at least one delete/save/verify mismatch.

Exit code: 0 if no failed records, 1 otherwise.
"""
from __future__ import annotations

import argparse
import functools
import html
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

_print = print
print = functools.partial(_print, flush=True)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = ROOT / "tools"
LOG_DIR = ROOT / "logs"

# ── Constants ───────────────────────────────────────────────────────────────
TARGET_PROJECT = "70l1"  # Partner Admin

DEFAULT_CREDS_FILE = TOOLS_DIR / ".qatouch_creds.json"
DEFAULT_AUTH_STATE = TOOLS_DIR / ".qatouch_auth_state.json"  # legacy; ignored
DEFAULT_RESUME_INPUT = (
    ROOT / "logs" / "pp_migration_phase_a_resume_20260625-091616.json"
)

DASH_FALLBACK = "-"

# Per recon: heavier than Phase A steps because we issue ~2x the calls per
# case (delete + save instead of just save). Overridable via --inter-call-ms.
INTER_CALL_DELAY = 0.8       # seconds between any two internal API calls
VERIFY_PAUSE = 0.7           # seconds between final save and re-fetch
RATE_LIMIT_PAUSE = 20.0      # seconds when we see HTTP 429

REFRESH_INSTRUCTIONS = (
    "QA Touch auth appears stale (HTTP 401 from /v1/* or /v2).\n"
    "Refresh it with:\n"
    "    python tools/qatouch_api_mode_update.py test\n"
    "That drives a logged-in browser, refreshes tools/.qatouch_auth_state.json,\n"
    "and rewrites tools/.qatouch_creds.json. Then resume this script with\n"
    "--resume-from N (N printed below)."
)


# ── Auth-death sentinel ─────────────────────────────────────────────────────
class AuthDied(Exception):
    """Raised the moment any /v1/* call returns 401.

    Continuing past a 401 is pointless - the session is invalidated and
    every subsequent read returns 401 (or 500). The caller catches this,
    prints a refresh-and-resume hint with the 1-based index of the failing
    case, writes the summary, and exits.
    """

    def __init__(self, op: str, status: int, detail: str = ""):
        self.op = op
        self.status = status
        self.detail = detail
        super().__init__(f"AUTH DIED on {op}: HTTP {status} {detail}".strip())


# ── Auth + HTTP plumbing (mirrors run_partner_admin_backfill.py) ────────────
class AuthCreds:
    def __init__(self, xsrf_token: str, cookie_header: str, domain: str):
        self.xsrf_token = xsrf_token
        self.cookie_header = cookie_header
        self.domain = domain

    @classmethod
    def load(cls, path: Path) -> "AuthCreds":
        if not path.exists():
            print(
                f"Auth creds file not found: {path}\n"
                "Generate it with:\n"
                "    python tools/qatouch_api_mode_update.py test",
                file=sys.stderr,
            )
            raise SystemExit(2)
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("xsrf_token", "cookie_header", "domain"):
            if not data.get(key):
                print(
                    f"Auth creds file missing required field: {key}",
                    file=sys.stderr,
                )
                raise SystemExit(2)
        return cls(data["xsrf_token"], data["cookie_header"], data["domain"])


def _common_headers(creds: AuthCreds) -> dict[str, str]:
    base = f"https://{creds.domain}"
    return {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json",
        "X-XSRF-TOKEN": creds.xsrf_token,
        "Cookie": creds.cookie_header,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Origin": base,
        "Referer": f"{base}/v2",
    }


def http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 30,
) -> tuple[int, bytes]:
    """Plain urllib request that swallows HTTPError (we want the body for 5xx)."""
    req = urllib.request.Request(
        url, method=method, data=body, headers=headers or {}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        body_bytes = b""
        try:
            body_bytes = e.read()
        except Exception:
            pass
        return e.code, body_bytes
    except urllib.error.URLError as e:
        return 0, f"URLError: {getattr(e, 'reason', e)}".encode("utf-8")


def _internal_request(
    creds: AuthCreds,
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
) -> tuple[int, Any]:
    """Issue an internal QA Touch request with full SPA-shape headers.

    Returns (status_code, parsed_body_or_raw_text).
    Caller is responsible for AuthDied detection on 401.
    """
    url = f"https://{creds.domain}{path}"
    body = json.dumps(json_body).encode("utf-8") if json_body is not None else None
    status, raw = http_request(
        method, url, headers=_common_headers(creds), body=body
    )
    text = raw.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, text


# ── Pre-flight: verify creds against /v2 ────────────────────────────────────
def verify_auth(creds: AuthCreds) -> tuple[bool, str]:
    """Hit GET https://{domain}/v2 once. Return (ok, message).

    Mirrors run_partner_admin_backfill.verify_auth - uses the lightweight
    HTML-Accept header shape (NOT the JSON-content-type internal-POST
    shape, which would 401 even with valid cookies).
    """
    url = f"https://{creds.domain}/v2"
    common = _common_headers(creds)
    headers = {
        "Cookie": common["Cookie"],
        "X-XSRF-TOKEN": common["X-XSRF-TOKEN"],
        "User-Agent": common["User-Agent"],
        "Accept": "text/html,application/json",
    }
    status, raw = http_request("GET", url, headers=headers)
    if status in (401, 403):
        return False, f"verify GET /v2 returned HTTP {status} (stale auth)"
    if status == 0:
        return False, raw.decode("utf-8", errors="replace")
    if status >= 400 and status != 404:
        return True, (
            f"verify GET /v2 returned HTTP {status} - non-fatal, "
            "cookies may still work for /v1/* endpoints"
        )
    return True, f"verify GET /v2 returned HTTP {status}"


# ── Internal API wrappers ───────────────────────────────────────────────────
def fetch_case_edit(
    creds: AuthCreds, project_key: str, case_key: str
) -> tuple[int, dict | None, str]:
    """POST /v1/case/edit/p/{pk}/cid/{ck} -> (status, data_dict_or_None, error_msg).

    Unwraps body["data"] when present. Raises AuthDied on 401.
    """
    status, body = _internal_request(
        creds, "POST", f"/v1/case/edit/p/{project_key}/cid/{case_key}",
        json_body={},
    )
    if status == 401:
        raise AuthDied("/v1/case/edit", 401, f"cid={case_key}")
    if status != 200 or not isinstance(body, dict):
        return status, None, f"HTTP {status}"
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(data, dict):
        return status, None, "no data field"
    return status, data, ""


def save_step(
    creds: AuthCreds,
    project_key: str,
    case_key: str,
    step_description: str,
    expected_result: str,
) -> dict:
    """POST /v1/steps/save with the proven body shape.

    Body: {cid, pid, step_description, expected_result}. Returns
    {ok, status, body, rateLimited}. Caller checks for 401 (AuthDied).
    """
    status, body = _internal_request(
        creds, "POST", "/v1/steps/save",
        json_body={
            "cid": case_key,
            "pid": project_key,
            "step_description": step_description,
            "expected_result": expected_result,
        },
    )
    body_text = body if isinstance(body, str) else json.dumps(body)[:300]
    return {
        "ok": 200 <= status < 300,
        "status": status,
        "body": body_text[:300] if isinstance(body_text, str) else "",
        "rateLimited": status == 429,
    }


def delete_step(creds: AuthCreds, step_id: str) -> dict:
    """GET /v1/steps/delete/mid/{id}?type=true. Returns {ok, status}."""
    status, body = _internal_request(
        creds, "GET", f"/v1/steps/delete/mid/{step_id}?type=true",
    )
    return {
        "ok": 200 <= status < 300,
        "status": status,
        "rateLimited": status == 429,
    }


# ── HTML / content helpers ──────────────────────────────────────────────────
def _strip_html(text: str) -> str:
    """Rough plain-text extraction for the 'is this empty or just "-"?'
    check. Server returns simple <p>...</p> wrappers in practice; we only
    need to detect emptiness vs the literal dash.
    """
    if not text:
        return ""
    t = text
    for token in ("<p>", "</p>", "<br>", "<br/>", "<br />", "&nbsp;"):
        t = t.replace(token, "")
    return t.strip()


def is_carrier_expected(expected_html: str) -> bool:
    """A 'carrier' is any expected_result that is NON-EMPTY and NOT the
    literal dash placeholder.
    """
    plain = _strip_html(expected_html or "")
    if not plain:
        return False
    if plain == DASH_FALLBACK:
        return False
    return True


def excerpt(text: str, n: int = 120) -> str:
    plain = _strip_html(text or "")
    return plain[:n]


def normalise_step_html(text: str) -> str:
    """Source caseStep[i].step / .description come back ALREADY HTML-wrapped
    in practice. Pass through if already HTML-tag-bracketed; otherwise wrap
    in <p>...</p> with html.escape so any stray &/< in plain text is safe.

    Matches the precedent in migrate_pp_cases_phase_a_steps.normalise_step_html
    + qatouch_c2c_step_split's gentle wrap.
    """
    if not text:
        return ""
    t = text.strip()
    if not t:
        return ""
    if t.startswith("<") and t.endswith(">"):
        return t
    # html.unescape -> html.escape round-trip preserves already-encoded
    # entities cleanly; matches the pattern called out in the spec.
    safe = html.escape(html.unescape(t), quote=False)
    return f"<p>{safe}</p>"


# ── Logging ─────────────────────────────────────────────────────────────────
def atomic_write_log(log_path: Path, entries: list[dict]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = log_path.with_suffix(log_path.suffix + ".tmp")
    tmp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    tmp.replace(log_path)


# ── Per-case work ───────────────────────────────────────────────────────────
def find_carrier_index(case_steps: list[dict]) -> int:
    """Return the 0-based index of the first step whose expected_result is
    a real value (not empty, not "-"). Return -1 if none found.
    """
    for i, s in enumerate(case_steps):
        if is_carrier_expected(s.get("description", "") or ""):
            return i
    return -1


def _save_with_retry(
    creds: AuthCreds,
    case_key: str,
    step_html: str,
    expected_html: str,
    row_label: str,
) -> dict:
    """Single /v1/steps/save with 429 backoff + 401 -> AuthDied."""
    r = save_step(creds, TARGET_PROJECT, case_key, step_html, expected_html)
    if r.get("status") == 429 or r.get("rateLimited"):
        print(f"    rate-limited on save {row_label} - pausing {RATE_LIMIT_PAUSE}s")
        time.sleep(RATE_LIMIT_PAUSE)
        r = save_step(
            creds, TARGET_PROJECT, case_key, step_html, expected_html
        )
    if r.get("status") == 401:
        raise AuthDied(
            "/v1/steps/save", 401,
            f"row {row_label} body={(r.get('body') or '')[:80]}",
        )
    return r


def _delete_with_retry(creds: AuthCreds, step_id: str) -> dict:
    """Single /v1/steps/delete with 429 backoff + 401 -> AuthDied."""
    r = delete_step(creds, step_id)
    if r.get("status") == 429 or r.get("rateLimited"):
        print(
            f"    rate-limited on delete sid={step_id} - pausing "
            f"{RATE_LIMIT_PAUSE}s"
        )
        time.sleep(RATE_LIMIT_PAUSE)
        r = delete_step(creds, step_id)
    if r.get("status") == 401:
        raise AuthDied("/v1/steps/delete", 401, f"sid={step_id}")
    return r


def process_one(creds: AuthCreds, record: dict, args) -> dict:
    """Process one target case. Returns a log record per the spec."""
    source_key = record.get("source_key", "")
    target_key = record["target_key"]
    target_module = record.get("target_module_name", "?")
    source_title = record.get("source_title", "")

    entry: dict[str, Any] = {
        "source_key": source_key,
        "target_key": target_key,
        "target_module": target_module,
        "source_title": source_title,
        "status": "pending",
        "original_position": None,
        "real_expected_excerpt": "",
        "errors": [],
    }

    # 1. Read target /v1/case/edit
    status, tgt, err = fetch_case_edit(creds, TARGET_PROJECT, target_key)
    if tgt is None:
        entry["status"] = "failed"
        entry["errors"].append(f"target edit read failed: {err or status}")
        return entry

    case_steps = tgt.get("caseStep") or []
    total = len(case_steps)

    if total == 0:
        entry["status"] = "no_expected_to_move"
        entry["errors"].append("no caseStep rows on target")
        return entry

    # 2. Locate carrier_step
    carrier_idx = find_carrier_index(case_steps)
    if carrier_idx < 0:
        entry["status"] = "no_expected_to_move"
        return entry

    carrier = case_steps[carrier_idx]
    real_expected_html = carrier.get("description", "") or ""
    entry["original_position"] = carrier_idx + 1  # 1-based for humans
    entry["real_expected_excerpt"] = excerpt(real_expected_html)

    # 3. Already at last? Idempotency short-circuit.
    if carrier_idx == total - 1:
        entry["status"] = "already_at_last"
        return entry

    if args.dry_run:
        entry["status"] = "dry_run"
        entry["errors"].append(
            f"would rebuild rows {carrier_idx + 1}..{total} (cut at "
            f"position {carrier_idx + 1}); move real expected from "
            f"step {carrier_idx + 1} to step {total}; stamp '-' on "
            f"intermediate rows"
        )
        return entry

    # 4. Capture step text for every row from carrier..end. We will
    #    re-save these (step text preserved, expected_result rewritten)
    #    after deleting them.
    tail_rows = case_steps[carrier_idx:]  # rows to delete + rebuild
    planned: list[dict] = []
    for i, row in enumerate(tail_rows):
        step_html = row.get("step", "") or ""
        if i == len(tail_rows) - 1:
            planned.append({
                "step_html": step_html,
                "expected_html": real_expected_html,
            })
        else:
            planned.append({
                "step_html": step_html,
                "expected_html": DASH_FALLBACK,
            })

    # 5. Delete the tail rows. Tolerate individual delete failures.
    for row in tail_rows:
        sid = row.get("id")
        if not sid:
            entry["errors"].append(
                f"warning: tail row missing id: {row.get('step', '')[:60]!r}"
            )
            continue
        r = _delete_with_retry(creds, str(sid))
        if not r.get("ok"):
            entry["errors"].append(
                f"delete step id={sid} failed: status={r.get('status')}"
            )
        time.sleep(args.inter_call_seconds)

    # 6. Re-save the planned tail in order. Server assigns position by
    #    insertion order - caller must loop in order.
    for i, plan in enumerate(planned, 1):
        step_html = normalise_step_html(plan["step_html"])
        expected_html = normalise_step_html(plan["expected_html"])
        if not _strip_html(expected_html):
            expected_html = DASH_FALLBACK
        row_label = f"{i}/{len(planned)}"
        r = _save_with_retry(
            creds, target_key, step_html, expected_html, row_label,
        )
        if not r.get("ok"):
            entry["errors"].append(
                f"save row {i} failed: status={r.get('status')} "
                f"body={(r.get('body') or '')[:120]}"
            )
        time.sleep(args.inter_call_seconds)

    # 7. Verify by re-fetching /v1/case/edit.
    time.sleep(VERIFY_PAUSE)
    status, verify, err = fetch_case_edit(creds, TARGET_PROJECT, target_key)
    if verify is None:
        entry["errors"].append(f"verify re-read failed: {err or status}")
        entry["status"] = "failed"
        return entry

    verify_steps = verify.get("caseStep") or []
    final_count = len(verify_steps)

    if final_count != total:
        entry["errors"].append(
            f"verify_mismatch: expected {total} rows after rebuild, "
            f"found {final_count}"
        )
    else:
        # Last row's description must equal the real_expected we moved.
        last_row = verify_steps[-1] or {}
        last_desc = last_row.get("description", "") or ""
        if _strip_html(last_desc) != _strip_html(real_expected_html):
            entry["errors"].append(
                f"verify_mismatch: last row description does not match "
                f"moved expected. got={excerpt(last_desc)!r} "
                f"want={excerpt(real_expected_html)!r}"
            )
        # Original carrier position should now show "-".
        if carrier_idx < final_count:
            origin_row = verify_steps[carrier_idx] or {}
            origin_desc = origin_row.get("description", "") or ""
            if _strip_html(origin_desc) != DASH_FALLBACK:
                entry["errors"].append(
                    f"verify_mismatch: original carrier position "
                    f"{carrier_idx + 1} expected '-', got "
                    f"{excerpt(origin_desc)!r}"
                )

    has_mismatch = any(
        e.startswith("verify_mismatch") or e.startswith("save row")
        or e.startswith("delete step")
        for e in entry["errors"]
    )
    if not has_mismatch:
        entry["status"] = "moved"
    else:
        entry["status"] = "failed"

    return entry


# ── Orchestration ───────────────────────────────────────────────────────────
def run(args) -> int:
    creds_file = Path(args.creds_file) if args.creds_file else DEFAULT_CREDS_FILE
    resume_input = Path(args.input) if args.input else DEFAULT_RESUME_INPUT

    if not resume_input.exists():
        print(f"ERROR: input manifest not found: {resume_input}")
        return 1

    all_records = json.loads(resume_input.read_text(encoding="utf-8"))
    print(f"Loaded {len(all_records)} target records from {resume_input.name}")

    if args.resume_from:
        print(f"Resuming from index {args.resume_from}")
        all_records = all_records[args.resume_from:]

    if args.limit:
        print(f"Limit: first {args.limit} records")
        all_records = all_records[: args.limit]

    total = len(all_records)
    if total == 0:
        print("Nothing to process.")
        return 0

    # Load + verify creds before opening the log file so we don't leave
    # an empty log behind on a pre-flight failure.
    creds = AuthCreds.load(creds_file)
    print(f"  Auth domain:   {creds.domain}")
    print(f"  Creds file:    {creds_file}")

    if not args.skip_verify:
        ok, msg = verify_auth(creds)
        if not ok:
            print(f"  Pre-flight FAILED: {msg}", file=sys.stderr)
            print(file=sys.stderr)
            print(REFRESH_INSTRUCTIONS, file=sys.stderr)
            return 2
        print(f"  Pre-flight OK: {msg}")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"pp_expected_to_last_{ts}.json"

    inter_call_ms = max(0, args.inter_call_ms)
    args.inter_call_seconds = inter_call_ms / 1000.0

    print("=" * 70)
    print("  PHASE A POLISH - MOVE EXPECTED RESULT TO LAST STEP (urllib)")
    print(f"  target project:   {TARGET_PROJECT}  (Partner Admin)")
    print(f"  records:          {total}")
    print(f"  rate-ms:          {args.rate_ms} (inter-case)")
    print(f"  inter-call:       {inter_call_ms}ms")
    print(f"  dry-run:          {args.dry_run}")
    print(f"  log:              {log_path.relative_to(ROOT)}")
    print("=" * 70)

    rate_seconds = max(0.0, args.rate_ms / 1000.0)
    log_entries: list[dict] = []
    counters = {
        "moved": 0,
        "already_at_last": 0,
        "no_expected_to_move": 0,
        "failed": 0,
        "dry_run": 0,
    }

    auth_died: AuthDied | None = None
    auth_died_at_idx = 0  # 1-based index within this run (post-slice)

    for idx, rec in enumerate(all_records, 1):
        try:
            entry = process_one(creds, rec, args)
        except AuthDied as exc:
            entry = {
                "source_key": rec.get("source_key", ""),
                "target_key": rec.get("target_key", ""),
                "target_module": rec.get("target_module_name", "?"),
                "source_title": rec.get("source_title", ""),
                "status": "failed",
                "original_position": None,
                "real_expected_excerpt": "",
                "errors": [str(exc)],
            }
            log_entries.append(entry)
            counters["failed"] += 1
            atomic_write_log(log_path, log_entries)
            auth_died = exc
            auth_died_at_idx = idx
            break

        log_entries.append(entry)
        counters[entry["status"]] = counters.get(entry["status"], 0) + 1

        title_short = (entry.get("source_title") or "")[:50]
        pos_str = (
            f" pos={entry['original_position']}"
            if entry.get("original_position") else ""
        )
        err_str = (
            f" errs={len(entry['errors'])}"
            if entry["errors"] and entry["status"] != "dry_run"
            else ""
        )
        print(
            f"  [{idx}/{total}] {entry['target_module']}: "
            f"{title_short} -> {entry['status']}{pos_str}{err_str}"
        )

        atomic_write_log(log_path, log_entries)

        if idx % 25 == 0 or idx == total:
            print(
                f"    --- rollup @ {idx}/{total}: "
                f"moved={counters['moved']} "
                f"already_at_last={counters['already_at_last']} "
                f"no_expected_to_move={counters['no_expected_to_move']} "
                f"failed={counters['failed']} "
                f"dry_run={counters['dry_run']}"
            )

        if idx < total:
            time.sleep(rate_seconds)

    if auth_died is not None:
        manifest_idx_1based = (args.resume_from or 0) + auth_died_at_idx
        resume_from_hint = manifest_idx_1based - 1
        print()
        print("!" * 70)
        print(f"!  AUTH DIED at case {manifest_idx_1based} ({auth_died})")
        print("!  The QA Touch session was invalidated mid-run.")
        print("!  Refresh creds via: python tools/qatouch_api_mode_update.py test")
        print(f"!  Then resume with: --resume-from {resume_from_hint}")
        print("!" * 70)

    # ── Summary ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  PHASE A POLISH - SUMMARY")
    print(f"  Total processed:       {total}")
    print(f"  Moved:                 {counters['moved']}")
    print(f"  Already at last:       {counters['already_at_last']}")
    print(f"  No expected to move:   {counters['no_expected_to_move']}")
    print(f"  Failed:                {counters['failed']}")
    print(f"  Dry-run:               {counters['dry_run']}")
    print(f"  Log written to:        {log_path.relative_to(ROOT)}")
    print("=" * 70)

    return 0 if counters["failed"] == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Phase A polish - move each PP target's real 'Expected Result' "
            "from whichever step carries it (typically step 1) to the LAST "
            "step, stamping '-' on the original location. (urllib build.)"
        )
    )
    ap.add_argument(
        "--input", default=str(DEFAULT_RESUME_INPUT),
        help=(
            "Input JSON manifest of target records "
            f"(default: {DEFAULT_RESUME_INPUT.name})"
        ),
    )
    ap.add_argument(
        "--limit", type=int, default=0,
        help="Process only the first N records (probe / canary mode).",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Print plan per case; no writes.",
    )
    ap.add_argument(
        "--resume-from", type=int, default=0,
        help="Skip the first N records of the input list.",
    )
    ap.add_argument(
        "--auth-state-file", default=str(DEFAULT_AUTH_STATE),
        help=(
            "IGNORED in the urllib build; kept for CLI compatibility with "
            "old runbooks. Auth is read from --creds-file instead."
        ),
    )
    ap.add_argument(
        "--creds-file", default=str(DEFAULT_CREDS_FILE),
        help=(
            "QA Touch creds JSON (xsrf_token + cookie_header + domain) "
            f"written by qatouch_api_mode_update.py test "
            f"(default: {DEFAULT_CREDS_FILE.name})."
        ),
    )
    ap.add_argument(
        "--rate-ms", type=int, default=1300,
        help="Milliseconds between cases (default 1300).",
    )
    ap.add_argument(
        "--inter-call-ms", type=int, default=int(INTER_CALL_DELAY * 1000),
        help=(
            f"Milliseconds between internal API calls within a case "
            f"(default {int(INTER_CALL_DELAY * 1000)})."
        ),
    )
    ap.add_argument(
        "--skip-verify", action="store_true",
        help="Skip the pre-flight GET /v2 auth check (not recommended).",
    )
    args = ap.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
