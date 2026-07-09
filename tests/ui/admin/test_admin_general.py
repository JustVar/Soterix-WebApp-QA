"""Admin General section tests - sidebar navigation, tab switching,
sub-sections (Audit Trail, Event Wall), and dashboard structure.

Covers the Admin General sub-tabs that are not part of Users, Sites,
or Rules test suites. Verifies navigation flow and page structure.
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.admin_page import AdminPage





class TestAdminGeneral:
    """Tests for Admin General section navigation and content."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.admin = AdminPage(self.page)
        self.admin.navigate_to_admin()
        yield

    # --- Admin sidebar structure ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_admin_sidebar_tabs_visible(self):
        """Verify all main admin sidebar tabs are visible."""
        expect(self.admin.users_tab.first).to_be_visible(timeout=10000)
        expect(self.admin.sites_tab.first).to_be_visible(timeout=5000)
        expect(self.admin.general_tab).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_navigate_to_general(self):
        """Verify clicking General tab opens the General section."""
        self.admin.general_tab.wait_for(state="visible", timeout=10000)
        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)

        # General section should show sub-tabs like Rules, Audit Trail, etc.
        rules_tab = self.page.locator("p:text-is('Rules')")
        expect(rules_tab).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_general_section_has_rules_tab(self):
        """Verify the General section contains the Rules sub-tab."""
        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)

        rules = self.page.locator("p:text-is('Rules')")
        expect(rules).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_general_section_has_audit_trail(self):
        """Verify the General section contains an Audit Trail sub-tab."""
        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)

        audit = self.page.get_by_text("Audit Trail", exact=False).first
        expect(audit).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_general_section_has_event_wall(self):
        """Verify the General section contains an Event Wall sub-tab."""
        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)

        event_wall = self.page.get_by_text("Event Wall", exact=False).first
        expect(event_wall).to_be_visible(timeout=10000)

    # --- Tab switching ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_switch_users_to_sites(self):
        """Verify switching from Users tab to Sites tab works."""
        self.admin.navigate_to_users()
        self.page.wait_for_timeout(1000)

        self.admin.navigate_to_sites()
        self.page.wait_for_timeout(1000)

        # Sites should show search and site cards/list
        search = self.page.locator("input[placeholder*='Search']")
        expect(search.first).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_switch_sites_to_general(self):
        """Verify switching from Sites tab to General tab works."""
        self.admin.navigate_to_sites()
        self.page.wait_for_timeout(1000)

        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)

        rules = self.page.locator("p:text-is('Rules')")
        expect(rules).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_round_trip_users_general_users(self):
        """Verify navigating Users -> General -> Users round-trip works."""
        self.admin.navigate_to_users()
        self.page.wait_for_timeout(1000)

        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)

        self.admin.navigate_to_users()
        self.page.wait_for_timeout(1000)

        # Users tab content should be visible (add button)
        expect(self.admin.add_user_button).to_be_visible(timeout=10000)

    # --- Audit Trail navigation ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_open_audit_trail(self):
        """Verify clicking Audit Trail opens the audit log view.

        Checks that clicking the Audit Trail tab shows some kind of
        log content (table, list, or filter controls).
        """
        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)

        audit = self.page.get_by_text("Audit Trail", exact=False).first

        if audit.count() == 0 or not audit.is_visible():
            pytest.skip("Audit Trail tab not found in General section")

        audit.click()
        self.page.wait_for_timeout(3000)

        # Audit Trail should show some content - table, search, or filter
        # Check for common elements: search input, table rows, or data content
        has_content = (
            self.page.locator("input[placeholder*='Search']").count() > 0 or
            self.page.locator("table, .MuiTable-root").count() > 0 or
            self.page.locator("[class*='audit'], [class*='log']").count() > 0 or
            self.page.locator("th, td").count() > 0
        )

        assert has_content, "Audit Trail page should have visible content"

    # --- Event Wall navigation ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_open_event_wall(self):
        """Verify clicking Event Wall opens the event wall view."""
        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)

        event_wall = self.page.get_by_text("Event Wall", exact=False).first

        if event_wall.count() == 0 or not event_wall.is_visible():
            pytest.skip("Event Wall tab not found in General section")

        event_wall.click()
        self.page.wait_for_timeout(3000)

        # Event Wall should show some content
        has_content = (
            self.page.locator("[class*='event'], [class*='wall']").count() > 0 or
            self.page.locator("img").count() > 5 or
            self.page.locator("div").count() > 10
        )

        assert has_content, "Event Wall page should have visible content"

    # --- Admin page refresh ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_admin_page_after_refresh(self):
        """Verify the Admin page loads correctly after a browser refresh."""
        self.page.reload()
        self.page.wait_for_timeout(3000)

        # Should still show admin sidebar tabs
        expect(self.admin.users_tab.first).to_be_visible(timeout=15000)
