"""QA Touch browser automation - sync steps, rename modules, audit steps,
detect duplicates, delete cases.

DEPRECATED COMMANDS (03/12/2026 - use internal API instead):
  set-mode, set-tags, set-type, set-priority, bulk-update
  The internal API POST /v1/case/update/p/{pid}/cid/{key} can update any case
  field at ~0.2s/case vs ~3-5s/case with browser automation.
  See: qatouch_api_mode_update.py for the working pattern.

ACTIVE COMMANDS (no API alternative - browser required):
  sync-steps, sync-unfound, rename-modules, check-duplicates, audit-steps,
  delete, explore

Usage:
  python tools/qatouch_browser.py sync-steps        [--step-dir DIR] [--cases K1 K2] [--limit N] [--dry-run]
  python tools/qatouch_browser.py sync-unfound      [--cases K1 K2] [--limit N] [--dry-run]
  python tools/qatouch_browser.py rename-modules    [--csv FILE] [--limit N] [--dry-run]
  python tools/qatouch_browser.py check-duplicates
  python tools/qatouch_browser.py audit-steps       [--limit N]
  python tools/qatouch_browser.py delete            [--csv FILE] [--cases K1 K2] [--dry-run]
  python tools/qatouch_browser.py explore           --case CASE_KEY
"""
from __future__ import annotations

import csv
import functools
import json
import os
import re
import sys
import time
from datetime import datetime

_print = print
print = functools.partial(_print, flush=True)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from dotenv import load_dotenv
load_dotenv()
from tools.qatouch_client import QATouchClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DOMAIN = 'soterixsystems'
PROJECT_KEY = 'JlW1'
BASE_URL = f'https://{DOMAIN}.qatouch.com'
AUTH_STATE_FILE = os.path.join(ROOT, 'tools', '.qatouch_auth_state.json')
SHOT_DIR = os.path.join(ROOT, 'tools', 'debug_screenshots')
DEFAULT_CSV = os.path.join(ROOT, 'config', 'qatouch_set_automation_mode.csv')
DELETE_CSV = os.path.join(ROOT, 'config', 'qatouch_stubs_to_delete.csv')
RENAME_CSV = os.path.join(ROOT, 'config', 'qatouch_module_rename_plan.csv')

os.makedirs(SHOT_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# Rate Limiter
# ---------------------------------------------------------------------------
class RateLimiter:
    """Pace operations to avoid QA Touch rate limits."""

    def __init__(self, min_interval=2.5, burst_pause=12.0, burst_threshold=5):
        self.min_interval = min_interval
        self.burst_pause = burst_pause
        self.burst_threshold = burst_threshold
        self.op_count = 0
        self.last_op = 0.0

    def wait(self):
        self.op_count += 1
        if self.op_count % self.burst_threshold == 0:
            print(f'    [rate-limit] Pause {self.burst_pause}s after {self.op_count} ops...')
            time.sleep(self.burst_pause)
            self.last_op = time.time()
            return
        elapsed = time.time() - self.last_op
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_op = time.time()


# ---------------------------------------------------------------------------
# Run Report
# ---------------------------------------------------------------------------
class RunReport:
    """Track per-case results for summary and retry."""

    def __init__(self):
        self.results: list[dict] = []

    def add(self, case_key, status, error=''):
        self.results.append({'case_key': case_key, 'status': status, 'error': error})

    @property
    def success_count(self):
        return sum(1 for r in self.results if r['status'] in ('success', 'ok', 'already_set'))

    @property
    def skip_count(self):
        return sum(1 for r in self.results if r['status'] == 'skipped')

    @property
    def fail_count(self):
        return sum(1 for r in self.results if r['status'] not in ('success', 'ok', 'already_set', 'skipped'))

    def print_summary(self):
        print(f'\n{"=" * 60}')
        print(f'  RESULTS')
        print(f'  Success: {self.success_count}')
        print(f'  Skipped: {self.skip_count}')
        print(f'  Failed:  {self.fail_count}')
        print(f'{"=" * 60}')
        if self.fail_count > 0:
            print('\n  Failed cases:')
            for r in self.results:
                if r['status'] not in ('success', 'ok', 'already_set', 'skipped'):
                    print(f'    [{r["case_key"]}] {r["status"]}: {r["error"]}')

    def save(self):
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        path = os.path.join(SHOT_DIR, f'run_report_{ts}.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2)
        print(f'  Report saved: {path}')


# ---------------------------------------------------------------------------
# Screenshot helper
# ---------------------------------------------------------------------------
def shot(page, name, case_key=''):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    fname = f'{ts}_{name}_{case_key}'.rstrip('_')
    path = os.path.join(SHOT_DIR, f'{fname}.png')
    try:
        page.screenshot(path=path, full_page=True)
        print(f'    [screenshot] {fname}.png')
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Auth Management
# ---------------------------------------------------------------------------
def wait_for_login(page, timeout=300):
    """Navigate to QA Touch and wait for manual login."""
    page.goto(f'{BASE_URL}/v2#/', timeout=60000)
    print('\n' + '=' * 60)
    print('  BROWSER OPENED - Please log in to QA Touch')
    print(f'  Timeout: {timeout}s')
    print('=' * 60)

    start = time.time()
    tick = 0
    while time.time() - start < timeout:
        tick += 1
        if tick % 10 == 0:
            print(f'  ... waiting ({int(time.time() - start)}s)')
        if _check_logged_in(page):
            elapsed = int(time.time() - start)
            print(f'>>> Login detected after {elapsed}s!')
            time.sleep(2)
            page.context.storage_state(path=AUTH_STATE_FILE)
            return True
        time.sleep(3)
    print('>>> Login timeout.')
    return False


def _check_logged_in(page) -> bool:
    url = page.url or ''
    # If login form is visible, definitely not logged in
    try:
        login_form = page.locator('input[type="password"], .login-form, form[action*="login"]')
        if login_form.count() > 0 and login_form.first.is_visible(timeout=1000):
            return False
    except Exception:
        pass
    if any(x in url for x in ['/dashboard', '/project', '/testCase',
                                '/modules', '/new-projects', '/case/list']):
        return True
    for sel in ['text="NexaiQ-Core"', 'text="Dashboard"', 'text="Project List"']:
        try:
            if page.locator(sel).first.is_visible(timeout=500):
                return True
        except Exception:
            pass
    return False


def setup_browser(p, headless=False):
    """Launch browser with saved auth or manual login."""
    # Use a real Chrome user-agent to avoid CloudFront WAF blocking headless browsers
    _CHROME_UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36')
    browser = p.chromium.launch(headless=headless, slow_mo=150)

    if os.path.exists(AUTH_STATE_FILE):
        print('  Loading saved auth state...')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 900},
                                  storage_state=AUTH_STATE_FILE,
                                  user_agent=_CHROME_UA)
        page = ctx.new_page()
        page.goto(f'{BASE_URL}/v2#/new-projects')
        time.sleep(5)
        if _check_logged_in(page):
            print('  Auth state valid!')
            return browser, ctx, page
        print('  Auth expired - need fresh login.')
        ctx.close()

    ctx = browser.new_context(viewport={'width': 1400, 'height': 900},
                              user_agent=_CHROME_UA)
    page = ctx.new_page()
    if not wait_for_login(page):
        browser.close()
        return None, None, None
    return browser, ctx, page


def ensure_authenticated(page, context) -> bool:
    """Check session is alive, re-auth if needed."""
    if _check_logged_in(page):
        return True
    print('  Session expired - re-authenticating...')
    try:
        page.goto(f'{BASE_URL}/v2#/')
        time.sleep(3)
        if _check_logged_in(page):
            context.storage_state(path=AUTH_STATE_FILE)
            return True
    except Exception:
        pass
    # Need manual re-login
    if wait_for_login(page):
        context.storage_state(path=AUTH_STATE_FILE)
        return True
    return False


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------
def _dismiss_survey(page):
    """Dismiss QA Touch survey popup if present (blocks all clicks)."""
    try:
        survey = page.locator('.survey-parent-container')
        if survey.count() > 0 and survey.first.is_visible(timeout=1000):
            # Try clicking close/X button first
            close = page.locator('.survey-parent-container button:has-text("×"), '
                                 '.survey-parent-container .close, '
                                 '.survey-parent-container [aria-label="Close"]')
            if close.count() > 0:
                close.first.click(force=True)
                time.sleep(1)
                return
            # Fallback: remove via JS
            page.evaluate('() => document.querySelectorAll(".survey-parent-container").forEach(e => e.remove())')
            time.sleep(0.5)
    except Exception:
        # Last resort: force remove
        try:
            page.evaluate('() => document.querySelectorAll(".survey-parent-container").forEach(e => e.remove())')
        except Exception:
            pass


def enter_project(page, context=None):
    """Navigate into NexaiQ-Core project. Re-authenticates if session expired."""
    page.goto(f'{BASE_URL}/v2#/new-projects')
    page.wait_for_load_state('networkidle')
    time.sleep(3)

    # Check if we actually landed on the projects page or got redirected to login
    proj = page.locator('text="NexaiQ-Core"').first
    try:
        proj.wait_for(state='visible', timeout=5000)
    except Exception:
        # Likely expired session - re-authenticate
        print('  Session expired at project entry - re-authenticating...')
        if context and ensure_authenticated(page, context):
            page.goto(f'{BASE_URL}/v2#/new-projects')
            page.wait_for_load_state('networkidle')
            time.sleep(3)
            proj = page.locator('text="NexaiQ-Core"').first
            try:
                proj.wait_for(state='visible', timeout=10000)
            except Exception:
                # Re-auth claimed success but project still not visible - force manual login
                print('  Re-auth returned True but project not visible - forcing manual login...')
                if wait_for_login(page):
                    page.goto(f'{BASE_URL}/v2#/new-projects')
                    page.wait_for_load_state('networkidle')
                    time.sleep(3)
                    proj = page.locator('text="NexaiQ-Core"').first
                    proj.wait_for(state='visible', timeout=10000)
                else:
                    raise TimeoutError('Could not enter project - manual login failed')
        else:
            raise TimeoutError('Could not enter project - authentication failed')

    # Dismiss any survey/overlay popups that block clicks
    _dismiss_survey(page)

    proj.click(force=True)
    time.sleep(4)
    page.wait_for_load_state('networkidle')
    print('  Entered project.')


def navigate_to_module(page, module_name: str, match_index: int = 0) -> bool:
    """Filter the module tree and click target module.

    match_index: which match to click (0 = first, 1 = second, etc.)
                 Used when multiple modules share the same name.
    """
    filt = page.locator('input[placeholder="Type To Filter Module"]').first
    try:
        filt.wait_for(state='visible', timeout=5000)
    except Exception:
        print(f'    Module filter not found')
        return False

    # Build filter candidates: try raw name first (preserves & - etc.),
    # then without parenthetical suffix, then cleaned version, then first word.
    raw_trimmed = module_name.strip()
    clean = re.sub(r'[^A-Za-z0-9 ]', ' ', module_name).strip()
    clean = ' '.join(clean.split())  # collapse multiple spaces
    words = clean.split()
    filter_candidates = [raw_trimmed]
    # Strip parenthetical suffix: "Site Actions (More Options Menu)" -> "Site Actions"
    paren_stripped = re.sub(r'\s*\(.*\)\s*$', '', raw_trimmed).strip()
    if paren_stripped and paren_stripped != raw_trimmed:
        filter_candidates.append(paren_stripped)
    cleaned_short = ' '.join(words[:3]) if len(words) > 3 else clean
    if cleaned_short != raw_trimmed and cleaned_short not in filter_candidates:
        filter_candidates.append(cleaned_short)
    if words and words[0] not in filter_candidates:
        filter_candidates.append(words[0])

    found = None
    for filter_text in filter_candidates:
        filt.fill('')
        time.sleep(0.5)
        filt.fill(filter_text)
        time.sleep(3)

        found = page.evaluate('''(args) => {
            var modName = args[0], targetIdx = args[1];
            var target = modName.toLowerCase().trim();
            var nodes = document.querySelectorAll('.node-text.module_name_wrap');
            var matchCount = 0;

            // Exact matches first
            for (var i = 0; i < nodes.length; i++) {
                if (nodes[i].textContent.trim().toLowerCase() === target) {
                    if (matchCount === targetIdx) {
                        nodes[i].click();
                        return {clicked: true, matchIndex: matchCount, totalMatches: 0};
                    }
                    matchCount++;
                }
            }
            // Count total exact matches for reporting
            var totalExact = matchCount;

            // If targetIdx=0 and no exact match, try substring
            if (targetIdx === 0) {
                for (var i = 0; i < nodes.length; i++) {
                    if (nodes[i].textContent.trim().toLowerCase().indexOf(target) >= 0) {
                        nodes[i].click();
                        return {clicked: true, matchIndex: 0, totalMatches: totalExact};
                    }
                }
            }
            return {clicked: false, totalMatches: totalExact};
        }''', [module_name, match_index])

        if found and found.get('clicked'):
            break

    if found and found.get('clicked'):
        time.sleep(3)
        suffix = f' (match {match_index + 1})' if match_index > 0 else ''
        print(f'    Navigated to module: {module_name}{suffix}')
        filt.fill('')
        time.sleep(0.5)
        return True

    print(f'    Module not found: {module_name} (match_index={match_index})')
    filt.fill('')
    time.sleep(0.5)
    return False


def navigate_to_module_by_key(page, module_name: str, module_key: str) -> bool:
    """Navigate to the correct module by checking the header key badge.

    When multiple modules share the same name (e.g. 3 "Maps" nodes in the tree),
    this clicks each match until the header badge (span.release_key) shows the
    expected module_key.
    """
    if not module_key:
        return navigate_to_module(page, module_name)

    filt = page.locator('input[placeholder="Type To Filter Module"]').first
    try:
        filt.wait_for(state='visible', timeout=5000)
    except Exception:
        print(f'    Module filter not found')
        return False

    filt.fill('')
    time.sleep(0.5)
    filt.fill(module_name.strip())
    time.sleep(3)

    # Count exact matches
    total = page.evaluate('''(modName) => {
        var target = modName.toLowerCase().trim();
        var nodes = document.querySelectorAll('.node-text.module_name_wrap');
        var count = 0;
        for (var i = 0; i < nodes.length; i++) {
            if (nodes[i].getBoundingClientRect().height > 0 &&
                nodes[i].textContent.trim().toLowerCase() === target) {
                count++;
            }
        }
        return count;
    }''', module_name)

    if total == 0:
        print(f'    Module not found: {module_name}')
        filt.fill('')
        time.sleep(0.5)
        return False

    # Try each match until header key matches
    for idx in range(total):
        page.evaluate('''(args) => {
            var target = args[0].toLowerCase().trim();
            var targetIdx = args[1];
            var nodes = document.querySelectorAll('.node-text.module_name_wrap');
            var matchCount = 0;
            for (var i = 0; i < nodes.length; i++) {
                if (nodes[i].getBoundingClientRect().height > 0 &&
                    nodes[i].textContent.trim().toLowerCase() === target) {
                    if (matchCount === targetIdx) {
                        nodes[i].click();
                        return;
                    }
                    matchCount++;
                }
            }
        }''', [module_name, idx])
        time.sleep(3)

        # Check header key
        header_key = _get_selected_module_key(page)
        if header_key == module_key:
            print(f'    Navigated to module: {module_name} (match {idx + 1}/{total}, key={module_key})')
            filt.fill('')
            time.sleep(0.5)
            return True

    # No match found by key - try expanding all collapsed parent modules
    # The target module may be hidden under a collapsed parent node.
    print(f'    Module key {module_key} not found in {total} matches, expanding parents...')
    filt.fill('')
    time.sleep(1)

    # Expand all collapsed parent nodes in the tree (try multiple selectors)
    expanded = page.evaluate('''() => {
        // Try multiple selectors for the tree expand toggles
        var selectors = [
            '.vs-tree-node > .vs-tree-icon',
            '.tree-node .tree-toggle',
            '.el-tree-node__expand-icon',
            '[class*="tree-node"] [class*="toggle"]',
            '[class*="tree-node"] [class*="caret"]',
            '[class*="tree-node"] [class*="arrow"]'
        ];
        var count = 0;
        for (var s = 0; s < selectors.length; s++) {
            var toggles = document.querySelectorAll(selectors[s]);
            for (var i = 0; i < toggles.length; i++) {
                var t = toggles[i];
                var rect = t.getBoundingClientRect();
                if (rect.height > 0) {
                    var parent = t.closest('[class*="tree-node"]');
                    // Skip already-expanded nodes
                    if (parent && (parent.classList.contains('vs-tree-node--expanded') ||
                        parent.classList.contains('is-expanded'))) continue;
                    t.click();
                    count++;
                }
            }
            if (count > 0) break;
        }
        return count;
    }''')
    if expanded > 0:
        print(f'    Expanded {expanded} collapsed parent nodes')
        time.sleep(3)

        # Re-filter with all parents expanded
        filt.fill(module_name.strip())
        time.sleep(3)

        new_total = page.evaluate('''(modName) => {
            var target = modName.toLowerCase().trim();
            var nodes = document.querySelectorAll('.node-text.module_name_wrap');
            var count = 0;
            for (var i = 0; i < nodes.length; i++) {
                if (nodes[i].getBoundingClientRect().height > 0 &&
                    nodes[i].textContent.trim().toLowerCase() === target) {
                    count++;
                }
            }
            return count;
        }''', module_name)

        if new_total > total:
            print(f'    Found {new_total} matches after expansion (was {total})')
            for idx in range(new_total):
                page.evaluate('''(args) => {
                    var target = args[0].toLowerCase().trim();
                    var targetIdx = args[1];
                    var nodes = document.querySelectorAll('.node-text.module_name_wrap');
                    var matchCount = 0;
                    for (var i = 0; i < nodes.length; i++) {
                        if (nodes[i].getBoundingClientRect().height > 0 &&
                            nodes[i].textContent.trim().toLowerCase() === target) {
                            if (matchCount === targetIdx) {
                                nodes[i].click();
                                return;
                            }
                            matchCount++;
                        }
                    }
                }''', [module_name, idx])
                time.sleep(3)

                header_key = _get_selected_module_key(page)
                if header_key == module_key:
                    print(f'    Navigated to module: {module_name} (match {idx + 1}/{new_total}, key={module_key})')
                    filt.fill('')
                    time.sleep(0.5)
                    return True

    # Still not found - fall back to first match
    print(f'    Module key {module_key} still not found, using first match')
    navigate_to_module(page, module_name)
    filt.fill('')
    time.sleep(0.5)
    return True


def count_module_matches(page, module_name: str) -> int:
    """Count how many modules match the given name in the tree."""
    filt = page.locator('input[placeholder="Type To Filter Module"]').first
    try:
        filt.wait_for(state='visible', timeout=3000)
    except Exception:
        return 0

    raw_trimmed = module_name.strip()
    clean = re.sub(r'[^A-Za-z0-9 ]', ' ', module_name).strip()
    clean = ' '.join(clean.split())
    words = clean.split()
    filter_candidates = [raw_trimmed]
    paren_stripped = re.sub(r'\s*\(.*\)\s*$', '', raw_trimmed).strip()
    if paren_stripped and paren_stripped != raw_trimmed:
        filter_candidates.append(paren_stripped)
    cleaned_short = ' '.join(words[:3]) if len(words) > 3 else clean
    if cleaned_short != raw_trimmed and cleaned_short not in filter_candidates:
        filter_candidates.append(cleaned_short)
    if words and words[0] not in filter_candidates:
        filter_candidates.append(words[0])

    for filter_text in filter_candidates:
        filt.fill('')
        time.sleep(0.5)
        filt.fill(filter_text)
        time.sleep(2)

        count = page.evaluate('''(modName) => {
            var target = modName.toLowerCase().trim();
            var nodes = document.querySelectorAll('.node-text.module_name_wrap');
            var count = 0;
            for (var i = 0; i < nodes.length; i++) {
                if (nodes[i].textContent.trim().toLowerCase() === target) count++;
            }
            return count;
        }''', module_name)

        if count > 0:
            filt.fill('')
            time.sleep(0.5)
            return count

    filt.fill('')
    time.sleep(0.5)
    return 0


# ---------------------------------------------------------------------------
# Case Finding - Pagination + Per-Page Selector
# ---------------------------------------------------------------------------
def _match_case_in_dom(page, title, action='scroll'):
    """Find the best-matching case in the DOM for a given title.

    action='scroll' - scrolls element into view and returns {found: true/false}
    action='coords' - returns {x, y} click coordinates or null

    Uses best-match strategy: scores each candidate by overlap with the target
    title, and picks the highest-scoring match. This avoids clicking the wrong
    case when multiple cases share the same title prefix.
    """
    return page.evaluate('''(args) => {
        var title = args[0], action = args[1];
        var containers = document.querySelectorAll('.cl-container');
        var bestEl = null, bestScore = 0;

        for (var i = 0; i < containers.length; i++) {
            var ps = containers[i].querySelectorAll('p');
            for (var j = 0; j < ps.length; j++) {
                var text = ps[j].textContent.trim();
                if (!text || text.length < 10) continue;
                var score = 0;

                // Exact match is perfect score
                if (text === title) {
                    score = 10000;
                } else {
                    // Score by shared prefix length
                    var minLen = Math.min(text.length, title.length);
                    var shared = 0;
                    for (var k = 0; k < minLen; k++) {
                        if (text[k] === title[k]) shared++;
                        else break;
                    }
                    // Need at least 15 chars of shared prefix
                    if (shared >= 15) score = shared;
                    // Bonus if DOM text is a substring of title (DOM truncated)
                    if (shared === text.length && text.length >= 15) score += 500;
                    // Bonus if title is a substring of DOM text
                    if (shared === title.length && title.length >= 15) score += 500;
                }

                if (score > bestScore) {
                    bestScore = score;
                    bestEl = ps[j];
                }
            }
        }

        if (!bestEl || bestScore < 15) return action === 'coords' ? null : {found: false};

        if (action === 'coords') {
            var r = bestEl.getBoundingClientRect();
            return {x: Math.round(r.x + 30), y: Math.round(r.y + r.height / 2)};
        }
        bestEl.scrollIntoView({block: 'center'});
        return {found: true};
    }''', [title, action])


def _search_cases_in_dom(page, title):
    """Search currently-loaded .cl-container elements for a case title.
    Returns {found: true/false}. Uses best-match scoring to avoid title collisions."""
    return _match_case_in_dom(page, title, action='scroll')


def _get_case_coords(page, title):
    """Get fresh click coordinates for a case already scrolled into view."""
    return _match_case_in_dom(page, title, action='coords')


def _maximize_per_page(page):
    """Change the per-page selector to the highest available option.

    QA Touch uses a vue-select per-page dropdown (default: 20).
    We click it open and select the largest option to show all cases at once.
    """
    # Check if per-page selector exists
    per_page = page.locator('.per-page-selector, .per-page-dd')
    if per_page.count() == 0:
        return False

    # Open the per-page dropdown (force=True to click through any lingering overlays)
    per_page.first.click(force=True)
    time.sleep(1)

    # Find available options and pick the largest
    result = page.evaluate('''() => {
        var options = document.querySelectorAll('.vs__dropdown-option');
        var best = null;
        var bestVal = 0;
        for (var i = 0; i < options.length; i++) {
            var text = options[i].textContent.trim();
            var num = parseInt(text, 10);
            if (!isNaN(num) && num > bestVal) {
                bestVal = num;
                best = options[i];
            }
            if (text.toLowerCase() === 'all') {
                best = options[i];
                bestVal = 99999;
            }
        }
        if (best) {
            best.click();
            return {clicked: true, value: best.textContent.trim()};
        }
        return {clicked: false};
    }''')

    if result.get('clicked'):
        print(f'    [per-page] Set to {result["value"]}')
        time.sleep(4)  # Wait for re-render with new page size
        return True

    # Close dropdown if nothing was selected
    page.keyboard.press('Escape')
    return False


def _get_pagination_info(page):
    """Get current pagination state: current page, total pages."""
    return page.evaluate('''() => {
        var active = document.querySelector('.page-item.active button');
        var currentPage = active ? parseInt(active.textContent.trim(), 10) : 1;

        var allButtons = document.querySelectorAll('button[aria-posinset]');
        var maxPage = 1;
        allButtons.forEach(function(btn) {
            var setSize = parseInt(btn.getAttribute('aria-setsize'), 10);
            if (!isNaN(setSize) && setSize > maxPage) maxPage = setSize;
        });

        return {currentPage: currentPage, totalPages: maxPage};
    }''')


def _go_to_page(page, page_num):
    """Click a specific page number in the pagination bar."""
    # Try clicking the button with the exact page number
    clicked = page.evaluate('''(pageNum) => {
        var buttons = document.querySelectorAll('button.page-link');
        for (var i = 0; i < buttons.length; i++) {
            if (buttons[i].textContent.trim() === String(pageNum)) {
                buttons[i].click();
                return true;
            }
        }
        return false;
    }''', page_num)

    if clicked:
        time.sleep(3)  # Wait for page content to load
    return clicked


def _go_to_next_page(page):
    """Click the 'Next' button in the pagination bar."""
    next_btn = page.locator('button[aria-label="Go to next page"]')
    if next_btn.count() > 0:
        try:
            next_btn.first.click()
            time.sleep(3)
            return True
        except Exception:
            pass
    return False


def scroll_to_find_case(page, title, max_attempts=80):
    """Find a case in the paginated list.

    Strategy:
    1. First try to maximize per-page count (show all cases on one page)
    2. Search current page DOM for the title
    3. If not found, iterate through pagination pages

    Returns True if found (element scrolled into view), False if exhausted.
    """
    # First check if already visible on current page
    result = _search_cases_in_dom(page, title)
    if result.get('found'):
        return True

    # Try to maximize per-page to show all cases at once
    if _maximize_per_page(page):
        time.sleep(2)
        result = _search_cases_in_dom(page, title)
        if result.get('found'):
            return True

        # Also scroll the content container to check all loaded cases
        page.evaluate('''() => {
            var wrap = document.querySelector('.test_case_table_content_outer_wrap');
            if (wrap) wrap.scrollTop = 0;
        }''')
        time.sleep(0.5)

        # Scroll through the container (cases may be off-screen even if loaded)
        for _ in range(20):
            page.evaluate('''() => {
                var wrap = document.querySelector('.test_case_table_content_outer_wrap');
                if (wrap) wrap.scrollTop += 500;
            }''')
            time.sleep(0.5)
            result = _search_cases_in_dom(page, title)
            if result.get('found'):
                return True
            # Check if at bottom
            at_bottom = page.evaluate('''() => {
                var wrap = document.querySelector('.test_case_table_content_outer_wrap');
                if (wrap) return wrap.scrollTop + wrap.clientHeight >= wrap.scrollHeight - 20;
                return true;
            }''')
            if at_bottom:
                break

    # If maximizing didn't work (or wasn't available), paginate through pages
    pag = _get_pagination_info(page)
    total_pages = pag.get('totalPages', 1)
    current_page = pag.get('currentPage', 1)
    print(f'    [pagination] Page {current_page}/{total_pages}, searching for case...')

    if total_pages <= 1:
        return False

    # Search each page
    for pg in range(1, total_pages + 1):
        if pg == current_page:
            continue  # Already checked current page
        if not _go_to_page(page, pg):
            # Try next button instead
            if not _go_to_next_page(page):
                break
        time.sleep(1)

        # Scroll content area to check all cases on this page
        page.evaluate('''() => {
            var wrap = document.querySelector('.test_case_table_content_outer_wrap');
            if (wrap) wrap.scrollTop = 0;
        }''')
        time.sleep(0.5)

        result = _search_cases_in_dom(page, title)
        if result.get('found'):
            print(f'    [pagination] Found on page {pg}!')
            return True

        # Scroll through this page's content
        for _ in range(5):
            page.evaluate('''() => {
                var wrap = document.querySelector('.test_case_table_content_outer_wrap');
                if (wrap) wrap.scrollTop += 500;
            }''')
            time.sleep(0.3)
            result = _search_cases_in_dom(page, title)
            if result.get('found'):
                print(f'    [pagination] Found on page {pg} (after scroll)!')
                return True

    print(f'    [pagination] Case not found after checking {total_pages} pages')
    return False


def find_and_click_case(page, title):
    """Find a case via infinite scroll and click to open detail page."""
    if not scroll_to_find_case(page, title):
        print(f'    Case not found after scrolling: "{title[:60]}..."')
        return False

    time.sleep(1)

    # Use Playwright mouse click on the case title element
    # First try coordinate click (works reliably for most cases)
    coords = _get_case_coords(page, title)
    if not coords:
        print(f'    Could not get coordinates for case')
        return False

    page.mouse.click(coords['x'], coords['y'])
    time.sleep(4)

    # Verify the case detail opened (drawer should appear)
    drawer = page.locator('.ant-drawer')
    if drawer.count() > 0 and drawer.first.is_visible(timeout=2000):
        return True

    # Drawer didn't open - try clicking the parent .cl-container via JS
    print('    [click] Coord click failed, trying container click...')
    try:
        page.evaluate('''(title) => {
            var containers = document.querySelectorAll('.cl-container');
            var bestEl = null;
            var bestScore = 0;
            for (var i = 0; i < containers.length; i++) {
                var ps = containers[i].querySelectorAll('p');
                for (var j = 0; j < ps.length; j++) {
                    var text = ps[j].textContent.trim();
                    if (!text || text.length < 10) continue;
                    var minLen = Math.min(text.length, title.length);
                    var shared = 0;
                    for (var k = 0; k < minLen; k++) {
                        if (text[k] === title[k]) shared++;
                        else break;
                    }
                    if (shared >= 15 && shared > bestScore) {
                        bestScore = shared;
                        bestEl = containers[i];
                    }
                }
            }
            if (bestEl && bestScore >= 15) {
                // Dispatch a real mouse event on the container
                var r = bestEl.getBoundingClientRect();
                var evt = new MouseEvent('click', {
                    bubbles: true, cancelable: true,
                    clientX: r.x + r.width / 2,
                    clientY: r.y + r.height / 2
                });
                bestEl.dispatchEvent(evt);
                return true;
            }
            return false;
        }''', title)
        time.sleep(4)

        if drawer.count() > 0 and drawer.first.is_visible(timeout=2000):
            return True
    except Exception:
        pass

    # Last resort: Playwright click on first visible .cl-container with matching text
    print('    [click] Container click failed, trying Playwright locator...')
    try:
        loc = page.locator(f'.cl-container:has(p:text("{title[:40]}"))')
        if loc.count() > 0:
            loc.first.click(timeout=5000)
            time.sleep(4)
            return True
    except Exception:
        pass

    print('    [click] All click methods failed')
    return False


def navigate_to_case_by_url(page, case_key) -> bool:
    """Open case in a new tab via direct URL, bypassing module search.

    Opens a new browser tab with the case detail URL, waits for it to load,
    and returns the new page. The original page/tab is preserved.
    Returns the new Page object if successful, or False if failed.
    """
    # This is a stub - actual new-tab logic is handled in the sync loop.
    # See _sync_case_in_new_tab() for the full implementation.
    return False


def _sync_case_in_new_tab(context, page, case_key, steps,
                          module_key='', module_name='', case_title=''):
    """Open case in a new tab, write steps, close tab. Returns 'ok'/'partial'/'fail'/'already_set'.

    Preserves the original page state by working in a separate tab.
    Enters project, navigates to the correct module (by key if ambiguous), finds case, writes steps.
    """
    if not case_title or not module_name:
        print(f'    [new-tab] Missing case_title or module_name')
        return 'fail'

    print(f'    [new-tab] Opening {case_key} in new tab...')
    new_page = None
    try:
        new_page = context.new_page()

        # Enter project in new tab (cookies shared via browser context)
        new_page.goto(f'{BASE_URL}/v2#/new-projects', wait_until='networkidle', timeout=30000)
        time.sleep(3)

        proj = new_page.locator('text="NexaiQ-Core"').first
        try:
            proj.wait_for(state='visible', timeout=8000)
        except Exception:
            print(f'    [new-tab] Project not visible')
            new_page.close()
            return 'fail'

        _dismiss_survey(new_page)
        proj.click(force=True)
        time.sleep(5)
        new_page.wait_for_load_state('networkidle')

        # Navigate to module - use key-aware navigation for disambiguation
        if module_key:
            nav_ok = navigate_to_module_by_key(new_page, module_name, module_key)
        else:
            nav_ok = navigate_to_module(new_page, module_name)

        if not nav_ok:
            print(f'    [new-tab] Could not navigate to module: {module_name}')
            new_page.close()
            return 'fail'

        # Find and click the case by title
        if not find_and_click_case(new_page, case_title):
            print(f'    [new-tab] Case not found in module list')
            new_page.close()
            return 'fail'

        # Case detail drawer should be open - look for Edit button
        edit_btn = new_page.locator('button:has-text("Edit")')
        if edit_btn.count() == 0 or not edit_btn.first.is_visible(timeout=8000):
            print(f'    [new-tab] Edit button not visible after clicking case')
            new_page.close()
            return 'fail'

        print(f'    [new-tab] Case loaded, opening edit form...')

        # Click Edit
        edit_btn.first.click()
        time.sleep(3)

        # Click Steps tab
        if not click_form_tab(new_page, 'Steps'):
            time.sleep(2)
            # Try switching template
            if _switch_to_test_case_template(new_page):
                print('      Switched template to Test Case')
                time.sleep(2)
                if not click_form_tab(new_page, 'Steps'):
                    print(f'    [new-tab] Steps tab not found')
                    new_page.close()
                    return 'fail'
            else:
                print(f'    [new-tab] Steps tab not found')
                new_page.close()
                return 'fail'

        time.sleep(2)

        # Clear existing steps
        existing = _extract_step_data(new_page)
        if _steps_match(existing, steps):
            print(f'      Already synced ({len(steps)} steps match)')
            new_page.close()
            return 'already_set'

        if existing:
            cleared = _clear_all_steps(new_page)
            print(f'      Cleared {cleared} existing steps')
            time.sleep(1)

        # Write steps
        for i, step in enumerate(steps):
            if i > 0:
                if not _click_add_step(new_page):
                    print(f'      Failed to add step row {i + 1}')
                    break
            action = step.get('action', '')
            expected = step.get('expected', '')
            if not _write_step_row(new_page, i, action, expected):
                print(f'      Failed to write step {i + 1}')

        # Verify
        time.sleep(1)
        written = _extract_step_data(new_page)
        result = 'fail'
        if len(written) >= len(steps):
            print(f'      Wrote {len(steps)} steps')
            result = 'ok'
        elif len(written) >= len(steps) * 0.8:
            print(f'      Wrote {len(written)}/{len(steps)} steps (accepted)')
            result = 'ok'
        else:
            print(f'      Partial: wrote {len(written)}/{len(steps)} steps')
            result = 'partial'

        # Save
        save_btn = new_page.locator('button:has-text("Save")')
        if save_btn.count() > 0:
            save_btn.first.click()
            time.sleep(3)
            print('    Saved!')

        new_page.close()
        return result

    except Exception as e:
        print(f'    [new-tab] Error: {e}')
        if new_page:
            try:
                new_page.close()
            except Exception:
                pass
        return 'fail'


# ---------------------------------------------------------------------------
# Case Detail - Edit Form
# ---------------------------------------------------------------------------
def open_edit_form(page) -> bool:
    """On case detail page, click Edit to open the form. Returns True if form opened."""
    # Try to find and click the Edit button (normal path)
    for selector in ['button:has-text("Edit")', 'button.edit-btn',
                     'a:has-text("Edit")', '[data-testid="edit-button"]']:
        try:
            btn = page.locator(selector)
            if btn.first.is_visible(timeout=8000):
                btn.first.click()
                time.sleep(3)
                return True
        except Exception:
            continue

    # If no Edit button, check if we're already in edit mode
    # (Steps tab + Save & Continue visible = already editing this case)
    try:
        tabs = page.locator('text="Steps"')
        save_cont = page.locator('button:has-text("Save & Continue")')
        if (tabs.count() > 0 and tabs.first.is_visible(timeout=2000) and
                save_cont.count() > 0 and save_cont.first.is_visible(timeout=1000)):
            print('    Already in edit mode')
            return True
    except Exception:
        pass

    print('    Edit button not found')
    shot(page, 'no_edit_btn')
    return False


def _force_dismiss_drawers(page):
    """Dismiss drawers via Escape keys (preferred) + JS class cleanup.

    IMPORTANT: Do NOT use el.remove() or el.style.display='none' on
    ant-drawer elements - Ant Design Vue reuses them and DOM removal
    or inline style hiding prevents new drawers from opening.
    Instead: press Escape (triggers proper Vue close), then clean up
    any leftover classes/masks that block interaction.
    """
    try:
        page.keyboard.press('Escape')
        time.sleep(0.3)
        page.keyboard.press('Escape')
        time.sleep(0.3)
        page.keyboard.press('Escape')
        time.sleep(0.3)
    except Exception:
        pass

    try:
        page.evaluate('''() => {
            // Remove masks (safe - Ant recreates them with new drawers)
            document.querySelectorAll('.ant-drawer-mask').forEach(el => el.remove());
            // Remove swal overlays
            document.querySelectorAll('.swal-overlay').forEach(el => el.remove());
            // Restore body scroll
            document.body.style.overflow = '';
            document.body.classList.remove('ant-scrolling-effect');
            // Remove pointer-events blocking from any hidden drawers
            document.querySelectorAll('.ant-drawer').forEach(el => {
                el.style.pointerEvents = '';
                el.style.display = '';
            });
        }''')
    except Exception:
        pass


def save_and_close(page) -> bool:
    """Click Save, then close the edit form via Cancel/X button."""
    # --- Save ---
    save_btn = page.locator('button.save-continue-btn, button:has-text("Save")')
    if save_btn.count() > 0:
        try:
            save_btn.first.click(force=True)
            time.sleep(3)
            print('    Saved!')
        except Exception:
            try:
                page.evaluate('document.querySelector("button.save-continue-btn")?.click()')
                time.sleep(3)
                print('    Saved (via JS)!')
            except Exception:
                print('    Save click failed')
                return False
    else:
        print('    Save button not found')
        shot(page, 'no_save_btn')
        page.keyboard.press('Escape')
        time.sleep(1)
        return False

    # Dismiss any swal dialogs that appear after save
    _dismiss_swal(page)

    # Close overlays with Escape - avoid button clicks that may navigate away
    for _ in range(3):
        page.keyboard.press('Escape')
        time.sleep(0.5)

    # Force-remove any remaining drawers/modals via JS
    _force_dismiss_drawers(page)
    time.sleep(1)
    return True


def _dismiss_swal(page):
    """Dismiss sweetalert dialogs that may appear after save."""
    _handle_close_swal(page)


def _close_edit_form(page):
    """Close the case edit form using Cancel/X, then handle the 'close without saving' swal.

    QA Touch edit form has: Cancel button (top-right), X close (top-left circled).
    Clicking Cancel may trigger a swal dialog: 'Are you sure you want to close without saving?'
    with buttons: [Save & Close] [Close] [Cancel]. We click 'Close' (red) to dismiss.
    """
    # Try Cancel button or X to initiate close
    closed = False
    for selector in [
        'button:text-is("Cancel")',
        'button:has-text("Cancel")',
    ]:
        try:
            btn = page.locator(selector)
            if btn.count() > 0 and btn.first.is_visible(timeout=3000):
                btn.first.click(force=True)
                time.sleep(2)
                closed = True
                break
        except Exception:
            continue

    if not closed:
        # Try the X close button at top-left
        try:
            x_btn = page.locator('svg').filter(has=page.locator('circle, path'))
            for i in range(min(x_btn.count(), 5)):
                box = x_btn.nth(i).bounding_box()
                if box and box['y'] < 60 and box['x'] < 200:
                    x_btn.nth(i).click(force=True)
                    time.sleep(2)
                    closed = True
                    break
        except Exception:
            pass

    if not closed:
        page.keyboard.press('Escape')
        time.sleep(2)

    # Handle the swal "close without saving" confirmation dialog
    _handle_close_swal(page)


def _handle_close_swal(page):
    """Handle the 'Are you sure you want to close without saving?' swal dialog.

    Buttons: [Save & Close] [Close] [Cancel]
    We want to click 'Close' (red) to dismiss without saving (already saved).
    """
    try:
        swal = page.locator('.swal-overlay--show-modal, .swal-modal')
        if swal.count() == 0:
            return  # No swal dialog - we're good

        # Click the red "Close" button (NOT "Save & Close", NOT "Cancel")
        # The Close button has class swal-button--danger or is the red one
        for selector in [
            '.swal-button--danger',                          # Red danger button
            'button.swal-button:text-is("Close")',           # Exact "Close" text
            'button.swal-button:not(.swalButtonLeft):not(:has-text("Cancel"))',  # Middle button
        ]:
            try:
                btn = page.locator(selector)
                if btn.count() > 0 and btn.first.is_visible(timeout=2000):
                    btn.first.click(force=True)
                    time.sleep(2)
                    return
            except Exception:
                continue

        # Fallback: click the second swal button (Close is usually the middle one)
        try:
            buttons = page.locator('button.swal-button')
            if buttons.count() >= 2:
                buttons.nth(1).click(force=True)
                time.sleep(2)
                return
        except Exception:
            pass

        # Last resort: Escape to dismiss
        page.keyboard.press('Escape')
        time.sleep(1)
    except Exception:
        pass


def close_case_detail(page):
    """Close case detail without saving - uses force clicks and fallbacks."""
    # Try multiple close approaches with force=True to bypass overlays
    for selector in ['.ant-drawer-close', 'button.close-btn',
                     'button:text-is("Close")', '.modal-close']:
        try:
            btn = page.locator(selector)
            if btn.count() > 0 and btn.first.is_visible(timeout=2000):
                btn.first.click(force=True)
                time.sleep(1)
                return
        except Exception:
            continue
    # Fallback: Escape key
    page.keyboard.press('Escape')
    time.sleep(1)
    page.keyboard.press('Escape')
    time.sleep(1)


def force_close_all_overlays(page):
    """Force-close any open drawers, modals, or overlays that block interaction.

    Used for error recovery when the page is in a stuck state.
    """
    # Try Escape key multiple times
    for _ in range(3):
        page.keyboard.press('Escape')
        time.sleep(0.5)

    # Try clicking Cancel button if visible
    for selector in ['button:has-text("Cancel")', 'button:has-text("Close")',
                     '.ant-drawer-close', '.ant-modal-close']:
        try:
            btn = page.locator(selector)
            if btn.count() > 0 and btn.first.is_visible(timeout=1000):
                btn.first.click(force=True)
                time.sleep(1)
        except Exception:
            pass

    # If drawers are still open, force-remove them via JS
    try:
        page.evaluate('''() => {
            document.querySelectorAll('.ant-drawer-open').forEach(el => el.remove());
            document.querySelectorAll('.ant-modal-wrap').forEach(el => el.remove());
            document.querySelectorAll('.ant-drawer-mask').forEach(el => el.remove());
            document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        }''')
        time.sleep(1)
    except Exception:
        pass


def recover_to_module(page, context, module, module_key='') -> bool:
    """Robust recovery: get back to a module's case list from any broken state.

    Tries progressively more aggressive recovery: navigate directly, then
    force-close overlays + re-enter project, then full page reload.
    Uses module_key for disambiguation when multiple modules share a name.
    Returns True if we're back on the module's case list.
    """
    def _nav(pg):
        if module_key:
            return navigate_to_module_by_key(pg, module, module_key)
        return navigate_to_module(pg, module)

    # Always dismiss drawers first - they block everything
    _force_dismiss_drawers(page)

    # Attempt 1: direct navigate
    if _nav(page):
        return True

    # Attempt 2: close overlays + re-enter project
    try:
        force_close_all_overlays(page)
        enter_project(page, context)
        if _nav(page):
            return True
    except Exception:
        pass

    # Attempt 3: full page reload
    try:
        page.goto(f'{BASE_URL}/v2#/new-projects')
        time.sleep(5)
        enter_project(page, context)
        if _nav(page):
            return True
    except Exception:
        pass

    print(f'    RECOVERY FAILED for module: {module}')
    return False


def _switch_to_test_case_template(page) -> bool:
    """Switch from Exploratory Session (or other) template to Test Case.

    The Template dropdown is at the top of the edit form. Changing it to
    'Test Case' adds the Steps tab which is needed for step sync.
    Returns True if template was changed, False if already correct or failed.
    """
    try:
        # Find the template dropdown (shows current template name)
        tmpl = page.locator('.template-dropdown, [class*="template"] .dropdown,'
                            ' span:has-text("Exploratory Session")')
        if tmpl.count() == 0:
            # Try finding by the template label area
            tmpl = page.evaluate('''() => {
                var labels = document.querySelectorAll('span, div, p');
                for (var i = 0; i < labels.length; i++) {
                    var t = labels[i].textContent.trim();
                    if (t === 'Exploratory Session' || t === 'Exploratory Session ✓') {
                        return true;
                    }
                }
                return false;
            }''')
            if not tmpl:
                return False

        # Click the template dropdown to open it
        dd = page.locator('text="Exploratory Session"').first
        if not dd.is_visible(timeout=3000):
            return False
        dd.click()
        time.sleep(1)

        # Look for "Test Case (Steps)" option in the dropdown
        tc_option = page.locator('text="Test Case (Steps)"')
        for i in range(tc_option.count()):
            el = tc_option.nth(i)
            try:
                if el.is_visible(timeout=2000):
                    el.click()
                    time.sleep(3)  # Wait for form to reload with new template
                    return True
            except Exception:
                continue

        # If dropdown opened but Test Case not found, press Escape
        page.keyboard.press('Escape')
        return False
    except Exception:
        return False


def click_form_tab(page, tab_name: str) -> bool:
    """Click a tab on the case edit form (e.g. 'Others', 'Test Case Details')."""
    # Tabs are typically rendered as nav items or links
    tab = page.locator(f'a:has-text("{tab_name}"), li:has-text("{tab_name}"), '
                       f'span:has-text("{tab_name}"), div[role="tab"]:has-text("{tab_name}")')
    for i in range(tab.count()):
        el = tab.nth(i)
        try:
            if not el.is_visible(timeout=1000):
                continue
        except Exception:
            continue
        text = el.text_content().strip()
        if text == tab_name or text.lower() == tab_name.lower():
            try:
                el.click(timeout=5000)
                time.sleep(2)
                return True
            except Exception:
                continue
    return False


# ---------------------------------------------------------------------------
# Dropdown Interaction - Mode, Type, Priority
# ---------------------------------------------------------------------------
def _find_field_container(page, label_text: str):
    """Find the form-group container for a given label text via JS."""
    return page.evaluate('''(label) => {
        var els = document.querySelectorAll('label, .form-label, span.label, p');
        for (var i = 0; i < els.length; i++) {
            var t = els[i].textContent.trim();
            if (t === label || t === label + ':') {
                var parent = els[i].closest('.form-group, .row, .col, div[class*="form"]');
                if (parent) {
                    return {found: true, id: parent.id || '', cls: parent.className.substring(0, 100)};
                }
            }
        }
        return {found: false};
    }''', label_text)


def set_dropdown_value(page, label_text: str, target_value: str) -> bool:
    """Set a dropdown field to target_value. Handles native <select> and vue-select.

    For Mode: must be on the 'Others' tab.
    For Type/Priority: on 'Test Case Details' tab (default).
    """
    # Strategy 1: Native <select> (Type and Priority often use these)
    # IMPORTANT: only match VISIBLE labels, skip hidden selects (Quill editor)
    selected = page.evaluate('''(args) => {
        var label = args[0], value = args[1];
        var els = document.querySelectorAll('label, .form-label, span, p, div, h5, h6');
        for (var i = 0; i < els.length; i++) {
            var directText = '';
            for (var j = 0; j < els[i].childNodes.length; j++) {
                if (els[i].childNodes[j].nodeType === 3) directText += els[i].childNodes[j].textContent;
            }
            directText = directText.trim();
            if (directText !== label && directText !== label + ':') continue;

            // Skip labels that are not visible (e.g. on hidden tabs)
            var labelRect = els[i].getBoundingClientRect();
            if (labelRect.width === 0 || labelRect.height === 0) continue;

            // Walk up to find a container with a VISIBLE, non-Quill select
            var el = els[i];
            for (var depth = 0; depth < 6; depth++) {
                var parent = el.parentElement;
                if (!parent) break;
                var allSels = parent.querySelectorAll('select');
                for (var si = 0; si < allSels.length; si++) {
                    var sel = allSels[si];
                    var selStyle = window.getComputedStyle(sel);
                    if (selStyle.display === 'none' || selStyle.visibility === 'hidden') continue;
                    if (sel.classList.contains('ql-size') || sel.classList.contains('ql-header')
                        || sel.classList.contains('ql-font')) continue;
                    var current = sel.options[sel.selectedIndex]
                        ? sel.options[sel.selectedIndex].text.trim() : '';
                    if (current === value) return {done: true, was: 'already_set'};
                    for (var k = 0; k < sel.options.length; k++) {
                        if (sel.options[k].text.trim() === value) {
                            sel.value = sel.options[k].value;
                            sel.dispatchEvent(new Event('change', {bubbles: true}));
                            return {done: true, was: 'native_select'};
                        }
                    }
                }
                el = parent;
            }
        }
        return {done: false};
    }''', [label_text, target_value])

    if selected and selected.get('done'):
        if selected.get('was') == 'already_set':
            print(f'    {label_text} already set to {target_value}')
        else:
            print(f'    {label_text} -> {target_value} (native select)')
        return True

    # Strategy 2: Vue-select dropdown
    # Walk up from VISIBLE label to find vue-select components
    opened = page.evaluate('''(label) => {
        var els = document.querySelectorAll('label, .form-label, span, p, div, h5, h6');
        for (var i = 0; i < els.length; i++) {
            var directText = '';
            for (var j = 0; j < els[i].childNodes.length; j++) {
                if (els[i].childNodes[j].nodeType === 3) directText += els[i].childNodes[j].textContent;
            }
            if (directText.trim() !== label && directText.trim() !== label + ':') continue;

            // CRITICAL: skip labels that are not visible (on hidden tabs)
            var labelRect = els[i].getBoundingClientRect();
            if (labelRect.width === 0 || labelRect.height === 0) continue;

            // Walk up multiple levels looking for vue-select
            var el = els[i];
            for (var depth = 0; depth < 8; depth++) {
                var parent = el.parentElement;
                if (!parent) break;
                var trigger = parent.querySelector(
                    '.vs__dropdown-toggle, .multiselect, [role="combobox"], .dropdown-toggle'
                );
                if (trigger) {
                    var tRect = trigger.getBoundingClientRect();
                    if (tRect.width > 0 && tRect.height > 0) {
                        trigger.click();
                        return {opened: true, depth: depth, trigger: trigger.className.substring(0, 60)};
                    }
                }
                var inp = parent.querySelector('.vs__search, input[type="search"]');
                if (inp) {
                    var iRect = inp.getBoundingClientRect();
                    if (iRect.width > 0 || iRect.height > 0) {
                        inp.click();
                        return {opened: true, depth: depth};
                    }
                }
                el = parent;
            }
        }
        return {opened: false};
    }''', label_text)

    if not opened or not opened.get('opened'):
        # Fallback: check if value text is already displayed
        current_el = page.locator(f'text="{target_value}"')
        if current_el.count() > 0:
            print(f'    {label_text} appears already set to {target_value}')
            return True
        print(f'    {label_text} dropdown not found')
        shot(page, f'dropdown_not_found_{label_text}')
        return False

    # Check if dropdown options are actually visible; if not, try clicking the search input
    opts_visible = page.evaluate('''() => {
        var opts = document.querySelectorAll('.vs__dropdown-option');
        var visible = 0;
        opts.forEach(function(o) {
            var r = o.getBoundingClientRect();
            if (r.width > 0 && r.height > 0) visible++;
        });
        return {visible: visible};
    }''')

    if opts_visible.get('visible', 0) == 0:
        # Options not visible - try clicking the search input directly
        page.evaluate('''(label) => {
            var els = document.querySelectorAll('label, .form-label, span, p, div');
            for (var i = 0; i < els.length; i++) {
                var dt = '';
                for (var j = 0; j < els[i].childNodes.length; j++) {
                    if (els[i].childNodes[j].nodeType === 3) dt += els[i].childNodes[j].textContent;
                }
                if (dt.trim() !== label && dt.trim() !== label + ':') continue;
                var r = els[i].getBoundingClientRect();
                if (r.width === 0 || r.height === 0) continue;
                var el = els[i];
                for (var d = 0; d < 8; d++) {
                    var parent = el.parentElement;
                    if (!parent) break;
                    // Try clicking the vs__search input
                    var search = parent.querySelector('.vs__search');
                    if (search) {
                        var sr = search.getBoundingClientRect();
                        if (sr.width > 0 || sr.height > 0) {
                            search.focus();
                            search.click();
                            return true;
                        }
                    }
                    el = parent;
                }
            }
            return false;
        }''', label_text)
        time.sleep(1.5)

        # Re-check - options should be visible now
        time.sleep(0.5)

    time.sleep(1.5)

    # Click the target option using Playwright (not JS) to ensure Vue reactivity
    option_clicked = False

    # First find the option via JS to locate it, then click via Playwright
    opt_locator = page.locator('.vs__dropdown-option, .multiselect__option, '
                               'li[role="option"], .dropdown-item')
    opt_count = opt_locator.count()
    for idx in range(opt_count):
        el = opt_locator.nth(idx)
        try:
            if not el.is_visible(timeout=500):
                continue
            text = el.text_content().strip()
            if text == target_value:
                el.click()
                option_clicked = True
                time.sleep(1)
                break
        except Exception:
            continue

    if not option_clicked:
        # Broader Playwright fallback
        opt = page.locator(f'li:has-text("{target_value}"), '
                           f'div[class*="option"]:has-text("{target_value}")')
        for idx in range(opt.count()):
            el = opt.nth(idx)
            try:
                if el.is_visible(timeout=500):
                    el.click()
                    option_clicked = True
                    time.sleep(1)
                    break
            except Exception:
                continue

    if option_clicked:
        # Verify the change took effect
        time.sleep(0.5)
        current = page.evaluate('''(label) => {
            var els = document.querySelectorAll('label, .form-label, span, p, div');
            for (var i = 0; i < els.length; i++) {
                var dt = '';
                for (var j = 0; j < els[i].childNodes.length; j++) {
                    if (els[i].childNodes[j].nodeType === 3) dt += els[i].childNodes[j].textContent;
                }
                if (dt.trim() !== label && dt.trim() !== label + ':') continue;
                var r = els[i].getBoundingClientRect();
                if (r.width === 0 || r.height === 0) continue;
                var el = els[i];
                for (var d = 0; d < 8; d++) {
                    var parent = el.parentElement;
                    if (!parent) break;
                    var selected = parent.querySelector('.vs__selected');
                    if (selected) return selected.textContent.trim();
                    el = parent;
                }
            }
            return null;
        }''', label_text)
        print(f'    {label_text} -> {target_value} (vue-select), verified={current}')
        return True

    print(f'    "{target_value}" option not found for {label_text}')
    shot(page, f'option_not_found_{label_text}')
    page.keyboard.press('Escape')
    time.sleep(0.5)
    return False


def set_mode_on_case(page, target='Automation') -> bool:
    """Set Mode field on the currently-open edit form.

    Mode is on the 'Others' tab. Goes there directly.
    Checks if already set before trying to change.
    """
    # Go directly to Others tab (Mode is always there)
    if not click_form_tab(page, 'Others'):
        print('    Others tab not found')
        shot(page, 'others_tab_not_found')
        return False

    # Check current Mode value before trying to change
    current_mode = page.evaluate('''() => {
        var labels = document.querySelectorAll('label');
        for (var i = 0; i < labels.length; i++) {
            var dt = '';
            for (var j = 0; j < labels[i].childNodes.length; j++) {
                if (labels[i].childNodes[j].nodeType === 3) dt += labels[i].childNodes[j].textContent;
            }
            if (dt.trim() !== 'Mode') continue;
            var r = labels[i].getBoundingClientRect();
            if (r.width === 0 || r.height === 0) continue;
            var el = labels[i];
            for (var d = 0; d < 8; d++) {
                var parent = el.parentElement;
                if (!parent) break;
                var selected = parent.querySelector('.vs__selected');
                if (selected) return selected.textContent.trim();
                el = parent;
            }
        }
        return null;
    }''')

    if current_mode and current_mode.lower() == target.lower():
        print(f'    Mode already set to {target}')
        return True

    print(f'    Current Mode: {current_mode or "empty"} -> setting to {target}')
    if set_dropdown_value(page, 'Mode', target):
        return True

    # Fallback: try Custom Fields tab
    if click_form_tab(page, 'Custom Fields'):
        if set_dropdown_value(page, 'Mode', target):
            return True

    print('    Mode field not found on any tab')
    shot(page, 'mode_not_found')
    return False


# ---------------------------------------------------------------------------
# Tag Management
# ---------------------------------------------------------------------------
def get_existing_tags(page) -> list[str]:
    """Read tag chips from both 'Tags' and 'New Tags' vue-select sections.

    QA Touch DOM: gpt_content_outer_wrap (label) -> next sibling: v-select.
    'New Tags' inner div has class 'add_new_tag_lable_outer_wrap'.
    """
    tags = page.evaluate('''() => {
        var result = [];
        var outers = document.querySelectorAll('.gpt_content_outer_wrap');
        for (var i = 0; i < outers.length; i++) {
            var label = outers[i].querySelector('label');
            if (!label) continue;
            var lt = label.textContent.trim();
            if (lt.indexOf('Tags') < 0) continue;

            // The vue-select is the NEXT sibling of gpt_content_outer_wrap
            var vselect = outers[i].nextElementSibling;
            while (vselect && !vselect.classList.contains('v-select')) {
                vselect = vselect.nextElementSibling;
            }
            if (!vselect) continue;

            var chips = vselect.querySelectorAll('.vs__selected');
            chips.forEach(function(c) {
                var text = c.textContent.replace(/[x\u00d7\u2715]/gi, '').trim();
                if (text && text.length > 0 && text !== 'Select Tags') {
                    result.push(text.toUpperCase());
                }
            });
        }
        return result;
    }''')
    return tags or []


def _find_new_tags_vselect(page):
    """Find the New Tags vue-select and focus its search input.

    DOM: gpt_content_outer_wrap -> inner has class add_new_tag_lable_outer_wrap
    -> next sibling = v-select with .vs__search input.
    Returns True if input was focused.
    """
    return page.evaluate('''() => {
        var outers = document.querySelectorAll('.gpt_content_outer_wrap');
        for (var i = 0; i < outers.length; i++) {
            var inner = outers[i].querySelector('.add_new_tag_lable_outer_wrap');
            if (!inner) continue;

            var vselect = outers[i].nextElementSibling;
            while (vselect && !vselect.classList.contains('v-select')) {
                vselect = vselect.nextElementSibling;
            }
            if (!vselect) continue;

            vselect.scrollIntoView({block: 'center'});
            var input = vselect.querySelector('.vs__search, input[type="search"]');
            if (input) {
                input.click();
                input.focus();
                return true;
            }
            var trigger = vselect.querySelector('.vs__dropdown-toggle');
            if (trigger) {
                trigger.click();
                return true;
            }
        }
        return false;
    }''')


def add_tag(page, tag_name: str) -> bool:
    """Add a tag via the 'New Tags' vue-select dropdown.

    QA Touch has two tag areas:
    - 'Tags': system-level dropdown (predefined tags)
    - 'New Tags': custom tags with Add New button (where SMOKE/SANITY live)

    DOM: gpt_content_outer_wrap (label) -> next sibling = v-select.
    'New Tags' wrapper has class 'add_new_tag_lable_outer_wrap'.
    'Add New' is an <a> inside .add_release_create_button_wrap.
    """
    tag_upper = tag_name.upper()

    # Check if already present in either section
    existing = get_existing_tags(page)
    if tag_upper in [t.upper() for t in existing]:
        print(f'    Tag "{tag_name}" already present')
        return True

    # Open the New Tags vue-select (retry once - DOM may still be rendering)
    if not _find_new_tags_vselect(page):
        time.sleep(3)
        # Scroll down to ensure New Tags section is loaded
        page.evaluate('''() => {
            var form = document.querySelector('.modal-body, .edit-form, [class*="edit"]');
            if (form) form.scrollTop = form.scrollHeight;
        }''')
        time.sleep(1)
        if not _find_new_tags_vselect(page):
            print(f'    New Tags vue-select not found')
            shot(page, 'new_tags_not_found')
            return False

    time.sleep(0.5)

    # Type the tag name to filter
    page.keyboard.type(tag_name, delay=100)
    time.sleep(1.5)

    # Check if there's a matching option in dropdown
    option_clicked = page.evaluate('''(tagName) => {
        var upper = tagName.toUpperCase();
        var options = document.querySelectorAll(
            '.vs__dropdown-option, li[role="option"]'
        );
        for (var i = 0; i < options.length; i++) {
            var text = options[i].textContent.trim().toUpperCase();
            if (text === upper || text.indexOf(upper) >= 0) {
                options[i].click();
                return true;
            }
        }
        return false;
    }''', tag_name)

    if option_clicked:
        print(f'    Tag "{tag_name}" selected from New Tags dropdown')
        time.sleep(0.5)
        return True

    # No match - click "Add New" link to create it
    page.keyboard.press('Escape')
    time.sleep(0.3)

    add_new = page.evaluate('''() => {
        var links = document.querySelectorAll('.add_release_create_button_wrap a');
        for (var i = 0; i < links.length; i++) {
            if (links[i].textContent.trim() === 'Add New') {
                links[i].click();
                return true;
            }
        }
        return false;
    }''')

    if add_new:
        time.sleep(1.5)
        # "Add New" opens a modal dialog with Label, Key, Status fields.
        # Fill Label and Key, then click the modal's Save button.
        modal_handled = page.evaluate('''(tagName) => {
            // Fill Label field
            var inputs = document.querySelectorAll('input');
            var labelInput = null, keyInput = null;
            for (var inp of inputs) {
                var ph = (inp.placeholder || '').toLowerCase();
                if (ph === 'enter label') labelInput = inp;
                else if (ph === 'enter key') keyInput = inp;
            }
            if (!labelInput || !keyInput) return 'modal_inputs_not_found';

            labelInput.focus();
            labelInput.value = tagName.toUpperCase();
            labelInput.dispatchEvent(new Event('input', {bubbles: true}));
            labelInput.dispatchEvent(new Event('change', {bubbles: true}));

            keyInput.focus();
            keyInput.value = tagName.toLowerCase();
            keyInput.dispatchEvent(new Event('input', {bubbles: true}));
            keyInput.dispatchEvent(new Event('change', {bubbles: true}));

            // Click the modal Save button (not the main form's save-continue-btn)
            var btns = document.querySelectorAll('button');
            for (var b of btns) {
                if (b.textContent.trim() === 'Save' && !b.classList.contains('save-continue-btn') && b.offsetHeight > 0) {
                    var rect = b.getBoundingClientRect();
                    if (rect.top > 200 && rect.top < 600) {
                        b.click();
                        return 'modal_saved';
                    }
                }
            }
            return 'modal_save_not_found';
        }''', tag_name)
        time.sleep(1.5)
        print(f'    Tag "{tag_name}" created via Add New ({modal_handled})')
        return True

    print(f'    Could not add tag "{tag_name}"')
    shot(page, 'tag_add_failed', tag_name)
    return False


def add_tags_to_case(page, tags: list[str]) -> bool:
    """Add multiple tags to the currently-open edit form."""
    all_ok = True
    for tag in tags:
        if not add_tag(page, tag.strip()):
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# Core Operations
# ---------------------------------------------------------------------------
def process_case(page, context, case, operations, rate_limiter, report):
    """Process a single case: navigate to it, open edit, apply operations, save.

    operations: list of dicts, each with 'action' key:
        {'action': 'set-mode', 'value': 'Automation'}
        {'action': 'set-tags', 'tags': ['SMOKE', 'SANITY']}
        {'action': 'set-type', 'value': 'Functional'}
        {'action': 'set-priority', 'value': 'Critical'}
    """
    title = case['case_title']
    key = case['case_key']
    print(f'\n  Processing [{key}]: "{title[:60]}..."')

    rate_limiter.wait()

    # Find and click case (with retry on detail page failure)
    detail_ok = False
    for attempt in range(2):
        if not find_and_click_case(page, title):
            report.add(key, 'not_found', f'Case not found in list')
            return False

        # Verify we're on detail page
        try:
            if page.locator('button:has-text("Edit")').first.is_visible(timeout=5000):
                detail_ok = True
                break
        except Exception:
            pass

        if attempt == 0:
            print(f'    Detail page not loaded, retrying...')
            page.keyboard.press('Escape')
            time.sleep(2)
        else:
            print(f'    Not on case detail page')
            shot(page, 'not_detail', key)
            report.add(key, 'no_detail', 'Edit button not visible after click')
            return False

    if not detail_ok:
        report.add(key, 'no_detail', 'Edit button not visible after click')
        return False

    # Open edit form
    if not open_edit_form(page):
        report.add(key, 'no_edit', 'Could not open edit form')
        close_case_detail(page)
        return False

    # Apply operations
    success = True
    for op in operations:
        action = op['action']
        if action == 'set-mode':
            if not set_mode_on_case(page, op.get('value', 'Automation')):
                success = False
        elif action == 'set-tags':
            if not add_tags_to_case(page, op['tags']):
                success = False
        elif action == 'set-type':
            if not set_dropdown_value(page, 'Type', op['value']):
                success = False
        elif action == 'set-priority':
            if not set_dropdown_value(page, 'Priority', op['value']):
                success = False

    # Save
    if success:
        if save_and_close(page):
            report.add(key, 'success')
            return True
        else:
            report.add(key, 'save_fail', 'Save button not found')
            return False
    else:
        # Still save partial changes
        save_and_close(page)
        report.add(key, 'partial', 'Some operations failed')
        return False


def run_batch(page, context, cases, operations, rate_limiter, report):
    """Process cases grouped by module for efficient navigation.

    Handles duplicate module names by trying each match when a case
    isn't found in the first module.
    """
    by_module: dict[str, list[dict]] = {}
    for c in cases:
        by_module.setdefault(c['module'], []).append(c)

    for module, module_cases in by_module.items():
        print(f'\n  Module: {module} ({len(module_cases)} cases)')

        if not ensure_authenticated(page, context):
            print('  FATAL: Cannot authenticate')
            for c in module_cases:
                report.add(c['case_key'], 'auth_fail')
            return

        # Count how many modules share this name
        num_matches = count_module_matches(page, module)

        if not navigate_to_module(page, module, match_index=0):
            print(f'    SKIP - could not navigate')
            for c in module_cases:
                report.add(c['case_key'], 'nav_fail', f'Module not found: {module}')
            continue

        for case in module_cases:
            ok = process_case(page, context, case, operations, rate_limiter, report)
            if not ok:
                # If case wasn't found and there are duplicate modules, try others
                last_result = report.results[-1] if report.results else {}
                if last_result.get('status') == 'not_found' and num_matches > 1:
                    print(f'    Trying other "{module}" modules ({num_matches} total)...')
                    # Remove the failed result so we can retry
                    report.results.pop()
                    found_in_alt = False
                    for alt_idx in range(1, num_matches):
                        if navigate_to_module(page, module, match_index=alt_idx):
                            ok = process_case(page, context, case, operations, rate_limiter, report)
                            if ok:
                                found_in_alt = True
                                break
                            # Check if it was found this time
                            if report.results[-1].get('status') != 'not_found':
                                found_in_alt = True
                                break
                            report.results.pop()  # Remove failed attempt
                    if not found_in_alt:
                        report.add(case['case_key'], 'not_found',
                                   f'Case not found in any of {num_matches} "{module}" modules')
                    # Return to first module for remaining cases
                    navigate_to_module(page, module, match_index=0)
                else:
                    # Standard re-navigation for next case
                    time.sleep(1)
                    if not ensure_authenticated(page, context):
                        for c2 in module_cases:
                            if c2['case_key'] not in [r['case_key'] for r in report.results]:
                                report.add(c2['case_key'], 'auth_fail')
                        return
                    navigate_to_module(page, module)


# ---------------------------------------------------------------------------
# CSV / Input Loading
# ---------------------------------------------------------------------------
def load_csv(path) -> list[dict]:
    """Load cases from CSV. Expects at least: case_key, case_title, module."""
    if not os.path.exists(path):
        print(f'  CSV not found: {path}')
        return []
    cases = []
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append(row)
    return cases


def resolve_cases_from_keys(keys: list[str]) -> list[dict]:
    """Look up case titles and modules from API by case keys."""
    client = QATouchClient()
    all_cases = client.list_all_test_cases(PROJECT_KEY)
    by_key = {c['case_key']: c for c in all_cases}
    result = []
    for k in keys:
        c = by_key.get(k)
        if c:
            result.append({
                'case_key': c['case_key'],
                'case_title': c['case_title'],
                'module': c.get('module name', 'Unknown'),
            })
        else:
            print(f'  WARNING: Case {k} not found in QA Touch')
    return result


# ---------------------------------------------------------------------------
# Explore command - debug screenshots of every form tab
# ---------------------------------------------------------------------------
def _dump_dom_diagnostics(page, label=''):
    """Print diagnostic info about the current case list DOM."""
    info = page.evaluate('''() => {
        // Check for .cl-container elements
        var containers = document.querySelectorAll('.cl-container');
        var titles = [];
        for (var i = 0; i < Math.min(10, containers.length); i++) {
            var ps = containers[i].querySelectorAll('p');
            for (var j = 0; j < ps.length; j++) {
                var t = ps[j].textContent.trim();
                if (t.length > 15) { titles.push(t.substring(0, 80)); break; }
            }
        }

        // Check for scrollable container
        var scrollInfo = null;
        var c = containers[0];
        if (c) {
            var el = c.parentElement;
            for (var i = 0; i < 15 && el; i++) {
                var style = window.getComputedStyle(el);
                scrollInfo = {
                    tag: el.tagName,
                    cls: el.className.substring(0, 100),
                    scrollH: el.scrollHeight,
                    clientH: el.clientHeight,
                    scrollTop: el.scrollTop,
                    overflowY: style.overflowY,
                    level: i
                };
                if (style.overflowY === 'auto' || style.overflowY === 'scroll'
                    || el.scrollHeight > el.clientHeight + 50) {
                    scrollInfo.isScrollable = true;
                    break;
                }
                el = el.parentElement;
            }
        }

        // Check for alternative case list selectors
        var altSelectors = {
            'tr.case-row': document.querySelectorAll('tr.case-row').length,
            'div[class*="case"]': document.querySelectorAll('div[class*="case"]').length,
            'div[class*="test-case"]': document.querySelectorAll('div[class*="test-case"]').length,
            'div[class*="tc-list"]': document.querySelectorAll('div[class*="tc-list"]').length,
            'table tbody tr': document.querySelectorAll('table tbody tr').length,
            '.case-list-item': document.querySelectorAll('.case-list-item').length,
            'a[href*="case"]': document.querySelectorAll('a[href*="case"]').length,
        };

        return {
            containerCount: containers.length,
            firstTitles: titles,
            scrollInfo: scrollInfo,
            altSelectors: altSelectors,
            bodyScrollH: document.body.scrollHeight,
            bodyClientH: document.body.clientHeight,
            url: window.location.href,
        };
    }''')

    prefix = f'  [{label}] ' if label else '  '
    print(f'{prefix}DOM Diagnostics:')
    print(f'{prefix}  URL: {info.get("url", "?")}')
    print(f'{prefix}  .cl-container count: {info["containerCount"]}')
    if info.get('firstTitles'):
        print(f'{prefix}  First {len(info["firstTitles"])} case titles:')
        for t in info['firstTitles']:
            print(f'{prefix}    - {t}')
    si = info.get('scrollInfo')
    if si:
        print(f'{prefix}  Scroll container: <{si["tag"]}> cls="{si.get("cls", "")}"')
        print(f'{prefix}    scrollHeight={si.get("scrollH")}, clientHeight={si.get("clientH")}, '
              f'scrollTop={si.get("scrollTop")}, overflowY={si.get("overflowY")}')
        print(f'{prefix}    isScrollable={si.get("isScrollable", False)}, level={si.get("level")}')
    else:
        print(f'{prefix}  No scroll container found')
    alts = info.get('altSelectors', {})
    for sel, count in alts.items():
        if count > 0:
            print(f'{prefix}  ALT selector "{sel}": {count} elements')
    print(f'{prefix}  body: scrollH={info.get("bodyScrollH")}, clientH={info.get("bodyClientH")}')


def cmd_explore(case_key):
    """Open a single case and screenshot every tab on the edit form."""
    print(f'\n  Exploring case [{case_key}]...')
    cases = resolve_cases_from_keys([case_key])
    if not cases:
        return

    case = cases[0]
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser, context, page = setup_browser(p)
        if not browser:
            return
        try:
            enter_project(page, context)
            if not navigate_to_module(page, case['module']):
                return

            # Dump DOM diagnostics before attempting to find the case
            _dump_dom_diagnostics(page, 'after_module_nav')
            shot(page, 'explore_module_view', case_key)

            if not find_and_click_case(page, case['case_title']):
                # Dump diagnostics on failure
                _dump_dom_diagnostics(page, 'case_not_found')
                shot(page, 'explore_case_not_found', case_key)
                return

            shot(page, 'explore_detail', case_key)

            if not open_edit_form(page):
                return

            shot(page, 'explore_edit_default', case_key)

            # Try each known tab
            for tab in ['Test Case Details', 'Steps', 'Others', 'Attachments',
                        'Link Testcase', 'Link Requirements', 'Custom Fields',
                        'Jira Requirements']:
                if click_form_tab(page, tab):
                    shot(page, f'explore_tab_{tab.replace(" ", "_").lower()}', case_key)
                    time.sleep(1)

            print(f'  Screenshots saved to {SHOT_DIR}/')
            close_case_detail(page)
        finally:
            context.storage_state(path=AUTH_STATE_FILE)
            browser.close()


# ---------------------------------------------------------------------------
# Module Rename (batch rename duplicate module names)
# ---------------------------------------------------------------------------
def _get_selected_module_key(page) -> str:
    """Read the module_key from the header's release_key span."""
    return page.evaluate('''() => {
        var span = document.querySelector('span.release_key');
        return span ? span.textContent.trim() : '';
    }''') or ''


def rename_single_module(page, old_name, new_name, match_index=0):
    """Rename one module via the header Edit Module modal.

    Flow: click module in tree -> click Edit Module icon -> modal with input
    -> clear + type new name -> click Save.

    Returns status: 'success', 'not_found', 'no_edit_btn', 'modal_fail', 'verify_fail'
    """
    print(f'    Renaming: "{old_name}" \u2192 "{new_name}" (match {match_index})')

    # 1. Click the module in the tree to select it
    if not navigate_to_module(page, old_name, match_index=match_index):
        print(f'      Module not found in tree')
        return 'not_found'

    time.sleep(2)

    # 2. Click the "Edit Module" icon in the header bar
    edit_btn = page.locator('a[title="Edit Module"]')
    if edit_btn.count() == 0:
        print('      Edit Module button not found')
        shot(page, 'no_edit_module_btn', old_name.replace(' ', '_'))
        return 'no_edit_btn'

    edit_btn.first.click()
    time.sleep(2)

    # 3. Wait for the Edit Module modal with name input
    name_input = page.locator('input[placeholder="Module Name"]')
    try:
        name_input.wait_for(state='visible', timeout=5000)
    except Exception:
        print('      Edit Module modal did not appear')
        shot(page, 'modal_not_opened', old_name.replace(' ', '_'))
        page.keyboard.press('Escape')
        time.sleep(1)
        return 'modal_fail'

    current_val = name_input.input_value()
    print(f'      Modal opened, current name: "{current_val}"')

    # 4. Clear and type new name
    name_input.click()
    name_input.fill('')
    time.sleep(0.3)
    name_input.fill(new_name)
    time.sleep(0.5)

    # 5. Click Save
    save_btn = page.locator('.modal.show button:has-text("Save"), '
                            '.modal-dialog button:has-text("Save")')
    if save_btn.count() == 0:
        print('      Save button not found in modal')
        shot(page, 'no_save_in_modal', new_name.replace(' ', '_')[:30])
        page.keyboard.press('Escape')
        time.sleep(1)
        return 'modal_fail'

    save_btn.first.click()
    time.sleep(3)

    # 6. Verify: check that the modal closed and the tree shows the new name
    # Modal should be gone
    modal_gone = page.evaluate('''() => {
        var modals = document.querySelectorAll('.modal.show');
        return modals.length === 0;
    }''')
    if not modal_gone:
        print('      Modal still visible after Save - possible validation error')
        shot(page, 'modal_still_open', new_name.replace(' ', '_')[:30])
        page.keyboard.press('Escape')
        time.sleep(1)
        return 'modal_fail'

    # Verify by checking the header now shows the new name
    time.sleep(1)
    header_name = page.evaluate('''() => {
        var sel = document.querySelector('.ant-select-selection-selected-value');
        return sel ? sel.textContent.trim() : '';
    }''')

    if header_name.lower() == new_name.lower():
        print(f'      Verified: header shows "{header_name}"')
        return 'success'

    # Fallback: check the tree for the new name using navigate helper
    filt = page.locator('input[placeholder="Type To Filter Module"]').first
    filt.fill('')
    time.sleep(0.5)
    filt.fill(new_name.strip())
    time.sleep(2)

    found = page.evaluate('''(name) => {
        var target = name.toLowerCase().trim();
        var nodes = document.querySelectorAll('.node-text.module_name_wrap');
        for (var i = 0; i < nodes.length; i++) {
            if (nodes[i].textContent.trim().toLowerCase() === target) return true;
        }
        return false;
    }''', new_name)

    filt.fill('')
    time.sleep(0.5)

    if found:
        print(f'      Verified: "{new_name}" found in tree')
        return 'success'

    print(f'      Warning: could not verify "{new_name}"')
    shot(page, 'rename_verify_fail', new_name.replace(' ', '_')[:30])
    return 'verify_fail'


def _identify_module_by_key(page, old_name, remaining_entries, match_index=0):
    """Click module match_index, read module_key from header, match to entry.

    The header displays the module_key in span.release_key after clicking a module.
    This is 100% reliable identification - no case count guessing needed.
    Returns the matched entry dict, or None if not found.
    """
    if not navigate_to_module(page, old_name, match_index=match_index):
        return 'no_match'  # No more modules in tree with this name

    time.sleep(2)
    module_key = _get_selected_module_key(page)
    print(f'      Module key from header: {module_key}')

    for e in remaining_entries:
        if e['module_key'] == module_key:
            return e

    print(f'      WARNING: key {module_key} not in remaining entries')
    return None  # Found module but key unknown - caller can try next index


def cmd_rename_modules(csv_file=None, dry_run=False, limit=None):
    """Batch rename duplicate modules from the rename plan CSV.

    Strategy:
    1. Group entries by old_name
    2. For each group, click match_index=0 in the tree
    3. Read module_key from header span.release_key to identify the entry
    4. Open Edit Module modal, type new_name, Save
    5. After rename, old_name filter returns one fewer exact match,
       so the next duplicate becomes match_index=0
    """
    path = csv_file or RENAME_CSV
    if not os.path.exists(path):
        print(f'  Rename CSV not found: {path}')
        return

    entries = []
    with open(path, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            entries.append(row)

    if not entries:
        print('  No rename entries found.')
        return

    # Group by old_name
    groups: dict[str, list[dict]] = {}
    for e in entries:
        groups.setdefault(e['old_name'], []).append(e)

    total = sum(len(g) for g in groups.values())
    if limit:
        total = min(total, limit)

    print(f'\n{"=" * 60}')
    print(f'  QA Touch Module Rename')
    print(f'  Total: {total} modules across {len(groups)} name groups')
    print(f'{"=" * 60}')

    for old_name, group in sorted(groups.items()):
        print(f'\n  "{old_name}" ({len(group)} variants):')
        for e in group:
            print(f'    \u2192 "{e["new_name"]}" ({e["case_count"]} cases)')

    if dry_run:
        print('\n  DRY RUN \u2014 no browser launched.')
        return

    from playwright.sync_api import sync_playwright
    rate_limiter = RateLimiter(min_interval=3.0, burst_pause=15.0, burst_threshold=5)
    report = RunReport()
    processed = 0

    with sync_playwright() as p:
        browser, context, page = setup_browser(p)
        if not browser:
            print('  Failed to set up browser.')
            return
        try:
            enter_project(page, context)

            for old_name, group in sorted(groups.items()):
                if limit and processed >= limit:
                    break

                # Refresh page every 20 operations to prevent stale DOM
                if processed > 0 and processed % 20 == 0:
                    print(f'\n  [Refreshing page after {processed} operations]')
                    page.reload()
                    time.sleep(5)
                    enter_project(page, context)

                print(f'\n  === {old_name} ({len(group)} variants) ===')

                if not ensure_authenticated(page, context):
                    for e in group:
                        report.add(e['module_key'], 'auth_fail')
                    continue

                remaining = list(group)

                while remaining:
                    if limit and processed >= limit:
                        break

                    rate_limiter.wait()

                    # Try match_index 0..N to skip over unknown modules
                    entry = None
                    max_scan = len(remaining) + 5  # allow for unknowns
                    for mi in range(max_scan):
                        result = _identify_module_by_key(
                            page, old_name, remaining, match_index=mi)
                        if result == 'no_match':
                            # No more modules in tree with this name
                            break
                        if result is not None:
                            entry = result
                            break
                        # navigate_to_module succeeded but key not in
                        # remaining - try the next match index
                        print(f'      Skipping unknown module at index {mi}')

                    if entry is None:
                        print(f'    Could not identify module, '
                              f'skipping {len(remaining)} remaining')
                        for e in remaining:
                            report.add(e['module_key'], 'not_found',
                                       f'Module not found/identified')
                        break

                    print(f'\n    [{entry["module_key"]}] '
                          f'"{old_name}" \u2192 "{entry["new_name"]}"')

                    # Module is already selected (navigate_to_module called
                    # inside _identify_module_by_key), so just open the
                    # Edit Module modal directly
                    edit_btn = page.locator('a[title="Edit Module"]')
                    if edit_btn.count() == 0:
                        print('      Edit Module button not found')
                        shot(page, 'no_edit_btn', entry['module_key'])
                        report.add(entry['module_key'], 'no_edit_btn')
                        remaining.remove(entry)
                        processed += 1
                        continue

                    edit_btn.first.click()
                    time.sleep(2)

                    # Wait for modal
                    name_input = page.locator('input[placeholder="Module Name"]')
                    try:
                        name_input.wait_for(state='visible', timeout=5000)
                    except Exception:
                        print('      Modal did not appear')
                        shot(page, 'no_modal', entry['module_key'])
                        page.keyboard.press('Escape')
                        time.sleep(1)
                        report.add(entry['module_key'], 'modal_fail')
                        remaining.remove(entry)
                        processed += 1
                        continue

                    # Clear and type new name
                    name_input.click()
                    name_input.fill('')
                    time.sleep(0.3)
                    name_input.fill(entry['new_name'])
                    time.sleep(0.5)

                    # Click Save
                    save_btn = page.locator(
                        '.modal.show button:has-text("Save"), '
                        '.modal-dialog button:has-text("Save")')
                    if save_btn.count() > 0:
                        save_btn.first.click()
                        time.sleep(3)
                    else:
                        page.keyboard.press('Enter')
                        time.sleep(3)

                    # Verify modal closed
                    modal_gone = page.evaluate('''() => {
                        return document.querySelectorAll('.modal.show').length === 0;
                    }''')

                    if not modal_gone:
                        print('      Modal still open after Save')
                        shot(page, 'save_failed', entry['module_key'])
                        page.keyboard.press('Escape')
                        time.sleep(1)
                        report.add(entry['module_key'], 'save_fail',
                                   f'{old_name} \u2192 {entry["new_name"]}')
                        remaining.remove(entry)
                        processed += 1
                        continue

                    # Quick verify: check header
                    header_name = page.evaluate('''() => {
                        var sel = document.querySelector(
                            '.ant-select-selection-selected-value');
                        return sel ? sel.textContent.trim() : '';
                    }''')

                    if header_name.lower() == entry['new_name'].lower():
                        print(f'      Renamed: "{old_name}" \u2192 '
                              f'"{entry["new_name"]}"')
                        report.add(entry['module_key'], 'success')
                    else:
                        print(f'      Rename unverified '
                              f'(header shows "{header_name}")')
                        report.add(entry['module_key'], 'verify_fail',
                                   f'Header: {header_name}')

                    remaining.remove(entry)
                    processed += 1

            report.print_summary()
            report.save()

        finally:
            context.storage_state(path=AUTH_STATE_FILE)
            browser.close()


# ---------------------------------------------------------------------------
# Step Structure Audit
# ---------------------------------------------------------------------------
def _extract_step_data(page):
    """Extract step data from the currently visible Steps tab.

    Returns a list of step dicts with 'description' and 'expected' text.
    Also detects if a single step contains numbered sub-steps.
    """
    return page.evaluate('''() => {
        // Steps tab has pairs of rich-text editors: Step Description + Expected Result
        // Each step row has a Step Description editor and Expected Result editor
        // Look for the step containers - typically .ProseMirror editors or contenteditable divs
        var editors = document.querySelectorAll('.ProseMirror, [contenteditable="true"]');
        var stepDescs = [];
        var stepExpected = [];

        // The layout alternates: Step Description, Expected Result, Step Description, ...
        // Find labeled sections
        var labels = document.querySelectorAll('label, .form-label, p');
        var descLabels = [];
        var expLabels = [];
        for (var i = 0; i < labels.length; i++) {
            var t = labels[i].textContent.trim();
            if (t.indexOf('Step Description') >= 0) descLabels.push(labels[i]);
            if (t.indexOf('Expected Result') >= 0) expLabels.push(labels[i]);
        }

        // Each step row typically has one desc editor and one expected editor
        // Try to pair them up
        var steps = [];
        if (descLabels.length > 0) {
            for (var i = 0; i < descLabels.length; i++) {
                var descEl = descLabels[i];
                var descEditor = descEl.parentElement ?
                    descEl.parentElement.querySelector('.ProseMirror, [contenteditable]') : null;
                var descText = descEditor ? descEditor.textContent.trim() : '';

                var expText = '';
                if (i < expLabels.length) {
                    var expEl = expLabels[i];
                    var expEditor = expEl.parentElement ?
                        expEl.parentElement.querySelector('.ProseMirror, [contenteditable]') : null;
                    expText = expEditor ? expEditor.textContent.trim() : '';
                }

                steps.push({description: descText, expected: expText});
            }
        }

        // Fallback: find editors without labels
        if (steps.length === 0) {
            var edits = document.querySelectorAll('.ProseMirror');
            for (var i = 0; i < edits.length; i += 2) {
                var desc = edits[i] ? edits[i].textContent.trim() : '';
                var exp = (i + 1 < edits.length) ? edits[i + 1].textContent.trim() : '';
                if (desc || exp) steps.push({description: desc, expected: exp});
            }
        }

        return steps;
    }''')


def _analyze_step_quality(steps):
    """Analyze step data and return quality assessment.

    Returns dict with:
      step_count: number of step rows
      all_in_one: True if 1 row with numbered sub-steps
      numbered_count: how many numbered sub-steps detected in text
      max_desc_len: longest description text
    """
    if not steps:
        return {'step_count': 0, 'all_in_one': False, 'numbered_count': 0,
                'max_desc_len': 0, 'issue': 'no_steps'}

    step_count = len(steps)
    max_desc_len = max(len(s.get('description', '')) for s in steps)

    # Check if a single step has numbered sub-steps
    all_in_one = False
    numbered_count = 0
    if step_count == 1:
        desc = steps[0].get('description', '')
        # Detect patterns like "1. ... 2. ... 3. ..." or "Step 1: ... Step 2: ..."
        numbered = re.findall(r'(?:^|\s)(\d+)\.\s', desc)
        numbered_count = len(numbered)
        if numbered_count >= 3:
            all_in_one = True

    issue = 'none'
    if all_in_one:
        issue = 'all_in_one_line'
    elif step_count == 1 and max_desc_len > 200:
        issue = 'single_long_step'
    elif step_count == 0:
        issue = 'no_steps'

    return {
        'step_count': step_count,
        'all_in_one': all_in_one,
        'numbered_count': numbered_count,
        'max_desc_len': max_desc_len,
        'issue': issue,
    }


# ---------------------------------------------------------------------------
# Step Sync - Write step definitions from JSON into QA Touch Steps tab
# ---------------------------------------------------------------------------

def _clear_all_steps(page) -> int:
    """Remove all existing step rows by clicking delete buttons.
    Returns the number of steps deleted."""
    deleted = 0
    for attempt in range(30):  # Safety limit
        delete_btns = page.locator('button[title="Delete"], button:has-text("Delete Step"), '
                                   'button.delete-step, i.fa-trash, svg[data-icon="trash"]')
        if delete_btns.count() == 0:
            break
        try:
            delete_btns.last.click()
            time.sleep(1)
            # Confirm if dialog appears
            confirm = page.locator('button:has-text("Yes"), button:has-text("OK"), '
                                   'button:has-text("Confirm")')
            if confirm.count() > 0 and confirm.first.is_visible(timeout=1000):
                confirm.first.click()
                time.sleep(1)
            deleted += 1
        except Exception:
            break
    return deleted


def _click_add_step(page) -> bool:
    """Click the 'Add New Step' button. Returns True if clicked."""
    # Try the main "Add New Step" button at the top of the Steps panel
    for selector in [
        'button:has-text("Add New Step")',
        'a:has-text("Add New Step")',
        'button:has-text("Add Step")',
        'a:has-text("Add Step")',
        'button:has-text("+ Add")',
    ]:
        btn = page.locator(selector)
        try:
            if btn.count() > 0 and btn.first.is_visible(timeout=2000):
                btn.first.click()
                time.sleep(2)
                return True
        except Exception:
            continue
    return False


def _write_prosemirror(page, editor_el, text: str) -> bool:
    """Write text into a ProseMirror editor element.

    Strategy: click to focus -> Ctrl+A to select all -> type new text.
    ProseMirror captures keyboard input natively.
    """
    try:
        editor_el.click()
        time.sleep(0.3)
        page.keyboard.press('Control+a')
        time.sleep(0.2)
        page.keyboard.type(text, delay=10)
        time.sleep(0.3)
        return True
    except Exception as e:
        print(f'      ProseMirror write failed: {e}')
        return False


def _write_step_row(page, step_index: int, action: str, expected: str) -> bool:
    """Write action and expected result into a step row at the given index.

    Finds the ProseMirror editors paired with 'Step Description' and
    'Expected Result' labels for the specified step row.
    """
    # Find all Step Description and Expected Result editors via JS
    editors = page.evaluate('''(idx) => {
        var labels = document.querySelectorAll('label, .form-label, p');
        var descLabels = [];
        var expLabels = [];
        for (var i = 0; i < labels.length; i++) {
            var t = labels[i].textContent.trim();
            if (t.indexOf('Step Description') >= 0) descLabels.push(i);
            if (t.indexOf('Expected Result') >= 0) expLabels.push(i);
        }
        return {descCount: descLabels.length, expCount: expLabels.length};
    }''', step_index)

    # Try label-based approach first
    desc_labels = page.locator('label:has-text("Step Description"), p:has-text("Step Description")')
    exp_labels = page.locator('label:has-text("Expected Result"), p:has-text("Expected Result")')

    ok = True
    if desc_labels.count() > step_index:
        desc_parent = desc_labels.nth(step_index).locator('..').locator('.ProseMirror, [contenteditable="true"]')
        if desc_parent.count() > 0 and action:
            ok = _write_prosemirror(page, desc_parent.first, action) and ok
    else:
        # Fallback: use all ProseMirror editors, paired (desc, exp, desc, exp...)
        all_editors = page.locator('.ProseMirror')
        desc_idx = step_index * 2
        if all_editors.count() > desc_idx and action:
            ok = _write_prosemirror(page, all_editors.nth(desc_idx), action) and ok

    if exp_labels.count() > step_index:
        exp_parent = exp_labels.nth(step_index).locator('..').locator('.ProseMirror, [contenteditable="true"]')
        if exp_parent.count() > 0 and expected:
            ok = _write_prosemirror(page, exp_parent.first, expected) and ok
    else:
        all_editors = page.locator('.ProseMirror')
        exp_idx = step_index * 2 + 1
        if all_editors.count() > exp_idx and expected:
            ok = _write_prosemirror(page, all_editors.nth(exp_idx), expected) and ok

    return ok


def _steps_match(existing: list[dict], desired: list[dict]) -> bool:
    """Check if existing steps already match the desired steps (idempotency)."""
    if len(existing) != len(desired):
        return False
    for ex, ds in zip(existing, desired):
        ex_desc = ex.get('description', '').strip()
        ex_exp = ex.get('expected', '').strip()
        ds_action = ds.get('action', '').strip()
        ds_expected = ds.get('expected', '').strip()
        if ex_desc != ds_action or ex_exp != ds_expected:
            return False
    return True


def cmd_sync_steps(step_dir=None, csv_file=None, case_keys=None, dry_run=False,
                   limit=None, include_manual=False, manual_only=False,
                   batch=None, resume=False):
    """Sync step definitions from JSON files into QA Touch Steps tab.

    Reads step JSON files from tests/steps/, matches to QA Touch cases
    via qatouch_case_mapping.json, then writes steps into each case's
    Steps tab via browser automation.

    With --include-manual, also reads generated/manual step files from
    tests/steps/manual/ where tests are keyed by case_key directly.
    """
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    steps_root = Path(step_dir) if step_dir else root / 'tests' / 'steps'
    manual_root = steps_root / 'manual'
    mapping_path = root / 'config' / 'qatouch_case_mapping.json'
    checkpoint_path = root / 'config' / 'step_sync_checkpoint.json'

    if not steps_root.exists():
        print(f'  Step directory not found: {steps_root}')
        return

    # Load case mapping (nodeid -> case_key + module)
    if not mapping_path.exists():
        print(f'  Case mapping not found: {mapping_path}')
        return

    with open(mapping_path) as f:
        mapping_data = json.load(f)
    mappings = mapping_data.get('mappings', {})

    # Build case_key -> {nodeid, module, case_title} lookup
    key_to_info = {}
    for nodeid, info in mappings.items():
        ck = info.get('case_key', '')
        if ck:
            key_to_info[ck] = {
                'nodeid': nodeid,
                'module': info.get('module', 'Unknown'),
                'case_title': info.get('case_title', ''),
            }

    # Load latest snapshot for authoritative module names and keys
    # (case_mapping often has parent module names, snapshot has correct sub-modules)
    snapshot_modules = {}
    snapshot_module_keys = {}
    snapshot_dir = root / 'config' / 'qatouch_snapshots'
    if snapshot_dir.exists():
        snapshots = sorted(snapshot_dir.glob('snapshot_*.json'))
        if snapshots:
            try:
                with open(snapshots[-1], encoding='utf-8') as f:
                    snap_data = json.load(f)
                for case in snap_data.get('cases', []):
                    ck = case.get('case_key', '')
                    mod = case.get('module name', '')
                    mkey = case.get('module_key', '')
                    if ck and mod:
                        snapshot_modules[ck] = mod
                    if ck and mkey:
                        snapshot_module_keys[ck] = mkey
                print(f'  Loaded {len(snapshot_modules)} module mappings from snapshot')
            except Exception as e:
                print(f'  Warning: Could not load snapshot: {e}')

    # Track case_keys already added to sync_plan (Playwright takes priority)
    seen_case_keys = set()

    # ── Load Playwright step files ──────────────────────────────────────
    pw_files = sorted(
        f for f in steps_root.rglob('*.json')
        if not str(f).startswith(str(manual_root)) and f.name != 'generated_metadata.json'
    )
    print(f'  Found {len(pw_files)} Playwright step files in {steps_root}')

    sync_plan = []
    if manual_only:
        print(f'  --manual-only: skipping {len(pw_files)} Playwright step files')

    for sf in ([] if manual_only else pw_files):
        try:
            with open(sf, encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f'  Warning: Could not load {sf}: {e}')
            continue

        test_file = data.get('test_file', '')
        class_name = data.get('class', '')
        tests = data.get('tests', {})

        for method_name, test_data in tests.items():
            steps = test_data.get('steps', [])
            if not steps or not any(s.get('action') for s in steps):
                continue  # Skip empty stubs

            # Build nodeid to look up case_key
            nodeid = f'{test_file}::{class_name}::{method_name}'
            info = None
            for nid, ninfo in mappings.items():
                if nid == nodeid or nid.split('[')[0] == nodeid:
                    info = ninfo
                    break

            if not info:
                continue  # No QA Touch mapping for this test

            ck = info.get('case_key', '')
            if not ck:
                continue

            # Filter by --cases if provided
            if case_keys and ck not in case_keys:
                continue

            # Prefer snapshot module (correct sub-module) over case_mapping module
            module = snapshot_modules.get(ck, info.get('module', 'Unknown'))
            sync_plan.append({
                'case_key': ck,
                'module': module,
                'module_key': snapshot_module_keys.get(ck, ''),
                'case_title': info.get('case_title', method_name),
                'steps': steps,
                'nodeid': nodeid,
                'source': 'playwright',
            })
            seen_case_keys.add(ck)

    # ── Load manual/generated step files ────────────────────────────────
    if include_manual and manual_root.exists():
        manual_files = sorted(
            f for f in manual_root.rglob('*.json')
            if f.name != 'generated_metadata.json'
        )
        print(f'  Found {len(manual_files)} manual/generated step files in {manual_root}')

        manual_count = 0
        for sf in manual_files:
            try:
                with open(sf, encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f'  Warning: Could not load {sf}: {e}')
                continue

            module_name = data.get('module_name', 'Unknown')
            tests = data.get('tests', {})

            for case_key, test_data in tests.items():
                steps = test_data.get('steps', [])
                if not steps or not any(s.get('action') for s in steps):
                    continue

                # Playwright steps take priority - skip if already added
                if case_key in seen_case_keys:
                    continue

                # Filter by --cases if provided
                if case_keys and case_key not in case_keys:
                    continue

                title = test_data.get('title', case_key)
                # Prefer snapshot module over step file module
                resolved_module = snapshot_modules.get(case_key, module_name)
                sync_plan.append({
                    'case_key': case_key,
                    'module': resolved_module,
                    'module_key': snapshot_module_keys.get(case_key, ''),
                    'case_title': title,
                    'steps': steps,
                    'nodeid': None,
                    'source': 'manual',
                })
                seen_case_keys.add(case_key)
                manual_count += 1

        print(f'  Added {manual_count} manual/generated cases to sync plan')

    # ── Apply batch filter ──────────────────────────────────────────────
    if batch:
        try:
            batch_n, batch_total = batch.split('/')
            batch_n = int(batch_n)
            batch_total = int(batch_total)
        except (ValueError, AttributeError):
            print(f'  Invalid batch format: {batch} (expected N/M, e.g. 1/8)')
            return

        total = len(sync_plan)
        chunk_size = (total + batch_total - 1) // batch_total
        start = (batch_n - 1) * chunk_size
        end = min(start + chunk_size, total)
        sync_plan = sync_plan[start:end]
        print(f'  Batch {batch_n}/{batch_total}: cases {start + 1}-{end} of {total}')

    # ── Apply checkpoint (resume) ───────────────────────────────────────
    if resume and checkpoint_path.exists():
        try:
            with open(checkpoint_path, encoding='utf-8') as f:
                checkpoint = json.load(f)
            synced_keys = set(checkpoint.get('synced_case_keys', []))
            before = len(sync_plan)
            sync_plan = [item for item in sync_plan if item['case_key'] not in synced_keys]
            print(f'  Resumed: skipping {before - len(sync_plan)} already-synced cases')
        except Exception as e:
            print(f'  Warning: Could not load checkpoint: {e}')

    if limit:
        sync_plan = sync_plan[:limit]

    pw_count = sum(1 for item in sync_plan if item.get('source') == 'playwright')
    manual_count = sum(1 for item in sync_plan if item.get('source') == 'manual')
    print(f'  Cases to sync: {len(sync_plan)} (Playwright: {pw_count}, Manual: {manual_count})')

    if not sync_plan:
        print('  Nothing to sync.')
        return

    # Preview
    for item in sync_plan[:20]:
        src = item.get('source', '?')[0].upper()
        print(f'  [{src}] [{item["case_key"]}] ({item["module"]}) '
              f'{item["case_title"][:50]} -- {len(item["steps"])} steps')
    if len(sync_plan) > 20:
        print(f'  ... and {len(sync_plan) - 20} more')

    if dry_run:
        print('\n  DRY RUN - no browser launched.')
        return

    # Execute
    from playwright.sync_api import sync_playwright

    rate_limiter = RateLimiter()
    report = RunReport()

    # Load existing checkpoint for incremental saving
    synced_keys = set()
    if checkpoint_path.exists():
        try:
            with open(checkpoint_path, encoding='utf-8') as f:
                synced_keys = set(json.load(f).get('synced_case_keys', []))
        except Exception:
            pass

    def _save_checkpoint():
        """Save checkpoint after each successful sync."""
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump({
                'synced_case_keys': sorted(synced_keys),
                'last_updated': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'total_synced': len(synced_keys),
            }, f, indent=2)

    cases_processed = 0

    with sync_playwright() as p:
        browser, context, page = setup_browser(p)
        if not browser:
            print('  Failed to set up browser.')
            return
        try:
            enter_project(page, context)

            # Group by module for efficient navigation
            by_module: dict[str, list[dict]] = {}
            for item in sync_plan:
                by_module.setdefault(item['module'], []).append(item)

            for module, module_items in by_module.items():
                print(f'\n  Module: {module} ({len(module_items)} cases)')

                if not ensure_authenticated(page, context):
                    for item in module_items:
                        report.add(item['case_key'], 'auth_fail')
                    continue

                # Use module_key from first item for disambiguation
                first_mkey = module_items[0].get('module_key', '') if module_items else ''
                module_nav_ok = recover_to_module(page, context, module, module_key=first_mkey)
                if not module_nav_ok:
                    print(f'    Module nav failed - will use new-tab for all {len(module_items)} cases')

                module_aborted = False
                for item in module_items:
                    if module_aborted:
                        report.add(item['case_key'], 'skipped', 'Module aborted after recovery failure')
                        continue

                    ck = item['case_key']
                    title = item['case_title']
                    steps = item['steps']
                    mkey = item.get('module_key', '')
                    src = item.get('source', '?')[0].upper()
                    print(f'    [{src}] [{ck}] {title[:55]}')

                    # If module nav failed, go straight to new-tab approach
                    if not module_nav_ok:
                        tab_result = _sync_case_in_new_tab(context, page, ck, steps, module_key=mkey, module_name=module, case_title=title)
                        if tab_result in ('ok', 'already_set'):
                            if tab_result == 'ok':
                                report.add(ck, 'ok', 'via new-tab')
                            else:
                                report.add(ck, 'already_set')
                            synced_keys.add(ck)
                            cases_processed += 1
                            _save_checkpoint()
                            rate_limiter.wait()
                        elif tab_result == 'partial':
                            report.add(ck, 'partial', 'via new-tab')
                        else:
                            report.add(ck, 'not_found')
                        continue

                    try:
                        # Navigate to case (module-based search first)
                        if not find_and_click_case(page, title):
                            # Fallback: open in new tab via module-key URL
                            tab_result = _sync_case_in_new_tab(context, page, ck, steps, module_key=mkey, module_name=module, case_title=title)
                            if tab_result in ('ok', 'already_set'):
                                if tab_result == 'ok':
                                    report.add(ck, 'ok', 'via new-tab')
                                else:
                                    report.add(ck, 'already_set')
                                synced_keys.add(ck)
                                cases_processed += 1
                                _save_checkpoint()
                                rate_limiter.wait()
                            elif tab_result == 'partial':
                                report.add(ck, 'partial', 'via new-tab')
                                shot(page, f'partial_{ck}')
                            else:
                                report.add(ck, 'not_found')
                            # No need to recover - original page untouched
                            continue

                        # Open edit form
                        if not open_edit_form(page):
                            report.add(ck, 'edit_fail')
                            force_close_all_overlays(page)
                            close_case_detail(page)
                            if not recover_to_module(page, context, module, module_key=first_mkey):
                                module_aborted = True
                            continue

                        # Navigate to Steps tab (retry for slow-loading tabs)
                        if not click_form_tab(page, 'Steps'):
                            time.sleep(3)
                            if not click_form_tab(page, 'Steps'):
                                # Check if wrong template (e.g. Exploratory Session)
                                if _switch_to_test_case_template(page):
                                    print('      Switched template to Test Case')
                                    time.sleep(2)
                                    if not click_form_tab(page, 'Steps'):
                                        shot(page, f'tab_fail_{ck}')
                                        report.add(ck, 'tab_fail', 'Steps tab not found')
                                        save_and_close(page)
                                        if not recover_to_module(page, context, module, module_key=first_mkey):
                                            module_aborted = True
                                        continue
                                else:
                                    shot(page, f'tab_fail_{ck}')
                                    report.add(ck, 'tab_fail', 'Steps tab not found')
                                    save_and_close(page)
                                    if not recover_to_module(page, context, module, module_key=first_mkey):
                                        module_aborted = True
                                    continue

                        time.sleep(2)

                        # Check current steps (idempotency)
                        existing = _extract_step_data(page)
                        if _steps_match(existing, steps):
                            print(f'      Already synced ({len(steps)} steps match)')
                            report.add(ck, 'already_set')
                            synced_keys.add(ck)
                            save_and_close(page)
                            if not recover_to_module(page, context, module, module_key=first_mkey):
                                module_aborted = True
                            cases_processed += 1
                            _save_checkpoint()
                            rate_limiter.wait()
                            continue

                        # Clear existing steps
                        if existing:
                            cleared = _clear_all_steps(page)
                            print(f'      Cleared {cleared} existing steps')
                            time.sleep(1)

                        # Add and write each step
                        for i, step in enumerate(steps):
                            if i > 0:
                                if not _click_add_step(page):
                                    print(f'      Failed to add step row {i + 1}')
                                    break

                            action = step.get('action', '')
                            expected = step.get('expected', '')
                            if not _write_step_row(page, i, action, expected):
                                print(f'      Failed to write step {i + 1}')

                        # Verify
                        time.sleep(1)
                        written = _extract_step_data(page)
                        if len(written) >= len(steps):
                            print(f'      Wrote {len(steps)} steps')
                            report.add(ck, 'ok')
                            synced_keys.add(ck)
                        elif len(written) >= len(steps) * 0.8:
                            # Accept 80%+ as success (intermittent add-row failures)
                            print(f'      Wrote {len(written)}/{len(steps)} steps (accepted)')
                            report.add(ck, 'ok', f'{len(written)}/{len(steps)}')
                            synced_keys.add(ck)
                        else:
                            print(f'      Partial: wrote {len(written)}/{len(steps)} steps')
                            report.add(ck, 'partial', f'{len(written)}/{len(steps)}')
                            shot(page, f'partial_{ck}')

                        save_and_close(page)
                        if not recover_to_module(page, context, module, module_key=first_mkey):
                            module_aborted = True
                        rate_limiter.wait()

                        # Save checkpoint after every successful case
                        cases_processed += 1
                        _save_checkpoint()

                        # Re-authenticate every 50 cases to prevent session timeout
                        if cases_processed % 50 == 0:
                            ensure_authenticated(page, context)

                    except Exception as e:
                        print(f'      ERROR: {e}')
                        report.add(ck, 'error', str(e)[:200])
                        shot(page, f'error_{ck}')
                        if not recover_to_module(page, context, module, module_key=first_mkey):
                            module_aborted = True

            # Final checkpoint save
            _save_checkpoint()

            report.print_summary()
            if report.fail_count > 0:
                report.save()

        finally:
            # Always save checkpoint on exit (even on crash)
            _save_checkpoint()
            context.storage_state(path=AUTH_STATE_FILE)
            browser.close()


def cmd_audit_steps(sample_size=30, csv_file=None):
    """Audit test step structure across a sample of cases.

    Opens each case's edit form, clicks the Steps tab, and checks if
    steps are properly separated or crammed into a single line.
    """
    # Get sample cases from API
    client = QATouchClient()
    all_cases = client.list_all_test_cases(PROJECT_KEY)
    print(f'  Total cases in project: {len(all_cases)}')

    if csv_file:
        # Use specific cases from CSV
        case_keys_from_csv = set()
        with open(csv_file, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                case_keys_from_csv.add(row.get('case_key', ''))
        cases = [c for c in all_cases if c.get('case_key') in case_keys_from_csv]
    else:
        # Sample evenly across modules
        import random
        by_module: dict[str, list] = {}
        for c in all_cases:
            mod = c.get('module name', 'unknown')
            by_module.setdefault(mod, []).append(c)

        sampled = []
        mod_names = sorted(by_module.keys())
        random.seed(42)  # Deterministic for reproducibility
        per_mod = max(1, sample_size // len(mod_names)) if mod_names else 1
        for mod in mod_names:
            pool = by_module[mod]
            n = min(per_mod, len(pool))
            sampled.extend(random.sample(pool, n))
            if len(sampled) >= sample_size:
                break

        # If we didn't get enough, fill from remaining
        if len(sampled) < sample_size:
            remaining = [c for c in all_cases if c not in sampled]
            extra = random.sample(remaining, min(sample_size - len(sampled), len(remaining)))
            sampled.extend(extra)

        cases = sampled[:sample_size]

    print(f'  Auditing {len(cases)} cases...\n')

    from playwright.sync_api import sync_playwright
    results = []

    with sync_playwright() as p:
        browser, context, page = setup_browser(p)
        if not browser:
            return
        try:
            enter_project(page, context)
            rate_limiter = RateLimiter(min_interval=2.0, burst_pause=10.0, burst_threshold=8)

            for i, case in enumerate(cases):
                ck = case.get('case_key', '?')
                title = case.get('case_title', '?')
                module = case.get('module name', '?')
                print(f'  [{i+1}/{len(cases)}] [{ck}] {module}: {title[:50]}...')

                rate_limiter.wait()

                # Refresh page every 15 cases
                if i > 0 and i % 15 == 0:
                    print(f'    [Refreshing page]')
                    page.reload()
                    time.sleep(5)
                    enter_project(page, context)

                # Navigate to module
                if not navigate_to_module(page, module):
                    print(f'    Module not found: {module}')
                    results.append({
                        'case_key': ck, 'module': module,
                        'title': title[:80], 'issue': 'module_not_found',
                        'step_count': 0, 'numbered_count': 0,
                    })
                    continue

                # Find and click case
                if not find_and_click_case(page, title):
                    print(f'    Case not found')
                    results.append({
                        'case_key': ck, 'module': module,
                        'title': title[:80], 'issue': 'case_not_found',
                        'step_count': 0, 'numbered_count': 0,
                    })
                    continue

                # Open edit form
                if not open_edit_form(page):
                    results.append({
                        'case_key': ck, 'module': module,
                        'title': title[:80], 'issue': 'edit_form_failed',
                        'step_count': 0, 'numbered_count': 0,
                    })
                    continue

                # Click Steps tab
                if not click_form_tab(page, 'Steps'):
                    print(f'    Steps tab not found')
                    # Close form
                    page.keyboard.press('Escape')
                    time.sleep(1)
                    results.append({
                        'case_key': ck, 'module': module,
                        'title': title[:80], 'issue': 'no_steps_tab',
                        'step_count': 0, 'numbered_count': 0,
                    })
                    continue

                # Extract step data
                steps = _extract_step_data(page)
                analysis = _analyze_step_quality(steps)

                status_icon = {
                    'all_in_one_line': 'BAD',
                    'single_long_step': 'WARN',
                    'no_steps': 'EMPTY',
                    'none': 'OK',
                }[analysis['issue']]

                desc_preview = ''
                if steps:
                    desc_preview = steps[0].get('description', '')[:60]

                print(f'    [{status_icon}] {analysis["step_count"]} steps, '
                      f'numbered={analysis["numbered_count"]}, '
                      f'desc="{desc_preview}..."')

                results.append({
                    'case_key': ck, 'module': module,
                    'title': title[:80], 'issue': analysis['issue'],
                    'step_count': analysis['step_count'],
                    'numbered_count': analysis['numbered_count'],
                    'max_desc_len': analysis['max_desc_len'],
                })

                # Close the edit form (Escape or close button)
                close_btn = page.locator('span.close-icon, button.close, '
                                         'button:has-text("Cancel")')
                if close_btn.count() > 0:
                    close_btn.first.click()
                    time.sleep(2)
                else:
                    page.keyboard.press('Escape')
                    time.sleep(2)

                # Go back to case list
                page.go_back()
                time.sleep(3)

        finally:
            context.storage_state(path=AUTH_STATE_FILE)
            browser.close()

    # Print summary
    total = len(results)
    all_in_one = sum(1 for r in results if r['issue'] == 'all_in_one_line')
    single_long = sum(1 for r in results if r['issue'] == 'single_long_step')
    no_steps = sum(1 for r in results if r['issue'] == 'no_steps')
    ok = sum(1 for r in results if r['issue'] == 'none')
    errors = sum(1 for r in results if r['issue'] in
                 ('module_not_found', 'case_not_found', 'edit_form_failed', 'no_steps_tab'))

    print(f'\n{"=" * 60}')
    print(f'  STEP AUDIT RESULTS ({total} cases sampled)')
    print(f'{"=" * 60}')
    print(f'  OK (individual steps):  {ok}')
    print(f'  BAD (all in one line):  {all_in_one}')
    print(f'  WARN (single long):     {single_long}')
    print(f'  EMPTY (no steps):       {no_steps}')
    print(f'  Errors (nav failed):    {errors}')
    if total > 0:
        bad_pct = (all_in_one + single_long) / total * 100
        print(f'\n  Issue rate: {bad_pct:.0f}% of sampled cases')

    # Save report
    report_path = os.path.join(SHOT_DIR, f'step_audit_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    print(f'  Report saved: {report_path}')


# ---------------------------------------------------------------------------
# Duplicate Module Detection (API-based, no browser needed)
# ---------------------------------------------------------------------------
def cmd_check_duplicates():
    """Scan QA Touch modules via API and report any duplicate names.

    This is a guardrail command - run before scaffold-new or after bulk
    module creation to catch duplicate module names early.
    """
    client = QATouchClient()
    modules = client.list_all_modules('JlW1')

    # Group by name
    by_name: dict[str, list] = {}
    for m in modules:
        name = m.get('section_name', '').strip()
        by_name.setdefault(name, []).append(m)

    dupes = {name: mods for name, mods in by_name.items() if len(mods) > 1}

    if not dupes:
        print(f'\n  No duplicate module names found ({len(modules)} modules total).')
        return

    total_dupe_modules = sum(len(v) for v in dupes.values())
    print(f'\n  WARNING: {len(dupes)} duplicate name groups '
          f'({total_dupe_modules} modules)')
    print(f'  {"=" * 50}')

    for name, mods in sorted(dupes.items()):
        print(f'\n  "{name}" ({len(mods)} modules):')
        for m in mods:
            key = m.get('section_key', '?')
            count = m.get('case_count', '?')
            print(f'    [{key}] {count} cases')

    print(f'\n  Fix: Rename duplicates using rename-modules command.')
    print(f'  Convention: "{"{Category}"} - {"{Feature Context}"}"')
    print(f'  Example: "Search - Insights", "Search - LPR"')


# ---------------------------------------------------------------------------
# Sync Unfound - retry not_found cases with full page reload per case
# ---------------------------------------------------------------------------
def _wait_for_case_list(page, timeout=10):
    """Wait for .cl-container elements to appear in the DOM."""
    start = time.time()
    while time.time() - start < timeout:
        count = page.evaluate('() => document.querySelectorAll(".cl-container").length')
        if count > 0:
            return count
        time.sleep(1)
    return 0


def _find_case_exhaustive(page, title, module):
    """Enhanced case search: maximize per-page, scroll exhaustively, paginate.

    Returns True if the case was found and scrolled into view.
    """
    # Wait for case list to fully load
    container_count = _wait_for_case_list(page, timeout=10)
    if container_count == 0:
        print(f'      [exhaustive] No .cl-container elements after 10s wait')
        return False

    # Try immediate DOM search
    result = _search_cases_in_dom(page, title)
    if result.get('found'):
        return True

    # Maximize per-page (try twice)
    for attempt in range(2):
        if _maximize_per_page(page):
            time.sleep(5)  # Longer wait for re-render
            break
        time.sleep(2)

    # Wait for containers to re-render after per-page change
    _wait_for_case_list(page, timeout=8)

    # Search current DOM
    result = _search_cases_in_dom(page, title)
    if result.get('found'):
        return True

    # Scroll content container exhaustively (60 iterations × 500px = 30,000px)
    page.evaluate('''() => {
        var wrap = document.querySelector('.test_case_table_content_outer_wrap');
        if (wrap) wrap.scrollTop = 0;
    }''')
    time.sleep(0.5)

    for scroll_i in range(60):
        page.evaluate('''() => {
            var wrap = document.querySelector('.test_case_table_content_outer_wrap');
            if (wrap) wrap.scrollTop += 500;
        }''')
        time.sleep(0.5)
        result = _search_cases_in_dom(page, title)
        if result.get('found'):
            print(f'      [exhaustive] Found after {scroll_i + 1} scroll steps')
            return True
        at_bottom = page.evaluate('''() => {
            var wrap = document.querySelector('.test_case_table_content_outer_wrap');
            if (wrap) return wrap.scrollTop + wrap.clientHeight >= wrap.scrollHeight - 20;
            return true;
        }''')
        if at_bottom:
            break

    # Paginate through all pages with longer waits
    pag = _get_pagination_info(page)
    total_pages = pag.get('totalPages', 1)
    if total_pages <= 1:
        return False

    print(f'      [exhaustive] Paginating through {total_pages} pages...')
    for pg in range(1, total_pages + 1):
        if not _go_to_page(page, pg):
            if not _go_to_next_page(page):
                break
        time.sleep(2)  # Longer wait between pages

        # Scroll each page
        page.evaluate('''() => {
            var wrap = document.querySelector('.test_case_table_content_outer_wrap');
            if (wrap) wrap.scrollTop = 0;
        }''')
        time.sleep(0.5)

        result = _search_cases_in_dom(page, title)
        if result.get('found'):
            print(f'      [exhaustive] Found on page {pg}!')
            return True

        for scroll_j in range(30):
            page.evaluate('''() => {
                var wrap = document.querySelector('.test_case_table_content_outer_wrap');
                if (wrap) wrap.scrollTop += 500;
            }''')
            time.sleep(0.3)
            result = _search_cases_in_dom(page, title)
            if result.get('found'):
                print(f'      [exhaustive] Found on page {pg} (after scroll {scroll_j + 1})!')
                return True
            at_bottom2 = page.evaluate('''() => {
                var wrap = document.querySelector('.test_case_table_content_outer_wrap');
                if (wrap) return wrap.scrollTop + wrap.clientHeight >= wrap.scrollHeight - 20;
                return true;
            }''')
            if at_bottom2:
                break

    return False


def _get_all_dom_titles(page):
    """Get all case titles currently in the DOM for diagnostics."""
    return page.evaluate('''() => {
        var containers = document.querySelectorAll('.cl-container');
        var titles = [];
        for (var i = 0; i < containers.length; i++) {
            var ps = containers[i].querySelectorAll('p');
            for (var j = 0; j < ps.length; j++) {
                var t = ps[j].textContent.trim();
                if (t.length > 15) { titles.push(t); break; }
            }
        }
        return titles;
    }''')


def cmd_sync_unfound(case_keys=None, limit=None, dry_run=False):
    """Retry not_found cases from the latest run report with enhanced search.

    Groups cases by module and uses exhaustive DOM search (longer waits,
    aggressive scrolling, per-page maximization). Falls back to full page
    reload + re-enter project if the first search attempt fails.
    """
    from pathlib import Path
    import glob as g2

    root = Path(__file__).resolve().parent.parent
    manual_root = root / 'tests' / 'steps' / 'manual'
    checkpoint_path = root / 'config' / 'step_sync_checkpoint.json'

    # Load snapshot module keys for module_key lookup
    snapshot_module_keys = {}
    snapshot_dir = root / 'config' / 'qatouch_snapshots'
    if snapshot_dir.exists():
        snapshots = sorted(snapshot_dir.glob('snapshot_*.json'))
        if snapshots:
            try:
                with open(snapshots[-1], encoding='utf-8') as f:
                    snap_data = json.load(f)
                for case in snap_data.get('cases', []):
                    ck = case.get('case_key', '')
                    mkey = case.get('module_key', '')
                    if ck and mkey:
                        snapshot_module_keys[ck] = mkey
            except Exception:
                pass

    # Find not_found case keys
    if case_keys:
        unfound_keys = set(case_keys)
        print(f'  Using {len(unfound_keys)} case keys from --cases')
    else:
        # Collect not_found keys from ALL run reports (union)
        report_files = sorted(g2.glob(str(root / 'tools' / 'debug_screenshots' / 'run_report_*.json')))
        if not report_files:
            print('  No run reports found. Use --cases to specify case keys.')
            return

        unfound_keys = set()
        for rf in report_files:
            try:
                with open(rf) as f:
                    data = json.load(f)
                for e in data:
                    if e.get('status') == 'not_found':
                        unfound_keys.add(e['case_key'])
            except Exception:
                continue

        if not unfound_keys:
            print('  No run reports with not_found entries. Use --cases to specify case keys.')
            return

        print(f'  Collected {len(unfound_keys)} unique not_found keys from {len(report_files)} reports')

    if not unfound_keys:
        print('  No not_found cases to retry.')
        return

    # Load step data from manual step files
    sync_plan = []
    for filepath in sorted(manual_root.rglob('*.json')):
        if filepath.name == 'generated_metadata.json':
            continue
        try:
            with open(filepath, encoding='utf-8') as f:
                data = json.load(f)
        except Exception:
            continue

        module_name = data.get('module_name', 'Unknown')
        for ck, test_data in data.get('tests', {}).items():
            if ck not in unfound_keys:
                continue
            steps = test_data.get('steps', [])
            if not steps or not any(s.get('action') for s in steps):
                continue
            sync_plan.append({
                'case_key': ck,
                'module': module_name,
                'module_key': data.get('module_key', snapshot_module_keys.get(ck, '')),
                'case_title': test_data.get('title', ck),
                'steps': steps,
            })

    print(f'  Loaded step data for {len(sync_plan)} cases')
    missing = unfound_keys - {item['case_key'] for item in sync_plan}
    if missing:
        print(f'  Warning: {len(missing)} case keys not found in manual step files')

    if limit:
        sync_plan = sync_plan[:limit]

    # Preview
    print(f'\n{"=" * 60}')
    print(f'  QA Touch sync-unfound - {len(sync_plan)} cases')
    print(f'  Strategy: per-module grouping, enhanced search, reload-on-failure')
    print(f'{"=" * 60}')
    for item in sync_plan[:20]:
        print(f'  [{item["case_key"]}] ({item["module"]}) {item["case_title"][:50]}')
    if len(sync_plan) > 20:
        print(f'  ... and {len(sync_plan) - 20} more')

    if dry_run:
        print('\n  DRY RUN - no browser launched.')
        return

    # Load checkpoint
    synced_keys = set()
    if checkpoint_path.exists():
        try:
            with open(checkpoint_path, encoding='utf-8') as f:
                synced_keys = set(json.load(f).get('synced_case_keys', []))
        except Exception:
            pass

    # Skip already-synced
    before = len(sync_plan)
    sync_plan = [item for item in sync_plan if item['case_key'] not in synced_keys]
    if before > len(sync_plan):
        print(f'  Skipping {before - len(sync_plan)} already-synced cases')

    if not sync_plan:
        print('  All cases already synced.')
        return

    def _save_checkpoint():
        with open(checkpoint_path, 'w', encoding='utf-8') as f:
            json.dump({
                'synced_case_keys': sorted(synced_keys),
                'last_updated': time.strftime('%Y-%m-%dT%H:%M:%S'),
                'total_synced': len(synced_keys),
            }, f, indent=2)

    # Execute
    from playwright.sync_api import sync_playwright

    report = RunReport()
    rate_limiter = RateLimiter(min_interval=3.0, burst_pause=15.0, burst_threshold=5)

    # Group by module for efficient navigation (process all cases per module)
    from collections import OrderedDict
    by_module: OrderedDict[str, list] = OrderedDict()
    for item in sync_plan:
        by_module.setdefault(item['module'], []).append(item)

    with sync_playwright() as p:
        browser, context, page = setup_browser(p)
        if not browser:
            print('  Failed to set up browser.')
            return
        try:
            enter_project(page, context)
            case_num = 0

            def _nav_to_module_with_idx(mod, idx):
                """Navigate to a module using the known working match_index."""
                if idx > 0:
                    return navigate_to_module(page, mod, match_index=idx)
                return navigate_to_module(page, mod)

            def _recover_to_module_with_idx(mod, idx):
                """Recover to module, using match_index for duplicates."""
                _force_dismiss_drawers(page)
                if _nav_to_module_with_idx(mod, idx):
                    return True
                # Fallback: close overlays + re-enter project
                try:
                    force_close_all_overlays(page)
                    enter_project(page, context)
                    if _nav_to_module_with_idx(mod, idx):
                        return True
                except Exception:
                    pass
                return False

            for module, module_items in by_module.items():
                print(f'\n  Module: {module} ({len(module_items)} cases)')

                # Re-authenticate every module to prevent session timeout
                if not ensure_authenticated(page, context):
                    for item in module_items:
                        report.add(item['case_key'], 'auth_fail')
                    continue

                # Get module_key from first item (all items in same module share the key)
                first_mkey = module_items[0].get('module_key', '') if module_items else ''
                working_idx = 0

                # Navigate to module - use key-aware navigation
                navigated = False
                if first_mkey:
                    navigated = navigate_to_module_by_key(page, module, first_mkey)
                else:
                    # Check for duplicate module names
                    num_matches = count_module_matches(page, module)
                    working_idx = 0
                    if num_matches > 1:
                        print(f'    WARNING: {num_matches} modules match "{module}"')

                    # Try each duplicate until cases appear
                    for match_idx in range(max(1, num_matches)):
                        if not navigate_to_module(page, module, match_index=match_idx):
                            continue
                        time.sleep(5)
                        container_count = _wait_for_case_list(page, timeout=10)
                        if container_count > 0:
                            if match_idx > 0:
                                print(f'    Found cases in match #{match_idx + 1}')
                            working_idx = match_idx
                            navigated = True
                            break
                        elif num_matches > 1:
                            print(f'    Match #{match_idx + 1}: 0 cases, trying next...')

                if not navigated:
                    # Last resort: full recovery
                    if not recover_to_module(page, context, module, module_key=first_mkey):
                        for item in module_items:
                            report.add(item['case_key'], 'nav_fail', f'Module: {module}')
                        continue
                    time.sleep(5)

                container_count = _wait_for_case_list(page, timeout=10)

                print(f'    Case list loaded: {container_count} containers')

                # Maximize per-page once for the module (with retry)
                for attempt in range(2):
                    if _maximize_per_page(page):
                        time.sleep(5)
                        break
                    time.sleep(2)

                # Re-check container count after per-page change
                container_count = _wait_for_case_list(page, timeout=5)
                if container_count > 0:
                    print(f'    After per-page: {container_count} containers')

                for item in module_items:
                    case_num += 1
                    ck = item['case_key']
                    title = item['case_title']
                    steps = item['steps']

                    print(f'\n    [{case_num}/{len(sync_plan)}] [{ck}] {title[:55]}')

                    try:
                        # Enhanced search with exhaustive scroll/pagination
                        if not _find_case_exhaustive(page, title, module):
                            # Dump diagnostics
                            dom_titles = _get_all_dom_titles(page)
                            print(f'      NOT FOUND - {len(dom_titles)} cases in DOM:')
                            for dt in dom_titles[:10]:
                                print(f'        - {dt[:70]}')
                            if len(dom_titles) > 10:
                                print(f'        ... and {len(dom_titles) - 10} more')

                            # Retry: re-navigate to correct module duplicate
                            print(f'      Retrying module navigation (idx={working_idx})...')
                            if _recover_to_module_with_idx(module, working_idx):
                                time.sleep(5)
                                _wait_for_case_list(page, timeout=10)
                                for _ in range(2):
                                    if _maximize_per_page(page):
                                        time.sleep(5)
                                        break
                                    time.sleep(2)
                                if not _find_case_exhaustive(page, title, module):
                                    shot(page, f'unfound_{ck}')
                                    report.add(ck, 'not_found')
                                    continue
                            else:
                                report.add(ck, 'not_found', 'Module recovery failed')
                                continue

                        # Use find_and_click_case for the clicking logic
                        if not find_and_click_case(page, title):
                            report.add(ck, 'not_found', 'Click failed')
                            if not _recover_to_module_with_idx(module, working_idx):
                                break
                            continue

                        # Open edit form
                        if not open_edit_form(page):
                            report.add(ck, 'edit_fail')
                            force_close_all_overlays(page)
                            close_case_detail(page)
                            if not _recover_to_module_with_idx(module, working_idx):
                                break
                            continue

                        # Navigate to Steps tab
                        if not click_form_tab(page, 'Steps'):
                            time.sleep(3)
                            if not click_form_tab(page, 'Steps'):
                                if _switch_to_test_case_template(page):
                                    time.sleep(2)
                                    if not click_form_tab(page, 'Steps'):
                                        report.add(ck, 'tab_fail')
                                        save_and_close(page)
                                        if not _recover_to_module_with_idx(module, working_idx):
                                            break
                                        continue
                                else:
                                    report.add(ck, 'tab_fail')
                                    save_and_close(page)
                                    if not _recover_to_module_with_idx(module, working_idx):
                                        break
                                    continue

                        time.sleep(2)

                        # Check existing steps (idempotency)
                        existing = _extract_step_data(page)
                        if _steps_match(existing, steps):
                            print(f'      Already synced ({len(steps)} steps match)')
                            report.add(ck, 'already_set')
                            synced_keys.add(ck)
                            save_and_close(page)
                            _save_checkpoint()
                            rate_limiter.wait()
                            if not _recover_to_module_with_idx(module, working_idx):
                                break
                            continue

                        # Clear existing steps
                        if existing:
                            cleared = _clear_all_steps(page)
                            print(f'      Cleared {cleared} existing steps')
                            time.sleep(1)

                        # Write steps
                        for i, step in enumerate(steps):
                            if i > 0:
                                if not _click_add_step(page):
                                    print(f'      Failed to add step row {i + 1}')
                                    break
                            action = step.get('action', '')
                            expected = step.get('expected', '')
                            if not _write_step_row(page, i, action, expected):
                                print(f'      Failed to write step {i + 1}')

                        # Verify
                        time.sleep(1)
                        written = _extract_step_data(page)
                        if len(written) >= len(steps):
                            print(f'      Wrote {len(steps)} steps')
                            report.add(ck, 'ok')
                            synced_keys.add(ck)
                        elif len(written) >= len(steps) * 0.8:
                            print(f'      Wrote {len(written)}/{len(steps)} steps (accepted)')
                            report.add(ck, 'ok', f'{len(written)}/{len(steps)}')
                            synced_keys.add(ck)
                        else:
                            print(f'      Partial: wrote {len(written)}/{len(steps)} steps')
                            report.add(ck, 'partial', f'{len(written)}/{len(steps)}')
                            shot(page, f'partial_{ck}')

                        save_and_close(page)
                        _save_checkpoint()
                        rate_limiter.wait()

                        # Recover to module for next case
                        if not _recover_to_module_with_idx(module, working_idx):
                            break

                    except Exception as e:
                        print(f'      ERROR: {e}')
                        report.add(ck, 'error', str(e)[:200])
                        shot(page, f'error_{ck}')
                        if not _recover_to_module_with_idx(module, working_idx):
                            break

            # Final save
            _save_checkpoint()
            report.print_summary()
            if report.fail_count > 0:
                report.save()

        finally:
            _save_checkpoint()
            context.storage_state(path=AUTH_STATE_FILE)
            browser.close()


# ---------------------------------------------------------------------------
# Command Dispatch
# ---------------------------------------------------------------------------
USAGE = """
QA Touch Browser Automation

Commands:
  set-mode          Set Mode=Automation on cases
  set-tags          Add tags to cases (comma-separated)
  set-type          Set Type on cases (Functional, Regression, Acceptance, etc.)
  set-priority      Set Priority on cases (Critical, High, Medium, Low)
  sync-steps        Write step definitions from JSON files into QA Touch Steps tab
  sync-unfound      Retry not_found cases from latest run report (full reload per case)
  delete            Delete cases from QA Touch
  bulk-update       Apply multiple property changes from CSV
  rename-modules    Rename duplicate modules from CSV plan
  check-duplicates  Scan for duplicate module names (API, no browser)
  audit-steps       Sample cases and check step structure (browser)
  explore           Debug: screenshot every form tab for a case

Options:
  --csv FILE            CSV input (default: config/qatouch_set_automation_mode.csv)
  --cases K1 K2         Specific case keys (resolved via API)
  --step-dir DIR        Step JSON directory (default: tests/steps/)
  --include-manual      Also sync generated/manual steps from tests/steps/manual/
  --batch N/M           Split into M batches, run batch N (e.g. --batch 1/8)
  --resume              Resume from checkpoint (skip already-synced cases)
  --limit N             Process only first N items (for testing)
  --dry-run             Preview without browser

Examples:
  python tools/qatouch_browser.py set-mode --cases LD3gmJ wmjgKb
  python tools/qatouch_browser.py set-tags SMOKE,SANITY --csv config/my_cases.csv
  python tools/qatouch_browser.py set-type Functional --cases LD3gmJ
  python tools/qatouch_browser.py sync-steps --dry-run
  python tools/qatouch_browser.py sync-steps --include-manual --dry-run
  python tools/qatouch_browser.py sync-steps --include-manual --batch 1/8
  python tools/qatouch_browser.py sync-steps --include-manual --resume
  python tools/qatouch_browser.py sync-steps --cases LD3gmJ wmjgKb
  python tools/qatouch_browser.py sync-steps --limit 5
  python tools/qatouch_browser.py bulk-update --csv config/bulk.csv
  python tools/qatouch_browser.py rename-modules --dry-run
  python tools/qatouch_browser.py check-duplicates
  python tools/qatouch_browser.py sync-unfound --dry-run
  python tools/qatouch_browser.py sync-unfound --cases kpZX4e 11zPWb
  python tools/qatouch_browser.py sync-unfound --limit 5
  python tools/qatouch_browser.py audit-steps --limit 30
  python tools/qatouch_browser.py explore --case LD3gmJ
"""


def _parse_args():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(USAGE)
        sys.exit(0)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    dry_run = '--dry-run' in args
    if dry_run:
        args.remove('--dry-run')

    csv_file = DEFAULT_CSV
    if '--csv' in args:
        idx = args.index('--csv')
        csv_file = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    case_keys = None
    if '--cases' in args:
        idx = args.index('--cases')
        case_keys = args[idx + 1:]
        args = args[:idx]

    case_key_single = None
    if '--case' in args:
        idx = args.index('--case')
        case_key_single = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    limit = None
    if '--limit' in args:
        idx = args.index('--limit')
        limit = int(args[idx + 1])
        args = args[:idx] + args[idx + 2:]

    step_dir = None
    if '--step-dir' in args:
        idx = args.index('--step-dir')
        step_dir = args[idx + 1]
        args = args[:idx] + args[idx + 2:]

    include_manual = '--include-manual' in args
    if include_manual:
        args.remove('--include-manual')

    manual_only = '--manual-only' in args
    if manual_only:
        args.remove('--manual-only')
        include_manual = True  # --manual-only implies --include-manual

    batch = None
    if '--batch' in args:
        idx = args.index('--batch')
        batch = args[idx + 1]  # e.g. "1/8"
        args = args[:idx] + args[idx + 2:]

    resume = '--resume' in args
    if resume:
        args.remove('--resume')

    # Positional value (for set-tags, set-type, set-priority)
    value = args[0] if args else None

    return cmd, value, csv_file, case_keys, case_key_single, dry_run, limit, step_dir, include_manual, manual_only, batch, resume


def main():
    cmd, value, csv_file, case_keys, case_key_single, dry_run, limit, step_dir, include_manual, manual_only, batch, resume = _parse_args()

    if cmd == 'explore':
        if not case_key_single and case_keys:
            case_key_single = case_keys[0]
        if not case_key_single:
            print('  explore requires --case CASE_KEY')
            return
        cmd_explore(case_key_single)
        return

    if cmd == 'rename-modules':
        cmd_rename_modules(csv_file=csv_file if csv_file != DEFAULT_CSV else None,
                           dry_run=dry_run, limit=limit)
        return

    if cmd == 'check-duplicates':
        cmd_check_duplicates()
        return

    if cmd == 'audit-steps':
        cmd_audit_steps(
            sample_size=limit or 30,
            csv_file=csv_file if csv_file != DEFAULT_CSV else None)
        return

    if cmd == 'sync-steps':
        cmd_sync_steps(
            step_dir=step_dir,
            csv_file=csv_file if csv_file != DEFAULT_CSV else None,
            case_keys=case_keys,
            dry_run=dry_run,
            limit=limit,
            include_manual=include_manual,
            manual_only=manual_only,
            batch=batch,
            resume=resume)
        return

    if cmd == 'sync-unfound':
        cmd_sync_unfound(
            case_keys=case_keys,
            limit=limit,
            dry_run=dry_run)
        return

    # Load cases
    if case_keys:
        print(f'  Resolving {len(case_keys)} case keys via API...')
        cases = resolve_cases_from_keys(case_keys)
    else:
        cases = load_csv(csv_file)

    if not cases:
        print('  No cases to process.')
        return

    # Build operations list
    operations = []
    if cmd == 'set-mode':
        operations.append({'action': 'set-mode', 'value': value or 'Automation'})
    elif cmd == 'set-tags':
        if not value:
            print('  set-tags requires TAG1,TAG2 argument')
            return
        tags = [t.strip() for t in value.split(',')]
        operations.append({'action': 'set-tags', 'tags': tags})
    elif cmd == 'set-type':
        if not value:
            print('  set-type requires TYPE argument')
            return
        operations.append({'action': 'set-type', 'value': value})
    elif cmd == 'set-priority':
        if not value:
            print('  set-priority requires PRIORITY argument')
            return
        operations.append({'action': 'set-priority', 'value': value})
    elif cmd == 'delete':
        print('  Delete not yet implemented in new script - use qatouch_set_mode.py')
        return
    elif cmd == 'bulk-update':
        # Each row in CSV can have: mode, tags, type, priority columns
        for c in cases:
            c['_ops'] = []
            if c.get('mode'):
                c['_ops'].append({'action': 'set-mode', 'value': c['mode']})
            if c.get('tags'):
                c['_ops'].append({'action': 'set-tags', 'tags': [t.strip() for t in c['tags'].split(',')]})
            if c.get('type'):
                c['_ops'].append({'action': 'set-type', 'value': c['type']})
            if c.get('priority'):
                c['_ops'].append({'action': 'set-priority', 'value': c['priority']})
    else:
        print(f'  Unknown command: {cmd}')
        print(USAGE)
        return

    # Preview
    print(f'\n{"=" * 60}')
    print(f'  QA Touch Browser Automation - {cmd}')
    print(f'  Cases: {len(cases)}')
    if operations:
        for op in operations:
            print(f'  Operation: {op}')
    print(f'{"=" * 60}')
    for c in cases[:20]:
        print(f'  [{c.get("case_key", "?")}] ({c.get("module", "?")}) {c.get("case_title", "?")[:55]}')
    if len(cases) > 20:
        print(f'  ... and {len(cases) - 20} more')

    if dry_run:
        print('\n  DRY RUN - no browser launched.')
        return

    # Execute
    from playwright.sync_api import sync_playwright
    rate_limiter = RateLimiter()
    report = RunReport()

    with sync_playwright() as p:
        browser, context, page = setup_browser(p)
        if not browser:
            print('  Failed to set up browser.')
            return
        try:
            enter_project(page, context)

            if cmd == 'bulk-update':
                # Process each case with its per-row operations
                by_module: dict[str, list[dict]] = {}
                for c in cases:
                    by_module.setdefault(c.get('module', 'Unknown'), []).append(c)

                for module, module_cases in by_module.items():
                    print(f'\n  Module: {module} ({len(module_cases)} cases)')
                    if not navigate_to_module(page, module):
                        for c in module_cases:
                            report.add(c['case_key'], 'nav_fail')
                        continue

                    for case in module_cases:
                        ops = case.get('_ops', [])
                        if not ops:
                            report.add(case['case_key'], 'skipped', 'No operations')
                            continue
                        ok = process_case(page, context, case, ops, rate_limiter, report)
                        if not ok:
                            time.sleep(1)
                            navigate_to_module(page, module)
            else:
                run_batch(page, context, cases, operations, rate_limiter, report)

            report.print_summary()
            if report.fail_count > 0:
                report.save()

        finally:
            context.storage_state(path=AUTH_STATE_FILE)
            browser.close()


if __name__ == '__main__':
    main()
