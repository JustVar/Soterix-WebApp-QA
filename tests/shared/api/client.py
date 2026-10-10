"""Small client for the internal /v-apiserver REST API.

The UI tests use it to build and remove test data (camera groups,
bookmarks, saved views) without driving the browser through screens
the test does not prove. It stays inside this repo: the API test repo
is a separate project and nothing here imports from it.

Every response is an envelope: {status, code, description, message,
result}. The `message` text is not a signal. `addgroup` answers
"Successfully Retrieved!", and a bookmark DELETE answers "Successfully
deleted!" while the row stays in the list with `deletedAt` set. The
client checks `code` and returns `result`. The caller confirms the
write with a read (grouptree, the bookmark list) before relying on it.

Verified against QA on 2026-08-24.
"""
from __future__ import annotations

import hashlib
import os
import warnings

import requests
import urllib3

# The web client sends one fixed display name on login, the same for every
# account. The account is `accountid`. The name is a server setting, so it
# lives in .env as LOGIN_USERNAME_LABEL, not in code. The login answers
# code 200 with status 2002, so `status` is not an "OK" check (verified
# 2026-08-24).
LABEL_SETTING = "LOGIN_USERNAME_LABEL"
# The tenant answers a dead session with this status (code 401) and the
# message "Session expired! Re-login required!" (measured 09/15/2026).
SESSION_EXPIRED_STATUS = 3113
LOGIN_PATH = "/REST/central/user/login"
TIMEOUT_S = 30


class ApiError(Exception):
    """A request the API refused, with the envelope fields."""

    def __init__(self, status, code, message, path):
        self.status = status
        self.code = code
        self.message = message
        self.path = path
        super().__init__(f"{path}: code={code} status={status} {message}")


class LoginConfigError(RuntimeError):
    """A login setting is missing, so no request was sent."""


def login_username_label() -> str:
    """The fixed display name the login carries, read from .env at call time.

    Blank raises LoginConfigError: the tenant answers a blank name with the
    same refusal as a wrong password, which sends the reader to the wrong fix.
    """
    label = os.environ.get(LABEL_SETTING, "").strip()
    if not label:
        raise LoginConfigError(f"{LABEL_SETTING} is empty in .env, and the login needs it")
    return label


class InternalApi:
    """One logged-in session against `{base_url}/v-apiserver`."""

    def __init__(self, base_url: str, site_id: int, session=None, verify: bool = False):
        self.base_url = base_url.rstrip("/") + "/v-apiserver"
        self.site_id = int(site_id)
        self.site_name: str | None = None
        self.user: str | None = None
        self.session = session or requests.Session()
        self.session.verify = verify
        self._password: str | None = None

    def login(self, user: str, password: str) -> str:
        """Log in and keep the JSESSIONID cookie on the session.

        The password is kept so a session the tenant expires mid-run can
        be renewed; see _request.
        """
        body = {
            "accountid": user,
            "username": login_username_label(),
            "password": hashlib.sha512(password.encode()).hexdigest(),
        }
        result = self.post("/REST/central/user/login", body)
        token = result[0]["JSESSIONID"]
        self.session.headers["Cookie"] = f"JSESSIONID={token}"
        self.user = user
        self._password = password
        return token

    def get(self, path: str, params: dict | None = None) -> list:
        return self._request("GET", path, params=params)

    def post(self, path: str, json=None, *, params: dict | None = None, files=None) -> list:
        return self._request("POST", path, json=json, params=params, files=files)

    def delete(self, path: str) -> list:
        return self._request("DELETE", path)

    def _request(self, method: str, path: str, **kwargs) -> list:
        """Send the request and return the envelope's `result`.

        Raises ApiError when `code` is not 200 or the body is not JSON.
        A session the tenant expired is renewed once and the request is
        sent again: the fixture logs in at session start and a full run
        outlives the token (status 3113 after about 28 minutes, which
        failed a test for a reason that was not the app's behaviour).
        """
        try:
            return self._send(method, path, **kwargs)
        except ApiError as first:
            if not self._is_expired_session(first) or not self._can_relogin(path):
                raise
            self.login(self.user, self._password)
            return self._send(method, path, **kwargs)

    @staticmethod
    def _is_expired_session(error: ApiError) -> bool:
        """The tenant's own answer for a dead session: status 3113, or a
        message naming it. The code is 401 on both."""
        return error.status == SESSION_EXPIRED_STATUS or (
            "session expired" in str(error.message or "").lower())

    def _can_relogin(self, path: str) -> bool:
        """A renewal needs the account, the password and a path that is
        not the login itself (which would recurse)."""
        return bool(self.user and self._password) and not path.endswith(LOGIN_PATH)

    def _send(self, method: str, path: str, **kwargs) -> list:
        # QA serves a self-signed certificate. The warning is silenced
        # per request: pytest resets the warning filters after every
        # test, so a one-time disable at construction lapses for the
        # session client and the next test reports it.
        with warnings.catch_warnings():
            if not self.session.verify:
                warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)
            response = self.session.request(
                method, self.base_url + path, timeout=TIMEOUT_S, **kwargs
            )
        try:
            envelope = response.json()
        except ValueError:
            raise ApiError(response.status_code, None, response.text[:200], path) from None
        if envelope.get("code") != 200:
            raise ApiError(
                envelope.get("status"), envelope.get("code"), envelope.get("message"), path
            )
        result = envelope.get("result")
        return [] if result is None else result
