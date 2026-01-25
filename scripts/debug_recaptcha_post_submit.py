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
    page = browser.new_page()
    page.goto(base)
    try:
        page.wait_for_load_state('networkidle', timeout=15000)
    except Exception:
        pass

    # Fill credentials
    try:
        page.locator('input[name="email"]').fill(email or '')
        page.locator('input[name="password"]').fill(password or '')
    except Exception as e:
        print('Fill error:', e)

    # Handle ReCAPTCHA
    print('Looking for ReCAPTCHA...')
    try:
        frame = page.frame_locator("iframe[title='reCAPTCHA']")
        anchor = frame.locator('#recaptcha-anchor')
        if anchor.count():
            print('Clicking ReCAPTCHA...')
            anchor.click()
            time.sleep(3)
            print('ReCAPTCHA clicked, waiting...')
        else:
            print('No reCAPTCHA anchor found')
    except Exception as e:
        print('ReCAPTCHA error:', e)

    # Click submit
    print('Clicking submit...')
    try:
        page.locator('button[type="submit"]').click()
    except Exception as e:
        print('Submit click error:', e)

    # Wait and observe
    print('Waiting for navigation...')
    time.sleep(10)

    try:
        print(f'Final URL: {page.url}')
    except Exception:
        pass
    try:
        print(f'Page title: {page.title()}')
    except Exception:
        pass

    # Check for error messages
    try:
        errors = page.locator('.error, [role="alert"], .MuiAlert-root')
        print('Errors count:', errors.count())
        for i in range(errors.count()):
            try:
                print('Error found:', errors.nth(i).inner_text())
            except Exception:
                pass
    except Exception as e:
        print('Error checking messages:', e)

    # Print cookies
    try:
        print('Cookies:', page.context.cookies())
    except Exception as e:
        print('Cookie read error:', e)

    # Leave browser open briefly for inspection
    print('Sleeping 5s before closing browser...')
    time.sleep(5)
    browser.close()
