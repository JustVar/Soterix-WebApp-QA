from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://qa.example.invalid')
    page.wait_for_load_state('networkidle')

    inputs = page.query_selector_all('input')
    print(f'Found {len(inputs)} input fields:')
    for i, inp in enumerate(inputs):
        print(f'Input {i}:')
        print(f'  id: {inp.get_attribute("id")}')
        print(f'  name: {inp.get_attribute("name")}')
        print(f'  type: {inp.get_attribute("type")}')
        print(f'  placeholder: {inp.get_attribute("placeholder")}')
        print(f'  aria-label: {inp.get_attribute("aria-label")}')
        print(f'  class: {inp.get_attribute("class")}')

    buttons = page.query_selector_all('button')
    print(f'\nFound {len(buttons)} buttons:')
    for i, btn in enumerate(buttons):
        print(f'Button {i}:')
        try:
            text = btn.inner_text()
        except Exception:
            text = None
        print(f'  text: {text}')
        print(f'  type: {btn.get_attribute("type")}')
        print(f'  class: {btn.get_attribute("class")}')

    browser.close()
