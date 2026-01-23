"""Authentication helper for API clients."""
from __future__ import annotations

import os
import time
from typing import Optional

import requests
import urllib3
from playwright.sync_api import sync_playwright
import json
from tests.shared.pages.login_page import LoginPage

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Determine verification behaviour: disable verification for non-production envs
_ENV = os.getenv("ENV", "").lower()
_VERIFY = False if _ENV not in ("prod", "production") else True


class AuthHelper:
    def __init__(self, base_url: str):
        # Normalize base_url to include /v-apiserver if not present so
        # auth helper paths can use '/REST/...' directly.
        b = (base_url or "").rstrip("/")
        if not b.endswith("/v-apiserver"):
            b = b + "/v-apiserver"
        self.base_url = b
        self._token: Optional[str] = None
        self._token_expiry: float = 0.0

    def login(self, email: str, password: str) -> str:
        """Login using API and return bearer token. Caches token per instance.

        Attempt the central login endpoint first and fall back to SSO if
        central explicitly returns 404. Per QA guidance, try the QA lab user
        `qa@soterixsystems.com` first, then fall back to the provided
        credentials if needed.
        """
        if self._token and time.time() < self._token_expiry - 30:
            return self._token

        # Credentials to try, in order: the provided QA account, QA lab account,
        # then the credentials passed into the function.
        candidates = [
            ("qa@soterixsystems.com", "***REMOVED***"),
            ("qa@soterixsystems.com", password),
            (email, password),
        ]

        last_exc = None
        for user, pwd in candidates:
            central_url = f"{self.base_url}/REST/central/user/auth/login"
            payload = {"username": user, "password": pwd}
            params = {"username": user, "password": pwd}
            # Print request info (mask password)
            masked = {k: ("***" if k == "password" else v) for k, v in payload.items()}
            params_str = "{" + f"'username': '{user}', 'password': '***'" + "}"
            print(f"AUTH TRY central -> url={central_url} params={params_str} body={masked}")
            try:
                r = requests.post(central_url, params=params, json=payload, timeout=15, verify=_VERIFY)
                print(f"AUTH RESP central -> status={r.status_code} body={r.text[:800]}")
            except Exception as e:
                last_exc = e
                continue

            # If central explicitly not found, try SSO
            if r.status_code == 404:
                try:
                    sso_url = f"{self.base_url}/REST/sso/login"
                    sso_body = {"username": user, "password": pwd}
                    masked_sso = {"username": user, "password": "***"}
                    print(f"AUTH FALLBACK -> trying SSO url={sso_url} body={masked_sso}")
                    r2 = requests.post(sso_url, json=sso_body, timeout=15, verify=_VERIFY)
                    print(f"AUTH RESP sso -> status={r2.status_code} body={r2.text[:800]}")
                except Exception as e2:
                    last_exc = e2
                    continue
                try:
                    r2.raise_for_status()
                    body = r2.json()
                    token = body.get("token") or body.get("access_token") or body.get("data", {}).get("token")
                    if token:
                        print(f"AUTH SUCCESS sso -> user={user}")
                        self._token = token
                        self._token_expiry = time.time() + 1800
                        return token
                    last_exc = RuntimeError(f"SSO login did not return token: {body}")
                    continue
                except Exception as e3:
                    last_exc = e3
                    continue

            # For other central responses, validate and parse
            try:
                r.raise_for_status()
                body = r.json()
                token = body.get("token") or body.get("access_token") or body.get("data", {}).get("token")
                if not token:
                    last_exc = RuntimeError(f"Login did not return token: {body}")
                    continue
                self._token = token
                self._token_expiry = time.time() + 1800
                return token
            except Exception as e:
                last_exc = e
                continue

        if last_exc:
            raise last_exc
        raise RuntimeError("Login failed for all attempted credential variants")

    def get_authenticated_client(self, credentials: dict, client_class):
        token = self.login(credentials["username"], credentials["password"])
        return client_class(self.base_url, token)

    def login_via_ui(self, email: str, password: str, headless: bool = False, timeout: int = 60000) -> str:
        """Perform UI login using Playwright and extract an auth token.

        Extraction order: cookies, localStorage, sessionStorage, network requests.
        Returns token string if found, otherwise raises RuntimeError.
        """
        # Derive site root (remove /v-apiserver if present)
        site = self.base_url
        if site.endswith("/v-apiserver"):
            site = site[: -len("/v-apiserver")]

        token = None
        captured_requests = []
        captured_responses = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            context = browser.new_context()
            page = context.new_page()

            # capture requests to inspect headers later
            def _on_request(req):
                try:
                    captured_requests.append({
                        "url": req.url,
                        "headers": dict(req.headers),
                    })
                except Exception:
                    pass

            page.on("request", _on_request)

            # capture responses so we can inspect JSON bodies for tokens
            def _on_response(resp):
                try:
                    body = None
                    try:
                        body = resp.text()
                    except Exception:
                        body = None
                    captured_responses.append({
                        "url": resp.url,
                        "status": resp.status,
                        "headers": dict(resp.headers),
                        "body": body,
                    })
                except Exception:
                    pass

            page.on("response", _on_response)

            # Perform login using existing Page Object (which handles reCAPTCHA)
            try:
                login_page = LoginPage(page)
                # Navigate to the login page and perform the login flow
                print(f"DEBUG: Navigating to login page: {site}")
                login_page.goto(site)
                try:
                    print(f"DEBUG: page title before login: {page.title()}" )
                except Exception:
                    pass
                # Call the LoginPage.login which contains recaptcha handling
                print(f"DEBUG: Calling LoginPage.login() with user={email}")
                login_page.login(email, password)

                # Wait for ReCAPTCHA to complete
                try:
                    page.wait_for_timeout(2000)
                except Exception:
                    pass
                print("[UI LOGIN] Credentials filled, ReCAPTCHA clicked")

                # Check if still on login page - need to click login button
                try:
                    if '/auth/login' in (page.url or ''):
                        print("[UI LOGIN] Still on login page, clicking login button...")

                        # Wait for ReCAPTCHA to fully verify (checkmark / response populated)
                        print("[UI LOGIN] Waiting for ReCAPTCHA verification to complete...")
                        try:
                            page.wait_for_function("""
                                () => {
                                    const iframe = document.querySelector('iframe[title*="reCAPTCHA"]');
                                    if (!iframe) return false;
                                    const response = document.querySelector('[name="g-recaptcha-response"]');
                                    return response && response.value && response.value.length > 0;
                                }
                            """, timeout=15000)
                            print("[UI LOGIN] ReCAPTCHA verification complete!")
                        except Exception:
                            print("[UI LOGIN] ReCAPTCHA wait timed out, trying anyway...")
                            try:
                                page.wait_for_timeout(5000)
                            except Exception:
                                pass

                        # Additional buffer
                        try:
                            page.wait_for_timeout(1000)
                        except Exception:
                            pass
                        login_button = None
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
                                btn = page.locator(selector).first
                                if btn.is_visible(timeout=1000):
                                    login_button = btn
                                    print(f"[UI LOGIN] Found button with selector: {selector}")
                                    break
                            except Exception:
                                continue

                        if login_button:
                            try:
                                login_button.click()
                                print("[UI LOGIN] Login button clicked!")
                            except Exception as e:
                                print(f"[UI LOGIN] Failed to click login button: {e}")
                        else:
                            print("[UI LOGIN] WARNING: Could not find login button")
                            try:
                                import os as _os
                                _os.makedirs("logs", exist_ok=True)
                                page.screenshot(path="logs/login_button_not_found.png")
                                print("Saved screenshot: logs/login_button_not_found.png")
                            except Exception:
                                pass
                except Exception:
                    pass
                try:
                    print(f"DEBUG: page title after login call: {page.title()}")
                except Exception:
                    pass
            except Exception:
                try:
                    context.close()
                    browser.close()
                except Exception:
                    pass
                raise

            # Wait for redirect away from login page (max 30s)
            try:
                # Wait up to `timeout` ms for redirect away from login
                start = time.time()
                max_seconds = max(1, int(timeout / 1000))
                while True:
                    cur = page.url
                    print(f"DEBUG: current url poll: {cur}")
                    if "/auth/login" not in (cur or ""):
                        break
                    if time.time() - start > max_seconds:
                        break
                    time.sleep(0.5)
                try:
                    print(f"Current URL after login: {page.url}")
                    print(f"DEBUG: page title post-wait: {page.title()}")
                except Exception:
                    pass
            except Exception:
                pass

            # Ensure login navigation completed and cookies settled
            try:
                # If we are redirected to dashboard, or not on /auth/login, proceed
                print(f"Current URL after login: {page.url}")
            except Exception:
                pass
            try:
                page.wait_for_timeout(2000)
            except Exception:
                pass

            # Get cookies from the browser context and look for JSESSIONID (case-insensitive)
            try:
                cookies = context.cookies()
                print(f"DEBUG: All cookies: {[c.get('name') for c in cookies]}")
                for cookie in cookies:
                    try:
                        if str(cookie.get("name", "")).lower() == "jsessionid" and cookie.get("value"):
                            token = cookie.get("value")
                            print(f"DEBUG: Found JSESSIONID: {str(token)[:20]}...")
                            break
                    except Exception:
                        continue
            except Exception:
                cookies = []

            # If no JSESSIONID, print potential error messages and capture screenshot for debugging
            if not token:
                try:
                    # look for common error selectors
                    errs = []
                    for sel in (".error", ".toast-error", "[role='alert']", ".alert-danger"):
                        try:
                            loc = page.locator(sel)
                            if loc.count():
                                errs.append(loc.inner_text())
                        except Exception:
                            continue
                    if errs:
                        print("DEBUG: Page error messages:")
                        for e in errs:
                            print(e)
                except Exception:
                    pass
                try:
                    os.makedirs("logs", exist_ok=True)
                    ss = os.path.join("logs", "login_failure.png")
                    page.screenshot(path=ss, full_page=True)
                    print(f"Saved screenshot: {ss}")
                except Exception:
                    pass

            # 2) Check localStorage
            if not token:
                try:
                    ls = page.evaluate("() => JSON.stringify(window.localStorage)")
                    if ls:
                        obj = json.loads(ls)
                        # Print requested keys for debugging and later analysis
                        for key in ("rolePermissions", "userInfo", "enterpriseId", "userId"):
                            if key in obj:
                                print(f"localStorage[{key}] = {obj.get(key)}")
                        for k, v in obj.items():
                            if any(sub in k.lower() for sub in ("token", "auth", "access", "jwt")):
                                token = v
                                break
                except Exception:
                    pass

            # 3) Check sessionStorage
            if not token:
                try:
                    ss = page.evaluate("() => JSON.stringify(window.sessionStorage)")
                    if ss:
                        obj = json.loads(ss)
                        for key in ("rolePermissions", "userInfo", "enterpriseId", "userId"):
                            if key in obj:
                                print(f"sessionStorage[{key}] = {obj.get(key)}")
                        for k, v in obj.items():
                            if any(sub in k.lower() for sub in ("token", "auth", "access", "jwt")):
                                token = v
                                break
                except Exception:
                    pass

            # 4) Inspect captured requests for Authorization header or token-like values
            if not token:
                try:
                    for r in captured_requests:
                        headers = r.get("headers", {})
                        auth = headers.get("authorization") or headers.get("Authorization")
                        if auth and isinstance(auth, str):
                            if auth.lower().startswith("bearer "):
                                token = auth.split(" ", 1)[1].strip()
                                break
                            else:
                                token = auth.strip()
                                break
                except Exception:
                    pass

            # 5) Inspect captured responses for JSON bodies containing token
            if not token:
                try:
                    for r in captured_responses:
                        body = r.get("body")
                        if not body:
                            continue
                        try:
                            j = json.loads(body)
                        except Exception:
                            # sometimes response contains HTML or JS; skip
                            continue
                        # look for common token fields
                        if isinstance(j, dict):
                            for key in ("token", "access_token", "id_token", "auth_token"):
                                if key in j and j[key]:
                                    token = j[key]
                                    break
                            if token:
                                break
                            # nested data.token
                            data = j.get("data")
                            if isinstance(data, dict) and data.get("token"):
                                token = data.get("token")
                                break
                except Exception:
                    pass

            try:
                context.close()
                browser.close()
            except Exception:
                pass

        if not token:
            # Save debug artifacts for investigation
            try:
                import os, json as _json
                os.makedirs("logs", exist_ok=True)
                with open(os.path.join("logs", "debug_ui_requests.json"), "w", encoding="utf-8") as f:
                    _json.dump(captured_requests, f, indent=2)
                with open(os.path.join("logs", "debug_ui_responses.json"), "w", encoding="utf-8") as f:
                    _json.dump(captured_responses, f, indent=2)
                # try to save page HTML (if available)
                try:
                    with open(os.path.join("logs", "debug_ui_page.html"), "w", encoding="utf-8") as f:
                        f.write(page.content())
                except Exception:
                    pass
            except Exception:
                pass

            raise RuntimeError("UI login did not yield an auth token from cookies/localStorage/sessionStorage/network headers")

        # Cache token (JSESSIONID or token-like)
        self._token = token
        self._token_expiry = time.time() + 1800

        # Validate by calling central user session with Cookie header if token looks like a JSESSIONID
        try:
            import re
            is_jsession = bool(re.fullmatch(r"[0-9a-fA-F]{16,128}", token)) if isinstance(token, str) else False
            session_ok = False
            if is_jsession:
                test_url = f"{self.base_url}/REST/central/user/session"
                try:
                    r = requests.get(test_url, headers={"Cookie": f"JSESSIONID={token}"}, timeout=10, verify=_VERIFY)
                    print(f"Session test -> {r.status_code} {r.text[:300]}")
                    if r.status_code == 200:
                        session_ok = True
                except Exception as e:
                    print(f"Session test request failed: {e}")

            if session_ok:
                return token
            else:
                # return token anyway; callers will attempt and tests will validate
                return token
        except Exception:
            return token
