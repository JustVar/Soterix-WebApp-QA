from playwright.sync_api import sync_playwright
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from tests.shared.pages.login_page import LoginPage
from dotenv import load_dotenv
import os

load_dotenv()

username = os.environ.get('QA_USER')
password = os.environ.get('QA_PASSWORD')
base = 'https://qa.example.invalid'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()
    lp = LoginPage(page, base)
    lp.login(username, password)
    page.wait_for_timeout(3000)
    print('Current URL after login:', page.url)

    queries = [
        'text=Logout',
        'button[aria-label="user-menu"]',
        'xpath=//*[@id="root"]/div/div/div/div[2]/div/div',
        'xpath=//*[@id="root"]/div/div[2]/div/div[3]/p'
    ]

    for q in queries:
        try:
            loc = page.locator(q)
            print(f"Selector {q}: count={loc.count()}")
            if loc.count():
                try:
                    print('  inner_text:', loc.first.inner_text())
                except Exception:
                    pass
                try:
                    print('  outer_html snippet:', loc.first.evaluate('el => el.outerHTML'))
                except Exception:
                    pass
        except Exception as e:
            print('Error querying', q, e)

    # print header area
    try:
        header = page.locator('header').first
        print('Header outerHTML len:', header.evaluate('el => el.outerHTML.length'))
    except Exception:
        pass

    browser.close()
