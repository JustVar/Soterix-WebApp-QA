# conftest.py
import importlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict

import pytest

from config.base_config import config  # dict resolved from ENV

# Register plugins
pytest_plugins = ['plugins.qatouch_reporter', 'plugins.verification_runner']

# Logging (env/tenant resolution)
LOG_FILE = os.path.join("logs", "env_config.log")
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

def pytest_addoption(parser):
    """Register the opt-in required to run hardware-disrupting tests."""
    parser.addoption(
        "--run-destructive",
        action="store_true",
        default=False,
        help="Run tests marked 'destructive'. These interrupt real hardware - "
             "e.g. rebooting every camera in the C2C registry. Off by default.",
    )


def pytest_collection_modifyitems(config, items):
    """Skip destructive tests unless they were explicitly asked for.

    A plain `pytest tests/ui/c2c/` parametrises over every enabled camera in
    the registry, so an unguarded reboot test takes out the whole lab fleet.
    Running it has to be a deliberate act, not the default.
    """
    if config.getoption("--run-destructive"):
        return
    skip = pytest.mark.skip(
        reason="destructive: disrupts real hardware. Pass --run-destructive to run it."
    )
    for item in items:
        if "destructive" in item.keywords:
            item.add_marker(skip)


def _from_env_or_config(env_key: str, cfg_key: str, default: str = "") -> str:
    """Environment var takes precedence; fallback to active env config dict key."""
    return os.environ.get(env_key) or config.get(cfg_key, default)

def resolve_tenant_data(tenant_name: str) -> dict[str, str]:
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

def build_no_tenant_login_data() -> dict[str, str]:
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
# API testing moved to the Soterix-API-QA repo (see docs/REPO_SPLIT_PLAN.md).
# This repo is UI automation + manual test cases only.
# ----------------


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


@pytest.fixture
def authenticated_page(browser, auth_state_path, base_url, login_data):
    """Provide a Playwright page with cached authentication.

    Uses pytest-playwright's browser fixture to avoid event loop conflicts.
    First run: Logs in via UI and saves storage state to file.
    Subsequent runs: Loads cached state (skips login entirely).
    """
    import os

    context = None
    page = None

    # Check if we have cached auth state
    if os.path.exists(auth_state_path):
        print(f"[AUTH] Loading cached session from {auth_state_path}")
        try:
            context = browser.new_context(storage_state=auth_state_path)
            page = context.new_page()
            page.goto(base_url)
            page.wait_for_load_state('domcontentloaded', timeout=30000)

            # Fast session validation - check URL and key elements
            # Wait briefly for app to initialize, then check state
            try:
                page.wait_for_timeout(1500)  # Brief wait for React to hydrate

                # Check if we're on login page (session expired)
                if '/auth/login' in page.url:
                    raise Exception("Redirected to login - session invalid")

                # Check for login form (another sign of expired session)
                if page.locator("input[type='email']").is_visible():
                    raise Exception("Login form visible - session invalid")

                # Session is valid - verify nav element exists
                nav = page.locator("text=Views").first
                nav.wait_for(state="visible", timeout=5000)
                print("[AUTH] Cached session is valid")
                yield page
                page.close()
                context.close()
                return

            except Exception as e:
                print(f"[AUTH] Cached session expired: {e}")
                page.close()
                context.close()
                os.remove(auth_state_path)
        except Exception as e:
            print(f"[AUTH] Failed to load cached session: {e}")
            if os.path.exists(auth_state_path):
                try:
                    os.remove(auth_state_path)
                except Exception:
                    pass

    # No valid cache - perform fresh login
    print("[AUTH] Performing fresh login...")
    context = browser.new_context()
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

    yield page
    page.close()
    context.close()


def pytest_sessionfinish(session, exitstatus):
    """Email the HTML report after the session finishes, when opted in.

    Opt-in via SEND_TEST_REPORT=1. The recipient must be set explicitly in
    REPORT_RECIPIENT - there is deliberately no default address so a report
    can never be mailed to someone unexpected.
    """
    if not os.environ.get("SEND_TEST_REPORT"):
        return

    recipient = os.environ.get("REPORT_RECIPIENT")
    if not recipient:
        print("\n[WARNING] SEND_TEST_REPORT is set but REPORT_RECIPIENT is empty - "
              "no report sent. Set REPORT_RECIPIENT in .env.")
        return

    try:
        from tools.email_client import GraphEmailClient
        report_path = Path("reports/report.html")
        if not report_path.exists():
            print(f"\n[WARNING] No report at {report_path} - nothing to send.")
            return

        html = report_path.read_text(encoding="utf-8", errors="replace")
        status = "PASSED" if exitstatus == 0 else "FAILED"

        body = f"""
        <h2>Test Run Report</h2>
        <p><strong>Status:</strong> {status}</p>
        <p><strong>Time:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <hr>
        {html}
        """

        client = GraphEmailClient()
        client.send_email(
            to=recipient,
            subject=f"Test Report - {status}",
            body_html=body,
            attachments=[str(report_path)],
        )
        print(f"\n[SUCCESS] Test report sent to {recipient}")
    except Exception as e:
        print(f"\n[WARNING] Failed to send test report: {e}")
