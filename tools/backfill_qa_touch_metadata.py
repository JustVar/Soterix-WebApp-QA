#!/usr/bin/env python3
"""Reusable QA Touch metadata backfill via the internal /v1/case/update endpoint.

Generalizes the OTA backfill pattern (build_ota_update_payloads_v2.py +
qatouch_api_mode_update.py) so it works for ANY project + module + case set:

  - Reads a canonical CSV (one row per test case)
  - Matches CSV rows to live QA Touch cases by Test Case Title (paginated
    public /getAllTestCases endpoint)
  - Fetches each case's current edit-form state via the internal
    POST /v1/case/edit/p/{projectKey}/cid/{caseKey} endpoint
  - Merges desired metadata fields onto the current state, preserving
    `caseStep` from the edit-form body (the server REJECTS the update with
    HTTP 422 {"errors":{"caseStep":["Please add some steps in Test Case"]}}
    if it is missing - verified on the Partner Admin backfill 2026-06-24,
    421 cases, 420 OK + 1 known-empty-steps failure)
  - POSTs the merged body to POST /v1/case/update/p/{projectKey}/cid/{caseKey}
  - Tolerates the documented 500 quirk: when the response is HTTP 500 with
    msg="Server Error", the data WAS saved (the server errors on a post-save
    side effect) - that case is recorded as SUCCESS.

Auth model:
  This script never opens a browser. It consumes the small credentials JSON
  written by tools/qa_touch_auth_helper.py:

      {
        "xsrf_token":    "<decoded XSRF-TOKEN cookie value>",
        "cookie_header": "name=value; name=value; ...",
        "domain":        "soterixsystems.qatouch.com"
      }

  Refresh the auth state with:
      python tools/qa_touch_auth_helper.py --verify

CSV columns (canonical - produced by tools/xlsx_to_csv stream):
  - Test Case Title    (required - used to match the live case)
  - Module_name        (informational; logged for context)
  - Reference          (informational - recorded as source_ref in the log)
  - Type               (enum: Functional/Negative/Security/Performance/...)
  - Priority           (enum: Critical/High/Medium/Low)
  - Mode               (enum: Manual/Automation/empty)
  - Tags               (pipe-delimited: smoke|sanity|regression|future)
  - Description        (optional plain text - sent as `description`)
  - Precondition       (optional plain text - sent as `precondition`)
  - Test Data          (optional plain text - sent as `test_data`)

  Columns NOT updated by this script:
  - Steps / Expected_result (separate flow - see build_ota_update_payloads_v2.py
    + qatouch_browser sync-steps; this script preserves the existing caseStep
    from the edit-form body and overlays metadata only, so step content is left
    untouched. Cases that already have empty caseStep at fetch time will fail
    update with HTTP 422 - those need the step flow first.)

Enum mappings (Type/Priority/Tag are encrypted IDs unique per project):
  Encrypted IDs are auto-fetched from /v1/add/case/meta/p/{projectKey} once at
  start. CSV values that don't appear in the QA Touch enum are mapped to the
  closest fit (Negative -> Functional, Security -> Other) and the mapping is
  printed up-front so reviewers can adjust the CSV if needed.

CLI:

    python tools/backfill_qa_touch_metadata.py \\
        --project-key JlW1 \\
        --csv tests/data/c2c_ota_test_cases.csv \\
        --auth-state-file tools/.qatouch_creds.json \\
        [--dry-run] \\
        [--rate-ms 1300] \\
        [--title-column "Test Case Title"] \\
        [--limit 0] \\
        [--log-dir logs]

Output:
  logs/backfill_{project_key}_{YYYYMMDD-HHMMSS}.json - one record per CSV row:
      {
        "source_ref":      "C2C_OTA_001",
        "title":           "OTA - ...",
        "target_case_key": "abc123" | null,
        "status":          "ok" | "ok_500_quirk" | "dry_run"
                            | "unmatched" | "failed" | "fetch_failed",
        "http_status":     200 | 500 | 401 | ...,
        "errors":          [ "..." ]
      }

Exit codes:
  0  all CSV rows either succeeded or were dry-run / OK-via-500-quirk
  1  one or more rows failed (after summary is printed)
  2  fatal precondition error (auth missing, CSV missing, meta fetch failed)
"""
from __future__ import annotations

import argparse
import csv
import functools
import json
import os
import re
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

REPO = Path(__file__).resolve().parent.parent
DEFAULT_AUTH_FILE = REPO / "tools" / ".qatouch_creds.json"
DEFAULT_LOG_DIR = REPO / "logs"
DEFAULT_TITLE_COL = "Test Case Title"

# ---------------------------------------------------------------------------
# Public REST API (api.qatouch.com) - used ONLY to enumerate live cases by
# title. Read credentials are taken from the same API config that
# build_ota_update_payloads_v2.py uses, since title->case_key resolution does
# not depend on the user's browser session.
# ---------------------------------------------------------------------------
REST_BASE = "https://api.qatouch.com/api/v1"

# ---------------------------------------------------------------------------
# Internal API (the QA Touch SPA's own backend, same origin as the UI).
# Requires XSRF-TOKEN header + matching session cookie.
# ---------------------------------------------------------------------------
def internal_base(domain: str) -> str:
    return f"https://{domain}"


# ---------------------------------------------------------------------------
# Enum-name -> encrypted-id mapping (built dynamically per project)
# ---------------------------------------------------------------------------
# Fallback for CSV Type values that aren't in QA Touch's enum. Mirrors the
# decisions made in build_ota_update_payloads_v2.py.
TYPE_NAME_FALLBACK = {
    "Negative": "Functional",  # negative tests ARE functional
    "Security": "Other",       # closest fit
}

# Acceptable Mode values (the UI uses lowercase strings, not enc_ids).
MODE_NORMALIZE = {
    "manual": "manual",
    "automation": "automation",
    "automated": "automation",
    "": "",
}


# ---------------------------------------------------------------------------
# Auth + HTTP plumbing
# ---------------------------------------------------------------------------
class AuthCreds:
    def __init__(self, xsrf_token: str, cookie_header: str, domain: str):
        self.xsrf_token = xsrf_token
        self.cookie_header = cookie_header
        self.domain = domain

    @classmethod
    def load(cls, path: Path) -> AuthCreds:
        if not path.exists():
            raise SystemExit(
                f"Auth creds file not found: {path}\n"
                "Generate it with:\n"
                "    python tools/qa_touch_auth_helper.py --verify"
            )
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("xsrf_token", "cookie_header", "domain"):
            if not data.get(key):
                raise SystemExit(f"Auth creds file missing required field: {key}")
        return cls(data["xsrf_token"], data["cookie_header"], data["domain"])


def load_rest_token() -> tuple[str, str] | None:
    """Best-effort load of the public REST api-token + domain from the environment.

    Returns (api_token, domain_short) or None if not configured. The domain
    is the short form (e.g. "soterixsystems"), not the full host.
    """
    token = os.environ.get("QATOUCH_API_TOKEN") or os.environ.get("QATOUCH_API_KEY")
    domain = os.environ.get("QATOUCH_DOMAIN")
    if not token or not domain:
        return None
    return token, domain


def http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 30,
) -> tuple[int, bytes, dict[str, str]]:
    """Plain urllib request that swallows HTTPError (we want the body for 500s).

    Returns (status_code, body_bytes, response_headers_dict).
    """
    req = urllib.request.Request(url, method=method, data=body, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read(), dict(r.headers.items())
    except urllib.error.HTTPError as e:
        body_bytes = b""
        try:
            body_bytes = e.read()
        except Exception:
            pass
        return e.code, body_bytes, dict(e.headers.items()) if e.headers else {}


def internal_post(
    creds: AuthCreds, path: str, json_body: dict[str, Any]
) -> tuple[int, dict | str]:
    """POST to QA Touch internal endpoint using XSRF + Cookie auth.

    Returns (status_code, parsed_body_or_raw_text).
    """
    url = f"{internal_base(creds.domain)}{path}"
    body = json.dumps(json_body).encode("utf-8")
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json",
        "X-XSRF-TOKEN": creds.xsrf_token,
        "Cookie": creds.cookie_header,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Origin": internal_base(creds.domain),
        "Referer": f"{internal_base(creds.domain)}/v2",
    }
    status, raw, _ = http_request("POST", url, headers=headers, body=body)
    text = raw.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, text


# ---------------------------------------------------------------------------
# Public REST helpers (case enumeration by project)
# ---------------------------------------------------------------------------
def rest_get(path: str, token: str, domain_short: str) -> dict:
    req = urllib.request.Request(
        f"{REST_BASE}/{path}",
        headers={
            "api-token": token,
            "domain": domain_short,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_all_cases(project_key: str, token: str, domain_short: str) -> list[dict]:
    """Paginate /getAllTestCases/{projectKey} until exhausted."""
    cases: list[dict] = []
    page = 1
    while page <= 200:
        try:
            r = rest_get(
                f"getAllTestCases/{project_key}?page={page}", token, domain_short
            )
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} fetching page {page}", file=sys.stderr)
            break
        data = r.get("data", []) or []
        if not data:
            break
        cases.extend(data)
        if not r.get("link", {}).get("next"):
            break
        page += 1
    return cases


# ---------------------------------------------------------------------------
# Meta endpoint - Type / Priority / Tag enc_id lookup per project
# ---------------------------------------------------------------------------
def fetch_meta(creds: AuthCreds, project_key: str) -> dict[str, dict[str, str]]:
    """Return {"type": {name: enc_id}, "priority": {...}, "tag": {...}}.

    Endpoint: POST /v1/add/case/meta/p/{projectKey}
    The QA Touch SPA hits this once to populate dropdown choices on the
    add/edit case form. Shape varies slightly across releases - we tolerate
    both `list[{name, enc_id}]` and `list[{label, value}]`.
    """
    status, body = internal_post(creds, f"/v1/add/case/meta/p/{project_key}", {})
    if status != 200 or not isinstance(body, dict):
        raise SystemExit(
            f"Failed to fetch case meta (status={status}): "
            f"{str(body)[:300]}"
        )

    data = body.get("data") if isinstance(body.get("data"), dict) else body

    def _to_map(items: Any) -> dict[str, str]:
        out: dict[str, str] = {}
        if not isinstance(items, list):
            return out
        for it in items:
            if not isinstance(it, dict):
                continue
            name = it.get("name") or it.get("label") or it.get("title")
            enc = it.get("enc_id") or it.get("value") or it.get("id")
            if name and enc is not None:
                out[str(name)] = str(enc)
        return out

    # Field names observed: caseType, casePriority, caseTags (or types/priorities/tags)
    type_map = _to_map(
        data.get("caseType") or data.get("types") or data.get("type") or []
    )
    pri_map = _to_map(
        data.get("casePriority")
        or data.get("priorities")
        or data.get("priority")
        or []
    )
    tag_map = _to_map(
        data.get("caseTags")
        or data.get("tags")
        or data.get("newtags")
        or data.get("newTags")
        or []
    )

    if not type_map or not pri_map:
        raise SystemExit(
            "Case meta response did not contain type/priority maps in a "
            "recognized shape. Inspect response:\n"
            f"{json.dumps(data, indent=2)[:1500]}"
        )

    # Normalize tag keys to lowercase - UI is case-insensitive on tag names
    tag_map_lower = {k.lower(): v for k, v in tag_map.items()}

    return {"type": type_map, "priority": pri_map, "tag": tag_map_lower}


# ---------------------------------------------------------------------------
# Case-level operations
# ---------------------------------------------------------------------------
def fetch_case_edit_form(
    creds: AuthCreds, project_key: str, case_key: str
) -> tuple[int, dict | None]:
    """Fetch the current edit-form payload for a case.

    Endpoint: POST /v1/case/edit/p/{projectKey}/cid/{caseKey}
    Returns (status, data_dict_or_None).
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
# Payload building
# ---------------------------------------------------------------------------
def parse_tag_cell(cell: str, tag_map: dict[str, str]) -> tuple[list[str], list[str]]:
    """Return (enc_ids, unknown_tag_names) for a pipe-delimited tag cell."""
    enc_ids: list[str] = []
    unknown: list[str] = []
    for raw in (cell or "").split("|"):
        t = raw.strip()
        if not t:
            continue
        enc = tag_map.get(t.lower())
        if enc:
            enc_ids.append(enc)
        else:
            unknown.append(t)
    return enc_ids, unknown


def resolve_type_enc(
    csv_type: str, type_map: dict[str, str]
) -> tuple[str | None, str | None]:
    """Resolve a CSV Type cell to an encrypted id.

    Returns (enc_id, effective_name). If no match found, returns (None, None).
    """
    if not csv_type:
        return None, None
    if csv_type in type_map:
        return type_map[csv_type], csv_type
    fallback = TYPE_NAME_FALLBACK.get(csv_type)
    if fallback and fallback in type_map:
        return type_map[fallback], fallback
    return None, None


def normalize_mode(csv_mode: str) -> str | None:
    """Return the canonical lowercase mode string, or None if blank/unknown."""
    if csv_mode is None:
        return None
    key = csv_mode.strip().lower()
    return MODE_NORMALIZE.get(key, None if key else "")


def build_update_payload(
    *,
    current: dict,
    csv_row: dict[str, str],
    type_map: dict[str, str],
    priority_map: dict[str, str],
    tag_map: dict[str, str],
) -> tuple[dict, list[str]]:
    """Merge desired CSV fields onto the current edit-form state.

    Returns (payload, warnings). PRESERVES `caseStep` from the current
    edit-form body - the QA Touch server REQUIRES it on update and returns
    HTTP 422 {"errors":{"caseStep":["Please add some steps in Test Case"]}}
    if it is missing. (Original code stripped it based on an unverified
    hypothesis; the Partner Admin backfill 2026-06-24 proved this wrong:
    stripping caseStep -> 422 on all 422 cases; preserving it -> 420 OK,
    1 known-empty-steps failure. See also qatouch_api_mode_update.py:cmd_test
    which echoes the full edit-form body including caseStep and succeeds.)

    Steps are still NOT mutated by this function - we just pass the
    server-provided caseStep through unchanged so the validator passes.
    """
    warnings: list[str] = []
    # Deep-copy via JSON round-trip so we never mutate the cached current state
    payload = json.loads(json.dumps(current))

    # --- Type
    # Accept both vendor-canonical slugs (post 2026-06-26 converter rename) and
    # the legacy friendly headers (sitedevice_canonical / distributor_canonical /
    # ldap_canonical pre-rename) so historical CSVs keep working.
    csv_type = (csv_row.get("test_type") or csv_row.get("Type") or "").strip()
    if csv_type:
        enc, effective = resolve_type_enc(csv_type, type_map)
        if enc:
            payload["type"] = enc
            if effective != csv_type:
                warnings.append(
                    f"Type '{csv_type}' mapped to '{effective}' (not in QA Touch enum)"
                )
        else:
            warnings.append(f"Type '{csv_type}' has no mapping - left unchanged")

    # --- Priority
    csv_pri = (csv_row.get("test_priority") or csv_row.get("Priority") or "").strip()
    if csv_pri:
        enc = priority_map.get(csv_pri)
        if enc:
            payload["priority"] = enc
        else:
            warnings.append(f"Priority '{csv_pri}' not in QA Touch enum - left unchanged")

    # --- Mode (lowercase string, not enc_id)
    raw_mode = csv_row.get("test_mode") if "test_mode" in csv_row else csv_row.get("Mode")
    if raw_mode is not None:
        norm = normalize_mode(raw_mode or "")
        if norm is not None:
            payload["mode"] = norm
        else:
            warnings.append(f"Mode '{raw_mode}' not recognized - left unchanged")

    # --- Tags (list of enc_ids; QA Touch field is `newtags`)
    raw_tags = csv_row.get("newtags") if "newtags" in csv_row else csv_row.get("Tags")
    if raw_tags is not None:
        enc_ids, unknown = parse_tag_cell(raw_tags or "", tag_map)
        payload["newtags"] = enc_ids
        if unknown:
            warnings.append(f"Unknown tags ignored: {unknown}")

    # --- Free-text fields (only set when CSV has a non-blank value).
    # Each tuple: (vendor_canonical_csv_col, legacy_csv_col, qa_touch_payload_field).
    # NB: the QA Touch `/v1/case/update` payload uses `description` for the
    # user-visible Description (different from the import wizard, where the
    # `description` column is silently dropped and `test_description` is the
    # user-visible slug - see docs/qa_touch_integration.md §7.A.1).
    for canonical_col, legacy_col, qt_field in (
        ("reference", "Reference", "reference"),
        ("test_description", "Description", "description"),
        ("precondition", "Precondition", "precondition"),
        ("test_data", "Test Data", "test_data"),
    ):
        val = csv_row.get(canonical_col)
        if val is None or str(val).strip() == "":
            val = csv_row.get(legacy_col)
        if val is not None and str(val).strip() != "":
            payload[qt_field] = val

    # Ensure server-required array fields exist even if not on current
    for required in (
        "checkedRequirements",
        "gitlabcheckedRequirements",
        "detailArray",
    ):
        payload.setdefault(required, [])

    return payload, warnings


# ---------------------------------------------------------------------------
# Result classification
# ---------------------------------------------------------------------------
def classify_response(status: int, body: Any) -> tuple[str, list[str]]:
    """Classify an update response.

    Returns (status_label, errors).

    status_label values:
      - "ok"             - HTTP 200, parsed body has status==true
      - "ok_500_quirk"   - HTTP 500 with msg="Server Error" (documented quirk:
                           data IS saved, server errors on post-save side effect)
      - "failed"         - anything else
    """
    errors: list[str] = []

    if status == 200:
        if isinstance(body, dict):
            if body.get("status") in (True, "true", 1):
                return "ok", []
            # 200 but logical failure
            errors.append(
                f"200 OK but body status={body.get('status')} "
                f"msg={body.get('msg', '')[:200]}"
            )
            return "failed", errors
        # Non-JSON 200 - treat as ok defensively but warn
        errors.append("200 OK with non-JSON body")
        return "ok", errors

    if status == 500:
        msg = ""
        if isinstance(body, dict):
            msg = str(body.get("msg") or body.get("message") or "")
        elif isinstance(body, str):
            msg = body[:200]
        # The documented quirk - server saved the data, then 500'd on a
        # post-save side effect (notification, indexing, etc.)
        if "Server Error" in msg or msg.lower().strip() == "server error":
            return "ok_500_quirk", []
        errors.append(f"500 with unexpected msg: {msg[:200]}")
        return "failed", errors

    # 4xx or other
    msg = ""
    if isinstance(body, dict):
        msg = str(body.get("msg") or body.get("message") or body)[:200]
    elif isinstance(body, str):
        msg = body[:200]
    errors.append(f"HTTP {status}: {msg}")
    return "failed", errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def normalize_title(s: str) -> str:
    """Trim + collapse whitespace for title matching."""
    return re.sub(r"\s+", " ", (s or "").strip())


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--project-key", required=True, help="QA Touch project key (e.g. JlW1, 70l1, 60W5)")
    ap.add_argument("--csv", required=True, type=Path, help="Canonical CSV path")
    ap.add_argument(
        "--auth-state-file",
        type=Path,
        default=DEFAULT_AUTH_FILE,
        help=f"Creds JSON from qa_touch_auth_helper.py (default: {DEFAULT_AUTH_FILE})",
    )
    ap.add_argument("--dry-run", action="store_true", help="Preview, no POSTs to update")
    ap.add_argument(
        "--rate-ms",
        type=int,
        default=1300,
        help="Inter-call delay in milliseconds (default: 1300)",
    )
    ap.add_argument(
        "--title-column",
        default=DEFAULT_TITLE_COL,
        help=f"CSV column holding the case title (default: {DEFAULT_TITLE_COL!r})",
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process at most N rows (0 = all). Useful for staged rollouts.",
    )
    ap.add_argument(
        "--log-dir",
        type=Path,
        default=DEFAULT_LOG_DIR,
        help=f"Directory for the per-run log JSON (default: {DEFAULT_LOG_DIR})",
    )
    ap.add_argument(
        "--rest-domain",
        default=None,
        help="Override short REST domain (default: QATOUCH_DOMAIN from .env)",
    )
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        return 2

    creds = AuthCreds.load(args.auth_state_file)
    print(f"  Auth domain: {creds.domain}")
    print(f"  Project:     {args.project_key}")
    print(f"  CSV:         {args.csv}")
    print(f"  Dry run:     {args.dry_run}")

    # --- Load CSV
    csv_rows = list(csv.DictReader(args.csv.open(encoding="utf-8-sig")))
    print(f"  CSV rows:    {len(csv_rows)}")
    if not csv_rows:
        print("  Nothing to do - CSV has no rows.", file=sys.stderr)
        return 0

    if args.title_column not in csv_rows[0]:
        print(
            f"  CSV missing required title column {args.title_column!r}.\n"
            f"  Available columns: {list(csv_rows[0].keys())}",
            file=sys.stderr,
        )
        return 2

    # --- Fetch live cases for the project (public REST)
    rest_creds = load_rest_token()
    if not rest_creds:
        print(
            "  Missing public REST credentials. Set QATOUCH_API_TOKEN and "
            "QATOUCH_DOMAIN in your .env at the repo root (see .env.template).",
            file=sys.stderr,
        )
        return 2
    token, domain_short = rest_creds
    # --rest-domain overrides the domain from the environment.
    if args.rest_domain:
        domain_short = args.rest_domain
    if args.rest_domain:
        domain_short = args.rest_domain

    print(f"  Fetching live cases for project {args.project_key} ...")
    live_cases = fetch_all_cases(args.project_key, token, domain_short)
    print(f"  Live cases:  {len(live_cases)}")

    title_to_case = {
        normalize_title(c.get("case_title", "")): c for c in live_cases
    }

    # --- Fetch meta (enum enc_ids)
    print("  Fetching case meta (enum enc_ids) ...")
    try:
        meta = fetch_meta(creds, args.project_key)
    except SystemExit:
        raise
    print(
        f"  Meta loaded: {len(meta['type'])} types, "
        f"{len(meta['priority'])} priorities, {len(meta['tag'])} tags"
    )
    print(f"  Types:      {sorted(meta['type'].keys())}")
    print(f"  Priorities: {sorted(meta['priority'].keys())}")
    print(f"  Tags:       {sorted(meta['tag'].keys())}")

    # --- Iterate
    log_records: list[dict] = []
    summary = {
        "total": 0,
        "ok": 0,
        "ok_500_quirk": 0,
        "failed": 0,
        "unmatched": 0,
        "fetch_failed": 0,
        "dry_run": 0,
    }

    rows_to_process = csv_rows if args.limit <= 0 else csv_rows[: args.limit]

    for i, row in enumerate(rows_to_process, 1):
        summary["total"] += 1
        # Accept both vendor-canonical and legacy title-column names so the
        # explicit `--title-column` flag stays optional for typical runs.
        title_raw = row.get(args.title_column) or row.get("title") or row.get("Test Case Title") or ""
        title = normalize_title(title_raw)
        ref = (row.get("reference") or row.get("Reference") or "").strip()
        module = (row.get("section_name") or row.get("Module_name") or "").strip()

        rec: dict[str, Any] = {
            "source_ref": ref,
            "title": title_raw,
            "module": module,
            "target_case_key": None,
            "status": None,
            "http_status": None,
            "errors": [],
        }

        live = title_to_case.get(title)
        if not live:
            summary["unmatched"] += 1
            rec["status"] = "unmatched"
            rec["errors"].append("No live case with matching Test Case Title")
            print(f"  [{i}/{len(rows_to_process)}] {ref or title[:40]} -> UNMATCHED")
            log_records.append(rec)
            continue

        case_key = live.get("case_key") or live.get("caseKey") or live.get("id")
        rec["target_case_key"] = case_key

        # --- Fetch current edit-form state
        status, current = fetch_case_edit_form(creds, args.project_key, case_key)
        if status != 200 or current is None:
            summary["fetch_failed"] += 1
            rec["status"] = "fetch_failed"
            rec["http_status"] = status
            rec["errors"].append(f"Edit-form fetch HTTP {status}")
            print(
                f"  [{i}/{len(rows_to_process)}] {ref or title[:40]} "
                f"({case_key}) -> FETCH_FAILED ({status})"
            )
            log_records.append(rec)
            time.sleep(args.rate_ms / 1000.0)
            continue

        # --- Build merged payload
        payload, warnings = build_update_payload(
            current=current,
            csv_row=row,
            type_map=meta["type"],
            priority_map=meta["priority"],
            tag_map=meta["tag"],
        )
        if warnings:
            rec["errors"].extend([f"warn: {w}" for w in warnings])

        if args.dry_run:
            summary["dry_run"] += 1
            rec["status"] = "dry_run"
            print(
                f"  [{i}/{len(rows_to_process)}] {ref or title[:40]} "
                f"({case_key}) -> DRY_RUN "
                f"type={payload.get('type')} priority={payload.get('priority')} "
                f"mode={payload.get('mode')} tags={payload.get('newtags')}"
            )
            log_records.append(rec)
            time.sleep(args.rate_ms / 1000.0)
            continue

        # --- POST update
        post_status, post_body = post_case_update(
            creds, args.project_key, case_key, payload
        )
        label, errs = classify_response(post_status, post_body)
        rec["status"] = label
        rec["http_status"] = post_status
        rec["errors"].extend(errs)

        if label == "ok":
            summary["ok"] += 1
        elif label == "ok_500_quirk":
            summary["ok_500_quirk"] += 1
        else:
            summary["failed"] += 1

        marker = {
            "ok": "OK",
            "ok_500_quirk": "OK*",
            "failed": "FAIL",
        }[label]
        print(
            f"  [{i}/{len(rows_to_process)}] {ref or title[:40]} "
            f"({case_key}) -> {marker} (HTTP {post_status})"
        )

        log_records.append(rec)
        time.sleep(args.rate_ms / 1000.0)

    # --- Write log
    args.log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = args.log_dir / f"backfill_{args.project_key}_{ts}.json"
    log_path.write_text(
        json.dumps(
            {
                "project_key": args.project_key,
                "csv": str(args.csv),
                "dry_run": args.dry_run,
                "rate_ms": args.rate_ms,
                "summary": summary,
                "records": log_records,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # --- Summary table
    print()
    print("=" * 60)
    print(f"  BACKFILL SUMMARY  (project {args.project_key})")
    print("=" * 60)
    print(f"  Total rows:        {summary['total']}")
    print(f"  OK:                {summary['ok']}")
    print(f"  OK (500 quirk):    {summary['ok_500_quirk']}")
    print(f"  Failed:            {summary['failed']}")
    print(f"  Unmatched titles:  {summary['unmatched']}")
    print(f"  Fetch failed:      {summary['fetch_failed']}")
    print(f"  Dry run:           {summary['dry_run']}")
    print(f"  Log:               {log_path}")
    print("=" * 60)

    return 1 if summary["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
