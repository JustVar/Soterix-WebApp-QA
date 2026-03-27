"""Insights page navigation and System Status tests.

Covers navigation to Insights page, System Status dashboard,
and Widgets tab switching.

Migrated from Selenium:
- test_insights_system_status_dashboard (line 2147)
- open_insights_page helper (line 219)
- switch_to_widgets helper (line 254)
"""
import pytest
from tests.shared.pages.insights_page import InsightsPage


SITE_NAME = "Driver Site"


class TestInsightsNavigation:
    """Tests for Insights page navigation and browsing."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.insights = InsightsPage(self.page)

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.qatouch("RgGQ4a")
    def test_navigate_to_insights(self):
        """Verify navigation to the Insights page via the sidebar."""
        self.insights.navigate()
        self.step_capture.mark(1, "Navigate to the Insights page via sidebar")

        assert "insights" in self.page.url.lower(), (
            f"Expected URL to contain 'insights', got: {self.page.url}"
        )
        self.step_capture.mark(2, "Verify URL contains 'insights'")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.qatouch("xm9jVZ")
    def test_system_status_link_visible(self):
        """Verify the System Status link is visible on the Insights page."""
        self.insights.navigate()
        self.step_capture.mark(1, "Navigate to the Insights page")

        expect = self.insights.system_status_link.first
        expect.wait_for(state="visible", timeout=15000)
        self.step_capture.mark(2, "Verify System Status link is visible")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.qatouch("lR2lDP")
    def test_open_system_status_dashboard(self):
        """Verify the System Status dashboard opens and loads for a site.

        Navigates to Insights, clicks System Status, selects Driver Site,
        and verifies 'Devices' text appears.
        """
        self.insights.open_system_status(SITE_NAME)
        self.step_capture.mark(1, "Open System Status dashboard for Driver Site")

        self.insights.devices_label.wait_for(
            state="visible", timeout=15000
        )
        self.step_capture.mark(2, "Verify Devices label is visible on the dashboard")

    @pytest.mark.ui
    @pytest.mark.insights
    def test_close_system_status_tab(self):
        """Verify the System Status tab can be closed."""
        self.insights.open_system_status(SITE_NAME)
        self.step_capture.mark(1, "Open System Status dashboard for Driver Site")

        self.insights.close_tab()
        self.step_capture.mark(2, "Close the System Status tab")

        # After closing, System Status link should be visible again
        self.insights.system_status_link.first.wait_for(
            state="visible", timeout=10000
        )
        self.step_capture.mark(3, "Verify System Status link reappears on landing page")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.qatouch("9e1b7W")
    def test_switch_to_widgets_tab(self):
        """Verify switching from Dashboard to Widgets tab."""
        self.insights.switch_to_widgets()
        self.step_capture.mark(1, "Switch to the Widgets tab")

        self.insights.my_widgets_text.wait_for(
            state="visible", timeout=15000
        )
        self.step_capture.mark(2, "Verify My Widgets text is visible")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.qatouch("gQxXLl")
    def test_create_widget_button_visible(self):
        """Verify the 'Create New Widget' button is visible in Widgets tab."""
        self.insights.switch_to_widgets()
        self.step_capture.mark(1, "Switch to the Widgets tab")

        self.insights.create_widget_button.wait_for(
            state="visible", timeout=15000
        )
        self.step_capture.mark(2, "Verify Create New Widget button is visible")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.qatouch("Pgw91d")
    def test_widget_search_input_visible(self):
        """Verify the widget search input is visible in Widgets tab."""
        self.insights.switch_to_widgets()
        self.step_capture.mark(1, "Switch to the Widgets tab")

        self.insights.search_input.wait_for(
            state="visible", timeout=15000
        )
        self.step_capture.mark(2, "Verify the widget search input is visible")
