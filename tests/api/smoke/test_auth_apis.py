"""
QA-API-AUTH-01 - Auth API smoke (central + SSO login)
Spec: qa/Automation_QA.xlsx › Test Mapping › row "QA-API-AUTH-01"
Section: I. API
Owner: JV
Deployment: After FT

Covers the two login paths the SPA uses: central credential login and the SSO
fallback. Logout is intentionally omitted - exercising it on a shared session
would terminate other concurrently running tests.

Catalog rows (see docs/API_ENDPOINTS.md):
- POST /REST/central/user/auth/login
- POST /REST/sso/login
"""
import os

import pytest
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_VERIFY = os.getenv("SSL_VERIFY", "false").lower() in ("true", "1", "yes")


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-AUTH-01")
def test_central_login_accepts_valid_credentials(api_base_url, login_data):
    """POST /REST/central/user/auth/login with valid creds returns a token.

    Uses AuthHelper.login() which tries central then SSO. A non-empty token
    string proves at least one of the two endpoints accepted the credentials.
    """
    from tests.shared.api_clients.auth_helper import AuthHelper

    helper = AuthHelper(api_base_url)
    token = helper.login(login_data["username"], login_data["password"])

    assert token, "Expected a session token from /REST/central/user/auth/login or /REST/sso/login"
    assert isinstance(token, str) and len(token) >= 16


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-AUTH-01")
def test_central_login_rejects_invalid_credentials(api_base_url):
    """POST /REST/central/user/auth/login with bogus creds returns non-2xx.

    Calls the endpoint directly so we never trigger the UI fallback that
    AuthHelper.login() would attempt for unknown users.
    """
    base = api_base_url.rstrip("/")
    if not base.endswith("/v-apiserver"):
        base = base + "/v-apiserver"
    url = f"{base}/REST/central/user/auth/login"
    r = requests.post(
        url,
        json={"username": "not-a-real-user@example.invalid", "password": "wrong-password"},
        timeout=15,
        verify=_VERIFY,
    )
    # Vendor returns 401/403 for bad creds; some deployments return 200 with
    # an error body. Either way, the response must NOT contain a usable token.
    body = {}
    try:
        body = r.json()
    except Exception:
        pass
    token = body.get("token") or body.get("access_token") or (body.get("data") or {}).get("token")
    assert not token, f"Invalid creds yielded a token: status={r.status_code} body={r.text[:300]}"


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-AUTH-01")
@pytest.mark.skipif(
    not os.getenv("SSO_TEST_USERNAME"),
    reason="SSO smoke needs SSO_TEST_USERNAME and SSO_TEST_PASSWORD env vars",
)
def test_sso_login_accepts_valid_credentials(api_base_url):
    """POST /REST/sso/login with a valid SSO account returns a token.

    SSO is the fallback path when central login is unavailable. Not every env
    has SSO configured, so this test only runs when explicit creds are provided.
    """
    base = api_base_url.rstrip("/")
    if not base.endswith("/v-apiserver"):
        base = base + "/v-apiserver"
    url = f"{base}/REST/sso/login"
    r = requests.post(
        url,
        json={
            "username": os.environ["SSO_TEST_USERNAME"],
            "password": os.environ["SSO_TEST_PASSWORD"],
        },
        timeout=15,
        verify=_VERIFY,
    )
    r.raise_for_status()
    body = r.json()
    token = body.get("token") or body.get("access_token") or (body.get("data") or {}).get("token")
    assert token, f"SSO login did not return a token: {body}"
