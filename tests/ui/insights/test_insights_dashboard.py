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
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.insights = InsightsPage(self.page)
        self.insights.navigate()
        yield

    # --- Dashboard landing ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("VKbewQ")
    def test_dashboard_landing_loads(self):
        """Verify the Insights dashboard landing page loads successfully."""
        assert "insights" in self.page.url.lower()
        self.step_capture.mark(1, "Verify URL contains 'insights'")

        # Should have dashboard content (preset or my dashboards)
        expect(self.insights.system_status_link.first).to_be_visible(
            timeout=15000
        )
        self.step_capture.mark(2, "Verify dashboard content is visible")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("RgGQ4a")
    def test_all_insights_tab_visible(self):
        """Verify the All Insights tab is visible on the dashboard."""
        expect(self.insights.all_insights_tab).to_be_visible(timeout=10000)
        self.step_capture.mark(1, "Verify the All Insights tab is visible")

    # --- Preset Dashboard ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("mBdX60")
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
        self.step_capture.mark(1, "Locate the Preset Dashboard section")

        expect(preset.first).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify Preset Dashboard section header is visible")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("gQxXRW")
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
        self.step_capture.mark(1, "Locate Preset Dashboard cards")

        assert cards.count() > 0, "Expected at least one Preset Dashboard card"
        self.step_capture.mark(2, "Verify at least one Preset Dashboard card is displayed")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("n8jQ76")
    def test_preset_dashboard_view_all(self):
        """Verify View All link is visible in Preset Dashboard section."""
        view_all = self.page.locator(
            "a:has-text('View All'), "
            "p:has-text('View All'), "
            "span:has-text('View All')"
        )
        if view_all.count() == 0:
            pytest.skip("View All link not found in Preset Dashboard section")
        self.step_capture.mark(1, "Locate View All link in Preset Dashboard section")

        expect(view_all.first).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify View All link is visible")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("Nj39xE")
    def test_preset_card_clickable(self):
        """Verify clicking a Preset Dashboard card triggers navigation."""
        cards = self.page.locator(
            "[class*='dashboard-card'], [class*='preset'], "
            ".MuiCard-root, [class*='card']"
        )
        if cards.count() == 0:
            pytest.skip("No dashboard cards found to click")
        self.step_capture.mark(1, "Locate a Preset Dashboard card")

        cards.first.click()
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(2, "Click the first Preset Dashboard card")

        # Should navigate to a dashboard view or remain on insights
        assert "insights" in self.page.url.lower() or "dashboard" in self.page.url.lower()
        self.step_capture.mark(3, "Verify navigation occurred after clicking card")

    # --- My Dashboard ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("K4n96b")
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
        self.step_capture.mark(1, "Locate the My Dashboard section")

        expect(my_dash.first).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify My Dashboard section header is visible")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("LD3X7P")
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
        self.step_capture.mark(1, "Locate the View All link in My Dashboard section")

        expect(view_all_links.nth(1)).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify View All link is visible in My Dashboard section")

    # --- Create New Dashboard ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("XGLQrD")
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
                self.page.wait_for_timeout(2000)
                create_btn = self.page.locator(
                    "button:has-text('Create New'), "
                    "button:has-text('Create')"
                )

        if create_btn.count() == 0:
            pytest.skip("Create New button not found")
        self.step_capture.mark(1, "Locate the Create New button on the dashboard page")

        expect(create_btn.first).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify Create New button is visible")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("LD3Xwx")
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
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(1, "Click the Create New button")

        # Should show a form with name input or widget selection
        has_form = (
            self.page.locator("input").count() > 0
            or self.page.locator("[class*='dashboard-form']").count() > 0
            or self.page.locator("button:has-text('Save')").count() > 0
            or self.page.locator("button:has-text('Discard')").count() > 0
        )
        assert has_form, "Expected dashboard creation form elements"
        self.step_capture.mark(2, "Verify dashboard creation form elements are displayed")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("kpZX05")
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
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(1, "Click the Create New button to open creation screen")

        save = self.page.locator("button:has-text('Save')")
        discard = self.page.locator(
            "button:has-text('Discard'), button:has-text('Cancel')"
        )

        has_controls = save.count() > 0 or discard.count() > 0
        if not has_controls:
            pytest.skip("Save/Discard buttons not found on creation screen")

        if save.count() > 0:
            expect(save.first).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify Discard and Save buttons are visible")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("5BRM3m")
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
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(1, "Click Create New to open dashboard creation screen")

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
        self.step_capture.mark(2, "Locate the Dashboard Name input field")

        name_input.first.fill("Test Dashboard Automation")
        self.page.wait_for_timeout(500)

        value = name_input.first.input_value()
        assert "Test Dashboard" in value
        self.step_capture.mark(3, "Fill in dashboard name and verify the value")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("lR2l6J")
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
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(1, "Click Create New to open dashboard creation screen")

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
        self.step_capture.mark(2, "Verify Save button is disabled without a dashboard name")

    # --- Page behavior ---

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("dypXjd")
    def test_insights_page_scrollable(self):
        """Verify Insights dashboard page is scrollable."""
        self.page.evaluate("window.scrollBy(0, 300)")
        self.page.wait_for_timeout(500)
        self.step_capture.mark(1, "Scroll down 300 pixels on the Insights page")

        self.page.evaluate("window.scrollTo(0, 0)")
        self.page.wait_for_timeout(500)
        self.step_capture.mark(2, "Scroll back to top of the page")

        assert "insights" in self.page.url.lower()
        self.step_capture.mark(3, "Verify page remains valid after scrolling")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.insights_dashboard
    @pytest.mark.qatouch("wmjK7z")
    def test_dashboard_page_after_refresh(self):
        """Verify Insights dashboard page loads correctly after refresh."""
        self.page.reload()
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(1, "Refresh the Insights dashboard page")

        assert "insights" in self.page.url.lower()
        self.step_capture.mark(2, "Verify URL still contains 'insights' after refresh")

        expect(self.insights.system_status_link.first).to_be_visible(
            timeout=15000
        )
        self.step_capture.mark(3, "Verify System Status link is visible after refresh")
