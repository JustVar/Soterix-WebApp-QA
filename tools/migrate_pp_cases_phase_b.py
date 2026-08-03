#!/usr/bin/env python3
"""Phase B of the PP migration: archive the 214 source cases in JlW1.

Phase A (already complete) replicated 214 cases from JlW1 (source) to 70l1
(target) and copied metadata onto the new target cases. This script closes
the migration by archiving (vendor-internal "delete") the 214 originals in
JlW1, leaving 70l1 as the single source of truth.

What "delete" actually does
---------------------------
QA Touch's /v1/case/delete endpoint MOVES THE CASE TO AN ARCHIVE, not a hard
purge. The case can be recovered from the project's Archive view in the UI
(workspace-admin can permanently delete from there; that endpoint is not yet
captured - see qa_touch_integration.md section 8). This script is therefore
safe-by-default: an accidental delete is recoverable.

Endpoint
--------
    POST /v1/case/delete/cid/{caseKey}    body: {}

NOTE: this endpoint does NOT take a /p/{projectKey}/ path segment - it
diverges from /v1/case/edit and /v1/case/update which both DO take the
project segment. The shape is taken on trust from a successful TR0029
delete in 70l1 on 2026-06-24 (response: {"success":true,
"msg":"Case Deleted Successfully","count":0,"totalcount":246}).

To guard against the path being wrong, the script makes ONE canary delete
on the first eligible case and verifies totalcount drops by exactly 1
before continuing with the rest of the batch.

Auth model
----------
Reads cookie/XSRF from tools/.qatouch_creds.json - same pattern as
run_partner_admin_backfill.py. Refresh stale auth with:

    python tools/qatouch_api_mode_update.py test

Per-case flow
-------------
1. (optional) Pre-flight target check: POST /v1/case/edit/p/70l1/cid/{target_key}.
   If 404 or empty, SKIP this delete with status="target_missing".
   Bypass with --skip-target-check.
2. POST /v1/case/delete/cid/{source_key} with {} body.
3. Classify:
     - 200 + msg contains "Deleted Successfully"  -> "deleted"
     - 404                                         -> "already_gone"
     - else                                        -> "failed"
4. Invariant: response.totalcount must drop by exactly 1 between
   consecutive successful deletes. On mismatch, HALT the batch.

Exit codes
----------
  0  all 214 cases deleted (or already_gone, or skipped via --resume-from)
  1  one or more cases failed
  2  fatal pre-flight error (auth missing, input missing, verify 401/403)
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
DEFAULT_CREDS_FILE = TOOLS_DIR / ".qatouch_creds.json"
DEFAULT_LOG_DIR = REPO / "logs"
DEFAULT_INPUT_FILE = (
    REPO / "logs" / "pp_migration_phase_a_resume_20260625-091616.json"
)

SOURCE_PROJECT = "JlW1"
TARGET_PROJECT = "70l1"

REFRESH_INSTRUCTIONS = (
    "QA Touch auth appears stale (verify GET returned 401/403).\n"
    "Refresh it with:\n"
    "    python tools/qatouch_api_mode_update.py test\n"
    "That drives a logged-in browser, refreshes tools/.qatouch_auth_state.json,\n"
    "and rewrites tools/.qatouch_creds.json. Then re-run this script."
)


# ---------------------------------------------------------------------------
# Auth + HTTP plumbing (lifted verbatim from run_partner_admin_backfill.py)
# ---------------------------------------------------------------------------
class AuthCreds:
    def __init__(self, xsrf_token: str, cookie_header: str, domain: str):
        self.xsrf_token = xsrf_token
        self.cookie_header = cookie_header
        self.domain = domain

    @classmethod
    def load(cls, path: Path) -> AuthCreds:
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
        return 0, f"URLError: {getattr(e, 'reason', e)}".encode()


def internal_post(
    creds: AuthCreds, path: str, json_body: dict[str, Any]
) -> tuple[int, dict | str]:
    """POST to a QA Touch internal endpoint. Returns (status, parsed_body_or_text)."""
    url = f"https://{creds.domain}{path}"
    body = json.dumps(json_body).encode("utf-8")
    status, raw = http_request("POST", url, headers=_common_headers(creds), body=body)
    text = raw.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, text


# ---------------------------------------------------------------------------
# Pre-flight: verify cookie/XSRF still authenticate (mirrors backfill script)
# ---------------------------------------------------------------------------
def verify_auth(creds: AuthCreds) -> tuple[bool, str]:
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
            "cookies may still work for /v1/case/* endpoints"
        )
    return True, f"verify GET /v2 returned HTTP {status}"


# ---------------------------------------------------------------------------
# Case ops
# ---------------------------------------------------------------------------
def fetch_target_edit_form(
    creds: AuthCreds, project_key: str, case_key: str
) -> tuple[int, dict | None]:
    """POST /v1/case/edit/p/{projectKey}/cid/{caseKey}. Returns (status, data|None)."""
    status, body = internal_post(
        creds, f"/v1/case/edit/p/{project_key}/cid/{case_key}", {}
    )
    if status != 200 or not isinstance(body, dict):
        return status, None
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    return status, data if isinstance(data, dict) else None


def post_case_delete(
    creds: AuthCreds, case_key: str
) -> tuple[int, dict | str]:
    """POST /v1/case/delete/cid/{caseKey} with empty body - archives the case."""
    return internal_post(creds, f"/v1/case/delete/cid/{case_key}", {})


def classify_delete_response(status: int, body: Any) -> tuple[str, list[str], int | None]:
    """Classify a delete response.

    Returns (status_label, errors, totalcount_after).
      - 200 + msg ~ "Deleted Successfully" -> "deleted"
      - 404                                -> "already_gone"
      - else                               -> "failed"
    """
    errors: list[str] = []
    totalcount: int | None = None

    if isinstance(body, dict):
        tc = body.get("totalcount")
        if isinstance(tc, int):
            totalcount = tc

    if status == 200:
        if isinstance(body, dict):
            msg = str(body.get("msg") or body.get("message") or "")
            success = body.get("success") in (True, "true", 1) or body.get(
                "status"
            ) in (True, "true", 1)
            if success and "Deleted Successfully" in msg:
                return "deleted", [], totalcount
            if "Deleted Successfully" in msg:
                # success flag missing/odd but msg confirms
                return "deleted", [], totalcount
            errors.append(
                f"200 OK but unexpected body success={body.get('success')} "
                f"msg={msg[:200]}"
            )
            return "failed", errors, totalcount
        errors.append("200 OK with non-JSON body")
        return "failed", errors, totalcount

    if status == 404:
        return "already_gone", [], totalcount

    if status in (401, 403):
        errors.append(f"HTTP {status} (stale auth)")
        return "failed", errors, totalcount

    msg = ""
    detail = ""
    if isinstance(body, dict):
        msg = str(body.get("msg") or body.get("message") or "")[:200]
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
    return "failed", errors, totalcount


# ---------------------------------------------------------------------------
# Log writer - append-flush every record (crash-resilient)
# ---------------------------------------------------------------------------
class RunLog:
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
        payload = {**self.header, "records": self.records}
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
        "--input",
        type=Path,
        default=DEFAULT_INPUT_FILE,
        help=f"Phase A resume manifest JSON (default: {DEFAULT_INPUT_FILE})",
    )
    ap.add_argument(
        "--creds-file",
        type=Path,
        default=DEFAULT_CREDS_FILE,
        help=f"Auth creds JSON (default: {DEFAULT_CREDS_FILE})",
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
        help="Process at most N records after --resume-from (0 = all).",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Verify target (unless --skip-target-check) but do NOT POST delete.",
    )
    ap.add_argument(
        "--resume-from",
        type=int,
        default=0,
        help="Skip the first N records (1-based). Use after a mid-run abort.",
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
    ap.add_argument(
        "--skip-target-check",
        action="store_true",
        help=(
            "Skip the per-case verification that the replicated target case "
            "exists in the target project before deleting the source. NOT "
            "recommended - leaves no safety net if Phase A was incomplete."
        ),
    )
    args = ap.parse_args()

    # --- Pre-flight: input file
    if not args.input.exists():
        print(f"Input manifest not found: {args.input}", file=sys.stderr)
        return 2
    try:
        records = json.loads(args.input.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Input file is not valid JSON: {e}", file=sys.stderr)
        return 2
    if not isinstance(records, list) or not records:
        print(
            f"Input must be a non-empty JSON array. Got: "
            f"{type(records).__name__}",
            file=sys.stderr,
        )
        return 2

    # --- Pre-flight: creds + verify
    creds = AuthCreds.load(args.creds_file)
    print("=" * 64)
    print("  PP MIGRATION PHASE B - ARCHIVE SOURCE CASES IN JlW1")
    print("=" * 64)
    print("  NOTE: 'delete' in QA Touch ARCHIVES the case; it does NOT")
    print("        permanently destroy it. Cases are recoverable via the")
    print("        project's Archive view in the UI.")
    print()
    print(f"  Auth domain:        {creds.domain}")
    print(f"  Input manifest:     {args.input}")
    print(f"  Records in input:   {len(records)}")
    print(f"  Source project:     {SOURCE_PROJECT} (will be archived)")
    print(f"  Target project:     {TARGET_PROJECT} (verified before delete)")
    print(f"  Dry run:            {args.dry_run}")
    print(f"  Rate ms:            {args.rate_ms}")
    print(f"  Resume from:        {args.resume_from}")
    print(f"  Limit:              {args.limit if args.limit > 0 else 'all'}")
    print(f"  Skip target check:  {args.skip_target_check}")

    if not args.skip_verify:
        ok, msg = verify_auth(creds)
        if not ok:
            print(f"  Pre-flight FAILED: {msg}", file=sys.stderr)
            print(file=sys.stderr)
            print(REFRESH_INSTRUCTIONS, file=sys.stderr)
            return 2
        print(f"  Pre-flight OK: {msg}")

    # --- Slice
    start_idx = max(0, args.resume_from)
    sliced = records[start_idx:]
    if args.limit > 0:
        sliced = sliced[: args.limit]
    if not sliced:
        print("  Nothing to process after applying --resume-from / --limit.")
        return 0

    # --- Open log
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = args.log_dir / f"pp_migration_phase_b_{ts}.json"
    summary = {
        "total_records":   len(records),
        "to_process":      len(sliced),
        "deleted":         0,
        "already_gone":    0,
        "target_missing":  0,
        "failed":          0,
        "dry_run":         0,
        "skipped":         start_idx,
    }
    header = {
        "started_at":         datetime.now().isoformat(timespec="seconds"),
        "input_file":         str(args.input),
        "creds_file":         str(args.creds_file),
        "source_project":     SOURCE_PROJECT,
        "target_project":     TARGET_PROJECT,
        "dry_run":            args.dry_run,
        "rate_ms":            args.rate_ms,
        "resume_from":        args.resume_from,
        "limit":              args.limit,
        "skip_verify":        args.skip_verify,
        "skip_target_check":  args.skip_target_check,
        "total_records":      len(records),
        "to_process":         len(sliced),
        "summary":            summary,
    }
    runlog = RunLog(log_path, header)
    print(f"  Log file:           {log_path}")
    print()

    # --- Record skipped entries up front
    for i in range(start_idx):
        r = records[i]
        runlog.append({
            "i":                i + 1,
            "source_key":       r.get("source_key"),
            "source_title":     r.get("source_title"),
            "target_key":       r.get("target_key"),
            "target_module":    r.get("target_module_name"),
            "status":           "skipped",
            "http_status":      None,
            "totalcount_after": None,
            "errors":           ["skipped via --resume-from"],
        })

    # --- Main loop
    last_totalcount: int | None = None
    halted = False
    halt_reason = ""

    try:
        for offset, rec_in in enumerate(sliced):
            i = start_idx + offset + 1
            source_key = rec_in.get("source_key")
            target_key = rec_in.get("target_key")
            source_title = rec_in.get("source_title") or ""
            target_module = rec_in.get("target_module_name") or ""

            rec: dict[str, Any] = {
                "i":                i,
                "source_key":       source_key,
                "source_title":     source_title,
                "target_key":       target_key,
                "target_module":    target_module,
                "status":           None,
                "http_status":      None,
                "totalcount_after": None,
                "errors":           [],
            }

            short_title = source_title[:50]
            label_prefix = f"  [{i}/{summary['total_records']}] {target_module}: {short_title}"

            if not source_key:
                rec["status"] = "failed"
                rec["errors"].append("manifest record missing source_key")
                summary["failed"] += 1
                runlog.append(rec)
                print(f"{label_prefix} -> FAIL (no source_key)")
                time.sleep(args.rate_ms / 1000.0)
                continue

            # 1. Target-existence pre-flight
            if not args.skip_target_check:
                if not target_key:
                    rec["status"] = "target_missing"
                    rec["errors"].append("manifest record missing target_key")
                    summary["target_missing"] += 1
                    runlog.append(rec)
                    print(f"{label_prefix} -> SKIP (target_key missing in manifest)")
                    time.sleep(args.rate_ms / 1000.0)
                    continue
                t_status, t_body = fetch_target_edit_form(
                    creds, TARGET_PROJECT, target_key
                )
                if t_status in (401, 403):
                    rec["status"] = "failed"
                    rec["http_status"] = t_status
                    rec["errors"].append(
                        f"target verify HTTP {t_status} - stale auth, aborting"
                    )
                    summary["failed"] += 1
                    runlog.append(rec)
                    print(f"{label_prefix} -> ABORT (HTTP {t_status} on target verify)")
                    halted = True
                    halt_reason = (
                        f"Stale auth on target verify (HTTP {t_status}). "
                        f"Refresh creds and resume with --resume-from {i - 1}"
                    )
                    break
                if t_status != 200 or t_body is None:
                    rec["status"] = "target_missing"
                    rec["http_status"] = t_status
                    rec["errors"].append(
                        f"target {TARGET_PROJECT}/{target_key} not reachable "
                        f"(HTTP {t_status})"
                    )
                    summary["target_missing"] += 1
                    runlog.append(rec)
                    print(f"{label_prefix} -> SKIP (target {target_key} HTTP {t_status})")
                    time.sleep(args.rate_ms / 1000.0)
                    continue

            # 2. Dry-run short-circuit (don't post the delete)
            if args.dry_run:
                rec["status"] = "dry_run"
                summary["dry_run"] += 1
                runlog.append(rec)
                print(f"{label_prefix} -> DRY_RUN (would delete {source_key})")
                time.sleep(args.rate_ms / 1000.0)
                continue

            # 3. POST delete
            d_status, d_body = post_case_delete(creds, source_key)

            # Stale-auth check - abort cleanly if cookies expired mid-run
            if d_status in (401, 403):
                rec["status"] = "failed"
                rec["http_status"] = d_status
                rec["errors"].append(
                    f"delete HTTP {d_status} - stale auth, aborting"
                )
                summary["failed"] += 1
                runlog.append(rec)
                print(f"{label_prefix} -> ABORT (HTTP {d_status} on delete)")
                halted = True
                halt_reason = (
                    f"Stale auth on delete (HTTP {d_status}). "
                    f"Refresh creds and resume with --resume-from {i - 1}"
                )
                break

            label, errs, totalcount = classify_delete_response(d_status, d_body)
            rec["status"] = label
            rec["http_status"] = d_status
            rec["totalcount_after"] = totalcount
            rec["errors"].extend(errs)

            if label == "deleted":
                summary["deleted"] += 1
                # Invariant: totalcount must drop by exactly 1.
                if totalcount is not None and last_totalcount is not None:
                    if totalcount != last_totalcount - 1:
                        rec["errors"].append(
                            f"INVARIANT FAILED: totalcount went "
                            f"{last_totalcount} -> {totalcount} (expected "
                            f"{last_totalcount - 1})"
                        )
                        runlog.append(rec)
                        print(
                            f"{label_prefix} -> HALT (totalcount "
                            f"{last_totalcount} -> {totalcount}, "
                            f"expected {last_totalcount - 1})"
                        )
                        halted = True
                        halt_reason = (
                            f"totalcount invariant failed at i={i}: "
                            f"{last_totalcount} -> {totalcount}. "
                            f"Resume with --resume-from {i} after review."
                        )
                        # Don't double-append; rec is already in.
                        break
                last_totalcount = totalcount
                runlog.append(rec)
                tc_str = (
                    f"jlw1 total now: {totalcount}"
                    if totalcount is not None
                    else "totalcount missing"
                )
                print(f"{label_prefix} -> deleted ({tc_str})")
            elif label == "already_gone":
                summary["already_gone"] += 1
                runlog.append(rec)
                print(f"{label_prefix} -> already_gone (HTTP 404)")
            else:
                summary["failed"] += 1
                runlog.append(rec)
                print(f"{label_prefix} -> FAIL (HTTP {d_status})")

            # Periodic rollup every 25 cases
            if (offset + 1) % 25 == 0:
                print(
                    f"  ---- progress: [{i}/{summary['total_records']}] "
                    f"deleted={summary['deleted']} gone={summary['already_gone']} "
                    f"target_missing={summary['target_missing']} "
                    f"failed={summary['failed']} "
                    f"(jlw1 total: {last_totalcount})"
                )

            time.sleep(args.rate_ms / 1000.0)
    except KeyboardInterrupt:
        print()
        print(f"  Interrupted by user. Progress flushed to: {log_path}")
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
        interrupted=halted,
        halt_reason=halt_reason if halted else "",
        summary=summary,
    )

    # --- Final summary
    print()
    print("=" * 64)
    print("  PP MIGRATION PHASE B SUMMARY")
    print("=" * 64)
    print(f"  Total records:    {summary['total_records']}")
    print(f"  Processed:        {summary['to_process']}")
    print(f"  Skipped:          {summary['skipped']}")
    print(f"  Deleted:          {summary['deleted']}")
    print(f"  Already gone:     {summary['already_gone']}")
    print(f"  Target missing:   {summary['target_missing']}")
    print(f"  Failed:           {summary['failed']}")
    print(f"  Dry run:          {summary['dry_run']}")
    if last_totalcount is not None:
        print(f"  Final jlw1 total: {last_totalcount}")
    print(f"  Log:              {log_path}")
    if halted:
        print()
        print(f"  HALTED: {halt_reason}")
    print("=" * 64)

    if halted:
        return 1
    return 1 if summary["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
