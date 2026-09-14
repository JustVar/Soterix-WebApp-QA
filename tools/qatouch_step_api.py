"""QA Touch Step API Sync - fix broken step pairing via internal web API.

The QA Touch bulk CSV import broke step/expected-result pairing (steps and expected
results became separate rows). This tool uses Playwright for authentication only,
then calls QA Touch's internal web API via page.evaluate() for all operations:

  GET step IDs:  POST /v1/case/edit/p/{pid}/cid/{key} -> data.caseStep[].id
  Delete step:   GET /v1/steps/delete/mid/{stepId}?type=true
  Create step:   POST /v1/steps/save {cid, pid, step_description, expected_result}

No UI navigation required. Processes ~2-3 cases/second.

Usage:
  python tools/qatouch_step_api.py test                            # Test on TC0001
  python tools/qatouch_step_api.py sync                            # Sync all 3,011 cases
  python tools/qatouch_step_api.py sync --dry-run                  # Preview without changes
  python tools/qatouch_step_api.py sync --batch 1/4                # Process batch 1 of 4
  python tools/qatouch_step_api.py sync --cases 5BRMnj 21zWnm     # Specific cases only
  python tools/qatouch_step_api.py sync --resume                   # Skip already-synced
  python tools/qatouch_step_api.py verify                          # Verify 20 random synced cases
  python tools/qatouch_step_api.py verify --sample 50              # Verify 50 random cases
  python tools/qatouch_step_api.py verify --cases 5BRMnj 21zWnm   # Verify specific cases
"""
from __future__ import annotations

import argparse
import csv
import functools
import html as html_mod
import json
import os
import signal
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

from dotenv import load_dotenv

load_dotenv(ROOT / '.env')

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print('ERROR: playwright required. Install with: pip install playwright && playwright install chromium')
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = 'https://soterixsystems.qatouch.com'
PROJECT_KEY = 'JlW1'

CSV_FILES = [
    os.path.expanduser('~/Downloads/QATouch_BulkUpdate_Part1.csv'),
    os.path.expanduser('~/Downloads/QATouch_BulkUpdate_Part2.csv'),
    os.path.expanduser('~/Downloads/QATouch_BulkUpdate_Part3.csv'),
]

CHECKPOINT_FILE = str(ROOT / 'config' / 'step_api_sync_checkpoint.json')
AUTH_STATE_FILE = str(ROOT / 'tools' / '.qatouch_auth_state.json')

# Timing - keep conservative to avoid rate limiting
INTER_CALL_DELAY = 0.15   # between individual API calls
INTER_CASE_DELAY = 0.3    # between cases
RATE_LIMIT_PAUSE = 15.0   # pause after hitting rate limit
BURST_PAUSE = 10.0        # pause every N cases
BURST_THRESHOLD = 25      # trigger burst pause every N cases


# ---------------------------------------------------------------------------
# CSV Loading
# ---------------------------------------------------------------------------
def load_csv_steps() -> dict[str, dict]:
    """Load all 3 CSV files and return {case_key: {steps: [...]}}.

    Steps and expected results are newline-separated in the CSV. They are
    positionally paired: step[0] goes with expected[0], etc.
    """
    cases = {}
    for csv_path in CSV_FILES:
        if not os.path.exists(csv_path):
            print(f'  WARNING: CSV not found: {csv_path}')
            continue
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for row in reader:
                if len(row) < 13:
                    continue
                case_key = row[0].strip()
                if not case_key:
                    continue
                raw_steps = row[11].split('\n') if row[11].strip() else []
                raw_expected = row[12].split('\n') if row[12].strip() else []

                max_len = max(len(raw_steps), len(raw_expected))
                steps = []
                for i in range(max_len):
                    step_text = raw_steps[i].strip() if i < len(raw_steps) else ''
                    exp_text = raw_expected[i].strip() if i < len(raw_expected) else ''
                    if not step_text and not exp_text:
                        continue
                    if not step_text:
                        continue
                    steps.append({
                        'step': step_text,
                        'expected': exp_text if exp_text else 'Step completed successfully',
                    })

                if steps:
                    cases[case_key] = {'steps': steps}
    return cases


# ---------------------------------------------------------------------------
# Checkpoint Management
# ---------------------------------------------------------------------------
def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, encoding='utf-8') as f:
            return json.load(f)
    return {'synced': {}, 'errors': {}}


def save_checkpoint(cp: dict):
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    with open(CHECKPOINT_FILE, 'w', encoding='utf-8') as f:
        json.dump(cp, f, indent=2)


# ---------------------------------------------------------------------------
# HTML Escaping for step content
# ---------------------------------------------------------------------------
def escape_for_html(text: str) -> str:
    """Safely prepare text for embedding in <p> tags.

    First unescapes any pre-existing HTML entities (e.g. &gt; from CSV data),
    then re-escapes &, <, > for safe HTML embedding.
    """
    plain = html_mod.unescape(text)          # &gt; -> >, &amp; -> &
    return html_mod.escape(plain, quote=False)  # & -> &amp;, < -> &lt;, > -> &gt;


# ---------------------------------------------------------------------------
# Playwright Login
# ---------------------------------------------------------------------------
def login(p):
    """Launch browser, authenticate, return (browser, context, page)."""
    browser = p.chromium.launch(headless=False, slow_mo=50)

    if os.path.exists(AUTH_STATE_FILE):
        print('  Loading saved auth state...')
        ctx = browser.new_context(
            storage_state=AUTH_STATE_FILE,
            viewport={'width': 1400, 'height': 900},
        )
        page = ctx.new_page()
        page.goto(f'{BASE_URL}/v2#/new-projects', timeout=60000)
        time.sleep(5)
        if _is_logged_in(page, deep_check=True):
            print('  Auth state valid!')
            return browser, ctx, page
        print('  Auth expired -- need fresh login.')
        ctx.close()
        try:
            os.remove(AUTH_STATE_FILE)
        except OSError:
            pass

    ctx = browser.new_context(viewport={'width': 1400, 'height': 900})
    page = ctx.new_page()
    page.goto(f'{BASE_URL}/login', timeout=60000)

    print()
    print('=' * 60)
    print('  BROWSER OPENED -- Please log in to QA Touch')
    print('  Waiting up to 300 seconds...')
    print('=' * 60)

    for _ in range(100):
        time.sleep(3)
        if _is_logged_in(page):
            print('  Login detected!')
            time.sleep(2)
            ctx.storage_state(path=AUTH_STATE_FILE)
            return browser, ctx, page

    browser.close()
    raise SystemExit('Login timeout after 300s')


def _is_logged_in(page, deep_check: bool = False) -> bool:
    """Check if user is logged in.

    When deep_check=True (used for saved auth validation), makes an actual
    API call to confirm the session is alive - not just URL/DOM heuristics.
    """
    url = page.url or ''
    url_match = any(x in url for x in ['/dashboard', '/project', '/testCase',
                                        '/modules', '/new-projects', '/case/list'])
    if not url_match:
        # Check DOM as fallback
        for sel in ['text="NexaiQ-Core"', 'text="Dashboard"', 'text="Project List"']:
            try:
                if page.locator(sel).first.is_visible(timeout=500):
                    url_match = True
                    break
            except Exception:
                pass
    if not url_match:
        return False
    if not deep_check:
        return True
    # Deep check: make a real API call to confirm session is alive
    try:
        result = page.evaluate("""
            async () => {
                try {
                    const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
                    const resp = await fetch('/v1/case/edit/p/JlW1/cid/0rzJ8Q', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Accept': 'application/json',
                            'X-XSRF-TOKEN': decodeURIComponent(token || '')
                        },
                        body: JSON.stringify({})
                    });
                    if (!resp.ok) return false;
                    const data = await resp.json();
                    return !!(data && data.data && data.data.caseStep);
                } catch (e) { return false; }
            }
        """)
        return result is True
    except Exception:
        return False


def enter_project(page):
    """Make sure we're inside the NexaiQ-Core project."""
    page.goto(f'{BASE_URL}/v2#/new-projects', timeout=30000)
    time.sleep(3)
    try:
        proj = page.locator('text="NexaiQ-Core"').first
        if proj.is_visible(timeout=5000):
            proj.click()
            time.sleep(3)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Internal API calls via page.evaluate()
# ---------------------------------------------------------------------------
def get_step_ids(page, case_key: str) -> list[str]:
    """Get step IDs for a case via POST /v1/case/edit/p/{pid}/cid/{key}.

    Returns list of step ID strings (e.g. ['l2QanJ', 'rQ7aM0', ...]).
    """
    result = page.evaluate("""
        async (caseKey) => {
            try {
                const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
                const resp = await fetch('/v1/case/edit/p/JlW1/cid/' + caseKey, {
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
    """, case_key)
    if result.get('error'):
        return []
    return result.get('ids', [])


def delete_step(page, step_id: str) -> bool:
    """Delete a step by its internal ID."""
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


def create_step(page, cid: str, step_desc: str, expected: str) -> dict:
    """Create a step with correct pairing. Returns {ok, status, rateLimited}."""
    safe_desc = escape_for_html(step_desc)
    safe_exp = escape_for_html(expected)

    # Use argument passing instead of f-string to avoid injection issues
    return page.evaluate("""
        async ([cid, desc, exp]) => {
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
                        pid: 'JlW1',
                        step_description: '<p>' + desc + '</p>',
                        expected_result: '<p>' + exp + '</p>'
                    })
                });
                const body = await resp.text();
                let bodyJson = null;
                try { bodyJson = JSON.parse(body); } catch(e) {}
                return {
                    ok: resp.ok,
                    status: resp.status,
                    rateLimited: resp.status === 429,
                    body: body.substring(0, 500),
                    bodyJson: bodyJson
                };
            } catch (e) {
                return { ok: false, error: e.message };
            }
        }
    """, [cid, safe_desc, safe_exp])


# ---------------------------------------------------------------------------
# Per-Case Sync Logic
# ---------------------------------------------------------------------------
def sync_case(page, case_key: str, steps: list[dict], dry_run: bool = False,
              verbose: bool = False) -> dict:
    """Delete old steps and create correct ones for a single case.

    Returns {'status': 'ok'|'error'|'partial', 'deleted': N, 'created': N, 'error': ''}
    """
    result = {'status': 'ok', 'deleted': 0, 'created': 0, 'error': ''}

    if dry_run:
        result['created'] = len(steps)
        return result

    # 1. Get existing step IDs
    step_ids = get_step_ids(page, case_key)
    if step_ids is None:
        result['status'] = 'error'
        result['error'] = 'Failed to get step IDs'
        return result

    # 2. Delete all existing steps
    for sid in step_ids:
        if delete_step(page, sid):
            result['deleted'] += 1
        time.sleep(INTER_CALL_DELAY)

    # 3. Create new steps with correct pairing
    for i, s in enumerate(steps, 1):
        r = create_step(page, case_key, s['step'], s['expected'])
        if r.get('rateLimited'):
            print(f'    Rate limited! Pausing {RATE_LIMIT_PAUSE}s...')
            time.sleep(RATE_LIMIT_PAUSE)
            r = create_step(page, case_key, s['step'], s['expected'])
        if r.get('ok'):
            result['created'] += 1
            if verbose:
                body = r.get('body', '')[:200]
                print(f'    step {i}: OK (HTTP {r.get("status")}) body={body}')
        else:
            err = r.get('error', f'HTTP {r.get("status")}')
            if verbose:
                print(f'    step {i}: FAIL ({err}) body={r.get("body", "")[:200]}')
            if result['status'] == 'ok':
                result['status'] = 'partial'
                result['error'] = f'Step {result["created"] + 1} failed: {err}'
        time.sleep(INTER_CALL_DELAY)

    # Post-create verification
    if not dry_run and result['created'] > 0:
        time.sleep(0.5)
        verify_ids = get_step_ids(page, case_key)
        if verify_ids is not None and len(verify_ids) != len(steps):
            if verbose:
                print(f'    VERIFY: expected {len(steps)} steps, found {len(verify_ids)}')
            result['status'] = 'verify_mismatch'
            result['error'] = f'Created {result["created"]} but only {len(verify_ids)} persisted'

    if result['status'] == 'ok' and result['created'] != len(steps):
        result['status'] = 'partial'
        result['error'] = f'Only {result["created"]}/{len(steps)} steps created'

    return result


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_test(page):
    """Test the full delete+create flow on TC0001 (5BRMnj)."""
    test_key = '5BRMnj'
    print(f'\n=== TEST: case {test_key} ===\n')

    all_cases = load_csv_steps()
    if test_key not in all_cases:
        print(f'ERROR: Case {test_key} not found in CSV files.')
        return

    csv_steps = all_cases[test_key]['steps']
    print(f'CSV has {len(csv_steps)} steps:')
    for i, s in enumerate(csv_steps, 1):
        print(f'  {i}. {s["step"][:80]}')
        print(f'     => {s["expected"][:80]}')

    # Get current step IDs
    print('\n--- Get existing step IDs ---')
    step_ids = get_step_ids(page, test_key)
    print(f'  Found {len(step_ids)} existing steps: {step_ids}')

    # Delete all
    print(f'\n--- Delete {len(step_ids)} steps ---')
    deleted = 0
    for sid in step_ids:
        ok = delete_step(page, sid)
        print(f'  {sid}: {"OK" if ok else "FAIL"}')
        if ok:
            deleted += 1
        time.sleep(INTER_CALL_DELAY)

    # Create new
    print(f'\n--- Create {len(csv_steps)} steps ---')
    created = 0
    for i, s in enumerate(csv_steps, 1):
        r = create_step(page, test_key, s['step'], s['expected'])
        print(f'  {i}. {"OK" if r.get("ok") else "FAIL"} -- {s["step"][:60]}')
        if r.get('ok'):
            created += 1
        time.sleep(INTER_CALL_DELAY)

    # Verify
    print('\n--- Verify ---')
    time.sleep(1)
    new_ids = get_step_ids(page, test_key)
    print(f'  New step count: {len(new_ids)} (expected {len(csv_steps)})')
    print(f'  Deleted: {deleted}, Created: {created}/{len(csv_steps)}')
    print(f'  Result: {"PASS" if len(new_ids) == len(csv_steps) else "MISMATCH"}')


def run_audit(page, all_cases: dict, checkpoint: dict, sample_size: int = 10,
              label: str = '') -> bool:
    """Verify a random sample of synced cases have correct step counts.

    Returns True if all samples pass, False if any mismatch found.
    """
    import random
    synced_keys = list(checkpoint.get('synced', {}).keys())
    if not synced_keys:
        print('  [audit] No synced cases to verify')
        return True

    sample = random.sample(synced_keys, min(sample_size, len(synced_keys)))
    print(f'\n  {"=" * 50}')
    print(f'  AUDIT{" - " + label if label else ""}: verifying {len(sample)} cases')
    print(f'  {"=" * 50}')

    pass_count = 0
    fail_count = 0
    zero_count = 0
    for key in sample:
        expected = len(all_cases[key]['steps']) if key in all_cases else 0
        actual_ids = get_step_ids(page, key)
        actual = len(actual_ids)
        status = 'PASS' if actual == expected else 'FAIL'
        if status == 'PASS':
            pass_count += 1
        else:
            fail_count += 1
            if actual == 0 and expected > 0:
                zero_count += 1
        print(f'    {key}: expected={expected} actual={actual} {status}')
        time.sleep(INTER_CALL_DELAY)

    print(f'  Result: {pass_count}/{len(sample)} passed, {fail_count} failed')
    print(f'  {"=" * 50}\n')

    if fail_count > 0:
        if zero_count == fail_count and zero_count >= 3:
            print(f'  SESSION EXPIRED: all {zero_count} failures returned 0 steps.')
            print('  This is a dead session, not missing data.')
            print('  Delete auth state and re-run with fresh login:')
            print('    del tools\\.qatouch_auth_state.json')
        else:
            print(f'  WARNING: {fail_count} case(s) failed audit!')
        print('  Sync will PAUSE. Investigate before continuing with --resume.')
        return False
    return True


def cmd_verify(page, cases_arg: list[str] | None, sample_size: int):
    """Standalone verify command - check synced cases against CSV expected counts."""
    all_cases = load_csv_steps()
    checkpoint = load_checkpoint()
    synced = checkpoint.get('synced', {})

    if cases_arg:
        # Verify specific cases
        keys_to_check = cases_arg
    elif synced:
        # Verify a sample of synced cases
        import random
        keys_to_check = random.sample(list(synced.keys()), min(sample_size, len(synced)))
    else:
        print('No synced cases found in checkpoint. Nothing to verify.')
        return

    print(f'\n=== VERIFY: {len(keys_to_check)} cases ===\n')

    pass_count = 0
    fail_count = 0
    for key in keys_to_check:
        expected = len(all_cases[key]['steps']) if key in all_cases else -1
        actual_ids = get_step_ids(page, key)
        actual = len(actual_ids)
        status = 'PASS' if actual == expected else 'FAIL'
        if status == 'PASS':
            pass_count += 1
        else:
            fail_count += 1
        print(f'  {key}: expected={expected} actual={actual} {status}')
        time.sleep(INTER_CALL_DELAY)

    print(f'\n  Passed: {pass_count}/{len(keys_to_check)}')
    print(f'  Failed: {fail_count}')
    if fail_count > 0:
        print(f'  Re-sync failed cases with: sync --cases {" ".join(k for k in keys_to_check if len(get_step_ids(page, k)) != len(all_cases.get(k, {}).get("steps", [])))}')


def cmd_sync(page, dry_run: bool, batch: str | None, cases: list[str] | None,
             resume: bool, verbose: bool = False):
    """Sync steps for all (or selected) cases."""
    all_cases = load_csv_steps()
    print(f'\nLoaded {len(all_cases)} cases from CSV files')

    if cases:
        target_keys = [k for k in cases if k in all_cases]
        missing = [k for k in cases if k not in all_cases]
        if missing:
            print(f'  WARNING: {len(missing)} case(s) not in CSV: {", ".join(missing[:10])}')
    else:
        target_keys = sorted(all_cases.keys())

    if batch:
        try:
            n, m = batch.split('/')
            n, m = int(n), int(m)
            chunk_size = len(target_keys) // m
            start = (n - 1) * chunk_size
            end = start + chunk_size if n < m else len(target_keys)
            target_keys = target_keys[start:end]
            print(f'  Batch {n}/{m}: cases {start + 1}-{end} ({len(target_keys)} cases)')
        except ValueError:
            print(f'ERROR: Invalid batch format "{batch}". Use N/M (e.g., 1/4)')
            return

    checkpoint = load_checkpoint()
    if resume:
        before = len(target_keys)
        target_keys = [k for k in target_keys if k not in checkpoint['synced']]
        skipped = before - len(target_keys)
        print(f'  Resume: skipping {skipped} already-synced cases')

    total = len(target_keys)
    if total == 0:
        print('  Nothing to sync.')
        return

    mode = 'DRY RUN' if dry_run else 'LIVE'
    print(f'\n{"=" * 60}')
    print(f'  SYNC {mode}: {total} cases')
    print(f'{"=" * 60}\n')

    interrupted = False
    def handle_sigint(_sig, _frame):
        nonlocal interrupted
        interrupted = True
        print('\n  Ctrl+C detected -- finishing current case then stopping...')
    old_handler = signal.signal(signal.SIGINT, handle_sigint)

    synced_count = 0
    error_count = 0
    start_time = time.time()

    try:
        for idx, case_key in enumerate(target_keys, 1):
            if interrupted:
                print(f'\n  Interrupted at case {idx}/{total}')
                break

            case_data = all_cases[case_key]
            step_count = len(case_data['steps'])

            # Rate limit burst pause
            if not dry_run and idx > 1 and (idx - 1) % BURST_THRESHOLD == 0:
                print(f'  [rate-limit] Burst pause {BURST_PAUSE}s after {idx - 1} cases...')
                time.sleep(BURST_PAUSE)

            try:
                result = sync_case(page, case_key, case_data['steps'], dry_run=dry_run,
                                   verbose=verbose)

                if result['status'] in ('ok', 'partial'):
                    synced_count += 1
                    elapsed = time.time() - start_time
                    rate = elapsed / idx
                    eta = rate * (total - idx)
                    if eta > 3600:
                        eta_str = f'{eta / 3600:.1f}h'
                    elif eta > 60:
                        eta_str = f'{int(eta // 60)}m{int(eta % 60)}s'
                    else:
                        eta_str = f'{int(eta)}s'
                    status_char = '+' if result['status'] == 'ok' else '~'
                    print(f'[{idx}/{total}] {status_char} {case_key} '
                          f'del={result["deleted"]} add={result["created"]}/{step_count} '
                          f'({rate:.1f}s/case ETA {eta_str})')
                    if not dry_run:
                        checkpoint['synced'][case_key] = {
                            'steps': result['created'],
                            'timestamp': datetime.now().isoformat(),
                        }
                        if result['status'] == 'partial':
                            checkpoint['errors'][case_key] = result['error']
                else:
                    error_count += 1
                    print(f'[{idx}/{total}] X {case_key} -- {result["error"]}')
                    if not dry_run:
                        checkpoint['errors'][case_key] = result['error']

                # Save checkpoint periodically
                if not dry_run and idx % 25 == 0:
                    save_checkpoint(checkpoint)

                # Automatic audit checkpoints
                if not dry_run and not cases and idx in (50, total // 4, total // 2, 3 * total // 4):
                    save_checkpoint(checkpoint)
                    pct = int(100 * idx / total)
                    audit_ok = run_audit(page, all_cases, checkpoint,
                                        sample_size=5 if idx == 50 else 10,
                                        label=f'after {idx}/{total} ({pct}%)')
                    if not audit_ok:
                        print(f'  Audit FAILED at case {idx}. Stopping sync.')
                        print('  Fix issues, then resume with: sync --resume')
                        break

                if not dry_run:
                    time.sleep(INTER_CASE_DELAY)

            except Exception as e:
                error_count += 1
                print(f'[{idx}/{total}] X {case_key} -- EXCEPTION: {e}')
                if not dry_run:
                    checkpoint['errors'][case_key] = str(e)
    finally:
        signal.signal(signal.SIGINT, old_handler)

    if not dry_run:
        save_checkpoint(checkpoint)

    elapsed = time.time() - start_time
    print(f'\n{"=" * 60}')
    print(f'  SYNC COMPLETE ({mode})')
    print(f'  Synced:  {synced_count}')
    print(f'  Errors:  {error_count}')
    print(f'  Total:   {total}')
    print(f'  Time:    {int(elapsed // 60)}m {int(elapsed % 60)}s')
    if synced_count > 0:
        print(f'  Rate:    {elapsed / synced_count:.1f}s/case')
    if not dry_run:
        print(f'  Checkpoint: {CHECKPOINT_FILE}')
    print(f'{"=" * 60}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description='QA Touch Step API Sync -- fix broken step pairing',
    )
    sub = parser.add_subparsers(dest='command')

    sub.add_parser('test', help='Test on TC0001 (5BRMnj)')

    sync_parser = sub.add_parser('sync', help='Sync all cases')
    sync_parser.add_argument('--dry-run', action='store_true')
    sync_parser.add_argument('--batch', type=str, help='Process batch N/M (e.g., 1/4)')
    sync_parser.add_argument('--cases', nargs='+', help='Specific case keys')
    sync_parser.add_argument('--resume', action='store_true')
    sync_parser.add_argument('--verbose', action='store_true', help='Show API response bodies')

    verify_parser = sub.add_parser('verify', help='Verify synced cases have correct step counts')
    verify_parser.add_argument('--cases', nargs='+', help='Specific case keys to verify')
    verify_parser.add_argument('--sample', type=int, default=20, help='Sample size (default 20)')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    print('Launching browser and authenticating with QA Touch...')

    with sync_playwright() as p:
        browser, ctx, page = login(p)

        try:
            print('  Entering NexaiQ-Core project...')
            enter_project(page)

            if args.command == 'test':
                cmd_test(page)
            elif args.command == 'sync':
                cmd_sync(page,
                         dry_run=args.dry_run,
                         batch=args.batch,
                         cases=args.cases,
                         resume=args.resume,
                         verbose=getattr(args, 'verbose', False))
            elif args.command == 'verify':
                cmd_verify(page,
                           cases_arg=args.cases,
                           sample_size=args.sample)
        finally:
            try:
                ctx.storage_state(path=AUTH_STATE_FILE)
            except Exception:
                pass
            print('\nClosing browser...')
            browser.close()


if __name__ == '__main__':
    main()
