"""Fixtures for Camera-to-Cloud (C2C) hardware tests.

These tests target the camera's built-in web UI directly via HTTP Basic Auth,
NOT the NexaiQ-Core cloud application.

Tests parametrize over entries in tests/data/c2c_cameras.yaml - each enabled
camera runs the full test suite. Multi-lens cameras are listed as separate
entries (one per lens) since each lens has its own license.

Override via environment variables (single-camera mode):
    C2C_CAMERA_IP    - Override camera IP (skips YAML, uses env only)
    C2C_CAMERA_USER  - Camera username (default: root)
    C2C_CAMERA_PASS  - Camera password (default: ***REMOVED***)

Example runs:
    # All enabled cameras
    pytest tests/ui/c2c/ -m c2c_hardware

    # Single camera via env var
    C2C_CAMERA_IP=192.168.1.149 pytest tests/ui/c2c/

    # Specific camera by id
    pytest tests/ui/c2c/ -k "bc-5v-1-qa-lab"

    # Multi-lens only
    pytest tests/ui/c2c/ -k "multi-lens"
"""
import os
import socket
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml

# Default fallback config when no YAML registry is used
DEFAULT_CAMERA = {
    "id": "default",
    "ip": os.environ.get("C2C_CAMERA_IP", "192.168.1.149"),
    "user": os.environ.get("C2C_CAMERA_USER", "root"),
    "password": os.environ.get("C2C_CAMERA_PASS", "***REMOVED***"),
    "model": "BC-5V-1",
    "manufacturer": "SOTERIX SYSTEMS",
    "max_resolution": "2592x1944",
    "max_framerate": 30,
    "lens_count": 1,
    "multi_lens": False,
    "expected_license": "ProAI 1ch",
    "expected_license_count": 1,
}

CAMERAS_YAML = Path(__file__).parent.parent.parent / "data" / "c2c_cameras.yaml"


def _load_cameras():
    """Load camera registry from YAML. Respects C2C_CAMERA_IP env override."""
    # Env override - single camera mode (skips YAML entirely)
    if os.environ.get("C2C_CAMERA_IP"):
        return [DEFAULT_CAMERA]

    if not CAMERAS_YAML.exists():
        return [DEFAULT_CAMERA]

    with open(CAMERAS_YAML) as f:
        data = yaml.safe_load(f) or {}

    cameras = data.get("cameras", [])
    # Filter to enabled cameras only
    enabled = [c for c in cameras if c.get("enabled", True)]
    return enabled if enabled else [DEFAULT_CAMERA]


# Discover cameras at collection time so pytest can parametrize
_AVAILABLE_CAMERAS = _load_cameras()

# How long to wait when probing whether a camera is on the network at all.
# Deliberately short: this is a "is it there" check, not a page load.
REACHABILITY_TIMEOUT = float(os.environ.get("C2C_PROBE_TIMEOUT", "1.5"))

# Cache probe results so 55 tests against one camera cost a single connect.
_reachable_cache: dict[str, bool] = {}


def _camera_reachable(ip: str, port: int = 80) -> bool:
    """True if a TCP connection to the camera's web UI succeeds quickly."""
    if ip in _reachable_cache:
        return _reachable_cache[ip]
    try:
        with socket.create_connection((ip, port), timeout=REACHABILITY_TIMEOUT):
            result = True
    except OSError:
        result = False
    _reachable_cache[ip] = result
    return result


@pytest.fixture(
    scope="session",
    params=_AVAILABLE_CAMERAS,
    ids=[c["id"] for c in _AVAILABLE_CAMERAS],
)
def camera_config(request):
    """Camera profile dict for the current test run (parametrized).

    Each test class that uses this fixture runs once per enabled camera.
    Contains: id, ip, user, password, model, expected_license, etc.

    These are hardware tests: they talk to a physical camera's web UI on the
    lab network, not to NexaiQ-Core. When that camera is not reachable - the
    usual case off-site - the tests skip instead of each burning a 15s
    navigation timeout and reporting a misleading failure.

    Set C2C_REQUIRE_HARDWARE=1 to turn an unreachable camera into a real
    failure (use this on the lab runner, where absence IS the bug).
    """
    camera = request.param
    ip = camera["ip"]
    if not _camera_reachable(ip) and not os.environ.get("C2C_REQUIRE_HARDWARE"):
        pytest.skip(
            f"C2C camera {camera['id']} at {ip} is not reachable "
            f"(no TCP connect within {REACHABILITY_TIMEOUT}s). These are "
            f"hardware tests - run them on the lab network, or set "
            f"C2C_REQUIRE_HARDWARE=1 to fail instead of skip."
        )
    return camera


@contextmanager
def _camera_context(browser, camera_config, path):
    """Yield a page on the camera at `path`, always closing the context.

    The navigation happens during fixture setup and can raise (an unreachable
    or slow camera times out). Without the try/finally the context would leak
    on every such failure - a full suite run against absent hardware used to
    strand one browser context per test.
    """
    context = browser.new_context(
        http_credentials={
            "username": camera_config["user"],
            "password": camera_config["password"],
        },
        ignore_https_errors=True,
    )
    try:
        page = context.new_page()
        page.goto(
            f"http://{camera_config['ip']}{path}",
            wait_until="domcontentloaded",
            timeout=15000,
        )
        yield page
    finally:
        context.close()


@pytest.fixture
def camera_page(browser, camera_config):
    """Playwright page pre-authenticated to the camera's main live view."""
    with _camera_context(browser, camera_config, "/cgi-bin/index.cgi") as page:
        yield page


@pytest.fixture
def camera_setup_page(browser, camera_config):
    """Playwright page navigated to the camera's Setup/admin page."""
    with _camera_context(
        browser, camera_config, "/cgi-bin/admin/setup_main.cgi"
    ) as page:
        yield page


@pytest.fixture
def camera(camera_setup_page, camera_config):
    """CameraHardwarePage object bound to the parametrized camera."""
    # Import here to avoid circular issues at collection
    from tests.shared.pages.camera_hardware_page import CameraHardwarePage
    return CameraHardwarePage(camera_setup_page, camera_config)
