from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import json

load_dotenv()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    
    # Load cached auth
    page.goto('https://qa.example.invalid')
    try:
        page.wait_for_load_state('networkidle', timeout=10000)
    except Exception:
        pass
    
    cache_path = '.session_cache'
    if not os.path.exists(cache_path):
        print('.session_cache not found; run capture script first')
        browser.close()
        raise SystemExit(1)

    with open(cache_path, 'r', encoding='utf-8') as f:
        cache = json.load(f)

    # Inject cookie
    try:
        if 'cookie' in cache and isinstance(cache['cookie'], dict):
            context.add_cookies([cache['cookie']])
            print('Injected cookie:', cache['cookie'].get('name'))
    except Exception as e:
        print('Cookie injection error:', e)

    # Inject localStorage
    try:
        if 'localStorage' in cache and isinstance(cache['localStorage'], dict):
            for key, value in cache['localStorage'].items():
                if isinstance(value, (str, int, float, bool)):
                    v = str(value).replace("'", "\\'")
                    page.evaluate(f"localStorage.setItem('{key}', '{v}')")
            print('Injected localStorage items:', len(cache['localStorage']))
    except Exception as e:
        print('localStorage injection error:', e)

    page.reload()
    try:
        page.wait_for_timeout(5000)
    except Exception:
        pass
    
    print(f'URL: {page.url}')
    
    # Find potential logout/menu elements
    print('\nLooking for user menu / logout elements...')
    for text in ['Logout', 'Log out', 'Sign out', 'Profile', 'Account']:
        els = page.locator(f'text={text}').all()
        print(f'  text={text}: {len(els)} found')
    
    for selector in ['[aria-label*="user"]', '[aria-label*="menu"]', '[aria-label*="profile"]', '[aria-label*="account"]', 'button:has(svg)', '.MuiAvatar-root', '[data-testid*="user"]', '[data-testid*="menu"]']:
        try:
            els = page.locator(selector).all()
            print(f'  {selector}: {len(els)} found')
        except Exception as e:
            print(f'  {selector}: error {e}')

    print('\nAll buttons on page:')
    try:
        buttons = page.locator('button').all()
        for i, btn in enumerate(buttons[:20]):
            try:
                label = btn.get_attribute('aria-label') or ''
                text = btn.inner_text()[:60] if btn.inner_text() else ''
                print(f'  Button {i}: aria-label="{label}" text="{text}"')
            except Exception:
                print(f'  Button {i}: (could not read attributes)')
    except Exception as e:
        print('Buttons enumeration error:', e)

    input('Press Enter to close browser...')
    browser.close()
