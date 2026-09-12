"""Insights page navigation and System Status tests.

Covers navigation to Insights page, System Status dashboard,
and Widgets tab switching. Every check reads a value the page shows:
the address, the preset link's target, the site the dashboard is on and
its device and camera counts adding up, the tab that is inactive, the
Create New button's label and the Search box's placeholder (measured
09/12/2026 on US; register row 53).

Migrated from Selenium:
- test_insights_system_status_dashboard (line 2147)
- open_insights_page helper (line 219)
- switch_to_widgets helper (line 254)
"""
import re

import pytest
from playwright.sync_api import expect

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
        """Verify the System Status preset link on the Insights page.

        Steps:
        1. Click Insights in the left sidebar.
           Expected: Under Preset Dashboard, a System Status link points at the system status dashboard.
        """
        self.insights.navigate()
        link = self.insights.system_status_link.first
        expect(link).to_be_visible(timeout=15000)
        expect(link).to_have_text("System Status")
        expect(link).to_have_attribute("href", re.compile(re.escape(InsightsPage.SYSTEM_STATUS_URL)))
        # the section header is one P: "Preset Dashboard <nbsp> | <nbsp>View All"
        header = self.page.locator("p").filter(has_text=re.compile(r"^Preset Dashboard"))
        expect(header).to_contain_text("View All")

    @pytest.mark.ui
    @pytest.mark.insights
    def test_open_system_status_dashboard(self):
        """Verify the System Status dashboard opens and loads for a site.

        Steps:
        1. Click Insights, then System Status, and select the configured site.
           Expected: The address ends in /insights/systemStatus and the site selector reads the site.
        2. Read the Devices, Cameras and Health Monitor panels.
           Expected: Devices' Total is the sum of its Cameras, Smoke Detector and Thermostats; the Cameras panel's Fixed, PTZ and Zoom add up to its Total, which equals the Devices' camera count; the Health Monitor's online and offline cameras add up to that total.
        """
        self.insights.open_system_status(SITE_NAME)
        expect(self.page).to_have_url(re.compile(re.escape(InsightsPage.SYSTEM_STATUS_URL)))
        expect(self.insights.devices_label).to_be_visible(timeout=15000)
        assert self.insights.selected_site_text() == SITE_NAME, (
            f"the site selector reads {self.insights.selected_site_text()!r}, not {SITE_NAME!r}")
        figures = self.insights.system_status_figures()
        devices, cameras = figures["devices"], figures["cameras"]
        assert devices["cameras"] + devices["smoke"] + devices["thermostats"] == devices["total"], (
            f"the Devices panel does not add up: {devices}")
        assert cameras["fixed"] + cameras["ptz"] + cameras["zoom"] == cameras["total"], (
            f"the Cameras panel does not add up: {cameras}")
        assert cameras["total"] == devices["cameras"], (
            f"the Cameras panel counts {cameras['total']}, the Devices panel {devices['cameras']}")
        assert figures["camera_online"] + figures["camera_offline"] == cameras["total"], (
            f"the Health Monitor's {figures['camera_online']} online and "
            f"{figures['camera_offline']} offline cameras do not add up to {cameras['total']}")

    @pytest.mark.ui
    @pytest.mark.insights
    def test_close_system_status_tab(self):
        """Verify the System Status tab can be closed.

        Steps:
        1. Click Insights in the left sidebar, then click System Status.
           Expected: The System Status dashboard opens with a site dropdown.
        2. Select the configured test site in the dropdown.
           Expected: The dashboard shows the Devices section.
        3. Click the close icon on the System Status tab.
           Expected: The address is back on /insights and the System Status link shows again under Preset Dashboard.
        """
        self.insights.open_system_status(SITE_NAME)
        expect(self.page).to_have_url(re.compile(re.escape(InsightsPage.SYSTEM_STATUS_URL)))
        self.insights.close_tab()
        expect(self.page).to_have_url(re.compile(r"/insights/?$"), timeout=10000)
        link = self.insights.system_status_link.first
        expect(link).to_be_visible(timeout=10000)
        expect(link).to_have_text("System Status")

    @pytest.mark.ui
    @pytest.mark.insights
    def test_switch_to_widgets_tab(self):
        """Verify switching from Dashboard to Widgets tab.

        Steps:
        1. Click Insights, then the Widgets tab.
           Expected: My Dashboards becomes the inactive tab, the page shows Preset Widgets and My Widgets, and the address stays on /insights.
        """
        self.insights.switch_to_widgets()
        expect(self.insights.inactive_tab).to_have_text("My Dashboards")
        # the section headers are one P each: "Preset Widgets <nbsp> | <nbsp>View All"
        # and "My Widgets <nbsp> | <nbsp>View All"
        expect(self.page.locator("p").filter(has_text=re.compile(r"^Preset Widgets"))).to_contain_text(
            "View All", timeout=15000)
        expect(self.insights.my_widgets_text).to_contain_text("View All", timeout=15000)
        expect(self.page).to_have_url(re.compile(r"/insights/?$"))

    @pytest.mark.ui
    @pytest.mark.insights
    def test_create_widget_button_visible(self):
        """Verify the Create New button in the Widgets tab.

        Steps:
        1. Click Insights, then the Widgets tab.
           Expected: One enabled Create New button is shown.
        """
        self.insights.switch_to_widgets()
        button = self.insights.create_widget_button
        expect(button).to_have_count(1)
        expect(button).to_have_text("Create New")
        expect(button).to_be_enabled()

    @pytest.mark.ui
    @pytest.mark.insights
    def test_widget_search_input_visible(self):
        """Verify the widget search box in the Widgets tab.

        Steps:
        1. Click Insights, then the Widgets tab.
           Expected: The search box is shown, empty, with the placeholder Search.
        """
        self.insights.switch_to_widgets()
        expect(self.insights.search_input).to_be_visible(timeout=15000)
        expect(self.insights.search_input).to_have_value("")
        expect(self.insights.search_input).to_have_attribute("placeholder", "Search")
