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
    Credentials source:
      - If TENANT is set -> load data/<TENANT>_login_data.py
      - Else -> 'no-tenant' mode via env vars or env config defaults
    """
    tenant = (os.environ.get("TENANT") or "").strip()
    if tenant:
        logging.info(f"[TENANT CONFIG] Using tenant file for: {tenant}")
        return resolve_tenant_data(tenant)

    logging.info("[TENANT CONFIG] No tenant specified; using no-tenant mode.")
    return build_no_tenant_login_data()

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


@pytest.fixture(scope="session")
def api_base_url(env_config):
    return env_config.get('base_url')


@pytest.fixture(scope="session")
def api_auth_token(api_base_url, login_data):
    helper = auth_helper_mod.AuthHelper(api_base_url)
    try:
        token = helper.login(login_data['username'], login_data['password'])
        return token
    except Exception as e:
        print(f"API login failed, falling back to UI login: {e}")
        # Use Playwright-driven UI login to obtain a token when API auth is broken
        token = helper.login_via_ui(login_data['username'], login_data['password'])
        return token


@pytest.fixture
def dashboard_api(api_base_url, api_auth_token):
    return dashboard_mod.DashboardAPI(api_base_url, api_auth_token)


@pytest.fixture
def camera_api(api_base_url, api_auth_token):
    return camera_mod.CameraAPI(api_base_url, api_auth_token)


@pytest.fixture
def user_api(api_base_url, api_auth_token):
    return user_mod.UserAPI(api_base_url, api_auth_token)


@pytest.fixture
def search_api(api_base_url, api_auth_token):
    return search_mod.SearchAPI(api_base_url, api_auth_token)


@pytest.fixture
def test_site_id():
    return 1


@pytest.fixture
def test_channel_ids():
    return [1, 2, 3, 4, 5, 6]
