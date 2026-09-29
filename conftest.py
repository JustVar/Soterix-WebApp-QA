# conftest.py
import json
import logging
import os
import re
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

# Register plugins
# The products path rule (which QA Touch project a test root reports to)
# lives in the products shim, which self-configures on import. The
# reporting modules import the PACKAGE products directly, so nothing else
# triggers that side effect - import it here so the rule is set for the session.
import plugins.products
from config.base_config import config, get_credentials  # dict resolved from ENV
from config.secret import Secret
from plugins.paths import fit_name
from tests.shared.auth_state import auth_state_filename

pytest_plugins = ['plugins.xdist_recovery', 'plugins.wall_clock', 'plugins.qatouch_reporter', 'plugins.verification_runner', 'plugins.report_media',
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
    the command line overrides the ini silently, and a wrong value ran
    for a month before anybody could tell. Runs without -n are untouched.
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


def _session_account() -> tuple[str, str]:
    """(account, password) the UI login will use: QA_USER and QA_PASSWORD
    through the env module. The same choice login_data makes."""
    creds = get_credentials()
    return creds.get("email") or "", Secret(creds.get("password") or "")


def pytest_sessionstart(session):
    """Ask once whether the tenant answers and the account signs in, before
    any browser opens; refuse the run with one named line when not
    (tests/shared/helpers/preflight.py). Then choose the run's site and
    camera, which may ask the server too."""
    from tests.shared.helpers import preflight
    if not preflight.skip_reason(session.config):
        account, password = _session_account()
        refusal = preflight.check(str(ENV_SETTINGS.get("base_url") or ""), account, password)
        if refusal:
            pytest.exit(refusal, returncode=preflight.EXIT_CODE)
    # The run's camera is chosen HERE, on every process, not only at collection.
    # Under xdist the controller never collects, so a choice made there alone
    # leaves the workers driving one camera while the run record, built on
    # the controller, names another with no reason. The choice is
    # deterministic, so every process reaches the same camera alone.
    _choose_camera(session.config)


# Markers whose tests create and delete data on the server. They run only
# where config/env/ sets allow_write True (prod: False).
WRITE_MARKERS = ("admin_users", "admin_rules", "admin_sites", "bookmark", "sequences")

# The collection hook receives pytest's own `config`, which shadows the
# env dict imported above. This alias keeps the dict reachable there.
ENV_SETTINGS = config


def env_skip_reason(markers, settings, env_name: str) -> str | None:
    """Why the active environment refuses this test, or None to let it run.

    `markers` is the set of marker names on the test, never item.keywords:
    keywords also hold parametrize ids, and an id that spelled a marker
    name once skipped the pins that prove the guard.

    A missing flag counts as False, the same default base_config's
    is_write_allowed uses: an env file that says nothing about writes gets
    none.
    """
    if not settings.get("allow_write", False):
        for marker in WRITE_MARKERS:
            if marker in markers:
                return (f"env {env_name}: allow_write is False in config/env/, so tests "
                        f"marked '{marker}' do not run here")
    # The env's `without` map (config/env/<env>.py > without): what the
    # server itself lacks, by marker, with the reason. The reason is the
    # skip text, so the report says what is missing and on whose word,
    # not just "skipped". An env with no map refuses nothing.
    without = (settings or {}).get("without") or {}
    for marker, why in without.items():
        if marker in markers:
            return (f"env {env_name} is without '{marker}': {why} "
                    f"(config/env/{env_name}.py > without)")
    return None


def marker_names(item) -> set[str]:
    """The names of the markers on a collected test, own and inherited."""
    return {mark.name for mark in item.iter_markers()}


def pytest_collection_modifyitems(config, items):
    """Skip what this run may not execute: the env guard has no opt-in
    flag. Prod is read-only by config, and no command line lifts that."""
    env_name = (os.environ.get("ENV") or "qa").strip().lower()
    # Which camera this run drives, before the guard measures one: the guard has
    # to measure the camera the tests will actually use. Deterministic, so every
    # xdist worker reaches the same answer on its own and none has to be told.
    _choose_camera(config)
    for item in items:
        reason = env_skip_reason(marker_names(item), ENV_SETTINGS, env_name)
        if reason:
            item.add_marker(pytest.mark.skip(reason=reason))
    stream_guard(config, items)


# What the run chose, for the summary line and the run record.
_CAMERA_PICK: dict = {}
# The camera config/env/ names, kept before anything overwrites it. Choosing
# reads this, never ENV_SETTINGS: the choice WRITES test_camera_name, so a
# second call would treat the chosen camera as the configured one and lose
# the fallback.
_CONFIGURED_CAMERA = ENV_SETTINGS.get("test_camera_name")


def _choose_camera(config) -> dict:
    """Point test_camera_name at this run's camera and remember why.

    One camera for the whole run, so its tests are comparable with each other
    and the run page's history strip keeps its meaning. TEST_CAMERA pins one
    by name. A run selected by a camera-specific marker (`-m lpr`) drives the
    camera config/env/ lists for it under camera_capabilities
    (tests/shared/helpers/camera_pool.py).

    Chosen once per process. Collection can run more than once in one
    interpreter (the pins run nested sessions), and a second choice would print
    a second [CAMERA] line for a run that has one camera.
    """
    global _CAMERA_PICK
    if _CAMERA_PICK:
        return _CAMERA_PICK
    from tests.shared.helpers import camera_pool
    configured, configured_reason = _CONFIGURED_CAMERA, None
    record = _discover_site_and_camera(config)
    if record:
        configured, configured_reason = record["camera"], record["camera_reason"]
    getoption = getattr(config, "getoption", None)
    markexpr = getoption("markexpr", default="") if getoption else ""
    capabilities = ENV_SETTINGS.get("camera_capabilities") or {}
    capability = camera_pool.capability_for(camera_pool.markexpr_words(markexpr), capabilities)
    pick = camera_pool.choose(configured, capability=capability, capabilities=capabilities,
                              configured_reason=configured_reason)
    _CAMERA_PICK = pick
    if pick.get("camera"):
        ENV_SETTINGS["test_camera_name"] = pick["camera"]
    # The archive reads this out of the env config and writes the camera and its
    # reason into the run's provenance, so the run page can name the camera and
    # mark it when it changed between two runs.
    ENV_SETTINGS["camera_pick"] = pick
    # The line prints only when something changed the choice: the run page
    # names the camera on every run, the terminal only when it is not the
    # configured one.
    if pick.get("camera") != _CONFIGURED_CAMERA:
        _STREAM_LINES.append(camera_pool.describe(pick))
    return pick


# The stream guard's lines for the terminal summary: under -n the workers'
# prints never reach the terminal, and the README tells people to read
# the [STREAM] line.
_STREAM_LINES: list[str] = []


def _discover_site_and_camera(config) -> dict | None:
    """Fill the site and the camera config/env/ leaves blank, from the server.

    Returns the discovery record, or None when config/env/ names everything
    (the server is not asked). The choice is by name order, so every xdist
    process reaches the same site and camera alone
    (tests/shared/api/discovery.py).

    A server that cannot be read, or a configured name it does not know,
    stops the run the way the preflight does: one line, exit code 7,
    before any browser opens. With PREFLIGHT=off, and on an xdist worker
    (the controller already asked), the error is a line in the summary
    and the tests that need a camera fail on their own. A session that
    runs no tenant test (--collect-only, the offline pins) asks nothing.
    """
    from tests.shared.api import discovery
    from tests.shared.helpers import preflight
    if not discovery.needs_discovery(ENV_SETTINGS):
        return None
    skipped = preflight.skip_reason(config)
    if skipped and not skipped.startswith((f"{preflight.SWITCH}=off", "xdist worker")):
        return None
    try:
        record = discovery.fill_config(ENV_SETTINGS, get_credentials())
    except discovery.DiscoveryError as exc:
        message = f"DISCOVERY: {exc}"
        if skipped:
            _STREAM_LINES.append(f"[CAMERA] {message}")
            return None
        pytest.exit(message, returncode=preflight.EXIT_CODE)
    if record["site_reason"] != discovery.CONFIGURED_SITE_REASON:
        _STREAM_LINES.append(f"[SITE] '{record['site_name']}' (siteId {record['site_id']}): "
                             f"{record['site_reason']}")
    return record
WORKER_MEASURE_KEY = "qa_stream_measure"


def _measure_stream(config) -> dict:
    """The guard's measurement, with its second look, and its lines kept for the summary."""
    from tests.shared.helpers import stream_health
    channel = config.getoption("--browser-channel", default=None)
    headed = bool(config.getoption("--headed", default=False))
    camera = ENV_SETTINGS.get("test_camera_name")
    measure = stream_health.assess(camera, channel, headed=headed)
    _STREAM_LINES.append(stream_health.describe(measure))
    if measure.get("frames") == 0 and not measure.get("error"):
        # a second look before skipping the whole session on one empty
        # window: a camera has read 0 frames and then 117 a minute apart,
        # and one 8 s sample once skipped 43 tests
        measure = stream_health.assess(camera, channel, headed=headed)
        _STREAM_LINES.append("[STREAM] second measurement: " + stream_health.describe(measure))
    return measure


def _may_collect_livestream(config) -> bool:
    """Whether the session's targets can hold a `livestream` test, read from
    the files: the controller of an xdist run never collects, and a
    measurement costs a login, a socket and a Chrome launch."""
    from tests.shared.helpers import stream_health
    if "not " + stream_health.MARKER in (config.getoption("markexpr", default="") or ""):
        return False
    root = Path(str(config.rootpath))
    for arg in (config.args or ["tests/ui"]):
        path = Path(str(arg).split("::")[0])
        path = path if path.is_absolute() else root / path
        files = [path] if path.is_file() else sorted(path.rglob("test_*.py")) if path.is_dir() else []
        for file in files:
            try:
                if stream_health.MARKER in file.read_text(encoding="utf-8", errors="replace"):
                    return True
            except OSError:  # why: an unreadable file cannot veto the measurement; the next file decides
                continue
    return False


def pytest_configure_node(node):
    """xdist controller, once per worker: hand every worker the ONE
    measurement. Each worker used to measure for itself at collection:
    four logins, four sockets, four Chrome launches, four verdicts that
    could disagree, and no line on the terminal."""
    from tests.shared.helpers import stream_health
    config = node.config
    if not stream_health.guard_enabled() or config.getoption("--collect-only", default=False):
        return
    if not hasattr(config, "_qa_stream_measure"):
        config._qa_stream_measure = _measure_stream(config) if _may_collect_livestream(config) else None
    if config._qa_stream_measure is not None:
        node.workerinput[WORKER_MEASURE_KEY] = json.dumps(config._qa_stream_measure, default=str)


def pytest_terminal_summary(terminalreporter):
    """The stream guard's measurement, where the reader is."""
    if not _STREAM_LINES:
        return
    terminalreporter.section("stream guard")
    for line in _STREAM_LINES:
        terminalreporter.write_line(line)


def stream_guard(config, items) -> None:
    """Measure the test camera's stream once and skip the `livestream` tests
    with the measurement when the media socket delivers no frames (a dead
    camera otherwise fails dozens of tests, each named after its own
    timeout). Measures only when a livestream test was collected and the
    run will execute it; a failed measurement skips nothing and says so.
    See tests/shared/helpers/stream_health.py."""
    from tests.shared.helpers import stream_health
    targets = [item for item in items if stream_health.MARKER in item.keywords]
    if not targets or not stream_health.guard_enabled() or config.getoption("--collect-only", default=False):
        return
    # Two facts: the socket's frame count, and whether THIS browser decodes
    # what the channel streams. "This browser" is the one the tests get:
    # the session's channel, flags (CHROME_ARGS) and headed-ness, since
    # Chrome on Linux decodes H.265 only headed on a Wayland display with
    # the VA-API flags (docs/LINUX_H265.md).
    shared = (getattr(config, "workerinput", None) or {}).get(WORKER_MEASURE_KEY)
    if shared:
        measure = json.loads(shared)   # the controller measured once for every worker
    else:
        measure = _measure_stream(config)
        for line in _STREAM_LINES[-2:]:
            print(line)
    reason = stream_health.stream_skip_reason(measure)
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
    """The account the tests sign in as: QA_USER and QA_PASSWORD from .env,
    read through the env module (config/env/<ENV>.py get_credentials)."""
    creds = get_credentials()
    user = creds.get("email") or ""
    password = Secret(creds.get("password") or "")
    if not user or not password:
        raise ValueError("QA_USER and QA_PASSWORD must be set in .env (copy .env.template). "
                         "The tests sign in as that account.")
    logging.getLogger(__name__).info("[CREDENTIALS] Using QA_USER from .env")
    return {"username": user, "password": password}


# ----------------
# API testing lives in the Soterix-API-QA repo. This repo is UI automation
# and manual test cases only.
# ----------------


# ----------------
# Session-Cached Authentication (Playwright Storage State)
# ----------------
# Caching the signed-in state saves the login on every test: about 345 s
# on a full run.

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
    "app answered 401 to a live session and bounced to login mid-test. "
    "The locator is not the fault. Read the 401 responses in the trace."
)


def _session_drop_note(item, rep) -> str | None:
    """The session-drop line for a failed setup or call whose page shows
    the login screen, else None. The page is the one authenticated_page
    stashed on the item; a fixture layered on it that navigates in setup
    bounces the same way, and so does a second tab of the same context.
    A page already closed has no URL and gets no note."""
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
    of the locator that timed out on the login page. Such failures read as
    locator timeouts until somebody opens the screenshots.
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


# The last of the landing page's post-login calls (the session check, the
# site tree, then the status), and it lands after the nav shows, so the
# nav alone is too early to yield on.
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
    the cache filename carries a slug of the base_url: two envs running on
    one machine at the same time must not fight over one file. On different
    domains the reused cookies do not apply and a stale cache is caught and
    refreshed; on shared cookie domains (staging and prod under one parent
    domain) a stage session could otherwise pass validation against prod,
    which is the case a per-env file prevents outright.
    """
    return auth_state_filename(base_url, os.environ.get("PYTEST_XDIST_WORKER") or "")


# The first refused login of this process, kept so the tests after it fail
# in a second with the same line instead of submitting the form again.
_LOGIN_REFUSED: list[str] = []


def _login_refusal(lp, page, account: str) -> str | None:
    """The line that names a rejected login, or None when the form is gone.

    LoginPage.login swallows its own wait, and the 60 s wait after it then
    failed as 'Timeout 60000ms exceeded' with the app's message never
    quoted: 73 s per test, the form resubmitted each time. A form still
    up with an error, a captcha or
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
    return (f"[LOGIN] {page.url} kept the login form after submit. On screen: {message or 'no message'!r}. "
            f"Captcha shown: {'yes' if captcha else 'no'}. Lockout text: {'yes' if lockout else 'no'}. "
            f"Account: {account}. Later tests fail with this line "
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
            # A test that navigates before those answered aborts them
            # and the app bounces to /auth/login. Yield on the same
            # signal the cached path validates on, the nav, and then
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
