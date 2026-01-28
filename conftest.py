# conftest.py
import os
import importlib
import logging
import pytest
from typing import Dict
from config.base_config import config  # dict resolved from ENV

# Logging (env/tenant resolution)
LOG_FILE = os.path.join("logs", "env_config.log")
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

def _from_env_or_config(env_key: str, cfg_key: str, default: str = "") -> str:
    """Environment var takes precedence; fallback to active env config dict key."""
    return os.environ.get(env_key) or config.get(cfg_key, default)

def resolve_tenant_data(tenant_name: str) -> Dict[str, str]:
    """
    Load tenant-specific login data from data/<tenant_name>_login_data.py
    (must define `login_data` dict).
    """
    try:
        module = importlib.import_module(f"data.{tenant_name}_login_data")
        return module.login_data
    except ModuleNotFoundError as e:
        raise Exception(
            f"Tenant login data file not found: data/{tenant_name}_login_data.py"
        ) from e

def build_no_tenant_login_data() -> Dict[str, str]:
    """
    Build login data for 'no-tenant' mode.
    Priority:
      1) AUTO_USER / AUTO_PASSWORD env vars (+ optional EXPECTED_LANDING)
      2) default_user / default_password from the active env config
    """
    username = _from_env_or_config("AUTO_USER", "default_user")
    password = _from_env_or_config("AUTO_PASSWORD", "default_password")
    expected_landing = os.environ.get("EXPECTED_LANDING", "/dashboard")

    missing = []
    if not username:
        missing.append("AUTO_USER or config['default_user']")
    if not password:
        missing.append("AUTO_PASSWORD or config['default_password']")
    if missing:
        hints = "; ".join(missing)
        raise RuntimeError(
            "No-tenant login requires automation credentials. "
            f"Please set {hints}."
        )

    return {"username": username, "password": password, "expected_landing": expected_landing}

@pytest.fixture(scope="session")
def env_config():
    """Resolved environment configuration dict (from ENV)."""
    logging.info(f"[ENV CONFIG] Loaded config for: {os.environ.get('ENV')}")
    return config


@pytest.fixture(scope="session")
def base_url(env_config):
    """Provide a `base_url` fixture for tests that expect it.

    Many tests call `base_url + '/auth/login'`; return the site root from
    the active env config so tests can append paths as needed.
    """
    return env_config.get("base_url", "")

@pytest.fixture(scope="session")
def login_data():
    """
    Credentials source (per-user): read from environment variables `QA_USER` and `QA_PASSWORD`.
    This fixture requires these to be set (e.g., via a `.env` file).
    """
    user = os.environ.get("QA_USER")
    password = os.environ.get("QA_PASSWORD")
    if not user or not password:
        raise ValueError("QA_USER and QA_PASSWORD must be set in environment or .env file. See .env.template")
    logging.info("[TENANT CONFIG] Using QA_USER from environment")
    return {"username": user, "password": password, "expected_landing": os.environ.get("EXPECTED_LANDING", "/dashboard")} 

@pytest.fixture
def login(page, env_config, login_data):
    """Perform login and wait for expected landing."""
    page.goto(env_config["base_url"])
    page.fill("input[type='email']", login_data["username"])
    page.fill("input[type='password']", login_data["password"])
    page.click("button[type='submit']")
    page.wait_for_url(f"**{login_data['expected_landing']}**")
    return page


@pytest.fixture
def tenant_login(login_data):
    """Backward-compatible alias for tests using the old `tenant_login` fixture name.

    Returns the same dict as `login_data` so tests that expect
    `tenant_login[...]` continue to work unchanged.
    """
    return login_data


# ----------------
# API Testing Fixtures
# ----------------
import tests.shared.api_clients.auth_helper as auth_helper_mod
import tests.shared.api_clients.dashboard_api as dashboard_mod
import tests.shared.api_clients.camera_api as camera_mod
import tests.shared.api_clients.user_api as user_mod
import tests.shared.api_clients.search_api as search_mod
import tests.shared.api_clients.site_helper as site_helper
import tests.shared.api_clients.discovery_helper as discovery_mod
import tests.shared.api_clients.enterprise_helper as enterprise_mod


@pytest.fixture(scope="session")
def api_base_url(env_config):
    # Prefer explicit api_base_url (includes /v-apiserver) if provided by env config
    return env_config.get('api_base_url', env_config.get('base_url'))


@pytest.fixture(scope="session")
def api_auth_helper(api_base_url):
    """Provide a single `AuthHelper` instance for the entire test session."""
    helper = auth_helper_mod.AuthHelper(api_base_url)
    print("[FIXUP] Created session-scoped AuthHelper")
    return helper


# ----------------
# Session-Cached Authentication (Playwright Storage State)
# ----------------
# This optimization saves ~345 seconds on test runs by caching auth state.
# See docs/SESSION_CACHING_IMPLEMENTATION.md for details.

AUTH_STATE_FILE = ".auth_state.json"


@pytest.fixture(scope="session")
def auth_state_path():
    """Path to the cached authentication state file."""
    return AUTH_STATE_FILE


@pytest.fixture(scope="session")
def session_browser():
    """Session-scoped browser instance shared across all UI tests."""
    from playwright.sync_api import sync_playwright

    pw = sync_playwright().start()
    browser = pw.chromium.launch(headless=True)
    yield browser
    browser.close()
    pw.stop()


@pytest.fixture(scope="session")
def authenticated_context(session_browser, auth_state_path, base_url, login_data):
    """Session-scoped authenticated browser context.

    First run: Logs in via UI and saves storage state to file.
    Subsequent runs: Loads cached state (skips login entirely).
    """
    import os
    import time

    # Check if we have cached auth state
    if os.path.exists(auth_state_path):
        print(f"[AUTH] Loading cached session from {auth_state_path}")
        try:
            context = session_browser.new_context(storage_state=auth_state_path)
            # Verify the session is still valid
            page = context.new_page()
            page.goto(base_url)
            page.wait_for_load_state('domcontentloaded', timeout=30000)
            # Give app time to redirect if session invalid
            time.sleep(2)

            # If we're not redirected to login, session is valid
            if '/auth/login' not in page.url:
                print("[AUTH] Cached session is valid")
                page.close()
                yield context
                context.close()
                return
            else:
                print("[AUTH] Cached session expired, re-authenticating...")
                page.close()
                context.close()
                # Delete stale cache
                os.remove(auth_state_path)
        except Exception as e:
            print(f"[AUTH] Failed to load cached session: {e}")
            if os.path.exists(auth_state_path):
                os.remove(auth_state_path)

    # No valid cache - perform fresh login
    print("[AUTH] Performing fresh login...")
    context = session_browser.new_context()
    page = context.new_page()

    try:
        from tests.shared.pages.login_page import LoginPage
        lp = LoginPage(page, base_url)
        lp.login(login_data['username'], login_data['password'])

        # Wait for login to complete (not on login page anymore)
        page.wait_for_function(
            "() => !window.location.href.includes('/auth/login')",
            timeout=60000
        )
        # Use domcontentloaded instead of networkidle (app has persistent connections)
        page.wait_for_load_state('domcontentloaded', timeout=30000)

        # Save the authenticated state
        context.storage_state(path=auth_state_path)
        print(f"[AUTH] Session saved to {auth_state_path}")

    except Exception as e:
        print(f"[AUTH] Login failed: {e}")
        raise
    finally:
        page.close()

    yield context
    context.close()


@pytest.fixture
def authenticated_page(authenticated_context, base_url):
    """Provide a Playwright page from the authenticated session context.

    This is function-scoped so each test gets a fresh page,
    but they all share the same authenticated context (session-scoped).
    The page is navigated to base_url so tests start on the main app.
    """
    page = authenticated_context.new_page()
    page.goto(base_url)
    page.wait_for_load_state('domcontentloaded', timeout=30000)
    yield page
    page.close()


@pytest.fixture(scope="session")
def api_auth_token(api_auth_helper, login_data):
    # Use the shared session-scoped AuthHelper
    helper = api_auth_helper
    print("[FIXUP] api_auth_token fixture starting; using shared AuthHelper")
    try:
        token = helper.login(login_data['username'], login_data['password'])
        print("[FIXUP] api_auth_token obtained token")
        return token
    except Exception as e:
        print(f"API login failed in fixture, falling back to UI login: {e}")
        token = helper.login_via_ui(login_data['username'], login_data['password'])
        return token


@pytest.fixture(scope="session")
def dashboard_api(api_base_url, api_auth_token):
    return dashboard_mod.DashboardAPI(api_base_url, api_auth_token)


@pytest.fixture(scope="session")
def camera_api(api_base_url, api_auth_token):
    return camera_mod.CameraAPI(api_base_url, api_auth_token)


@pytest.fixture(scope="session")
def user_api(api_base_url, api_auth_token):
    return user_mod.UserAPI(api_base_url, api_auth_token)


@pytest.fixture(scope="session")
def search_api(api_base_url, api_auth_token):
    return search_mod.SearchAPI(api_base_url, api_auth_token)


@pytest.fixture(scope="session")
def enterprise_helper(api_base_url, api_auth_token):
    """Session-scoped EnterpriseHelper for dynamic enterpriseId lookup."""
    from tests.shared.api_clients.enterprise_helper import EnterpriseHelper
    return EnterpriseHelper(api_base_url, api_auth_token)


@pytest.fixture(scope="session")
def site_discovery(api_base_url, api_auth_token):
    """Session-scoped SiteDiscovery for auto-discovering user sites."""
    from tests.shared.api_clients.site_discovery import SiteDiscovery
    return SiteDiscovery(api_base_url, api_auth_token)


@pytest.fixture(scope="session")
def discovered_site(site_discovery, login_data):
    """Auto-discovered default site for the logged-in user."""
    user_email = login_data.get("username")
    site = site_discovery.get_default_site(user_email)
    if not site:
        pytest.skip(f"No sites found for user {user_email}")
    return site


@pytest.fixture(scope="session")
def discovered_site_id(discovered_site):
    """Auto-discovered site ID."""
    return discovered_site.get("siteId")


@pytest.fixture(scope="session")
def discovered_enterprise_id(discovered_site):
    """Auto-discovered enterprise ID from the user's default site."""
    return discovered_site.get("enterpriseId")


@pytest.fixture(scope="session")
def test_enterprise_id(enterprise_helper, test_site_id):
    """Dynamically fetched enterpriseId for the test site."""
    return enterprise_helper.get_enterprise_id(test_site_id)


@pytest.fixture(scope="session")
def test_site_id(user_api, camera_api, login_data):
    """Discover a site id the logged-in user can access.

    Steps:
    - Attempt to read assigned sites via `get_available_sites`.
    - If none found, probe a small range of site ids with `camera_api.get_camera_tree`
      and return the first site id that succeeds.
    """
    # Prefer known QA site for QA environment to speed up tests
    import os as _os
    if _os.environ.get("ENV", "").lower() == "qa":
        return 110

    sites = site_helper.get_available_sites(user_api)
    if sites:
        first = sites[0]
        for k in ("siteId", "site_id", "id"):
            if isinstance(first, dict) and k in first:
                return first.get(k)
    # If no sites returned from API, probe candidate site ids (small range)
    for candidate in range(1, 51):
        try:
            tree = camera_api.get_camera_tree(candidate)
            # If no exception and response seems valid, accept candidate
            if tree:
                return candidate
        except Exception:
            continue
    # As a last resort, if using known qa-lab account, return a conservative default
    username = login_data.get("username", "")
    if "qa-lab" in username:
        # Driver Site is typically on a different edge; prefer candidate 2
        return 2
    raise RuntimeError("Unable to discover a test site id for the current user")


@pytest.fixture(scope="session")
def discovery_helper(api_base_url, api_auth_token):
    """Session-scoped DiscoveryHelper wrapping a simple BaseAPI client."""
    from tests.shared.api_clients.base_api_client import BaseAPIClient
    client = BaseAPIClient(api_base_url, api_auth_token)
    return discovery_mod.DiscoveryHelper(client)


@pytest.fixture(scope="session")
def test_channel_ids(discovery_helper, test_site_id):
    """Return channel ids for the selected test site, preferring snapshot-capable channels."""
    # Prefer channels that expose a snapshot URL
    try:
        snapshot_ids = discovery_helper.get_snapshot_capable_channels(test_site_id)
    except Exception:
        snapshot_ids = []
    if snapshot_ids:
        return sorted(snapshot_ids)

    try:
        ids = discovery_helper.get_site_channels(test_site_id)
    except Exception:
        ids = []
    if ids:
        return sorted(ids)

    # fallback
    return [1]