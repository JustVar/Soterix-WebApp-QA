"""LPR event feed, clip playback, and player control tests.

The live event feed renders on the LPR camera page as plate cards
(plate, confidence, vehicle class, camera, timestamp). Clicking a
card opens an inline clip player with a video, a position/duration
strip, and Share / Export / Create Link / fullscreen / seek controls.
"""
import re
import time

import pytest
from playwright.sync_api import TimeoutError as PWTimeoutError, expect

from tests.shared.pages.lpr_page import LprPage

# Position/duration readout in the clip player ('00:00 / 00:20')
# When the feed was last measured empty in this process (time.monotonic()).
# An empty feed costs the full wait to prove. On india the feed is empty most
# nights, and 8 tests each paid the 30 s (09/21/2026 nightly: 4 minutes of the
# leg). The first test pays it. For the next 5 minutes the others wait 5 s: a
# feed that fills in that time still shows within it.
_FEED_EMPTY = {"at": None}
FEED_WAIT_MS = 30000
FEED_RECHECK_MS = 5000
FEED_EMPTY_HOLDS_S = 300


def _feed_wait_ms(now: float | None = None) -> int:
    """The wait for the first event card: short when the feed was measured empty a moment ago."""
    now = time.monotonic() if now is None else now
    at = _FEED_EMPTY["at"]
    return FEED_RECHECK_MS if at is not None and now - at < FEED_EMPTY_HOLDS_S else FEED_WAIT_MS


TIME_STRIP_RE = re.compile(r"\d{2}:\d{2} / \d{2}:\d{2}")
# A card's full timestamp line carries the date too (tolerant of the
# time and date landing in sibling nodes)
FULL_TS_RE = re.compile(
    r"\d{1,2}:\d{2}:\d{2} [AP]M\s*\|\s*\w{3} \d{1,2} \d{4}"
)


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
        defect, so it skips - but only a genuinely empty feed. Feed
        content that the card anchor fails to match is locator rot
        and fails loud instead of hiding as nine data-state skips.
        """
        self.lpr.ensure_lpr_camera_page()
        cards = self.lpr.event_cards()
        try:
            cards.first.wait_for(state="visible", timeout=_feed_wait_ms())
        # deliberate: this timeout means the feed is empty, and the
        # branch below proves that before it skips - it fails loud when
        # the feed HAS content and only the card anchor missed
        except PWTimeoutError:
            has_content = (
                self.page.get_by_text(re.compile(r"\d+%")).count() > 0
                or self.page.get_by_text(
                    re.compile(r"\d{1,2}:\d{2}:\d{2}")
                ).count() > 0
            )
            if has_content:
                pytest.fail(
                    "The feed shows event content but no card matched "
                    "the timestamp anchor - the card locator rotted"
                )
            _FEED_EMPTY["at"] = time.monotonic()
            pytest.skip("No LPR events in the live feed")
        _FEED_EMPTY["at"] = None
        return cards

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_event_selection_play_pause_scrubber(self):
        """Selecting an event opens its clip player, and close ends it.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens and the event feed lists plate cards.
        2. Click the first event card.
           Expected: The clip player opens with a video and a position readout such as 00:00 / 00:20.
        3. Click the close icon on the player.
           Expected: The player closes and no video remains.
        """
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
        """The live feed lists at least one event card.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens.
        2. Look at the event feed.
           Expected: At least one event card shows a plate, a confidence, a camera, and a timestamp.
        """
        self.step_capture.mark(1, "Navigate to the LPR camera page")
        cards = self._open_feed_or_skip()

        self.step_capture.mark(2, "Verify the feed is populated")
        # Polling count: the live feed re-renders as events arrive,
        # so an instant read can catch a transient zero
        expect(cards).not_to_have_count(0, timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_event_scrubber_control(self):
        """The clip player shows its timeline readout and seek controls.

        Steps:
        1. Click LPR in the left sidebar, then click the first event card in the feed.
           Expected: The clip player opens with a video.
        2. Look at the player controls.
           Expected: The player shows the position readout and the Backward and Forward seek icons.
        3. Click the close icon on the player.
           Expected: The player closes.
        """
        self.step_capture.mark(1, "Open the first event")
        self._open_feed_or_skip()
        self.lpr.open_first_event()

        self.step_capture.mark(2, "Verify timeline readout and seek icons")
        # .first: the open player shows one position readout (mm:ss / mm:ss)
        expect(self.page.get_by_text(TIME_STRIP_RE).first).to_have_text(
            TIME_STRIP_RE, timeout=10000
        )
        expect(self.page.locator("img[alt='Backward']")).not_to_have_count(0)
        expect(self.page.locator("img[alt='forward']")).not_to_have_count(0)

        self.step_capture.mark(3, "Close the player")
        self.lpr.close_event_player()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_event_filter_by_type(self):
        """The feed filter opens with camera and duration options.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The LPR camera page opens.
        2. Click the Filter icon above the event feed.
           Expected: The filter panel opens with Cameras and Duration sections and an Apply button.
        """
        self.step_capture.mark(1, "Navigate to the LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(2, "Open the filter panel")
        # The filter icon ships no alt text and no testid; its src is
        # the only handle it has
        self.page.locator("img[src*='filter']").first.click()
        expect(self.page.get_by_text("Cameras", exact=True).first)\
            .to_be_visible(timeout=10000)
        expect(self.page.get_by_text("Duration", exact=True)).not_to_have_count(0)
        expect(self.page.get_by_text("Apply", exact=True)).not_to_have_count(0)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_event_timestamp_verification(self):
        """Event cards carry a full time-and-date stamp.

        Steps:
        1. Click LPR in the left sidebar.
           Expected: The event feed lists at least one card.
        2. Read the timestamp line on the first card.
           Expected: The line shows a time and a date, for example 1:37:38 AM | Aug 11 2026.
        """
        self.step_capture.mark(1, "Navigate to the LPR camera page")
        cards = self._open_feed_or_skip()

        self.step_capture.mark(2, "Verify the first card's timestamp")
        # The card anchor matches on the time alone; the assertion
        # requires the date part too, so it is not circular
        assert FULL_TS_RE.search(cards.first.inner_text()) is not None, (
            "First event card has no full 'time | date' stamp"
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_event_details_panel(self):
        """The clip player exposes the event's action controls.

        Steps:
        1. Click LPR in the left sidebar, then click the first event card in the feed.
           Expected: The clip player opens with a video.
        2. Look at the action icons on the player.
           Expected: The player shows Share, Export, and Create Link icons.
        3. Click the close icon on the player.
           Expected: The player closes.
        """
        self.step_capture.mark(1, "Open the first event")
        self._open_feed_or_skip()
        self.lpr.open_first_event()

        self.step_capture.mark(2, "Verify Share / Export / Create Link")
        for alt in ("Share", "Export", "Create Link"):
            expect(
                self.page.locator(f"img[alt='{alt}']").first
            ).to_be_visible(timeout=10000)
            expect(self.page.locator(f"img[alt='{alt}']")).not_to_have_count(0)

        self.step_capture.mark(3, "Close the player")
        self.lpr.close_event_player()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_playback_speed_control(self):
        """Speed control on the clip player (absent in the current UI).

        Steps:
        1. Click LPR in the left sidebar, then click the first event card in the feed.
           Expected: The clip player opens with its position readout.
        2. Look for a playback speed control such as 1x.
           Expected: No speed control is shown. The current player has none.
        """
        self.step_capture.mark(1, "Open the first event")
        self._open_feed_or_skip()
        self.lpr.open_first_event()

        self.step_capture.mark(2, "Look for a speed control")
        # The player chrome renders after the video attaches; decide
        # only once the timeline readout proves the chrome is up
        expect(self.page.get_by_text(TIME_STRIP_RE).first).to_be_visible(
            timeout=10000
        )
        speed = self.page.get_by_text(re.compile(r"^[0-9.]+x$"))
        try:
            speed.first.wait_for(state="visible", timeout=3000)
        # deliberate: the player chrome is proved up by the timeline
        # readout above, so this timeout is the measured absence of a
        # speed control, not a page that failed to load
        except PWTimeoutError:
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
        """The seek controls act on the open clip without breaking it.

        Steps:
        1. Click LPR in the left sidebar, then click the first event card in the feed.
           Expected: The clip player opens with a video.
        2. Click the Forward icon, then the Backward icon.
           Expected: The video and the position readout stay visible.
        3. Click the close icon on the player.
           Expected: The player closes.
        """
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
        """Fullscreen engages and releases on the clip player.

        Steps:
        1. Click LPR in the left sidebar, then click the first event card in the feed.
           Expected: The clip player opens with a video.
        2. Click the full screen icon.
           Expected: The player fills the screen.
        3. Exit full screen.
           Expected: The player returns to its inline size.
        4. Click the close icon on the player.
           Expected: The player closes.
        """
        self.step_capture.mark(1, "Open the first event")
        self._open_feed_or_skip()
        self.lpr.open_first_event()

        self.step_capture.mark(2, "Enter fullscreen")
        self.page.locator("img[alt='full screen']").first.click()
        self.page.wait_for_function(
            "() => document.fullscreenElement != null", timeout=10000
        )
        assert self.page.evaluate("() => document.fullscreenElement != null") is True, (
            "the player did not take the screen")

        self.step_capture.mark(3, "Exit fullscreen")
        # Escape does not release programmatic fullscreen headless;
        # exitFullscreen is the dependable path. Guarded: the call
        # rejects when fullscreen already dropped on its own
        self.page.evaluate(
            "document.fullscreenElement ? document.exitFullscreen() : null"
        )
        self.page.wait_for_function(
            "() => document.fullscreenElement == null", timeout=10000
        )

        self.step_capture.mark(4, "Close the player")
        self.lpr.close_event_player()
