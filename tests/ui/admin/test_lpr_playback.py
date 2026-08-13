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
        if not SITE_NAME or not CAMERA_NAME:
            pytest.skip(
                "test_site_name / test_camera_name not configured "
                "for this ENV (see config/env/)"
            )
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
        expect(
            self.page.get_by_text(SITE_NAME, exact=False).first
        ).to_be_visible()

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
        # The live icon shows only on an activated tile
        expect(
            self.page.locator("img[alt='live icon']").first
        ).to_be_visible(timeout=10000)

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
        # Visible-filtered: MUI keeps detached hidden backdrops in the
        # DOM, so a bare count (or a .first peek) checks the wrong thing
        expect(
            self.page.locator("div[class*='MuiBackdrop-root']:visible")
        ).to_have_count(0)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.flaky(reruns=1)
    def test_open_playback_timeout_popup(self):
        """Verify the timeout popup opens for a playing LPR stream.

        The popup opens only while a stream plays; without one the
        icon click yields nothing but its tooltip.
        """
        self.step_capture.mark(1, "Play the configured camera")
        self.lpr.ensure_lpr_camera_page()
        self.lpr.play_camera(site_name=SITE_NAME, camera_name=CAMERA_NAME)

        self.step_capture.mark(2, "Open the playback timeout popup")
        self.lpr.open_playback_timeout_popup()
        # Dialog-scoped: page-wide Cancel picks can land elsewhere
        popup = self.page.get_by_text("Set Timeout Duration").first\
            .locator("xpath=ancestor::*[.//*[text()='Save']][1]")
        expect(popup.get_by_text("Cancel", exact=True).first)\
            .to_be_visible()

        self.step_capture.mark(3, "Cancel and clear the view")
        popup.get_by_text("Cancel", exact=True).first.click()
        expect(
            self.page.get_by_text("Set Timeout Duration").first
        ).to_be_hidden(timeout=10000)
        self.lpr.clear_all_tiles()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.livestream
    @pytest.mark.flaky(reruns=1)
    def test_open_lpr_playback_timeout_popup(self):
        """Verify the LPR timeout popup opens and closes cleanly."""
        self.step_capture.mark(1, "Play the configured camera")
        self.lpr.ensure_lpr_camera_page()
        self.lpr.play_camera(site_name=SITE_NAME, camera_name=CAMERA_NAME)

        self.step_capture.mark(2, "Open the LPR playback timeout popup")
        self.lpr.open_lpr_playback_timeout_popup()
        # Dialog-scoped: page-wide Save/Cancel picks can land elsewhere
        popup = self.page.get_by_text("Set Timeout Duration").first\
            .locator("xpath=ancestor::*[.//*[text()='Save']][1]")
        expect(popup.get_by_text("Save", exact=True).first)\
            .to_be_visible()

        self.step_capture.mark(3, "Cancel and clear the view")
        popup.get_by_text("Cancel", exact=True).first.click()
        expect(
            self.page.get_by_text("Set Timeout Duration").first
        ).to_be_hidden(timeout=10000)
        self.lpr.clear_all_tiles()


class TestLprViewsIntegration:
    """Tests for LPR integration with Views page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        if not SITE_NAME or not CAMERA_NAME:
            pytest.skip(
                "test_site_name / test_camera_name not configured "
                "for this ENV (see config/env/)"
            )
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
        """Verify the configured camera plays from its site group.

        The oracle lives in play_camera: it raises when the camera is
        missing or no new stream appears past the baseline.
        """
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
        """Verify the whole camera group plays onto the tiles.

        The oracle lives in play_camera: it raises when no new stream
        appears past the baseline after the group drop.
        """
        self.step_capture.mark(1, "Navigate to LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, f"Play all cameras of '{SITE_NAME}'")
        self.lpr.play_camera(site_name=SITE_NAME, play_all_cameras=True)

        self.step_capture.mark(3, "Clear the view")
        self.lpr.clear_all_tiles()
