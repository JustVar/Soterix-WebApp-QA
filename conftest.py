# conftest.py
import importlib
import logging
from logging.handlers import RotatingFileHandler
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict

import pytest

from config.base_config import config  # dict resolved from ENV
from plugins.paths import fit_name

# Register plugins
pytest_plugins = ['plugins.qatouch_reporter', 'plugins.verification_runner', 'plugins.report_media',
                  'plugins.run_archive', 'plugins.single_run_guard',
                  'tests.shared.api.fixtures']

# Logging (env/tenant resolution)
LOG_FILE = os.path.join("logs", "env_config.log")
os.makedirs("logs", exist_ok=True)
# One rotating file: the log was appending for good and had reached 1.4 MB
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[RotatingFileHandler(LOG_FILE, maxBytes=512_000, backupCount=2)])

def pytest_addoption(parser):
    """Register the opt-in required to run hardware-disrupting tests."""
    parser.addoption(
        "--run-destructive",
        action="store_true",
        default=False,
        help="Run tests marked 'destructive'. These interrupt real hardware - "
             "e.g. rebooting every camera in the C2C registry. Off by default.",
    )


# Markers whose tests change hardware or tenant data, grouped by the
# config/env/ flag that must be True for them to run (prod: both False).
DELETE_MARKERS = ("destructive", "mutating")
WRITE_MARKERS = ("admin_users", "admin_rules", "admin_sites", "bookmark", "sequences")

# The collection hook receives pytest's own `config`, which shadows the
# env dict imported above. This alias keeps the dict reachable there.
ENV_SETTINGS = config


def env_skip_reason(keywords, settings, env_name: str) -> str | None:
    """Why the active environment refuses this test, or None to let it run.

    A missing flag counts as False, the same default base_config's
    is_write_allowed and is_delete_allowed use: an env file that says
    nothing about writes gets none.
    """
    for flag, markers in (("allow_delete", DELETE_MARKERS), ("allow_write", WRITE_MARKERS)):
        if settings.get(flag, False):
            continue
        for marker in markers:
            if marker in keywords:
                return (f"env {env_name}: {flag} is False in config/env/, so tests "
                        f"marked '{marker}' do not run here")
    return None


def pytest_collection_modifyitems(config, items):
    """Skip what this run may not execute.

    Destructive tests need --run-destructive: a plain `pytest tests/ui/c2c/`
    parametrises over every enabled camera in the registry, so an unguarded
    reboot test takes out the whole lab fleet. Running it has to be a
    deliberate act, not the default.

    The env guard has no opt-in flag. Prod is read-only by config, and
    --run-destructive does not lift that.
    """
    run_destructive = config.getoption("--run-destructive")
    destructive_skip = pytest.mark.skip(
        reason="destructive: disrupts real hardware. Pass --run-destructive to run it."
    )
    env_name = (os.environ.get("ENV") or "qa").strip().lower()
    for item in items:
        if not run_destructive and "destructive" in item.keywords:
            item.add_marker(destructive_skip)
        reason = env_skip_reason(item.keywords, ENV_SETTINGS, env_name)
        if reason:
            item.add_marker(pytest.mark.skip(reason=reason))


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
    """Active account credentials.

    Two sources, checked in this order:
    1. If the BOX env var is set, use that box's account from config/env/
       (for example BOX=india on ENV=qa). The box names the password variable
       to read from .env.
    2. Otherwise read QA_USER and QA_PASSWORD from .env. This is the default
       and matches how the team runs the suite today.
    """
    expected_landing = os.environ.get("EXPECTED_LANDING", "/dashboard")

    box = os.environ.get("BOX")
    if box:
        from config.base_config import get_credentials
        creds = get_credentials()
        if not creds.get("email") or not creds.get("password"):
            raise ValueError(
                f"BOX='{box}' is set but its credentials are incomplete. The "
                f"box's password variable is empty or missing in .env; see the "
                f"password_env key for this box in config/env/.")
        logging.info(f"[CREDENTIALS] Using box '{box}' account from env config")
        return {"username": creds["email"], "password": creds["password"],
                "expected_landing": expected_landing}

    user = os.environ.get("QA_USER")
    password = os.environ.get("QA_PASSWORD")
    if not user or not password:
        raise ValueError("QA_USER and QA_PASSWORD must be set in environment or .env file. See .env.template")
    logging.info("[CREDENTIALS] Using QA_USER from environment")
    return {"username": user, "password": password, "expected_landing": expected_landing}

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
# See docs/archive/SESSION_CACHING_IMPLEMENTATION.md for details.

AUTH_STATE_FILE = ".auth_state.json"

TRACE_DIR = Path("reports") / "artifacts"

# Stem cap for trace and video names. plugins/report_media.py predicts the
# trace name with the same sanitizer and cap, so change both together.
TRACE_NAME_MAX = 150

# Video clips record under the trace dir so pytest-playwright's session-start
# wipe of reports/artifacts/ clears them and run_archive's copy keeps them.
# A kept clip moves up next to its trace as <test>-video.webm.
VIDEO_DIR = TRACE_DIR / "videos"

# Same off values as plugins/report_media.py so one convention covers every
# switch: RECORD_VIDEO=off skips recording entirely.
_OFF_VALUES = ("off", "0", "false", "no")


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Stash each phase's report on the item so fixtures can see the outcome.

    Fixtures tear down after the test finishes, so `request.node.rep_call`
    is how `authenticated_page` knows whether to keep or discard its trace.
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


def _artifact_path(name: str, kind: str, suffix: str) -> Path:
    """reports/artifacts/<safe>-<kind><suffix> for a test node id.

    The stem is capped first. fit_name then keeps the absolute path within
    the Windows path cap: past it Playwright's save fails, the failure
    shows only as a printed line, and the evidence is lost.
    """
    safe = re.sub(r"[^\w.-]+", "-", name).strip("-")[:TRACE_NAME_MAX]
    TRACE_DIR.mkdir(parents=True, exist_ok=True)
    return TRACE_DIR / fit_name(TRACE_DIR, f"{safe}-{kind}", suffix)


def _trace_path(name: str) -> Path:
    """Build a filesystem-safe trace path from a test node id."""
    return _artifact_path(name, "trace", ".zip")


def _video_path(name: str) -> Path:
    """Build a filesystem-safe video path from a test node id (same
    sanitizer and cap as _trace_path, so the clip sorts next to its trace)."""
    return _artifact_path(name, "video", ".webm")


def _video_context_args() -> dict:
    """The new_context kwargs that record every page of the context.

    Empty under RECORD_VIDEO=off. pytest-playwright's --video flag only
    covers the plugin's own context, never the one this fixture builds.
    """
    if os.environ.get("RECORD_VIDEO", "").strip().lower() in _OFF_VALUES:
        return {}
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    return {"record_video_dir": str(VIDEO_DIR)}


def _video_of(page):
    """The page's video handle, or None when recording is off.

    Taken while the page is still open: the handle stays valid after the
    page and context close, and that is when its file is complete.
    """
    try:
        return page.video
    except Exception as e:
        print(f"[VIDEO] Could not get the video handle: {e}")
        return None


def _test_failed(request) -> bool:
    """Whether the test body failed, read from the report conftest stashed."""
    rep_call = getattr(request.node, "rep_call", None)
    return rep_call is not None and rep_call.failed


def _finish_tracing(context, request) -> None:
    """Save the trace if the test failed; otherwise discard it.

    Mirrors pytest-playwright's --tracing=retain-on-failure for the context
    this fixture creates itself (which the plugin's flag does not cover).
    """
    try:
        if _test_failed(request):
            path = _trace_path(request.node.nodeid)
            context.tracing.stop(path=str(path))
            print(f"[TRACE] Saved failure trace to {path}")
        else:
            context.tracing.stop()
    except Exception as e:
        print(f"[TRACE] Could not finalize trace: {e}")


def _finish_video(video, keep_as: str | None) -> None:
    """Keep the clip as <keep_as>-video.webm, or discard it when keep_as is None.

    Same keep-on-failure rule as _finish_tracing. Must run after the
    context closed: Playwright finishes writing the .webm on context close,
    and save_as refuses a page that is still open. The raw file under
    VIDEO_DIR is deleted either way so the folder never accumulates the
    clips of passing tests.
    """
    if video is None:
        return
    try:
        if keep_as is not None:
            path = _video_path(keep_as)
            video.save_as(str(path))
            print(f"[VIDEO] Saved failure video to {path}")
        video.delete()
    except Exception as e:
        print(f"[VIDEO] Could not finalize video: {e}")


@pytest.fixture(scope="session")
def auth_state_path():
    """Path to the cached authentication state file.

    Under pytest-xdist each worker gets its own file so workers never race
    on a shared cache (each worker is a separate process and session).
    """
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker:
        return f".auth_state.{worker}.json"
    return AUTH_STATE_FILE


@pytest.fixture
def authenticated_page(browser, auth_state_path, base_url, login_data, request):
    """Provide a Playwright page with cached authentication.

    Uses pytest-playwright's browser fixture to avoid event loop conflicts.
    First run: Logs in via UI and saves storage state to file.
    Subsequent runs: Loads cached state (skips login entirely).

    Records a Playwright trace and a video for every test and keeps both
    only on failure (reports/artifacts/<test>-trace.zip, open with
    `playwright show-trace`; reports/artifacts/<test>-video.webm).
    RECORD_VIDEO=off skips the video.
    """
    import os

    context = None
    page = None
    video = None

    # Check if we have cached auth state
    if os.path.exists(auth_state_path):
        print(f"[AUTH] Loading cached session from {auth_state_path}")
        try:
            context = browser.new_context(storage_state=auth_state_path,
                                          **_video_context_args())
            context.tracing.start(screenshots=True, snapshots=True, sources=True)
            page = context.new_page()
            video = _video_of(page)
            page.goto(base_url)
            page.wait_for_load_state('domcontentloaded', timeout=30000)

            # Fast session validation. If the session is dead the app shows
            # the login form instead of the nav, so waiting for the nav is
            # both the readiness wait and the validity check.
            if '/auth/login' in page.url or page.locator("input[type='email']").is_visible():
                raise Exception("Login page shown - session invalid")
            nav = page.locator("text=Views").first
            nav.wait_for(state="visible", timeout=10000)
            print("[AUTH] Cached session is valid")
        except Exception as e:
            print(f"[AUTH] Cached session unusable: {e}")
            if page is not None:
                page.close()
            if context is not None:
                context.close()
            # The dead session's clip is not the test's evidence.
            _finish_video(video, None)
            context = None
            page = None
            video = None
            try:
                os.remove(auth_state_path)
            except OSError:
                pass

    if context is None:
        # No valid cache - perform fresh login
        print("[AUTH] Performing fresh login...")
        context = browser.new_context(**_video_context_args())
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        video = _video_of(page)

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
            try:
                path = _trace_path(f"{request.node.nodeid}-login-failure")
                context.tracing.stop(path=str(path))
                print(f"[TRACE] Saved login-failure trace to {path}")
            except Exception:
                pass
            page.close()
            context.close()
            _finish_video(video, f"{request.node.nodeid}-login-failure")
            raise

    yield page
    _finish_tracing(context, request)
    page.close()
    context.close()
    _finish_video(video, request.node.nodeid if _test_failed(request) else None)


# Graph's sendMail call carries the whole message in one request with a
# documented cap of about 4 MB, and base64 inflates the attachment by 4/3.
# Inline only reports small enough that body + encoded attachment still
# fit; past the attach cap even the attachment would sink the send, so the
# body carries a pointer to the per-run archive instead (reports/runs/
# keeps every run's full report).
REPORT_INLINE_MAX_BYTES = int(1.5 * 1024 * 1024)
REPORT_ATTACH_MAX_BYTES = int(2.5 * 1024 * 1024)


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

        size = report_path.stat().st_size
        attachments = [str(report_path)]
        if size <= REPORT_INLINE_MAX_BYTES:
            html = report_path.read_text(encoding="utf-8", errors="replace")
        elif size <= REPORT_ATTACH_MAX_BYTES:
            html = "<p>Report too large to inline - see the attached file.</p>"
        else:
            attachments = []
            html = ("<p>Report too large to send by email - open the "
                    "archived copy under reports/runs/ (index.html lists "
                    "runs newest first).</p>")
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
            attachments=attachments,
        )
        print(f"\n[SUCCESS] Test report sent to {recipient}")
    except Exception as e:
        print(f"\n[WARNING] Failed to send test report: {e}")
