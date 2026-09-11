"""Deeper full screen player and playback control tests.

Extends basic fullscreen coverage with control bar element checks,
volume interaction, share/settings/overlays visibility, live mode
indicator, and multi-camera fullscreen transitions.
"""
import pytest
from playwright.sync_api import Error as PlaywrightError, expect
from tests.shared.pages.views_page import ViewsPage
from tests.shared.pages.fullscreen_page import FullScreenPage


SITE_NAME = None


class TestViewsPlayback:
    """Tests for deeper fullscreen playback controls and behavior."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.views = ViewsPage(self.page)
        self.views.navigate()
        self.views.wait_for_page_load()

        # Ensure at least one camera is in a tile
        video_tiles = self.page.locator(
            "[class*='video_container'][class*='new_video_player']"
        )
        if video_tiles.count() == 0:
            self.views.expand_site_and_show_cameras(SITE_NAME)
            self.views.add_first_camera_via_checkbox()
            # the tile appearing is the added signal
            video_tiles.first.wait_for(state="visible", timeout=30000)

    def _enter_fullscreen(self) -> FullScreenPage:
        """Enter fullscreen on first tile and return FullScreenPage."""
        self.views.enter_fullscreen_on_tile(0)
        fs = FullScreenPage(self.page)
        fs.wait_for_stream_loaded(timeout=120000)
        # the loader clearing is not playing: a dead stream fails here,
        # named, instead of later at a click
        fs.assert_stream_playing()
        return fs

    # --- Control bar deeper checks ---

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_share_icon_visible_in_fullscreen(self):
        """Verify the share icon is visible in fullscreen player."""
        fs = self._enter_fullscreen()
        expect(fs.share_icon).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_settings_icon_visible_in_fullscreen(self):
        """Verify the settings icon is visible in fullscreen player."""
        fs = self._enter_fullscreen()
        expect(fs.settings_icon).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_overlays_icon_visible_in_fullscreen(self):
        """Verify the overlays icon is visible in fullscreen player."""
        fs = self._enter_fullscreen()
        expect(fs.overlays_icon).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_live_indicator_in_fullscreen(self):
        """Verify the live indicator is shown for a live camera stream."""
        fs = self._enter_fullscreen()

        # _enter_fullscreen already proved the stream plays, so this is
        # a contradiction, not an absent precondition (item 25).
        assert fs.is_streaming(), (
            "The fullscreen player passed assert_stream_playing but does "
            "not read as streaming, so the live indicator cannot be read"
        )

        # Live cameras should show the Live. indicator icon
        assert fs.is_live_mode(), (
            "Expected live mode indicator for a live camera stream"
        )

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_control_container_visible(self):
        """Verify the main control container is rendered in fullscreen."""
        fs = self._enter_fullscreen()
        expect(fs.control_container).to_be_visible(timeout=5000)

    # --- Volume interaction ---

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_volume_control_clickable(self):
        """Verify clicking volume control doesn't crash (mute toggle)."""
        fs = self._enter_fullscreen()
        expect(fs.volume_control).to_be_visible(timeout=5000)

        # Click volume (toggles mute)
        fs.volume_control.click()

        # the icon stays present through the mute toggle; the
        # retrying expect absorbs the state flip
        volume_icons = self.page.locator("img[src*='media/volumn']")
        expect(volume_icons.first).to_be_visible(timeout=5000)

    # --- Fullscreen transitions ---

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_exit_and_reenter_fullscreen(self):
        """Verify exiting fullscreen and re-entering works."""
        fs = self._enter_fullscreen()
        assert fs.is_streaming(), "Should stream on first entry"

        # Exit; the add-tab button returning is the signal
        fs.exit_fullscreen()
        self.views.add_tab_button.wait_for(state="visible", timeout=10000)

        # Re-enter
        fs2 = self._enter_fullscreen()
        assert fs2.is_streaming(), "Should stream after re-entering fullscreen"

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_bookmarks_toggle_opens_panel(self):
        """Verify the bookmarks dots icon opens/closes the panel."""
        fs = self._enter_fullscreen()
        expect(fs.bookmarks_toggle).to_be_visible(timeout=5000)

        # Open and close the bookmarks panel; both page-object calls
        # settle internally
        fs.open_bookmarks_panel()
        fs.close_bookmarks_panel()

        # Player should still be streaming after toggle
        assert fs.is_streaming(), "Stream should remain active after bookmark panel toggle"

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.flaky(reruns=1)
    @pytest.mark.livestream
    def test_fullscreen_second_tile(self):
        """Verify fullscreen works on a second camera tile.

        Adds a second camera, enters fullscreen on it, and verifies streaming.
        """
        # Ensure site tree is expanded (the call confirms cameras
        # visible on its own)
        self.views.expand_site_and_show_cameras(SITE_NAME)

        # Check if there's a second camera to add
        thumbnails = self.page.locator(".cameraThumbnailWrapper")
        if thumbnails.count() < 2:
            pytest.skip("Need at least 2 cameras for multi-tile test")

        # Hover and add second camera via checkbox; the click's own
        # actionability wait covers the hover-rendered checkbox
        second_camera = thumbnails.nth(1)
        second_camera.hover()
        checkbox = second_camera.locator(".sidebar-custom-checkbox")
        checkbox.click()

        # the second tile appearing is the added signal
        video_tiles = self.page.locator(
            "[class*='video_container'][class*='new_video_player']"
        )
        # The checkbox click above landed, so a second tile that never
        # appears is a failed add or a dead stream - both red, both
        # counted. The old handler reported it as Blocked (item 25).
        video_tiles.nth(1).wait_for(state="visible", timeout=15000)

        self.views.enter_fullscreen_on_tile(1)
        fs = FullScreenPage(self.page)
        fs.wait_for_stream_loaded(timeout=120000)

        # one user-path self-heal: the player intermittently shows
        # 'The camera failed to load' over a rendering live frame
        # (measured 08/13/2026); refresh recovers it
        fs.recover_stream_if_failed()

        assert fs.is_streaming(), "Second camera should stream in fullscreen"

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_timeline_elements_present(self):
        """Verify timeline-related elements exist in fullscreen.

        In LIVE mode, timeline controls are disabled but present.
        Verifies the pause icon is rendered (live-disabled or archive-active).

        Steps:
        1. On Views, open a camera tile in fullscreen.
           Expected: The stream plays and the player shows its timeline controls, with a pause control present (disabled in live mode, active in archive playback).
        """
        fs = self._enter_fullscreen()

        # At least one pause icon variant should be in the DOM
        has_live_pause = fs.pause_icon_live.count() > 0
        has_archive_pause = fs.pause_icon_archive.count() > 0

        assert has_live_pause or has_archive_pause, (
            "Expected at least one pause icon variant (live or archive mode)"
        )
