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
        self.lpr.go_to_views_page()
        # a titled view tab is the Views-page arrival signal
        expect(
            self.page.locator("div.tabInner[title]").first
        ).to_be_visible(timeout=15000)
        print("[STEP 3] Navigated to Views page")

        self.step_capture.mark(4, "Navigation test completed")
        print("[PASS] LPR navigation successful")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_create_multiple_views(self):
        """Create multiple view tabs by clicking view plus button."""
        self.step_capture.mark(1, "Navigate to LPR page first")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Navigate to Views page")
        self.lpr.go_to_views_page()

        self.step_capture.mark(3, "Find view add (+) tab")
        tabs = self.page.locator("div.tabInner[title]")
        tabs.first.wait_for(state="visible", timeout=30000)
        add_tab = self.page.locator("div.tabInner:not([title])").first
        expect(add_tab).to_be_visible(timeout=10000)

        self.step_capture.mark(4, "Click the add (+) tab")
        before = tabs.count()
        add_tab.click()

        self.step_capture.mark(5, "Verify a new view tab was created")
        expect(tabs).to_have_count(before + 1, timeout=10000)

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
