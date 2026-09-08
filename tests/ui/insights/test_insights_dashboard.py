"""Insights Dashboard tests - the landing page, its preset, and the creation flow.

Rebuilt 09/08/2026 against the measured page (register item 25; the
probes are in reports/probe_shots/insights_*). The old file guarded
every step with a `count() == 0 -> skip` on a union such as
`button:has-text('Create'), div:has-text('Create New')`: that union
matched 18 elements, its .first was an ancestor div, the click never
navigated, and the creation tests skipped every run. One of them then
passed anyway because its oracle was `input count > 0`, which the
landing's own Search box satisfies.

What the page is, measured on the US box:
- Landing (/insights): tabs 'My Dashboards' and 'Widgets', a Search
  box, ONE 'Create New' button, ONE 'View All', and the preset entry
  'System Status' as a link to /insights/systemStatus. There are no
  dashboard cards on this build; 'System Status' is the preset.
- View All stays on the landing on a tenant with no user dashboards.
- Create New opens /insights/createNewDashboard: an 'Enter Dashboard
  Name' field, an 'Add a widget' picker, and Discard/Save buttons.
  Save is disabled with no name AND still disabled with a name and no
  widget. Discard neither leaves the screen nor asks to confirm.
"""
import re

import pytest
from playwright.sync_api import expect

from tests.shared.pages.insights_page import InsightsPage

CREATE_URL = "/insights/createNewDashboard"
SYSTEM_STATUS_URL = "/insights/systemStatus"


class TestInsightsDashboard:
    """Tests for the Insights landing page and the dashboard creation flow."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.insights = InsightsPage(self.page)
        self.insights.navigate()
        # The preset link is the landing's loaded signal (it is what the
        # first test waits on); every test below starts from a proved page
        self.insights.system_status_link.first.wait_for(
            state="visible", timeout=15000
        )
        # Exact role and name: a has-text union here matched ancestor
        # divs and its .first click went nowhere (measured 09/08/2026)
        self.create_new = self.page.get_by_role(
            "button", name="Create New", exact=True
        )
        self.view_all = self.page.get_by_text("View All", exact=True).filter(
            visible=True
        )
        self.name_input = self.page.locator(
            "input[placeholder='Enter Dashboard Name']"
        )
        self.save = self.page.get_by_role("button", name="Save", exact=True)
        self.discard = self.page.get_by_role("button", name="Discard", exact=True)

    def _open_creation_screen(self):
        """Click Create New; the URL and the name field are the opened signal."""
        self.create_new.first.click()
        self.page.wait_for_url(f"**{CREATE_URL}**", timeout=15000)
        self.name_input.first.wait_for(state="visible", timeout=10000)

    # --- Dashboard landing ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_dashboard_landing_loads(self):
        """Verify the Insights dashboard landing page loads successfully.

        Steps:
        1. Click Insights in the left sidebar.
           Expected: The Insights page opens and lists the System Status preset.
        """
        assert "insights" in self.page.url.lower()
        expect(self.insights.system_status_link.first).to_be_visible(
            timeout=15000
        )

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_all_insights_tab_visible(self):
        """Verify the All Insights tab is visible on the dashboard.

        Steps:
        1. Click Insights in the left sidebar.
           Expected: The All Insights tab is shown at the top of the page.
        """
        expect(self.insights.all_insights_tab).to_be_visible(timeout=10000)

    # --- Preset dashboard (System Status) ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_preset_dashboard_section_visible(self):
        """Verify the landing shows its sections and the preset entry.

        Steps:
        1. Click Insights in the left sidebar.
           Expected: The page shows the My Dashboards and Widgets tabs and lists System Status as the preset dashboard.
        """
        expect(self.page.get_by_text("My Dashboards", exact=True)).to_be_visible()
        expect(self.page.get_by_text("Widgets", exact=True).first).to_be_visible()
        expect(self.insights.system_status_link.first).to_be_visible()

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_preset_dashboard_cards_displayed(self):
        """Verify the preset dashboard is listed as a link on the landing.

        This build lists the preset as a text link, not a card
        (measured 09/08/2026); the name keeps its historical wording so
        the QA Touch mapping stays stable.

        Steps:
        1. Click Insights in the left sidebar.
           Expected: System Status is listed and is a link to the system status dashboard.
        """
        link = self.insights.system_status_link.first
        expect(link).to_be_visible()
        expect(link).to_have_attribute("href", re.compile(re.escape(SYSTEM_STATUS_URL)))

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_preset_dashboard_view_all(self):
        """Verify the View All control is visible on the landing.

        Steps:
        1. Click Insights in the left sidebar.
           Expected: A View All control is shown next to the dashboard list.
        """
        expect(self.view_all.first).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_preset_card_clickable(self):
        """Verify clicking the preset entry opens the System Status dashboard.

        Steps:
        1. Click Insights in the left sidebar, then click System Status.
           Expected: The System Status dashboard opens and shows the Devices and Cameras panels.
        """
        self.insights.system_status_link.first.click()
        self.page.wait_for_url(f"**{SYSTEM_STATUS_URL}**", timeout=15000)
        expect(self.insights.devices_label).to_be_visible(timeout=15000)
        expect(self.page.get_by_text("Cameras", exact=True).first).to_be_visible()

    # --- My Dashboards ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_my_dashboard_section_visible(self):
        """Verify the My Dashboards tab is visible on the landing.

        Steps:
        1. Click Insights in the left sidebar.
           Expected: The My Dashboards tab is shown.
        """
        expect(self.page.get_by_text("My Dashboards", exact=True)).to_be_visible(
            timeout=10000
        )

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_my_dashboard_view_all(self):
        """Verify View All keeps the user on the landing when there is nothing more to list.

        Measured 09/08/2026 on a tenant with no user dashboards: the
        click stays on /insights and the landing controls remain. The
        old test wanted a second View All link that this build does not
        render.

        Steps:
        1. Click Insights in the left sidebar, then click View All.
           Expected: The page stays on the Insights landing and the Create New button is still shown.
        """
        self.view_all.first.click()
        expect(self.page).to_have_url(re.compile(r"/insights/?$"), timeout=10000)
        expect(self.create_new.first).to_be_visible()

    # --- Create New Dashboard ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_create_new_button_visible(self):
        """Verify the Create New button is visible on the landing.

        Steps:
        1. Click Insights in the left sidebar.
           Expected: A Create New button is shown above the dashboard list.
        """
        expect(self.create_new.first).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_create_dashboard_opens_form(self):
        """Verify clicking Create New opens the dashboard creation screen.

        Steps:
        1. Click Insights in the left sidebar, then Create New.
           Expected: The Create New Dashboard screen opens with a Dashboard Name field and an Add a widget picker.
        """
        self._open_creation_screen()
        expect(self.page.get_by_text("Add a widget", exact=True)).to_be_visible()
        expect(self.page.locator("input[placeholder='Search Widgets']")).to_be_visible()

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_create_dashboard_has_discard_and_save(self):
        """Verify Discard and Save buttons are shown on the creation screen.

        Steps:
        1. Click Insights in the left sidebar, then Create New.
           Expected: The creation screen shows a Discard button and a Save button.
        """
        self._open_creation_screen()
        expect(self.discard.first).to_be_visible(timeout=10000)
        expect(self.save.first).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_create_dashboard_name_field(self):
        """Verify the Dashboard Name field accepts a name.

        Steps:
        1. Click Insights in the left sidebar, then Create New.
           Expected: The creation screen shows an empty Dashboard Name field.
        2. Type a name into the field.
           Expected: The field shows the typed name.
        """
        self._open_creation_screen()
        expect(self.name_input.first).to_have_value("")
        self.name_input.first.fill("Test Dashboard Automation")
        expect(self.name_input.first).to_have_value("Test Dashboard Automation")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_save_disabled_without_name(self):
        """Verify Save stays disabled until the dashboard has a name and a widget.

        Measured 09/08/2026: Save is disabled with no name, and still
        disabled with a name and no widget. Nothing is saved here.

        Steps:
        1. Click Insights in the left sidebar, then Create New.
           Expected: The Save button is disabled.
        2. Type a dashboard name without adding a widget.
           Expected: The Save button is still disabled.
        """
        self._open_creation_screen()
        expect(self.save.first).to_be_disabled()
        self.name_input.first.fill("Test Dashboard Automation")
        expect(self.save.first).to_be_disabled()

    # --- Page behavior ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_insights_page_scrollable(self):
        """Verify the Insights landing survives scrolling.

        Steps:
        1. Click Insights in the left sidebar, scroll down and back up.
           Expected: The page stays on Insights and the System Status preset is still listed.
        """
        self.page.evaluate("window.scrollBy(0, 300)")
        self.page.evaluate("window.scrollTo(0, 0)")
        assert "insights" in self.page.url.lower()
        expect(self.insights.system_status_link.first).to_be_visible()

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_dashboard_page_after_refresh(self):
        """Verify the Insights landing loads again after a browser refresh.

        Steps:
        1. Click Insights in the left sidebar, then refresh the browser.
           Expected: The Insights landing loads again and lists the System Status preset.
        """
        # reload waits for the load event on its own
        self.page.reload()
        assert "insights" in self.page.url.lower()
        expect(self.insights.system_status_link.first).to_be_visible(
            timeout=15000
        )
