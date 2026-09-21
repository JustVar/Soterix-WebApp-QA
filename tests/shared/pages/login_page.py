import os
import re

from playwright.sync_api import Error as PlaywrightError, Page

# Timeouts (milliseconds)
RECAPTCHA_TIMEOUT = 15000
SHORT_WAIT = 2000
LOGIN_WAIT = 10000


def _active_base_url() -> str:
    """The base url of the environment ENV selects, or '' when it cannot load."""
    try:
        from config.base_config import config
        return str(config.get("base_url") or "")
    except Exception:  # why: a page object must still construct when the env module cannot load; the caller's page.url is next
        return ""


class LoginPage:
    """Playwright Page Object Model for the application's login page.

    This class centralizes selectors and login helpers including a best-effort
    ReCAPTCHA checkbox handler and robust submit button selection.
    """

    def __init__(self, page: Page, base_url: str | None = None):
        """Initialize LoginPage.

        Args:
            page: Playwright Page instance.
            base_url: Optional base URL for the app. If not provided, will
                attempt to derive from `page.url`.
        """
        self.page = page
        # A caller that passes only `page` gets the ACTIVE environment's
        # base url. The old fallback read BASE_URL from .env whatever ENV
        # said, and an ENV=neurosen experiment signed in to the QA tenant
        # through it (09/18/2026).
        raw_base = base_url or _active_base_url() or (getattr(page, 'url', None) or '')
        self.base_url = raw_base.rstrip("/")

        # selector fallbacks
        self._email_selectors: list[str] = [
            '[data-testid="email"]',
            '[aria-label="Email"]',
            'input[name="email"]',
            '//input[contains(@name, "email")]',
        ]
        self._password_selectors: list[str] = [
            '[data-testid="password"]',
            '[aria-label="Password"]',
            'input[name="password"]',
            '//input[contains(@name, "password")]',
        ]
        self._login_button_selectors: list[str] = [
            'button[type="submit"]',
            'button:has-text("Login")',
            'button:has-text("Sign In")',
            'input[type="submit"]',
            '.login-button',
            '#login-btn',
            'button.btn-primary',
        ]
        self._error_selectors: list[str] = [
            '[data-testid="error-message"]',
            '[role="alert"]',
            '.error',
            'text=Invalid',
            '//div[contains(@class, "error")]',
        ]

    def _first_visible(self, selectors: list[str]):
        """Return the first visible locator from a list of selectors, or None."""
        for s in selectors:
            try:
                locator = self.page.locator(s)
                if locator.count() and locator.first.is_visible():
                    return locator.first
            # selector-fallback probe: a bad candidate is a miss, the caller
            # fills the returned or fallback locator and raises if the field
            # never exists
            except Exception:
                continue
        return None

    def goto(self, base_url: str | None = None, app_type: str = "customer"):
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
        # networkidle is a settle hint, not a readiness check: the app holds
        # persistent connections (see login() below and the conftest.py auth
        # fixture) so it may never fire, and a timeout here means the full
        # wait budget was already spent - swallowing it never shortens the
        # settle. callers that need the form prove it themselves: login()'s
        # fill() auto-waits and raises
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
                    btn.click(timeout=10000)
                    return True
            # submit-button fallback probe: an absent candidate never reaches
            # this except (is_visible() ignores its timeout and returns False
            # without raising); it only covers a click that failed on a
            # visible candidate (disabled, obscured, detached mid-navigation)
            # or a torn-down page. the miss is reported as False and login()
            # takes its own direct-submit / Enter fallback; every login()
            # caller asserts is_logged_in()/is_login_page()/
            # get_error_message() itself
            except Exception:
                continue

        # Fallback: try role-based
        try:
            if p.get_by_role("button", name="Login").count():
                p.get_by_role("button", name="Login").click(timeout=10000)
                return True
        # last-candidate probe: on failure the method returns False and
        # login() falls back to a direct submit click
        except Exception:
            pass

        return False

    def _handle_recaptcha(self, max_retries: int = 3) -> bool:
        """Best-effort handler for ReCAPTCHA checkbox.

        Returns True if ReCAPTCHA appears completed or not present; False on timeout.
        """
        p = self.page
        for _attempt in range(1, max_retries + 1):
            try:
                frame_loc = p.frame_locator("iframe[title='reCAPTCHA']")
                anchor = frame_loc.locator("#recaptcha-anchor")
                if not anchor.count():
                    return True
                anchor.wait_for(state="visible", timeout=SHORT_WAIT)
                # reCAPTCHA iframe pacing: the anchor becomes clickable
                # a beat after it renders, with no DOM signal
                p.wait_for_timeout(SHORT_WAIT)
                anchor.click(timeout=10000)
                try:
                    p.wait_for_function(
                        "() => { const r = document.querySelector('textarea.g-recaptcha-response'); return r && r.value && r.value.length > 0; }",
                        timeout=RECAPTCHA_TIMEOUT,
                    )
                    return True
                # no token on this attempt. The loop tries again and returns False
                # after the last one. login() submits anyway and its callers assert
                except Exception:
                    # reCAPTCHA challenge polling beat before the next
                    # frame candidate
                    p.wait_for_timeout(SHORT_WAIT)
                    continue
            # best-effort recaptcha retry: any failure on this attempt (frame
            # probe during navigation, anchor absent/invisible/unclickable,
            # no token) counts as a failed attempt and moves to the next one;
            # after max_retries the method returns False. safe to swallow:
            # the recaptcha click never gates submit - login(), the only
            # caller, ignores the return value and submits anyway, and every
            # login() caller asserts the outcome itself (is_logged_in /
            # get_error_message / wait_for_url)
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

        self._handle_recaptcha()

        clicked = self.click_login_button()

        if not clicked:
            try:
                self.page.locator('button[type="submit"]').click()
            except Exception:
                try:
                    self.page.keyboard.press('Enter')
                except Exception as exc:
                    raise AssertionError(
                        "login form was not submitted: no submit button "
                        "matched and pressing Enter failed"
                    ) from exc

        try:
            # Success signal: the app leaves the login page. The landing URL
            # varies (currently '/', historically '/dashboard'), so wait for
            # departure rather than a specific destination. networkidle is not
            # usable here - the app holds persistent connections.
            self.page.wait_for_url(lambda url: '/auth/login' not in url, timeout=LOGIN_WAIT)
            self.page.wait_for_load_state('domcontentloaded', timeout=LOGIN_WAIT)
        # login() also drives negative attempts that must stay on
        # /auth/login; every caller asserts is_logged_in() or the error
        # message afterwards
        except Exception:
            pass

        return self

    def is_logged_in(self) -> bool:
        """Return True when a dashboard marker is visible or the URL changed away from login."""
        try:
            if self.page.locator("text=Drag & Drop Camera here").count():
                return self.page.locator("text=Drag & Drop Camera here").first.is_visible()
        # dashboard-marker probe is optional; on failure the url check below
        # decides and callers assert the returned bool
        except Exception:
            pass
        return "/auth/login" not in self.page.url

    def is_login_page(self) -> bool:
        """Return True when the current page appears to be the login page."""
        # Give the page a moment to settle after redirect
        try:
            self.page.wait_for_load_state('domcontentloaded', timeout=5000)
        # settle wait only; the url and form checks below run either way and
        # callers assert the returned bool
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
        # form-field probe: a locator error means no login form was
        # detected, the method returns False and callers assert it
        except Exception:
            pass
        return False

    def get_error_message(self) -> str | None:
        """Return a visible error/validation message if present, otherwise None."""
        for s in self._error_selectors:
            try:
                loc = self.page.locator(s)
                try:
                    loc.first.wait_for(state="visible", timeout=SHORT_WAIT)
                # visibility wait is a settle hint per candidate; the
                # count/text check below still runs and callers assert the
                # returned message
                except Exception:
                    pass
                if loc.count():
                    txt = loc.first.text_content(timeout=5000)
                    if txt:
                        return txt.strip()
            # error-selector fallback probe: a failing candidate is a miss,
            # the method returns None and callers assert the message
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
            # optional-ui probe: a failing selector is a miss, the method
            # returns False and the caller has its own assertion
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
            # optional-ui probe: a failing text locator is a miss, the method
            # returns False and the caller has its own assertion
            except Exception:
                continue
        return False

    def find_password_reset_link(self) -> str | None:
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
                    return loc.first.text_content(timeout=5000).strip()
            # optional-link probe: a failing candidate is a miss, the method
            # returns None and the caller decides what to assert
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
        # a page that cannot answer reads as a closed menu. The test asserts
        # that this returns True
        except Exception:
            return False

    def get_profile_menu_items(self) -> list[str]:
        """Return text content of all visible profile menu items.

        Scoped to the popover containing 'Sign out' to avoid picking up
        unrelated MUI menus (camera context menus, tile actions, etc.).
        """
        items: list[str] = []
        # This build's menu is a box in the secondary header, not a
        # popover: the avatar's initials, the account name, its role and
        # 'Sign out' as <p> lines (measured 09/12/2026). Read that box
        # first; the popover selectors below serve older builds.
        sign_out = self.page.locator("p").filter(has_text=re.compile(r"^Sign out$")).first
        if sign_out.count() and sign_out.is_visible():
            box = sign_out.locator("xpath=ancestor::div[2]")
            lines = [t.strip() for t in box.locator("p").all_inner_texts() if t.strip()]
            if "Sign out" in lines:
                return lines
        # Find the popover that contains "Sign out" - that's the profile menu
        # this build renders the menu as a role=menu list inside a
        # MuiPopover-root (measured 09/12/2026); the paper classes stay
        # for older builds
        popover_selectors = [
            '[role="menu"]:has-text("Sign out")',
            '.MuiMenu-list:has-text("Sign out")',
            '.MuiPopover-paper:has-text("Sign out")',
            '.MuiMenu-paper:has-text("Sign out")',
            '.MuiPopover-root:has-text("Sign out")',
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
                            txt = loc.nth(i).text_content(timeout=5000)
                            if txt and txt.strip():
                                items.append(txt.strip())
                        if items:
                            return items
            # popover fallback probe: a failing candidate is a miss, the
            # method returns the collected list for the caller to assert on
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
                    loc.click(timeout=10000)
                    return self
            # sign-out selector fallback: a missed candidate continues, the
            # raise after the loop reports the failure if none matched
            except Exception:
                continue
        raise Exception("Could not find 'Sign out' button in profile menu")

    def logout(self):
        """Perform full logout: open profile menu, click Sign out, wait for login page."""
        self.open_profile_menu()
        self.click_sign_out()
        try:
            self.page.wait_for_url('**/auth/login**', timeout=LOGIN_WAIT)
        except PlaywrightError:
            # Some app versions redirect to root or a different auth URL;
            # the URL wait missed, so give the redirect a beat before
            # checking the login form
            self.page.wait_for_timeout(5000)
            if not self.is_login_page():
                # Until 09/21/2026 this branch opened /auth/login itself, and
                # is_login_page() then said yes: the logout tests passed on a
                # Sign out that went nowhere. A logout that does not land fails here.
                raise AssertionError(
                    f"Sign out did not open the login page: the address is {self.page.url}") from None
        return self

