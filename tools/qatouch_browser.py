"""QA Touch browser automation - set Mode, Tags, Type, Priority; rename modules;
audit steps; detect duplicates; delete cases.

Replaces qatouch_set_mode.py with robust pagination handling, auth refresh,
multi-tab form navigation, tag management, module rename, and step auditing.

Usage:
  python tools/qatouch_browser.py set-mode          [--csv FILE] [--cases K1 K2] [--dry-run]
  python tools/qatouch_browser.py set-tags          TAG1,TAG2 [--csv FILE] [--cases K1 K2] [--dry-run]
  python tools/qatouch_browser.py set-type          TYPE [--csv FILE] [--cases K1 K2] [--dry-run]
  python tools/qatouch_browser.py set-priority      PRI [--csv FILE] [--cases K1 K2] [--dry-run]
  python tools/qatouch_browser.py rename-modules    [--csv FILE] [--limit N] [--dry-run]
  python tools/qatouch_browser.py check-duplicates
  python tools/qatouch_browser.py audit-steps       [--limit N]
  python tools/qatouch_browser.py delete            [--csv FILE] [--cases K1 K2] [--dry-run]
  python tools/qatouch_browser.py bulk-update       --csv FILE [--dry-run]
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
        return sum(1 for r in self.results if r['status'] == 'success')

    @property
    def skip_count(self):
        return sum(1 for r in self.results if r['status'] == 'skipped')

    @property
    def fail_count(self):
        return sum(1 for r in self.results if r['status'] not in ('success', 'skipped'))

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
                if r['status'] not in ('success', 'skipped'):
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
    page.goto(f'{BASE_URL}/v2#/')
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
    browser = p.chromium.launch(headless=headless, slow_mo=150)

    if os.path.exists(AUTH_STATE_FILE):
        print('  Loading saved auth state...')
        ctx = browser.new_context(viewport={'width': 1400, 'height': 900},
                                  storage_state=AUTH_STATE_FILE)
        page = ctx.new_page()
        page.goto(f'{BASE_URL}/v2#/new-projects')
        time.sleep(5)
        if _check_logged_in(page):
            print('  Auth state valid!')
            return browser, ctx, page
        print('  Auth expired - need fresh login.')
        ctx.close()

    ctx = browser.new_context(viewport={'width': 1400, 'height': 900})
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
def enter_project(page):
    """Navigate into NexaiQ-Core project."""
    page.goto(f'{BASE_URL}/v2#/new-projects')
    page.wait_for_load_state('networkidle')
    time.sleep(3)
    page.locator('text="NexaiQ-Core"').first.click()
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
    # then cleaned version, then just the first word as last resort.
    raw_trimmed = module_name.strip()
    clean = re.sub(r'[^A-Za-z0-9 ]', ' ', module_name).strip()
    clean = ' '.join(clean.split())  # collapse multiple spaces
    words = clean.split()
    filter_candidates = [raw_trimmed]
    cleaned_short = ' '.join(words[:3]) if len(words) > 3 else clean
    if cleaned_short != raw_trimmed:
        filter_candidates.append(cleaned_short)
    if words and words[0] != raw_trimmed and words[0] != cleaned_short:
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
    cleaned_short = ' '.join(words[:3]) if len(words) > 3 else clean
    if cleaned_short != raw_trimmed:
        filter_candidates.append(cleaned_short)
    if words and words[0] != raw_trimmed and words[0] != cleaned_short:
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
def _search_cases_in_dom(page, title):
    """Search currently-loaded .cl-container elements for a case title.
    Returns {found: true/false}."""
    return page.evaluate('''(title) => {
        var containers = document.querySelectorAll('.cl-container');
        var target = title.length > 60 ? title.substring(0, 60) : title;
        for (var i = 0; i < containers.length; i++) {
            var ps = containers[i].querySelectorAll('p');
            for (var j = 0; j < ps.length; j++) {
                var text = ps[j].textContent.trim();
                if (text === title || (target.length >= 20 && text.indexOf(target) >= 0)) {
                    ps[j].scrollIntoView({block: 'center'});
                    return {found: true};
                }
            }
        }
        return {found: false};
    }''', title)


def _get_case_coords(page, title):
    """Get fresh click coordinates for a case already scrolled into view."""
    return page.evaluate('''(title) => {
        var containers = document.querySelectorAll('.cl-container');
        var target = title.length > 60 ? title.substring(0, 60) : title;
        for (var i = 0; i < containers.length; i++) {
            var ps = containers[i].querySelectorAll('p');
            for (var j = 0; j < ps.length; j++) {
                var text = ps[j].textContent.trim();
                if (text === title || (target.length >= 20 && text.indexOf(target) >= 0)) {
                    var r = ps[j].getBoundingClientRect();
                    return {x: Math.round(r.x + 30), y: Math.round(r.y + r.height / 2)};
                }
            }
        }
        return null;
    }''', title)


def _maximize_per_page(page):
    """Change the per-page selector to the highest available option.

    QA Touch uses a vue-select per-page dropdown (default: 20).
    We click it open and select the largest option to show all cases at once.
    """
    # Check if per-page selector exists
    per_page = page.locator('.per-page-selector, .per-page-dd')
    if per_page.count() == 0:
        return False

    # Open the per-page dropdown
    per_page.first.click()
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
    coords = _get_case_coords(page, title)
    if not coords:
        print(f'    Could not get coordinates for case')
        return False

    page.mouse.click(coords['x'], coords['y'])
    time.sleep(4)
    return True


# ---------------------------------------------------------------------------
# Case Detail - Edit Form
# ---------------------------------------------------------------------------
def open_edit_form(page) -> bool:
    """On case detail page, click Edit to open the form. Returns True if form opened."""
    try:
        edit_btn = page.locator('button:has-text("Edit")')
        if edit_btn.first.is_visible(timeout=5000):
            edit_btn.first.click()
            time.sleep(3)
            return True
    except Exception:
        pass
    print('    Edit button not found')
    shot(page, 'no_edit_btn')
    return False


def save_and_close(page) -> bool:
    """Click Save, then Close on the case edit form."""
    save_btn = page.locator('button.save-continue-btn, button:has-text("Save")')
    if save_btn.count() > 0:
        save_btn.first.click()
        time.sleep(3)
        print('    Saved!')
    else:
        print('    Save button not found')
        shot(page, 'no_save_btn')
        page.keyboard.press('Escape')
        time.sleep(1)
        return False

    # Close
    close_btn = page.locator('button:has-text("Close")')
    if close_btn.count() > 0:
        close_btn.first.click()
        time.sleep(2)
    else:
        page.go_back()
        time.sleep(3)
    return True


def close_case_detail(page):
    """Close case detail without saving."""
    close_btn = page.locator('button:has-text("Close")')
    if close_btn.count() > 0:
        close_btn.first.click()
        time.sleep(2)
    else:
        page.go_back()
        time.sleep(3)


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

    # Open the New Tags vue-select
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
        time.sleep(1)
        print(f'    Tag "{tag_name}" created via Add New')
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

    # Find and click case
    if not find_and_click_case(page, title):
        report.add(key, 'not_found', f'Case not found in list')
        return False

    # Verify we're on detail page
    try:
        if not page.locator('button:has-text("Edit")').first.is_visible(timeout=5000):
            raise Exception('Edit not visible')
    except Exception:
        print(f'    Not on case detail page')
        shot(page, 'not_detail', key)
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
            enter_project(page)
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
            enter_project(page)

            for old_name, group in sorted(groups.items()):
                if limit and processed >= limit:
                    break

                # Refresh page every 20 operations to prevent stale DOM
                if processed > 0 and processed % 20 == 0:
                    print(f'\n  [Refreshing page after {processed} operations]')
                    page.reload()
                    time.sleep(5)
                    enter_project(page)

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
            enter_project(page)
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
                    enter_project(page)

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
# Command Dispatch
# ---------------------------------------------------------------------------
USAGE = """
QA Touch Browser Automation

Commands:
  set-mode          Set Mode=Automation on cases
  set-tags          Add tags to cases (comma-separated)
  set-type          Set Type on cases (Functional, Regression, Acceptance, etc.)
  set-priority      Set Priority on cases (Critical, High, Medium, Low)
  delete            Delete cases from QA Touch
  bulk-update       Apply multiple property changes from CSV
  rename-modules    Rename duplicate modules from CSV plan
  check-duplicates  Scan for duplicate module names (API, no browser)
  audit-steps       Sample cases and check step structure (browser)
  explore           Debug: screenshot every form tab for a case

Options:
  --csv FILE    CSV input (default: config/qatouch_set_automation_mode.csv)
  --cases K1 K2 Specific case keys (resolved via API)
  --limit N     Process only first N items (for testing)
  --dry-run     Preview without browser

Examples:
  python tools/qatouch_browser.py set-mode --cases LD3gmJ wmjgKb
  python tools/qatouch_browser.py set-tags SMOKE,SANITY --csv config/my_cases.csv
  python tools/qatouch_browser.py set-type Functional --cases LD3gmJ
  python tools/qatouch_browser.py bulk-update --csv config/bulk.csv
  python tools/qatouch_browser.py rename-modules --dry-run
  python tools/qatouch_browser.py rename-modules --limit 2
  python tools/qatouch_browser.py check-duplicates
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

    # Positional value (for set-tags, set-type, set-priority)
    value = args[0] if args else None

    return cmd, value, csv_file, case_keys, case_key_single, dry_run, limit


def main():
    cmd, value, csv_file, case_keys, case_key_single, dry_run, limit = _parse_args()

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
            enter_project(page)

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
