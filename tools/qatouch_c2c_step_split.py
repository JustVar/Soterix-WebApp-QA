"""C2C Hardware - Post-Import Step Splitter.

QA Touch's CSV import puts all steps into a single "merged" step row.
This tool splits that merged step into individual step rows by:

  1. Logging into QA Touch via Playwright (reuses saved auth state)
  2. Fetching all cases in the C2C Hardware module(s) of project 60W5
  3. Matching them to our c2c_hardware_test_cases.csv by title
  4. For each matched case:
       - Reading the newline-separated steps + expected results from CSV
       - Deleting the existing merged step via /v1/steps/delete
       - Creating one step row per line via /v1/steps/save

Usage:
  python tools/qatouch_c2c_step_split.py list        # List what will be processed
  python tools/qatouch_c2c_step_split.py dry-run     # Preview without changes
  python tools/qatouch_c2c_step_split.py sync        # Actually split the steps
  python tools/qatouch_c2c_step_split.py sync --only "Verify camera web UI login"

This is a focused variant of tools/qatouch_step_api.py - same APIs, but
reads our CSV directly and works against project 60W5 (C2C project).
"""
from __future__ import annotations

import argparse
import csv
import functools
import html as html_mod
import os
import re
import sys
import time
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
# Constants - C2C project specific
# ---------------------------------------------------------------------------
BASE_URL = 'https://soterixsystems.qatouch.com'
PROJECT_KEY = '60W5'
CSV_FILE = ROOT / 'tests' / 'data' / 'c2c_hardware_test_cases.csv'
AUTH_STATE_FILE = str(ROOT / 'tools' / '.qatouch_auth_state.json')

INTER_CALL_DELAY = 0.15
INTER_CASE_DELAY = 0.3
RATE_LIMIT_PAUSE = 15.0


# ---------------------------------------------------------------------------
# CSV Loading - by title (we don't have keys yet)
# ---------------------------------------------------------------------------
def load_csv_by_title() -> dict[str, dict]:
    """Load C2C CSV keyed by test case title.

    Returns {title: {module, steps: [{step, expected}, ...]}}
    """
    cases = {}
    with open(CSV_FILE, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            title = row['Test Case Title'].strip()
            if not title:
                continue

            raw_steps = row['Steps'].split('\n') if row['Steps'].strip() else []
            raw_expected = row['Expected_result'].split('\n') if row['Expected_result'].strip() else []

            # Strip numeric prefix ("1. Do X" -> "Do X") for cleaner steps
            steps = []
            for i in range(max(len(raw_steps), len(raw_expected))):
                step_text = raw_steps[i].strip() if i < len(raw_steps) else ''
                exp_text = raw_expected[i].strip() if i < len(raw_expected) else ''
                # Strip leading "N. " numbering
                step_text = re.sub(r'^\d+\.\s*', '', step_text)
                exp_text = re.sub(r'^\d+\.\s*', '', exp_text)
                if not step_text:
                    continue
                steps.append({
                    'step': step_text,
                    'expected': exp_text if exp_text else 'Step completed successfully',
                })

            if steps:
                cases[title] = {
                    'module': row['Module_name'],
                    'steps': steps,
                }
    return cases


# ---------------------------------------------------------------------------
# HTML Escaping
# ---------------------------------------------------------------------------
def escape_for_html(text: str) -> str:
    plain = html_mod.unescape(text)
    return html_mod.escape(plain, quote=False)


# ---------------------------------------------------------------------------
# Playwright Login (reused from main tool)
# ---------------------------------------------------------------------------
def login(p):
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
        if _is_logged_in(page):
            print('  Auth state valid!')
            return browser, ctx, page
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


def _is_logged_in(page) -> bool:
    url = page.url or ''
    url_match = any(x in url for x in ['/dashboard', '/project', '/testCase',
                                        '/modules', '/new-projects', '/case/list'])
    if not url_match:
        for sel in ['text="Dashboard"', 'text="Project List"']:
            try:
                if page.locator(sel).first.is_visible(timeout=500):
                    url_match = True
                    break
            except Exception:
                pass
    return url_match


# ---------------------------------------------------------------------------
# QA Touch Internal API calls
# ---------------------------------------------------------------------------
def fetch_project_cases(page) -> list[dict]:
    """Fetch all cases in project 60W5 with {key, title, module} via the
    case list API.

    Uses the Test Case list endpoint which returns all cases in the project.
    We paginate until we get them all.
    """
    all_cases = []
    page_num = 1
    while True:
        result = page.evaluate("""
            async ([pid, pageNum]) => {
                try {
                    const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
                    const resp = await fetch('/v1/case/list/p/' + pid + '?page=' + pageNum, {
                        method: 'GET',
                        headers: {
                            'Accept': 'application/json',
                            'X-XSRF-TOKEN': decodeURIComponent(token || '')
                        }
                    });
                    if (!resp.ok) return { error: 'HTTP ' + resp.status };
                    return await resp.json();
                } catch (e) {
                    return { error: e.message };
                }
            }
        """, [PROJECT_KEY, page_num])

        if result.get('error'):
            print(f'  ERROR fetching page {page_num}: {result["error"]}')
            break

        cases = (result.get('data') or {}).get('cases', []) or []
        if not cases:
            cases = (result.get('data') or {}).get('testcases', []) or []
        if not cases:
            cases = result.get('cases', []) or []

        if not cases:
            # Last page
            break

        for c in cases:
            all_cases.append({
                'key': c.get('case_key') or c.get('key') or c.get('id'),
                'title': c.get('case_title') or c.get('title') or c.get('name', ''),
                'module': c.get('module_name') or c.get('module', ''),
            })

        print(f'  Fetched page {page_num}: {len(cases)} cases (total: {len(all_cases)})')
        page_num += 1
        if page_num > 50:
            break  # Safety cap
        time.sleep(0.2)

    return all_cases


def get_step_ids(page, case_key: str) -> list[str]:
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
        return []
    return result.get('ids', [])


def delete_step(page, step_id: str) -> bool:
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
    safe_desc = escape_for_html(step_desc)
    safe_exp = escape_for_html(expected)

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
                        step_description: '<p>' + desc + '</p>',
                        expected_result: '<p>' + exp + '</p>'
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
    """, [PROJECT_KEY, cid, safe_desc, safe_exp])


# ---------------------------------------------------------------------------
# Sync Logic
# ---------------------------------------------------------------------------
def sync_case(page, case_key: str, _title: str, steps: list[dict],
              dry_run: bool = False) -> dict:
    result = {'status': 'ok', 'deleted': 0, 'created': 0, 'error': ''}

    if dry_run:
        result['created'] = len(steps)
        return result

    step_ids = get_step_ids(page, case_key)
    for sid in step_ids:
        if delete_step(page, sid):
            result['deleted'] += 1
        time.sleep(INTER_CALL_DELAY)

    for i, s in enumerate(steps, 1):
        r = create_step(page, case_key, s['step'], s['expected'])
        if r.get('rateLimited'):
            print(f'    Rate limited! Pausing {RATE_LIMIT_PAUSE}s...')
            time.sleep(RATE_LIMIT_PAUSE)
            r = create_step(page, case_key, s['step'], s['expected'])
        if r.get('ok'):
            result['created'] += 1
        else:
            err = r.get('error') or f'HTTP {r.get("status")}'
            if result['status'] == 'ok':
                result['status'] = 'partial'
                result['error'] = f'Step {i} failed: {err}'
        time.sleep(INTER_CALL_DELAY)

    # Verify
    time.sleep(0.5)
    verify_ids = get_step_ids(page, case_key)
    if len(verify_ids) != len(steps):
        result['status'] = 'verify_mismatch'
        result['error'] = f'Expected {len(steps)}, got {len(verify_ids)}'

    return result


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_list(_page, _args):
    csv_cases = load_csv_by_title()
    print(f'\n=== CSV loaded: {len(csv_cases)} cases ===\n')
    for title, data in csv_cases.items():
        print(f'  [{data["module"]:<45}] {title}  ({len(data["steps"])} steps)')


def cmd_dry_run(page, _args):
    """Fetch cases from QA Touch, match to CSV, show what WOULD happen."""
    csv_cases = load_csv_by_title()
    print(f'\n=== Loaded {len(csv_cases)} cases from CSV ===')

    print(f'\n=== Fetching cases from QA Touch (project {PROJECT_KEY}) ===')
    qt_cases = fetch_project_cases(page)
    print(f'  Total cases in project: {len(qt_cases)}')

    # Build title -> key map (only C2C-prefixed modules)
    qt_by_title = {}
    for c in qt_cases:
        module = c.get('module', '') or ''
        if 'C2C Hardware' in module or any(
            t in c['title'] for t in csv_cases
        ):
            qt_by_title[c['title']] = c['key']

    print('  Matching to CSV cases...')
    matched = 0
    missing = []
    for title in csv_cases:
        if title in qt_by_title:
            matched += 1
        else:
            missing.append(title)

    print('\n=== Match Results ===')
    print(f'  Matched: {matched}/{len(csv_cases)}')
    if missing:
        print('  Missing from QA Touch:')
        for t in missing:
            print(f'    - {t}')

    print('\n=== DRY RUN - Steps that WOULD be split ===')
    for title, data in csv_cases.items():
        key = qt_by_title.get(title, '???')
        print(f'\n  [{key}] {title}')
        for i, s in enumerate(data['steps'], 1):
            print(f'    {i}. {s["step"][:75]}')
            print(f'       => {s["expected"][:75]}')


def cmd_sync(page, args):
    csv_cases = load_csv_by_title()
    print(f'\n=== Loaded {len(csv_cases)} cases from CSV ===')

    print(f'\n=== Fetching cases from QA Touch (project {PROJECT_KEY}) ===')
    qt_cases = fetch_project_cases(page)
    qt_by_title = {c['title']: c['key'] for c in qt_cases if c.get('key')}

    # Optional title filter
    only = getattr(args, 'only', None)
    targets = {t: d for t, d in csv_cases.items()
               if t in qt_by_title and (not only or only.lower() in t.lower())}

    print(f'\n=== Syncing {len(targets)} cases ===\n')

    summary = {'ok': 0, 'partial': 0, 'error': 0, 'missing': 0}
    for i, (title, data) in enumerate(targets.items(), 1):
        key = qt_by_title[title]
        print(f'[{i:2}/{len(targets)}] {key} - {title[:65]}')
        r = sync_case(page, key, title, data['steps'], dry_run=args.dry_run)
        status = r['status']
        summary[status if status in summary else 'error'] = \
            summary.get(status, 0) + 1
        print(f'         {status.upper()}: deleted={r["deleted"]}, '
              f'created={r["created"]}/{len(data["steps"])}'
              + (f'  ({r["error"]})' if r.get('error') else ''))
        time.sleep(INTER_CASE_DELAY)

    print('\n=== Summary ===')
    for k, v in summary.items():
        print(f'  {k}: {v}')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='C2C step splitter')
    sub = parser.add_subparsers(dest='cmd', required=True)

    sub.add_parser('list', help='Show CSV cases that will be processed')

    p_dry = sub.add_parser('dry-run', help='Fetch cases, match, preview')
    p_dry.set_defaults(dry_run=True)

    p_sync = sub.add_parser('sync', help='Split steps for real')
    p_sync.add_argument('--only', help='Only process cases with this substring in title')
    p_sync.add_argument('--dry-run', action='store_true', help='Preview only')

    args = parser.parse_args()

    with sync_playwright() as p:
        if args.cmd == 'list':
            cmd_list(None, args)
            return

        browser, _ctx, page = login(p)
        try:
            if args.cmd == 'dry-run':
                cmd_dry_run(page, args)
            elif args.cmd == 'sync':
                cmd_sync(page, args)
        finally:
            browser.close()


if __name__ == '__main__':
    main()
