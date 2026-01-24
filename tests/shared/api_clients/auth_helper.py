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
        # Session cache settings
        self.CACHE_FILE = ".session_cache"
        self.CACHE_MAX_AGE_HOURS = 8

    def _load_cached_token(self) -> Optional[str]:
        """Load token from cache if valid"""
        import json as _json
        import time as _time

        print("[AUTH CACHE] Checking for cached token...")
        print(f"[AUTH CACHE] Cache file exists: {os.path.exists(self.CACHE_FILE)}")
        if not os.path.exists(self.CACHE_FILE):
            return None

        try:
            with open(self.CACHE_FILE, "r", encoding="utf-8") as f:
                cache = _json.load(f)

            print(f"[AUTH CACHE] Loaded: {cache}")

            cached_time = cache.get("timestamp", 0)
            age_hours = (time.time() - cached_time) / 3600
            if age_hours > self.CACHE_MAX_AGE_HOURS:
                print(f"[AUTH] Cache expired ({age_hours:.1f} hours old)")
                try:
                    os.remove(self.CACHE_FILE)
                except Exception:
                    pass
                return None

            token = cache.get("token")
            base_url = cache.get("base_url")

            print(f"[AUTH CACHE] Base URL match: {base_url} == {self.base_url}")

            # Ensure cached token is for the same base_url
            if base_url and base_url != self.base_url:
                print(f"[AUTH] Cache entry base_url mismatch: {base_url} != {self.base_url}")
                return None

            # Quick validation
            if token and self._validate_token(token):
                print(f"[AUTH] Using cached token ({age_hours:.1f} hours old)")
                return token
            else:
                print("[AUTH] Cached token invalid, will re-login")
                try:
                    os.remove(self.CACHE_FILE)
                except Exception:
                    pass
                return None

        except Exception as e:
            print(f"[AUTH] Cache read error: {e}")
            return None

    def _save_token_to_cache(self, token: str) -> None:
        """Save token to cache"""
        import json as _json
        import time as _time

        cache = {"token": token, "base_url": self.base_url, "timestamp": time.time()}
        try:
            with open(self.CACHE_FILE, "w", encoding="utf-8") as f:
                _json.dump(cache, f)
            print("[AUTH] Token saved to cache")
        except Exception as e:
            print(f"[AUTH] Failed to save token cache: {e}")

    def _validate_token(self, token: str) -> bool:
        """Quick check if token is still valid"""
        try:
            headers = {"Cookie": f"JSESSIONID={token}"}
            url = f"{self.base_url}/REST/central/user/session"
            r = requests.get(url, headers=headers, verify=_VERIFY, timeout=10)
            return r.status_code == 200
        except Exception:
            return False
    def login(self, email: str, password: str) -> str:
        """Login using API and return bearer/JSESSION token.

        Flow:
        1) Try cached token
        2) Try API login (central -> sso)
        3) Fallback to UI login
        """
        # 1) Try cached token first
        cached = self._load_cached_token()
        if cached:
            self._token = cached
            self._token_expiry = time.time() + 1800
            print("[AUTH] Returning cached token")
            return cached

        # 2) If in-memory token still fresh, use it
        if self._token and time.time() < self._token_expiry - 30:
            return self._token

        payload = {"username": email, "password": password}
        masked = {"username": email, "password": "***"}

        # Try API login (central then SSO). If anything goes wrong, fall back to UI.
        try:
            central_url = f"{self.base_url}/REST/central/user/auth/login"
            print(f"AUTH TRY central -> url={central_url} body={masked}")
            r = requests.post(central_url, json=payload, timeout=15, verify=_VERIFY)
            print(f"AUTH RESP central -> status={r.status_code} body={r.text[:800]}")

            # If central not found, try SSO
            if r.status_code == 404:
                sso_url = f"{self.base_url}/REST/sso/login"
                print(f"AUTH FALLBACK -> trying SSO url={sso_url} body={masked}")
                r2 = requests.post(sso_url, json=payload, timeout=15, verify=_VERIFY)
                print(f"AUTH RESP sso -> status={r2.status_code} body={r2.text[:800]}")
                r2.raise_for_status()
                body = r2.json()
                token = body.get("token") or body.get("access_token") or body.get("data", {}).get("token")
            else:
                r.raise_for_status()
                body = r.json()
                token = body.get("token") or body.get("access_token") or body.get("data", {}).get("token")

            if token:
                self._token = token
                self._token_expiry = time.time() + 1800
                try:
                    self._save_token_to_cache(self._token)
                except Exception:
                    pass
                return token
            else:
                print("[AUTH] API login did not return a token; will try UI fallback")
        except Exception as e:
            print(f"[AUTH] API login failed: {e}; will try UI fallback")

        # 3) Fallback to UI login
        try:
            print("[AUTH] Falling back to UI login")
            token = self.login_via_ui(email, password)
            if token:
                self._token = token
                self._token_expiry = time.time() + 1800
                try:
                    self._save_token_to_cache(self._token)
                except Exception:
                    pass
                return token
        except Exception as e:
            print(f"[AUTH] UI login failed: {e}")
            raise

        raise RuntimeError("All login methods failed to obtain a token")

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
                # Call the LoginPage.login which fills credentials and handles reCAPTCHA
                print(f"DEBUG: Calling LoginPage.login() with user={email}")
                login_page.login(email, password)

                # Click login button after ReCAPTCHA is handled
                try:
                    login_page.click_login_button()
                except Exception as e:
                    print(f"[UI LOGIN] click_login_button() raised: {e}")

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
        try:
            # persist UI-obtained token to cache so subsequent runs reuse it
            self._save_token_to_cache(self._token)
        except Exception:
            pass

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
