from typing import List, Optional

from playwright.sync_api import Page
import os

# Timeouts (milliseconds)
RECAPTCHA_TIMEOUT = 15000
SHORT_WAIT = 2000
LOGIN_WAIT = 10000


class LoginPage:
    """Playwright Page Object Model for the application's login page.

    This class centralizes selectors and login helpers including a best-effort
    ReCAPTCHA checkbox handler and robust submit button selection.
    """

    def __init__(self, page: Page, base_url: Optional[str] = None):
        """Initialize LoginPage.

        Args:
            page: Playwright Page instance.
            base_url: Optional base URL for the app. If not provided, will
                attempt to derive from `page.url`.
        """
        self.page = page
        # Allow backward-compatible construction from callers that only pass `page`.
        raw_base = base_url or os.environ.get('BASE_URL') or (getattr(page, 'url', None) or '')
        self.base_url = raw_base.rstrip("/")

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
            'button[type="submit"]',
            'button:has-text("Login")',
            'button:has-text("Sign In")',
            'input[type="submit"]',
            '.login-button',
            '#login-btn',
            'button.btn-primary',
        ]
        self._error_selectors: List[str] = [
            '[data-testid="error-message"]',
            '[role="alert"]',
            '.error',
            'text=Invalid',
            '//div[contains(@class, "error")]',
        ]

    def _first_visible(self, selectors: List[str]):
        """Return the first visible locator from a list of selectors, or None."""
        for s in selectors:
            try:
                locator = self.page.locator(s)
                if locator.count() and locator.first.is_visible():
                    return locator.first
            except Exception:
                continue
        return None

    def goto(self, base_url: Optional[str] = None, app_type: str = "customer"):
        """Navigate to the login page.

        Args:
            base_url: Optional base URL override (for backward compatibility)
            app_type: 'customer' or 'partner' to determine login path
        """
        if base_url:
            self.base_url = base_url.rstrip("/")
        path = "/login" if app_type == "partner" else "/auth/login"
        self.page.goto(self.base_url + path)
        try:
            self.page.wait_for_load_state("networkidle")
        except Exception:
            pass
        return self

    def enter_email(self, email: str):
        """Fill the email input using the first available selector."""
        loc = self._first_visible(self._email_selectors) or self.page.locator('input[type="email"]')
        loc.fill("")
        loc.fill(email)

    def enter_password(self, password: str):
        """Fill the password input using the first available selector."""
        loc = self._first_visible(self._password_selectors) or self.page.locator('input[type="password"]')
        loc.fill("")
        loc.fill(password)

    def click_login_button(self) -> bool:
        """Click a likely login/submit button and return True if clicked."""
        p = self.page
        for selector in self._login_button_selectors:
            try:
                btn = p.locator(selector).first
                if btn.is_visible(timeout=SHORT_WAIT):
                    btn.click()
                    return True
            except Exception:
                continue

        # Fallback: try role-based
        try:
            if p.get_by_role("button", name="Login").count():
                p.get_by_role("button", name="Login").click()
                return True
        except Exception:
            pass

        return False

    def _handle_recaptcha(self, max_retries: int = 3) -> bool:
        """Best-effort handler for ReCAPTCHA checkbox.

        Returns True if ReCAPTCHA appears completed or not present; False on timeout.
        """
        p = self.page
        for attempt in range(1, max_retries + 1):
            try:
                frame_loc = p.frame_locator("iframe[title='reCAPTCHA']")
                anchor = frame_loc.locator("#recaptcha-anchor")
                if not anchor.count():
                    return True
                try:
                    anchor.wait_for(state="visible", timeout=SHORT_WAIT)
                except Exception:
                    continue
                p.wait_for_timeout(SHORT_WAIT)
                try:
                    anchor.click()
                except Exception:
                    continue
                try:
                    p.wait_for_function(
                        "() => { const r = document.querySelector('textarea.g-recaptcha-response'); return r && r.value && r.value.length > 0; }",
                        timeout=RECAPTCHA_TIMEOUT,
                    )
                    return True
                except Exception:
                    p.wait_for_timeout(SHORT_WAIT)
                    continue
            except Exception:
                continue
        return False

    def login(self, email: str, password: str):
        """Perform login: navigate, fill credentials, attempt recaptcha, submit, and wait.

        Success signal: the browser leaves /auth/login (the landing URL varies
        by app version, so no specific destination is assumed).
        """
        if "/auth/login" not in self.page.url:
            self.goto()

        self.enter_email(email)
        self.enter_password(password)

        try:
            self._handle_recaptcha()
        except Exception:
            pass

        clicked = False
        try:
            clicked = self.click_login_button()
        except Exception:
            pass

        if not clicked:
            try:
                self.page.locator('button[type="submit"]').click()
            except Exception:
                try:
                    self.page.keyboard.press('Enter')
                except Exception:
                    pass

        try:
            # Success signal: the app leaves the login page. The landing URL
            # varies (currently '/', historically '/dashboard'), so wait for
            # departure rather than a specific destination. networkidle is not
            # usable here - the app holds persistent connections.
            self.page.wait_for_url(lambda url: '/auth/login' not in url, timeout=LOGIN_WAIT)
            self.page.wait_for_load_state('domcontentloaded', timeout=LOGIN_WAIT)
        except Exception:
            pass

        return self

    def is_logged_in(self) -> bool:
        """Return True when a dashboard marker is visible or the URL changed away from login."""
        try:
            if self.page.locator("text=Drag & Drop Camera here").count():
                return self.page.locator("text=Drag & Drop Camera here").first.is_visible()
        except Exception:
            pass
        return "/auth/login" not in self.page.url

    def is_login_page(self) -> bool:
        """Return True when the current page appears to be the login page."""
        # Give the page a moment to settle after redirect
        try:
            self.page.wait_for_load_state('domcontentloaded', timeout=5000)
        except Exception:
            pass
        url = (self.page.url or "").lower()
        if "login" in url or "auth" in url:
            return True
        # Check for login form elements with multiple selector strategies
        login_input_selectors = [
            'input[name="email"]',
            'input[type="email"]',
            'input[placeholder*="mail"]',
            'input[placeholder*="user"]',
        ]
        password_selectors = [
            'input[name="password"]',
            'input[type="password"]',
        ]
        try:
            has_login = any(self.page.locator(s).count() > 0 for s in login_input_selectors)
            has_password = any(self.page.locator(s).count() > 0 for s in password_selectors)
            if has_login and has_password:
                return True
        except Exception:
            pass
        return False

    def get_error_message(self) -> Optional[str]:
        """Return a visible error/validation message if present, otherwise None."""
        for s in self._error_selectors:
            try:
                loc = self.page.locator(s)
                try:
                    loc.first.wait_for(state="visible", timeout=SHORT_WAIT)
                except Exception:
                    pass
                if loc.count():
                    txt = loc.first.text_content()
                    if txt:
                        return txt.strip()
            except Exception:
                continue
        return None

    def has_captcha(self) -> bool:
        """Return True if a CAPTCHA or reCAPTCHA element is visible."""
        selectors = [
            "iframe[title='reCAPTCHA']",
            "[class*='captcha']",
            "[class*='recaptcha']",
            "[id*='captcha']",
        ]
        for s in selectors:
            try:
                loc = self.page.locator(s)
                if loc.count() > 0 and loc.first.is_visible():
                    return True
            except Exception:
                continue
        return False

    def has_lockout_message(self) -> bool:
        """Return True if a rate-limit / lockout message is visible."""
        lockout_terms = ["too many", "try again", "timeout", "wait", "locked"]
        for term in lockout_terms:
            try:
                loc = self.page.locator(f"text=/{term}/i")
                if loc.count() > 0 and loc.first.is_visible():
                    return True
            except Exception:
                continue
        return False

    def find_password_reset_link(self) -> Optional[str]:
        """Find a 'Forgot password' or 'Reset' link on the login page.

        Returns the link text if found, None otherwise.
        """
        reset_selectors = [
            "a:has-text('Forgot')",
            "a:has-text('Reset')",
            "span:has-text('Forgot')",
            "button:has-text('Forgot')",
            "p:has-text('Forgot')",
            "a[href*='forgot']",
            "a[href*='reset']",
        ]
        for s in reset_selectors:
            try:
                loc = self.page.locator(s)
                if loc.count() > 0 and loc.first.is_visible():
                    return loc.first.text_content().strip()
            except Exception:
                continue
        return None

    # ------------------------------------------------------------------
    # Profile menu & logout
    # ------------------------------------------------------------------

    def open_profile_menu(self):
        """Click the profile avatar to open the dropdown menu."""
        avatar = self.page.locator('.MuiAvatar-root').first
        avatar.wait_for(state="visible", timeout=15000)
        avatar.click()
        # Wait for the profile-specific menu (contains "Sign out")
        self.page.locator('text=Sign out').wait_for(state="visible", timeout=5000)
        return self

    def is_profile_menu_open(self) -> bool:
        """Return True when the profile dropdown menu is visible."""
        try:
            return self.page.locator('text=Sign out').is_visible()
        except Exception:
            return False

    def get_profile_menu_items(self) -> List[str]:
        """Return text content of all visible profile menu items.

        Scoped to the popover containing 'Sign out' to avoid picking up
        unrelated MUI menus (camera context menus, tile actions, etc.).
        """
        items: List[str] = []
        # Find the popover that contains "Sign out" - that's the profile menu
        popover_selectors = [
            '.MuiPopover-paper:has-text("Sign out")',
            '.MuiMenu-paper:has-text("Sign out")',
        ]
        for ps in popover_selectors:
            try:
                popover = self.page.locator(ps).first
                if not popover.is_visible():
                    continue
                for child_sel in ['li', '[role="menuitem"]', 'p']:
                    loc = popover.locator(child_sel)
                    if loc.count() > 0:
                        for i in range(loc.count()):
                            txt = loc.nth(i).text_content()
                            if txt and txt.strip():
                                items.append(txt.strip())
                        if items:
                            return items
            except Exception:
                continue
        return items

    def click_sign_out(self):
        """Click the 'Sign out' option in the profile menu."""
        sign_out_selectors = [
            'text=Sign out',
            'p:has-text("Sign out")',
            '[role="menuitem"]:has-text("Sign out")',
            'li:has-text("Sign out")',
        ]
        for s in sign_out_selectors:
            try:
                loc = self.page.locator(s).first
                if loc.is_visible(timeout=SHORT_WAIT):
                    loc.click()
                    return self
            except Exception:
                continue
        raise Exception("Could not find 'Sign out' button in profile menu")

    def logout(self):
        """Perform full logout: open profile menu, click Sign out, wait for login page."""
        self.open_profile_menu()
        self.click_sign_out()
        try:
            self.page.wait_for_url('**/auth/login**', timeout=LOGIN_WAIT)
        except Exception:
            # Some app versions redirect to root or a different auth URL
            self.page.wait_for_timeout(5000)
            # Verify we're actually logged out by checking for login form
            if not self.is_login_page():
                # Try navigating to login page directly
                self.page.goto(f"{self.base_url}/auth/login", wait_until="domcontentloaded")
                self.page.wait_for_timeout(2000)
        return self

