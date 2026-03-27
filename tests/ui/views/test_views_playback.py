"""Deeper full screen player and playback control tests.

Extends basic fullscreen coverage with control bar element checks,
volume interaction, share/settings/overlays visibility, live mode
indicator, and multi-camera fullscreen transitions.
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.views_page import ViewsPage
from tests.shared.pages.fullscreen_page import FullScreenPage


SITE_NAME = "Driver Site"


class TestViewsPlayback:
    """Tests for deeper fullscreen playback controls and behavior."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.views = ViewsPage(self.page)
        self.views.navigate()
        self.views.wait_for_page_load()

        # Ensure at least one camera is in a tile
        video_tiles = self.page.locator(
            "[class*='video_container'][class*='new_video_player']"
        )
        if video_tiles.count() == 0:
            self.views.expand_site_and_show_cameras(SITE_NAME)
            self.page.wait_for_timeout(500)
            self.views.add_first_camera_via_checkbox()
            self.page.wait_for_timeout(2000)
            video_tiles.first.wait_for(state="visible", timeout=30000)

    def _enter_fullscreen(self) -> FullScreenPage:
        """Enter fullscreen on first tile and return FullScreenPage."""
        self.views.enter_fullscreen_on_tile(0)
        fs = FullScreenPage(self.page)
        fs.wait_for_stream_loaded(timeout=120000)
        return fs

    # --- Control bar deeper checks ---

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.qatouch("Nj3r6e")
    def test_share_icon_visible_in_fullscreen(self):
        """Verify the share icon is visible in fullscreen player."""
        fs = self._enter_fullscreen()
        self.step_capture.mark(1, "Enter fullscreen on first camera tile")

        expect(fs.share_icon).to_be_visible(timeout=5000)
        self.step_capture.mark(2, "Verify share icon is visible in fullscreen")

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.qatouch("K4nmwJ")
    def test_settings_icon_visible_in_fullscreen(self):
        """Verify the settings icon is visible in fullscreen player."""
        fs = self._enter_fullscreen()
        self.step_capture.mark(1, "Enter fullscreen on first camera tile")

        expect(fs.settings_icon).to_be_visible(timeout=5000)
        self.step_capture.mark(2, "Verify settings icon is visible in fullscreen")

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.qatouch("jPn2ad")
    def test_overlays_icon_visible_in_fullscreen(self):
        """Verify the overlays icon is visible in fullscreen player."""
        fs = self._enter_fullscreen()
        self.step_capture.mark(1, "Enter fullscreen on first camera tile")

        expect(fs.overlays_icon).to_be_visible(timeout=5000)
        self.step_capture.mark(2, "Verify overlays icon is visible in fullscreen")

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.qatouch("41VXLb")
    def test_live_indicator_in_fullscreen(self):
        """Verify the live indicator is shown for a live camera stream."""
        fs = self._enter_fullscreen()
        self.step_capture.mark(1, "Enter fullscreen on first camera tile")

        if not fs.is_streaming():
            pytest.skip("Stream not active - cannot verify live indicator")

        # Live cameras should show the Live. indicator icon
        assert fs.is_live_mode(), (
            "Expected live mode indicator for a live camera stream"
        )
        self.step_capture.mark(2, "Verify live indicator is displayed in fullscreen")

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.qatouch("pDpdjG")
    def test_control_container_visible(self):
        """Verify the main control container is rendered in fullscreen."""
        fs = self._enter_fullscreen()
        self.step_capture.mark(1, "Enter fullscreen on first camera tile")

        expect(fs.control_container).to_be_visible(timeout=5000)
        self.step_capture.mark(2, "Verify control container is visible in fullscreen")

    # --- Volume interaction ---

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.qatouch("LD3g6e")
    def test_volume_control_clickable(self):
        """Verify clicking volume control doesn't crash (mute toggle)."""
        fs = self._enter_fullscreen()
        self.step_capture.mark(1, "Enter fullscreen on first camera tile")

        expect(fs.volume_control).to_be_visible(timeout=5000)
        self.step_capture.mark(2, "Verify volume control is visible in fullscreen")

        # Click volume (toggles mute)
        fs.volume_control.click()
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(3, "Click volume control to toggle mute")

        # Volume icon should still be visible (just changed state)
        volume_icons = self.page.locator("img[src*='media/volumn']")
        assert volume_icons.count() > 0, "Volume icon should still be present after click"
        self.step_capture.mark(4, "Verify volume icon is still present after click")

    # --- Fullscreen transitions ---

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.qatouch("wmjg7G")
    def test_exit_and_reenter_fullscreen(self):
        """Verify exiting fullscreen and re-entering works."""
        fs = self._enter_fullscreen()
        assert fs.is_streaming(), "Should stream on first entry"
        self.step_capture.mark(1, "Enter fullscreen and verify stream is active")

        # Exit
        fs.exit_fullscreen()
        self.page.wait_for_timeout(1000)
        self.views.add_tab_button.wait_for(state="visible", timeout=10000)
        self.step_capture.mark(2, "Exit fullscreen and return to Views page")

        # Re-enter
        fs2 = self._enter_fullscreen()
        assert fs2.is_streaming(), "Should stream after re-entering fullscreen"
        self.step_capture.mark(3, "Re-enter fullscreen and verify stream resumes")

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.qatouch("yaWrV9")
    def test_bookmarks_toggle_opens_panel(self):
        """Verify the bookmarks dots icon opens/closes the panel."""
        fs = self._enter_fullscreen()
        self.step_capture.mark(1, "Enter fullscreen on first camera tile")

        expect(fs.bookmarks_toggle).to_be_visible(timeout=5000)
        self.step_capture.mark(2, "Verify bookmarks toggle icon is visible")

        # Open bookmarks panel
        fs.open_bookmarks_panel()
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(3, "Open bookmarks panel")

        # Close bookmarks panel (toggle again)
        fs.close_bookmarks_panel()
        self.page.wait_for_timeout(500)
        self.step_capture.mark(4, "Close bookmarks panel")

        # Player should still be streaming after toggle
        assert fs.is_streaming(), "Stream should remain active after bookmark panel toggle"
        self.step_capture.mark(5, "Verify stream remains active after panel toggle")

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.flaky(reruns=1)
    @pytest.mark.qatouch("0rzxZb")
    def test_fullscreen_second_tile(self):
        """Verify fullscreen works on a second camera tile.

        Adds a second camera, enters fullscreen on it, and verifies streaming.
        """
        # Ensure site tree is expanded
        self.views.expand_site_and_show_cameras(SITE_NAME)
        self.page.wait_for_timeout(500)

        # Check if there's a second camera to add
        thumbnails = self.page.locator(".cameraThumbnailWrapper")
        if thumbnails.count() < 2:
            pytest.skip("Need at least 2 cameras for multi-tile test")

        # Hover and add second camera via checkbox
        second_camera = thumbnails.nth(1)
        second_camera.hover()
        self.page.wait_for_timeout(150)
        checkbox = second_camera.locator(".sidebar-custom-checkbox")
        checkbox.click()
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(1, "Add second camera to Views tile grid")

        # Enter fullscreen on second tile
        video_tiles = self.page.locator(
            "[class*='video_container'][class*='new_video_player']"
        )
        if video_tiles.count() < 2:
            pytest.skip("Second camera tile not loaded")

        self.views.enter_fullscreen_on_tile(1)
        fs = FullScreenPage(self.page)
        fs.wait_for_stream_loaded(timeout=120000)
        self.step_capture.mark(2, "Enter fullscreen on second camera tile")

        assert fs.is_streaming(), "Second camera should stream in fullscreen"
        self.step_capture.mark(3, "Verify second camera is streaming in fullscreen")

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.qatouch("kpZQr0")
    def test_timeline_elements_present(self):
        """Verify timeline-related elements exist in fullscreen.

        In LIVE mode, timeline controls are disabled but present.
        Verifies the pause icon is rendered (live-disabled or archive-active).
        """
        fs = self._enter_fullscreen()
        self.step_capture.mark(1, "Enter fullscreen on first camera tile")

        # At least one pause icon variant should be in the DOM
        has_live_pause = fs.pause_icon_live.count() > 0
        has_archive_pause = fs.pause_icon_archive.count() > 0

        assert has_live_pause or has_archive_pause, (
            "Expected at least one pause icon variant (live or archive mode)"
        )
        self.step_capture.mark(2, "Verify timeline pause icon is present in fullscreen")
