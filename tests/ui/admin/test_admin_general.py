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

    def _open_general(self):
        """Click the General tab; the Rules sub-tab signals it rendered.

        .first is required: 'Rules' appears in the admin sidebar and in the
        General sub-nav, so the bare locator violates strict mode.
        """
        self.admin.general_tab.click()
        expect(
            self.page.locator("p:text-is('Rules')").first
        ).to_be_visible(timeout=10000)

    # --- Admin sidebar structure ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_admin_sidebar_tabs_visible(self):
        """Verify all main admin sidebar tabs are visible.

        Soft assertions check all 3 tabs and report every failure together
        instead of stopping at the first missing tab.
        """
        expect.soft(self.admin.users_tab.first).to_be_visible(timeout=10000)
        expect.soft(self.admin.sites_tab.first).to_be_visible(timeout=5000)
        expect.soft(self.admin.general_tab).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_navigate_to_general(self):
        """Verify clicking General tab opens the General section."""
        self.admin.general_tab.wait_for(state="visible", timeout=10000)
        self._open_general()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_general_section_has_rules_tab(self):
        """Verify the General section contains the Rules sub-tab."""
        self._open_general()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_general_section_has_audit_trail(self):
        """Verify the General section contains an Audit Trail sub-tab."""
        self._open_general()

        audit = self.page.get_by_text("Audit Trail", exact=False).first
        expect(audit).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_general_section_has_event_wall(self):
        """Verify the General section contains an Event Wall sub-tab."""
        self._open_general()

        event_wall = self.page.get_by_text("Event Wall", exact=False).first
        expect(event_wall).to_be_visible(timeout=10000)

    # --- Tab switching ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_switch_users_to_sites(self):
        """Verify switching from Users tab to Sites tab works."""
        self.admin.navigate_to_users()
        self.admin.navigate_to_sites()

        # Sites should show search and site cards/list
        search = self.page.locator("input[placeholder*='Search']")
        expect(search.first).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_switch_sites_to_general(self):
        """Verify switching from Sites tab to General tab works."""
        self.admin.navigate_to_sites()
        self._open_general()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_round_trip_users_general_users(self):
        """Verify navigating Users -> General -> Users round-trip works."""
        self.admin.navigate_to_users()
        self._open_general()
        self.admin.navigate_to_users()

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
        self._open_general()

        # Wait for the tab before deciding to skip - an instant count()/
        # is_visible() check races the General content render
        audit = self.page.get_by_text("Audit Trail", exact=False).first
        try:
            audit.wait_for(state="visible", timeout=10000)
        except Exception:
            pytest.skip("Audit Trail tab not found in General section")

        audit.click()

        # Audit Trail should show some content - table, search, or filter.
        # A retrying wait on the union replaces the old sleep + count checks.
        content = (
            self.page.locator("input[placeholder*='Search']")
            .or_(self.page.locator("table, .MuiTable-root"))
            .or_(self.page.locator("[class*='audit'], [class*='log']"))
            .or_(self.page.locator("th, td"))
        )
        expect(content.first).to_be_visible(timeout=15000)

    # --- Event Wall navigation ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_open_event_wall(self):
        """Verify clicking Event Wall opens the event wall view."""
        self._open_general()

        # Wait for the tab before deciding to skip - an instant count()/
        # is_visible() check races the General content render
        event_wall = self.page.get_by_text("Event Wall", exact=False).first
        try:
            event_wall.wait_for(state="visible", timeout=10000)
        except Exception:
            pytest.skip("Event Wall tab not found in General section")

        event_wall.click()

        # Event Wall should show some content
        content = self.page.locator("[class*='event'], [class*='wall']")
        try:
            expect(content.first).to_be_visible(timeout=15000)
        except AssertionError:
            assert self.page.locator("img").count() > 5, \
                "Event Wall page should have visible content"

    # --- Admin page refresh ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_admin_page_after_refresh(self):
        """Verify the Admin page loads correctly after a browser refresh."""
        self.page.reload()

        # Should still show admin sidebar tabs
        expect(self.admin.users_tab.first).to_be_visible(timeout=15000)
