from playwright.sync_api import sync_playwright
import sys
import os
# Ensure project root is on sys.path so local packages (config, tests, etc.) import correctly
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from config.base_config import config
import time


def find_and_fill(page, selectors, value):
    for sel in selectors:
        try:
            if page.locator(sel).count():
                page.locator(sel).fill(value)
                return True
        except Exception:
            continue
    return False


def main():
    env = os.environ.get("ENV", "qa")
    print("ENV:", env)
    base_url = config.get("base_url")
    print("base_url:", base_url)

    username = os.environ.get("AUTO_USER")
    password = os.environ.get("AUTO_PASSWORD")
    if not username or not password:
        raise SystemExit("AUTO_USER/AUTO_PASSWORD must be set in environment")

    app_type = os.environ.get("APP_TYPE", "customer")
    login_path = "/login" if app_type == "partner" else "/auth/login"
    login_url = base_url.rstrip("/") + login_path

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 900})
        page = context.new_page()
        print("Navigating to", login_url)
        page.goto(login_url)

        # fill username
        filled = find_and_fill(page, ["input[name='email']", "input[type='email']", "[placeholder*='Email']", "[placeholder*='Username']"], username)
        # fill password
        filled_pw = find_and_fill(page, ["input[name='password']", "input[type='password']", "[placeholder*='Password']"], password)

        # handle reCAPTCHA (best-effort)
        try:
            frame_loc = page.frame_locator("iframe[title='reCAPTCHA']")
            anchor = frame_loc.locator("#recaptcha-anchor")
            if anchor.count():
                try:
                    anchor.wait_for(state="visible", timeout=5000)
                    anchor.click()
                except Exception:
                    try:
                        anchor.click(timeout=2000)
                    except Exception:
                        pass

                try:
                    page.wait_for_function(
                        "() => document.querySelector('textarea.g-recaptcha-response') && document.querySelector('textarea.g-recaptcha-response').value.length > 0",
                        timeout=10000,
                    )
                except Exception:
                    pass
        except Exception:
            pass

        # click submit
        try:
            if page.locator("button[type='submit']").count():
                page.locator("button[type='submit']").first.click()
            elif page.locator("button:has-text('Login')").count():
                page.locator("button:has-text('Login')").first.click()
            else:
                page.locator("button").first.click()
        except Exception as e:
            print("Click failed:", e)

        # wait a bit for any navigation / SPA activity
        time.sleep(8)

        # Save debug artifacts
        os.makedirs("logs", exist_ok=True)
        screenshot_path = os.path.join("logs", "debug_login.png")
        html_path = os.path.join("logs", "debug_login.html")
        try:
            page.screenshot(path=screenshot_path, full_page=True)
            print("Saved screenshot:", screenshot_path)
        except Exception as e:
            print("Screenshot failed:", e)
        try:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(page.content())
            print("Saved page HTML:", html_path)
        except Exception as e:
            print("Save HTML failed:", e)

        print("Current URL:", page.url)

        context.close()
        browser.close()


if __name__ == "__main__":
    main()
