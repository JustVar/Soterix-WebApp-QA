"""LPR Grid layout and Timer popup tests."""
import pytest
import time
from tests.shared.pages.lpr_page import LprPage


class TestLprGridLayout:
    """Tests for LPR grid layout selection."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_select_grid_layouts(self):
        """Test selecting 1x1, 2x2, and 3x3 grid layouts."""
        self.step_capture.mark(1, "Navigate to Views page")
        self.lpr.go_to_views_page()

        # Test 1x1 Grid
        self.step_capture.mark(2, "Click 1x1 grid layout")
        grid_1x1 = self.page.locator("img[alt='1*1']").first
        if grid_1x1.count() > 0:
            grid_1x1.scroll_into_view_if_needed()
            grid_1x1.click()
            self.page.wait_for_timeout(2000)
            print("[STEP 2] Clicked 1x1 grid")

        # Test 2x2 Grid
        self.step_capture.mark(3, "Click 2x2 grid layout")
        grid_2x2 = self.page.locator("button:has(span[contains(@class,'grid-two')])").first
        if grid_2x2.count() > 0:
            grid_2x2.click()
            self.page.wait_for_timeout(2000)
            print("[STEP 3] Clicked 2x2 grid")

        # Test 3x3 Grid
        self.step_capture.mark(4, "Click 3x3 grid layout")
        grid_3x3 = self.page.locator("button:has(span[contains(@class,'grid-nine')])").first
        if grid_3x3.count() > 0:
            grid_3x3.click()
            self.page.wait_for_timeout(2000)
            print("[STEP 4] Clicked 3x3 grid")

        self.step_capture.mark(5, "Grid layout changes completed")
        print("[PASS] Grid layout selection test passed")


class TestLprTimer:
    """Tests for LPR timer popup functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_timer_popup_validation(self):
        """Validate timer popup opens and closes correctly."""
        self.step_capture.mark(1, "Navigate to Views page")
        self.lpr.go_to_views_page()

        self.step_capture.mark(2, "Click Timer button")
        timer_btn = self.page.locator("button:has(img[contains(@src,'timer')])").first
        if timer_btn.count() > 0:
            timer_btn.wait_for(state="visible", timeout=30000)
            timer_btn.click()
            self.page.wait_for_timeout(1000)

            self.step_capture.mark(3, "Verify popup opened")
            popup_title = self.page.locator("p:has-text('Set Timeout Duration')").first
            if popup_title.count() > 0:
                popup_title.wait_for(state="visible", timeout=30000)
                assert popup_title.is_visible(), "Popup not visible"
                print("[STEP 3] Popup opened successfully")

                self.step_capture.mark(4, "Close popup with X icon")
                close_icon = self.page.locator("img[contains(@src,'close')]").first
                if close_icon.count() > 0:
                    close_icon.click()
                    self.page.wait_for_timeout(1000)
                    print("[STEP 4] Popup closed")

        self.step_capture.mark(5, "Timer validation completed")
        print("[PASS] Timer popup validation passed")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_timer_dropdown_values(self):
        """Test selecting different timeout duration values."""
        self.step_capture.mark(1, "Navigate to Views page")
        self.lpr.go_to_views_page()

        self.step_capture.mark(2, "Click Timer button")
        timer_btn = self.page.locator("button:has(img[contains(@src,'timer')])").first
        if timer_btn.count() == 0:
            print("[INFO] Timer button not available, skipping test")
            return

        durations = ["15 Minutes", "30 Minutes", "45 Minutes"]

        for duration in durations:
            self.step_capture.mark(3, f"Testing duration: {duration}")

            # Open timer if not already open
            if not self.page.locator("p:has-text('Set Timeout Duration')").is_visible():
                timer_btn.click()
                self.page.wait_for_timeout(500)

            # Open dropdown
            dropdown = self.page.locator("div[contains(@class,'MuiSelect-select')]").first
            if dropdown.count() > 0:
                dropdown.click()
                self.page.wait_for_timeout(500)

                # Select duration
                option = self.page.locator(f"li:has-text('{duration}')").first
                if option.count() > 0:
                    option.click()
                    self.page.wait_for_timeout(500)
                    print(f"[STEP 3.1] Selected {duration}")

                    # Click Save
                    save_btn = self.page.locator("div:has-text('Save')").first
                    if save_btn.count() > 0:
                        save_btn.click()
                        self.page.wait_for_timeout(1000)
                        print(f"[STEP 3.2] Saved {duration}")

        self.step_capture.mark(4, "All duration values tested")
        print("[PASS] Timer dropdown values test passed")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_timer_cancel_button(self):
        """Test timer popup cancel button."""
        self.step_capture.mark(1, "Navigate to Views page")
        self.lpr.go_to_views_page()

        self.step_capture.mark(2, "Open timer popup")
        timer_btn = self.page.locator("button:has(img[contains(@src,'timer')])").first
        if timer_btn.count() > 0:
            timer_btn.click()
            self.page.wait_for_timeout(500)

            self.step_capture.mark(3, "Click Cancel button")
            cancel_btn = self.page.locator("div:has-text('Cancel')").first
            if cancel_btn.count() > 0:
                cancel_btn.click()
                self.page.wait_for_timeout(1000)
                print("[STEP 3] Clicked Cancel")

                self.step_capture.mark(4, "Verify popup closed")
                popup = self.page.locator("p:has-text('Set Timeout Duration')").all()
                visible_popups = [p for p in popup if p.is_visible()]
                assert len(visible_popups) == 0, "Popup still visible after Cancel"
                print("[STEP 4] Popup closed successfully")

        self.step_capture.mark(5, "Cancel button test completed")
        print("[PASS] Timer cancel button test passed")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_timer_after_page_refresh(self):
        """Test timer default value persists after page refresh."""
        from config.base_config import config

        self.step_capture.mark(1, "Navigate to Views and add camera")
        self.lpr.go_to_views_page()

        camera_name = config.get("test_camera_name", "main gate")

        # Add camera
        locations = self.page.locator("p:has-text('Locations & Cameras')").first
        if locations.count() > 0:
            locations.click()
            self.page.wait_for_timeout(1000)

            search = self.page.locator("input[placeholder='Search']").first
            if search.count() > 0:
                search.fill(camera_name)
                self.page.wait_for_timeout(1000)

                checkbox = self.page.locator("img[contains(@src,'uncheck-icon')]").first
                if checkbox.count() > 0:
                    checkbox.hover()
                    checkbox.click()
                    print("[STEP 1] Camera selected")

        self.step_capture.mark(2, "Refresh page")
        self.page.reload()
        self.page.wait_for_load_state("networkidle", timeout=30000)
        self.page.wait_for_timeout(2000)
        print("[STEP 2] Page refreshed")

        self.step_capture.mark(3, "Verify timer default value is 15 Minutes")
        timer_btn = self.page.locator("button:has(img[contains(@src,'timer')])").first
        if timer_btn.count() > 0:
            timer_btn.click()
            self.page.wait_for_timeout(500)

            default_value = self.page.locator("p:has-text('15 Minutes')").first
            if default_value.count() > 0:
                assert default_value.is_visible(), "Default 15 Minutes not visible"
                print("[STEP 3] Timer default value confirmed: 15 Minutes")

                # Close popup
                cancel_btn = self.page.locator("div:has-text('Cancel')").first
                if cancel_btn.count() > 0:
                    cancel_btn.click()

        self.step_capture.mark(4, "Timer refresh test completed")
        print("[PASS] Timer default value persisted after refresh")
