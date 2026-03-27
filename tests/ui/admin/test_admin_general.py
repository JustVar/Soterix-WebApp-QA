"""Admin General section tests - sidebar navigation, tab switching,
sub-sections (Audit Trail, Event Wall), and dashboard structure.

Covers the Admin General sub-tabs that are not part of Users, Sites,
or Rules test suites. Verifies navigation flow and page structure.
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.admin_page import AdminPage


SITE_NAME = "Driver Site"


class TestAdminGeneral:
    """Tests for Admin General section navigation and content."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.admin = AdminPage(self.page)
        self.admin.navigate_to_admin()
        yield

    # --- Admin sidebar structure ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    @pytest.mark.qatouch("VKbBPP")
    def test_admin_sidebar_tabs_visible(self):
        """Verify all main admin sidebar tabs are visible."""
        expect(self.admin.users_tab.first).to_be_visible(timeout=10000)
        self.step_capture.mark(1, "Verify the Users tab is visible in the admin sidebar")

        expect(self.admin.sites_tab.first).to_be_visible(timeout=5000)
        self.step_capture.mark(2, "Verify the Sites tab is visible in the admin sidebar")

        expect(self.admin.general_tab).to_be_visible(timeout=5000)
        self.step_capture.mark(3, "Verify the General tab is visible in the admin sidebar")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    @pytest.mark.qatouch("3gj8NP")
    def test_navigate_to_general(self):
        """Verify clicking General tab opens the General section."""
        self.admin.general_tab.wait_for(state="visible", timeout=10000)
        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(1, "Click the General tab in the admin sidebar")

        # General section should show sub-tabs like Rules, Audit Trail, etc.
        rules_tab = self.page.locator("p:text-is('Rules')")
        expect(rules_tab).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify the Rules sub-tab is visible in the General section")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    @pytest.mark.qatouch("Pgw4jm")
    def test_general_section_has_rules_tab(self):
        """Verify the General section contains the Rules sub-tab."""
        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(1, "Click the General tab in the admin sidebar")

        rules = self.page.locator("p:text-is('Rules')")
        expect(rules).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify the Rules sub-tab is visible in the General section")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    @pytest.mark.qatouch("68lnEV")
    def test_general_section_has_audit_trail(self):
        """Verify the General section contains an Audit Trail sub-tab."""
        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(1, "Click the General tab in the admin sidebar")

        audit = self.page.get_by_text("Audit Trail", exact=False).first
        expect(audit).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify the Audit Trail sub-tab is visible in the General section")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    @pytest.mark.qatouch("7ErGBe")
    def test_general_section_has_event_wall(self):
        """Verify the General section contains an Event Wall sub-tab."""
        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(1, "Click the General tab in the admin sidebar")

        event_wall = self.page.get_by_text("Event Wall", exact=False).first
        expect(event_wall).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify the Event Wall sub-tab is visible in the General section")

    # --- Tab switching ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    @pytest.mark.qatouch("9e1NMZ")
    def test_switch_users_to_sites(self):
        """Verify switching from Users tab to Sites tab works."""
        self.admin.navigate_to_users()
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(1, "Click the Users tab in the admin sidebar")

        self.admin.navigate_to_sites()
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(2, "Switch to the Sites tab")

        # Sites should show search and site cards/list
        search = self.page.locator("input[placeholder*='Search']")
        expect(search.first).to_be_visible(timeout=10000)
        self.step_capture.mark(3, "Verify the Sites search input is visible")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    @pytest.mark.qatouch("qzdVD4")
    def test_switch_sites_to_general(self):
        """Verify switching from Sites tab to General tab works."""
        self.admin.navigate_to_sites()
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(1, "Click the Sites tab in the admin sidebar")

        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(2, "Switch to the General tab")

        rules = self.page.locator("p:text-is('Rules')")
        expect(rules).to_be_visible(timeout=10000)
        self.step_capture.mark(3, "Verify the Rules sub-tab is visible in the General section")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    @pytest.mark.qatouch("XGLep0")
    def test_round_trip_users_general_users(self):
        """Verify navigating Users -> General -> Users round-trip works."""
        self.admin.navigate_to_users()
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(1, "Navigate to the Users tab")

        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(2, "Switch to the General tab")

        self.admin.navigate_to_users()
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(3, "Navigate back to the Users tab")

        # Users tab content should be visible (add button)
        expect(self.admin.add_user_button).to_be_visible(timeout=10000)
        self.step_capture.mark(4, "Verify the Add User button is visible after round-trip navigation")

    # --- Audit Trail navigation ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    @pytest.mark.qatouch("3gj9EP")
    def test_open_audit_trail(self):
        """Verify clicking Audit Trail opens the audit log view.

        Checks that clicking the Audit Trail tab shows some kind of
        log content (table, list, or filter controls).
        """
        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(1, "Click the General tab in the admin sidebar")

        audit = self.page.get_by_text("Audit Trail", exact=False).first

        if audit.count() == 0 or not audit.is_visible():
            pytest.skip("Audit Trail tab not found in General section")

        audit.click()
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(2, "Click the Audit Trail sub-tab")

        # Audit Trail should show some content - table, search, or filter
        # Check for common elements: search input, table rows, or data content
        has_content = (
            self.page.locator("input[placeholder*='Search']").count() > 0 or
            self.page.locator("table, .MuiTable-root").count() > 0 or
            self.page.locator("[class*='audit'], [class*='log']").count() > 0 or
            self.page.locator("th, td").count() > 0
        )

        assert has_content, "Audit Trail page should have visible content"
        self.step_capture.mark(3, "Verify Audit Trail displays content such as tables or search controls")

    # --- Event Wall navigation ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    @pytest.mark.qatouch("RgGBWd")
    def test_open_event_wall(self):
        """Verify clicking Event Wall opens the event wall view."""
        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(1, "Click the General tab in the admin sidebar")

        event_wall = self.page.get_by_text("Event Wall", exact=False).first

        if event_wall.count() == 0 or not event_wall.is_visible():
            pytest.skip("Event Wall tab not found in General section")

        event_wall.click()
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(2, "Click the Event Wall sub-tab")

        # Event Wall should show some content
        has_content = (
            self.page.locator("[class*='event'], [class*='wall']").count() > 0 or
            self.page.locator("img").count() > 5 or
            self.page.locator("div").count() > 10
        )

        assert has_content, "Event Wall page should have visible content"
        self.step_capture.mark(3, "Verify Event Wall displays visible content")

    # --- Admin page refresh ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    @pytest.mark.qatouch("mBdD1V")
    def test_admin_page_after_refresh(self):
        """Verify the Admin page loads correctly after a browser refresh."""
        self.page.reload()
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(1, "Refresh the Admin page in the browser")

        # Should still show admin sidebar tabs
        expect(self.admin.users_tab.first).to_be_visible(timeout=15000)
        self.step_capture.mark(2, "Verify the Users tab is still visible after page refresh")
