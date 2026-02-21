"""License Navigation & Layout tests - tab rendering, switching,
state retention, counts display, default layout, responsiveness."""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.license_page import LicensePage


class TestLicenseNavigation:
    """Tests for Licenses page navigation, tabs, and layout."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.license = LicensePage(self.page)
        yield

    def _navigate(self):
        """Helper to navigate to Licenses page."""
        self.license.navigate()

    # --- Access & Landing ---

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_navigate_to_licenses(self):
        """Verify navigating to Licenses page loads successfully."""
        self._navigate()

        # Page should have license-related content visible
        content = self.page.locator(
            "text=Licenses, text=Available, text=Assigned"
        ).first
        expect(content).to_be_visible(timeout=15000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_default_layout(self):
        """Verify Licenses page default layout renders correctly."""
        self._navigate()

        # Summary widget area should be visible
        summary = self.page.locator(
            "text=Total Licenses, text=Active, text=Available, text=Suspended"
        ).first
        expect(summary).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_total_licenses_widget_visible(self):
        """Verify Total Licenses widget is displayed."""
        self._navigate()

        widget = self.page.locator("text=Total Licenses").first
        expect(widget).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_license_counts_displayed(self):
        """Verify Active, Available and Suspended license counts are shown."""
        self._navigate()

        for label in ["Active", "Available", "Suspended"]:
            count_el = self.page.locator(f"text={label}").first
            expect(count_el).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_counts_persist_after_refresh(self):
        """Verify license summary persists after page refresh."""
        self._navigate()

        # Note a visible label before refresh
        active_el = self.page.locator("text=Active").first
        expect(active_el).to_be_visible(timeout=10000)

        self.page.reload()
        self.page.wait_for_timeout(3000)

        expect(active_el).to_be_visible(timeout=15000)

    # --- Tab Switching ---

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_available_tab_is_default(self):
        """Verify Available Licenses tab is the default selected tab."""
        self._navigate()

        # The available tab or its content should be active/visible
        available_content = self.page.locator(
            "text=Available Licenses, text=License Item, text=License Key"
        ).first
        expect(available_content).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_switch_between_tabs(self):
        """Verify switching between Available and Assigned Licenses tabs."""
        self._navigate()

        # Switch to Assigned tab
        self.license.switch_to_assigned_tab()
        assigned_content = self.page.locator(
            "text=Assigned Licenses, text=Site, text=Assigned"
        ).first
        expect(assigned_content).to_be_visible(timeout=10000)

        # Switch back to Available tab
        self.license.switch_to_available_tab()
        available_content = self.page.locator(
            "text=Available Licenses, text=License Item, text=License Key"
        ).first
        expect(available_content).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_available_tab_displays_feature_list(self):
        """Verify Available Licenses tab displays a list of license features."""
        self._navigate()
        self.license.switch_to_available_tab()

        # Should show at least one row/item in the table
        rows = self.page.locator(
            "tr, div[class*='row']"
        )
        self.page.wait_for_timeout(2000)
        assert rows.count() > 0, "No license features displayed in Available tab"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_available_tab_columns(self):
        """Verify expected columns are displayed in Available Licenses tab."""
        self._navigate()
        self.license.switch_to_available_tab()

        headers = self.license.get_column_headers()
        assert len(headers) > 0, "No column headers found"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_available_tab_retains_state_after_navigation(self):
        """Verify Available Licenses tab retains state after navigation away and back."""
        self._navigate()
        self.license.switch_to_available_tab()

        # Navigate away (e.g., to dashboard via sidebar)
        dashboard_link = self.page.locator("a[href*='dashboard']").first
        if dashboard_link.count() > 0:
            dashboard_link.click()
            self.page.wait_for_timeout(2000)

        # Navigate back to Licenses
        self._navigate()

        # Available tab should still be visible/active
        available_content = self.page.locator(
            "text=Available Licenses, text=License Item"
        ).first
        expect(available_content).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_search_bar_visible(self):
        """Verify search bar is present on Licenses page."""
        self._navigate()

        expect(self.license.search_input).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_license_module_accessible_after_refresh(self):
        """Verify Licenses module remains accessible after multiple page refreshes."""
        self._navigate()

        for _ in range(3):
            self.page.reload()
            self.page.wait_for_timeout(2000)

        content = self.page.locator(
            "text=Licenses, text=Available, text=Assigned"
        ).first
        expect(content).to_be_visible(timeout=15000)
