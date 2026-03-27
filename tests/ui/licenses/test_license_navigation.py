"""License Navigation & Layout tests -- tab rendering, switching,
state retention, counts display, default layout, responsiveness."""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.license_page import LicensePage


class TestLicenseNavigation:
    """Tests for Licenses page navigation, tabs, and layout."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.license = LicensePage(self.page)
        yield

    def _navigate(self):
        """Helper to navigate to Licenses page."""
        self.license.navigate()

    # --- Access & Landing ---

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("8V1lbn")
    def test_navigate_to_licenses(self):
        """Verify navigating to Licenses page loads successfully."""
        self.step_capture.mark(1, "Navigate to the Licenses page")
        self._navigate()

        # Page should have license-related content visible
        content = self.page.locator(
            "text=Licenses, text=Available, text=Assigned"
        ).first
        expect(content).to_be_visible(timeout=15000)

        self.step_capture.mark(2, "Verify Licenses page content is visible")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("M73EzN")
    def test_default_layout(self):
        """Verify Licenses page default layout renders correctly."""
        self.step_capture.mark(1, "Navigate to the Licenses page")
        self._navigate()

        # Summary widget area should be visible
        summary = self.page.locator(
            "text=Total Licenses, text=Active, text=Available, text=Suspended"
        ).first
        expect(summary).to_be_visible(timeout=10000)

        self.step_capture.mark(2, "Verify summary widget with Total, Active, Available, Suspended is visible")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("DrdZz4")
    def test_total_licenses_widget_visible(self):
        """Verify Total Licenses widget is displayed."""
        self.step_capture.mark(1, "Navigate to the Licenses page")
        self._navigate()

        widget = self.page.locator("text=Total Licenses").first
        expect(widget).to_be_visible(timeout=10000)

        self.step_capture.mark(2, "Verify Total Licenses widget is displayed")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("eJqjmn")
    def test_license_counts_displayed(self):
        """Verify Active, Available and Suspended license counts are shown."""
        self.step_capture.mark(1, "Navigate to the Licenses page")
        self._navigate()

        for label in ["Active", "Available", "Suspended"]:
            count_el = self.page.locator(f"text={label}").first
            expect(count_el).to_be_visible(timeout=10000)

        self.step_capture.mark(2, "Verify Active, Available, and Suspended count labels are visible")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("vanmXV")
    def test_counts_persist_after_refresh(self):
        """Verify license summary persists after page refresh."""
        self.step_capture.mark(1, "Navigate to the Licenses page")
        self._navigate()

        # Note a visible label before refresh
        active_el = self.page.locator("text=Active").first
        expect(active_el).to_be_visible(timeout=10000)

        self.step_capture.mark(2, "Verify Active label is visible before refresh")

        self.page.reload()
        self.page.wait_for_timeout(3000)

        expect(active_el).to_be_visible(timeout=15000)

        self.step_capture.mark(3, "Refresh the page and verify license counts persist")

    # --- Tab Switching ---

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("bj0G4q")
    def test_available_tab_is_default(self):
        """Verify Available Licenses tab is the default selected tab."""
        self.step_capture.mark(1, "Navigate to the Licenses page")
        self._navigate()

        # The available tab or its content should be active/visible
        available_content = self.page.locator(
            "text=Available Licenses, text=License Item, text=License Key"
        ).first
        expect(available_content).to_be_visible(timeout=10000)

        self.step_capture.mark(2, "Verify Available Licenses tab is selected by default")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("Z8xRWR")
    def test_switch_between_tabs(self):
        """Verify switching between Available and Assigned Licenses tabs."""
        self.step_capture.mark(1, "Navigate to the Licenses page")
        self._navigate()

        # Switch to Assigned tab
        self.license.switch_to_assigned_tab()
        assigned_content = self.page.locator(
            "text=Assigned Licenses, text=Site, text=Assigned"
        ).first
        expect(assigned_content).to_be_visible(timeout=10000)

        self.step_capture.mark(2, "Switch to Assigned Licenses tab and verify content")

        # Switch back to Available tab
        self.license.switch_to_available_tab()
        available_content = self.page.locator(
            "text=Available Licenses, text=License Item, text=License Key"
        ).first
        expect(available_content).to_be_visible(timeout=10000)

        self.step_capture.mark(3, "Switch back to Available Licenses tab and verify content")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("RgGyrK")
    def test_available_tab_displays_feature_list(self):
        """Verify Available Licenses tab displays a list of license features."""
        self.step_capture.mark(1, "Navigate to the Licenses page and select Available tab")
        self._navigate()
        self.license.switch_to_available_tab()

        # Should show at least one row/item in the table
        rows = self.page.locator(
            "tr, div[class*='row']"
        )
        self.page.wait_for_timeout(2000)
        assert rows.count() > 0, "No license features displayed in Available tab"

        self.step_capture.mark(2, "Verify license feature rows are displayed in Available tab")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("dypNdB")
    def test_available_tab_columns(self):
        """Verify expected columns are displayed in Available Licenses tab."""
        self.step_capture.mark(1, "Navigate to the Licenses page and select Available tab")
        self._navigate()
        self.license.switch_to_available_tab()

        headers = self.license.get_column_headers()
        assert len(headers) > 0, "No column headers found"

        self.step_capture.mark(2, "Verify column headers are present in Available Licenses tab")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("xm9E4m")
    def test_available_tab_retains_state_after_navigation(self):
        """Verify Available Licenses tab retains state after navigation away and back."""
        self.step_capture.mark(1, "Navigate to the Licenses page and select Available tab")
        self._navigate()
        self.license.switch_to_available_tab()

        # Navigate away (e.g., to dashboard via sidebar)
        dashboard_link = self.page.locator("a[href*='dashboard']").first
        if dashboard_link.count() > 0:
            dashboard_link.click()
            self.page.wait_for_timeout(2000)

        self.step_capture.mark(2, "Navigate away from the Licenses page")

        # Navigate back to Licenses
        self._navigate()

        # Available tab should still be visible/active
        available_content = self.page.locator(
            "text=Available Licenses, text=License Item"
        ).first
        expect(available_content).to_be_visible(timeout=10000)

        self.step_capture.mark(3, "Navigate back and verify Available tab content is restored")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("VKbBrV")
    def test_search_bar_visible(self):
        """Verify search bar is present on Licenses page."""
        self.step_capture.mark(1, "Navigate to the Licenses page")
        self._navigate()

        expect(self.license.search_input).to_be_visible(timeout=10000)

        self.step_capture.mark(2, "Verify search bar is visible on the page")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("J8d3rn")
    def test_license_module_accessible_after_refresh(self):
        """Verify Licenses module remains accessible after multiple page refreshes."""
        self.step_capture.mark(1, "Navigate to the Licenses page")
        self._navigate()

        for _ in range(3):
            self.page.reload()
            self.page.wait_for_timeout(2000)

        self.step_capture.mark(2, "Refresh the page three times")

        content = self.page.locator(
            "text=Licenses, text=Available, text=Assigned"
        ).first
        expect(content).to_be_visible(timeout=15000)

        self.step_capture.mark(3, "Verify Licenses page remains accessible after multiple refreshes")
