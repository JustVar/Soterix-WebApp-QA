#!/usr/bin/env python3
"""Phase A (continuation) - copy SOURCE step rows onto the 214 already-migrated
Partner Portal targets. New ordering: write-steps-under-template=1, then
flip-template-last as a 'surfacing' step (empirically proven on TR0250
2026-06-25). The Steps tab renders post-flip with the already-persisted rows.

Why this script exists
======================
Yesterday's run (`migrate_pp_cases_phase_a.py`) replicated 214 source cases
(JlW1) -> target shells (70l1) and copied metadata via /v1/case/update.
That endpoint refuses to write step rows safely (see RISKS below) and the
target shells were created with the default template=1 ("Exploratory Session"),
which renders NO Steps tab. Targets start with caseStep=[] (empirically
probed - no placeholder step row exists, contrary to the prior assumption).
This script completes the migration by:

  1. Read target /v1/case/edit (expect template=1, caseStep=[]).
  2. Read source /v1/case/edit for step content + expected_count.
  3. Idempotency short-circuit: template==2 AND caseStep_len==expected_count
     -> already_done.
  4. WRITE STEPS FIRST under template=1: for each source step in `position`
     order, POST /v1/steps/save with {cid, pid, step_description,
     expected_result}. Each returns 200 even though /v1/case/edit will still
     show caseStep=[] under template=1 - this is the documented
     "hidden but persisted" behavior. Do NOT re-fetch /v1/case/edit between
     saves to "verify" - it will look empty and trigger false retries.
     INTER_STEP_DELAY between saves; retry once on 429 with RATE_LIMIT_PAUSE.
  5. NO PLACEHOLDER DELETE PHASE. Targets start with caseStep=[]; the
     previous assumption that there was a placeholder row was empirically
     wrong. Skip steps/delete entirely.
  6. FLIP TEMPLATE LAST via /v1/case/update with payload built from the
     target edit body: payload["template"]=2 AND payload["caseStep"]=
     [{"step":"<p>.</p>","description":"<p>-</p>"}] (a one-row stub purely
     to pass the "Please add some steps in Test Case" validator - the stub
     row is silently dropped server-side per PROBE C). Tolerate the
     500-on-success quirk via update_succeeded(); do NOT count flip as
     success on body-substring alone - gate on the post-flip re-read.
  7. VERIFY by re-fetching /v1/case/edit: expect template==2 AND
     len(caseStep)==expected_count AND step content matches what was sent.

Source-of-truth strategy (USE_JLW1)
===================================
JlW1 is the canonical source for per-step expected_result text: source
caseStep[i].description carries the row-level Expected Result. The 39-file
xlsx hunt in Downloads matched only 1 of 213 PP titles exactly (0.47%) and
that one row was a NexaiQ-Core Permissions Panel row, not a PP Admin>Users
row. No xlsx covers Admin>Platform Management or Admin>Audit Trail at the
correct grain. JlW1 is self-consistent and authoritative.

When source .description is empty (steps 2..N convention puts overall result
only on step 1), fall back to literal "-" (DASH_FALLBACK) - validated to
pass the server-side "Please Enter Expected Result" check 2026-06-25.

RISKS / why we DO NOT use /v1/case/update for step writes
=========================================================
- cleanup_ota_steps.py:16-21 - wholesale caseStep replacement via
  /v1/case/update is hazardous. The /v1/steps/* endpoints are the path
  the UI uses and were confirmed working. Step CRUD goes through
  /v1/steps/* only; /v1/case/update is used here ONLY for the final
  template flip (with a stub caseStep row to pass the validator).
- Per-step /v1/steps/save (one HTTP per step) is the only confirmed-safe
  path for writing step content.

Idempotency
===========
- Re-fetches target before each write. Already_done = template==2 AND
  caseStep_len==expected_count.
- template==1 AND caseStep_len==0 AND expected_count>0 -> normal full run.
- template==1 AND caseStep_len>0 (impossible per probe, defensive) ->
  treat as needs-redo: delete via /v1/steps/delete then proceed.
- Per-case atomic log writes (`logs/pp_migration_phase_a_steps_{ts}.json`)
  so a mid-run crash never loses progress.

NOTE on crash recovery: if the script crashes BETWEEN step-save and
template-flip, the case is left with template=1 and caseStep=[] in the UI
but with N persisted-but-hidden rows server-side. On resume, the
idempotency check will treat it as a fresh case and DOUBLE-WRITE. The
pragmatic mitigation is to inspect the per-case log to identify
mid-flip casualties and hand-fix them.

Rate-limit budget
=================
- 214 cases × ~13 avg source steps = ~2800 /v1/steps/save calls +
  ~214 flip calls + ~3 reads/case ≈ 3700 internal calls. With 0.4s
  inter-step pause + 1.3s inter-case pause and the conservative 20s
  pause on 429, expect ~60-90 min wall time.

CLI
===
  python tools/migrate_pp_cases_phase_a_steps.py
      [--limit N]                  process first N targets (probe mode)
      [--dry-run]                  print plan, no writes
      [--resume-from N]            skip the first N records of the input
      [--skip-modules X,Y]         CSV of target_module_name to skip
      [--auth-state-file PATH]     Playwright storage state
      [--rate-ms 1300]             inter-case pause (ms)
      [--only-template]            ONLY flip template (stub row, empty
                                   Steps tab); for repair only.
      [--only-steps]               ONLY copy steps under current template
                                   (visible if template=2, hidden if 1).

Inputs
======
  logs/pp_migration_phase_a_resume_20260625-091616.json
  (214 records carrying source_key + target_key + target_module_name +
   source_title - written by the yesterday's metadata-copy run.)

Outputs
=======
  logs/pp_migration_phase_a_steps_{YYYYmmdd-HHMMSS}.json - per-case record:
    {source_key, target_key, target_module, status, template_change,
     steps_copied_count, steps_failed_count, errors[]}

Exit code: 0 if all done/skipped, 1 if any failed.
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import sys
import time
from datetime import datetime
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

SOURCE_PROJECT = "JlW1"  # NexaiQ-Core
TARGET_PROJECT = "70l1"  # Partner Admin

# Template enum (verified in repo: qatouch_full_audit.py:427,
# qatouch_browser.py:1412-1462).
TEMPLATE_EXPLORATORY = 1
TEMPLATE_STEPS = 2

DEFAULT_AUTH_STATE = ROOT / "tools" / ".qatouch_auth_state.json"
DEFAULT_RESUME_INPUT = (
    ROOT / "logs" / "pp_migration_phase_a_resume_20260625-091616.json"
)
LOG_DIR = ROOT / "logs"

# Per cleanup_ota_steps.py timings - step CRUD is heavier than metadata update.
INTER_STEP_DELAY = 0.4      # seconds between /v1/steps/save calls
INTER_CALL_DELAY = 0.3      # seconds between any other internal call
RATE_LIMIT_PAUSE = 20.0     # seconds when we see HTTP 429
VERIFY_PAUSE = 0.7          # seconds between final save and re-fetch

# Fallback for empty per-step expected_result. Source convention puts the
# overall result only on step 1; steps 2..N are blank and the server-side
# validator rejects empty ("Please Enter Expected Result"). Single dash
# accepted (probed 2026-06-25). Configurable so the canary can detect any
# future validator tightening that rejects "-" specifically.
DASH_FALLBACK = "-"


# ── Browser auth (Playwright) - mirrors migrate_pp_cases_phase_a.py ─────────
def open_browser(p, auth_state_file: Path):
    browser = p.chromium.launch(
        headless=False, slow_mo=50, args=["--start-maximized"]
    )
    if auth_state_file.exists():
        print(f"  Loading saved auth state: {auth_state_file}")
        ctx = browser.new_context(
            storage_state=str(auth_state_file),
            viewport={"width": 1400, "height": 900},
        )
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
    for _ in range(200):
        time.sleep(3)
        url = page.url or ""
        if "/login" not in url and "qatouch.com" in url:
            print("  Login detected!")
            time.sleep(2)
            ctx.storage_state(path=str(auth_state_file))
            return browser, ctx, page
    browser.close()
    raise SystemExit("Login timeout after 600s")


# ── Internal API helpers (run inside the page context) ──────────────────────
def internal_get_case_edit(page, project_key: str, case_key: str) -> dict:
    """POST /v1/case/edit/p/{pk}/cid/{ck} - returns the full edit-form
    payload (the dict under data.data, NOT the wrapper). On error returns
    {"__error": "..."}.
    """
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
    """POST /v1/case/update/p/{pk}/cid/{ck} with a FULL edit-form body.

    Returns {status, ok, body}. We deliberately do not raise - the OTA
    backfill stream documented a "500-on-success" quirk (status 500 with
    "Case Updated Successfully" in the body). Caller re-reads to confirm.
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
    """Tolerate the 500-on-success quirk: parse body for success markers.

    HTTP 500 with body containing 'successfully' / '"status":true' /
    'updated' / 'case updated' is treated as success (documented quirk
    on /v1/case/update).

    Explicit guard: HTTP 422 with a known validator phrase ('please add
    some steps', 'please enter') is NEVER a success - the word 'updated'
    can appear adjacent to the validator phrase and would otherwise be a
    false positive. Caller MUST still verify by re-reading the case.
    """
    status = resp.get("status") or 0
    body = (resp.get("body") or "").lower()
    if status == 422 and (
        "please add some steps" in body or "please enter" in body
    ):
        return False
    if resp.get("ok"):
        return True
    # Documented vendor quirk on /v1/case/update: HTTP 500 + body =
    # {"message":"Server Error"}. The save SUCCEEDED; the 500 is a
    # post-save side-effect error. Confirmed empirically on TR0249/TR0250
    # 2026-06-25 - template flipped AND caseStep persisted despite 500.
    # See backfill_qa_touch_metadata.py:classify_response (Partner Admin
    # backfill yesterday) which keys on this exact pattern.
    if status == 500 and ("server error" in body):
        return True
    return (
        "successfully" in body
        or '"status":true' in body
        or "case updated" in body
        or "updated" in body
    )


def delete_step(page, step_id: str) -> dict:
    """GET /v1/steps/delete/mid/{id}?type=true. Returns {ok, status}."""
    return page.evaluate(
        """
        async (stepId) => {
            try {
                const resp = await fetch('/v1/steps/delete/mid/' + stepId + '?type=true');
                return {ok: resp.ok, status: resp.status};
            } catch (e) {
                return {ok: false, status: 0, error: e.message};
            }
        }
        """,
        step_id,
    )


def save_step(page, project_key: str, case_key: str,
              step_description: str, expected_result: str) -> dict:
    """POST /v1/steps/save with the proven body shape.

    Per recon: cid, pid, step_description, expected_result (no position,
    no from_reusable_step on the wire). Server assigns ordering by
    insertion sequence - caller MUST loop in `position` order.
    """
    return page.evaluate(
        """
        async ({pid, cid, desc, exp}) => {
            try {
                const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
                const resp = await fetch('/v1/steps/save', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-XSRF-TOKEN': decodeURIComponent(token || '')
                    },
                    body: JSON.stringify({
                        cid: cid,
                        pid: pid,
                        step_description: desc,
                        expected_result: exp
                    })
                });
                const body = await resp.text();
                return {
                    ok: resp.ok,
                    status: resp.status,
                    rateLimited: resp.status === 429,
                    body: body.substring(0, 300)
                };
            } catch (e) {
                return {ok: false, status: 0, error: e.message};
            }
        }
        """,
        {
            "pid": project_key,
            "cid": case_key,
            "desc": step_description,
            "exp": expected_result,
        },
    )


# ── Payload helpers ─────────────────────────────────────────────────────────
def build_template_flip_payload(target_edit: dict) -> dict:
    """Echo the CURRENT target edit body back as the /v1/case/update
    payload, flipping `template` to 2 and supplying a one-row caseStep
    STUB to pass the server-side validator.

    Why the stub row: with template=2 the validator rejects an empty
    caseStep with "Please add some steps in Test Case" (HTTP 422). The
    stub row ({step:'<p>.</p>', description:'<p>-</p>'}) satisfies the
    validator and is silently dropped server-side - it is NOT persisted
    (verified PROBE C 2026-06-25). The already-persisted, hidden-under-
    template=1 step rows surface immediately after the flip.

    Defensive fills for checkedRequirements / gitlabcheckedRequirements /
    detailArray match the pattern in
    backfill_qa_touch_metadata.py:447 and migrate_pp_cases_phase_a.py:456.
    """
    payload = json.loads(json.dumps(target_edit))  # deep copy
    payload["template"] = TEMPLATE_STEPS

    # Stub row - purely to pass "Please add some steps" validator.
    # Server drops it; the real (persisted-under-template=1) rows surface.
    payload["caseStep"] = [
        {"step": "<p>.</p>", "description": "<p>-</p>"}
    ]

    # The update endpoint expects these arrays even when empty
    # (per qatouch_api_mode_update.py + migrate_pp_cases_phase_a.py:456).
    for field in ("checkedRequirements", "gitlabcheckedRequirements",
                  "detailArray"):
        if field not in payload:
            payload[field] = []
    return payload


def normalise_step_html(text: str) -> str:
    """Source caseStep[i].step / .description come back ALREADY HTML-wrapped
    (verified in recon: `<p>Step 1: Launch the Soterix Partner Portal...</p>`).
    Pass through verbatim if already HTML; wrap plain text in <p>...</p>.
    Mirrors qatouch_c2c_step_split.py's gentle wrap.
    """
    if not text:
        return ""
    t = text.strip()
    if not t:
        return ""
    if t.startswith("<") and t.endswith(">"):
        return t
    return f"<p>{t}</p>"


def extract_sorted_steps(source_edit: dict) -> list[dict]:
    """Return source `caseStep` sorted by `position` ascending. Robust to
    missing/non-integer position (defaults to 0)."""
    raw = source_edit.get("caseStep") or []
    return sorted(raw, key=lambda s: s.get("position", 0) or 0)


# ── Logging ─────────────────────────────────────────────────────────────────
def atomic_write_log(log_path: Path, entries: list[dict]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = log_path.with_suffix(log_path.suffix + ".tmp")
    tmp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    tmp.replace(log_path)


# ── Per-case work ───────────────────────────────────────────────────────────
def process_one(page, record: dict, args) -> dict:
    """Process one target. Returns a log record per the spec."""
    source_key = record["source_key"]
    target_key = record["target_key"]
    target_module = record.get("target_module_name", "?")
    source_title = record.get("source_title", "")

    entry: dict[str, Any] = {
        "source_key": source_key,
        "target_key": target_key,
        "target_module": target_module,
        "source_title": source_title,
        "status": "pending",
        "template_change": None,
        "steps_copied_count": 0,
        "steps_failed_count": 0,
        "errors": [],
    }

    # 1. Read target edit body
    tgt = internal_get_case_edit(page, TARGET_PROJECT, target_key)
    if not tgt or tgt.get("__error"):
        entry["status"] = "failed"
        entry["errors"].append(f"target edit read failed: {tgt}")
        return entry

    # 2. Read source edit body - needed for step content AND for the
    #    idempotency check (we compare counts).
    src = internal_get_case_edit(page, SOURCE_PROJECT, source_key)
    if not src or src.get("__error"):
        entry["status"] = "failed"
        entry["errors"].append(f"source edit read failed: {src}")
        return entry
    time.sleep(INTER_CALL_DELAY)

    source_steps = extract_sorted_steps(src)
    expected_count = len(source_steps)
    target_template = tgt.get("template")
    target_steps_now = tgt.get("caseStep") or []
    target_step_count = len(target_steps_now)

    # 3. Idempotency short-circuit. Under the new ordering:
    #    - already_done: template==2 AND caseStep_len == expected_count.
    #    - template==1 AND caseStep_len==0 AND expected_count>0: normal
    #      full run (the common case for fresh shells).
    #    - template==1 AND caseStep_len>0: impossible per empirical probe
    #      (targets start with caseStep=[]). Defensive: log warning and
    #      delete the stray rows via /v1/steps/delete then proceed.
    already_template = (str(target_template) == str(TEMPLATE_STEPS))
    already_steps = (target_step_count == expected_count and expected_count > 0)

    if already_template and already_steps:
        entry["status"] = "already_done"
        entry["steps_copied_count"] = expected_count
        return entry

    if args.dry_run:
        entry["status"] = "dry_run"
        entry["template_change"] = (
            [target_template, TEMPLATE_STEPS]
            if not already_template else None
        )
        entry["steps_copied_count"] = expected_count
        entry["errors"].append(
            f"would write {expected_count} steps under template="
            f"{target_template} then flip to {TEMPLATE_STEPS} "
            f"(current target rows: {target_step_count})"
        )
        return entry

    # 3b. Defensive cleanup: template==1 with stray step rows shouldn't
    #     happen (targets start caseStep=[]), but if it does, delete the
    #     strays before writing to keep the count clean.
    if not already_template and target_step_count > 0:
        entry["errors"].append(
            f"warning: template=1 but target has {target_step_count} step "
            f"rows (impossible per probe); deleting before write"
        )
        for s in target_steps_now:
            sid = s.get("id")
            if not sid:
                continue
            r = delete_step(page, str(sid))
            if not r.get("ok"):
                entry["errors"].append(
                    f"defensive delete step {sid} failed: "
                    f"status={r.get('status')}"
                )
            time.sleep(INTER_CALL_DELAY)

    # 4. WRITE STEPS FIRST under template=1 (unless --only-template).
    #    Per PROBE 2026-06-25: /v1/steps/save returns 200 under template=1
    #    and the rows are persisted-but-hidden. /v1/case/edit under
    #    template=1 will continue to return caseStep=[] - this is
    #    expected, NOT a save failure. Do NOT re-fetch /v1/case/edit
    #    between saves to verify; verification happens AFTER the flip.
    #
    #    Expected-result strategy: source caseStep[i].description is the
    #    authoritative per-step expected text (JlW1 / USE_JLW1). When
    #    .description is empty (common on steps 2..N - source convention
    #    puts the overall result only on step 1), fall back to literal
    #    DASH_FALLBACK ("-") - validated to pass the server-side
    #    "Please Enter Expected Result" check (probed 2026-06-25). Do NOT
    #    fall back to case-level expectedResult/expectedStep; recon showed
    #    those are not populated for PP cases.
    if not args.only_template:
        for i, s in enumerate(source_steps, 1):
            step_html = normalise_step_html(s.get("step", "") or "")
            expected_html = normalise_step_html(s.get("description", "") or "")
            if not expected_html.strip():
                expected_html = DASH_FALLBACK
            r = save_step(
                page, TARGET_PROJECT, target_key, step_html, expected_html,
            )

            # One retry on 429 with a fat backoff.
            if r.get("rateLimited"):
                print(
                    f"    rate-limited on step {i}/{expected_count} - "
                    f"pausing {RATE_LIMIT_PAUSE}s"
                )
                time.sleep(RATE_LIMIT_PAUSE)
                r = save_step(
                    page, TARGET_PROJECT, target_key, step_html, expected_html,
                )

            if r.get("ok"):
                entry["steps_copied_count"] += 1
            else:
                entry["steps_failed_count"] += 1
                entry["errors"].append(
                    f"step {i} save failed: status={r.get('status')} "
                    f"body={(r.get('body') or '')[:120]}"
                )
            time.sleep(INTER_STEP_DELAY)

    # 5. FLIP TEMPLATE LAST (unless --only-steps). Sends a one-row caseStep
    #    stub to pass the validator; the stub is dropped server-side and
    #    the already-persisted rows surface in the UI.
    flipped_template = False
    if not already_template and not args.only_steps:
        payload = build_template_flip_payload(tgt)
        upd = internal_update_case(page, TARGET_PROJECT, target_key, payload)
        if not update_succeeded(upd):
            entry["status"] = "failed"
            entry["errors"].append(
                f"template flip failed: status={upd.get('status')} "
                f"body={(upd.get('body') or '')[:200]}"
            )
            return entry
        flipped_template = True
        entry["template_change"] = [target_template, TEMPLATE_STEPS]
        time.sleep(INTER_CALL_DELAY)

    # 6. VERIFY by re-fetching /v1/case/edit. Gate flip success on the
    #    post-flip read (not on body-substring alone - 500-on-success
    #    quirk means a real server error is indistinguishable from the
    #    documented quirk by body inspection).
    time.sleep(VERIFY_PAUSE)
    verify = internal_get_case_edit(page, TARGET_PROJECT, target_key)
    if not verify or verify.get("__error"):
        entry["errors"].append(f"verify re-read failed: {verify}")
    else:
        verify_steps = verify.get("caseStep") or []
        final_count = len(verify_steps)
        final_template = verify.get("template")

        # Count check. Under --only-template we expect caseStep empty
        # (stub dropped, no real rows written). Under --only-steps we
        # expect template unchanged (likely still 1, so caseStep stays
        # hidden - count check is meaningless and skipped).
        if args.only_template:
            if str(final_template) != str(TEMPLATE_STEPS):
                entry["errors"].append(
                    f"verify_mismatch: template={final_template} (want "
                    f"{TEMPLATE_STEPS})"
                )
        elif args.only_steps:
            # Cannot meaningfully verify hidden-under-template=1 rows.
            entry["errors"].append(
                f"verify_skipped_only_steps: template={final_template} "
                f"caseStep_len={final_count}"
            )
        else:
            if final_count != expected_count:
                entry["errors"].append(
                    f"verify_mismatch: expected {expected_count} steps, "
                    f"found {final_count}"
                )
            if str(final_template) != str(TEMPLATE_STEPS):
                entry["errors"].append(
                    f"verify_mismatch: template={final_template} (want "
                    f"{TEMPLATE_STEPS})"
                )
            # Content check: compare per-step .step / .description to
            # what we sent. Log mismatches; do not fail (HTML
            # normalisation may not roundtrip byte-identical for nested
            # tables or images, but content is semantically correct).
            for i, sent in enumerate(source_steps):
                if i >= len(verify_steps):
                    break
                sent_step = normalise_step_html(sent.get("step", "") or "")
                sent_desc = normalise_step_html(
                    sent.get("description", "") or ""
                )
                if not sent_desc.strip():
                    sent_desc = DASH_FALLBACK
                got = verify_steps[i] or {}
                got_step = (got.get("step") or "").strip()
                got_desc = (got.get("description") or "").strip()
                if sent_step.strip() != got_step:
                    entry["errors"].append(
                        f"verify_content_mismatch: step {i+1} "
                        f"sent={sent_step[:80]!r} got={got_step[:80]!r}"
                    )
                if sent_desc.strip() != got_desc:
                    entry["errors"].append(
                        f"verify_content_mismatch: step {i+1} expected "
                        f"sent={sent_desc[:80]!r} got={got_desc[:80]!r}"
                    )

    # 7. Final status. verify_content_mismatch entries are warnings only
    #    and do NOT flip status to failed; verify_mismatch (count/template)
    #    does.
    has_count_or_template_mismatch = any(
        e.startswith("verify_mismatch") for e in entry["errors"]
    )
    if (
        entry["steps_failed_count"] == 0
        and not has_count_or_template_mismatch
    ):
        if args.only_template:
            entry["status"] = (
                "template_updated" if flipped_template else "already_done"
            )
        elif args.only_steps:
            entry["status"] = "steps_copied"
        else:
            entry["status"] = "steps_copied"
    else:
        entry["status"] = "failed"
    return entry


# ── Orchestration ───────────────────────────────────────────────────────────
def run(args) -> int:
    auth_state_file = (
        Path(args.auth_state_file) if args.auth_state_file
        else DEFAULT_AUTH_STATE
    )
    resume_input = (
        Path(args.input) if args.input else DEFAULT_RESUME_INPUT
    )

    if not resume_input.exists():
        print(f"ERROR: resume input not found: {resume_input}")
        return 1

    all_records = json.loads(resume_input.read_text(encoding="utf-8"))
    print(f"Loaded {len(all_records)} target records from {resume_input.name}")

    skip_modules = {
        m.strip() for m in (args.skip_modules or "").split(",") if m.strip()
    }
    if skip_modules:
        print(f"Skipping modules: {sorted(skip_modules)}")
        all_records = [
            r for r in all_records
            if r.get("target_module_name") not in skip_modules
        ]
        print(f"  After skip: {len(all_records)} records")

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

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    log_path = LOG_DIR / f"pp_migration_phase_a_steps_{ts}.json"

    print("=" * 70)
    print("  PHASE A - TEMPLATE FLIP + STEP COPY")
    print(f"  source:        {SOURCE_PROJECT}  (NexaiQ-Core)")
    print(f"  target:        {TARGET_PROJECT}  (Partner Admin)")
    print(f"  records:       {total}")
    print(f"  rate-ms:       {args.rate_ms} (inter-case)")
    print(f"  inter-step:    {int(INTER_STEP_DELAY * 1000)}ms")
    print(f"  dry-run:       {args.dry_run}")
    print(f"  only-template: {args.only_template}")
    print(f"  only-steps:    {args.only_steps}")
    print(f"  log:           {log_path.relative_to(ROOT)}")
    print("=" * 70)

    rate_seconds = max(0.0, args.rate_ms / 1000.0)
    log_entries: list[dict] = []
    counters = {
        "steps_copied": 0,
        "template_updated": 0,
        "already_done": 0,
        "failed": 0,
        "dry_run": 0,
    }

    with sync_playwright() as p:
        browser, ctx, page = open_browser(p, auth_state_file)
        try:
            for idx, rec in enumerate(all_records, 1):
                entry = process_one(page, rec, args)
                log_entries.append(entry)
                counters[entry["status"]] = (
                    counters.get(entry["status"], 0) + 1
                )

                # Per-case progress line
                tc = entry.get("template_change")
                tc_str = (
                    f"template:{tc[0]}->{tc[1]} " if tc else ""
                )
                title_short = (entry.get("source_title") or "")[:50]
                step_str = (
                    f"+{entry['steps_copied_count']}steps"
                    if entry["steps_copied_count"] else ""
                )
                err_str = (
                    f" errs={len(entry['errors'])}"
                    if entry["errors"] and entry["status"] != "dry_run"
                    else ""
                )
                print(
                    f"  [{idx}/{total}] {entry['target_module']}: "
                    f"{title_short} -> {entry['status']} "
                    f"({tc_str}{step_str}){err_str}"
                )

                # Per-case atomic log write - survive a crash.
                atomic_write_log(log_path, log_entries)

                # Periodic rollup
                if idx % 25 == 0 or idx == total:
                    print(
                        f"    --- rollup @ {idx}/{total}: "
                        f"steps_copied={counters['steps_copied']} "
                        f"template_updated={counters['template_updated']} "
                        f"already_done={counters['already_done']} "
                        f"failed={counters['failed']} "
                        f"dry_run={counters['dry_run']}"
                    )

                if idx < total:
                    time.sleep(rate_seconds)
        finally:
            try:
                # Re-save storage state in case XSRF rotated mid-run.
                ctx.storage_state(path=str(auth_state_file))
            except Exception:
                pass
            browser.close()

    # ── Summary ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  PHASE A STEPS - SUMMARY")
    print(f"  Total processed:   {total}")
    print(f"  Steps copied:      {counters['steps_copied']}")
    print(f"  Template only:     {counters['template_updated']}")
    print(f"  Already done:      {counters['already_done']}")
    print(f"  Failed:            {counters['failed']}")
    print(f"  Dry-run:           {counters['dry_run']}")
    print(f"  Log written to:    {log_path.relative_to(ROOT)}")
    print("=" * 70)

    return 0 if counters["failed"] == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Phase A continuation - flip target template to 2 and copy "
            "source step rows for the 214 already-migrated Partner Portal "
            "cases."
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
        help="Print plan + counts per case; no writes.",
    )
    ap.add_argument(
        "--resume-from", type=int, default=0,
        help="Skip the first N records of the input list.",
    )
    ap.add_argument(
        "--skip-modules", default="",
        help=(
            "Comma-separated list of target_module_name values to skip "
            "(e.g. 'Admin > Audit Trail')."
        ),
    )
    ap.add_argument(
        "--auth-state-file", default=str(DEFAULT_AUTH_STATE),
        help=f"Playwright storage state file (default: {DEFAULT_AUTH_STATE}).",
    )
    ap.add_argument(
        "--rate-ms", type=int, default=1300,
        help="Milliseconds between cases (default 1300).",
    )
    ap.add_argument(
        "--only-template", action="store_true",
        help=(
            "Flip template to 2 (sends stub row to pass validator). "
            "Steps tab will render but be empty. Use only to repair "
            "prior partial runs."
        ),
    )
    ap.add_argument(
        "--only-steps", action="store_true",
        help=(
            "Write source steps under current template without flipping. "
            "If target is already template=2 the writes are visible "
            "immediately; if template=1 they persist but stay hidden "
            "until a later flip."
        ),
    )
    args = ap.parse_args()

    if args.only_template and args.only_steps:
        print("ERROR: --only-template and --only-steps are mutually exclusive")
        return 2

    return run(args)


if __name__ == "__main__":
    sys.exit(main())
