"""QA Touch browser automation - set Mode, Tags, Type, Priority; delete cases.

Replaces qatouch_set_mode.py with robust infinite-scroll handling, auth refresh,
multi-tab form navigation, and tag management.

Usage:
  python tools/qatouch_browser.py set-mode   [--csv FILE] [--cases K1 K2] [--dry-run]
  python tools/qatouch_browser.py set-tags   TAG1,TAG2 [--csv FILE] [--cases K1 K2] [--dry-run]
  python tools/qatouch_browser.py set-type   TYPE [--csv FILE] [--cases K1 K2] [--dry-run]
  python tools/qatouch_browser.py set-priority PRI [--csv FILE] [--cases K1 K2] [--dry-run]
  python tools/qatouch_browser.py delete     [--csv FILE] [--cases K1 K2] [--dry-run]
  python tools/qatouch_browser.py bulk-update --csv FILE [--dry-run]
  python tools/qatouch_browser.py explore    --case CASE_KEY
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

    clean = re.sub(r'[^A-Za-z0-9 ]', ' ', module_name).strip()
    words = clean.split()
    filter_text = ' '.join(words[:3]) if len(words) > 3 else clean

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

    clean = re.sub(r'[^A-Za-z0-9 ]', ' ', module_name).strip()
    words = clean.split()
    filter_text = ' '.join(words[:3]) if len(words) > 3 else clean

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

    filt.fill('')
    time.sleep(0.5)
    return count


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
    """Read tag chips currently applied on the edit form."""
    tags = page.evaluate('''() => {
        var result = [];
        // Find the "Tags" label (not "New Tags")
        var labels = document.querySelectorAll('label, .form-label, span');
        var tagSection = null;
        for (var i = 0; i < labels.length; i++) {
            var t = labels[i].textContent.trim();
            if (t === 'Tags') {
                // Make sure it's not preceded by "New"
                var prev = labels[i].previousElementSibling;
                if (prev && prev.textContent.trim().toLowerCase().includes('new')) continue;
                tagSection = labels[i].closest('.form-group, .row, .col, div');
                break;
            }
        }
        if (!tagSection) return result;
        // Read chip text from vue-select selected items
        var chips = tagSection.querySelectorAll(
            '.vs__selected, .multiselect__tag, [class*="tag-chip"], span[class*="badge"]'
        );
        chips.forEach(function(c) {
            var text = c.textContent.replace(/[x\\u00d7\\u2715]/gi, '').trim();
            if (text && text.length > 0 && text !== 'Select Tags') {
                result.push(text.toUpperCase());
            }
        });
        return result;
    }''')
    return tags or []


def add_tag(page, tag_name: str) -> bool:
    """Add a single tag to the case via the Tags dropdown.

    1. Open the Tags vue-select dropdown
    2. Type tag name to filter
    3. Click matching option
    4. If no option, try the New Tags section
    """
    tag_upper = tag_name.upper()

    # Check if already present
    existing = get_existing_tags(page)
    if tag_upper in [t.upper() for t in existing]:
        print(f'    Tag "{tag_name}" already present')
        return True

    # Open the Tags dropdown - find the first "Select Tags" placeholder
    # that is NOT inside the "New Tags" section
    opened = page.evaluate('''(tagName) => {
        var labels = document.querySelectorAll('label, .form-label, span');
        for (var i = 0; i < labels.length; i++) {
            var t = labels[i].textContent.trim();
            if (t === 'Tags') {
                var prev = labels[i].previousElementSibling;
                if (prev && prev.textContent.trim().toLowerCase().includes('new')) continue;
                var section = labels[i].closest('.form-group, .row, .col, div');
                if (!section) continue;
                // Find and click the vue-select input
                var trigger = section.querySelector('.vs__dropdown-toggle, [role="combobox"]');
                if (trigger) { trigger.click(); return true; }
                var input = section.querySelector('.vs__search, input[type="search"], input[type="text"]');
                if (input) { input.click(); return true; }
            }
        }
        return false;
    }''', tag_name)

    if not opened:
        print(f'    Tags dropdown not found')
        shot(page, 'tags_dropdown_not_found')
        return False

    time.sleep(1)

    # Type to filter
    search_input = page.locator('.vs__search:visible, input[role="combobox"]:visible').first
    try:
        search_input.fill(tag_name)
        time.sleep(1.5)
    except Exception:
        # Try typing directly
        page.keyboard.type(tag_name, delay=100)
        time.sleep(1.5)

    # Click matching option
    option_found = page.evaluate('''(tagName) => {
        var upper = tagName.toUpperCase();
        var options = document.querySelectorAll(
            '.vs__dropdown-option, .multiselect__option, li[role="option"]'
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

    if option_found:
        print(f'    Tag "{tag_name}" added via dropdown')
        time.sleep(0.5)
        return True

    # Close dropdown with Escape, try New Tags section
    page.keyboard.press('Escape')
    time.sleep(0.5)
    return _add_new_tag(page, tag_name)


def _add_new_tag(page, tag_name: str) -> bool:
    """Add a tag via the 'New Tags' section + 'Add New' button."""
    print(f'    Tag "{tag_name}" not in existing tags, trying New Tags...')

    # Find the New Tags section
    new_tag_opened = page.evaluate('''(tagName) => {
        var labels = document.querySelectorAll('label, .form-label, span');
        for (var i = 0; i < labels.length; i++) {
            var t = labels[i].textContent.trim();
            if (t === 'New Tags') {
                var section = labels[i].closest('.form-group, .row, .col, div');
                if (!section) continue;
                var input = section.querySelector('input, .vs__search, [type="text"]');
                if (input) { input.click(); input.value = ''; return true; }
            }
        }
        return false;
    }''', tag_name)

    if not new_tag_opened:
        print(f'    New Tags input not found')
        return False

    time.sleep(0.5)
    page.keyboard.type(tag_name, delay=100)
    time.sleep(1)

    # Click "Add New" button
    add_btn = page.locator('button:has-text("Add New")')
    if add_btn.count() > 0:
        add_btn.first.click()
        time.sleep(1)
        print(f'    Tag "{tag_name}" created via New Tags')
        return True

    print(f'    "Add New" button not found')
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
# Command Dispatch
# ---------------------------------------------------------------------------
USAGE = """
QA Touch Browser Automation

Commands:
  set-mode      Set Mode=Automation on cases
  set-tags      Add tags to cases (comma-separated)
  set-type      Set Type on cases (Functional, Regression, Acceptance, etc.)
  set-priority  Set Priority on cases (Critical, High, Medium, Low)
  delete        Delete cases from QA Touch
  bulk-update   Apply multiple property changes from CSV
  explore       Debug: screenshot every form tab for a case

Options:
  --csv FILE    CSV input (default: config/qatouch_set_automation_mode.csv)
  --cases K1 K2 Specific case keys (resolved via API)
  --dry-run     Preview without browser

Examples:
  python tools/qatouch_browser.py set-mode --cases LD3gmJ wmjgKb
  python tools/qatouch_browser.py set-tags SMOKE,SANITY --csv config/my_cases.csv
  python tools/qatouch_browser.py set-type Functional --cases LD3gmJ
  python tools/qatouch_browser.py bulk-update --csv config/bulk.csv
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

    # Positional value (for set-tags, set-type, set-priority)
    value = args[0] if args else None

    return cmd, value, csv_file, case_keys, case_key_single, dry_run


def main():
    cmd, value, csv_file, case_keys, case_key_single, dry_run = _parse_args()

    if cmd == 'explore':
        if not case_key_single and case_keys:
            case_key_single = case_keys[0]
        if not case_key_single:
            print('  explore requires --case CASE_KEY')
            return
        cmd_explore(case_key_single)
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
