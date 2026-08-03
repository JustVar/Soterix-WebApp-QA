"""Set Mode=Automation on QA Touch test cases via browser automation.

Reads case keys from qatouch_set_automation_mode.csv and sets Mode=Automation
on each case in QA Touch UI. Also handles deleting stub cases listed in
qatouch_stubs_to_delete.csv.

Usage:
    python tools/qatouch_set_mode.py                 # set Mode=Automation on all cases in CSV
    python tools/qatouch_set_mode.py --delete         # delete stub cases from CSV
    python tools/qatouch_set_mode.py --dry-run        # preview what would be done
    python tools/qatouch_set_mode.py --cases K1 K2    # set mode on specific case keys
"""
from __future__ import annotations

import csv
import functools
import os
import sys
import time

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

DOMAIN = 'soterixsystems'
PROJECT_KEY = 'JlW1'
BASE_URL = f'https://{DOMAIN}.qatouch.com'
AUTH_STATE_FILE = os.path.join(ROOT, 'tools', '.qatouch_auth_state.json')
SHOT_DIR = os.path.join(ROOT, 'tools', 'debug_screenshots')
AUTOMATION_CSV = os.path.join(ROOT, 'config', 'qatouch_set_automation_mode.csv')
DELETE_CSV = os.path.join(ROOT, 'config', 'qatouch_stubs_to_delete.csv')

os.makedirs(SHOT_DIR, exist_ok=True)


def shot(page, name):
    path = os.path.join(SHOT_DIR, f'{name}.png')
    page.screenshot(path=path, full_page=True)
    print(f'    [screenshot] {name}.png')


def wait_for_login(page, timeout=300):
    """Navigate to QA Touch and wait for manual login."""
    page.goto(f'{BASE_URL}/v2#/')
    print('\n' + '=' * 60)
    print('  BROWSER OPENED - Please log in to QA Touch')
    print('  Auth state will be saved for future runs.')
    print(f'  Timeout: {timeout}s')
    print('=' * 60)

    start = time.time()
    check_count = 0
    while time.time() - start < timeout:
        check_count += 1
        elapsed = int(time.time() - start)
        if check_count % 10 == 0:
            print(f'  ... waiting for login ({elapsed}s elapsed)')
        try:
            url = page.url or ''
            has_auth = any(x in url for x in [
                '/dashboard', '/project', '/testCase',
                '/modules', '/new-projects', '/case/list',
            ])
            if not has_auth:
                for sel in ['text="NexaiQ-Core"', 'text="Dashboard"',
                            'text="Project List"', 'text="Test Cases"']:
                    try:
                        if page.locator(sel).first.is_visible(timeout=300):
                            has_auth = True
                            break
                    except Exception:
                        pass
            if has_auth:
                print(f'>>> Login detected after {elapsed}s!')
                time.sleep(2)
                page.context.storage_state(path=AUTH_STATE_FILE)
                print(f'  Auth state saved to {AUTH_STATE_FILE}')
                return True
        except Exception:
            pass
        time.sleep(3)

    print('>>> Login timeout reached.')
    return False


def setup_browser(p, use_saved_auth=True):
    """Launch browser with optional saved auth state."""
    browser = p.chromium.launch(headless=False, slow_mo=200)

    if use_saved_auth and os.path.exists(AUTH_STATE_FILE):
        print('  Loading saved auth state...')
        context = browser.new_context(
            viewport={'width': 1400, 'height': 900},
            storage_state=AUTH_STATE_FILE,
        )
        page = context.new_page()
        page.goto(f'{BASE_URL}/v2#/new-projects')
        time.sleep(5)

        is_logged_in = False
        for sel in ['text="NexaiQ-Core"', 'text="Project List"', 'text="Dashboard"']:
            try:
                if page.locator(sel).first.is_visible(timeout=3000):
                    is_logged_in = True
                    break
            except Exception:
                pass

        if is_logged_in:
            print('  Auth state valid!')
            return browser, context, page
        print('  Auth state expired. Need fresh login.')
        context.close()

    context = browser.new_context(viewport={'width': 1400, 'height': 900})
    page = context.new_page()
    if not wait_for_login(page):
        browser.close()
        return None, None, None

    return browser, context, page


def enter_project(page):
    """Navigate into the NexaiQ-Core project."""
    page.goto(f'{BASE_URL}/v2#/new-projects')
    page.wait_for_load_state('networkidle')
    time.sleep(3)
    page.locator('text="NexaiQ-Core"').first.click()
    time.sleep(4)
    page.wait_for_load_state('networkidle')
    print('  Entered project.')


def navigate_to_module(page, module_name: str) -> bool:
    """Filter the module tree and click the target module."""
    filter_input = page.locator('input[placeholder="Type To Filter Module"]').first
    if filter_input.count() == 0:
        print('    Module filter input not found')
        return False

    # Use first 2-3 distinctive words for filtering
    import re
    clean_name = re.sub(r'[^A-Za-z0-9 ]', ' ', module_name).strip()
    words = clean_name.split()
    filter_text = ' '.join(words[:3]) if len(words) > 3 else clean_name

    filter_input.fill('')
    time.sleep(0.5)
    filter_input.fill(filter_text)
    time.sleep(3)

    # Click the module node using JS
    found = page.evaluate('''(modName) => {
        var target = modName.toLowerCase().trim();
        var nodes = document.querySelectorAll('.node-text.module_name_wrap');
        for (var i = 0; i < nodes.length; i++) {
            if (nodes[i].textContent.trim().toLowerCase() === target) {
                nodes[i].click();
                return true;
            }
        }
        // Partial match fallback
        for (var i = 0; i < nodes.length; i++) {
            if (nodes[i].textContent.trim().toLowerCase().indexOf(target) >= 0) {
                nodes[i].click();
                return true;
            }
        }
        return false;
    }''', module_name)

    if found:
        time.sleep(3)
        print(f'    Navigated to module: {module_name}')
    else:
        print(f'    Module not found: {module_name}')

    # Clear filter
    filter_input.fill('')
    time.sleep(1)

    return found


def find_and_click_case(page, case_title: str) -> bool:
    """Find a case by title in the case list and click to open it."""
    # Scroll to find the case and click it
    result = page.evaluate('''(title) => {
        var containers = document.querySelectorAll('.cl-container');
        for (var i = 0; i < containers.length; i++) {
            var ps = containers[i].querySelectorAll('p');
            for (var j = 0; j < ps.length; j++) {
                var text = ps[j].textContent.trim();
                if (text === title || text.indexOf(title.substring(0, 60)) >= 0) {
                    ps[j].scrollIntoView({block: 'center'});
                    return {
                        found: true,
                        x: Math.round(ps[j].getBoundingClientRect().x + 30),
                        y: Math.round(ps[j].getBoundingClientRect().y + ps[j].getBoundingClientRect().height / 2)
                    };
                }
            }
        }
        return {found: false};
    }''', case_title)

    if not result.get('found'):
        # Try scrolling down and searching again
        page.evaluate('window.scrollBy(0, 500)')
        time.sleep(2)
        result = page.evaluate('''(title) => {
            var containers = document.querySelectorAll('.cl-container');
            for (var i = 0; i < containers.length; i++) {
                var ps = containers[i].querySelectorAll('p');
                for (var j = 0; j < ps.length; j++) {
                    var text = ps[j].textContent.trim();
                    if (text === title || text.indexOf(title.substring(0, 60)) >= 0) {
                        ps[j].scrollIntoView({block: 'center'});
                        return {
                            found: true,
                            x: Math.round(ps[j].getBoundingClientRect().x + 30),
                            y: Math.round(ps[j].getBoundingClientRect().y + ps[j].getBoundingClientRect().height / 2)
                        };
                    }
                }
            }
            return {found: false};
        }''', case_title)

    if not result.get('found'):
        print(f'    Case not found in DOM: "{case_title[:60]}..."')
        return False

    time.sleep(1)
    # Get fresh coordinates after scroll
    coords = page.evaluate('''(title) => {
        var containers = document.querySelectorAll('.cl-container');
        for (var i = 0; i < containers.length; i++) {
            var ps = containers[i].querySelectorAll('p');
            for (var j = 0; j < ps.length; j++) {
                var text = ps[j].textContent.trim();
                if (text === title || text.indexOf(title.substring(0, 60)) >= 0) {
                    var r = ps[j].getBoundingClientRect();
                    return {x: Math.round(r.x + 30), y: Math.round(r.y + r.height / 2)};
                }
            }
        }
        return null;
    }''', case_title)

    if coords:
        page.mouse.click(coords['x'], coords['y'])
        time.sleep(4)
    return True


def set_mode_automation(page) -> bool:
    """On the case detail page, click Edit and set Mode to Automation."""
    # Click Edit button
    edit_btn = page.locator('button:has-text("Edit")')
    if edit_btn.count() == 0:
        print('    Edit button not found on case page')
        return False

    edit_btn.first.click()
    time.sleep(3)

    # Find the Mode dropdown - look for a select or dropdown near "Mode" label
    # QA Touch uses custom dropdowns, not standard <select>
    mode_set = page.evaluate('''() => {
        // Strategy 1: Find label "Mode" and click its sibling dropdown
        var labels = document.querySelectorAll('label, .form-label, span, p');
        for (var i = 0; i < labels.length; i++) {
            if (labels[i].textContent.trim() === 'Mode' ||
                labels[i].textContent.trim() === 'Mode:') {
                // Look for nearby select/dropdown
                var parent = labels[i].closest('.form-group, .row, div');
                if (parent) {
                    var select = parent.querySelector('select, [role="listbox"], .vs__dropdown-toggle, .multiselect, .dropdown-toggle');
                    if (select) {
                        select.click();
                        return {found: true, type: 'select'};
                    }
                    // Vue-select style
                    var vselect = parent.querySelector('.vs__search, input[role="combobox"]');
                    if (vselect) {
                        vselect.click();
                        return {found: true, type: 'vselect'};
                    }
                }
            }
        }
        // Strategy 2: Find any element containing current mode text "Manual"
        var elems = document.querySelectorAll('.vs__selected, .multiselect__single, option[selected]');
        for (var i = 0; i < elems.length; i++) {
            if (elems[i].textContent.trim() === 'Manual') {
                elems[i].closest('.vs__dropdown-toggle, .multiselect, select')?.click();
                return {found: true, type: 'current-value'};
            }
        }
        return {found: false};
    }''')

    if not mode_set.get('found'):
        # Fallback: look for any dropdown that shows "Manual" and click it
        manual_elem = page.locator('text="Manual"')
        if manual_elem.count() > 0:
            # Click the parent dropdown area
            manual_elem.first.click()
            time.sleep(1)
        else:
            print('    Mode dropdown not found')
            shot(page, 'mode_not_found')
            # Press Escape to close edit form
            page.keyboard.press('Escape')
            time.sleep(1)
            return False

    time.sleep(2)

    # Now select "Automation" from the dropdown options
    automation_selected = page.evaluate('''() => {
        // Strategy 1: Click option text
        var options = document.querySelectorAll(
            '.vs__dropdown-option, .multiselect__option, option, li[role="option"], .dropdown-item'
        );
        for (var i = 0; i < options.length; i++) {
            var text = options[i].textContent.trim();
            if (text === 'Automation' || text === 'automation') {
                options[i].click();
                return true;
            }
        }
        // Strategy 2: Look in visible list items
        var items = document.querySelectorAll('li, div[class*="option"]');
        for (var i = 0; i < items.length; i++) {
            if (items[i].textContent.trim() === 'Automation') {
                items[i].click();
                return true;
            }
        }
        return false;
    }''')

    if not automation_selected:
        # Try Playwright locator
        auto_option = page.locator('text="Automation"')
        if auto_option.count() > 0:
            auto_option.first.click()
            automation_selected = True
            time.sleep(1)

    if not automation_selected:
        print('    "Automation" option not found in dropdown')
        shot(page, 'automation_option_not_found')
        page.keyboard.press('Escape')
        time.sleep(1)
        return False

    time.sleep(1)

    # Click Save
    save_btn = page.locator('button.save-continue-btn, button:has-text("Save")')
    if save_btn.count() > 0:
        save_btn.first.click()
        time.sleep(3)
        print('    Mode set to Automation and saved!')
    else:
        print('    Save button not found')
        shot(page, 'save_not_found')
        return False

    return True


def close_case_detail(page):
    """Close the case detail view and return to the case list."""
    close_btn = page.locator('button:has-text("Close")')
    if close_btn.count() > 0:
        close_btn.first.click()
        time.sleep(2)
    else:
        # Try back navigation
        page.go_back()
        time.sleep(3)


def load_automation_csv() -> list[dict]:
    """Load the cases that need Mode=Automation from CSV."""
    if not os.path.exists(AUTOMATION_CSV):
        print(f'  CSV not found: {AUTOMATION_CSV}')
        return []
    cases = []
    with open(AUTOMATION_CSV, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cases.append(row)
    return cases


def load_delete_csv() -> list[str]:
    """Load stub case keys to delete from CSV."""
    if not os.path.exists(DELETE_CSV):
        return []
    keys = []
    with open(DELETE_CSV, encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            keys.append(row['stub_case_key'])
    return keys


def cmd_set_mode(dry_run=False, specific_keys=None):
    """Set Mode=Automation on all cases in the CSV."""
    cases = load_automation_csv()
    if specific_keys:
        cases = [c for c in cases if c['case_key'] in specific_keys]

    if not cases:
        print('No cases to process.')
        return

    print(f'\n{"=" * 60}')
    print('  QA Touch Mode=Automation Setter')
    print(f'  Cases to process: {len(cases)}')
    print(f'{"=" * 60}')

    for c in cases:
        print(f'  [{c["case_key"]}] ({c["module"]}) {c["case_title"][:60]}')

    if dry_run:
        print('\n  DRY RUN - no changes made.')
        return

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser, context, page = setup_browser(p)
        if not browser:
            print('  Failed to set up browser.')
            return

        try:
            enter_project(page)

            # Group cases by module to minimize navigation
            by_module: dict[str, list[dict]] = {}
            for c in cases:
                by_module.setdefault(c['module'], []).append(c)

            success = 0
            failed = 0

            for module, module_cases in by_module.items():
                print(f'\n  Module: {module} ({len(module_cases)} cases)')

                if not navigate_to_module(page, module):
                    print('    SKIP - could not navigate to module')
                    failed += len(module_cases)
                    continue

                for case in module_cases:
                    title = case['case_title']
                    key = case['case_key']
                    print(f'\n  Processing [{key}]: "{title[:60]}..."')

                    if not find_and_click_case(page, title):
                        print('    FAILED - case not found in list')
                        failed += 1
                        # Re-navigate to module
                        navigate_to_module(page, module)
                        continue

                    # Check if we're on the case detail page
                    edit_visible = False
                    try:
                        edit_visible = page.locator('button:has-text("Edit")').first.is_visible(timeout=5000)
                    except Exception:
                        pass

                    if not edit_visible:
                        print('    FAILED - not on case detail page')
                        shot(page, f'not_detail_{key}')
                        failed += 1
                        enter_project(page)
                        navigate_to_module(page, module)
                        continue

                    if set_mode_automation(page):
                        success += 1
                    else:
                        failed += 1

                    close_case_detail(page)
                    time.sleep(2)

            print(f'\n{"=" * 60}')
            print('  RESULTS')
            print(f'  Success: {success}')
            print(f'  Failed:  {failed}')
            print(f'{"=" * 60}')

        finally:
            context.storage_state(path=AUTH_STATE_FILE)
            browser.close()


def cmd_delete(dry_run=False):
    """Delete stub cases from QA Touch UI."""
    keys = load_delete_csv()
    if not keys:
        print('No stubs to delete.')
        return

    # Get titles for the keys
    client = QATouchClient()
    all_cases = client.list_all_test_cases(PROJECT_KEY)
    case_by_key = {c['case_key']: c for c in all_cases}

    found = []
    not_found = []
    for key in keys:
        case = case_by_key.get(key)
        if case:
            found.append(case)
        else:
            not_found.append(key)

    print(f'\n{"=" * 60}')
    print('  QA Touch Stub Deletion')
    print(f'  Cases to delete: {len(found)}')
    if not_found:
        print(f'  Already deleted: {len(not_found)} ({", ".join(not_found)})')
    print(f'{"=" * 60}')

    for c in found:
        print(f'  [{c["case_key"]}] ({c.get("module name", "?")}) {c["case_title"][:60]}')

    if dry_run:
        print('\n  DRY RUN - no deletions.')
        return

    if not found:
        print('  Nothing to delete - all stubs already removed.')
        return

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser, context, page = setup_browser(p)
        if not browser:
            return

        try:
            enter_project(page)

            # Group by module
            by_module: dict[str, list[dict]] = {}
            for c in found:
                mod = c.get('module name', 'Unknown')
                by_module.setdefault(mod, []).append(c)

            success = 0
            failed = 0

            for module, module_cases in by_module.items():
                print(f'\n  Module: {module} ({len(module_cases)} cases)')

                if not navigate_to_module(page, module):
                    failed += len(module_cases)
                    continue

                for case in module_cases:
                    title = case['case_title']
                    key = case['case_key']
                    print(f'\n  Deleting [{key}]: "{title[:60]}..."')

                    # Find the delete icon in the case row
                    deleted = page.evaluate('''(title) => {
                        var containers = document.querySelectorAll('.cl-container');
                        for (var i = 0; i < containers.length; i++) {
                            var ps = containers[i].querySelectorAll('p');
                            for (var j = 0; j < ps.length; j++) {
                                if (ps[j].textContent.trim().indexOf(title.substring(0, 50)) >= 0) {
                                    // Find delete icon in this row
                                    var deleteBtn = containers[i].querySelector('[title="Delete"], .fa-trash, .delete-icon, svg[data-icon="trash"]');
                                    if (deleteBtn) {
                                        deleteBtn.click();
                                        return 'clicked';
                                    }
                                    return 'no-delete-btn';
                                }
                            }
                        }
                        return 'not-found';
                    }''', title)

                    if deleted == 'clicked':
                        time.sleep(2)
                        # Confirm deletion dialog
                        confirm = page.locator('button:has-text("Yes"), button:has-text("Delete"), button:has-text("Confirm")')
                        if confirm.count() > 0:
                            confirm.first.click()
                            time.sleep(2)
                            print('    Deleted!')
                            success += 1
                        else:
                            print('    Confirmation dialog not found')
                            shot(page, f'delete_confirm_{key}')
                            failed += 1
                    else:
                        print(f'    Could not delete: {deleted}')
                        failed += 1

            print(f'\n{"=" * 60}')
            print('  RESULTS')
            print(f'  Deleted:  {success}')
            print(f'  Failed:   {failed}')
            print(f'{"=" * 60}')

        finally:
            context.storage_state(path=AUTH_STATE_FILE)
            browser.close()


def main():
    import argparse
    parser = argparse.ArgumentParser(description='QA Touch Mode/Delete automation')
    parser.add_argument('--delete', action='store_true', help='Delete stub cases instead of setting mode')
    parser.add_argument('--dry-run', action='store_true', help='Preview only, no changes')
    parser.add_argument('--cases', nargs='*', help='Specific case keys to process')
    args = parser.parse_args()

    if args.delete:
        cmd_delete(dry_run=args.dry_run)
    else:
        cmd_set_mode(dry_run=args.dry_run, specific_keys=args.cases)


if __name__ == '__main__':
    main()
