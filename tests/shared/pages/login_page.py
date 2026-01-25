from typing import List, Optional

from playwright.sync_api import Page


class LoginPage:
    """Page Object Model for the login page (Playwright).

    Uses a small set of stable selector fallbacks (data-testid, aria-label, name)
    and falls back to CSS/XPath when needed.
    """

    def __init__(self, page: Page, base_url: str):
        self.page = page
        self.base_url = base_url.rstrip("/")

        # selector fallbacks
        self._email_selectors: List[str] = [
            '[data-testid="email"]',
            '[aria-label="Email"]',
            'input[name="email"]',
            '//input[contains(@name, "email")]',
        ]
        self._password_selectors: List[str] = [
            '[data-testid="password"]',
            '[aria-label="Password"]',
            'input[name="password"]',
            '//input[contains(@name, "password")]',
        ]
        self._login_button_selectors: List[str] = [
            '[data-testid="login-button"]',
            'button:has-text("Login")',
            'button[type="submit"]',
            '//button[text()="Login"]',
        ]
        self._error_selectors: List[str] = [
            '[data-testid="error-message"]',
            '[role="alert"]',
            '.error',
            '//div[contains(@class,"error")]',
        ]
        self._captcha_selector = '[data-testid="recaptcha-checkbox"]',

    def _first_visible(self, selectors: List[str]):
        for s in selectors:
            try:
                locator = self.page.locator(s)
                if locator.count() and locator.first.is_visible():
                    return locator.first
            except Exception:
                # ignore bad selectors
                continue
        return None

    def goto(self):
        url = f"{self.base_url}/auth/login"
        self.page.goto(url)

    def enter_email(self, email: str):
        loc = self._first_visible(self._email_selectors)
        if not loc:
            # fallback: try common CSS
            loc = self.page.locator('input[type="email"]')
        loc.fill("")
        loc.fill(email)

    def enter_password(self, password: str):
        loc = self._first_visible(self._password_selectors)
        if not loc:
            loc = self.page.locator('input[type="password"]')
        loc.fill("")
        loc.fill(password)

    def click_login(self):
        btn = self._first_visible(self._login_button_selectors)
        if btn:
            btn.click()
        else:
            # try pressing Enter on password
            self.page.keyboard.press("Enter")

    def login(self, email: str, password: str):
        # Navigate first if we're not already on login
        if "/auth/login" not in self.page.url:
            self.goto()
        self.enter_email(email)
        self.enter_password(password)
        self.click_login()

    def get_error_message(self) -> Optional[str]:
        loc = self._first_visible(self._error_selectors)
        if loc:
            try:
                return loc.text_content().strip()
            except Exception:
                return None
        return None

    def is_logged_in(self) -> bool:
        # Prefer an explicit dashboard marker; fallback to checking for "Drag & Drop Camera here"
        try:
            if self.page.locator("text=Drag & Drop Camera here").count():
                return self.page.locator("text=Drag & Drop Camera here").first.is_visible()
        except Exception:
            pass
        # fallback: check URL change away from login
        return "/auth/login" not in self.page.url

    def is_login_page(self) -> bool:
        """Return True when the current page appears to be the login page."""
        url = self.page.url.lower()
        if "login" in url or "auth" in url:
            return True
        try:
            # presence of email/password inputs indicates login page
            if self.page.locator('input[name="email"]').count() and self.page.locator('input[name="password"]').count():
                return True
        except Exception:
            pass
        return False

    def get_error_message(self) -> Optional[str]:
        """Return a visible error/validation message if present, otherwise None."""
        selectors = [
            '[data-testid="error-message"]',
            '[role="alert"]',
            '.error',
            'text=Invalid',
            '//div[contains(@class, "error")]',
            '//div[contains(@class, "alert")]',
            '//p[contains(@class, "error-text")]',
            '//span[contains(@class, "error")]',
        ]
        for s in selectors:
            try:
                loc = self.page.locator(s)
                # wait briefly for potential client-side validation messages
                try:
                    loc.first.wait_for(state="visible", timeout=2000)
                except Exception:
                    # not visible yet or selector not applicable
                    pass
                if loc.count():
                    txt = loc.first.text_content()
                    if txt:
                        return txt.strip()
            except Exception:
                continue
        return None
import os
import pytest


class LoginPage:
    def __init__(self, page, base_url):
        self.page = page
        self.base_url = base_url

    def goto(self, app_type: str = "customer"):
        """Navigate to the correct login path depending on app type."""
        # NOTE: Stage/Prod environments show ReCAPTCHA which blocks automation.
        # Automated tests should target `qa` while ReCAPTCHA is enabled in stage/prod.
        path = "/login" if app_type == "partner" else "/auth/login"
        self.page.goto(self.base_url.rstrip("/") + path)
        return self

    def login(self, email: str, password: str):
        """Login with ReCAPTCHA handling.

        Fill credentials, attempt to handle reCAPTCHA, then submit and wait briefly
        for navigation to occur.
        """
        if "/auth/login" not in self.page.url:
            self.goto()

        # Fill credentials using stable selectors
        self.page.locator('input[name="email"]').fill(email)
        self.page.locator('input[name="password"]').fill(password)

        # Handle ReCAPTCHA before submitting (best-effort)
        try:
            self._handle_recaptcha()
        except Exception:
            # Don't fail tests solely because recaptcha handling had an internal error
            pass

        # Click submit using robust selector choices
        try:
            clicked = self.click_login_button()
            if not clicked:
                # fallback to simple submit
                try:
                    self.page.locator('button[type="submit"]').click()
                except Exception:
                    try:
                        self.page.keyboard.press('Enter')
                    except Exception:
                        pass
        except Exception:
            try:
                self.page.locator('button[type="submit"]').click()
            except Exception:
                pass

        # Wait for navigation or dashboard marker
        try:
            self.page.wait_for_url('**/dashboard**', timeout=10000)
        except Exception:
            try:
                self.page.wait_for_load_state('networkidle', timeout=10000)
            except Exception:
                pass

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

    def is_logged_in(self) -> bool:
        """Check whether we appear to be logged in.

        Prefer a visible dashboard marker, otherwise fall back to URL change.
        """
        try:
            if self.page.locator("text=Drag & Drop Camera here").count():
                return self.page.locator("text=Drag & Drop Camera here").first.is_visible()
        except Exception:
            pass
        return "/auth/login" not in self.page.url

    def get_error_message(self) -> Optional[str]:
        """Return a visible error/validation message if present, otherwise None."""
        selectors = [
            '[data-testid="error-message"]',
            '[role="alert"]',
            '.error',
            'text=Invalid',
            '//div[contains(@class, "error")]',
            '//div[contains(@class, "alert")]',
            '//p[contains(@class, "error-text"])',
            '//span[contains(@class, "error")]',
        ]
        for s in selectors:
            try:
                loc = self.page.locator(s)
                if loc.count():
                    txt = loc.first.text_content()
                    if txt:
                        return txt.strip()
            except Exception:
                continue
        return None
