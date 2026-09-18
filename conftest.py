# conftest.py
import importlib
import logging
import os
import re
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

# Register plugins
# The products path rule (tests/c2c -> Camera 2 Cloud) lives in the
# products shim, which self-configures on import. The reporting modules
# now import the PACKAGE products directly, so nothing else triggers that
# side effect - import it here so the rule is set for the session.
import plugins.products
from config.base_config import config  # dict resolved from ENV
from config.secret import Secret
from plugins.paths import fit_name
from tests.shared.auth_state import auth_state_filename

pytest_plugins = ['plugins.xdist_recovery', 'plugins.qatouch_reporter', 'plugins.verification_runner', 'plugins.report_media',
                  'plugins.run_archive', 'plugins.single_run_guard',
                  'tests.shared.api.fixtures']

# Logging (env/tenant resolution)
LOG_FILE = os.path.join("logs", "env_config.log")
os.makedirs("logs", exist_ok=True)
# One rotating file: the log was appending for good and had reached 1.4 MB
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    handlers=[RotatingFileHandler(LOG_FILE, maxBytes=512_000, backupCount=2)])

def pytest_configure(config):
    """Refuse a parallel run that would lose the tenant-state grouping.

    pytest.ini sets `--dist loadgroup`, which keeps every module that
    writes this account's state (its `xdist_group` mark) on one worker
    and serialises the one search job the server allows. A `--dist` on
    the command line overrides the ini silently; the docs said
    `--dist loadfile` for a month and nobody could tell (audit
    09/17/2026, row 86). Runs without -n are untouched.
    """
    try:
        workers = config.getoption("numprocesses")
        dist = config.getoption("dist")
    except ValueError:  # why: xdist not loaded (-p no:xdist): nothing to guard
        return
    if workers and dist != "loadgroup":
        raise pytest.UsageError(
            f"-n {workers} with --dist {dist}: use -n alone. pytest.ini sets --dist loadgroup so the "
            "modules that write tenant state stay on one worker (docs/PARALLEL_EXECUTION.md).")


def _session_account() -> tuple[str, str, str]:
    """(account, password, box) the UI login will use: the box pair when BOX
    is set, else the legacy QA_USER pair. The same choice login_data makes."""
    box = (os.environ.get("BOX") or "").strip()
    if box:
        from config.base_config import get_credentials
        creds = get_credentials()
        return creds.get("email") or "", Secret(creds.get("password") or ""), box
    return os.environ.get("QA_USER") or "", Secret(os.environ.get("QA_PASSWORD") or ""), ""


def pytest_sessionstart(session):
    """Ask once whether the tenant answers and the account signs in, before
    any browser opens; refuse the run with one named line when not
    (tests/shared/helpers/preflight.py)."""
    from tests.shared.helpers import preflight
    if preflight.skip_reason(session.config):
        return
    account, password, box = _session_account()
    refusal = preflight.check(str(ENV_SETTINGS.get("base_url") or ""), account, password, box=box)
    if refusal:
        pytest.exit(refusal, returncode=preflight.EXIT_CODE)


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
    # An env's own `without` map (config/env/<env>.py > without): what the
    # deployment itself lacks, by marker, with the reason. The Neurosen
    # private cloud is a build of the web app without some Core features;
    # a box's `without` says the same thing for one tenant inside an env.
    without = (settings or {}).get("without") or {}
    for marker, why in without.items():
        if marker in keywords:
            return (f"env {env_name} is without '{marker}': {why} "
                    f"(config/env/{env_name}.py > without)")
    return None


def box_skip_reason(keywords, box_settings, box_name: str) -> str | None:
    """Why the active box cannot host this test, or None to let it run.

    A box's `without` map (config/env/<env>.py > boxes > <box>) names the
    markers of what the tenant does not have, each with the measured or
    stated reason. The reason is the skip text, so the report says which
    box lacks what and on whose word, not just "skipped". A box with no
    `without` map refuses nothing.
    """
    without = (box_settings or {}).get("without") or {}
    for marker, why in without.items():
        if marker in keywords:
            return (f"box {box_name} is without '{marker}': {why} "
                    f"(config/env/ > boxes > {box_name} > without)")
    return None


def active_box_settings(settings, box_name: str) -> dict:
    """The active box's entry in the env's `boxes` map, or {} when the env has none."""
    return ((settings or {}).get("boxes") or {}).get(box_name) or {}


def pytest_collection_modifyitems(config, items):
    """Skip what this run may not execute.

    Destructive tests need --run-destructive: a plain `pytest tests/c2c/`
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
    # The box guard: a tenant that lacks a feature refuses that feature's
    # tests at collection, saying which box lacks what (config/env/ >
    # boxes > <box> > without). Resolved once; the box does not change
    # inside a run.
    from config.base_config import get_active_box
    box_name = get_active_box()
    box_settings = active_box_settings(ENV_SETTINGS, box_name)
    for item in items:
        if not run_destructive and "destructive" in item.keywords:
            item.add_marker(destructive_skip)
        reason = (env_skip_reason(item.keywords, ENV_SETTINGS, env_name)
                  or box_skip_reason(item.keywords, box_settings, box_name))
        if reason:
            item.add_marker(pytest.mark.skip(reason=reason))
    stream_guard(config, items, box_name)


def stream_guard(config, items, box_name: str) -> None:
    """Measure the box's stream once and skip the `livestream` tests with the
    measurement when the media socket delivers no frames (nine failures of
    the 09/11/2026 full run were this one condition, each named after its
    own timeout). Measures only when a livestream test was collected and
    the run will execute it; a failed measurement skips nothing and says
    so. See tests/shared/helpers/stream_health.py."""
    from tests.shared.helpers import stream_health
    targets = [item for item in items if stream_health.MARKER in item.keywords]
    if not targets or not stream_health.guard_enabled() or config.getoption("--collect-only", default=False):
        return
    # Two facts: the socket's frame count, and whether THIS browser decodes
    # what the channel streams. "This browser" is the one the tests get:
    # the session's channel, flags (CHROME_ARGS) and headed-ness, since
    # Chrome on Linux decodes H.265 only headed on a Wayland display with
    # spartan1's flags (deploy/spartan1/README.md, 09/17/2026).
    channel = config.getoption("--browser-channel", default=None)
    headed = bool(config.getoption("--headed", default=False))
    measure = stream_health.assess(ENV_SETTINGS.get("test_camera_name"), channel, headed=headed)
    print(stream_health.describe(measure))
    if measure.get("frames") == 0 and not measure.get("error"):
        # a second look before skipping the whole session on one empty
        # window: the US camera read 0 frames and then 117 a minute
        # apart (09/12/2026), and one 8 s sample had skipped 43 tests
        measure = stream_health.assess(ENV_SETTINGS.get("test_camera_name"), channel, headed=headed)
        print("[STREAM] second measurement: " + stream_health.describe(measure))
    reason = stream_health.stream_skip_reason(measure, box_name)
    if reason:
        for item in targets:
            item.add_marker(pytest.mark.skip(reason=reason))


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    """pytest-playwright's launch options plus the flags in CHROME_ARGS.

    The inner fixture is the plugin's own (headed, channel, slow-mo); this
    override appends the session's Chrome flags to it, so the browser the
    tests get is the one the stream guard measured
    (stream_health.chrome_args). Unset, nothing changes.
    """
    from tests.shared.helpers import stream_health
    return stream_health.launch_args_with_chrome_flags(browser_type_launch_args)


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
    password = Secret(_from_env_or_config("AUTO_PASSWORD", "default_password"))
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
    logging.getLogger(__name__).info(f"[ENV CONFIG] Loaded config for: {os.environ.get('ENV')}")
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
    2. Otherwise read QA_USER and QA_PASSWORD from .env: the legacy pair,
       for a .env without BOX (the template ships BOX=india).
    """
    expected_landing = os.environ.get("EXPECTED_LANDING", "/dashboard")

    box = os.environ.get("BOX")
    if box:
        from config.base_config import get_credentials
        creds = get_credentials()
        if not creds.get("email") or not creds.get("password"):
            settings = active_box_settings(ENV_SETTINGS, box)
            email_env = settings.get("email_env") or f"QA_{box.upper()}_USER"
            password_env = settings.get("password_env") or f"QA_{box.upper()}_PASSWORD"
            empty = [k for k in (email_env, password_env) if not os.environ.get(k)]
            raise ValueError(
                f"BOX='{box}' is set but {' and '.join(empty) or 'its account pair'} is empty in .env. "
                f"Fill both {email_env} and {password_env} (README > Quick Setup), or unset BOX to sign "
                f"in with the legacy QA_USER / QA_PASSWORD pair.")
        logging.getLogger(__name__).info(f"[CREDENTIALS] Using box '{box}' account from env config")
        return {"username": creds["email"], "password": Secret(creds["password"]),
                "expected_landing": expected_landing}

    user = os.environ.get("QA_USER")
    password = Secret(os.environ.get("QA_PASSWORD") or "")
    if not user or not password:
        raise ValueError("QA_USER and QA_PASSWORD must be set in environment or .env file. See .env.template")
    logging.getLogger(__name__).info("[CREDENTIALS] Using QA_USER from environment")
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
def pytest_runtest_teardown(item, nextitem):
    """After a test that ran a search job is torn down (its page has
    closed, so its polling stopped), stamp the moment: the next search
    waits only the remainder of the server's free window (search_gap)."""
    yield
    from tests.shared.helpers import search_gap
    if search_gap.ran_this_test():
        search_gap.note_stopped()


LOGIN_SCREEN = "/auth/login"
SESSION_DROP_NOTE = (
    "[SESSION] The page was on the login screen when the test failed. The "
    "app answered 401 to a live session and bounced to login mid-test "
    "(nightly traces 09/16/2026: india 09:12 and 09:13 UTC, us 09:47 UTC). "
    "The locator is not the fault; read the 401 responses in the trace."
)


def _session_drop_note(item, rep) -> str | None:
    """The session-drop line for a failed setup or call whose page shows
    the login screen, else None. The page is the one authenticated_page
    stashed on the item; a fixture layered on it that navigates in setup
    bounces the same way, and so does a second tab of the same context
    (both measured without a note, 09/18/2026). A page already closed has
    no URL and gets no note."""
    if rep.when not in ("setup", "call") or not rep.failed:
        return None
    page = getattr(item, "qa_page", None)
    if page is None:
        return None
    try:
        urls = [page.url]
    except Exception:  # why: a closed page raises; the note is optional
        return None
    try:
        urls += [p.url for p in page.context.pages if p is not page]
    except Exception:  # why: the other tabs are a bonus; the test's own page already answered
        pass
    return SESSION_DROP_NOTE if any(LOGIN_SCREEN in u for u in urls) else None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Stash each phase's report on the item so fixtures can see the outcome.

    Fixtures tear down after the test finishes, so `request.node.rep_call`
    is how `authenticated_page` knows whether to keep or discard its trace.

    A failed call whose page sits on the login screen gets the session-drop
    note appended to its traceback, so the log names the mechanism instead
    of the locator that timed out on the login page (three of the 09/16
    nightly's failures read as locator timeouts until their screenshots
    were opened).
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
    note = _session_drop_note(item, rep)
    if note and hasattr(rep.longrepr, "addsection"):
        rep.longrepr.addsection("session", note)


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


def _track_api_requests(page) -> dict:
    """Track the app's API requests on this page: the ones in flight and
    the URLs that finished, kept current by the page's request events
    until the tracker's off() removes the listeners. Websocket upgrades
    and the app's static files are not counted."""
    tracker: dict = {'in_flight': set(), 'finished': []}

    def started(request):
        if "/v-apiserver/" in request.url or "/api/" in request.url:
            tracker['in_flight'].add(request)

    def finished(request):
        if request in tracker['in_flight']:
            tracker['in_flight'].discard(request)
            tracker['finished'].append(request.url)

    def off():
        page.remove_listener("request", started)
        page.remove_listener("requestfinished", finished)
        page.remove_listener("requestfailed", finished)

    # plain functions: Playwright's sync wrapper cannot mark a bound builtin
    page.on("request", started)
    page.on("requestfinished", finished)
    page.on("requestfailed", finished)
    tracker['off'] = off
    return tracker


# The last of the landing page's post-login calls (traces 09/14/2026: the
# session check, the site tree, then the status), and it lands after the
# nav shows, so the nav alone is too early to yield on.
LANDING_REQUEST = "/api/status"


def _wait_for_landing(page, tracker: dict, timeout_ms: int = 15000) -> None:
    """Return once the landing page's status request has answered and no
    tracked API request is in flight, or at the timeout (a request the
    app never answers must not hold the fixture). Removes the listeners."""
    deadline = time.monotonic() + timeout_ms / 1000
    while time.monotonic() < deadline:
        landed = any(LANDING_REQUEST in url for url in tracker['finished'])
        if landed and not tracker['in_flight']:
            break
        page.wait_for_timeout(100)  # poll tick for the tracker
    tracker['off']()


@pytest.fixture(scope="session")
def auth_state_path(base_url):
    """Path to the cached authentication state file.

    Scoped to the ENVIRONMENT (its base_url), and under pytest-xdist to the
    worker. A session is only valid for the host it was created against, so
    the cache filename carries a slug of the base_url: a run against the US
    tenant must not load the India tenant's session, and two envs running on
    one machine at the same time must not fight over one file. On different
    domains the reused cookies simply do not apply and a stale cache is
    caught and refreshed; on shared cookie domains (staging vs prod under
    *.app.example.invalid) a stage session could otherwise pass validation
    against prod, which is the case a per-env file prevents outright.
    """
    return auth_state_filename(
        base_url,
        os.environ.get("BOX", "").strip().lower(),
        os.environ.get("PYTEST_XDIST_WORKER") or "",
    )


# The first refused login of this process, kept so the tests after it fail
# in a second with the same line instead of submitting the form again.
_LOGIN_REFUSED: list[str] = []


def _login_refusal(lp, page, account: str) -> str | None:
    """The line that names a rejected login, or None when the form is gone.

    LoginPage.login swallows its own wait, and the 60 s wait after it then
    failed as 'Timeout 60000ms exceeded' with the app's message never
    quoted: 73 s per test, the form resubmitted each time (measured on a
    loopback app, 09/18/2026). A form still up with an error, a captcha or
    a lockout text on it is a refusal; a form still up with none of those
    is left to the wait below, because a slow tenant looks the same.
    """
    try:
        if LOGIN_SCREEN not in page.url:
            return None
        message = lp.get_error_message()
        captcha = lp.has_captcha()
        lockout = lp.has_lockout_message()
    except Exception:  # why: reading the form is a courtesy; the wait below still decides
        return None
    if not (message or captcha or lockout):
        return None
    box = (os.environ.get("BOX") or "").strip()
    return (f"[LOGIN] {page.url} kept the login form after submit. On screen: {message or 'no message'!r}. "
            f"Captcha shown: {'yes' if captcha else 'no'}. Lockout text: {'yes' if lockout else 'no'}. "
            f"Account: {account}{f' (box {box})' if box else ''}. Later tests fail with this line "
            f"and do not submit the form again.")


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

    # The archive's provenance names the Chrome this session opened: the
    # first page fixture to know it writes it, later calls are no-ops.
    from plugins.run_archive import record_browser_version
    record_browser_version(browser.version, request.config.getoption("--browser-channel", default=None))

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
        # A login this process already saw refused is not submitted again:
        # every retry is one more failed attempt against the account.
        if _LOGIN_REFUSED:
            pytest.fail(_LOGIN_REFUSED[0], pytrace=False)
        # No valid cache - perform fresh login
        print("[AUTH] Performing fresh login...")
        context = browser.new_context(**_video_context_args())
        context.tracing.start(screenshots=True, snapshots=True, sources=True)
        page = context.new_page()
        video = _video_of(page)
        tracker = _track_api_requests(page)

        try:
            from tests.shared.pages.login_page import LoginPage
            lp = LoginPage(page, base_url)
            lp.login(login_data['username'], login_data['password'])
            refusal = _login_refusal(lp, page, login_data['username'])
            if refusal:
                _LOGIN_REFUSED.append(refusal)
                raise AssertionError(refusal)

            # Wait for login to complete (not on login page anymore)
            page.wait_for_function(
                "() => !window.location.href.includes('/auth/login')",
                timeout=60000
            )
            # Use domcontentloaded instead of networkidle (app has persistent connections)
            page.wait_for_load_state('domcontentloaded', timeout=30000)
            # The landing page finishes the login on its own: a session
            # check, the site tree and status, about 3 s after the form.
            # A test that navigated before those answered aborted them
            # and the app bounced to /auth/login (india traces 09/12 and
            # 09/14/2026, the logout-from-/search single). Yield on the
            # same signal the cached path validates on, the nav, and then
            # once the status request has answered and nothing is in
            # flight.
            page.locator("text=Views").first.wait_for(state="visible", timeout=30000)
            _wait_for_landing(page, tracker)

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

    # the makereport hook reads the page's URL at failure time
    request.node.qa_page = page
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
