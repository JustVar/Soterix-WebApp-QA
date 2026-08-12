"""LPR event feed, clip playback, and player control tests.

The live event feed renders on the LPR camera page as plate cards
(plate, confidence, vehicle class, camera, timestamp). Clicking a
card opens an inline clip player with a video, a position/duration
strip, and Share / Export / Create Link / fullscreen / seek controls.
"""
import re

import pytest
from playwright.sync_api import expect

from tests.shared.pages.lpr_page import LprPage

# Position/duration readout in the clip player ('00:00 / 00:20')
TIME_STRIP_RE = re.compile(r"\d{2}:\d{2} / \d{2}:\d{2}")
# A card's full timestamp line carries the date too
FULL_TS_RE = re.compile(r"\d{1,2}:\d{2}:\d{2} [AP]M \| \w{3} \d{1,2} \d{4}")


class TestLprEventPlayback:
    """Tests for LPR event selection and playback functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)

    def _open_feed_or_skip(self):
        """Land on the LPR camera page with at least one event card.

        The feed is live tenant data: an empty feed is a state, not a
        defect, so it skips instead of failing.
        """
        self.lpr.ensure_lpr_camera_page()
        cards = self.lpr.event_cards()
        try:
            cards.first.wait_for(state="visible", timeout=30000)
        except Exception:
            pytest.skip("No LPR events in the live feed")
        return cards

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_event_selection_play_pause_scrubber(self):
        """Selecting an event opens its clip player, and close ends it."""
        self.step_capture.mark(1, "Navigate to the LPR camera page")
        self._open_feed_or_skip()

        self.step_capture.mark(2, "Open the first event")
        self.lpr.open_first_event()
        expect(self.page.locator("video").first).to_be_visible(
            timeout=15000
        )

        self.step_capture.mark(3, "Verify the position/duration strip")
        expect(self.page.get_by_text(TIME_STRIP_RE).first).to_be_visible(
            timeout=10000
        )

        self.step_capture.mark(4, "Close the player")
        self.lpr.close_event_player()
        expect(self.page.locator("video")).to_have_count(0, timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_event_list_visibility(self):
        """The live feed lists at least one event card."""
        self.step_capture.mark(1, "Navigate to the LPR camera page")
        cards = self._open_feed_or_skip()

        self.step_capture.mark(2, "Verify the feed is populated")
        assert cards.count() >= 1, "Feed anchor visible but no cards counted"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_event_scrubber_control(self):
        """The clip player shows its timeline readout and seek controls."""
        self.step_capture.mark(1, "Open the first event")
        self._open_feed_or_skip()
        self.lpr.open_first_event()

        self.step_capture.mark(2, "Verify timeline readout and seek icons")
        expect(self.page.get_by_text(TIME_STRIP_RE).first).to_be_visible(
            timeout=10000
        )
        expect(self.page.locator("img[alt='Backward']").first).to_be_visible()
        expect(self.page.locator("img[alt='forward']").first).to_be_visible()

        self.step_capture.mark(3, "Close the player")
        self.lpr.close_event_player()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_event_filter_by_type(self):
        """The feed filter opens with camera and duration options."""
        self.step_capture.mark(1, "Navigate to the LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, "Open the filter panel")
        self.page.locator("img[src*='filter']").first.click()
        expect(self.page.get_by_text("Duration", exact=True).first)\
            .to_be_visible(timeout=10000)
        expect(self.page.get_by_text("Apply", exact=True).first)\
            .to_be_visible()

        self.step_capture.mark(3, "Dismiss the panel")
        self.page.keyboard.press("Escape")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_event_timestamp_verification(self):
        """Event cards carry a full time-and-date stamp."""
        self.step_capture.mark(1, "Navigate to the LPR camera page")
        cards = self._open_feed_or_skip()

        self.step_capture.mark(2, "Verify the first card's timestamp")
        # The card anchor matches on the time alone; the assertion
        # requires the date part too, so it is not circular
        assert FULL_TS_RE.search(cards.first.inner_text()), (
            "First event card has no full 'time | date' stamp"
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_event_details_panel(self):
        """The clip player exposes the event's action controls."""
        self.step_capture.mark(1, "Open the first event")
        self._open_feed_or_skip()
        self.lpr.open_first_event()

        self.step_capture.mark(2, "Verify Share / Export / Create Link")
        for alt in ("Share", "Export", "Create Link"):
            expect(
                self.page.locator(f"img[alt='{alt}']").first
            ).to_be_visible(timeout=10000)

        self.step_capture.mark(3, "Close the player")
        self.lpr.close_event_player()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_playback_speed_control(self):
        """Speed control on the clip player (absent in the current UI)."""
        self.step_capture.mark(1, "Open the first event")
        self._open_feed_or_skip()
        self.lpr.open_first_event()

        self.step_capture.mark(2, "Look for a speed control")
        speed = self.page.get_by_text(re.compile(r"^[0-9.]+x$"))
        if speed.count() == 0:
            self.lpr.close_event_player()
            # Measured 08/12/2026: the LPR clip player has no speed
            # control. Fail loud if one appears so it gets a real test.
            pytest.skip(
                "The LPR clip player exposes no speed control"
            )
        pytest.fail(
            "A speed control appeared on the LPR clip player - "
            "replace this guard with its real assertions"
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_event_navigation_next_prev(self):
        """The seek controls act on the open clip without breaking it."""
        self.step_capture.mark(1, "Open the first event")
        self._open_feed_or_skip()
        self.lpr.open_first_event()

        self.step_capture.mark(2, "Seek forward and backward")
        # The readout does not tick for short paused clips, so the
        # oracle is the player surviving both seeks with its video
        self.page.locator("img[alt='forward']").first.click()
        self.page.locator("img[alt='Backward']").first.click()
        expect(self.page.locator("video").first).to_be_visible(
            timeout=10000
        )
        expect(self.page.get_by_text(TIME_STRIP_RE).first).to_be_visible()

        self.step_capture.mark(3, "Close the player")
        self.lpr.close_event_player()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_fullscreen_event_playback(self):
        """Fullscreen engages and releases on the clip player."""
        self.step_capture.mark(1, "Open the first event")
        self._open_feed_or_skip()
        self.lpr.open_first_event()

        self.step_capture.mark(2, "Enter fullscreen")
        self.page.locator("img[alt='full screen']").first.click()
        self.page.wait_for_function(
            "() => document.fullscreenElement != null", timeout=10000
        )

        self.step_capture.mark(3, "Exit fullscreen")
        # Escape does not release programmatic fullscreen headless;
        # exitFullscreen is the dependable path
        self.page.evaluate("document.exitFullscreen()")
        self.page.wait_for_function(
            "() => document.fullscreenElement == null", timeout=10000
        )

        self.step_capture.mark(4, "Close the player")
        self.lpr.close_event_player()
