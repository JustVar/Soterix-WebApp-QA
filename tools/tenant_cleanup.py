#!/usr/bin/env python3
"""Delete the automation's leftover data from the shared QA tenant.

Targets ONLY names the suite itself creates (docs/TEST_REPAIRS.md row 7):

  - camera groups on the first site: "AutoTest Group *", "AutoTest Edited *",
    "Edited Group *", "2026*AutomationEdited *"
  - users whose card starts with "AutoTest" (the users tests' own name)

Anything else on the tenant is somebody's real data and is never touched.

    python tools/tenant_cleanup.py            # dry run: list what would go
    python tools/tenant_cleanup.py --apply    # delete it

Logs in fresh with QA_USER / QA_PASSWORD from .env (the same account the
tests use), headless. Every delete goes through the admin page object's
name-scoped helpers, so a list that is still filtering can never hand the
delete a stranger's row.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / '.env')

from playwright.sync_api import sync_playwright  # noqa: E402

from config.base_config import config  # noqa: E402

GROUP_PATTERNS = [
    re.compile(r'^AutoTest Group\b'),
    re.compile(r'^AutoTest Edited\b'),
    re.compile(r'^Edited Group\b'),
    re.compile(r'^2026.*AutomationEdited\b'),
]
USER_PATTERN = re.compile(r'^AutoTest\b')

# Each delete icon sits in a row with the group name; the nearest
# ancestor that carries text is that row, and its first line is the name.
GROUP_NAMES_JS = r"""() => [...document.querySelectorAll("img[alt='delete'].delete-icon")].map(icon => {
  let node = icon.parentElement;
  for (let i = 0; i < 4 && node; i++) {
    const text = (node.innerText || '').trim();
    if (text) return text.split(String.fromCharCode(10))[0].trim();
    node = node.parentElement;
  }
  return '';
}).filter(Boolean)"""


def _login(page):
    from tests.shared.pages.login_page import LoginPage
    LoginPage(page, config['base_url']).login(os.environ['QA_USER'],
                                             os.environ['QA_PASSWORD'])
    page.wait_for_function(
        "() => !window.location.href.includes('/auth/login')", timeout=60000)
    page.wait_for_load_state('domcontentloaded', timeout=30000)
    page.locator('text=Views').first.wait_for(state='visible', timeout=30000)


def _open_first_site(page, admin) -> str:
    """Same structural card locator the sites tests use."""
    headers = page.locator("*:has(> p.MuiTypography-root):has(img[alt='Options'])")
    headers.first.wait_for(state='visible', timeout=15000)
    name = headers.first.locator('p.MuiTypography-root').first.inner_text().strip()
    admin.click_site(name)
    return name


def _group_candidates(page) -> list[str]:
    names = page.evaluate(GROUP_NAMES_JS)
    return [n for n in names if any(p.match(n) for p in GROUP_PATTERNS)]


def _user_candidates(page, admin) -> list[str]:
    admin.search_user('AutoTest')
    # the filter has no completion signal; a bounded settle then a read
    page.wait_for_timeout(3000)
    cards = page.locator('.MuiPaper-root', has_text='AutoTest')
    names = []
    for i in range(cards.count()):
        first_line = cards.nth(i).inner_text().strip().split('\n')[0].strip()
        if USER_PATTERN.match(first_line):
            names.append(first_line)
    return sorted(set(names))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--apply', action='store_true',
                        help='delete the listed items (default: dry run)')
    args = parser.parse_args()

    from tests.shared.pages.admin_page import AdminPage

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        page = browser.new_context().new_page()
        _login(page)
        admin = AdminPage(page)

        # --- groups ---
        admin.navigate_to_admin()
        admin.navigate_to_sites()
        site = _open_first_site(page, admin)
        admin.open_groups_dropdown()
        all_groups = page.evaluate(GROUP_NAMES_JS)
        groups = _group_candidates(page)
        print(f'Site "{site}": {len(all_groups)} group(s) listed, '
              f'{len(groups)} automation leftover(s):')
        for name in groups:
            print(f'  group  {name}')
        if args.apply:
            for name in groups:
                admin.open_groups_dropdown()
                ok = admin.delete_camera_group_by_name(name)
                print(f'  {"deleted" if ok else "NOT FOUND"}  {name}')
            if groups:
                admin.open_groups_dropdown()
                left = _group_candidates(page)
                print(f'  remaining automation groups: {len(left)}')

        # --- users ---
        # the Groups dropdown is a MUI menu whose invisible backdrop
        # swallows clicks until it closes
        page.keyboard.press('Escape')
        page.locator('.MuiModal-backdrop').first.wait_for(state='hidden', timeout=5000)
        admin.navigate_to_users()
        users = _user_candidates(page, admin)
        print(f'Users: {len(users)} automation leftover(s):')
        for name in users:
            print(f'  user   {name}')
        if args.apply:
            for name in users:
                admin.delete_user(match_text=name)
                print(f'  deleted  {name}')

        browser.close()

    if not args.apply and (groups or users):
        print('\nDry run - nothing deleted. Re-run with --apply to delete the above.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
