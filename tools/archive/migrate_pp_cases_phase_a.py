#!/usr/bin/env python3
"""Phase A - REPLICATE Partner Portal cases from JlW1 (NexaiQ-Core) -> 70l1 (Partner Admin).

REPLICATE ONLY. No deletion from JlW1. Deletion is a separate explicit Phase B step,
to be run AFTER human review of the Phase A log.

Source modules in JlW1 (NexaiQ-Core):
  - 0yxeN  Users               (86 cases)
  - EGdBv  Platform Management (102 cases)
  - 6ynx8  Audit_Trail         (26 cases)

Target modules in 70l1 (Partner Admin) - discover-or-create:
  - 'Admin > Users'
  - 'Admin > Platform Management'
  - 'Admin > Audit Trail'   (note: underscore dropped on purpose)

Proven endpoints used (verified in OTA / metadata-backfill stream):
  Module create (REST, api-token + domain headers):
    POST https://api.qatouch.com/api/v1/module?projectKey={pk}&moduleName={name}
  Case list (REST):
    GET  https://api.qatouch.com/api/v1/getAllTestCases/{pk}?page=N
  Case create (REST):
    POST https://api.qatouch.com/api/v1/testCase
      body: {projectKey, sectionKey, caseTitle, description?, precondition?}
      Limitation: type/priority/mode/tags ignored on create - set after via /v1/case/update
  Case read (INTERNAL, XSRF + laravel_session via Playwright):
    POST https://soterixsystems.qatouch.com/v1/case/edit/p/{pk}/cid/{caseKey}
  Case metadata update (INTERNAL, XSRF + laravel_session via Playwright):
    POST https://soterixsystems.qatouch.com/v1/case/update/p/{pk}/cid/{caseKey}
      Tolerates the "500-on-success" quirk observed in OTA backfill - the body
      may say success even when the HTTP status is 500. We re-read the case to
      confirm the write actually applied.

Enc-ids for type/priority/tags are echoed back UNCHANGED from the source case's
/v1/case/edit payload. We do not translate them. They are the same project tenant
(soterixsystems.qatouch.com) so the enc_ids are valid across both projects.

CLI:
  python tools/migrate_pp_cases_phase_a.py [--limit N] [--dry-run]
                                           [--auth-state-file PATH]
                                           [--rate-ms 1300]

Outputs:
  logs/pp_migration_phase_a_log.json - per-case migration record (resumable manifest)

End-of-run summary prints: total / replicated / failed / unmatched.

IMPORTANT:
  - No JlW1 mutation occurs in this script. Period.
  - --dry-run prints what WOULD be created without making any writes.
  - Failures are logged and the run CONTINUES.
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import random
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

_print = print
print = functools.partial(_print, flush=True)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from playwright.sync_api import sync_playwright

# ── Constants ───────────────────────────────────────────────────────────────
DOMAIN = "soterixsystems"
UI_BASE = f"https://{DOMAIN}.qatouch.com"
REST_BASE = "https://api.qatouch.com"

SOURCE_PROJECT = "JlW1"  # NexaiQ-Core
TARGET_PROJECT = "70l1"  # Partner Admin

# Source modules in JlW1 - fixed by task spec
SOURCE_MODULES = [
    {"key": "0yxeN", "name": "Users",               "expected": 86,  "target_name": "Admin > Users"},
    {"key": "EGdBv", "name": "Platform Management", "expected": 102, "target_name": "Admin > Platform Management"},
    {"key": "6ynx8", "name": "Audit_Trail",         "expected": 26,  "target_name": "Admin > Audit Trail"},
]

DEFAULT_AUTH_STATE = ROOT / "tools" / ".qatouch_auth_state.json"
LOG_DIR = ROOT / "logs"
LOG_PATH = LOG_DIR / "pp_migration_phase_a_log.json"

MISSING_CREDS_MSG = (
    "Missing QA Touch REST credentials.\n"
    "Set both of these in your .env at the repo root (or export them):\n"
    "    QATOUCH_API_TOKEN=<your REST api-token>\n"
    "    QATOUCH_DOMAIN=soterixsystems\n"
    "See .env.template for the full list."
)


# ── REST helpers (api-token + domain headers) ────────────────────────────────
def load_rest_creds() -> tuple[str, str]:
    """Load QATOUCH_API_TOKEN + QATOUCH_DOMAIN from the environment / .env."""
    token = os.environ.get("QATOUCH_API_TOKEN") or os.environ.get("QATOUCH_API_KEY")
    domain = os.environ.get("QATOUCH_DOMAIN")
    if not token or not domain:
        raise SystemExit(MISSING_CREDS_MSG)
    return token, domain


def rest_get(path: str, token: str, domain: str, timeout: int = 30,
             max_retries: int = 4) -> dict:
    """REST GET with 429 backoff. api.qatouch.com rate-limits hard around page 35.

    On 429, sleeps 2s/4s/8s/16s and retries up to max_retries times. Any other
    HTTPError is raised (caller decides how to log).
    """
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        req = urllib.request.Request(
            f"{REST_BASE}{path}",
            headers={"api-token": token, "domain": domain, "Accept": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries:
                wait = 2 ** (attempt + 1)  # 2, 4, 8, 16
                print(f"  REST 429 on {path} - sleeping {wait}s then retrying "
                      f"(attempt {attempt + 1}/{max_retries})")
                time.sleep(wait)
                last_err = e
                continue
            raise
    if last_err:
        raise last_err
    raise RuntimeError("unreachable")


def rest_post(path: str, token: str, domain: str, body: dict | None = None,
              timeout: int = 30) -> tuple[int, str]:
    """POST returning (status, body_text). Tolerates non-2xx so caller can inspect."""
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"{REST_BASE}{path}",
        data=data,
        method="POST",
        headers={
            "api-token": token,
            "domain": domain,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body_text = ""
        try:
            body_text = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return e.code, body_text


# ── Module discover / create ────────────────────────────────────────────────
def list_all_modules(project_key: str, token: str, domain: str) -> list[dict]:
    all_mods: list[dict] = []
    page = 1
    while page <= 60:
        try:
            r = rest_get(f"/api/v1/getAllModules/{project_key}?page={page}",
                         token, domain)
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


def find_module_by_name(modules: list[dict], target_name: str) -> dict | None:
    target_norm = target_name.strip().lower()
    for m in modules:
        name = (m.get("section_name") or m.get("module_name") or "").strip().lower()
        if name == target_norm:
            return m
    return None


def create_module_via_query(project_key: str, module_name: str,
                            token: str, domain: str) -> dict:
    """POST /api/v1/module?projectKey=...&moduleName=... (per task spec).

    Returns a dict possibly carrying the new section_key. We don't trust the
    shape - caller re-lists modules to resolve the key.
    """
    qs = urllib.parse.urlencode({"projectKey": project_key, "moduleName": module_name})
    status, body = rest_post(f"/api/v1/module?{qs}", token, domain, body={})
    return {"status": status, "body": body}


def ensure_target_module(project_key: str, target_name: str,
                         token: str, domain: str,
                         dry_run: bool) -> tuple[str | None, bool]:
    """Return (module_key, created_flag). On dry-run, never creates."""
    mods = list_all_modules(project_key, token, domain)
    existing = find_module_by_name(mods, target_name)
    if existing:
        key = existing.get("section_key") or existing.get("module_key")
        print(f"  [module] EXISTS  '{target_name}' -> {key}")
        return key, False
    if dry_run:
        print(f"  [module] DRY-RUN would create '{target_name}'")
        return None, False
    print(f"  [module] CREATE  '{target_name}' via POST /api/v1/module?...")
    resp = create_module_via_query(project_key, target_name, token, domain)
    print(f"           response: status={resp['status']} body={resp['body'][:200]}")
    # Re-list to find the new module's key (response shape is not stable)
    mods = list_all_modules(project_key, token, domain)
    created = find_module_by_name(mods, target_name)
    if not created:
        print(f"  [module] ERROR: created '{target_name}' but cannot resolve key")
        return None, True
    key = created.get("section_key") or created.get("module_key")
    print(f"  [module] OK      '{target_name}' -> {key}")
    return key, True


# ── Source case pagination + filtering ──────────────────────────────────────
def fetch_all_project_cases(project_key: str, token: str, domain: str,
                            inter_page_sleep_seconds: float = 0.3) -> list[dict]:
    """Single full enumeration of /getAllTestCases/{pk}. Caller groups by
    module_key in memory.

    Was: fetch_source_cases_for_module(...) ran a full page-by-page scan
    PER module - so 3 modules = 3× pagination = ~180 REST calls back-to-back
    against api.qatouch.com, which rate-limits hard around page 35 (HTTP 429).
    The dry-run on 2026-06-25 surfaced this - Users (first scan) returned 86
    cases but Platform Management + Audit_Trail both came back EMPTY because
    every page was 429'd. One scan + in-memory filter avoids the issue, and
    rest_get's 429-backoff covers the rest.
    """
    all_cases: list[dict] = []
    page = 1
    while page <= 200:
        try:
            r = rest_get(
                f"/api/v1/getAllTestCases/{project_key}?page={page}",
                token, domain,
            )
        except urllib.error.HTTPError as e:
            print(f"  WARN: HTTP {e.code} on getAllTestCases page {page} - stopping")
            break
        data = r.get("data", []) or []
        if not data:
            break
        all_cases.extend(data)
        if not (r.get("link") or {}).get("next"):
            break
        page += 1
        if inter_page_sleep_seconds > 0:
            time.sleep(inter_page_sleep_seconds)
    return all_cases


def group_cases_by_module_key(cases: list[dict]) -> dict[str, list[dict]]:
    """Group an in-memory list of cases by module_key (falling back to section_key)."""
    out: dict[str, list[dict]] = {}
    for c in cases:
        mk = c.get("module_key") or c.get("section_key") or ""
        if not mk:
            continue
        out.setdefault(mk, []).append(c)
    return out


# ── Browser auth (Playwright) ───────────────────────────────────────────────
def open_browser(p, auth_state_file: Path):
    browser = p.chromium.launch(headless=False, slow_mo=50,
                                args=["--start-maximized"])
    if auth_state_file.exists():
        print(f"  Loading saved auth state: {auth_state_file}")
        ctx = browser.new_context(storage_state=str(auth_state_file),
                                  viewport={"width": 1400, "height": 900})
        page = ctx.new_page()
        page.goto(f"{UI_BASE}/v2#/new-projects", timeout=60000)
        time.sleep(5)
        url = page.url or ""
        if "/login" not in url and "qatouch.com" in url:
            print("  Auth state valid!")
            return browser, ctx, page
        print("  Auth state expired - re-login required.")
        ctx.close()

    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()
    page.goto(f"{UI_BASE}/login", timeout=60000)
    page.bring_to_front()
    print()
    print("=" * 60)
    print("  BROWSER OPENED - please log in to QA Touch.")
    print("  Waiting up to 600 seconds...")
    print("=" * 60)
    for _i in range(200):
        time.sleep(3)
        url = page.url or ""
        if "/login" not in url and "qatouch.com" in url:
            print("  Login detected!")
            time.sleep(2)
            ctx.storage_state(path=str(auth_state_file))
            return browser, ctx, page
    browser.close()
    raise SystemExit("Login timeout after 600s")


# ── Internal-API helpers (run in browser context, share laravel_session) ────
def internal_get_case(page, project_key: str, case_key: str) -> dict | None:
    """POST /v1/case/edit/p/{pk}/cid/{key} - returns full edit-form payload."""
    return page.evaluate(
        """
        async ({pk, ck}) => {
            try {
                const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
                const resp = await fetch('/v1/case/edit/p/' + pk + '/cid/' + ck, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-XSRF-TOKEN': decodeURIComponent(token || '')
                    },
                    body: JSON.stringify({})
                });
                if (!resp.ok) return {__error: 'HTTP ' + resp.status};
                const data = await resp.json();
                if (!data || !data.data) return {__error: 'no data field'};
                return data.data;
            } catch (e) {
                return {__error: e.message};
            }
        }
        """,
        {"pk": project_key, "ck": case_key},
    )


def internal_update_case(page, project_key: str, case_key: str,
                         payload: dict) -> dict:
    """POST /v1/case/update/p/{pk}/cid/{key} with the FULL edit-form payload.

    Returns {status, ok, body}. We deliberately do not raise on non-2xx - the
    OTA backfill stream documented a "500-on-success" quirk where the server
    returns 500 with status:true in the body. Caller verifies via re-read.
    """
    return page.evaluate(
        """
        async ({pk, ck, payload}) => {
            try {
                const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
                const resp = await fetch('/v1/case/update/p/' + pk + '/cid/' + ck, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json;charset=UTF-8',
                        'Accept': 'application/json',
                        'X-XSRF-TOKEN': decodeURIComponent(token || '')
                    },
                    body: JSON.stringify(payload)
                });
                const text = await resp.text();
                return {status: resp.status, ok: resp.ok, body: text.substring(0, 800)};
            } catch (e) {
                return {status: 0, ok: false, body: 'JS error: ' + e.message};
            }
        }
        """,
        {"pk": project_key, "ck": case_key, "payload": payload},
    )


def update_succeeded(resp: dict) -> bool:
    """Tolerate the 500-on-success quirk: parse body and look for status:true /
    'success' / 'updated'."""
    if resp.get("ok"):
        return True
    body = (resp.get("body") or "").lower()
    if "successfully" in body or '"status":true' in body or "updated" in body:
        return True
    return False


# ── Build update payload from source edit-data ──────────────────────────────
PRESERVED_FIELDS = (
    "caseTitle", "title",
    "description",
    "precondition",
    "reference",
    "type",         # enc_id string
    "priority",     # enc_id string
    "mode",         # 'manual' / 'automation' / ''
    "newtags",      # list of enc_id strings  (vendor renamed NewTags -> Tags around 2026-05;
                    # we send 'newtags' lowercase, matching the /v1/case/update payload shape
                    # used in qatouch_api_mode_update.py and OTA backfill)
)


def build_target_update_payload(target_edit: dict, source_edit: dict,
                                target_section_key: str) -> dict:
    """Take the freshly-created target case's edit payload, overlay metadata
    from the source case's edit payload, force the sectionId/sectionKey to the
    target module key, and return a payload suitable for /v1/case/update.

    We intentionally do NOT touch caseStep on create - step replication is a
    separate Phase A.1 step if needed.
    """
    payload = dict(target_edit)  # start from target shape so required fields exist

    for f in PRESERVED_FIELDS:
        if f in source_edit and source_edit[f] is not None:
            payload[f] = source_edit[f]

    # Section pinning: don't let the target drift back to whatever default the
    # create call dropped it into. Set every plausible key.
    for k in ("sectionId", "sectionKey", "section_key", "module_key"):
        if k in payload or k in source_edit:
            payload[k] = target_section_key

    # Required array fields that the update endpoint expects (per
    # qatouch_api_mode_update.py).
    for field in ("checkedRequirements", "gitlabcheckedRequirements", "detailArray"):
        if field not in payload:
            payload[field] = []

    return payload


# ── Case creation via REST ──────────────────────────────────────────────────
def rest_create_test_case(project_key: str, section_key: str, source: dict,
                          token: str, domain: str) -> tuple[int, str]:
    """POST /api/v1/testCase. Type/priority/mode/tags are ignored on create
    (per qatouch_client.py docstring) - we set them in the follow-up update."""
    body: dict[str, Any] = {
        "projectKey": project_key,
        "sectionKey": section_key,
        "caseTitle": source.get("caseTitle") or source.get("title") or "",
    }
    desc = source.get("description")
    if desc:
        body["description"] = desc
    pre = source.get("precondition")
    if pre:
        body["precondition"] = pre
    return rest_post("/api/v1/testCase", token, domain, body=body)


def find_target_case_by_title(project_key: str, title: str, section_key: str,
                              token: str, domain: str) -> dict | None:
    """Search from newest pages backward (created cases land at the end)."""
    try:
        first = rest_get(f"/api/v1/getAllTestCases/{project_key}?page=1",
                         token, domain)
    except urllib.error.HTTPError as e:
        print(f"  WARN: HTTP {e.code} on initial list for find-by-title")
        return None
    total = (first.get("meta") or {}).get("total", 0)
    per_page = 50
    last_page = max(1, (total + per_page - 1) // per_page)

    # search last 4 pages backward
    for pg in range(last_page, max(0, last_page - 4), -1):
        try:
            r = rest_get(
                f"/api/v1/getAllTestCases/{project_key}?page={pg}",
                token, domain,
            )
        except urllib.error.HTTPError:
            continue
        for c in r.get("data", []) or []:
            if (c.get("case_title") or "") == title:
                if c.get("module_key") == section_key:
                    return c
        time.sleep(0.2)
    # last resort: scan all pages
    for pg in range(1, last_page + 1):
        try:
            r = rest_get(
                f"/api/v1/getAllTestCases/{project_key}?page={pg}",
                token, domain,
            )
        except urllib.error.HTTPError:
            continue
        for c in r.get("data", []) or []:
            if (c.get("case_title") or "") == title and c.get("module_key") == section_key:
                return c
    return None


# ── Spot-verify ─────────────────────────────────────────────────────────────
SPOT_COMPARE_FIELDS = ("caseTitle", "title", "description", "precondition",
                       "reference", "type", "priority", "mode", "newtags")


def spot_verify(page, log_entries: list[dict], sample: int = 5) -> None:
    if not log_entries:
        print("  [verify] nothing to verify")
        return
    sample = min(sample, len(log_entries))
    picks = random.sample(log_entries, sample)
    print(f"\n  [verify] Spot-checking {sample} target cases vs source...")
    for entry in picks:
        src = internal_get_case(page, SOURCE_PROJECT, entry["source_key"])
        tgt = internal_get_case(page, TARGET_PROJECT, entry["target_key"])
        if not src or src.get("__error"):
            print(f"    [{entry['source_key']}] could not read source: {src}")
            continue
        if not tgt or tgt.get("__error"):
            print(f"    [{entry['source_key']}] could not read target: {tgt}")
            continue
        diffs = []
        for f in SPOT_COMPARE_FIELDS:
            sv = src.get(f)
            tv = tgt.get(f)
            if sv != tv:
                diffs.append(f)
        status = "MATCH" if not diffs else f"DIFFS: {diffs}"
        print(f"    [{entry['source_key']} -> {entry['target_key']}] {status}")


# ── Logging ─────────────────────────────────────────────────────────────────
def append_log(entries: list[dict]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(entries, indent=2), encoding="utf-8")


# ── Main per-case migration ─────────────────────────────────────────────────
def migrate_one_case(page, source_case: dict, source_mod_name: str,
                     target_section_key: str, target_mod_name: str,
                     token: str, domain: str, dry_run: bool,
                     rate_seconds: float) -> dict:
    """Migrate a single case. Returns a log entry dict (always; failures included)."""
    source_key = source_case.get("case_key") or source_case.get("caseKey")
    source_code = source_case.get("case_code") or source_case.get("caseCode") or ""
    source_title = source_case.get("case_title") or source_case.get("caseTitle") or ""

    entry: dict[str, Any] = {
        "source_key": source_key,
        "source_module_name": source_mod_name,
        "source_case_code": source_code,
        "source_title": source_title,
        "target_module_name": target_mod_name,
        "target_key": None,
        "target_case_code": None,
        "status": "pending",
        "error": "",
    }

    # 1. Read full source edit data
    src_edit = internal_get_case(page, SOURCE_PROJECT, source_key)
    if not src_edit or src_edit.get("__error"):
        entry["status"] = "failed"
        entry["error"] = f"source edit read failed: {src_edit}"
        print(f"    FAIL read source: {entry['error']}")
        return entry

    if dry_run:
        entry["status"] = "dry_run_would_create"
        entry["error"] = ""
        print(f"    DRY-RUN would create '{source_title[:60]}'")
        return entry

    # 2. Create target case shell via REST
    status, body = rest_create_test_case(
        TARGET_PROJECT, target_section_key, src_edit, token, domain
    )
    if status not in (200, 201) and '"success":true' not in body.lower():
        entry["status"] = "failed"
        entry["error"] = f"REST create returned status={status} body={body[:200]}"
        print(f"    FAIL create: {entry['error']}")
        return entry

    time.sleep(rate_seconds)

    # 3. Find the new target case (by title within target module) to get its key
    target_case = find_target_case_by_title(
        TARGET_PROJECT, source_title, target_section_key, token, domain,
    )
    if not target_case:
        entry["status"] = "failed"
        entry["error"] = "target case not found after create (title lookup failed)"
        print(f"    FAIL lookup: {entry['error']}")
        return entry

    target_key = target_case.get("case_key")
    entry["target_key"] = target_key
    entry["target_case_code"] = target_case.get("case_code") or target_case.get("caseCode") or ""

    # 4. Read target edit data (need the full payload shape for the update)
    tgt_edit = internal_get_case(page, TARGET_PROJECT, target_key)
    if not tgt_edit or tgt_edit.get("__error"):
        entry["status"] = "partial"
        entry["error"] = (
            f"created but could not read target edit data: {tgt_edit} "
            "(metadata not copied)"
        )
        print(f"    PARTIAL: {entry['error']}")
        return entry

    # 5. Build payload and update metadata on the target
    payload = build_target_update_payload(tgt_edit, src_edit, target_section_key)
    upd = internal_update_case(page, TARGET_PROJECT, target_key, payload)

    if not update_succeeded(upd):
        entry["status"] = "partial"
        entry["error"] = (
            f"created, but metadata update failed: "
            f"status={upd.get('status')} body={(upd.get('body') or '')[:200]}"
        )
        print(f"    PARTIAL update: {entry['error']}")
        return entry

    entry["status"] = "replicated"
    print(f"    OK  {source_key} -> {target_key} ({source_title[:60]})")
    return entry


# ── Orchestration ───────────────────────────────────────────────────────────
def run(args) -> int:
    auth_state_file = Path(args.auth_state_file) if args.auth_state_file else DEFAULT_AUTH_STATE
    rate_seconds = max(0.0, args.rate_ms / 1000.0)
    dry_run = bool(args.dry_run)

    print("=" * 70)
    print("  PARTNER PORTAL MIGRATION - Phase A (REPLICATE ONLY)")
    print(f"  source:     {SOURCE_PROJECT}  (NexaiQ-Core)")
    print(f"  target:     {TARGET_PROJECT}  (Partner Admin)")
    print(f"  auth state: {auth_state_file}")
    print(f"  rate:       {args.rate_ms}ms between calls")
    print(f"  dry-run:    {dry_run}")
    if args.limit:
        print(f"  limit:      first {args.limit} source cases (across all 3 modules)")
    print("=" * 70)

    token, domain = load_rest_creds()

    # Step 1 - discover or create the 3 target modules in 70l1
    print("\n[1/4] Resolving target modules in 70l1...")
    module_map: dict[str, str] = {}  # source module name -> target section_key
    for src in SOURCE_MODULES:
        key, _created = ensure_target_module(
            TARGET_PROJECT, src["target_name"], token, domain, dry_run,
        )
        module_map[src["name"]] = key  # may be None if dry-run

    # Step 2 - fetch source cases (ONCE) then group by module_key in memory
    print("\n[2/4] Fetching source cases from JlW1 (single full enumeration)...")
    source_cases = fetch_all_project_cases(SOURCE_PROJECT, token, domain)
    print(f"  Source enumeration: {len(source_cases)} total cases in JlW1")
    by_mod = group_cases_by_module_key(source_cases)
    work: list[tuple[dict, dict]] = []  # (source_case, source_module_def)
    for src in SOURCE_MODULES:
        cases = by_mod.get(src["key"], [])
        print(f"  {src['name']:24s}  found {len(cases):3d} cases  "
              f"(expected {src['expected']})")
        for c in cases:
            work.append((c, src))

    if args.limit:
        work = work[: args.limit]

    total = len(work)
    print(f"\n  Total cases to migrate this run: {total}")

    # Step 3 - launch browser session for internal endpoints, then migrate
    print("\n[3/4] Launching browser for internal /v1/case/edit + /v1/case/update...")
    log_entries: list[dict] = []
    replicated = failed = partial = unmatched = dry_run_count = 0

    with sync_playwright() as p:
        browser, _ctx, page = open_browser(p, auth_state_file)
        try:
            for idx, (source_case, src_mod) in enumerate(work, 1):
                target_section_key = module_map.get(src_mod["name"])
                if not target_section_key and not dry_run:
                    unmatched += 1
                    entry = {
                        "source_key": source_case.get("case_key"),
                        "source_module_name": src_mod["name"],
                        "source_case_code": source_case.get("case_code", ""),
                        "source_title": source_case.get("case_title", ""),
                        "target_module_name": src_mod["target_name"],
                        "target_key": None,
                        "target_case_code": None,
                        "status": "unmatched_no_target_module",
                        "error": "target module key unresolved",
                    }
                    log_entries.append(entry)
                    print(f"  [{idx}/{total}] UNMATCHED  no target module key")
                    continue

                print(f"  [{idx}/{total}] {src_mod['name']}: "
                      f"{(source_case.get('case_title') or '')[:55]}")

                entry = migrate_one_case(
                    page=page,
                    source_case=source_case,
                    source_mod_name=src_mod["name"],
                    target_section_key=target_section_key or "",
                    target_mod_name=src_mod["target_name"],
                    token=token,
                    domain=domain,
                    dry_run=dry_run,
                    rate_seconds=rate_seconds,
                )
                log_entries.append(entry)

                if entry["status"] == "replicated":
                    replicated += 1
                elif entry["status"] == "partial":
                    partial += 1
                elif entry["status"] == "dry_run_would_create":
                    dry_run_count += 1
                else:
                    failed += 1

                # Persist incrementally so a mid-run crash doesn't lose progress.
                append_log(log_entries)
                time.sleep(rate_seconds)

            # Step 4 - spot-verify if not dry-run
            if not dry_run:
                print("\n[4/4] Spot-verifying 5 random target cases vs source...")
                replicated_entries = [e for e in log_entries if e["status"] == "replicated"]
                spot_verify(page, replicated_entries, sample=5)
            else:
                print("\n[4/4] DRY-RUN - skipping spot-verify")
        finally:
            browser.close()

    # ── Summary ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  PHASE A - SUMMARY")
    print(f"  Total processed:  {total}")
    if dry_run:
        print(f"  Would create:     {dry_run_count}")
    else:
        print(f"  Replicated:       {replicated}")
        print(f"  Partial:          {partial}  (created but metadata not fully copied)")
    print(f"  Failed:           {failed}")
    print(f"  Unmatched:        {unmatched}  (no target module key)")
    print(f"  Log written to:   {LOG_PATH.relative_to(ROOT)}")
    print("=" * 70)
    print("\n  REMINDER: No JlW1 cases were deleted. Phase B (delete) is a")
    print("            separate explicit step after you review the log above.")
    return 0 if (failed == 0 and unmatched == 0) else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Phase A - replicate 214 PP cases JlW1 -> 70l1 (no deletion)."
    )
    ap.add_argument("--limit", type=int, default=0,
                    help="Process only the first N source cases (probe mode).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Print what WOULD be created without writing.")
    ap.add_argument("--auth-state-file", default=str(DEFAULT_AUTH_STATE),
                    help=f"Playwright storage state file (default: {DEFAULT_AUTH_STATE}).")
    ap.add_argument("--rate-ms", type=int, default=1300,
                    help="Milliseconds between internal/REST calls (default 1300).")
    args = ap.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
