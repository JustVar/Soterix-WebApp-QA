#!/usr/bin/env python3
"""Delete the automation's leftover data from the shared QA tenant.

Targets ONLY names the suite itself creates (docs/TEST_REPAIRS.md row 7):

  - camera groups on the first site: "AutoTest Group *", "AutoTest Edited *",
    "Edited Group *", "2026*AutomationEdited *"
  - users whose card starts with "AutoTest" (the users tests' own name)

Anything else on the tenant is somebody's real data and is never touched.

    python tools/tenant_cleanup.py            # dry run: list what would go
    python tools/tenant_cleanup.py --apply    # delete it

Channels (Admin > Integrations > Channels) are a separate errand: they
are never matched by pattern, only by the exact names passed on the
command line, and a run with --delete-channel does just that step.

    python tools/tenant_cleanup.py --delete-channel 123 --delete-channel Google
    python tools/tenant_cleanup.py --apply --delete-channel 123

BOX picks the account, so BOX picks the TENANT this deletes from:

    BOX=us python tools/tenant_cleanup.py --apply

It logs in headless as the active box's account and prints that address
and the site before it lists anything - read those two lines before you
pass --apply. Reading QA_USER directly sent every run to the default box
whatever BOX said, so `BOX=us ... --apply` would have deleted from India
(register item 30; item 23 was the same defect in explore_app.py).

The site is the box's configured test_site_name, not whichever card the
Sites page happens to list first. Every delete goes through the admin
page object's name-scoped helpers, so a list that is still filtering can
never hand the delete a stranger's row.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / '.env')

from playwright.sync_api import sync_playwright  # noqa: E402

from config.base_config import config, get_credentials  # noqa: E402

GROUP_PATTERNS = [
    re.compile(r'^AutoTest Group\b'),
    re.compile(r'^AutoTest Edited\b'),
    re.compile(r'^Edited Group\b'),
    re.compile(r'^2026.*AutomationEdited\b'),
]
USER_PATTERN = re.compile(r'^AutoTest\b')
# The user cards repeat one display name, so the e-mail is the identity
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

# A channel card is the grid item around its three-dots icon; the name
# is its p.textEllipsis and the url its p.lineClampTwoLine (probed
# 08/25, see _open_channels).
CHANNEL_ICON = "img.dropdown-toggle[src*='three-dots']"
CHANNEL_CARDS_JS = r"""() => [...document.querySelectorAll("img.dropdown-toggle[src*='three-dots']")].map(icon => {
  const card = icon.closest('.MuiGrid-item');
  const name = card && card.querySelector('p.textEllipsis');
  const url = card && card.querySelector('p.lineClampTwoLine');
  return [name ? name.textContent.trim() : '', url ? url.textContent.trim() : ''];
})"""

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


def active_account() -> tuple[str, str]:
    """The active box's account, falling back to the default one.

    A destructive tool must never guess its tenant. get_credentials()
    reads the box BOX names; the QA_USER fallback keeps a config with no
    box definitions working.
    """
    try:
        creds = get_credentials()
    except (KeyError, RuntimeError):
        creds = {}
    user = creds.get('email') or os.environ.get('QA_USER', '')
    password = creds.get('password') or os.environ.get('QA_PASSWORD', '')
    if not user or not password:
        raise SystemExit(
            'No account for this box. Set the box variables it names in '
            '.env (see config/env/), or QA_USER / QA_PASSWORD.'
        )
    return user, password


def _login(page):
    from tests.shared.pages.login_page import LoginPage
    user, password = active_account()
    box = os.environ.get('BOX', '').strip().lower() or config.get('default_box', '')
    print(f'Tenant:  box={box or "(default)"}  account={user}')
    LoginPage(page, config['base_url']).login(user, password)
    page.wait_for_function(
        "() => !window.location.href.includes('/auth/login')", timeout=60000)
    page.wait_for_load_state('domcontentloaded', timeout=30000)
    page.locator('text=Views').first.wait_for(state='visible', timeout=30000)


def _open_configured_site(page, admin) -> str:
    """Open the box's configured site, or say which sites ARE listed.

    Taking the first card meant a multi-site tenant got its groups
    cleaned on whichever site the page happened to list first - the
    same silent first-match this repo has repaired elsewhere. A
    destructive tool names its target (register item 30).
    """
    headers = page.locator("*:has(> p.MuiTypography-root):has(img[alt='Options'])")
    headers.first.wait_for(state='visible', timeout=15000)
    listed = page.evaluate(
        """() => [...document.querySelectorAll("*:has(> p.MuiTypography-root):has(img[alt='Options'])")]
             .map(h => (h.querySelector('p.MuiTypography-root')?.innerText || '').trim())
             .filter(Boolean)"""
    )
    name = config.get('test_site_name') or ''
    if not name:
        raise SystemExit(
            'test_site_name is not set for this box in config/env/, so this '
            f'run has no site to clean. Sites on the tenant: {listed}'
        )
    if name not in listed:
        raise SystemExit(
            f'The configured site {name!r} is not on the Sites page. '
            f'Sites listed: {listed}. Either BOX names the wrong tenant or '
            f'test_site_name is stale in config/env/.'
        )
    admin.click_site(name)
    return name


def _group_candidates(page) -> list[str]:
    names = page.evaluate(GROUP_NAMES_JS)
    return [n for n in names if any(p.match(n) for p in GROUP_PATTERNS)]


def _user_candidates(page, admin) -> list[str]:
    """The automation's leftover users, identified by e-mail.

    Returns e-mails, not names: every user the suite makes is called
    "AutoTest Playwright", so a name identifies the whole set and could
    hand a delete the wrong row. The e-mail carries the run stamp and
    is unique per user.

    The old reader read only the card's FIRST line and matched it
    against ^AutoTest. That line is the avatar's initials ("AP"), so it
    matched nothing and the tool reported "0 automation leftover(s)"
    with ten of them on screen (measured 09/04/2026). A cleanup tool
    that under-reports is worse than one that does not run: it makes
    the leak look fixed.
    """
    admin.search_user('AutoTest')
    # the filter has no completion signal; a bounded settle then a read
    page.wait_for_timeout(3000)
    cards = page.locator('.MuiPaper-root', has_text='AutoTest')
    found = []
    for i in range(cards.count()):
        email = user_email_from_card(cards.nth(i).inner_text())
        if email:
            found.append(email)
    return sorted(set(found))


def user_email_from_card(card_text: str) -> str | None:
    """The e-mail of an automation user card, or None if it is not one.

    Pure, so it can be pinned without a browser. A card reads
    "AP / AutoTest Playwright / Remote User / Supervisor / <e-mail>":
    the name is NOT on the first line, which is exactly what the old
    first-line-only check tripped over.
    """
    lines = [ln.strip() for ln in (card_text or '').split('\n')]
    if not any(USER_PATTERN.match(ln) for ln in lines):
        return None
    for ln in lines:
        if EMAIL_RE.match(ln):
            return ln
    return None


def _open_channels(page, admin):
    """Admin > Integrations > Channels card > View; waits for the list.

    Page facts (headless probe, 08/25/2026):
      - the Integrations tab shows three .MuiPaper-root cards (Webhooks,
        Channels, API Integration), each with a "View" MUI button; the
        channel list is behind the Channels card's View
      - the list is a MUI grid: one .MuiGrid-item per channel holding a
        thumbnail, img.dropdown-toggle[src*='three-dots'] (alt is
        empty), the name in p.textEllipsis and the url in
        p.lineClampTwoLine (may be empty)
      - the three-dots click opens div.dropdown-box - a plain box, no
        menu role - with two div.MuiStack-root items, Edit and Delete
        (img[alt='delete Icon'] src*='delete-icon'); one box at a time
      - Delete opens .MuiModal-root titled "Delete Channel" ("Are you
        sure you want to delete this channel? This action cannot be
        undone.") with Cancel and Delete buttons; a hidden "Deleting..."
        progress block sits in the same modal
    """
    admin.navigate_to_admin()
    page.get_by_text('Integrations', exact=True).first.click()
    card = page.locator('.MuiPaper-root', has_text='Channels').first
    card.get_by_role('button', name='View').first.click()
    # the Add button is the signal the list view rendered; the cards
    # follow from a fetch, so an empty list only shows after the wait
    page.locator('button.add-btn', has_text='Add New Channel').wait_for(
        state='visible', timeout=15000)
    with contextlib.suppress(Exception):
        page.locator(CHANNEL_ICON).first.wait_for(state='visible', timeout=15000)
    page.wait_for_timeout(1000)


def _channels(page) -> list[tuple[str, str]]:
    return [tuple(c) for c in page.evaluate(CHANNEL_CARDS_JS)]


def _channel_count(page, name: str) -> int:
    return sum(1 for n, _ in _channels(page) if n == name)


def _delete_channel(page, name: str) -> bool:
    """Delete one card whose name is exactly `name`; False when absent.

    The icon is scoped to that card, so the one dropdown-box that opens
    belongs to it; the row leaving the grid is the success signal.
    """
    before = _channel_count(page, name)
    if not before:
        return False
    exact = re.compile(rf'^{re.escape(name)}$')
    card = page.locator('.MuiGrid-item',
                        has=page.locator('p.textEllipsis', has_text=exact)).first
    card.locator(CHANNEL_ICON).click()
    menu = page.locator('.dropdown-box')
    menu.first.wait_for(state='visible', timeout=5000)
    if menu.count() != 1:
        raise RuntimeError(f'{menu.count()} channel menus open; expected 1')
    menu.locator('div.MuiStack-root', has_text='Delete').click()
    modal = page.locator('.MuiModal-root', has_text='Delete Channel')
    modal.wait_for(state='visible', timeout=5000)
    modal.locator("button:text-is('Delete')").click()
    modal.wait_for(state='hidden', timeout=15000)
    page.wait_for_function(
        "([name, n]) => [...document.querySelectorAll('.MuiGrid-item p.textEllipsis')]"
        ".filter(p => p.textContent.trim() === name).length < n",
        arg=[name, before], timeout=15000)
    return True


def _channels_step(page, admin, names: list[str], apply: bool) -> None:
    _open_channels(page, admin)
    listed = _channels(page)
    print(f'Channels: {len(listed)} listed:')
    for n, url in listed:
        print(f'  channel  {n}  {url}')
    for name in names:
        count = _channel_count(page, name)
        state = f'present x{count}' if count else 'not present'
        print(f'  requested  {name}: {state}')
    if not apply:
        return
    for name in names:
        # duplicates share a name; each pass takes one card
        while _delete_channel(page, name):
            print(f'  deleted  {name}')
    print(f'  remaining: {[n for n, _ in _channels(page)]}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--apply', action='store_true',
                        help='delete the listed items (default: dry run)')
    parser.add_argument('--delete-channel', action='append', default=[],
                        metavar='NAME',
                        help='delete the channel with exactly this name '
                             '(repeatable); the run does only the channels step')
    args = parser.parse_args()

    from tests.shared.pages.admin_page import AdminPage

    with sync_playwright() as p:
        browser = p.chromium.launch(channel='chrome', headless=True)
        page = browser.new_context().new_page()
        _login(page)
        admin = AdminPage(page)

        if args.delete_channel:
            _channels_step(page, admin, args.delete_channel, args.apply)
            browser.close()
            if not args.apply:
                print('\nDry run - nothing deleted. Re-run with --apply to delete.')
            return 0

        # --- groups ---
        admin.navigate_to_admin()
        admin.navigate_to_sites()
        site = _open_configured_site(page, admin)
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
        if users and not args.apply:
            print('  NOTE: the tenant refuses these deletes (register item '
                  '11); expect them to survive --apply until the app fix.')
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
