import os
import pytest
from tests.shared.pages.login_page import LoginPage
from tests.shared.pages.events_page import EventsPage

# Force QA environment for pilot tests (ReCAPTCHA disabled in QA)
os.environ.setdefault("ENV", "qa")


def test_events_search_smoke(page, base_url, tenant_login):
    """Smoke: login and perform a basic events search."""
    app_type = os.environ.get("APP_TYPE", "customer")

    LoginPage(page).goto(base_url, app_type=app_type).login(tenant_login["username"], tenant_login["password"])

    events = EventsPage(page)
    events.go_to_events(base_url).search(tenant_login.get("username", "test"))

    # If no exception/skip happened, consider smoke passed
    assert True
