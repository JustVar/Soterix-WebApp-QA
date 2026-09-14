"""C2C OTA Step Cleanup - replace merged single-step rows with proper per-step arrays.

CONTEXT
-------
The 85 OTA cases in project 60W5 (C2C) were imported from CSV with all steps merged
into a single QA Touch step row (e.g. one cell containing "1. Login... 2. Navigate..."
). Metadata (refs/tags/type/priority/mode/desc) was already backfilled by a sibling
tool. This script replaces the merged step rows with proper structured per-step rows
so the QA Touch UI renders each step individually.

Source of truth for the per-step content: tools/.ota_update_payloads_v2.json
(each entry has caseKey + a pre-built `steps` array of {position, step,
description, from_reusable_step}, where `step` is the step description HTML and
`description` is the expected_result HTML).

API STRATEGY (CRITICAL)
-----------------------
We use the dedicated /v1/steps/* endpoints - NOT /v1/case/update. Earlier work
proved that wholesale caseStep replacement via /v1/case/update returns HTTP 500
and corrupts case state. The /v1/steps/* endpoints are the path the UI uses and
were confirmed working by tools/qatouch_c2c_step_split.py on the C2C Hardware set.

  LIST current steps:  POST /v1/case/edit/p/{pid}/cid/{case_key}
                       -> data.caseStep[] -> take .id from each
  DELETE step:         GET  /v1/steps/delete/mid/{step_id}?type=true
  ADD step:            POST /v1/steps/save
                       body: {cid, pid, step_description, expected_result}

TEST-ONE-FIRST PROTOCOL (MANDATORY)
-----------------------------------
This is the riskiest of the six metadata/step streams. DO NOT run on all 85
cases without first verifying on one case:

    python tools/cleanup_ota_steps.py --only C2C_OTA_036

C2C_OTA_036 (caseKey NjL3xy) is the canary. After it runs, OPEN THAT CASE IN
THE QA TOUCH UI and confirm:
  - The merged step row is gone
  - Each authored step appears as its own row in the correct order
  - Expected results align with the right step
  - Step count matches the payload's `steps` array length

Only after manual UI verification on the canary should the full run proceed
(remove --only and optionally use --limit to ramp up).

USAGE
-----
  # canary - test on C2C_OTA_036 only
  python tools/cleanup_ota_steps.py --only C2C_OTA_036

  # preview without writes
  python tools/cleanup_ota_steps.py --dry-run

  # process a few to spot-check after canary
  python tools/cleanup_ota_steps.py --limit 5

  # full run (only after canary + spot-check pass)
  python tools/cleanup_ota_steps.py

  # multiple refs
  python tools/cleanup_ota_steps.py --only C2C_OTA_001,C2C_OTA_002

OUTPUT
------
logs/ota_step_cleanup_log.json - one entry per processed case:
  {case_key, ref, old_step_count, new_step_count, status, error, deleted, created}

status values: ok | partial | verify_mismatch | error | skipped | dry_run
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

_print = print
print = functools.partial(_print, flush=True)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / '.env')
except ImportError:
    pass

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print('ERROR: playwright required. pip install playwright && playwright install chromium')
    sys.exit(1)


# ---------------------------------------------------------------------------
# Constants - OTA stream, project 60W5
# ---------------------------------------------------------------------------
BASE_URL = 'https://soterixsystems.qatouch.com'
PROJECT_KEY = '60W5'

PAYLOAD_FILE = ROOT / 'tools' / '.ota_update_payloads_v2.json'
DEFAULT_AUTH_STATE_FILE = ROOT / 'tools' / '.qatouch_auth_state.json'
LOG_DIR = ROOT / 'logs'
LOG_FILE = LOG_DIR / 'ota_step_cleanup_log.json'

# Rate limiting - step CRUD is heavier than metadata update, 800ms between calls.
INTER_CALL_DELAY = 0.8      # between every individual API call
INTER_CASE_DELAY = 1.0      # between cases (additional pad)
RATE_LIMIT_PAUSE = 20.0     # back off on HTTP 429
VERIFY_PAUSE = 1.0          # before re-fetching for verification


# ---------------------------------------------------------------------------
# Payload loading
# ---------------------------------------------------------------------------
def load_payloads() -> list[dict]:
    """Load the 85 OTA case payloads.

    Each entry has at minimum: _ref, caseKey, steps[]. The `steps` array is the
    desired final state - already HTML-wrapped, already positioned.
    """
    if not PAYLOAD_FILE.exists():
        raise SystemExit(f'Payload file not found: {PAYLOAD_FILE}')
    with open(PAYLOAD_FILE, encoding='utf-8') as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise SystemExit(f'Expected list in {PAYLOAD_FILE}, got {type(data).__name__}')
    return data


def filter_payloads(payloads: list[dict], only: str | None, limit: int | None) -> list[dict]:
    """Apply --only (comma-separated refs) and --limit filters."""
    out = payloads
    if only:
        wanted = {r.strip() for r in only.split(',') if r.strip()}
        out = [p for p in out if p.get('_ref') in wanted or p.get('reference') in wanted]
        missing = wanted - {p.get('_ref') for p in out} - {p.get('reference') for p in out}
        if missing:
            print(f'  WARNING: --only refs not found in payload: {sorted(missing)}')
    if limit is not None and limit > 0:
        out = out[:limit]
    return out


# ---------------------------------------------------------------------------
# Auth / Playwright
# ---------------------------------------------------------------------------
def login(p, auth_state_file: str):
    """Open Chromium, reuse auth state if valid, else prompt manual login.

    The shared auth state at tools/.qatouch_auth_state.json may be stale. We
    detect that, drop it, and ask the operator to log in interactively. The
    refreshed state is then written back to the same file for the next run.
    """
    browser = p.chromium.launch(headless=False, slow_mo=50)

    if os.path.exists(auth_state_file):
        print(f'  Loading saved auth state from {auth_state_file}...')
        ctx = browser.new_context(
            storage_state=auth_state_file,
            viewport={'width': 1400, 'height': 900},
        )
        page = ctx.new_page()
        page.goto(f'{BASE_URL}/v2#/new-projects', timeout=60000)
        time.sleep(5)
        if _is_logged_in(page):
            print('  Auth state valid.')
            return browser, ctx, page
        print('  Auth state STALE - please refresh by logging in manually.')
        ctx.close()
        try:
            os.remove(auth_state_file)
        except OSError:
            pass

    ctx = browser.new_context(viewport={'width': 1400, 'height': 900})
    page = ctx.new_page()
    page.goto(f'{BASE_URL}/login', timeout=60000)

    print()
    print('=' * 60)
    print('  BROWSER OPENED - Please log in to QA Touch')
    print('  Waiting up to 300 seconds...')
    print('=' * 60)

    for _ in range(100):
        time.sleep(3)
        if _is_logged_in(page):
            print('  Login detected.')
            time.sleep(2)
            ctx.storage_state(path=auth_state_file)
            print(f'  Refreshed auth state written to {auth_state_file}')
            return browser, ctx, page

    browser.close()
    raise SystemExit('Login timeout after 300s')


def _is_logged_in(page) -> bool:
    url = page.url or ''
    if any(x in url for x in ['/dashboard', '/project', '/testCase',
                              '/modules', '/new-projects', '/case/list']):
        return True
    for sel in ['text="Dashboard"', 'text="Project List"']:
        try:
            if page.locator(sel).first.is_visible(timeout=500):
                return True
        except Exception:
            pass
    return False


# ---------------------------------------------------------------------------
# QA Touch internal API
# ---------------------------------------------------------------------------
def get_step_ids(page, case_key: str) -> list[str]:
    """Fetch current step IDs via /v1/case/edit.

    Returns step row IDs in their current order. We need the IDs to delete
    each row before we add the structured replacements.
    """
    result = page.evaluate("""
        async ([pid, caseKey]) => {
            try {
                const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
                const resp = await fetch('/v1/case/edit/p/' + pid + '/cid/' + caseKey, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-XSRF-TOKEN': decodeURIComponent(token || '')
                    },
                    body: JSON.stringify({})
                });
                if (!resp.ok) return { error: 'HTTP ' + resp.status, ids: [] };
                const data = await resp.json();
                const steps = data && data.data && data.data.caseStep ? data.data.caseStep : [];
                return { ids: steps.map(s => s.id).filter(Boolean), count: steps.length };
            } catch (e) {
                return { error: e.message, ids: [] };
            }
        }
    """, [PROJECT_KEY, case_key])
    if result.get('error'):
        print(f'    ERROR get_step_ids: {result["error"]}')
        return []
    return result.get('ids', [])


def delete_step(page, step_id: str) -> bool:
    """Delete a single step row by ID."""
    result = page.evaluate("""
        async (stepId) => {
            try {
                const resp = await fetch('/v1/steps/delete/mid/' + stepId + '?type=true');
                return { ok: resp.ok, status: resp.status };
            } catch (e) {
                return { ok: false, error: e.message };
            }
        }
    """, step_id)
    return result.get('ok', False)


def create_step(page, case_key: str, step_html: str, expected_html: str) -> dict:
    """Create a new step row.

    The payload's `step` and `description` fields are already HTML-wrapped
    (<p>...</p>) so we pass them through verbatim - qatouch_c2c_step_split
    wraps plain text in <p>...</p>, but the OTA payload v2 builder already
    did that for us.
    """
    return page.evaluate("""
        async ([pid, cid, desc, exp]) => {
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
                    body: body.substring(0, 300),
                };
            } catch (e) {
                return { ok: false, error: e.message };
            }
        }
    """, [PROJECT_KEY, case_key, step_html, expected_html])


# ---------------------------------------------------------------------------
# Per-case sync
# ---------------------------------------------------------------------------
def process_case(page, entry: dict, dry_run: bool) -> dict:
    """Replace the merged step row on one case with the structured array.

    Sequence:
      1. Fetch current step IDs (old_step_count = len)
      2. Delete every existing step row
      3. POST one new step per entry in payload.steps (in `position` order)
      4. Re-fetch and confirm new_step_count == expected
    """
    ref = entry.get('_ref') or entry.get('reference') or '<unknown>'
    case_key = entry.get('caseKey')
    steps = sorted(entry.get('steps', []), key=lambda s: s.get('position', 0))
    expected_count = len(steps)

    record = {
        'case_key': case_key,
        'ref': ref,
        'old_step_count': None,
        'new_step_count': None,
        'deleted': 0,
        'created': 0,
        'status': 'pending',
        'error': '',
        'timestamp': datetime.utcnow().isoformat() + 'Z',
    }

    if not case_key:
        record['status'] = 'error'
        record['error'] = 'missing caseKey in payload entry'
        return record

    if dry_run:
        record['status'] = 'dry_run'
        record['new_step_count'] = expected_count
        return record

    # 1. List current steps
    old_ids = get_step_ids(page, case_key)
    record['old_step_count'] = len(old_ids)
    time.sleep(INTER_CALL_DELAY)

    # 2. Delete each existing step row
    for sid in old_ids:
        if delete_step(page, sid):
            record['deleted'] += 1
        else:
            # Don't abort - try to continue. Verification step will catch state.
            print(f'    WARN: delete failed for step {sid}')
        time.sleep(INTER_CALL_DELAY)

    # 3. Create the structured replacements in `position` order
    for i, s in enumerate(steps, 1):
        step_html = s.get('step', '') or ''
        expected_html = s.get('description', '') or ''
        r = create_step(page, case_key, step_html, expected_html)

        if r.get('rateLimited'):
            print(f'    Rate limited! Pausing {RATE_LIMIT_PAUSE}s...')
            time.sleep(RATE_LIMIT_PAUSE)
            r = create_step(page, case_key, step_html, expected_html)

        if r.get('ok'):
            record['created'] += 1
        else:
            err = r.get('error') or f'HTTP {r.get("status")}'
            if record['status'] == 'pending':
                record['status'] = 'partial'
                record['error'] = f'step {i} failed: {err}'
        time.sleep(INTER_CALL_DELAY)

    # 4. Verify
    time.sleep(VERIFY_PAUSE)
    new_ids = get_step_ids(page, case_key)
    record['new_step_count'] = len(new_ids)

    if record['status'] == 'pending':
        if len(new_ids) == expected_count:
            record['status'] = 'ok'
        else:
            record['status'] = 'verify_mismatch'
            record['error'] = (f'expected {expected_count} steps after replace, '
                               f'found {len(new_ids)}')

    return record


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
def write_log(records: list[dict]):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'project': PROJECT_KEY,
        'total_processed': len(records),
        'counts_by_status': {},
        'records': records,
    }
    for r in records:
        s = r.get('status', 'unknown')
        summary['counts_by_status'][s] = summary['counts_by_status'].get(s, 0) + 1

    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f'\nLog written: {LOG_FILE}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='Replace merged single-step rows on C2C OTA cases with '
                    'structured per-step arrays. Run --only C2C_OTA_036 FIRST '
                    'and verify the result in the QA Touch UI before scaling up.',
    )
    parser.add_argument('--limit', type=int, default=None,
                        help='Process only the first N matching cases')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would happen; no writes')
    parser.add_argument('--only', type=str, default=None,
                        help='Comma-separated refs to process (e.g. '
                             'C2C_OTA_036,C2C_OTA_001)')
    parser.add_argument('--auth-state-file', type=str,
                        default=str(DEFAULT_AUTH_STATE_FILE),
                        help='Path to Playwright auth state JSON '
                             '(default: tools/.qatouch_auth_state.json)')
    args = parser.parse_args()

    payloads = load_payloads()
    print(f'Loaded {len(payloads)} OTA payloads from {PAYLOAD_FILE.name}')

    targets = filter_payloads(payloads, args.only, args.limit)
    print(f'Targets after filtering: {len(targets)} case(s)')
    if not targets:
        print('Nothing to do.')
        return

    # Loud canary reminder
    if not args.only and not args.dry_run and len(targets) > 5:
        print()
        print('=' * 70)
        print(f'  HEADS UP: about to process {len(targets)} cases.')
        print('  If you have NOT yet verified the canary (C2C_OTA_036, caseKey')
        print('  NjL3xy) in the QA Touch UI, cancel now (Ctrl-C) and run:')
        print()
        print('      python tools/cleanup_ota_steps.py --only C2C_OTA_036')
        print()
        print('  then visually confirm the case before proceeding.')
        print('=' * 70)
        print('  Sleeping 10s - press Ctrl-C to abort.')
        try:
            time.sleep(10)
        except KeyboardInterrupt:
            print('\nAborted.')
            return

    records: list[dict] = []

    with sync_playwright() as p:
        if args.dry_run:
            # Dry run still loads payloads but skips auth/browser.
            print('DRY-RUN - skipping browser/auth.')
            for i, entry in enumerate(targets, 1):
                rec = process_case(None, entry, dry_run=True)
                records.append(rec)
                print(f'  [{i:2}/{len(targets)}] {rec["ref"]} '
                      f'({rec["case_key"]}) -> would replace with '
                      f'{rec["new_step_count"]} steps')
            write_log(records)
            return

        browser, _ctx, page = login(p, args.auth_state_file)
        try:
            for i, entry in enumerate(targets, 1):
                ref = entry.get('_ref', '?')
                ck = entry.get('caseKey', '?')
                print(f'[{i:2}/{len(targets)}] {ref} ({ck})')
                rec = process_case(page, entry, dry_run=False)
                records.append(rec)
                print(f'         {rec["status"].upper()}: '
                      f'deleted={rec["deleted"]}, '
                      f'created={rec["created"]}/'
                      f'{len([s for s in entry.get("steps", [])])}, '
                      f'before={rec["old_step_count"]} '
                      f'after={rec["new_step_count"]}'
                      + (f'  ({rec["error"]})' if rec.get('error') else ''))
                # Write log after each case so a crash mid-run doesn't lose data
                write_log(records)
                time.sleep(INTER_CASE_DELAY)
        finally:
            browser.close()

    # Final summary
    print('\n=== Summary ===')
    counts: dict[str, int] = {}
    for r in records:
        counts[r['status']] = counts.get(r['status'], 0) + 1
    for k, v in counts.items():
        print(f'  {k}: {v}')


if __name__ == '__main__':
    main()
