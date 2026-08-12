"""LPR camera playback and views integration tests.

Tests for LPR camera playback, timeout settings, and views page
integration. Playback flow: the Locations & Cameras panel starts
closed and lists site > camera groups > cameras; cameras drag onto
'Drag & Drop Camera here' tiles.
"""
import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.pages.lpr_page import LprPage

SITE_NAME = config.get("test_site_name")
CAMERA_NAME = config.get("test_camera_name")


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

        self.step_capture.mark(2, "Verify a playback tile is visible")
        expect(
            self.page.get_by_text("Drag & Drop Camera here", exact=True).first
        ).to_be_visible(timeout=15000)

        self.step_capture.mark(3, "Verify on correct URL")
        assert "/lpr" in self.page.url, "Not on LPR camera page"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_open_locations_dropdown(self):
        """Verify Locations & Cameras dropdown opens and lists the site."""
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, "Open the Locations & Cameras dropdown")
        self.lpr.ensure_lpr_dropdown_open()

        self.step_capture.mark(3, "Verify the configured site is listed")
        expect(
            self.page.get_by_text(SITE_NAME, exact=False).first
        ).to_be_visible(timeout=30000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_wait_for_site_list_loading(self):
        """Verify site list loads correctly."""
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, "Open the panel and wait for the site")
        self.lpr.ensure_lpr_dropdown_open()
        self.lpr.wait_for_site_list(SITE_NAME)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_safe_reset_to_views(self):
        """Verify safe reset lands on the Views page."""
        self.step_capture.mark(1, "Call safe reset to Views")
        self.lpr.safe_reset_to_views()

        self.step_capture.mark(2, "Verify the Views page is active")
        # Views renders at the root URL; the subtab bar is the marker
        expect(self.page.locator(".viewTabs").first).to_be_visible(
            timeout=15000
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.flaky(reruns=1)
    def test_camera_tile_activation(self):
        """Play the configured camera, then activate its tile."""
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, f"Play camera '{CAMERA_NAME}'")
        self.lpr.play_camera(site_name=SITE_NAME, camera_name=CAMERA_NAME)

        self.step_capture.mark(3, "Activate the camera tile")
        self.lpr.activate_camera_tile()
        expect(self.page.locator("video").first).to_be_visible(
            timeout=15000
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_dismiss_backdrop(self):
        """Verify backdrop dismissal leaves no click-blocking overlay."""
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, "Dismiss any backdrop")
        self.lpr.dismiss_any_backdrop()

        self.step_capture.mark(3, "Verify no backdrop blocks the page")
        backdrop = self.page.locator("div[class*='MuiBackdrop-root']")
        if backdrop.count() > 0:
            assert not backdrop.first.is_visible(), (
                "A backdrop still covers the page after dismissal"
            )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_open_playback_timeout_popup(self):
        """Verify playback timeout popup opens on the Views page."""
        self.step_capture.mark(1, "Navigate to the Views page")
        self.lpr.go_to_views_page()

        self.step_capture.mark(2, "Open the playback timeout popup")
        self.lpr.open_playback_timeout_popup()
        expect(
            self.page.get_by_text("Playback Auto-Timeout").first
        ).to_be_visible(timeout=10000)

        self.step_capture.mark(3, "Close the popup")
        self.page.keyboard.press("Escape")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_open_lpr_playback_timeout_popup(self):
        """Verify LPR playback timeout popup opens on the LPR page."""
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, "Open the LPR playback timeout popup")
        self.lpr.open_lpr_playback_timeout_popup()
        expect(
            self.page.get_by_text("Playback Auto-Timeout").first
        ).to_be_visible(timeout=10000)

        self.step_capture.mark(3, "Close the popup")
        self.page.keyboard.press("Escape")


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
        # Views renders at the root URL; the subtab bar is the marker
        expect(self.page.locator(".viewTabs").first).to_be_visible(
            timeout=15000
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_safe_views_navigation_on_non_views_page(self):
        """Verify safe navigation to Views works from non-Views pages."""
        self.step_capture.mark(1, "Navigate to LPR Lists page first")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Navigate to Views")
        self.lpr.go_to_views_page()

        self.step_capture.mark(3, "Verify the Views page is active")
        # Views renders at the root URL; the subtab bar is the marker
        expect(self.page.locator(".viewTabs").first).to_be_visible(
            timeout=15000
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.flaky(reruns=1)
    def test_play_camera_by_location(self):
        """Verify the configured camera plays from its site group."""
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, f"Play camera '{CAMERA_NAME}'")
        self.lpr.play_camera(site_name=SITE_NAME, camera_name=CAMERA_NAME)

        self.step_capture.mark(3, "Clear the view")
        self.lpr.clear_all_tiles()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.flaky(reruns=1)
    def test_play_all_cameras(self):
        """Verify the whole camera group plays onto the tiles."""
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, f"Play all cameras of '{SITE_NAME}'")
        self.lpr.play_camera(site_name=SITE_NAME, play_all_cameras=True)

        self.step_capture.mark(3, "Clear the view")
        self.lpr.clear_all_tiles()
