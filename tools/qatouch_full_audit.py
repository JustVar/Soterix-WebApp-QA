"""QA Touch Full Audit - comprehensive data integrity verification.

Runs multiple independent audits to validate all 3,011 test cases after
the step-pairing sync. Does NOT modify any data - read-only verification.

Audits:
  1. Step Count Audit      - CSV expected step count vs live QA Touch (ALL cases)
  2. Step Content Audit     - CSV step text vs live QA Touch step text (sample)
  3. Case Title Audit       - CSV title vs snapshot title vs live (ALL cases)
  4. Module Integrity Audit - snapshot module vs live module (ALL cases)
  5. Duplicate Title Audit  - find duplicate titles, verify differentiators
  6. Tag Preservation Audit - verify Smoke/Sanity tags unchanged (ALL cases)
  7. CSV Cross-Reference    - Part1+Part2+Part3 coverage, no gaps or overlaps

Usage:
  python tools/qatouch_full_audit.py                    # Run all audits
  python tools/qatouch_full_audit.py --audit 1          # Run specific audit
  python tools/qatouch_full_audit.py --audit 1,2,3      # Run multiple audits
  python tools/qatouch_full_audit.py --content-sample 100  # Content audit sample size
"""
from __future__ import annotations

import argparse
import csv
import functools
import html as html_mod
import json
import os
import random
import sys
import time
from collections import Counter, defaultdict
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
    print('ERROR: playwright required.')
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
BASE_URL = 'https://soterixsystems.qatouch.com'
PROJECT_KEY = 'JlW1'
AUTH_STATE_FILE = str(ROOT / 'tools' / '.qatouch_auth_state.json')
REPORT_DIR = ROOT / 'config' / 'audit_reports'
SNAPSHOT_DIR = ROOT / 'config' / 'qatouch_snapshots'


def latest_snapshot_path():
    """Newest snapshot_*.json, or None. Refresh with qatouch_analytics.py snapshot."""
    if not SNAPSHOT_DIR.exists():
        return None
    files = sorted(SNAPSHOT_DIR.glob('snapshot_*.json'))
    return files[-1] if files else None


# Set from --snapshot in main(); defaults to the newest snapshot on disk.
# Was hard-coded to snapshot_2026-03-02.json, which froze the audit in March.
SNAPSHOT_FILE = latest_snapshot_path()

# This audit was written to verify the February 2026 bulk-update import
# against its three source CSVs. Every one of the seven passes reads that
# CSV data - even the ones whose docstrings say "snapshot vs live". The
# CSVs no longer exist on disk, so without --csv there is nothing to audit.
#
# For the ongoing question "has QA Touch drifted from what we think" use:
#   python tools/qatouch_analytics.py snapshot && python tools/qatouch_analytics.py report
#       (added / removed / changed cases vs the previous snapshot)
#   python tools/qatouch_contract_check.py
#       (API response shape, statuses, tag IDs, endpoints)
#   python tools/validate_run.py <RUN_KEY>
#       (uploaded results vs local results)
CSV_FILES = [
    os.path.expanduser('~/Downloads/QATouch_BulkUpdate_Part1.csv'),
    os.path.expanduser('~/Downloads/QATouch_BulkUpdate_Part2.csv'),
    os.path.expanduser('~/Downloads/QATouch_BulkUpdate_Part3.csv'),
]
CSV_AUDITS = {1, 2, 3, 4, 5, 6, 7}

INTER_CALL_DELAY = 0.15
BURST_PAUSE = 10.0
BURST_THRESHOLD = 50


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------
def load_csv_full() -> dict[str, dict]:
    """Load all CSV data with full metadata."""
    cases = {}
    for csv_path in CSV_FILES:
        if not os.path.exists(csv_path):
            print(f'  WARNING: CSV not found: {csv_path}')
            continue
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)  # the header row
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

                cases[case_key] = {
                    'case_code': row[1].strip() if len(row) > 1 else '',
                    'module': row[4].strip() if len(row) > 4 else '',
                    'title': row[5].strip() if len(row) > 5 else '',
                    'type': row[6].strip() if len(row) > 6 else '',
                    'priority': row[7].strip() if len(row) > 7 else '',
                    'mode': row[15].strip() if len(row) > 15 else '',
                    'tags': row[17].strip() if len(row) > 17 else '',
                    'steps': steps,
                    'csv_file': os.path.basename(csv_path),
                }
    return cases


def load_snapshot() -> dict[str, dict]:
    """Load snapshot data keyed by case_key."""
    if not SNAPSHOT_FILE or not os.path.exists(SNAPSHOT_FILE):
        print(f'  WARNING: Snapshot not found: {SNAPSHOT_FILE}')
        print('           Take one: python tools/qatouch_analytics.py snapshot')
        return {}
    print(f'  Snapshot file: {Path(SNAPSHOT_FILE).name}')
    with open(SNAPSHOT_FILE, encoding='utf-8') as f:
        data = json.load(f)
    return {c['case_key']: c for c in data.get('cases', [])}


# ---------------------------------------------------------------------------
# Playwright Login (same as qatouch_step_api.py)
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
    url = page.url or ''
    url_match = any(x in url for x in ['/dashboard', '/project', '/testCase',
                                        '/modules', '/new-projects', '/case/list'])
    if not url_match:
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
# Session Manager - auto-refresh on death
# ---------------------------------------------------------------------------
class SessionManager:
    """Manages Playwright browser session with auto-refresh on expiry.

    When the session dies (consecutive API errors), navigates to login page
    and waits indefinitely for the user to re-authenticate. This allows
    overnight runs to survive session expiry.
    """

    def __init__(self, browser, ctx, page):
        self.browser = browser
        self.ctx = ctx
        self.page = page
        self._consecutive_errors = 0
        self._max_errors = 5

    def get_case_edit_data(self, case_key: str) -> dict | None:
        """Get case data with auto-session-refresh on failure."""
        result = _get_case_edit_data_raw(self.page, case_key)
        if result is not None:
            self._consecutive_errors = 0
            return result

        self._consecutive_errors += 1
        if self._consecutive_errors >= self._max_errors:
            print(f'\n  SESSION EXPIRED: {self._consecutive_errors} consecutive API errors.')
            self._refresh_session()
            self._consecutive_errors = 0
            # Retry the failed call
            return _get_case_edit_data_raw(self.page, case_key)
        return None

    def _refresh_session(self):
        """Navigate to login and wait indefinitely for re-authentication."""
        print('  Refreshing session - navigating to login page...')
        try:
            os.remove(AUTH_STATE_FILE)
        except OSError:
            pass

        # Close old context, open new one on same browser
        try:
            self.ctx.close()
        except Exception:
            pass

        self.ctx = self.browser.new_context(viewport={'width': 1400, 'height': 900})
        self.page = self.ctx.new_page()
        self.page.goto(f'{BASE_URL}/login', timeout=60000)

        print()
        print('=' * 60)
        print('  SESSION EXPIRED - Please log in to QA Touch')
        print('  Waiting indefinitely (no timeout)...')
        print('  Audit will resume automatically after login.')
        print('=' * 60)

        while True:
            time.sleep(3)
            if _is_logged_in(self.page):
                print('  Login detected! Resuming audit...')
                time.sleep(2)
                self.ctx.storage_state(path=AUTH_STATE_FILE)
                enter_project(self.page)
                return


# ---------------------------------------------------------------------------
# API Helpers
# ---------------------------------------------------------------------------
def _get_case_edit_data_raw(page, case_key: str) -> dict | None:
    """Get full case edit data via POST /v1/case/edit/p/{pid}/cid/{key}.

    Returns the full data object including caseStep[], case details, etc.
    Returns None on error.
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
                if (!resp.ok) return { error: 'HTTP ' + resp.status };
                const data = await resp.json();
                if (!data || !data.data) return { error: 'No data in response' };
                const d = data.data;
                const steps = d.caseStep || [];
                return {
                    case_key: caseKey,
                    title: d.title || '',
                    module: d.sectionName || '',
                    template: d.template,
                    tags: (d.newtags || []).map(t => t.title || t).join(', '),
                    mode: d.mode || '',
                    type: d.type || '',
                    priority: d.priority || '',
                    step_count: steps.length,
                    steps: steps.map(s => ({
                        id: s.id,
                        description: s.step || '',
                        expected: s.description || ''
                    }))
                };
            } catch (e) {
                return { error: e.message };
            }
        }
    """, case_key)
    if result and result.get('error'):
        return None
    return result


def strip_html(text: str) -> str:
    """Remove <p> tags and HTML entities for comparison."""
    if not text:
        return ''
    t = text.replace('<p>', '').replace('</p>', '').strip()
    return html_mod.unescape(t)


# ---------------------------------------------------------------------------
# Report Writer
# ---------------------------------------------------------------------------
class AuditReport:
    def __init__(self, name: str):
        self.name = name
        self.lines = []
        self.pass_count = 0
        self.fail_count = 0
        self.warn_count = 0
        self.start_time = time.time()

    def log(self, msg: str):
        self.lines.append(msg)
        print(msg)

    def passed(self, msg: str):
        self.pass_count += 1
        self.lines.append(f'  PASS: {msg}')

    def failed(self, msg: str):
        self.fail_count += 1
        line = f'  FAIL: {msg}'
        self.lines.append(line)
        print(line)

    def warn(self, msg: str):
        self.warn_count += 1
        line = f'  WARN: {msg}'
        self.lines.append(line)
        print(line)

    def summary(self) -> str:
        elapsed = time.time() - self.start_time
        s = f'\n{"=" * 60}\n'
        s += f'  {self.name}\n'
        s += f'  Passed: {self.pass_count}  Failed: {self.fail_count}  Warnings: {self.warn_count}\n'
        s += f'  Time: {elapsed:.1f}s\n'
        s += f'  Result: {"PASS" if self.fail_count == 0 else "FAIL"}\n'
        s += f'{"=" * 60}\n'
        self.lines.append(s)
        print(s)
        return s

    def write(self, report_dir: Path):
        report_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_name = self.name.lower().replace(' ', '_').replace('-', '').replace('#', '')
        path = report_dir / f'{safe_name}_{ts}.txt'
        with open(path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.lines))
        return path


# ---------------------------------------------------------------------------
# Audit 1: Step Count (ALL 3,011 cases)
# ---------------------------------------------------------------------------
def audit_step_count(session, csv_data: dict, report: AuditReport):
    """Verify every case has the correct number of steps."""
    report.log(f'\n{"#" * 60}')
    report.log(f'# AUDIT 1: Step Count Verification - ALL {len(csv_data)} cases')
    report.log(f'{"#" * 60}\n')

    total = len(csv_data)
    checked = 0
    # template=2 is "Test Case Steps" (supports steps), others may not
    non_step_templates = []

    for i, (key, csv_case) in enumerate(csv_data.items(), 1):
        expected_count = len(csv_case['steps'])
        data = session.get_case_edit_data(key)

        if data is None:
            report.failed(f'{key}: API error')
            continue

        # Track non-standard templates
        tmpl = data.get('template')
        if tmpl is not None and tmpl != 2:
            non_step_templates.append((key, csv_case.get('case_code', ''), tmpl))

        actual_count = data.get('step_count', 0)
        if actual_count == expected_count:
            report.passed(f'{key} ({csv_case.get("case_code","")}) steps={actual_count}')
        else:
            report.failed(f'{key} ({csv_case.get("case_code","")}) expected={expected_count} actual={actual_count}')

        checked += 1
        time.sleep(INTER_CALL_DELAY)

        if i % BURST_THRESHOLD == 0:
            pct = i / total * 100
            print(f'  [{i}/{total}] ({pct:.0f}%) pass={report.pass_count} fail={report.fail_count}')
            time.sleep(BURST_PAUSE)

    report.log(f'\n  Checked: {checked}/{total}')
    if non_step_templates:
        report.log(f'\n  WARNING: {len(non_step_templates)} cases with non-standard template (not "Test Case Steps"):')
        for key, code, tmpl in non_step_templates:
            report.warn(f'{key} ({code}) template={tmpl} - steps may not persist')
    else:
        report.log('  All cases use "Test Case Steps" template (template=2)')


# ---------------------------------------------------------------------------
# Audit 2: Step Content (sample - text comparison)
# ---------------------------------------------------------------------------
def audit_step_content(session, csv_data: dict, report: AuditReport, sample_size: int = 50):
    """Compare actual step descriptions and expected results against CSV source."""
    report.log(f'\n{"#" * 60}')
    report.log(f'# AUDIT 2: Step Content Verification - {sample_size} case sample')
    report.log(f'{"#" * 60}\n')

    keys = list(csv_data.keys())
    sample = random.sample(keys, min(sample_size, len(keys)))

    for i, key in enumerate(sample, 1):
        csv_case = csv_data[key]
        data = session.get_case_edit_data(key)

        if data is None:
            report.failed(f'{key}: API error')
            continue

        live_steps = data.get('steps', [])
        csv_steps = csv_case['steps']

        if len(live_steps) != len(csv_steps):
            report.failed(f'{key}: step count mismatch (csv={len(csv_steps)} live={len(live_steps)})')
            continue

        step_match = True
        for j, (csv_s, live_s) in enumerate(zip(csv_steps, live_steps, strict=False)):
            csv_step_text = html_mod.unescape(csv_s['step']).strip()
            csv_exp_text = html_mod.unescape(csv_s['expected']).strip()

            live_step_text = strip_html(live_s.get('description', ''))
            live_exp_text = strip_html(live_s.get('expected', ''))

            if csv_step_text != live_step_text:
                report.failed(f'{key} step {j+1} description mismatch:\n'
                             f'    CSV:  {csv_step_text[:100]}\n'
                             f'    Live: {live_step_text[:100]}')
                step_match = False
            if csv_exp_text != live_exp_text:
                report.failed(f'{key} step {j+1} expected result mismatch:\n'
                             f'    CSV:  {csv_exp_text[:100]}\n'
                             f'    Live: {live_exp_text[:100]}')
                step_match = False

        if step_match:
            report.passed(f'{key} ({csv_case.get("case_code","")}) - all {len(csv_steps)} steps match')

        time.sleep(INTER_CALL_DELAY)
        if i % 25 == 0:
            print(f'  [{i}/{len(sample)}] pass={report.pass_count} fail={report.fail_count}')
            time.sleep(5.0)


# ---------------------------------------------------------------------------
# Audit 3: Case Title Verification (CSV vs Snapshot vs Live)
# ---------------------------------------------------------------------------
def _strip_csv_module_prefix(title: str) -> str:
    """Strip [Module Name] prefix from CSV titles (16 cases have this)."""
    import re
    return re.sub(r'^\[.*?\]\s*', '', title)


def audit_case_titles(session, csv_data: dict, snapshot: dict, report: AuditReport):
    """Compare case titles across CSV, snapshot, and live data."""
    report.log(f'\n{"#" * 60}')
    report.log('# AUDIT 3: Case Title Verification - ALL cases')
    report.log(f'{"#" * 60}\n')

    # First: CSV vs Snapshot (offline, fast)
    report.log('  --- Phase 1: CSV vs Snapshot (offline) ---')
    csv_snap_match = 0
    csv_snap_mismatch = 0
    prefix_stripped = 0
    for key in csv_data:
        csv_title = csv_data[key]['title']
        snap_title = snapshot.get(key, {}).get('case_title', '')
        if not snap_title:
            report.warn(f'{key}: not in snapshot')
            continue
        if csv_title == snap_title:
            csv_snap_match += 1
        elif _strip_csv_module_prefix(csv_title) == snap_title:
            csv_snap_match += 1
            prefix_stripped += 1
        else:
            csv_snap_mismatch += 1
            report.failed(f'{key} CSV≠Snapshot:\n'
                         f'    CSV:  {csv_title[:100]}\n'
                         f'    Snap: {snap_title[:100]}')
    report.log(f'  CSV vs Snapshot: {csv_snap_match} match ({prefix_stripped} with [Module] prefix stripped), {csv_snap_mismatch} mismatch\n')

    # Phase 2: CSV vs Live (API, slower - sample of 100)
    report.log('  --- Phase 2: CSV vs Live (API, 100-case sample) ---')
    keys = list(csv_data.keys())
    sample = random.sample(keys, min(100, len(keys)))

    for i, key in enumerate(sample, 1):
        data = session.get_case_edit_data(key)
        if data is None:
            report.failed(f'{key}: API error')
            continue

        csv_title = csv_data[key]['title']
        live_title = data.get('title', '')
        csv_normalized = _strip_csv_module_prefix(csv_title)
        if csv_normalized == live_title:
            report.passed(f'{key} title matches')
        else:
            report.failed(f'{key} CSV≠Live:\n'
                         f'    CSV:  {csv_title[:100]}\n'
                         f'    Live: {live_title[:100]}')

        time.sleep(INTER_CALL_DELAY)
        if i % 50 == 0:
            time.sleep(5.0)


# ---------------------------------------------------------------------------
# Audit 4: Module Integrity (Snapshot vs Live)
# ---------------------------------------------------------------------------
def audit_module_integrity(session, csv_data: dict, snapshot: dict, report: AuditReport):
    """Verify module assignments haven't changed."""
    report.log(f'\n{"#" * 60}')
    report.log('# AUDIT 4: Module Integrity - CSV vs Snapshot (offline)')
    report.log(f'{"#" * 60}\n')

    modules_csv = Counter()
    modules_snap = Counter()
    mismatches = []

    for key in csv_data:
        csv_mod = csv_data[key]['module']
        snap_mod = snapshot.get(key, {}).get('module name', '')
        modules_csv[csv_mod] += 1
        modules_snap[snap_mod] += 1

        if csv_mod and snap_mod and csv_mod != snap_mod:
            mismatches.append((key, csv_mod, snap_mod))

    report.log(f'  Unique modules in CSV: {len(modules_csv)}')
    report.log(f'  Unique modules in Snapshot: {len(modules_snap)}')
    report.log(f'  Module mismatches (CSV vs Snapshot): {len(mismatches)}')

    if mismatches:
        for key, csv_mod, snap_mod in mismatches[:20]:
            report.failed(f'{key}: CSV="{csv_mod}" Snap="{snap_mod}"')
        if len(mismatches) > 20:
            report.log(f'  ... and {len(mismatches) - 20} more')
    else:
        report.passed(f'All {len(csv_data)} cases have matching modules')

    # Module distribution
    report.log('\n  Module distribution (top 20 by case count):')
    for mod, count in modules_csv.most_common(20):
        report.log(f'    {count:>4} cases - {mod}')


# ---------------------------------------------------------------------------
# Audit 5: Duplicate Title Detection
# ---------------------------------------------------------------------------
def audit_duplicate_titles(csv_data: dict, report: AuditReport):
    """Find duplicate titles and verify differentiators exist."""
    report.log(f'\n{"#" * 60}')
    report.log('# AUDIT 5: Duplicate Title Detection')
    report.log(f'{"#" * 60}\n')

    title_to_keys = defaultdict(list)
    for key, case in csv_data.items():
        title_to_keys[case['title']].append(key)

    duplicates = {t: keys for t, keys in title_to_keys.items() if len(keys) > 1}
    report.log(f'  Total unique titles: {len(title_to_keys)}')
    report.log(f'  Titles with duplicates: {len(duplicates)}')
    report.log(f'  Cases affected: {sum(len(k) for k in duplicates.values())}')

    if duplicates:
        report.log('\n  Duplicate titles (showing modules for differentiation):')
        for title, keys in sorted(duplicates.items(), key=lambda x: -len(x[1])):
            report.log(f'\n    "{title[:80]}" - {len(keys)} copies:')
            for k in keys:
                mod = csv_data[k]['module']
                code = csv_data[k]['case_code']
                report.log(f'      {k} ({code}) in module: {mod}')
            # Check if modules differentiate them
            modules = [csv_data[k]['module'] for k in keys]
            if len(set(modules)) == len(modules):
                report.passed(f'"{title[:50]}..." differentiated by module ({len(keys)} copies)')
            else:
                report.warn(f'"{title[:50]}..." has same-module duplicates: {modules}')
    else:
        report.passed('No duplicate titles found')


# ---------------------------------------------------------------------------
# Audit 6: Tag Preservation (Smoke/Sanity)
# ---------------------------------------------------------------------------
def audit_tag_preservation(csv_data: dict, snapshot: dict, report: AuditReport):
    """Verify Smoke/Sanity tags in CSV match snapshot - tags must not change."""
    report.log(f'\n{"#" * 60}')
    report.log('# AUDIT 6: Tag Preservation (Smoke/Sanity) - offline')
    report.log(f'{"#" * 60}\n')

    csv_smoke = set()
    csv_sanity = set()
    snap_smoke = set()
    snap_sanity = set()

    for key, case in csv_data.items():
        tags_lower = case.get('tags', '').lower()
        if 'smoke' in tags_lower:
            csv_smoke.add(key)
        if 'sanity' in tags_lower:
            csv_sanity.add(key)

    for key, case in snapshot.items():
        tags_lower = (case.get('NewTags') or '').lower()
        if 'smoke' in tags_lower:
            snap_smoke.add(key)
        if 'sanity' in tags_lower:
            snap_sanity.add(key)

    report.log(f'  Smoke tags - CSV: {len(csv_smoke)}, Snapshot: {len(snap_smoke)}')
    report.log(f'  Sanity tags - CSV: {len(csv_sanity)}, Snapshot: {len(snap_sanity)}')

    # Compare
    smoke_only_csv = csv_smoke - snap_smoke
    smoke_only_snap = snap_smoke - csv_smoke
    sanity_only_csv = csv_sanity - snap_sanity
    sanity_only_snap = snap_sanity - csv_sanity

    if not smoke_only_csv and not smoke_only_snap:
        report.passed(f'Smoke tags match ({len(csv_smoke)} cases)')
    else:
        if smoke_only_csv:
            report.warn(f'Smoke in CSV but not snapshot: {len(smoke_only_csv)} - {list(smoke_only_csv)[:5]}')
        if smoke_only_snap:
            report.warn(f'Smoke in snapshot but not CSV: {len(smoke_only_snap)} - {list(smoke_only_snap)[:5]}')

    if not sanity_only_csv and not sanity_only_snap:
        report.passed(f'Sanity tags match ({len(csv_sanity)} cases)')
    else:
        if sanity_only_csv:
            report.warn(f'Sanity in CSV but not snapshot: {len(sanity_only_csv)} - {list(sanity_only_csv)[:5]}')
        if sanity_only_snap:
            report.warn(f'Sanity in snapshot but not CSV: {len(sanity_only_snap)} - {list(sanity_only_snap)[:5]}')


# ---------------------------------------------------------------------------
# Audit 7: CSV Cross-Reference
# ---------------------------------------------------------------------------
def audit_csv_cross_reference(report: AuditReport):
    """Verify CSV files cover all cases with no gaps or overlaps."""
    report.log(f'\n{"#" * 60}')
    report.log('# AUDIT 7: CSV Cross-Reference - Part1 + Part2 + Part3')
    report.log(f'{"#" * 60}\n')

    file_cases = {}
    all_keys = []
    for csv_path in CSV_FILES:
        fname = os.path.basename(csv_path)
        keys = []
        if not os.path.exists(csv_path):
            report.failed(f'{fname}: file not found')
            continue
        with open(csv_path, encoding='utf-8') as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if len(row) > 0 and row[0].strip():
                    keys.append(row[0].strip())
        file_cases[fname] = keys
        all_keys.extend(keys)
        report.log(f'  {fname}: {len(keys)} cases')

    total = len(all_keys)
    unique = len(set(all_keys))
    report.log(f'\n  Total rows: {total}')
    report.log(f'  Unique keys: {unique}')
    report.log(f'  Duplicates across files: {total - unique}')

    if total == unique:
        report.passed(f'No duplicate keys across CSV files ({total} unique)')
    else:
        dups = [k for k, c in Counter(all_keys).items() if c > 1]
        report.failed(f'{len(dups)} duplicate keys: {dups[:10]}')

    # Compare against snapshot
    snap = load_snapshot()
    snap_keys = set(snap.keys())
    csv_keys = set(all_keys)

    in_snap_not_csv = snap_keys - csv_keys
    in_csv_not_snap = csv_keys - snap_keys

    if not in_snap_not_csv:
        report.passed(f'All {len(snap_keys)} snapshot cases found in CSV')
    else:
        report.failed(f'{len(in_snap_not_csv)} snapshot cases missing from CSV: {list(in_snap_not_csv)[:10]}')

    if not in_csv_not_snap:
        report.passed(f'All {len(csv_keys)} CSV cases found in snapshot')
    else:
        report.warn(f'{len(in_csv_not_snap)} CSV cases not in snapshot: {list(in_csv_not_snap)[:10]}')

    # Check for cases with 0 steps
    csv_data = load_csv_full()
    zero_step_cases = [k for k, v in csv_data.items() if len(v['steps']) == 0]
    if zero_step_cases:
        report.warn(f'{len(zero_step_cases)} cases have 0 steps in CSV: {zero_step_cases[:10]}')
    else:
        report.passed(f'All {len(csv_data)} cases have at least 1 step')


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description='QA Touch Full Audit')
    parser.add_argument('--audit', type=str, default='all',
                       help='Comma-separated audit numbers (1-7) or "all"')
    parser.add_argument('--content-sample', type=int, default=50,
                       help='Sample size for content audit (default: 50)')
    parser.add_argument('--snapshot', type=str, default=None,
                       help='Snapshot JSON to audit against (default: newest in '
                            'config/qatouch_snapshots/)')
    parser.add_argument('--csv', type=str, default=None,
                       help='Comma-separated bulk-update CSV paths for audits 1,2,3,5,7')
    args = parser.parse_args()

    global SNAPSHOT_FILE, CSV_FILES
    if args.snapshot:
        SNAPSHOT_FILE = Path(args.snapshot)
    if args.csv:
        CSV_FILES = [c.strip() for c in args.csv.split(',') if c.strip()]

    if args.audit == 'all':
        audits_to_run = [1, 2, 3, 4, 5, 6, 7]
    else:
        audits_to_run = [int(x.strip()) for x in args.audit.split(',')]

    if not any(os.path.exists(c) for c in CSV_FILES):
        print('  No bulk-update CSV found. Every audit here compares the February import')
        print('  CSVs against QA Touch, so there is nothing to run. Pass --csv to point at')
        print('  the CSVs, or use the drift tools listed at the top of this file:')
        print('    python tools/qatouch_analytics.py snapshot ; python tools/qatouch_analytics.py report')
        print('    python tools/qatouch_contract_check.py')
        return

    print(f'\n{"=" * 60}')
    print(f'  QA TOUCH FULL AUDIT - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
    print(f'  Running audits: {audits_to_run}')
    print(f'{"=" * 60}\n')

    # Load data sources
    print('Loading data sources...')
    csv_data = load_csv_full()
    print(f'  CSV: {len(csv_data)} cases from {len(CSV_FILES)} files')
    snapshot = load_snapshot()
    print(f'  Snapshot: {len(snapshot)} cases')

    # Determine if we need Playwright (audits 1, 2, 3 need live API)
    need_live = bool(set(audits_to_run) & {1, 2, 3})
    page = None
    browser = None

    if need_live:
        print('\nLaunching browser for live API audits...')
        with sync_playwright() as p:
            browser, ctx, page = login(p)
            enter_project(page)
            session = SessionManager(browser, ctx, page)
            _run_audits(audits_to_run, session, csv_data, snapshot, args.content_sample)
            print('\nClosing browser...')
            browser.close()
    else:
        _run_audits(audits_to_run, None, csv_data, snapshot, args.content_sample)


def _run_audits(audits_to_run, session, csv_data, snapshot, content_sample):
    reports = []
    start = time.time()

    if 7 in audits_to_run:
        r = AuditReport('Audit #7 - CSV Cross-Reference')
        audit_csv_cross_reference(r)
        r.summary()
        reports.append(r)

    if 5 in audits_to_run:
        r = AuditReport('Audit #5 - Duplicate Title Detection')
        audit_duplicate_titles(csv_data, r)
        r.summary()
        reports.append(r)

    if 6 in audits_to_run:
        r = AuditReport('Audit #6 - Tag Preservation')
        audit_tag_preservation(csv_data, snapshot, r)
        r.summary()
        reports.append(r)

    if 4 in audits_to_run:
        r = AuditReport('Audit #4 - Module Integrity')
        audit_module_integrity(session, csv_data, snapshot, r)
        r.summary()
        reports.append(r)

    if 3 in audits_to_run:
        r = AuditReport('Audit #3 - Case Title Verification')
        audit_case_titles(session, csv_data, snapshot, r)
        r.summary()
        reports.append(r)

    if 2 in audits_to_run:
        r = AuditReport('Audit #2 - Step Content Verification')
        audit_step_content(session, csv_data, r, sample_size=content_sample)
        r.summary()
        reports.append(r)

    if 1 in audits_to_run:
        r = AuditReport('Audit #1 - Step Count Verification')
        audit_step_count(session, csv_data, r)
        r.summary()
        reports.append(r)

    # Write all reports
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for r in reports:
        path = r.write(REPORT_DIR)
        print(f'  Report saved: {path}')

    # Final summary
    elapsed = time.time() - start
    total_pass = sum(r.pass_count for r in reports)
    total_fail = sum(r.fail_count for r in reports)
    total_warn = sum(r.warn_count for r in reports)

    print(f'\n{"=" * 60}')
    print('  FULL AUDIT SUMMARY')
    print(f'  Total passed:   {total_pass}')
    print(f'  Total failed:   {total_fail}')
    print(f'  Total warnings: {total_warn}')
    print(f'  Total time:     {elapsed:.0f}s ({elapsed/60:.1f}m)')
    print(f'  Overall result: {"PASS" if total_fail == 0 else "FAIL"}')
    print(f'{"=" * 60}\n')

    # Write combined summary
    summary_path = REPORT_DIR / f'full_audit_summary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.txt'
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write(f'QA Touch Full Audit - {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
        f.write(f'{"=" * 60}\n\n')
        for r in reports:
            f.write(f'{r.name}: {"PASS" if r.fail_count == 0 else "FAIL"} '
                   f'(pass={r.pass_count} fail={r.fail_count} warn={r.warn_count})\n')
        f.write(f'\nOverall: {"PASS" if total_fail == 0 else "FAIL"}\n')
        f.write(f'Pass: {total_pass}  Fail: {total_fail}  Warn: {total_warn}\n')
    print(f'  Summary saved: {summary_path}')


if __name__ == '__main__':
    main()
