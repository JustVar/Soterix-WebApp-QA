from playwright.sync_api import sync_playwright
from dotenv import load_dotenv
import os
import time

load_dotenv()

email = os.environ.get('QA_USER')
password = os.environ.get('QA_PASSWORD')
base = os.environ.get('BASE_URL', 'https://qa.example.invalid')

print(f"Using email={email} base={base}")

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto(base)
    try:
        page.wait_for_load_state('networkidle', timeout=15000)
    except Exception:
        pass

    # Fill and submit
    try:
        page.locator('input[name="email"]').fill(email or '')
        page.locator('input[name="password"]').fill(password or '')
    except Exception as e:
        print('Fill error:', e)

    # ReCAPTCHA
    try:
        frame = page.frame_locator("iframe[title='reCAPTCHA']")
        anchor = frame.locator('#recaptcha-anchor')
        if anchor.count():
            print('Clicking reCAPTCHA...')
            anchor.click()
            time.sleep(5)
        else:
            print('No reCAPTCHA anchor')
    except Exception as e:
        print('ReCAPTCHA error:', e)

    try:
        page.locator('button[type="submit"]').click()
    except Exception as e:
        print('Submit click error:', e)

    print('Waiting for login to complete...')
    time.sleep(15)

    try:
        print(f'Final URL: {page.url}')
    except Exception:
        pass

    try:
        cookies = context.cookies()
        print(f'\nTotal cookies: {len(cookies)}')
        for c in cookies:
            print(f"  {c.get('name')}: domain={c.get('domain')}, path={c.get('path')}, value={str(c.get('value'))[:20]}...")
    except Exception as e:
        print('Cookie read error:', e)

    try:
        ls = page.evaluate('() => JSON.stringify(localStorage)')
        print('\nlocalStorage:', (ls or '')[:1000])
    except Exception as e:
        print('localStorage read error:', e)

    try:
        ss = page.evaluate('() => JSON.stringify(sessionStorage)')
        print('\nsessionStorage:', (ss or '')[:1000])
    except Exception as e:
        print('sessionStorage read error:', e)

    # Save cookies to .session_cache for reuse
    try:
        import json
        jsession = None
        for c in cookies:
            if str(c.get('name','')).lower() == 'jsessionid':
                jsession = c
                break
        if jsession:
            # Capture localStorage object if available
            local_storage_obj = {}
            try:
                ls_obj = page.evaluate('() => Object.assign({}, localStorage)')
                local_storage_obj = ls_obj or {}
            except Exception:
                local_storage_obj = {}
            cache = {
                'token': jsession.get('value'),
                'base_url': base,
                'cookie': jsession,
                'localStorage': local_storage_obj
            }
            with open('.session_cache', 'w', encoding='utf-8') as f:
                json.dump(cache, f)
            print('\nSaved .session_cache with JSESSIONID and localStorage')
    except Exception as e:
        print('Failed to save session_cache:', e)

    print('Sleeping 3s before closing browser...')
    time.sleep(3)
    browser.close()
