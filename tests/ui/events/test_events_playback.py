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



class TestEventsPlayback:
    """Tests for event video playback and export."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        """Navigate to Events, search, and pin an event.

        This setup prepares the page with search results and a pinned event.
        Individual tests handle playing the event as needed.
        """
        self.page = authenticated_page
        self.events = EventsPage(self.page)

        # Navigate and search (default = all cameras)
        self.events.navigate()
        self.events.wait_for_page_load()
        self.events.select_site(None)
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        # Pin the first event
        self.events.pin_event(0)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_playback
    def test_play_event_inline(self):
        """Verify clicking Play Video loads the inline event player."""
        self.events.play_event(0, timeout=60000)
        # one pause control marks the inline player playing
        expect(self.events.player_play_pause).to_have_count(1, timeout=15000)
        expect(self.events.player_play_pause).to_be_visible()

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_playback
    def test_player_controls_visible(self):
        """Verify all player controls are visible after playing an event."""
        self.events.play_event(0, timeout=60000)

        # Four independent checks on one screen: soft, so a missing
        # control reports with the others instead of hiding them
        expect.soft(self.events.player_play_pause).to_have_count(1, timeout=15000)
        expect.soft(self.events.player_backward).to_be_visible(timeout=5000)
        expect.soft(self.events.player_forward).to_have_count(1, timeout=5000)
        expect.soft(self.events.player_volume).to_have_count(1, timeout=5000)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_playback
    def test_event_action_toolbar(self):
        """Verify event action toolbar buttons are visible after playing."""
        self.events.play_event(0, timeout=60000)

        # Three independent checks on one screen: soft, so a missing
        # button reports with the others instead of hiding them
        expect.soft(self.events.share_button).to_have_count(1, timeout=10000)
        expect.soft(self.events.export_button).to_have_count(1, timeout=5000)
        expect.soft(self.events.lightbox_button).to_have_count(1, timeout=5000)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_playback
    def test_close_event_player(self):
        """Verify closing the player returns to event search results."""
        self.events.play_event(0, timeout=60000)
        expect(self.events.player_play_pause).to_be_visible(timeout=15000)

        self.events.close_player()

        # After closing, search results should still be visible
        count = self.events.get_event_count()
        assert count > 0, "Event results should still be visible after closing player"

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_playback
    @pytest.mark.slow
    def test_export_event(self):
        """Verify export dialog flow completes (progress bar appears and finishes)."""
        self.events.play_event(0, timeout=60000)
        expect(self.events.export_button).to_be_visible(timeout=10000)

        filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        returned_name = self.events.export_event(filename=filename)

        assert returned_name == filename, (
            f"Expected export filename '{filename}', got '{returned_name}'"
        )
