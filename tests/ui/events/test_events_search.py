"""Event search, filtering, and pin tests.

Covers the Events page search flow: site selection, camera selection,
duration filtering, searching, validating results, and pinning events.
"""
import time

import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.pages.events_page import EventsPage

# Site name used across event tests (same as Views tests). The shared
# tenant renames sites, so the name lives in config, never in the test.
SITE_NAME = config.get("test_site_name")


class TestEventsSearch:
    """Tests for Events page search and pin functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.events = EventsPage(self.page)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_navigate_to_events(self):
        """Verify clicking Events nav link loads the events page."""
        self.events.navigate()
        self.step_capture.mark(1, "Click the Events link in the sidebar navigation")
        expect(self.events.events_container).to_be_visible(timeout=60000)
        self.step_capture.mark(2, "Verify events container is visible")

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_select_site(self):
        """Verify site dropdown opens and a site can be selected."""
        self.events.navigate()
        self.events.wait_for_page_load()
        self.step_capture.mark(1, "Navigate to Events page and wait for load")

        self.events.select_site(SITE_NAME)
        self.step_capture.mark(2, "Open the site dropdown and select the test site")

        # After selecting, the dropdown should close and site name visible
        site_label = self.page.get_by_text(SITE_NAME, exact=False).first
        expect(site_label).to_be_visible(timeout=5000)
        self.step_capture.mark(3, "Verify the selected site name is visible on the page")

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_select_camera(self):
        """Verify camera dropdown opens and lists cameras.

        The camera dropdown uses a #simple-menu MUI Popover with a
        tree: Site > All Cameras > individual camera containers.
        Each container shows a thumbnail, camera name, and status icon.

        KNOWN LIMITATION: The MUI Checkbox inside each camera container
        has zero-dimension elements (no bounding box) and cannot be
        toggled via Playwright. Search uses 'all cameras' by default.
        """
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_site(SITE_NAME)
        self.events.select_first_available_camera(SITE_NAME)

        # After dismissing menu, search button should be visible
        expect(self.events.search_button).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_select_duration(self):
        """Verify duration filter can be changed from default.

        Duration dropdown is disabled until a site is selected.
        """
        self.events.navigate()
        self.events.wait_for_page_load()

        # Site must be selected first (duration is disabled without it)
        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")

        # The selected duration text should be visible
        duration_label = self.page.get_by_text("Last 7", exact=False).first
        expect(duration_label).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_select_rule(self):
        """Verify rule type filter opens and a rule can be selected.

        The 'All Rules' dropdown is an optional filter -- not required
        for search, but allows narrowing results by rule type.
        """
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_rule("Intrusion Detection")

        # After selecting, the combobox text should change from "All Rules"
        combo_text = self.page.locator('[role="combobox"]').first.inner_text()
        assert "Intrusion Detection" in combo_text, (
            f"Expected 'Intrusion Detection' in combobox, got '{combo_text}'"
        )

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_search_events(self):
        """Verify search returns event results after selecting filters.

        Uses default 'all cameras' (no specific camera selection) to
        ensure results are returned regardless of per-camera event data.
        """
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        count = self.events.get_event_count()
        assert count > 0, "Expected at least one event result after search"

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_event_snapshots_valid(self):
        """Verify event thumbnails have real images, not placeholders."""
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        assert self.events.has_valid_snapshots(), (
            "First event thumbnail should be a real image, "
            "not 'No_Image_Available' placeholder"
        )

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_pin_event(self):
        """Verify pinning an event updates the pinned clips counter."""
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        self.events.pin_event(0)

        pinned_text = self.events.get_pinned_count_text()
        assert "1" in pinned_text, (
            f"Expected pinned count to contain '1', got '{pinned_text}'"
        )

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_review_pinned_clips_button(self):
        """Verify 'Review Pinned Clips' button appears after pinning."""
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        self.events.pin_event(0)

        expect(self.events.review_pinned_button).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_search_with_specific_camera(self):
        """Verify search filters results by a single camera channel.

        Uses route interception to modify the API channelList from all
        cameras to one channel. This bypasses the MUI checkbox
        zero-dimension limitation while verifying per-camera search
        works at the API level.

        The channel is discovered from the unfiltered search response
        instead of hardcoded: the shared tenant renames sites and
        re-numbers channels, so a fixed channel is a delayed failure.
        """
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")

        # Unfiltered search first; capture its API responses to learn
        # which channel actually has events on this tenant.
        seen_events = []

        def capture_events(response):
            if "site/search/event" not in response.url:
                return
            try:
                for block in response.json().get("result", []):
                    seen_events.extend(block.get("eventList", []))
            # listener sees every search response; a non-json or
            # off-shape body is skipped and the channel check below
            # decides
            except (ValueError, KeyError, TypeError, AttributeError):
                pass

        self.page.on("response", capture_events)
        try:
            self.events.search_events(timeout=60000)
        finally:
            self.page.remove_listener("response", capture_events)

        channel = None
        channel_key = None
        for event in seen_events:
            if not isinstance(event, dict):
                continue
            for key in ("channelId", "channel", "channelNo", "channel_id"):
                if event.get(key) is not None:
                    channel = int(event[key])
                    channel_key = key
                    break
            if channel is not None:
                break
        if channel is None:
            pytest.skip(
                "Search responses carry no recognizable channel field; "
                "cannot derive a channel with events"
            )

        # Reload the Events page so the filtered search runs as the
        # first search of a fresh view: a second click on the results
        # view does not dispatch a new search POST.
        self.page.reload()
        self.events.wait_for_page_load()
        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")

        # Filtered search for the discovered channel. The oracle is the
        # API result stream: the client stops polling once it has its
        # batches, so a 100-percent completion response is not
        # guaranteed and the captured events themselves are the proof.
        totals = []
        filtered_events = []

        def capture_filtered(response):
            if "site/search/event" not in response.url:
                return
            try:
                for block in response.json().get("result", []):
                    totals.append(block.get("totalEvent", 0))
                    filtered_events.extend(block.get("eventList", []))
            # listener sees every search response; a non-json or
            # off-shape body is skipped and the asserts below own the
            # oracle
            except (ValueError, KeyError, TypeError, AttributeError):
                pass

        self.page.on("response", capture_filtered)
        try:
            self.events.search_events_for_channels([channel], timeout=60000)
            # The search job is async: hold the listener open until an
            # event batch or a positive total arrives
            deadline = time.monotonic() + 30
            while (time.monotonic() < deadline
                   and not filtered_events
                   and not any(t > 0 for t in totals)):
                self.page.wait_for_timeout(500)  # poll for job results
        finally:
            self.page.remove_listener("response", capture_filtered)

        assert filtered_events or any(t > 0 for t in totals), (
            f"Channel {channel} produced events in the unfiltered search "
            f"but the filtered search returned none (totals: {totals})"
        )

        # The filter itself is the point: every returned event must
        # belong to the requested channel
        mismatched = {
            ev.get(channel_key) for ev in filtered_events
            if isinstance(ev, dict)
            and ev.get(channel_key) not in (None, channel)
        }
        assert not mismatched, (
            f"Filtered search for channel {channel} returned events "
            f"from other channels: {sorted(mismatched)}"
        )

