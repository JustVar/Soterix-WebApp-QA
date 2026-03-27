"""Event video playback and export tests.

Covers event playback (inline player), player controls,
closing the player, and exporting events.
The modernized Events page plays videos inline (no separate player page).
"""
import datetime
import pytest
from playwright.sync_api import expect
from tests.shared.pages.events_page import EventsPage


# Site name used across event tests
SITE_NAME = "Driver Site"


class TestEventsPlayback:
    """Tests for event video playback and export."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        """Navigate to Events, search, and pin an event.

        This setup prepares the page with search results and a pinned event.
        Individual tests handle playing the event as needed.
        """
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.events = EventsPage(self.page)

        # Navigate and search (default = all cameras)
        self.events.navigate()
        self.events.wait_for_page_load()
        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        # Pin the first event
        self.events.pin_event(0)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_playback
    @pytest.mark.qatouch("8V1v5k")
    def test_play_event_inline(self):
        """Verify clicking Play Video loads the inline event player."""
        self.events.play_event(0, timeout=60000)
        self.step_capture.mark(1, "Play the first event inline")

        # Player controls should be visible (play/pause button)
        expect(self.events.player_play_pause).to_be_visible(timeout=15000)
        self.step_capture.mark(2, "Verify play/pause button is visible in the inline player")

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_playback
    @pytest.mark.qatouch("eJqmLp")
    def test_player_controls_visible(self):
        """Verify all player controls are visible after playing an event."""
        self.events.play_event(0, timeout=60000)
        self.step_capture.mark(1, "Play the first event inline")

        expect(self.events.player_play_pause).to_be_visible(timeout=15000)
        self.step_capture.mark(2, "Verify play/pause button is visible")

        expect(self.events.player_backward).to_be_visible(timeout=5000)
        expect(self.events.player_forward).to_be_visible(timeout=5000)
        self.step_capture.mark(3, "Verify backward and forward controls are visible")

        expect(self.events.player_volume).to_be_visible(timeout=5000)
        self.step_capture.mark(4, "Verify volume control is visible")

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_playback
    @pytest.mark.qatouch("PgwlNd")
    def test_event_action_toolbar(self):
        """Verify event action toolbar buttons are visible after playing."""
        self.events.play_event(0, timeout=60000)
        self.step_capture.mark(1, "Play the first event inline")

        expect(self.events.share_button).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify Share button is visible in the action toolbar")

        expect(self.events.export_button).to_be_visible(timeout=5000)
        self.step_capture.mark(3, "Verify Export button is visible in the action toolbar")

        expect(self.events.lightbox_button).to_be_visible(timeout=5000)
        self.step_capture.mark(4, "Verify Lightbox button is visible in the action toolbar")

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_playback
    @pytest.mark.qatouch("LD3m4v")
    def test_close_event_player(self):
        """Verify closing the player returns to event search results."""
        self.events.play_event(0, timeout=60000)
        expect(self.events.player_play_pause).to_be_visible(timeout=15000)
        self.step_capture.mark(1, "Play the first event and verify player loads")

        self.events.close_player()
        self.step_capture.mark(2, "Close the event player")

        # After closing, search results should still be visible
        count = self.events.get_event_count()
        assert count > 0, "Event results should still be visible after closing player"
        self.step_capture.mark(3, "Verify event search results are still visible after closing player")

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_playback
    @pytest.mark.slow
    @pytest.mark.qatouch("B86Epy")
    def test_export_event(self):
        """Verify export dialog flow completes (progress bar appears and finishes)."""
        self.events.play_event(0, timeout=60000)
        expect(self.events.export_button).to_be_visible(timeout=10000)
        self.step_capture.mark(1, "Play the first event and verify Export button is visible")

        filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        returned_name = self.events.export_event(filename=filename)
        self.step_capture.mark(2, "Enter export filename and complete the export dialog")

        assert returned_name == filename, (
            f"Expected export filename '{filename}', got '{returned_name}'"
        )
        self.step_capture.mark(3, "Verify the returned export filename matches the entered name")
