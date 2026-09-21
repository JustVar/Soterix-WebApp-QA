"""Deeper full screen player and playback control tests.

Extends basic fullscreen coverage with control bar element checks,
volume interaction, share/settings/overlays visibility, live mode
indicator, and multi-camera fullscreen transitions.
"""
import datetime
import re

import pytest
from playwright.sync_api import Error as PlaywrightError, expect

from tests.shared.pages.fullscreen_page import FullScreenPage
from tests.shared.pages.views_page import ViewsPage

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
        """Verify the share icon is in the fullscreen control bar.

        Steps:
        1. Open a camera tile in fullscreen.
           Expected: The control bar carries exactly one share icon (icon-share).
        """
        fs = self._enter_fullscreen()
        expect(fs.share_icon).to_have_count(1, timeout=5000)
        assert fs.control_icon_names().count("icon-share") == 1, (
            f"the control bar's icons read {fs.control_icon_names()}")

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_settings_icon_visible_in_fullscreen(self):
        """Verify the settings icon is in the fullscreen control bar.

        Steps:
        1. Open a camera tile in fullscreen.
           Expected: The control bar carries exactly one settings icon (Setting).
        """
        fs = self._enter_fullscreen()
        expect(fs.settings_icon).to_have_count(1, timeout=5000)
        assert fs.control_icon_names().count("Setting") == 1, (
            f"the control bar's icons read {fs.control_icon_names()}")

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_overlays_icon_visible_in_fullscreen(self):
        """Verify the overlays icon is in the fullscreen control bar.

        Steps:
        1. Open a camera tile in fullscreen.
           Expected: The control bar carries exactly one overlays icon.
        """
        fs = self._enter_fullscreen()
        expect(fs.overlays_icon).to_have_count(1, timeout=5000)
        assert fs.control_icon_names().count("overlays") == 1, (
            f"the control bar's icons read {fs.control_icon_names()}")

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_live_indicator_in_fullscreen(self):
        """Verify the live indicator and clock for a live camera stream.

        Steps:
        1. Open a camera tile in fullscreen.
           Expected: The player reads as streaming in live mode, and the bar's clock shows today's date.
        """
        fs = self._enter_fullscreen()
        # _enter_fullscreen already proved the stream plays, so this is
        # a contradiction, not an absent precondition (item 25).
        assert fs.is_streaming() is True, (
            "The fullscreen player passed assert_stream_playing but does "
            "not read as streaming, so the live indicator cannot be read"
        )
        # Live cameras should show the Live. indicator icon
        assert fs.is_live_mode() is True, (
            "Expected live mode indicator for a live camera stream"
        )
        clock = fs.clock_text()
        assert clock, f"the control bar shows no clock; it reads {fs.control_container.inner_text()[:120]!r}"
        shown = datetime.datetime.strptime(clock, "%I:%M:%S %p %b %d %Y").date()
        assert abs((shown - datetime.date.today()).days) <= 1, (
            f"the live clock reads {clock!r}, today is {datetime.date.today()}")

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_control_container_visible(self):
        """Verify the main control bar carries its measured icon set.

        Steps:
        1. Open a camera tile in fullscreen.
           Expected: The control bar carries the exit, Live, date picker, share, Bookmark, sequence, Search, overlays, Setting and bookmarks-dots icons.
        """
        fs = self._enter_fullscreen()
        expect(fs.control_container).to_be_visible(timeout=5000)
        names = fs.control_icon_names()
        missing = [i for i in FullScreenPage.CONTROL_ICONS if i not in names]
        assert not missing, f"the control bar lacks {missing}; it carries {names}"

    # --- Volume interaction ---

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_volume_control_clickable(self):
        """Verify the volume control toggles mute and back.

        Steps:
        1. Open a camera tile in fullscreen and read the volume icon.
           Expected: It shows the muted icon (streams start muted).
        2. Click it, then click it again.
           Expected: The icon switches to the volume-on icon, then back to muted.
        """
        fs = self._enter_fullscreen()
        expect(fs.volume_control.first).to_be_visible(timeout=5000)
        before = fs.volume_icon_name()
        assert before in (FullScreenPage.VOLUME_ON, FullScreenPage.VOLUME_MUTED), (
            f"the volume icon reads {before!r}")
        other = FullScreenPage.VOLUME_ON if before == FullScreenPage.VOLUME_MUTED else FullScreenPage.VOLUME_MUTED
        fs.volume_control.first.click()
        expect(fs.volume_control.first).to_have_attribute("src", re.compile(other), timeout=5000)
        fs.volume_control.first.click()
        expect(fs.volume_control.first).to_have_attribute("src", re.compile(before), timeout=5000)

    # --- Fullscreen transitions ---

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_exit_and_reenter_fullscreen(self):
        """Verify exiting fullscreen and re-entering works.

        Steps:
        1. Open a camera tile in fullscreen, then exit.
           Expected: The exit button is gone and the Views tab bar is back.
        2. Enter fullscreen again.
           Expected: The stream plays again (its time advances).
        """
        fs = self._enter_fullscreen()
        # oracle: assert_stream_playing raises unless the video's time advances
        fs.assert_stream_playing()
        # Exit; the add-tab button returning is the signal
        fs.exit_fullscreen()
        self.views.add_tab_button.wait_for(state="visible", timeout=10000)
        expect(fs.exit_fullscreen_button).to_have_count(0)
        # Re-enter
        fs2 = self._enter_fullscreen()
        expect(fs2.exit_fullscreen_button).to_have_count(1)
        fs2.assert_stream_playing()

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_bookmarks_toggle_opens_panel(self):
        """Verify the bookmarks dots icon opens/closes the panel.

        Steps:
        1. Open a camera tile in fullscreen and click the bookmarks dots icon.
           Expected: The bookmarks panel opens (its rows are listed when the camera has bookmarks).
        2. Close the panel.
           Expected: The rows are gone and the stream still plays.
        """
        fs = self._enter_fullscreen()
        expect(fs.bookmarks_toggle).to_have_count(1, timeout=5000)
        # Open and close the bookmarks panel; both page-object calls
        # settle internally
        fs.open_bookmarks_panel()
        opened = fs.bookmark_items.count()
        fs.close_bookmarks_panel()
        expect(fs.bookmark_items.filter(visible=True)).to_have_count(0, timeout=5000)
        print(f"[PLAYBACK] the bookmarks panel listed {opened} bookmark(s)")
        # oracle: assert_stream_playing raises unless the video's time advances
        fs.assert_stream_playing()

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.intermittent
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
        # The oracle is assert_stream_playing. is_streaming only says that no spinner and no failure text show. The video
        # element's own word is the proof: a decoded frame, and a currentTime that moves.
        fs.assert_stream_playing()

    @pytest.mark.ui
    @pytest.mark.views_playback
    @pytest.mark.livestream
    def test_timeline_elements_present(self):
        """Verify timeline-related elements exist in fullscreen.

        In LIVE mode, timeline controls are disabled but present.

        Steps:
        1. On Views, open a camera tile in fullscreen.
           Expected: The stream plays live, the bar shows the live-mode pause control, and the timeline shows at least three hh:mm labels.
        """
        fs = self._enter_fullscreen()
        assert fs.is_live_mode() is True, "the player is not in live mode"
        expect(fs.pause_icon_live).to_have_count(1)
        labels = re.findall(r"\b\d{2}:\d{2}\b", " ".join(fs.control_container.inner_text().split()))
        assert len(labels) >= 3, f"the timeline shows {labels}; expected hh:mm labels"
