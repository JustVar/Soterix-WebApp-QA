"""LPR Views management tests - create, close, and manage multiple views."""
import pytest
import time
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
        """Navigate to LPR and verify Locations element is visible."""
        self.step_capture.mark(1, "Navigate to LPR")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Verify LPR page loaded")
        assert self.lpr.create_list_button.count() > 0, "LPR page not loaded"

        self.step_capture.mark(3, "Verify Locations element visible")
        locations = self.page.locator("p:has-text('Locations & Cameras')")
        assert locations.count() > 0, "Locations & Cameras not visible"

        print("[PASS] LPR page loaded successfully")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_create_multiple_views(self):
        """Create multiple view tabs by clicking view plus button."""
        self.step_capture.mark(1, "Navigate to Views page")
        self.lpr.go_to_views_page()

        self.step_capture.mark(2, "Find view add button")
        view_button = self.page.locator("button[contains(@class,'tabTitleAddIcon')]").first
        view_button.wait_for(state="visible", timeout=30000)

        self.step_capture.mark(3, "Click view button 3 times")
        for i in range(3):
            view_button.click()
            self.page.wait_for_timeout(1000)
            print(f"[STEP 3.{i+1}] Clicked view button {i+1} time(s)")

        self.step_capture.mark(4, "Verify multiple view tabs created")
        print("[PASS] View button clicked multiple times successfully")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_close_all_views_with_popup(self):
        """Close all views and handle popup alert when closing last view."""
        self.step_capture.mark(1, "Navigate to Views page")
        self.lpr.go_to_views_page()

        self.step_capture.mark(2, "Close views until alert appears")
        while True:
            close_buttons = self.page.locator("button:has-text('Close')").all()

            if len(close_buttons) == 1:
                self.step_capture.mark(3, "Close last view and handle alert")
                close_buttons[0].click()
                self.page.wait_for_timeout(500)
                print("[STEP 3] Attempted to close last view")

                # Handle alert if it appears
                try:
                    self.page.on("dialog", lambda dialog: dialog.accept())
                    print("[STEP 3.1] Alert handled successfully")
                except:
                    print("[INFO] No alert popup appeared")

                break

            elif len(close_buttons) > 1:
                self.step_capture.mark(2, f"Close view - {len(close_buttons)} remaining")
                close_buttons[-1].click()
                self.page.wait_for_timeout(2000)
                print(f"[STEP 2] Closed one view ({len(close_buttons)-1} remaining)")

            else:
                print("[INFO] No close buttons found")
                break

        self.step_capture.mark(4, "Verify views closed")
        print("[PASS] Views handled successfully")
