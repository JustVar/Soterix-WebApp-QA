from playwright.sync_api import sync_playwright
from dotenv import load_dotenv

load_dotenv()

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://qa.example.invalid/auth/login')
    page.wait_for_load_state('networkidle')

    # Fill invalid credentials and submit
    page.locator('input[name="email"]').fill('invalid@example.com')
    page.locator('input[name="password"]').fill('wrongpass')
    page.locator('button[type="submit"]').click()

    # Wait for potential server response/render
    page.wait_for_timeout(3000)

    # Print any elements under the form
    form = page.query_selector('form')
    if form:
        elems = form.query_selector_all('div, p, span, label')
        print(f'Found {len(elems)} elements under form:')
        for i, e in enumerate(elems):
            try:
                txt = e.inner_text().strip()
            except Exception:
                txt = None
            cls = e.get_attribute('class')
            id_ = e.get_attribute('id')
            print(f'Elem {i}: id={id_} class={cls} text={repr(txt)}')
    else:
        print('No form element found')

    # Look for any elements with error/alert classes
    error_elems = page.query_selector_all('div.error, div.alert, p.error-text, span.error, [role="alert"]')
    print(f'Found {len(error_elems)} error-class elements:')
    for i, e in enumerate(error_elems):
        try:
            txt = e.inner_text().strip()
        except Exception:
            txt = None
        print(f'ErrorElem {i}: class={e.get_attribute("class")} id={e.get_attribute("id")} text={repr(txt)}')

    # Generic text search for common words
    keywords = ['Invalid', 'invalid', 'required', 'Required', 'error', 'Error']
    for kw in keywords:
        hits = page.locator(f'text="{kw}"')
        if hits.count():
            print(f'Found text matches for {kw}: {hits.count()}')

    browser.close()
