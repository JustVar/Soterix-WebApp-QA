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


@pytest.fixture(
    scope="session",
    params=_AVAILABLE_CAMERAS,
    ids=[c["id"] for c in _AVAILABLE_CAMERAS],
)
def camera_config(request):
    """Camera profile dict for the current test run (parametrized).

    Each test class that uses this fixture runs once per enabled camera.
    Contains: id, ip, user, password, model, expected_license, etc.
    """
    return request.param


@pytest.fixture
def camera_page(browser, camera_config):
    """Playwright page pre-authenticated to the camera's main live view."""
    context = browser.new_context(
        http_credentials={
            "username": camera_config["user"],
            "password": camera_config["password"],
        },
        ignore_https_errors=True,
    )
    page = context.new_page()
    page.goto(
        f"http://{camera_config['ip']}/cgi-bin/index.cgi",
        wait_until="domcontentloaded",
        timeout=15000,
    )
    yield page
    context.close()


@pytest.fixture
def camera_setup_page(browser, camera_config):
    """Playwright page navigated to the camera's Setup/admin page."""
    context = browser.new_context(
        http_credentials={
            "username": camera_config["user"],
            "password": camera_config["password"],
        },
        ignore_https_errors=True,
    )
    page = context.new_page()
    page.goto(
        f"http://{camera_config['ip']}/cgi-bin/admin/setup_main.cgi",
        wait_until="domcontentloaded",
        timeout=15000,
    )
    yield page
    context.close()


@pytest.fixture
def camera(camera_setup_page, camera_config):
    """CameraHardwarePage object bound to the parametrized camera."""
    # Import here to avoid circular issues at collection
    from tests.shared.pages.camera_hardware_page import CameraHardwarePage
    return CameraHardwarePage(camera_setup_page, camera_config)
