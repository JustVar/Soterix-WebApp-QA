#!/usr/bin/env python3
"""Verify the C2C OTA CSV import landed in QA Touch project 60W5.

Read-only sanity check. Logs in to QA Touch via Playwright (reuses saved auth
state from tools/.qatouch_auth_state.json), fetches every case in project 60W5,
and reports:

  - Total case count under `C2C OTA > ...` modules
  - Cases per OTA module (expected: 8 modules)
  - References that match the CSV (expected: C2C_OTA_001..085)
  - Anything missing or extra vs the CSV
  - A few spot-check cases (the 5 smoke + 5 critical)

Run:
    python tools/verify_c2c_ota_import.py
"""
from __future__ import annotations

import csv
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright

BASE_URL = 'https://soterixsystems.qatouch.com'
PROJECT_KEY = '60W5'
AUTH_STATE_FILE = str(ROOT / 'tools' / '.qatouch_auth_state.json')
CSV_PATH = ROOT / 'tests' / 'data' / 'c2c_ota_test_cases.csv'


def fetch_project_cases(page) -> list[dict]:
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
            print(f'  ERROR page {page_num}: {result["error"]}')
            break

        cases = (result.get('data') or {}).get('cases', []) or []
        if not cases:
            cases = (result.get('data') or {}).get('testcases', []) or []
        if not cases:
            cases = result.get('cases', []) or []
        if not cases:
            break

        for c in cases:
            all_cases.append({
                'key': c.get('case_key') or c.get('key') or c.get('id'),
                'title': c.get('case_title') or c.get('title') or c.get('name', ''),
                'module': c.get('module_name') or c.get('module', '') or '',
                'reference': c.get('reference') or c.get('case_reference') or '',
                'priority': c.get('priority') or c.get('priority_name') or '',
                'type': c.get('case_type') or c.get('type') or '',
            })
        print(f'  Fetched page {page_num}: +{len(cases)} (total {len(all_cases)})')
        page_num += 1
        if page_num > 60:
            break
        time.sleep(0.15)
    return all_cases


def main() -> int:
    if not CSV_PATH.exists():
        print(f'ERROR CSV not found: {CSV_PATH}')
        return 1
    with CSV_PATH.open(encoding='utf-8') as f:
        csv_rows = list(csv.DictReader(f))
    csv_refs = {r['Reference']: r for r in csv_rows}
    print(f'CSV references expected: {len(csv_refs)} (C2C_OTA_001..{max(csv_refs)})')

    if not Path(AUTH_STATE_FILE).exists():
        print(f'ERROR no saved auth state at {AUTH_STATE_FILE} - run a tool that logs in first.')
        return 2

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=AUTH_STATE_FILE)
        page = ctx.new_page()
        page.goto(f'{BASE_URL}/index.html#dashboard', timeout=60000)
        page.wait_for_load_state('networkidle', timeout=20000)
        time.sleep(1)
        print(f'\n=== Fetching cases in project {PROJECT_KEY} ===')
        all_cases = fetch_project_cases(page)
        browser.close()

    ota_cases = [c for c in all_cases if (c.get('module') or '').startswith('C2C OTA')]
    print(f'\nTotal cases in project: {len(all_cases)}')
    print(f'Cases under "C2C OTA > ..." modules: {len(ota_cases)}')

    by_module = Counter(c['module'] for c in ota_cases)
    print('\nPer-module count (live QA Touch):')
    for m, n in sorted(by_module.items()):
        print(f'  {m}: {n}')

    expected_modules = {f'C2C OTA > {m}' for m in [
        'Notification', 'Partner OTA Update', 'Customer Admin', 'Backend Validation',
        'Functional Validation', 'Negative Testing', 'Performance', 'Security',
    ]}
    missing_modules = expected_modules - set(by_module)
    extra_modules = set(by_module) - expected_modules
    if missing_modules:
        print(f'\nWARN missing OTA modules: {sorted(missing_modules)}')
    if extra_modules:
        print(f'WARN unexpected OTA modules: {sorted(extra_modules)}')

    # Reference match
    live_refs = {c.get('reference') for c in ota_cases if c.get('reference')}
    missing_refs = sorted(set(csv_refs) - live_refs)
    extra_refs = sorted(r for r in live_refs if r and r.startswith('C2C_OTA_') and r not in csv_refs)
    print(f'\nReference matches: {len(set(csv_refs) & live_refs)}/{len(csv_refs)}')
    if missing_refs:
        print(f'WARN missing from QA Touch: {missing_refs[:10]}{" ..." if len(missing_refs)>10 else ""}')
    if extra_refs:
        print(f'WARN extras in QA Touch: {extra_refs[:10]}{" ..." if len(extra_refs)>10 else ""}')

    # Spot-check the smoke + critical cases
    spot = ['C2C_OTA_001', 'C2C_OTA_004', 'C2C_OTA_011', 'C2C_OTA_026',
            'C2C_OTA_033', 'C2C_OTA_036', 'C2C_OTA_056', 'C2C_OTA_082', 'C2C_OTA_084']
    by_ref = {c.get('reference'): c for c in ota_cases if c.get('reference')}
    print('\nSpot-check (smoke + critical):')
    for ref in spot:
        c = by_ref.get(ref)
        if c:
            print(f'  OK {ref} [{c["module"]}] pri={c["priority"]} type={c["type"]} | {c["title"][:60]}')
        else:
            print(f'  MISSING {ref}')

    print('\nVerdict:', 'CLEAN' if not missing_refs and not missing_modules else 'NEEDS ATTENTION')
    return 0


if __name__ == '__main__':
    sys.exit(main())
