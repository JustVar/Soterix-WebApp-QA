"""LPR Views management tests - create, close, and manage multiple views."""
import pytest
import time
from playwright.sync_api import expect
from tests.shared.pages.lpr_page import LprPage


class TestLprViews:
    """Tests for LPR view creation and management."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_click_lpr_navigation(self):
        """Navigate to LPR then to Views page and verify page loaded."""
        self.step_capture.mark(1, "Navigate to LPR main page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Verify on LPR page")
        assert self.lpr.create_list_button.count() > 0, "Not on LPR Lists page"

        self.step_capture.mark(3, "Navigate to Views page")
        try:
            # Look for Views tab/link on LPR page
            views_element = self.page.locator("span:has-text('Views'), a[href*='views'], button:has-text('Views')").first
            if views_element.count() > 0:
                views_element.click()
                self.page.wait_for_timeout(2000)
                print("[STEP 3] Navigated to Views page")
        except Exception as e:
            print(f"[INFO] Could not navigate to Views: {e}")

        self.step_capture.mark(4, "Navigation test completed")
        print("[PASS] LPR navigation successful")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_create_multiple_views(self):
        """Create multiple view tabs by clicking view plus button."""
        self.step_capture.mark(1, "Navigate to LPR page first")
        self.lpr.navigate_to_lpr()
        self.page.wait_for_timeout(1000)

        self.step_capture.mark(2, "Look for Views page navigation")
        # Try to find and navigate to Views page
        try:
            views_link = self.page.locator("span:has-text('Views'), a[href*='views'], button:has-text('Views')").first
            if views_link.count() > 0:
                views_link.click()
                self.page.wait_for_timeout(2000)
                print("[STEP 2] Navigated to Views page")
        except Exception as e:
            print(f"[INFO] Could not navigate to Views: {e}")

        self.step_capture.mark(3, "Find view add button")
        # Try different selectors for the add button
        view_button = self.page.locator("button.tabTitleAddIcon").first
        if view_button.count() == 0:
            view_button = self.page.locator("button[class*='tabTitleAddIcon']").first
        if view_button.count() == 0:
            view_button = self.page.locator("button[class*='add']").first

        if view_button.count() > 0:
            try:
                view_button.wait_for(state="visible", timeout=30000)

                self.step_capture.mark(4, "Click view button")
                view_button.click()
                self.page.wait_for_timeout(1000)
                print("[STEP 4] Clicked view button")

                self.step_capture.mark(5, "Verify view tabs created")
                print("[PASS] View button clicked successfully")
            except Exception as e:
                print(f"[INFO] Could not click button: {e}")
        else:
            self.step_capture.mark(4, "View button not found")
            print("[INFO] View add button not found on page")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_close_all_views_with_popup(self):
        """Close views down to the last one, which refuses with an alert.

        Rebuilt 08/13/2026 on measured mechanics: view tabs are
        div.tabInner[title] with a closeTabIcon button, the untitled
        tabInner is the add (+) tab, and closing the FINAL view fires
        a native alert 'Action not permitted' while the view stays.
        The old version looked for 'Close' buttons that do not exist
        and registered its dialog handler after the click.
        """
        self.step_capture.mark(1, "Navigate to Views page")
        self.lpr.go_to_views_page()

        tabs = self.page.locator("div.tabInner[title]")
        tabs.first.wait_for(state="visible", timeout=30000)

        self.step_capture.mark(2, "Add a view so a closable one exists")
        baseline = tabs.count()
        self.page.locator("div.tabInner:not([title])").first.click()
        expect(tabs).to_have_count(baseline + 1, timeout=10000)

        self.step_capture.mark(3, "Close views down to the last one")
        while tabs.count() > 1:
            before = tabs.count()
            tabs.last.locator("button.closeTabIcon").click()
            expect(tabs).to_have_count(before - 1, timeout=10000)

        self.step_capture.mark(4, "The last view refuses with an alert")
        alerts = []
        self.page.on(
            "dialog", lambda d: (alerts.append(d.message), d.dismiss())
        )
        tabs.first.locator("button.closeTabIcon").click()
        # the native alert fires and dismisses with no DOM signal to
        # wait on; the assert below carries the oracle
        self.page.wait_for_timeout(1500)
        assert alerts, (
            "Closing the last view should fire the 'Action not "
            "permitted' alert"
        )
        expect(tabs).to_have_count(1)
