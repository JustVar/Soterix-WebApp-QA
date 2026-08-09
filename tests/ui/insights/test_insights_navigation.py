"""Insights page navigation and System Status tests.

Covers navigation to Insights page, System Status dashboard,
and Widgets tab switching.

Migrated from Selenium:
- test_insights_system_status_dashboard (line 2147)
- open_insights_page helper (line 219)
- switch_to_widgets helper (line 254)
"""
import pytest

from config.base_config import config
from tests.shared.pages.insights_page import InsightsPage

# The shared tenant renames sites, so the name lives in config
SITE_NAME = config.get("test_site_name")


class TestInsightsNavigation:
    """Tests for Insights page navigation and browsing."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.insights = InsightsPage(self.page)

    @pytest.mark.ui
    @pytest.mark.insights
    def test_navigate_to_insights(self):
        """Verify navigation to the Insights page via the sidebar."""
        self.insights.navigate()

        assert "insights" in self.page.url.lower(), (
            f"Expected URL to contain 'insights', got: {self.page.url}"
        )

    @pytest.mark.ui
    @pytest.mark.insights
    def test_system_status_link_visible(self):
        """Verify the System Status link is visible on the Insights page."""
        self.insights.navigate()

        expect = self.insights.system_status_link.first
        expect.wait_for(state="visible", timeout=15000)

    @pytest.mark.ui
    @pytest.mark.insights
    def test_open_system_status_dashboard(self):
        """Verify the System Status dashboard opens and loads for a site.

        Navigates to Insights, clicks System Status, selects the
        configured test site, and verifies 'Devices' text appears.
        """
        self.insights.open_system_status(SITE_NAME)

        self.insights.devices_label.wait_for(
            state="visible", timeout=15000
        )

    @pytest.mark.ui
    @pytest.mark.insights
    def test_close_system_status_tab(self):
        """Verify the System Status tab can be closed."""
        self.insights.open_system_status(SITE_NAME)
        self.insights.close_tab()

        # After closing, System Status link should be visible again
        self.insights.system_status_link.first.wait_for(
            state="visible", timeout=10000
        )

    @pytest.mark.ui
    @pytest.mark.insights
    def test_switch_to_widgets_tab(self):
        """Verify switching from Dashboard to Widgets tab."""
        self.insights.switch_to_widgets()

        self.insights.my_widgets_text.wait_for(
            state="visible", timeout=15000
        )

    @pytest.mark.ui
    @pytest.mark.insights
    def test_create_widget_button_visible(self):
        """Verify the 'Create New Widget' button is visible in Widgets tab."""
        self.insights.switch_to_widgets()

        self.insights.create_widget_button.wait_for(
            state="visible", timeout=15000
        )

    @pytest.mark.ui
    @pytest.mark.insights
    def test_widget_search_input_visible(self):
        """Verify the widget search input is visible in Widgets tab."""
        self.insights.switch_to_widgets()

        self.insights.search_input.wait_for(
            state="visible", timeout=15000
        )
