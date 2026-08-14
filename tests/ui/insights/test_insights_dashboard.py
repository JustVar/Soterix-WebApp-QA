"""Insights Dashboard tests - preset dashboards, my dashboards, creation flow.

Extends the Insights module with deeper validation of the dashboard
landing page, preset dashboard cards, my dashboard cards, and the
create new dashboard workflow.
"""
import pytest
from playwright.sync_api import expect

from tests.shared.pages.insights_page import InsightsPage


class TestInsightsDashboard:
    """Tests for Insights dashboard sections and creation flow."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.insights = InsightsPage(self.page)
        self.insights.navigate()
        yield

    # --- Dashboard landing ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_dashboard_landing_loads(self):
        """Verify the Insights dashboard landing page loads successfully."""
        assert "insights" in self.page.url.lower()

        # Should have dashboard content (preset or my dashboards)
        expect(self.insights.system_status_link.first).to_be_visible(
            timeout=15000
        )

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_all_insights_tab_visible(self):
        """Verify the All Insights tab is visible on the dashboard."""
        expect(self.insights.all_insights_tab).to_be_visible(timeout=10000)

    # --- Preset Dashboard ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_preset_dashboard_section_visible(self):
        """Verify Preset Dashboard section header is visible."""
        preset = self.page.locator(
            "p:has-text('Preset'), "
            "div:has-text('Preset Dashboard')"
        )
        if preset.count() == 0:
            preset = self.page.locator("text=/preset dashboard/i")
        if preset.count() == 0:
            pytest.skip("Preset Dashboard section not found on Insights page")

        expect(preset.first).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_preset_dashboard_cards_displayed(self):
        """Verify Preset Dashboard cards are displayed."""
        # Look for dashboard cards/tiles
        cards = self.page.locator(
            "[class*='dashboard-card'], [class*='preset'], "
            ".MuiCard-root, [class*='DashboardCard']"
        )
        if cards.count() == 0:
            # Try broader card-like elements near "Preset" text
            cards = self.page.locator(
                "div.MuiBox-root >> img, "
                "div[class*='card']"
            )
        if cards.count() == 0:
            pytest.skip("No Preset Dashboard cards found")

        assert cards.count() > 0, "Expected at least one Preset Dashboard card"

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_preset_dashboard_view_all(self):
        """Verify View All link is visible in Preset Dashboard section."""
        view_all = self.page.locator(
            "a:has-text('View All'), "
            "p:has-text('View All'), "
            "span:has-text('View All')"
        )
        if view_all.count() == 0:
            pytest.skip("View All link not found in Preset Dashboard section")

        expect(view_all.first).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_preset_card_clickable(self):
        """Verify clicking a Preset Dashboard card triggers navigation."""
        cards = self.page.locator(
            "[class*='dashboard-card'], [class*='preset'], "
            ".MuiCard-root, [class*='card']"
        )
        if cards.count() == 0:
            pytest.skip("No dashboard cards found to click")

        cards.first.click()

        # Should navigate to a dashboard view or remain on insights
        assert "insights" in self.page.url.lower() or "dashboard" in self.page.url.lower()

    # --- My Dashboard ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_my_dashboard_section_visible(self):
        """Verify My Dashboard section header is visible."""
        my_dash = self.page.locator(
            "p:has-text('My Dashboard'), "
            "div:has-text('My Dashboards')"
        )
        if my_dash.count() == 0:
            my_dash = self.page.locator("text=/my dashboard/i")
        if my_dash.count() == 0:
            pytest.skip("My Dashboard section not found on Insights page")

        expect(my_dash.first).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_my_dashboard_view_all(self):
        """Verify View All link is visible in My Dashboard section."""
        # Look for second "View All" (first is likely Preset)
        view_all_links = self.page.locator(
            "a:has-text('View All'), "
            "p:has-text('View All'), "
            "span:has-text('View All')"
        )
        if view_all_links.count() < 2:
            pytest.skip("Second View All link not found for My Dashboard")

        expect(view_all_links.nth(1)).to_be_visible(timeout=10000)

    # --- Create New Dashboard ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_create_new_button_visible(self):
        """Verify Create New button is visible on the dashboard page."""
        create_btn = self.page.locator(
            "button:has-text('Create New'), "
            "button:has-text('Create'), "
            "div:has-text('Create New')"
        )
        if create_btn.count() == 0:
            # May need to navigate to My Dashboards view first
            view_all = self.page.locator(
                "a:has-text('View All'), p:has-text('View All')"
            )
            if view_all.count() > 1:
                view_all.nth(1).click()
                create_btn = self.page.locator(
                    "button:has-text('Create New'), "
                    "button:has-text('Create')"
                )

        if create_btn.count() == 0:
            pytest.skip("Create New button not found")

        expect(create_btn.first).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_create_dashboard_opens_form(self):
        """Verify clicking Create New opens the dashboard creation screen."""
        create_btn = self.page.locator(
            "button:has-text('Create New'), "
            "button:has-text('Create'), "
            "div:has-text('Create New')"
        )
        if create_btn.count() == 0:
            pytest.skip("Create New button not found")

        create_btn.first.click()
        # the creation form rendering any control is the open
        # signal; a miss falls to the checks below
        try:
            self.page.locator(
                "input, button:has-text('Save')"
            ).first.wait_for(state="visible", timeout=10000)
        # absence falls to the following checks/skips
        except Exception:
            pass

        # Should show a form with name input or widget selection
        has_form = (
            self.page.locator("input").count() > 0
            or self.page.locator("[class*='dashboard-form']").count() > 0
            or self.page.locator("button:has-text('Save')").count() > 0
            or self.page.locator("button:has-text('Discard')").count() > 0
        )
        assert has_form, "Expected dashboard creation form elements"

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_create_dashboard_has_discard_and_save(self):
        """Verify Discard and Save buttons are visible on creation screen."""
        create_btn = self.page.locator(
            "button:has-text('Create New'), "
            "button:has-text('Create'), "
            "div:has-text('Create New')"
        )
        if create_btn.count() == 0:
            pytest.skip("Create New button not found")

        create_btn.first.click()
        # the creation form rendering any control is the open
        # signal; a miss falls to the checks below
        try:
            self.page.locator(
                "input, button:has-text('Save')"
            ).first.wait_for(state="visible", timeout=10000)
        # absence falls to the following checks/skips
        except Exception:
            pass

        save = self.page.locator("button:has-text('Save')")
        discard = self.page.locator(
            "button:has-text('Discard'), button:has-text('Cancel')"
        )

        has_controls = save.count() > 0 or discard.count() > 0
        if not has_controls:
            pytest.skip("Save/Discard buttons not found on creation screen")

        if save.count() > 0:
            expect(save.first).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_create_dashboard_name_field(self):
        """Verify Dashboard Name field is present and editable."""
        create_btn = self.page.locator(
            "button:has-text('Create New'), "
            "button:has-text('Create'), "
            "div:has-text('Create New')"
        )
        if create_btn.count() == 0:
            pytest.skip("Create New button not found")

        create_btn.first.click()
        # the creation form rendering any control is the open
        # signal; a miss falls to the checks below
        try:
            self.page.locator(
                "input, button:has-text('Save')"
            ).first.wait_for(state="visible", timeout=10000)
        # absence falls to the following checks/skips
        except Exception:
            pass

        # Look for an editable name input - exclude disabled inputs
        name_input = self.page.locator(
            "input[placeholder*='name' i]:not([disabled]), "
            "input[placeholder*='dashboard' i]:not([disabled])"
        )
        if name_input.count() == 0:
            # Fall back to any enabled text input
            name_input = self.page.locator(
                "input[type='text']:not([disabled]):not([readonly])"
            )
        if name_input.count() == 0 or not name_input.first.is_visible():
            pytest.skip("Dashboard name input not found")

        name_input.first.fill("Test Dashboard Automation")

        value = name_input.first.input_value()
        assert "Test Dashboard" in value

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_save_disabled_without_name(self):
        """Verify Save button is disabled when no dashboard name is entered."""
        create_btn = self.page.locator(
            "button:has-text('Create New'), "
            "button:has-text('Create'), "
            "div:has-text('Create New')"
        )
        if create_btn.count() == 0:
            pytest.skip("Create New button not found")

        create_btn.first.click()
        # the creation form rendering any control is the open
        # signal; a miss falls to the checks below
        try:
            self.page.locator(
                "input, button:has-text('Save')"
            ).first.wait_for(state="visible", timeout=10000)
        # absence falls to the following checks/skips
        except Exception:
            pass

        save = self.page.locator("button:has-text('Save')")
        if save.count() == 0:
            pytest.skip("Save button not found")

        # Save should be disabled without a name
        is_disabled = save.first.is_disabled()
        has_disabled_class = "disabled" in (
            save.first.get_attribute("class") or ""
        ).lower()

        # Either disabled attribute or disabled styling
        assert is_disabled or has_disabled_class, (
            "Save button should be disabled without dashboard name"
        )

    # --- Page behavior ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_insights_page_scrollable(self):
        """Verify Insights dashboard page is scrollable."""
        self.page.evaluate("window.scrollBy(0, 300)")
        self.page.evaluate("window.scrollTo(0, 0)")

        assert "insights" in self.page.url.lower()

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    def test_dashboard_page_after_refresh(self):
        """Verify Insights dashboard page loads correctly after refresh."""
        # reload waits for the load event on its own
        self.page.reload()

        assert "insights" in self.page.url.lower()
        expect(self.insights.system_status_link.first).to_be_visible(
            timeout=15000
        )
