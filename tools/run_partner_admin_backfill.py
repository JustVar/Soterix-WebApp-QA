#!/usr/bin/env python3
"""Run the Partner Admin metadata backfill against QA Touch.

Consumes a prebuilt payloads JSON (one entry per case, with caseKey + resolved
enc_ids for type/priority/tags + reference/description/precondition/test_data
already in place) and replays the proven /v1/case/edit -> /v1/case/update
sequence for each case.

Designed for the 422-row Partner Admin set built by
    tools/build_partner_admin_backfill.py
which lands in:
    tools/.partner_admin_backfill.json

Auth model
----------
This script never opens a browser. It reads cookie/XSRF auth from the small
creds JSON written by tools/qa_touch_auth_helper.py:

    {
      "xsrf_token":    "<decoded XSRF-TOKEN cookie value>",
      "cookie_header": "name=value; name=value; ...",
      "domain":        "soterixsystems.qatouch.com"
    }

Refresh auth state (when /v2 returns 401/403, or a redirect to /login is hit):

    python tools/qatouch_api_mode_update.py test

That command drives a logged-in browser, refreshes the storage state at
tools/.qatouch_auth_state.json, then writes a fresh tools/.qatouch_creds.json.

Endpoints used
--------------
  POST /v1/case/edit/p/{projectKey}/cid/{caseKey}    fetch current edit body
  POST /v1/case/update/p/{projectKey}/cid/{caseKey}  write merged update

Response envelope: nested under "data" (with a top-level fallback).

Result classification (matches backfill_qa_touch_metadata.classify_response):
  ok            : HTTP 200, body.status truthy
  ok_500_quirk  : HTTP 500 with msg "Server Error" - vendor quirk, data IS saved,
                  the 500 fires on a post-save side effect (notification / index)
  failed        : HTTP 200 with body.status=false, or any other non-success shape
  fetch_failed  : /v1/case/edit did not return 200 with a dict body
  dry_run       : --dry-run was set; payload was built and logged, no POST sent
  skipped       : --resume-from skipped this index

Per-case forbidden fields stripped before the update POST:
    caseStep, steps, stepsArray
Leaving caseStep on the wire is a HARD 500 (no save) that ALSO overwrites the
step rows with garbage - keep these popped.

Example end-to-end run
----------------------
    # 1. Refresh creds if needed (writes tools/.qatouch_creds.json)
    python tools/qatouch_api_mode_update.py test

    # 2. Dry-run first 5 cases to sanity-check the resolved enc_ids
    python tools/run_partner_admin_backfill.py --dry-run --limit 5

    # 3. Full run (422 cases, ~9.5 min at the default 1300 ms pace)
    python tools/run_partner_admin_backfill.py

    # 4. If a crash interrupted at index K, resume from there:
    python tools/run_partner_admin_backfill.py --resume-from K

Exit codes
----------
  0  all payloads succeeded (counting ok_500_quirk as success) or were skipped
  1  one or more payloads failed/fetch_failed after the run completed
  2  fatal pre-flight error (auth missing, payloads missing, verify GET 401/403)
"""
from __future__ import annotations

import argparse
import functools
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

# Always flush - long runs in CI / Windows consoles benefit
_print = print
print = functools.partial(_print, flush=True)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO / "tools"
DEFAULT_PAYLOADS_FILE = TOOLS_DIR / ".partner_admin_backfill.json"
DEFAULT_CREDS_FILE = TOOLS_DIR / ".qatouch_creds.json"
DEFAULT_LOG_DIR = REPO / "logs"

# Fields previously believed to trigger a HARD 500 if sent on update.
# CORRECTION (2026-06-24, observed during Partner Admin backfill): the server
# actually REQUIRES `caseStep` to be present - stripping it produces
# HTTP 422 {"errors":{"caseStep":["Please add some steps in Test Case"]}}.
# The working pattern (verified by qatouch_api_mode_update.py:cmd_test which
# echoes the full edit-form body, including caseStep, and gets 200 OK with
# "Case Updated Successfully") is: pass caseStep through unchanged. The
# original "strip caseStep" rule in backfill_qa_touch_metadata.py was never
# validated by an on-disk log - left empty here.
FORBIDDEN_UPDATE_FIELDS: tuple[str, ...] = ()

# Fields server-side requires to be present (default to [] if not on current
# edit-form body). Mirrors backfill_qa_touch_metadata.build_update_payload.
REQUIRED_ARRAY_FIELDS = (
    "checkedRequirements",
    "gitlabcheckedRequirements",
    "detailArray",
)

# Fields the payload JSON carries that are debug-only - never sent on update.
DEBUG_PAYLOAD_FIELDS = ("_csv_ref", "_csv_module", "caseCode", "caseTitle")

# The user-overlay fields we copy from the payload JSON onto the fetched
# current-edit-form state.
OVERLAY_FIELDS = (
    "reference",
    "description",
    "precondition",
    "test_data",
    "type",
    "priority",
    "mode",
    "newtags",
)

REFRESH_INSTRUCTIONS = (
    "QA Touch auth appears stale (verify GET returned 401/403).\n"
    "Refresh it with:\n"
    "    python tools/qatouch_api_mode_update.py test\n"
    "That drives a logged-in browser, refreshes tools/.qatouch_auth_state.json,\n"
    "and rewrites tools/.qatouch_creds.json. Then re-run this script."
)


# ---------------------------------------------------------------------------
# Auth + HTTP plumbing (same shape as backfill_qa_touch_metadata.py)
# ---------------------------------------------------------------------------
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
    """Plain urllib request that swallows HTTPError (we want the body for 500s)."""
    req = urllib.request.Request(url, method=method, data=body, headers=headers or {})
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
        # Surface network-layer failures as HTTP 0 with the reason in the body.
        return 0, f"URLError: {getattr(e, 'reason', e)}".encode("utf-8")


def internal_post(
    creds: AuthCreds, path: str, json_body: dict[str, Any]
) -> tuple[int, dict | str]:
    """POST to QA Touch internal endpoint using XSRF + Cookie auth.

    Returns (status_code, parsed_body_or_raw_text).
    """
    url = f"https://{creds.domain}{path}"
    body = json.dumps(json_body).encode("utf-8")
    status, raw = http_request("POST", url, headers=_common_headers(creds), body=body)
    text = raw.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, text


# ---------------------------------------------------------------------------
# Pre-flight: verify the cookie/XSRF still authenticate against /v2
# ---------------------------------------------------------------------------
def verify_auth(creds: AuthCreds) -> tuple[bool, str]:
    """Hit GET https://{domain}/v2 once. Return (ok, message).

    Treats 401/403 as the canonical "stale auth" signal - caller should print
    REFRESH_INSTRUCTIONS and exit 2. Other 4xx (except a hard 404) is a soft
    warning; 200/2xx/3xx is a pass. 404 on /v2 is NOT an auth signal (matches
    qa_touch_auth_helper.py behavior).
    """
    url = f"https://{creds.domain}/v2"
    # /v2 is the SPA shell (HTML) - use the same lightweight header shape
    # qa_touch_auth_helper.py uses, NOT the JSON-content-type internal-POST
    # shape. Sending Accept: application/json + Content-Type here causes
    # the server to return 401 even when cookies are valid.
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
        # Soft warning, not fatal - cookies often still work for /v1/case/*
        return True, (
            f"verify GET /v2 returned HTTP {status} - non-fatal, "
            "cookies may still work for /v1/case/* endpoints"
        )
    return True, f"verify GET /v2 returned HTTP {status}"


# ---------------------------------------------------------------------------
# Case-level operations
# ---------------------------------------------------------------------------
def fetch_case_edit_form(
    creds: AuthCreds, project_key: str, case_key: str
) -> tuple[int, dict | None]:
    """Fetch the current edit-form payload for a case.

    Endpoint: POST /v1/case/edit/p/{projectKey}/cid/{caseKey}
    Returns (status, data_dict_or_None). Unwraps body["data"] when present.
    """
    status, body = internal_post(
        creds, f"/v1/case/edit/p/{project_key}/cid/{case_key}", {}
    )
    if status != 200 or not isinstance(body, dict):
        return status, None
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    return status, data if isinstance(data, dict) else None


def post_case_update(
    creds: AuthCreds, project_key: str, case_key: str, payload: dict
) -> tuple[int, dict | str]:
    """POST the merged update body."""
    return internal_post(
        creds, f"/v1/case/update/p/{project_key}/cid/{case_key}", payload
    )


# ---------------------------------------------------------------------------
# Payload merge
# ---------------------------------------------------------------------------
def build_update_body(current: dict, overlay: dict) -> dict:
    """Deep-copy current edit-form state, strip forbidden fields, overlay deltas.

    Mirrors backfill_qa_touch_metadata.build_update_payload but uses the
    prebuilt overlay (already resolved to enc_ids by build_partner_admin_backfill).
    """
    # Deep-copy via JSON round-trip - never mutate the cached current state.
    body = json.loads(json.dumps(current))

    # Drop step-related fields (server 500s AND corrupts step rows otherwise).
    for k in FORBIDDEN_UPDATE_FIELDS:
        body.pop(k, None)

    # Overlay the CSV-derived fields. We only write keys that are present in
    # the overlay; absent keys stay as-is on the current edit-form body.
    for field in OVERLAY_FIELDS:
        if field not in overlay:
            continue
        val = overlay[field]
        if isinstance(val, str) and val.strip() == "" and field != "mode":
            # Don't blank out free-text fields with empty strings - but mode
            # is allowed to be "" (means "leave unset").
            continue
        body[field] = val

    # Ensure server-required array fields exist even if missing on current.
    for required in REQUIRED_ARRAY_FIELDS:
        body.setdefault(required, [])

    return body


# ---------------------------------------------------------------------------
# Result classification
# ---------------------------------------------------------------------------
def classify_response(status: int, body: Any) -> tuple[str, list[str]]:
    """Classify an update response.

    Returns (status_label, errors).

    status_label values:
      - "ok"             : HTTP 200, parsed body.status truthy
      - "ok_500_quirk"   : HTTP 500 with msg "Server Error" - the documented
                           quirk where the save succeeded but a post-save side
                           effect (notification/indexing) errored
      - "failed"         : anything else
    """
    errors: list[str] = []

    if status == 200:
        if isinstance(body, dict):
            if body.get("status") in (True, "true", 1):
                return "ok", []
            msg = str(body.get("msg") or body.get("message") or "")[:200]
            errors.append(f"200 OK but body status={body.get('status')} msg={msg}")
            return "failed", errors
        errors.append("200 OK with non-JSON body")
        return "ok", errors  # defensive - most likely success

    if status == 500:
        msg = ""
        if isinstance(body, dict):
            msg = str(body.get("msg") or body.get("message") or "")
        elif isinstance(body, str):
            msg = body[:200]
        if "Server Error" in msg or msg.lower().strip() == "server error":
            return "ok_500_quirk", []
        errors.append(f"500 with unexpected msg: {msg[:200]}")
        return "failed", errors

    msg = ""
    detail = ""
    if isinstance(body, dict):
        msg = str(body.get("msg") or body.get("message") or "")[:200]
        # Laravel 422 attaches per-field validation errors under "errors"
        if isinstance(body.get("errors"), dict):
            try:
                detail = " | errors=" + json.dumps(body["errors"])[:800]
            except Exception:
                detail = " | errors=<unserializable>"
        elif not msg:
            msg = str(body)[:200]
    elif isinstance(body, str):
        msg = body[:200]
    errors.append(f"HTTP {status}: {msg}{detail}")
    return "failed", errors


# ---------------------------------------------------------------------------
# Log writer - append-flush every record so a crash mid-run loses nothing.
# ---------------------------------------------------------------------------
class RunLog:
    """Streaming JSON log. Rewrites the whole file after every record.

    The total record set for this run tops out at 422 small dicts (~120 KB
    serialized) so a full rewrite per record costs effectively nothing, and
    we get crash-resilient progress without needing JSONL or a temp file.
    """

    def __init__(self, log_path: Path, header: dict):
        self.log_path = log_path
        self.header = header
        self.records: list[dict] = []
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._flush()

    def append(self, record: dict) -> None:
        self.records.append(record)
        self._flush()

    def update_header(self, **kv: Any) -> None:
        self.header.update(kv)
        self._flush()

    def _flush(self) -> None:
        payload = {
            **self.header,
            "records": self.records,
        }
        # Atomic write via temp file + replace - never leave a half-written log.
        tmp = self.log_path.with_suffix(self.log_path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.log_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--payloads-file",
        type=Path,
        default=DEFAULT_PAYLOADS_FILE,
        help=f"Prebuilt payloads JSON (default: {DEFAULT_PAYLOADS_FILE})",
    )
    ap.add_argument(
        "--creds-file",
        type=Path,
        default=DEFAULT_CREDS_FILE,
        help=f"Auth creds JSON from qa_touch_auth_helper.py (default: {DEFAULT_CREDS_FILE})",
    )
    ap.add_argument(
        "--rate-ms",
        type=int,
        default=1300,
        help="Inter-call delay in milliseconds (default: 1300, ~0.77 req/s).",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N payloads after --resume-from (0 = all).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch + merge but do NOT POST the update.",
    )
    ap.add_argument(
        "--resume-from",
        type=int,
        default=0,
        help="Skip the first N payloads (1-based). Use after a mid-run abort.",
    )
    ap.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help=f"Per-run log JSON directory (default: {DEFAULT_LOG_DIR})",
    )
    ap.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip the pre-flight GET /v2 auth check (not recommended).",
    )
    args = ap.parse_args()

    # --- Pre-flight: payloads file
    if not args.payloads_file.exists():
        print(f"Payloads file not found: {args.payloads_file}", file=sys.stderr)
        print(
            "  Build it with: python tools/build_partner_admin_backfill.py",
            file=sys.stderr,
        )
        return 2
    try:
        payloads = json.loads(args.payloads_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Payloads file is not valid JSON: {e}", file=sys.stderr)
        return 2
    if not isinstance(payloads, list) or not payloads:
        print(
            f"Payloads file must be a non-empty JSON array. Got: "
            f"{type(payloads).__name__} (len={len(payloads) if hasattr(payloads,'__len__') else 'n/a'})",
            file=sys.stderr,
        )
        return 2

    # --- Pre-flight: creds + verify
    creds = AuthCreds.load(args.creds_file)
    print(f"  Auth domain:   {creds.domain}")
    print(f"  Payloads file: {args.payloads_file}")
    print(f"  Total cases:   {len(payloads)}")
    print(f"  Dry run:       {args.dry_run}")
    print(f"  Rate ms:       {args.rate_ms}")
    print(f"  Resume from:   {args.resume_from}")
    print(f"  Limit:         {args.limit if args.limit > 0 else 'all'}")

    if not args.skip_verify:
        ok, msg = verify_auth(creds)
        if not ok:
            print(f"  Pre-flight FAILED: {msg}", file=sys.stderr)
            print(file=sys.stderr)
            print(REFRESH_INSTRUCTIONS, file=sys.stderr)
            return 2
        print(f"  Pre-flight OK: {msg}")

    # --- Decide which slice we'll process
    start_idx = max(0, args.resume_from)  # 1-based "skip first N" => slice start
    sliced = payloads[start_idx:]
    if args.limit > 0:
        sliced = sliced[: args.limit]
    if not sliced:
        print("  Nothing to process after applying --resume-from / --limit.")
        return 0

    # --- Open the streaming log
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = args.log_dir / f"backfill_partner_admin_{ts}.json"
    summary = {
        "total_payloads": len(payloads),
        "to_process": len(sliced),
        "ok": 0,
        "ok_500_quirk": 0,
        "failed": 0,
        "fetch_failed": 0,
        "dry_run": 0,
        "skipped": start_idx,
    }
    header = {
        "started_at":      datetime.now().isoformat(timespec="seconds"),
        "payloads_file":   str(args.payloads_file),
        "creds_file":      str(args.creds_file),
        "dry_run":         args.dry_run,
        "rate_ms":         args.rate_ms,
        "resume_from":     args.resume_from,
        "limit":           args.limit,
        "skip_verify":     args.skip_verify,
        "total_payloads":  len(payloads),
        "to_process":      len(sliced),
        "summary":         summary,
    }
    runlog = RunLog(log_path, header)
    print(f"  Log file:      {log_path}")
    print()

    # --- Record skipped entries up front so the log reflects the full set
    for i in range(start_idx):
        p = payloads[i]
        runlog.append({
            "i":           i + 1,
            "ref":         p.get("_csv_ref"),
            "projectKey":  p.get("projectKey"),
            "caseKey":     p.get("caseKey"),
            "status":      "skipped",
            "http_status": None,
            "errors":      ["skipped via --resume-from"],
        })

    # --- Main loop
    n_total = len(sliced)
    last_ref = ""
    try:
        for offset, payload in enumerate(sliced):
            i = start_idx + offset + 1  # 1-based index into the FULL payloads list
            ref = payload.get("_csv_ref") or ""
            project_key = payload.get("projectKey")
            case_key = payload.get("caseKey")
            last_ref = ref

            rec: dict[str, Any] = {
                "i":           i,
                "ref":         ref,
                "projectKey":  project_key,
                "caseKey":     case_key,
                "status":      None,
                "http_status": None,
                "errors":      [],
            }

            if not project_key or not case_key:
                rec["status"] = "failed"
                rec["errors"].append("payload missing projectKey or caseKey")
                summary["failed"] += 1
                runlog.append(rec)
                print(f"  [{i}/{summary['total_payloads']}] {ref or '?'} -> FAIL "
                      "(missing projectKey/caseKey)")
                # Still pace ourselves so we don't burst on bad data
                time.sleep(args.rate_ms / 1000.0)
                continue

            # 1. Fetch current edit-form state
            fetch_status, current = fetch_case_edit_form(creds, project_key, case_key)
            if fetch_status != 200 or current is None:
                rec["status"] = "fetch_failed"
                rec["http_status"] = fetch_status
                rec["errors"].append(f"edit-form fetch HTTP {fetch_status}")
                summary["fetch_failed"] += 1
                runlog.append(rec)
                print(f"  [{i}/{summary['total_payloads']}] {ref or case_key} "
                      f"-> FETCH_FAILED ({fetch_status})")
                time.sleep(args.rate_ms / 1000.0)
                continue

            # 2. Build merged body (overlay from payload)
            overlay = {k: payload[k] for k in OVERLAY_FIELDS if k in payload}
            body = build_update_body(current, overlay)

            # 3. Dry-run short-circuit
            if args.dry_run:
                rec["status"] = "dry_run"
                rec["http_status"] = None
                rec["overlay_keys"] = sorted(overlay.keys())
                summary["dry_run"] += 1
                runlog.append(rec)
                print(f"  [{i}/{summary['total_payloads']}] {ref or case_key} "
                      f"-> DRY_RUN type={body.get('type')} "
                      f"priority={body.get('priority')} mode={body.get('mode')} "
                      f"tags={body.get('newtags')}")
                time.sleep(args.rate_ms / 1000.0)
                continue

            # 4. POST update
            post_status, post_body = post_case_update(creds, project_key, case_key, body)
            label, errs = classify_response(post_status, post_body)
            rec["status"] = label
            rec["http_status"] = post_status
            rec["errors"].extend(errs)

            if label == "ok":
                summary["ok"] += 1
                marker = "OK"
            elif label == "ok_500_quirk":
                summary["ok_500_quirk"] += 1
                marker = "OK*"
            else:
                summary["failed"] += 1
                marker = "FAIL"

            runlog.append(rec)
            print(f"  [{i}/{summary['total_payloads']}] {ref or case_key} "
                  f"-> {marker} (HTTP {post_status})")

            # 5. Periodic progress summary (every 25 cases, by absolute index)
            if (offset + 1) % 25 == 0:
                print(
                    f"  ---- progress: [{i}/{summary['total_payloads']}] "
                    f"ok={summary['ok']} 500q={summary['ok_500_quirk']} "
                    f"fail={summary['failed']} fetch_fail={summary['fetch_failed']} "
                    f"(last ref: {last_ref})"
                )

            time.sleep(args.rate_ms / 1000.0)
    except KeyboardInterrupt:
        print()
        print(f"  Interrupted by user. Progress was flushed to: {log_path}")
        # `i` is the 1-based index of the case that was being processed when
        # Ctrl-C arrived. Resume by skipping the cases up to and including the
        # last fully-recorded one - which is i-1 if the current case never got
        # a recorded outcome, or i if it did. Append-flush guarantees that
        # every case in runlog.records is durably written, so the safe resume
        # point is "skip the first N already-logged non-skipped processed cases."
        last_logged_i = (
            runlog.records[-1]["i"] if runlog.records else start_idx
        )
        print(f"  Resume with: --resume-from {last_logged_i}")
        runlog.update_header(
            ended_at=datetime.now().isoformat(timespec="seconds"),
            interrupted=True,
            summary=summary,
        )
        return 1

    runlog.update_header(
        ended_at=datetime.now().isoformat(timespec="seconds"),
        interrupted=False,
        summary=summary,
    )

    # --- Final summary
    print()
    print("=" * 64)
    print("  PARTNER ADMIN BACKFILL SUMMARY")
    print("=" * 64)
    print(f"  Total payloads:   {summary['total_payloads']}")
    print(f"  Processed:        {summary['to_process']}")
    print(f"  Skipped:          {summary['skipped']}")
    print(f"  OK:               {summary['ok']}")
    print(f"  OK (500 quirk):   {summary['ok_500_quirk']}")
    print(f"  Failed:           {summary['failed']}")
    print(f"  Fetch failed:     {summary['fetch_failed']}")
    print(f"  Dry run:          {summary['dry_run']}")
    print(f"  Log:              {log_path}")
    print("=" * 64)

    failures = summary["failed"] + summary["fetch_failed"]
    return 1 if failures > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
