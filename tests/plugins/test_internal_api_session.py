"""Pins for the internal API client's session renewal.

The `api` fixture logs in once per session, and a full UI run outlives the
tenant's token: on 09/15/2026 a test failed 28 minutes into a full UI run
with status 3113, "Session expired! Re-login required!", which is not the
app behaviour that test exists to prove. The client renews the session once
and sends the request again.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.shared.api.client import ApiError, InternalApi  # noqa: E402

EXPIRED = {"code": 401, "status": 3113, "message": "Session expired! Re-login required!", "result": None}
LOGIN_OK = {"code": 200, "status": 2002, "message": "OK", "result": [{"JSESSIONID": "fresh-token"}]}
DATA_OK = {"code": 200, "status": 2000, "message": "OK", "result": [{"siteId": 16}]}


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.status_code = 200
        self.text = str(payload)

    def json(self):
        return self._payload


class FakeSession:
    """Answers each request from a scripted queue and records what it sent."""

    def __init__(self, payloads):
        self.payloads = list(payloads)
        self.sent: list[tuple[str, str, str | None]] = []
        self.headers: dict[str, str] = {}
        self.verify = False

    def request(self, method, url, **kwargs):
        self.sent.append((method, url, self.headers.get("Cookie")))
        return FakeResponse(self.payloads.pop(0))


@pytest.fixture(autouse=True)
def _login_label(monkeypatch):
    """The login needs its display name from .env; these pins set a placeholder."""
    monkeypatch.setenv("LOGIN_USERNAME_LABEL", "Example Label")


def _client(payloads) -> InternalApi:
    return InternalApi("https://host", 16, session=FakeSession(payloads))


def test_an_expired_session_is_renewed_and_the_request_resent():
    """The first answer is the expiry, then a login, then the request again with the new cookie."""
    api = _client([LOGIN_OK, EXPIRED, LOGIN_OK, DATA_OK])
    api.login("user@example.com", "pw")
    api.session.headers["Cookie"] = "JSESSIONID=stale"
    assert api.get("/REST/site/16/location/tree") == [{"siteId": 16}]
    paths = [url.rsplit("/v-apiserver", 1)[-1] for _m, url, _c in api.session.sent]
    assert paths[1:] == ["/REST/site/16/location/tree", "/REST/central/user/login",
                         "/REST/site/16/location/tree"]
    assert api.session.sent[1][2] == "JSESSIONID=stale"
    assert api.session.sent[-1][2] == "JSESSIONID=fresh-token"


def test_the_renewal_happens_once_and_the_second_expiry_raises():
    """A tenant that keeps refusing is reported, not retried forever."""
    api = _client([LOGIN_OK, EXPIRED, LOGIN_OK, EXPIRED])
    api.login("user@example.com", "pw")
    with pytest.raises(ApiError) as caught:
        api.get("/REST/site/16/location/tree")
    assert caught.value.status == 3113


def test_a_message_naming_the_expiry_counts_even_without_the_status():
    """The tenant has worded this two ways; the message is the second signal."""
    worded = {"code": 401, "status": 9999, "message": "session expired", "result": None}
    api = _client([LOGIN_OK, worded, LOGIN_OK, DATA_OK])
    api.login("user@example.com", "pw")
    assert api.get("/REST/site/16") == [{"siteId": 16}]


def test_an_ordinary_error_is_not_retried():
    """A refused write raises on the first answer; only an expiry renews."""
    refused = {"code": 400, "status": 3139, "message": "Required payload not found!", "result": None}
    api = _client([LOGIN_OK, refused])
    api.login("user@example.com", "pw")
    with pytest.raises(ApiError) as caught:
        api.post("/REST/clipbookmark", {})
    assert caught.value.code == 400
    assert len(api.session.sent) == 2


def test_a_failed_login_does_not_recurse():
    """An expiry answered by the login call itself raises instead of looping."""
    api = _client([EXPIRED])
    api.user, api._password = "user@example.com", "pw"
    with pytest.raises(ApiError):
        api.post("/REST/central/user/login", {})
    assert len(api.session.sent) == 1


def test_a_client_that_never_logged_in_raises_the_expiry():
    """Without an account and password there is nothing to renew with."""
    api = _client([EXPIRED])
    with pytest.raises(ApiError):
        api.get("/REST/site")
    assert len(api.session.sent) == 1
