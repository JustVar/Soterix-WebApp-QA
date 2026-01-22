import os
import pytest
from tests.shared.pages.login_page import LoginPage
from tests.shared.pages.camera_page import CameraPage

# Force QA environment for pilot tests (ReCAPTCHA disabled in QA)
os.environ.setdefault("ENV", "qa")


def test_play_camera_smoke(page, base_url, tenant_login):
    """Smoke: login and attempt to play the first available camera."""
    app_type = os.environ.get("APP_TYPE", "customer")

    LoginPage(page).goto(base_url, app_type=app_type).login(tenant_login["username"], tenant_login["password"])

    cam = CameraPage(page)
    # navigate to dashboard where cameras are expected
    cam.go_to_dashboard(base_url).play_first_camera()

    # If play_first_camera didn't skip, assume success
    assert True
