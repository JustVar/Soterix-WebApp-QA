#!/usr/bin/env python3
"""Reorganize the 175 flat LDAP cases in project JlW1 into proper sub-modules.

PROBLEM
-------
QA Touch's CSV importer collapsed every "LDAP > X" Module_name in the canonical
CSV down to the existing parent module 'LDAP' (section_key=vKv0n) instead of
auto-creating a sub-module per leaf name. Result: 175 cases sit flat under
'LDAP' with no sub-structure.

GOAL
----
1. Create the 10 canonical sub-modules under 'LDAP' (parent vKv0n).
2. For each of the 175 cases, look up its target leaf module from
   tests/data/ldap_canonical.csv (by Test Case Title) and move it by updating
   the case's sectionId via the internal /v1/case/update endpoint.

PARENT_ID RISK (READ BEFORE RUNNING)
------------------------------------
The public REST endpoint POST /api/v1/module?projectKey=...&moduleName=... is
known to create a module at root level. The PARAMETER NAME for setting a parent
module IS UNKNOWN. In prior probing, the server accepted 'parentId=vKv0n' but
silently ignored it (the module landed at root level).

This script's --probe-only mode tests four candidate param names sequentially
under a throwaway module name ('_PROBE_parent_test_<ts>'). After each create
attempt it re-lists modules and checks whether the new module appears as a
CHILD of vKv0n (by reading whatever parent indicator the API returns:
parent_id / parentId / parent_key / parent_section_key / section_parent_key).
If ANY candidate sticks, the script records the working param name and uses it
for the real run. If NONE work, the script ABORTS instead of dumping 10 new
modules at root level - a partial reorg is worse than no reorg.

Probe candidates (in order):
    parentId
    parent_id
    sectionParentKey
    parentKey

Candidates were chosen from QA Touch's mixed camelCase / snake_case API style
plus the v1 'section_parent_key' field name seen in module-list responses.

CANONICAL SUB-MODULES (10)
--------------------------
Derived from distinct Module_name leaf values in tests/data/ldap_canonical.csv
('LDAP > X' -> 'X'). The hard-coded list below is a safety net; the script
re-derives from the CSV at runtime and warns if the live set differs.

    - Attribute Mapping
    - LDAP Configuration
    - LDAP Groups Mapping
    - LDAP Navigation
    - LDAP Role Mapping
    - LDAP Settings
    - LDAP Settings Active Directory
    - LDAP User Mapping
    - LDAP Users Mapping
    - Test Authentication

ENDPOINTS
---------
Public REST (uses api-token + domain headers from the environment / .env):
    GET  /api/v1/getAllModules/{projectKey}?page=N
    POST /api/v1/module?projectKey=...&moduleName=...[&<parent-param>=vKv0n]
    GET  /api/v1/getAllTestCases/{projectKey}?page=N
        (optional &module_key=vKv0n if the server supports it; we filter client
        -side if not)

Internal (XSRF + session Cookie from tools/.qatouch_creds.json - produced by
tools/qa_touch_auth_helper.py):
    POST /v1/case/edit/p/{projectKey}/cid/{caseKey}      (read current state)
    POST /v1/case/update/p/{projectKey}/cid/{caseKey}    (write sectionId)

The /v1/case/update endpoint has the documented '500 = success' quirk
(HTTP 500 with msg='Server Error' means the data WAS saved; the server errors
on a post-save side effect). We tolerate it exactly as backfill_qa_touch_metadata.

AUTH PREREQS
------------
1. QATOUCH_API_TOKEN + QATOUCH_DOMAIN must be set in your .env at the repo root
   (same source used by migrate_pp_cases_phase_a.py).
2. tools/.qatouch_creds.json must exist and be fresh - refresh via:
       python tools/qa_touch_auth_helper.py --verify

CLI
---
    # 1) Probe the parent_id param name (no writes beyond throwaway module).
    python tools/reorganize_ldap_cases.py --probe-only

    # 2) Preview the full plan without writing anything.
    python tools/reorganize_ldap_cases.py --dry-run

    # 3) Real run (only after a successful probe).
    python tools/reorganize_ldap_cases.py --rate-ms 1000

Flags:
    --dry-run             Print plan, no module/case writes.
    --probe-only          Run parent-param probe + report; exit.
    --auth-state-file PATH  Override creds JSON (default tools/.qatouch_creds.json).
    --rate-ms N           Inter-call delay in ms (default 1000).
    --log-dir PATH        Where to write the run log (default logs/).
    --rest-domain DOMAIN  Override short REST domain (default from QATOUCH_DOMAIN).
    --skip-probe          Skip the probe step and create modules at root level
                          (DANGEROUS - only after manual confirmation).

EXIT CODES
----------
    0  All sub-modules created + all cases moved (or dry-run / probe-only OK).
    1  At least one case move failed.
    2  Fatal precondition error (auth missing, CSV missing, probe failed and
       --skip-probe not set).
"""
from __future__ import annotations

import argparse
import csv
import functools
import json
import os
import sys
import time
import urllib.error
import urllib.parse
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

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parent.parent
DEFAULT_AUTH_FILE = REPO / "tools" / ".qatouch_creds.json"
DEFAULT_LOG_DIR = REPO / "logs"
DEFAULT_CANONICAL_CSV = REPO / "tests" / "data" / "ldap_canonical.csv"

PROJECT_KEY = "JlW1"
LDAP_PARENT_SECTION_KEY = "vKv0n"

# Candidate param names to try for setting a created module's parent.
# Order matters: most-likely first.
PARENT_PARAM_CANDIDATES = [
    "parentId",
    "parent_id",
    "sectionParentKey",
    "parentKey",
]

# Hard-coded canonical sub-module leaf names (safety net; re-derived from CSV).
EXPECTED_LEAF_MODULES = {
    "Attribute Mapping",
    "LDAP Configuration",
    "LDAP Groups Mapping",
    "LDAP Navigation",
    "LDAP Role Mapping",
    "LDAP Settings",
    "LDAP Settings Active Directory",
    "LDAP User Mapping",
    "LDAP Users Mapping",
    "Test Authentication",
}

REST_BASE = "https://api.qatouch.com"


# ---------------------------------------------------------------------------
# Auth (mirrors backfill_qa_touch_metadata.AuthCreds)
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
    """Read public REST api-token + short domain from the environment / .env."""
    token = os.environ.get("QATOUCH_API_TOKEN") or os.environ.get("QATOUCH_API_KEY")
    domain = os.environ.get("QATOUCH_DOMAIN")
    if not token or not domain:
        return None
    return token, domain


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------
def http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 30,
) -> tuple[int, bytes, dict[str, str]]:
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


def rest_get(path: str, token: str, domain_short: str, max_retries: int = 4) -> dict:
    """REST GET with 429 backoff. api.qatouch.com rate-limits hard around page 35.

    On 429: sleeps 2s/4s/8s/16s and retries up to max_retries times.
    Other HTTPErrors are re-raised for caller to handle.
    """
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            f"{REST_BASE}{path}",
            headers={
                "api-token": token,
                "domain": domain_short,
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                wait = 2 ** (attempt + 1)
                print(f"  REST 429 on {path} - sleeping {wait}s then retrying "
                      f"(attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
                last_err = e
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("unreachable")


def rest_post(
    path: str, token: str, domain_short: str, body: dict | None = None
) -> tuple[int, str]:
    data = json.dumps(body or {}).encode("utf-8")
    status, raw, _ = http_request(
        "POST",
        f"{REST_BASE}{path}",
        headers={
            "api-token": token,
            "domain": domain_short,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        body=data,
    )
    return status, raw.decode("utf-8", errors="replace")


def internal_post(
    creds: AuthCreds, path: str, json_body: dict[str, Any]
) -> tuple[int, dict | str]:
    url = f"https://{creds.domain}{path}"
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
        "Origin": f"https://{creds.domain}",
        "Referer": f"https://{creds.domain}/v2",
    }
    status, raw, _ = http_request("POST", url, headers=headers, body=body)
    text = raw.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, text


# ---------------------------------------------------------------------------
# Module helpers
# ---------------------------------------------------------------------------
def list_all_modules(token: str, domain_short: str) -> list[dict]:
    all_mods: list[dict] = []
    page = 1
    while page <= 100:
        try:
            r = rest_get(
                f"/api/v1/getAllModules/{PROJECT_KEY}?page={page}", token, domain_short
            )
        except urllib.error.HTTPError as e:
            print(f"  WARN: HTTP {e.code} listing modules page {page}")
            break
        data = r.get("data", []) or []
        if not data:
            break
        all_mods.extend(data)
        if not (r.get("link") or {}).get("next"):
            break
        page += 1
    return all_mods


def module_parent_indicator(m: dict) -> str | None:
    """Extract whatever the API uses to indicate a module's parent.

    QA Touch's module-list response shape has drifted across releases; we try
    the common fields. Returns the parent identifier string, or None if the
    module is at root.
    """
    for k in (
        "parent_id",
        "parentId",
        "parent_key",
        "parentKey",
        "section_parent_key",
        "sectionParentKey",
    ):
        v = m.get(k)
        if v is not None and str(v).strip() not in ("", "0", "null", "None"):
            return str(v)
    return None


def module_key(m: dict) -> str | None:
    return m.get("section_key") or m.get("module_key") or m.get("moduleKey")


def module_name(m: dict) -> str:
    return (m.get("section_name") or m.get("module_name") or "").strip()


def find_module_by_name(modules: list[dict], target_name: str) -> dict | None:
    target_norm = target_name.strip().lower()
    for m in modules:
        if module_name(m).lower() == target_norm:
            return m
    return None


def create_module(
    name: str,
    token: str,
    domain_short: str,
    parent_param: str | None = None,
    parent_value: str | None = None,
) -> tuple[int, str]:
    qs_parts = {"projectKey": PROJECT_KEY, "moduleName": name}
    if parent_param and parent_value:
        qs_parts[parent_param] = parent_value
    qs = urllib.parse.urlencode(qs_parts)
    return rest_post(f"/api/v1/module?{qs}", token, domain_short, body={})


# ---------------------------------------------------------------------------
# Parent-param probe
# ---------------------------------------------------------------------------
def probe_parent_param(token: str, domain_short: str, dry_run: bool) -> str | None:
    """Test which (if any) parent-param name actually nests a new module.

    Returns the working param name, or None if nothing worked.

    Strategy: for each candidate, create a uniquely-named probe module with
    that param set to vKv0n, re-list modules, and inspect the new module's
    parent indicator. Stop at first hit.

    NOTE: throwaway modules are left in place - QA Touch's public REST API
    does not expose a module-delete endpoint at the time of writing. Caller
    should clean up manually via the UI after a probe run. Each probe name
    embeds a timestamp + the param-name attempted to make manual cleanup
    obvious.
    """
    if dry_run:
        print("  [probe] DRY-RUN - would test parent params: "
              + ", ".join(PARENT_PARAM_CANDIDATES))
        return None

    ts = datetime.now().strftime("%Y%m%d%H%M%S")
    for param in PARENT_PARAM_CANDIDATES:
        probe_name = f"_PROBE_parent_{param}_{ts}"
        print(f"  [probe] Trying param '{param}' with module '{probe_name}' ...")
        status, body = create_module(
            probe_name, token, domain_short,
            parent_param=param, parent_value=LDAP_PARENT_SECTION_KEY,
        )
        print(f"          create response: HTTP {status}  body={body[:200]}")
        # Re-list to see where the module actually landed
        mods = list_all_modules(token, domain_short)
        created = find_module_by_name(mods, probe_name)
        if not created:
            print(f"          could not find '{probe_name}' after create - skipping")
            continue
        parent = module_parent_indicator(created)
        print(f"          new module key={module_key(created)} parent={parent!r}")
        if parent == LDAP_PARENT_SECTION_KEY:
            print(f"  [probe] HIT: param '{param}' correctly nested the module "
                  f"under LDAP (vKv0n).")
            print("  [probe] NOTE: throwaway probe module still exists; delete via UI.")
            return param
        # Some APIs return the human name not the key - accept that too
        ldap_module = next(
            (m for m in mods if module_key(m) == LDAP_PARENT_SECTION_KEY), None
        )
        if ldap_module and parent and parent == module_name(ldap_module):
            print(f"  [probe] HIT (by-name): param '{param}' nested under LDAP "
                  "(parent reported as module name, not key).")
            print("  [probe] NOTE: throwaway probe module still exists; delete via UI.")
            return param

    print("  [probe] No candidate param nested the module under LDAP. The public "
          "REST 'create module' endpoint may not support setting a parent at all.")
    return None


# ---------------------------------------------------------------------------
# CSV: build title -> leaf-module map
# ---------------------------------------------------------------------------
def normalize_title(s: str) -> str:
    return " ".join((s or "").split())


def leaf_from_module_path(module_path: str) -> str:
    """'LDAP > Attribute Mapping' -> 'Attribute Mapping'. Falls back to the
    raw value if there's no ' > ' separator.
    """
    parts = [p.strip() for p in (module_path or "").split(">")]
    return parts[-1] if parts else ""


def load_csv_title_to_leaf(csv_path: Path) -> dict[str, str]:
    if not csv_path.exists():
        raise SystemExit(f"Canonical CSV not found: {csv_path}")
    out: dict[str, str] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if "Module_name" not in (reader.fieldnames or []) or \
           "Test Case Title" not in (reader.fieldnames or []):
            raise SystemExit(
                f"CSV missing required columns. Found: {reader.fieldnames}"
            )
        for row in reader:
            title = normalize_title(row.get("Test Case Title", ""))
            leaf = leaf_from_module_path(row.get("Module_name", ""))
            if title and leaf:
                out[title] = leaf
    return out


# ---------------------------------------------------------------------------
# Case fetch (filter to LDAP parent)
# ---------------------------------------------------------------------------
def fetch_cases_in_module(
    token: str, domain_short: str, section_key: str
) -> list[dict]:
    """Paginate /getAllTestCases and keep cases whose module/section matches.

    We do not assume the server supports a module_key query filter - instead
    we paginate everything and filter client-side. The case dict shape uses
    section_key / module_key / module to point at the parent.
    """
    cases: list[dict] = []
    page = 1
    while page <= 500:
        try:
            r = rest_get(
                f"/api/v1/getAllTestCases/{PROJECT_KEY}?page={page}",
                token, domain_short,
            )
        except urllib.error.HTTPError as e:
            print(f"  WARN: HTTP {e.code} fetching cases page {page}")
            break
        data = r.get("data", []) or []
        if not data:
            break
        for c in data:
            sk = (
                c.get("section_key")
                or c.get("module_key")
                or c.get("sectionId")
                or c.get("module")
            )
            if sk == section_key:
                cases.append(c)
        if not (r.get("link") or {}).get("next"):
            break
        page += 1
    return cases


# ---------------------------------------------------------------------------
# Case edit / update
# ---------------------------------------------------------------------------
def fetch_case_edit_form(
    creds: AuthCreds, case_key: str
) -> tuple[int, dict | None]:
    status, body = internal_post(
        creds, f"/v1/case/edit/p/{PROJECT_KEY}/cid/{case_key}", {}
    )
    if status != 200 or not isinstance(body, dict):
        return status, None
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    return status, data if isinstance(data, dict) else None


def post_case_update(
    creds: AuthCreds, case_key: str, payload: dict
) -> tuple[int, dict | str]:
    return internal_post(
        creds, f"/v1/case/update/p/{PROJECT_KEY}/cid/{case_key}", payload
    )


def build_section_update_payload(current: dict, new_section_key: str) -> dict:
    """Clone current edit-form state, set the 5 section-key aliases, return.

    QA Touch's case payload uses several section-key aliases that different
    code paths read on update (per docs/qa_touch_integration.md §7.B.1, proven
    on the 2026-06-26 LDAP re-org of 175/175 cases via chrome-devtools eval).
    Setting all five removes drift across the UI (module breadcrumbs, filters).

    IMPORTANT: caseStep MUST be preserved verbatim from /v1/case/edit. The
    server validator on /v1/case/update returns HTTP 422
    {"errors":{"caseStep":["Please add some steps in Test Case"]}} if
    caseStep is missing/empty - even on a section-only change. (Earlier
    revision of this function popped caseStep based on the same wrong
    hypothesis that backfill_qa_touch_metadata.build_update_payload was
    fixed for on 2026-06-24; corrected here 2026-06-26.)
    """
    payload = json.loads(json.dumps(current))
    # Overwrite all five section-key aliases to the destination key.
    for k in ("sectionId", "sectionKey", "section_key", "module_key", "moduleId"):
        payload[k] = new_section_key
    # Legacy alias kept for backwards-compat with older response shapes.
    if "module" in payload:
        payload["module"] = new_section_key
    for required in (
        "checkedRequirements",
        "gitlabcheckedRequirements",
        "detailArray",
    ):
        payload.setdefault(required, [])
    return payload


def classify_response(status: int, body: Any) -> tuple[str, list[str]]:
    """Same classifier as backfill_qa_touch_metadata."""
    errors: list[str] = []
    if status == 200:
        if isinstance(body, dict):
            if body.get("status") in (True, "true", 1):
                return "ok", []
            errors.append(
                f"200 OK but body status={body.get('status')} "
                f"msg={str(body.get('msg',''))[:200]}"
            )
            return "failed", errors
        errors.append("200 OK with non-JSON body")
        return "ok", errors
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
    if isinstance(body, dict):
        msg = str(body.get("msg") or body.get("message") or body)[:200]
    elif isinstance(body, str):
        msg = body[:200]
    errors.append(f"HTTP {status}: {msg}")
    return "failed", errors


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--dry-run", action="store_true",
                    help="Print plan, no module/case writes")
    ap.add_argument("--probe-only", action="store_true",
                    help="Just discover parent-id param (or confirm none works)")
    ap.add_argument("--skip-probe", action="store_true",
                    help="Skip probe; create sub-modules at root (DANGEROUS)")
    ap.add_argument("--auth-state-file", type=Path, default=DEFAULT_AUTH_FILE,
                    help=f"Creds JSON (default: {DEFAULT_AUTH_FILE})")
    ap.add_argument("--rate-ms", type=int, default=1000,
                    help="Inter-call delay in ms (default 1000)")
    ap.add_argument("--log-dir", type=Path, default=DEFAULT_LOG_DIR,
                    help=f"Run log directory (default: {DEFAULT_LOG_DIR})")
    ap.add_argument("--rest-domain", default=None,
                    help="Override short REST domain")
    ap.add_argument("--csv", type=Path, default=DEFAULT_CANONICAL_CSV,
                    help=f"Canonical CSV (default: {DEFAULT_CANONICAL_CSV})")
    args = ap.parse_args()

    # --- REST creds
    rest_creds = load_rest_token()
    if not rest_creds:
        print("  Missing QATOUCH_API_TOKEN / QATOUCH_DOMAIN. Set them in your "
              ".env at the repo root (see .env.template).", file=sys.stderr)
        return 2
    token, domain_short = rest_creds
    if args.rest_domain:
        domain_short = args.rest_domain
    print(f"  REST domain: {domain_short}")
    print(f"  Project:     {PROJECT_KEY}")
    print(f"  LDAP parent: {LDAP_PARENT_SECTION_KEY}")
    print(f"  Dry run:     {args.dry_run}")

    # --- Probe-only short circuit
    if args.probe_only:
        print("  Mode: PROBE-ONLY")
        working = probe_parent_param(token, domain_short, args.dry_run)
        if working:
            print(f"  RESULT: '{working}' nests under LDAP - use it on the real run.")
            return 0
        print("  RESULT: no candidate worked; sub-modules cannot be auto-nested "
              "via the public REST 'create module' endpoint.")
        return 2

    # --- Internal auth (needed for case updates only)
    creds = AuthCreds.load(args.auth_state_file)
    print(f"  Auth domain: {creds.domain}")

    # --- Load CSV
    title_to_leaf = load_csv_title_to_leaf(args.csv)
    print(f"  CSV rows w/ title: {len(title_to_leaf)}")
    csv_leaves = set(title_to_leaf.values())
    extra_in_csv = csv_leaves - EXPECTED_LEAF_MODULES
    missing_in_csv = EXPECTED_LEAF_MODULES - csv_leaves
    if extra_in_csv:
        print(f"  WARN: CSV has leaves not in expected set: {sorted(extra_in_csv)}")
    if missing_in_csv:
        print(f"  WARN: Expected leaves missing from CSV: {sorted(missing_in_csv)}")
    target_leaves = sorted(csv_leaves)
    print(f"  Target sub-modules ({len(target_leaves)}): {target_leaves}")

    # --- Probe parent param (unless explicitly skipped)
    parent_param: str | None = None
    if args.skip_probe:
        print("  Probe SKIPPED by flag - sub-modules will be created at ROOT.")
    elif args.dry_run:
        print("  DRY-RUN: skipping probe writes; assuming parent-param TBD.")
    else:
        parent_param = probe_parent_param(token, domain_short, dry_run=False)
        if not parent_param:
            print("  ABORTING: no parent-param candidate worked. Re-run with "
                  "--skip-probe only if you accept root-level modules.",
                  file=sys.stderr)
            return 2

    # --- Snapshot existing modules so we can detect/reuse pre-created ones
    print("  Listing existing modules ...")
    existing_modules = list_all_modules(token, domain_short)
    print(f"  Modules currently in project: {len(existing_modules)}")
    leaf_to_key: dict[str, str] = {}
    for leaf in target_leaves:
        m = find_module_by_name(existing_modules, leaf)
        if m:
            k = module_key(m)
            parent = module_parent_indicator(m)
            if k:
                leaf_to_key[leaf] = k
                tag = "as child of LDAP" if parent == LDAP_PARENT_SECTION_KEY \
                    else f"with parent={parent!r} (NOT LDAP)"
                print(f"  [module] EXISTS '{leaf}' -> {k}  ({tag})")

    # --- Create missing sub-modules
    for leaf in target_leaves:
        if leaf in leaf_to_key:
            continue
        if args.dry_run:
            print(f"  [module] DRY-RUN would create '{leaf}' "
                  f"(parent_param={parent_param!r})")
            continue
        print(f"  [module] CREATE '{leaf}' (parent_param={parent_param!r})")
        status, body = create_module(
            leaf, token, domain_short,
            parent_param=parent_param,
            parent_value=LDAP_PARENT_SECTION_KEY if parent_param else None,
        )
        print(f"           response: HTTP {status}  body={body[:200]}")
        time.sleep(args.rate_ms / 1000.0)
        # Re-list to find the new key (response shape is not stable)
        existing_modules = list_all_modules(token, domain_short)
        created = find_module_by_name(existing_modules, leaf)
        if not created or not module_key(created):
            print(f"  [module] ERROR: created '{leaf}' but cannot resolve key")
            return 2
        k = module_key(created)
        leaf_to_key[leaf] = k
        parent = module_parent_indicator(created)
        if parent_param and parent != LDAP_PARENT_SECTION_KEY:
            print(f"  [module] WARN: '{leaf}' created but parent={parent!r} - "
                  "the param did NOT take effect on this create. Aborting before "
                  "more orphans accumulate.")
            return 2
        print(f"           -> {k}  parent={parent!r}")

    # --- Fetch the 175 flat cases under LDAP
    print(f"  Fetching cases under section {LDAP_PARENT_SECTION_KEY} ...")
    flat_cases = fetch_cases_in_module(token, domain_short, LDAP_PARENT_SECTION_KEY)
    print(f"  Cases flat under LDAP: {len(flat_cases)}")
    if len(flat_cases) != 175:
        print(f"  WARN: expected 175 cases under LDAP, found {len(flat_cases)}. "
              "Continuing - count drift may be normal if cases were already moved.")

    # --- Plan + apply moves
    log_records: list[dict] = []
    summary = {
        "total": 0, "ok": 0, "ok_500_quirk": 0, "failed": 0,
        "unmatched": 0, "fetch_failed": 0, "dry_run": 0, "no_target_module": 0,
    }

    for i, c in enumerate(flat_cases, 1):
        summary["total"] += 1
        case_key = c.get("case_key") or c.get("caseKey") or c.get("id")
        title = normalize_title(c.get("case_title", ""))
        rec: dict[str, Any] = {
            "case_key": case_key,
            "title": c.get("case_title", ""),
            "target_leaf": None,
            "target_section_key": None,
            "status": None,
            "http_status": None,
            "errors": [],
        }

        leaf = title_to_leaf.get(title)
        if not leaf:
            summary["unmatched"] += 1
            rec["status"] = "unmatched"
            rec["errors"].append("Title not in canonical CSV")
            print(f"  [{i}/{len(flat_cases)}] {case_key} -> UNMATCHED title")
            log_records.append(rec)
            continue
        rec["target_leaf"] = leaf

        new_sk = leaf_to_key.get(leaf)
        if not new_sk:
            summary["no_target_module"] += 1
            rec["status"] = "no_target_module"
            rec["errors"].append(f"No section_key for leaf '{leaf}'")
            print(f"  [{i}/{len(flat_cases)}] {case_key} -> NO TARGET MODULE '{leaf}'")
            log_records.append(rec)
            continue
        rec["target_section_key"] = new_sk

        if args.dry_run:
            summary["dry_run"] += 1
            rec["status"] = "dry_run"
            print(f"  [{i}/{len(flat_cases)}] {case_key} -> DRY_RUN move to "
                  f"'{leaf}' ({new_sk})")
            log_records.append(rec)
            continue

        # Fetch current edit-form state
        status, current = fetch_case_edit_form(creds, case_key)
        if status != 200 or current is None:
            summary["fetch_failed"] += 1
            rec["status"] = "fetch_failed"
            rec["http_status"] = status
            rec["errors"].append(f"Edit-form fetch HTTP {status}")
            print(f"  [{i}/{len(flat_cases)}] {case_key} -> FETCH_FAILED ({status})")
            log_records.append(rec)
            time.sleep(args.rate_ms / 1000.0)
            continue

        payload = build_section_update_payload(current, new_sk)
        post_status, post_body = post_case_update(creds, case_key, payload)
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

        marker = {"ok": "OK", "ok_500_quirk": "OK*", "failed": "FAIL"}[label]
        print(f"  [{i}/{len(flat_cases)}] {case_key} -> {marker} "
              f"(HTTP {post_status}) -> '{leaf}'")
        log_records.append(rec)
        time.sleep(args.rate_ms / 1000.0)

    # --- Write log
    args.log_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = args.log_dir / f"reorganize_ldap_{ts}.json"
    log_path.write_text(
        json.dumps({
            "project_key": PROJECT_KEY,
            "ldap_parent": LDAP_PARENT_SECTION_KEY,
            "parent_param_used": parent_param,
            "dry_run": args.dry_run,
            "rate_ms": args.rate_ms,
            "leaf_to_key": leaf_to_key,
            "summary": summary,
            "records": log_records,
        }, indent=2),
        encoding="utf-8",
    )

    # --- Verification pass: re-fetch flat-LDAP count and per-sub counts
    if not args.dry_run:
        print("  Verifying post-move counts ...")
        all_cases_after_per_module: dict[str, int] = {}
        flat_after = fetch_cases_in_module(
            token, domain_short, LDAP_PARENT_SECTION_KEY
        )
        all_cases_after_per_module[LDAP_PARENT_SECTION_KEY] = len(flat_after)
        for leaf, sk in leaf_to_key.items():
            cases_here = fetch_cases_in_module(token, domain_short, sk)
            all_cases_after_per_module[f"{leaf}({sk})"] = len(cases_here)
        print(f"  Post-move counts: {all_cases_after_per_module}")

    # --- Summary
    print()
    print("=" * 60)
    print(f"  REORG SUMMARY  (project {PROJECT_KEY})")
    print("=" * 60)
    print(f"  Total cases:        {summary['total']}")
    print(f"  OK:                 {summary['ok']}")
    print(f"  OK (500 quirk):     {summary['ok_500_quirk']}")
    print(f"  Failed:             {summary['failed']}")
    print(f"  Unmatched titles:   {summary['unmatched']}")
    print(f"  No target module:   {summary['no_target_module']}")
    print(f"  Fetch failed:       {summary['fetch_failed']}")
    print(f"  Dry run:            {summary['dry_run']}")
    print(f"  Parent param used:  {parent_param!r}")
    print(f"  Log:                {log_path}")
    print("=" * 60)

    return 1 if summary["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
