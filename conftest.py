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


@pytest.fixture(scope="session")
def api_base_url(env_config):
    return env_config.get('base_url')


@pytest.fixture(scope="session")
def api_auth_helper(api_base_url):
    """Provide a single `AuthHelper` instance for the entire test session."""
    helper = auth_helper_mod.AuthHelper(api_base_url)
    print("[FIXUP] Created session-scoped AuthHelper")
    return helper


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
def test_channel_ids(camera_api, test_site_id):
    """Return channel ids for the selected test site."""
    try:
        tree = camera_api.get_camera_tree(test_site_id)
    except Exception:
        return [1]
    ids = set()
    # tree may be dict or list; try common shapes
    if isinstance(tree, dict):
        # common wrapper 'result'
        candidates = tree.get("result") or tree.get("channels") or []
    elif isinstance(tree, list):
        candidates = tree
    else:
        candidates = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        for k in ("channelId", "id", "channel_id"):
            v = item.get(k)
            if isinstance(v, int):
                ids.add(v)
    if not ids:
        # fallback
        return [1]
    return sorted(list(ids))
