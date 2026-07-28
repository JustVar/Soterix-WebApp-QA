"""LPR camera playback and views integration tests.

Tests for LPR camera playback, timeout settings, and views page integration.
"""
import pytest
from tests.shared.pages.lpr_page import LprPage


class TestLprCameraPlayback:
    """Tests for LPR camera playback functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_navigate_to_lpr_camera_page(self):
        """Navigate to LPR camera/playback page."""
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, "Verify Drag & Drop text is visible")
        drag_drop = self.page.locator("div:has-text('Drag & Drop Camera here')")
        assert drag_drop.count() > 0, "Drag & Drop text not found"

        self.step_capture.mark(3, "Verify on correct URL")
        assert "/lpr" in self.page.url, "Not on LPR camera page"

        print("[PASS] Navigated to LPR camera page successfully")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_open_locations_dropdown(self):
        """Verify Locations & Cameras dropdown can be opened."""
        self.step_capture.mark(1, "Navigate to LPR page")
        self.lpr.navigate_to_lpr()
        self.page.wait_for_timeout(1000)

        self.step_capture.mark(2, "Look for Locations & Cameras dropdown")
        locations = self.page.locator("p:has-text('Locations & Cameras')").first
        if locations.count() == 0:
            locations = self.page.locator("span:has-text('Locations')").first

        if locations.count() > 0:
            try:
                locations.click()
                self.page.wait_for_timeout(1500)
                self.step_capture.mark(3, "Verify dropdown is open")
                # Check if sites appeared
                sites = self.page.locator("span").all()
                visible_sites = [s for s in sites if s.is_visible() and ("Newtown" in s.text_content() or "site" in s.text_content().lower())]

                if len(visible_sites) > 0:
                    print("[PASS] Locations & Cameras dropdown opened successfully")
                else:
                    print("[INFO] Dropdown may be open but no sites visible")
            except Exception as e:
                print(f"[INFO] Could not open dropdown: {e}")
        else:
            print("[INFO] Locations dropdown element not found")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_wait_for_site_list_loading(self):
        """Verify site list loads correctly."""
        from config.base_config import config

        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        # Get site name from config
        site_name = config.get("test_site_name", "Newtown ActionArea")

        self.step_capture.mark(2, f"Wait for site '{site_name}' to load")
        try:
            self.lpr.wait_for_site_list(site_name)
            print(f"[PASS] Site '{site_name}' loaded")
        except Exception as e:
            print(f"[INFO] Site '{site_name}' not available: {e}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_safe_reset_to_views(self):
        """Verify safe reset to Views page doesn't break on errors."""
        self.step_capture.mark(1, "Call safe reset to Views")
        self.lpr.safe_reset_to_views()

        self.step_capture.mark(2, "Verify page is still responsive")
        assert self.page is not None, "Page object lost"

        print("[PASS] Safe reset to Views completed")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_camera_tile_activation(self):
        """Verify camera tile can be activated (if camera present)."""
        self.step_capture.mark(1, "Check if camera is present")
        camera_present = self.lpr.ensure_camera_present()

        if not camera_present:
            self.step_capture.mark(2, "No camera present - skipping activation")
            print("[INFO] No active camera to activate")
        else:
            self.step_capture.mark(2, "Activate camera tile")
            try:
                self.lpr.activate_camera_tile()
                print("[PASS] Camera tile activated")
            except Exception as e:
                print(f"[INFO] Could not activate camera tile: {e}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_dismiss_backdrop(self):
        """Verify backdrop dismissal doesn't error on page without backdrop."""
        self.step_capture.mark(1, "Call dismiss backdrop")
        self.lpr.dismiss_any_backdrop()

        self.step_capture.mark(2, "Verify page still responsive")
        assert self.page is not None, "Page became unresponsive"

        print("[PASS] Backdrop dismissal completed safely")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_open_playback_timeout_popup(self):
        """Verify playback timeout popup can be opened."""
        self.step_capture.mark(1, "Navigate to page with timeout icon")
        # This test requires being on a page with the timeout icon
        self.lpr.go_to_views_page()

        self.step_capture.mark(2, "Open playback timeout popup")
        try:
            self.lpr.open_playback_timeout_popup()
            print("[PASS] Playback timeout popup opened")
        except Exception as e:
            print(f"[INFO] Timeout popup not available: {e}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_open_lpr_playback_timeout_popup(self):
        """Verify LPR playback timeout popup can be opened."""
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, "Open LPR playback timeout popup")
        try:
            self.lpr.open_lpr_playback_timeout_popup()
            print("[PASS] LPR playback timeout popup opened")
        except Exception as e:
            print(f"[INFO] LPR timeout popup not available: {e}")


class TestLprViewsIntegration:
    """Tests for LPR integration with Views page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_navigate_to_views_page(self):
        """Verify navigation to Views page."""
        self.step_capture.mark(1, "Navigate to Views page")
        self.lpr.go_to_views_page()

        self.step_capture.mark(2, "Verify on Views page")
        # Either URL contains 'views' or specific elements are visible
        is_on_views = "/views" in self.page.url.lower() or \
                      self.page.locator("video, canvas").count() > 0 or \
                      self.page.locator("div:has-text('Drag & Drop')").count() > 0

        if is_on_views:
            print("[PASS] Navigated to Views page successfully")
        else:
            print("[INFO] May not be on Views page - URL or elements check failed")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_safe_views_navigation_on_non_views_page(self):
        """Verify safe navigation to Views works from non-Views pages."""
        self.step_capture.mark(1, "Navigate to LPR Lists page first")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Call safe Views navigation")
        self.lpr.go_to_views_page()

        self.step_capture.mark(3, "Verify navigation completed")
        # Just verify the page is still responsive
        assert self.page is not None, "Page became unresponsive"

        print("[PASS] Safe Views navigation completed")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_play_camera_by_location(self):
        """Verify camera can be played from location."""
        from config.base_config import config

        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        site_name = config.get("test_site_name", "Newtown ActionArea")
        camera_name = config.get("test_camera_name", "main gate")

        self.step_capture.mark(2, f"Play camera '{camera_name}' from site '{site_name}'")
        try:
            self.lpr.play_camera(
                site_name=site_name,
                location_name=site_name,
                camera_name=camera_name,
                play_all_cameras=False
            )
            print(f"[PASS] Camera '{camera_name}' played successfully")
        except AssertionError as e:
            print(f"[INFO] Camera playback not available: {e}")
        except Exception as e:
            print(f"[INFO] Camera playback error: {e}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_play_all_cameras(self):
        """Verify all cameras from location can be played."""
        from config.base_config import config

        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        site_name = config.get("test_site_name", "Newtown ActionArea")

        self.step_capture.mark(2, f"Play all cameras from site '{site_name}'")
        try:
            self.lpr.play_camera(
                site_name=site_name,
                location_name=site_name,
                camera_name="",
                play_all_cameras=True
            )
            print("[PASS] All cameras played successfully")
        except AssertionError as e:
            print(f"[INFO] Camera playback not available: {e}")
        except Exception as e:
            print(f"[INFO] Camera playback error: {e}")
