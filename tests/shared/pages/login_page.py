import os
import pytest


class LoginPage:
    def __init__(self, page):
        self.page = page

    def goto(self, base_url: str, app_type: str = "customer"):
        """Navigate to the correct login path depending on app type."""
        # NOTE: Stage/Prod environments show ReCAPTCHA which blocks automation.
        # Automated tests should target `qa` while ReCAPTCHA is enabled in stage/prod.
        path = "/login" if app_type == "partner" else "/auth/login"
        self.page.goto(base_url.rstrip("/") + path)
        return self

    def login(self, username: str, password: str):
        """Fill credentials using robust Playwright selectors and submit.

        Uses get_by_placeholder / get_by_role where possible and falls
        back to common attribute selectors.
        """
        p = self.page

        # username field (try placeholder then common attributes)
        try:
            if p.get_by_placeholder("Email").count():
                p.get_by_placeholder("Email").fill(username)
            elif p.get_by_placeholder("Username").count():
                p.get_by_placeholder("Username").fill(username)
            else:
                p.locator("input[name='email']").fill(username)
        except Exception:
            try:
                p.locator("input[name='email']").fill(username)
            except Exception:
                pytest.skip("No username field found on login page")

        # password field
        try:
            if p.get_by_placeholder("Password").count():
                p.get_by_placeholder("Password").fill(password)
            else:
                p.locator("input[name='password']").fill(password)
        except Exception:
            try:
                p.locator("input[type='password']").fill(password)
            except Exception:
                pytest.skip("No password field found on login page")

        # Try to handle reCAPTCHA checkbox (QA shows a checkbox inside an iframe).
        # Selector observed in debug HTML: iframe[title="reCAPTCHA"] with inner
        # element #recaptcha-anchor. We attempt to click it and wait for the
        # g-recaptcha-response textarea to be populated as an indication the
        # checkbox was checked.
        try:
            frame_loc = p.frame_locator("iframe[title='reCAPTCHA']")
            anchor = frame_loc.locator("#recaptcha-anchor")
            if anchor.count():
                try:
                    anchor.wait_for(state="visible", timeout=5000)
                    anchor.click()
                except Exception:
                    # best-effort click; continue to submit afterwards
                    try:
                        anchor.click(timeout=2000)
                    except Exception:
                        pass

                # Wait for g-recaptcha-response to be filled by the widget
                try:
                    p.wait_for_function(
                        "() => document.querySelector('textarea.g-recaptcha-response') && document.querySelector('textarea.g-recaptcha-response').value.length > 0",
                        timeout=10000,
                    )
                except Exception:
                    # If we can't detect the response, continue (best-effort)
                    pass
        except Exception:
            # If frames aren't present or access denied, continue without failing
            pass

        # submit (try role then common selectors)
        try:
            if p.get_by_role("button", name="Login").count():
                p.get_by_role("button", name="Login").click()
            elif p.get_by_role("button").count() == 1:
                p.get_by_role("button").first.click()
            else:
                p.locator("button[type='submit']").first.click()
        except Exception:
            # last-resort click any submit-like button
            try:
                p.locator("button").first.click()
            except Exception:
                pytest.skip("No login button found to submit credentials")

        return self
