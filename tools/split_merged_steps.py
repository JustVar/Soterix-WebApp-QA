#!/usr/bin/env python3
"""Split merged single-row caseStep blobs into per-row steps in QA Touch.

Consumes a manifest produced by tools/detect_merged_steps.py and, for each
case classified as "merged", deletes the single merged row and replaces it
with N rows - where N is the count of "Step N:" prefixes in the merged
body. Intermediate rows get expected_result = "-" (validator-accepted
DASH_FALLBACK); the LAST row gets the case-level expected (sourced from
caseStep[0].description, with fall-throughs to top-level expectedResult /
expectedStep / "-").

Endpoints
---------
  POST /v1/case/edit/p/{projectKey}/cid/{caseKey}    re-fetch for idempotency
  GET  /v1/steps/delete/mid/{stepId}?type=true       delete merged row
  POST /v1/steps/save                                 create per-step row
       body: {cid, pid, step_description, expected_result}
       both fields pre-wrapped <p>{escape_for_html(text)}</p>
       (matches qa_post_import_split_and_position.py:388-390)

Wire shape and round-trip exactly mirror the canonical splitter at
tools/qa_post_import_split_and_position.py. The detection-side regex and
threshold mirror tools/detect_merged_steps.py:134-135 so semantics never
drift between detect and split.

Auth model
----------
Same as tools/run_partner_admin_backfill.py: read cookie+XSRF from
tools/.qatouch_creds.json (refresh via `python tools/qatouch_api_mode_update.py test`)
and confirm with a lightweight GET /v2 ahead of any mutation.

Idempotency (4 layers - see CLI --help for full rationale)
-----------------------------------------------------------
  L1  Re-fetch /v1/case/edit on every case (manifest may be stale).
  L2  Re-run the merged-detection signature (>= 3 markers AND rows == 1).
  L3  Classify: rows == 0 -> skip empty; rows > 1 -> skip already_split;
      rows == 1 without merged signature -> skip not_merged_anymore.
  L4  After save, re-fetch and verify caseStep.length == N. Probe the
      LAST row's expected_result - if it's already real (non-empty AND
      not "-") on a row > 1 case, the case is genuinely finalised and
      we never re-split (mirrors splitter line 411-421).

Input options (mutually exclusive)
----------------------------------
  --manifest PATH                Manifest JSON from detect_merged_steps.py.
                                  Default: newest matching
                                  logs/merged_steps_manifest_{project_key}_*.json
  --case-keys CSV-LIST           Override manifest, process only these keys.
                                  Bypasses module filter.
  --module-key CSV-LIST          Manifest filter: only cases whose
                                  module_key is in this set.

Other CLI
---------
  --project-key 70l1             QA Touch project (default 70l1).
  --limit N                      Process at most N merged cases.
  --dry-run                      Re-fetch + parse + classify, no mutations.
  --resume-from N                Skip the first N merged cases (1-based).
  --creds-file PATH              .qatouch_creds.json path.
  --rate-ms 1300                 Per-case pacing (between cases).
  --inter-step-ms 400            Per-step pacing within a case.
  --log-dir PATH                 Per-run log JSON dir (default repo/logs).
  --skip-verify                  Skip the GET /v2 pre-flight (not recommended).

Exit codes
----------
  0  all cases succeeded or were skipped/dry-run
  1  one or more cases failed (or interrupted mid-run)
  2  fatal pre-flight (auth stale, manifest missing, etc.)
"""
from __future__ import annotations

import argparse
import functools
import html as html_mod
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

# Always flush - long runs on Windows consoles benefit.
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

# Canonical merged-step signature - same regex shape and threshold as the
# detect tool at tools/detect_merged_steps.py:134-135 and the canonical
# splitter at tools/qa_post_import_split_and_position.py:146.
STEP_PREFIX_RE = re.compile(r"(?im)^\s*Step\s*\d+\s*[:\.\)]\s*")
# Numbered-list style (`1.` / `2)` / `3:`) used by camera-firmware /
# spec-document authoring in 60W5 (Camera 2 Cloud). The dual-style match
# was added 2026-06-29 after the REST baseline audit flagged 117 of
# 60W5's 118 cases as merged-in-this-style - see memory note
# qa-touch-merged-steps-baseline.md and detect_merged_steps_rest.py
# for the matching detection logic.
NUMBERED_PREFIX_RE = re.compile(r"(?m)^\s*\d+\s*[\.\):]\s+")
MERGED_THRESHOLD = 3

# Validator-accepted fallback for empty expected_result. The server-side
# validator rejects empty with "Please Enter Expected Result"; a single
# dash passes (probed 2026-06-25). Matches DASH_FALLBACK in
# tools/migrate_pp_cases_phase_a_steps.py:175.
DASH_FALLBACK = "-"

# Treat any HTTP 429 with this many seconds pause then a single retry.
RATE_LIMIT_PAUSE = 20.0

REFRESH_INSTRUCTIONS = (
    "QA Touch internal-auth appears stale (verify GET returned 401/403).\n"
    "Refresh it with:\n"
    "    python tools/qatouch_api_mode_update.py test\n"
    "That drives a logged-in browser, refreshes tools/.qatouch_auth_state.json,\n"
    "and rewrites tools/.qatouch_creds.json. Then re-run this script."
)


# ---------------------------------------------------------------------------
# Auth + HTTP plumbing (lifted from tools/run_partner_admin_backfill.py)
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


def _http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 30,
) -> tuple[int, bytes]:
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
        return 0, f"URLError: {getattr(e, 'reason', e)}".encode("utf-8")


def internal_post(
    creds: AuthCreds, path: str, json_body: dict[str, Any]
) -> tuple[int, dict | str]:
    url = f"https://{creds.domain}{path}"
    body = json.dumps(json_body).encode("utf-8")
    status, raw = _http_request(
        "POST", url, headers=_common_headers(creds), body=body
    )
    text = raw.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, text


def internal_get(creds: AuthCreds, path: str) -> tuple[int, dict | str]:
    url = f"https://{creds.domain}{path}"
    # /v1/steps/delete is a GET; headers same shape minus Content-Type body.
    headers = _common_headers(creds)
    status, raw = _http_request("GET", url, headers=headers)
    text = raw.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, text


# ---------------------------------------------------------------------------
# Pre-flight: verify the cookie/XSRF still authenticate against /v2
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
    status, raw = _http_request("GET", url, headers=headers)
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
# Parse / classify (mirrors detect_merged_steps for invariant semantics)
# ---------------------------------------------------------------------------
def html_to_text(html: str | None) -> str:
    """Tags -> \\n, NBSP -> space. Identical to detect_merged_steps.html_to_text
    so detection and split share the SAME source-of-truth text."""
    return re.sub(r"<[^>]+>", "\n", html or "").replace("\xa0", " ")


def escape_for_html(text: str) -> str:
    """Round-trip unescape -> escape(quote=False).

    Mirrors qa_post_import_split_and_position.escape_for_html (lines 189-202).
    The converter pre-escaped < and > when writing the CSV; on save we need
    a clean &lt;/&gt; on the wire so the rich-text editor renders the
    original "<" character instead of the literal "&lt;".
    """
    plain = html_mod.unescape(text or "")
    return html_mod.escape(plain, quote=False)


def _pick_dominant_prefix_re(text: str) -> re.Pattern:
    """Pick the prefix regex that has more matches in the merged body.

    Two authoring styles produce merged-step bodies in the wild:
      - canonical "Step N: ..." (our own pipeline + most legacy imports)
      - plain numbered list "1. ..." / "2) ..." (camera-firmware /
        spec-document authoring in 60W5)

    Falls back to STEP_PREFIX_RE when both miss (callers handle the
    empty result; a body that hits neither is not actually merged).
    """
    step_n = len(STEP_PREFIX_RE.findall(text))
    num_n = len(NUMBERED_PREFIX_RE.findall(text))
    if num_n > step_n:
        return NUMBERED_PREFIX_RE
    return STEP_PREFIX_RE


def _split_merged_body(text: str, prefix_re: re.Pattern) -> list[str]:
    """Split a merged body on prefix_re; strip leftover numbering; drop empties.

    Used for both the steps body and the expected_result body so the two
    are parsed symmetrically - if the import had per-step expecteds
    embedded in the description field with the same prefix style, this
    extracts them with the same logic that extracts step text.
    """
    if not text:
        return []
    parts = prefix_re.split(text)
    items = [p.strip() for p in parts if p and p.strip()]
    items = [re.sub(r"^\d+\s*[\.\):-]\s*", "", s) for s in items]
    return [s for s in items if s]


def parse_merged_step(case_step_row: dict) -> tuple[list[tuple[str, str]], int]:
    """Return (pairs, marker_count) where pairs is the per-row plan.

    - Reads caseStep[0].step (the merged blob, possibly HTML).
    - html_to_text -> pick dominant prefix regex (Step-N or numbered-
      list - see _pick_dominant_prefix_re) -> split -> drop leading/
      empty parts.
    - Defensive strip of leftover "N. " / "N) " numbering from older
      converter runs (mirrors splitter line 148).
    - case-level expected = caseStep[0].description, the field where the
      QA Touch importer parked the source XLSX "Expected_result" cell
      (verified empirically 2026-06-25 on QGWKKm/WED66N).
    - Tries to split the expected body the same way (per-step
      expecteds embedded in description). If the split count matches
      the step count, those per-step expecteds are used 1:1. Otherwise
      falls back to the canonical "single assertion on last step,
      intermediates get '-' DASH_FALLBACK" behavior.

    `marker_count` is the count from the steps' dominant regex - same
    number the detector tools report. Threshold check happens at the
    call site.
    """
    raw_body = case_step_row.get("step") or ""
    raw_expected = case_step_row.get("description") or ""

    text = html_to_text(raw_body)
    prefix_re = _pick_dominant_prefix_re(text)
    steps = _split_merged_body(text, prefix_re)
    marker_count = len(prefix_re.findall(text))

    if not steps:
        return [], marker_count

    # Try to split the expected body symmetrically. If the resulting
    # count matches the step count, the case had per-step expecteds
    # baked into the description (legacy QA Touch importer behavior on
    # cases authored with one Expected per step in the source XLSX).
    expected_text = html_to_text(raw_expected).strip()
    if expected_text:
        exp_prefix_re = _pick_dominant_prefix_re(expected_text)
        expected_parts = _split_merged_body(expected_text, exp_prefix_re)
    else:
        expected_parts = []

    if expected_parts and len(expected_parts) == len(steps):
        # Per-step expecteds detected - pair them 1:1. Each one that is
        # empty/dash falls back to DASH_FALLBACK to keep the validator happy.
        expecteds = [
            e if e and e != "-" else DASH_FALLBACK
            for e in expected_parts
        ]
    else:
        # Single-on-last (the canonical "last step is the assertion"
        # behavior). Treat the whole expected text as the assertion.
        last_exp = expected_text if expected_text and expected_text != "-" else DASH_FALLBACK
        expecteds = ["-"] * (len(steps) - 1) + [last_exp]

    return list(zip(steps, expecteds)), marker_count


def case_step_signature(case_steps: list[dict]) -> tuple[int, int]:
    """Return (rows, marker_count). marker_count is 0 unless rows == 1.

    Uses the dominant of the two prefix regexes (Step-N vs numbered-
    list) so the signature matches what the detector tools report.
    """
    rows = len(case_steps)
    if rows != 1:
        return rows, 0
    body = case_steps[0].get("step") or ""
    text = html_to_text(body)
    prefix_re = _pick_dominant_prefix_re(text)
    return rows, len(prefix_re.findall(text))


def is_finalised(case_steps: list[dict]) -> bool:
    """Idempotency probe (mirrors splitter lines 411-421).

    A case with rows > 1 whose LAST row has a real (non-dash, non-empty)
    expected_result is genuinely finalised - never re-split.
    """
    if len(case_steps) <= 1:
        return False
    last = case_steps[-1]
    exp = (last.get("expected_result") or last.get("expectedResult") or "").strip()
    # html_to_text in case the row carries <p>...</p> wrap.
    text = html_to_text(exp).strip()
    return bool(text) and text != "-"


# ---------------------------------------------------------------------------
# Endpoint helpers
# ---------------------------------------------------------------------------
def fetch_case_edit(
    creds: AuthCreds, project_key: str, case_key: str
) -> tuple[int, dict | None, str | None]:
    """POST /v1/case/edit -> (status, data_dict, error_msg)."""
    path = f"/v1/case/edit/p/{project_key}/cid/{case_key}"
    status, body = internal_post(creds, path, {})
    if status == 429:
        print(f"  HTTP 429 on /v1/case/edit cid={case_key} - sleeping {RATE_LIMIT_PAUSE}s, retrying once")
        time.sleep(RATE_LIMIT_PAUSE)
        status, body = internal_post(creds, path, {})
    if status in (401, 403):
        return status, None, f"stale internal auth (HTTP {status})"
    if status != 200 or not isinstance(body, dict):
        return status, None, f"unexpected response (HTTP {status})"
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(data, dict):
        return status, None, "response body missing 'data' dict"
    return status, data, None


def delete_step(
    creds: AuthCreds, step_id: str
) -> tuple[int, str]:
    """GET /v1/steps/delete/mid/{step_id}?type=true."""
    path = f"/v1/steps/delete/mid/{step_id}?type=true"
    status, body = internal_get(creds, path)
    if status == 429:
        print(f"  HTTP 429 on /v1/steps/delete mid={step_id} - sleeping {RATE_LIMIT_PAUSE}s, retrying once")
        time.sleep(RATE_LIMIT_PAUSE)
        status, body = internal_get(creds, path)
    msg = ""
    if isinstance(body, dict):
        msg = str(body.get("msg") or body.get("message") or "")[:200]
    elif isinstance(body, str):
        msg = body[:200]
    return status, msg


def save_step(
    creds: AuthCreds,
    project_key: str,
    case_key: str,
    step_description: str,
    expected_result: str,
) -> tuple[int, str]:
    """POST /v1/steps/save with the proven body shape.

    Both fields pre-wrapped in <p>...</p> with escape_for_html round-trip
    applied (matches qa_post_import_split_and_position.create_step:386-390).
    /v1/steps/save does NOT exhibit the /v1/case/update 500-on-success
    quirk - treat any non-200 as a real failure.
    """
    safe_desc = escape_for_html(step_description)
    safe_exp = escape_for_html(expected_result)
    payload = {
        "cid": case_key,
        "pid": project_key,
        "step_description": f"<p>{safe_desc}</p>",
        "expected_result": f"<p>{safe_exp}</p>",
    }
    status, body = internal_post(creds, "/v1/steps/save", payload)
    if status == 429:
        print(f"  HTTP 429 on /v1/steps/save cid={case_key} - sleeping {RATE_LIMIT_PAUSE}s, retrying once")
        time.sleep(RATE_LIMIT_PAUSE)
        status, body = internal_post(creds, "/v1/steps/save", payload)
    msg = ""
    if isinstance(body, dict):
        msg = str(body.get("msg") or body.get("message") or "")[:200]
    elif isinstance(body, str):
        msg = body[:200]
    return status, msg


# ---------------------------------------------------------------------------
# Manifest discovery + record set selection
# ---------------------------------------------------------------------------
def newest_manifest(project_key: str, log_dir: Path) -> Path | None:
    pattern = f"merged_steps_manifest_{project_key}_*.json"
    candidates = sorted(log_dir.glob(pattern))
    return candidates[-1] if candidates else None


def load_manifest(path: Path) -> dict:
    if not path.exists():
        print(f"Manifest not found: {path}", file=sys.stderr)
        raise SystemExit(2)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"Manifest not valid JSON: {e}", file=sys.stderr)
        raise SystemExit(2)


# ---------------------------------------------------------------------------
# Streaming JSON log (atomic per-record rewrite - matches Partner Admin pattern)
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
    src = ap.add_mutually_exclusive_group()
    src.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help=(
            "detect_merged_steps.py manifest JSON. Default: newest matching "
            "logs/merged_steps_manifest_{project_key}_*.json"
        ),
    )
    src.add_argument(
        "--case-keys",
        default="",
        help=(
            "Comma-separated case_keys to process. Bypasses manifest entirely "
            "(useful for surgical re-runs). Module filter ignored when set."
        ),
    )
    ap.add_argument(
        "--module-key",
        default="",
        help=(
            "Comma-separated module_key filter applied to the manifest "
            "(only manifest entries whose module_key is in this set are processed)."
        ),
    )
    ap.add_argument(
        "--project-key",
        default="70l1",
        help="QA Touch project key (default: 70l1).",
    )
    ap.add_argument("--limit", type=int, default=0,
                    help="Process at most N merged cases after --resume-from (0 = all).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Re-fetch + parse + classify only. No delete/save calls.")
    ap.add_argument("--resume-from", type=int, default=0,
                    help="Skip the first N merged cases (1-based).")
    ap.add_argument("--creds-file", type=Path, default=DEFAULT_CREDS_FILE,
                    help=f"Auth creds JSON (default: {DEFAULT_CREDS_FILE}).")
    ap.add_argument("--rate-ms", type=int, default=1300,
                    help="Per-case pacing in milliseconds (default: 1300).")
    ap.add_argument("--inter-step-ms", type=int, default=400,
                    help="Per-step pacing within a case in milliseconds (default: 400).")
    ap.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR,
                    help=f"Per-run log directory (default: {DEFAULT_LOG_DIR}).")
    ap.add_argument("--skip-verify", action="store_true",
                    help="Skip the pre-flight GET /v2 auth check (not recommended).")
    args = ap.parse_args()

    project_key = args.project_key
    module_filter: set[str] | None = None
    if args.module_key.strip():
        module_filter = {m.strip() for m in args.module_key.split(",") if m.strip()}

    # --- Pre-flight: resolve the manifest / override set
    override_keys: list[str] = []
    if args.case_keys.strip():
        override_keys = [k.strip() for k in args.case_keys.split(",") if k.strip()]

    manifest_path: Path | None = None
    manifest_records: list[dict] = []

    if override_keys:
        # Synthesize records from --case-keys; manifest fields will be filled
        # by the L1 re-fetch (case_code/title sourced from /v1/case/edit if needed).
        for k in override_keys:
            manifest_records.append({
                "case_key":    k,
                "case_code":   "",
                "case_title":  "",
                "module_key":  "",
                "module_name": "",
                "classification": "merged",  # honoured pending L1+L2 re-check
            })
    else:
        manifest_path = args.manifest or newest_manifest(project_key, args.log_dir)
        if manifest_path is None:
            print(
                f"No --manifest given and no merged_steps_manifest_{project_key}_*.json "
                f"found in {args.log_dir}.",
                file=sys.stderr,
            )
            print(
                "  Run detect_merged_steps.py first, or pass --manifest / --case-keys.",
                file=sys.stderr,
            )
            return 2
        manifest = load_manifest(manifest_path)
        all_records = manifest.get("records") or []
        for r in all_records:
            if r.get("classification") != "merged":
                continue
            if module_filter is not None and r.get("module_key") not in module_filter:
                continue
            manifest_records.append(r)

    if not manifest_records:
        print(
            "  Nothing to process. Manifest contained no 'merged' records matching "
            "the filters, or --case-keys was empty.",
            file=sys.stderr,
        )
        return 0

    # --- Pre-flight: auth
    creds = AuthCreds.load(args.creds_file)
    print(f"  Project key:    {project_key}")
    if override_keys:
        print(f"  Source:         --case-keys ({len(override_keys)} keys)")
    else:
        print(f"  Manifest:       {manifest_path}")
        print(f"  Module filter:  {sorted(module_filter) if module_filter else 'ALL'}")
    print(f"  Merged cases:   {len(manifest_records)}")
    print(f"  Auth domain:    {creds.domain}")
    print(f"  Creds file:     {args.creds_file}")
    print(f"  Dry run:        {args.dry_run}")
    print(f"  Rate ms:        {args.rate_ms}")
    print(f"  Inter-step ms:  {args.inter_step_ms}")
    print(f"  Resume from:    {args.resume_from}")
    print(f"  Limit:          {args.limit if args.limit > 0 else 'all'}")

    if not args.skip_verify:
        ok, msg = verify_auth(creds)
        if not ok:
            print(f"  Pre-flight FAILED: {msg}", file=sys.stderr)
            print(file=sys.stderr)
            print(REFRESH_INSTRUCTIONS, file=sys.stderr)
            return 2
        print(f"  Pre-flight OK:  {msg}")

    # --- Slice
    start_idx = max(0, args.resume_from)
    sliced = manifest_records[start_idx:]
    if args.limit > 0:
        sliced = sliced[: args.limit]
    if not sliced:
        print("  Nothing to process after applying --resume-from / --limit.")
        return 0

    # --- Open the run log
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = args.log_dir / f"split_merged_steps_{ts}.json"
    summary: dict[str, Any] = {
        "total_merged":         len(manifest_records),
        "to_process":           len(sliced),
        "skipped_resume_from":  start_idx,
        "split":                0,
        "already_split_skipped": 0,
        "not_merged_anymore":   0,
        "empty_skipped":        0,
        "parse_failed":         0,
        "parse_ambiguous":      0,
        "verify_mismatch":      0,
        "failed":               0,
        "dry_run":              0,
    }
    header = {
        "started_at":   datetime.now().isoformat(timespec="seconds"),
        "project_key":  project_key,
        "manifest":     str(manifest_path) if manifest_path else None,
        "case_keys":    override_keys or None,
        "module_keys":  sorted(module_filter) if module_filter else None,
        "creds_file":   str(args.creds_file),
        "dry_run":      args.dry_run,
        "rate_ms":      args.rate_ms,
        "inter_step_ms": args.inter_step_ms,
        "resume_from":  args.resume_from,
        "limit":        args.limit,
        "skip_verify":  args.skip_verify,
        "summary":      summary,
    }
    runlog = RunLog(log_path, header)
    print(f"  Log file:       {log_path}")
    print()

    # Pre-log skipped entries so the log mirrors the full set.
    for i in range(start_idx):
        r = manifest_records[i]
        runlog.append({
            "i":            i + 1,
            "case_key":     r.get("case_key"),
            "case_code":    r.get("case_code"),
            "case_title":   r.get("case_title"),
            "module_key":   r.get("module_key"),
            "module_name":  r.get("module_name"),
            "classification": "skipped",
            "original_step_count":   None,
            "original_marker_count": None,
            "new_step_count":        None,
            "errors": ["skipped via --resume-from"],
        })

    n_total = len(manifest_records)
    interrupted = False
    last_logged_i = start_idx

    try:
        for offset, r in enumerate(sliced):
            i = start_idx + offset + 1
            case_key   = r.get("case_key") or ""
            case_code  = r.get("case_code") or ""
            case_title = r.get("case_title") or ""
            module_key = r.get("module_key") or ""
            module_name = r.get("module_name") or ""

            rec: dict[str, Any] = {
                "i":            i,
                "case_key":     case_key,
                "case_code":    case_code,
                "case_title":   case_title,
                "module_key":   module_key,
                "module_name":  module_name,
                "classification": None,
                "original_step_count":   None,
                "original_marker_count": None,
                "new_step_count":        None,
                "errors": [],
            }

            if not case_key:
                rec["classification"] = "failed"
                rec["errors"].append("manifest record missing case_key")
                summary["failed"] += 1
                runlog.append(rec)
                last_logged_i = i
                print(f"  [{i}/{n_total}] {module_name}: {(case_title or '?')[:50]} -> FAIL (no case_key)")
                time.sleep(args.rate_ms / 1000.0)
                continue

            # --- L1: re-fetch (manifest may be stale)
            fetch_status, data, err = fetch_case_edit(creds, project_key, case_key)
            if fetch_status in (401, 403):
                print(f"  [{i}/{n_total}] {module_name}: HTTP {fetch_status} on /v1/case/edit - internal auth stale. Aborting.",
                      file=sys.stderr)
                print(file=sys.stderr)
                print(REFRESH_INSTRUCTIONS, file=sys.stderr)
                print(f"  After refresh, resume with: --resume-from {last_logged_i}",
                      file=sys.stderr)
                rec["classification"] = "failed"
                rec["errors"].append(err or f"HTTP {fetch_status}")
                summary["failed"] += 1
                runlog.append(rec)
                runlog.update_header(
                    ended_at=datetime.now().isoformat(timespec="seconds"),
                    interrupted=True,
                    abort_reason=f"stale internal auth (HTTP {fetch_status})",
                    summary=summary,
                )
                return 2

            if err is not None or data is None:
                rec["classification"] = "failed"
                rec["errors"].append(err or f"HTTP {fetch_status}")
                summary["failed"] += 1
                runlog.append(rec)
                last_logged_i = i
                print(f"  [{i}/{n_total}] {module_name}: {(case_title or case_key)[:50]} -> FAIL ({err})")
                time.sleep(args.rate_ms / 1000.0)
                continue

            # Fill in any blanks on override-mode records from the fetched data.
            if not case_code:
                case_code = data.get("caseCode") or data.get("case_code") or ""
                rec["case_code"] = case_code
            if not case_title:
                case_title = data.get("caseTitle") or data.get("case_title") or ""
                rec["case_title"] = case_title
            if not module_name:
                module_name = data.get("moduleName") or data.get("module_name") or ""
                rec["module_name"] = module_name

            case_steps = data.get("caseStep") or data.get("case_steps") or []
            if not isinstance(case_steps, list):
                case_steps = []
            rows, marker_count = case_step_signature(case_steps)
            rec["original_step_count"] = rows
            rec["original_marker_count"] = marker_count

            # --- L3: classify and route
            if rows == 0:
                rec["classification"] = "empty_skipped"
                summary["empty_skipped"] += 1
                runlog.append(rec)
                last_logged_i = i
                print(f"  [{i}/{n_total}] {module_name}: {(case_title or case_key)[:50]} -> EMPTY (skip)")
                time.sleep(args.rate_ms / 1000.0)
                continue

            if rows > 1:
                # Either someone hand-edited since detection or a prior run
                # of this tool finished. Probe the LAST row to confirm.
                if is_finalised(case_steps):
                    rec["classification"] = "already_split_skipped"
                    summary["already_split_skipped"] += 1
                    msg_tag = "ALREADY_SPLIT"
                else:
                    rec["classification"] = "already_split_skipped"
                    rec["errors"].append("rows > 1 but last row expected is empty/dash - manual review")
                    summary["already_split_skipped"] += 1
                    msg_tag = "ALREADY_SPLIT (no real last-expected)"
                runlog.append(rec)
                last_logged_i = i
                print(f"  [{i}/{n_total}] {module_name}: {(case_title or case_key)[:50]} -> {msg_tag} (rows={rows})")
                time.sleep(args.rate_ms / 1000.0)
                continue

            if marker_count < MERGED_THRESHOLD:
                rec["classification"] = "not_merged_anymore"
                summary["not_merged_anymore"] += 1
                runlog.append(rec)
                last_logged_i = i
                print(f"  [{i}/{n_total}] {module_name}: {(case_title or case_key)[:50]} -> NOT_MERGED_ANYMORE (markers={marker_count})")
                time.sleep(args.rate_ms / 1000.0)
                continue

            # --- L2 done implicitly above (rows==1 AND markers>=3). Parse.
            merged_row = case_steps[0]
            step_id = merged_row.get("id") or merged_row.get("step_id") or ""
            pairs, _markers = parse_merged_step(merged_row)
            n_new = len(pairs)
            rec["new_step_count"] = n_new

            # Defensive: parse_failed / parse_ambiguous
            if n_new == 0:
                rec["classification"] = "parse_failed"
                rec["errors"].append("regex split yielded 0 non-empty parts despite markers>=3")
                summary["parse_failed"] += 1
                runlog.append(rec)
                last_logged_i = i
                print(f"  [{i}/{n_total}] {module_name}: {(case_title or case_key)[:50]} -> PARSE_FAILED (markers={marker_count})")
                time.sleep(args.rate_ms / 1000.0)
                continue
            if n_new == 1:
                rec["classification"] = "parse_ambiguous"
                rec["errors"].append("regex split yielded 1 part despite markers>=3 - inline reference?")
                summary["parse_ambiguous"] += 1
                runlog.append(rec)
                last_logged_i = i
                print(f"  [{i}/{n_total}] {module_name}: {(case_title or case_key)[:50]} -> PARSE_AMBIGUOUS (markers={marker_count})")
                time.sleep(args.rate_ms / 1000.0)
                continue

            # --- Dry-run short-circuit
            if args.dry_run:
                rec["classification"] = "dry_run"
                summary["dry_run"] += 1
                runlog.append(rec)
                last_logged_i = i
                print(f"  [{i}/{n_total}] {module_name}: {(case_title or case_key)[:50]} -> DRY_RUN ({marker_count} markers -> {n_new} steps)")
                time.sleep(args.rate_ms / 1000.0)
                continue

            # --- Mutate: delete merged row, then save N rows
            if not step_id:
                rec["classification"] = "failed"
                rec["errors"].append("merged caseStep[0] missing id; cannot delete safely")
                summary["failed"] += 1
                runlog.append(rec)
                last_logged_i = i
                print(f"  [{i}/{n_total}] {module_name}: {(case_title or case_key)[:50]} -> FAIL (no step id)")
                time.sleep(args.rate_ms / 1000.0)
                continue

            del_status, del_msg = delete_step(creds, str(step_id))
            if del_status in (401, 403):
                print(f"  [{i}/{n_total}] {module_name}: HTTP {del_status} on /v1/steps/delete - internal auth stale. Aborting.",
                      file=sys.stderr)
                print(file=sys.stderr)
                print(REFRESH_INSTRUCTIONS, file=sys.stderr)
                print(f"  After refresh, resume with: --resume-from {last_logged_i}",
                      file=sys.stderr)
                rec["classification"] = "failed"
                rec["errors"].append(f"delete HTTP {del_status}: {del_msg}")
                summary["failed"] += 1
                runlog.append(rec)
                runlog.update_header(
                    ended_at=datetime.now().isoformat(timespec="seconds"),
                    interrupted=True,
                    abort_reason=f"stale internal auth (HTTP {del_status})",
                    summary=summary,
                )
                return 2
            if del_status != 200:
                rec["classification"] = "failed"
                rec["errors"].append(f"delete HTTP {del_status}: {del_msg}")
                summary["failed"] += 1
                runlog.append(rec)
                last_logged_i = i
                print(f"  [{i}/{n_total}] {module_name}: {(case_title or case_key)[:50]} -> FAIL delete (HTTP {del_status})")
                time.sleep(args.rate_ms / 1000.0)
                continue

            time.sleep(args.inter_step_ms / 1000.0)

            # Save N rows in source order (server assigns position by insertion).
            save_failed = False
            for sidx, (step_desc, exp) in enumerate(pairs):
                s_status, s_msg = save_step(
                    creds, project_key, case_key, step_desc, exp
                )
                if s_status in (401, 403):
                    print(f"  [{i}/{n_total}] {module_name}: HTTP {s_status} on /v1/steps/save - internal auth stale. Aborting.",
                          file=sys.stderr)
                    print(file=sys.stderr)
                    print(REFRESH_INSTRUCTIONS, file=sys.stderr)
                    print(f"  After refresh, resume with: --resume-from {last_logged_i}",
                          file=sys.stderr)
                    rec["classification"] = "failed"
                    rec["errors"].append(f"save row {sidx+1}/{n_new} HTTP {s_status}: {s_msg}")
                    summary["failed"] += 1
                    runlog.append(rec)
                    runlog.update_header(
                        ended_at=datetime.now().isoformat(timespec="seconds"),
                        interrupted=True,
                        abort_reason=f"stale internal auth (HTTP {s_status})",
                        summary=summary,
                    )
                    return 2
                if s_status != 200:
                    rec["errors"].append(f"save row {sidx+1}/{n_new} HTTP {s_status}: {s_msg}")
                    save_failed = True
                    break
                if sidx < n_new - 1:
                    time.sleep(args.inter_step_ms / 1000.0)

            if save_failed:
                rec["classification"] = "failed"
                summary["failed"] += 1
                runlog.append(rec)
                last_logged_i = i
                print(f"  [{i}/{n_total}] {module_name}: {(case_title or case_key)[:50]} -> FAIL save (partial)")
                time.sleep(args.rate_ms / 1000.0)
                continue

            # --- L4: post-split verification
            time.sleep(0.5)
            v_status, v_data, v_err = fetch_case_edit(creds, project_key, case_key)
            if v_err is not None or v_data is None:
                rec["classification"] = "verify_mismatch"
                rec["errors"].append(f"verify fetch failed: {v_err or 'HTTP ' + str(v_status)}")
                summary["verify_mismatch"] += 1
                runlog.append(rec)
                last_logged_i = i
                print(f"  [{i}/{n_total}] {module_name}: {(case_title or case_key)[:50]} -> VERIFY_FETCH_FAIL")
                time.sleep(args.rate_ms / 1000.0)
                continue

            v_steps = v_data.get("caseStep") or v_data.get("case_steps") or []
            v_rows = len(v_steps) if isinstance(v_steps, list) else 0
            if v_rows != n_new:
                rec["classification"] = "verify_mismatch"
                rec["errors"].append(f"expected {n_new} rows after save, got {v_rows}")
                summary["verify_mismatch"] += 1
                runlog.append(rec)
                last_logged_i = i
                print(f"  [{i}/{n_total}] {module_name}: {(case_title or case_key)[:50]} -> VERIFY_MISMATCH ({n_new}->{v_rows})")
                time.sleep(args.rate_ms / 1000.0)
                continue

            # All checks passed.
            rec["classification"] = "split"
            summary["split"] += 1
            runlog.append(rec)
            last_logged_i = i
            print(f"  [{i}/{n_total}] {module_name}: {(case_title or case_key)[:50]} -> SPLIT ({marker_count} markers -> {n_new} steps)")

            # Periodic rollup every 25 cases.
            if (offset + 1) % 25 == 0:
                print(
                    f"  ---- progress: [{i}/{n_total}] "
                    f"split={summary['split']} skipped={summary['already_split_skipped']+summary['not_merged_anymore']+summary['empty_skipped']} "
                    f"parse_fail={summary['parse_failed']+summary['parse_ambiguous']} "
                    f"verify_mismatch={summary['verify_mismatch']} fail={summary['failed']} "
                    f"dry={summary['dry_run']}"
                )

            time.sleep(args.rate_ms / 1000.0)
    except KeyboardInterrupt:
        interrupted = True
        print()
        print(f"  Interrupted by user. Progress preserved at: {log_path}")
        print(f"  Resume with: --resume-from {last_logged_i}")

    runlog.update_header(
        ended_at=datetime.now().isoformat(timespec="seconds"),
        interrupted=interrupted,
        summary=summary,
    )

    # --- Final summary
    print()
    print("=" * 64)
    print("  SPLIT MERGED STEPS SUMMARY")
    print("=" * 64)
    print(f"  Total merged:           {summary['total_merged']}")
    print(f"  Processed:              {summary['to_process']}")
    print(f"  Skipped (resume-from):  {summary['skipped_resume_from']}")
    print(f"  Split:                  {summary['split']}")
    print(f"  Already-split skipped:  {summary['already_split_skipped']}")
    print(f"  Not merged anymore:     {summary['not_merged_anymore']}")
    print(f"  Empty skipped:          {summary['empty_skipped']}")
    print(f"  Parse failed:           {summary['parse_failed']}")
    print(f"  Parse ambiguous:        {summary['parse_ambiguous']}")
    print(f"  Verify mismatch:        {summary['verify_mismatch']}")
    print(f"  Failed:                 {summary['failed']}")
    print(f"  Dry run:                {summary['dry_run']}")
    print(f"  Log:                    {log_path}")
    print("=" * 64)

    failures = (
        summary["failed"]
        + summary["verify_mismatch"]
        + summary["parse_failed"]
        + summary["parse_ambiguous"]
    )
    return 1 if (failures > 0 or interrupted) else 0


if __name__ == "__main__":
    sys.exit(main())
