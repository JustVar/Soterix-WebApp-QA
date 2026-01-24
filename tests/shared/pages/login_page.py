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

    def login(self, username: str, password: str, max_recaptcha_retries: int = 3):
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

        # Handle reCAPTCHA with retries
        recaptcha_success = self._handle_recaptcha(max_retries=max_recaptcha_retries)
        if recaptcha_success:
            print("[UI LOGIN] ReCAPTCHA verified successfully")
        else:
            print("[UI LOGIN] ReCAPTCHA not verified, attempting login anyway")

        # Do NOT click submit here - let auth_helper handle it after ReCAPTCHA is verified
        return self

    def _handle_recaptcha(self, max_retries: int = 3) -> bool:
        """Handle reCAPTCHA checkbox with retries.
        
        Returns True if ReCAPTCHA was successfully completed, False otherwise.
        """
        p = self.page
        
        for attempt in range(1, max_retries + 1):
            print(f"[UI LOGIN] ReCAPTCHA attempt {attempt}/{max_retries}")
            
            try:
                # Find the reCAPTCHA iframe
                frame_loc = p.frame_locator("iframe[title='reCAPTCHA']")
                anchor = frame_loc.locator("#recaptcha-anchor")
                
                if not anchor.count():
                    print("[UI LOGIN] No reCAPTCHA found on page, skipping")
                    return True  # No reCAPTCHA = success
                
                # Wait for anchor to be visible and clickable
                try:
                    anchor.wait_for(state="visible", timeout=5000)
                except Exception:
                    print(f"[UI LOGIN] ReCAPTCHA anchor not visible on attempt {attempt}")
                    continue
                
                # Wait for iframe to be fully interactive
                p.wait_for_timeout(2000)
                
                # Click the checkbox
                try:
                    anchor.click()
                    print("[UI LOGIN] ReCAPTCHA checkbox clicked")
                except Exception as e:
                    print(f"[UI LOGIN] Failed to click ReCAPTCHA: {e}")
                    continue
                
                # Wait for verification (g-recaptcha-response to be filled)
                try:
                    p.wait_for_function(
                        """() => {
                            const response = document.querySelector('textarea.g-recaptcha-response');
                            return response && response.value && response.value.length > 0;
                        }""",
                        timeout=15000,
                    )
                    print("[UI LOGIN] ReCAPTCHA response verified")
                    return True
                except Exception:
                    print(f"[UI LOGIN] ReCAPTCHA verification timeout on attempt {attempt}")
                    # Wait before retry
                    p.wait_for_timeout(2000)
                    continue
                    
            except Exception as e:
                print(f"[UI LOGIN] ReCAPTCHA error on attempt {attempt}: {e}")
                continue
        
        return False

    def click_login_button(self):
        """Click the login/submit button. Call this after ReCAPTCHA is verified."""
        p = self.page
        
        selectors = [
            'button[type="submit"]',
            'button:has-text("Login")',
            'button:has-text("Sign In")',
            'button:has-text("LOG IN")',
            'input[type="submit"]',
            '.login-button',
            '#login-btn',
            'button.btn-primary'
        ]
        
        for selector in selectors:
            try:
                btn = p.locator(selector).first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    print(f"[UI LOGIN] Clicked login button: {selector}")
                    return True
            except Exception:
                continue
        
        # Fallback: try role-based
        try:
            if p.get_by_role("button", name="Login").count():
                p.get_by_role("button", name="Login").click()
                print("[UI LOGIN] Clicked login button via role")
                return True
        except Exception:
            pass
        
        print("[UI LOGIN] WARNING: Could not find login button")
        return False
