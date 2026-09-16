"""Event search, filtering, and pin tests.

Covers the Events page search flow: site selection, camera selection,
duration filtering, searching, validating results, and pinning events.
"""
import re
import time

import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.pages.events_page import EventsPage

# One search job per account and no cancel (register row 78): every
# searching module shares this xdist group so --dist loadgroup runs them
# on one worker, and tests/shared/helpers/search_gap.py spaces the searches.
pytestmark = pytest.mark.xdist_group("account_search")

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
        """Verify clicking Events nav link loads the events page.

        Steps:
        1. Click the Events link in the sidebar navigation.
           Expected: The address ends in /events and the event feed container renders.
        2. Read the filter selects.
           Expected: They read All Rules, Select Site and Last 1 Hour, the duration disabled until a site is chosen.
        """
        self.events.navigate()
        self.step_capture.mark(1, "Click the Events link in the sidebar navigation")
        expect(self.page).to_have_url(re.compile(r"/events/?$"))
        expect(self.events.events_container).to_be_visible(timeout=60000)
        self.step_capture.mark(2, "Read the filter selects")
        assert self.events.selector_texts() == ["All Rules", "Select Site", "Last 1 Hour"], (
            f"the Events selects read {self.events.selector_texts()}")
        expect(self.page.locator(".MuiSelect-select").nth(2)).to_have_attribute("aria-disabled", "true")

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_select_site(self):
        """Verify site dropdown opens and a site can be selected.

        Steps:
        1. Navigate to Events page and wait for load.
           Expected: Events page loads and the loader disappears.
        2. Open the site dropdown and select the test site.
           Expected: The site select reads the site's name.
        3. Read the duration select.
           Expected: It is enabled now that a site is chosen.
        """
        self.events.navigate()
        self.events.wait_for_page_load()
        self.step_capture.mark(1, "Navigate to Events page and wait for load")
        self.events.select_site(SITE_NAME)
        self.step_capture.mark(2, "Open the site dropdown and select the test site")
        expect(self.page.locator(".MuiSelect-select").nth(1)).to_have_text(SITE_NAME, timeout=5000)
        self.step_capture.mark(3, "Read the duration select")
        expect(self.page.locator(".MuiSelect-select").nth(2)).not_to_have_attribute("aria-disabled", "true")

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_select_camera(self):
        """Verify camera dropdown opens and lists the site's cameras.

        The camera dropdown uses a #simple-menu MUI Popover with a
        tree: Site > All Cameras > individual camera containers.
        Each container shows a thumbnail, camera name, and status icon.

        KNOWN LIMITATION: The MUI Checkbox inside each camera container
        has zero-dimension elements (no bounding box) and cannot be
        toggled via Playwright. Search uses 'all cameras' by default.

        Steps:
        1. Navigate to Events and select the test site.
           Expected: Events page loads with the site applied.
        2. Open the Locations & Cameras dropdown and expand the site, then All Cameras.
           Expected: The site node declares its camera count and exactly that many camera entries are listed.
        3. Dismiss the camera menu.
           Expected: The popover closes and the search button is visible again.
        """
        self.events.navigate()
        self.events.wait_for_page_load()
        self.events.select_site(SITE_NAME)
        declared, listed = self.events.camera_menu_counts(SITE_NAME)
        assert declared > 0, f"the site node declares {declared} cameras"
        assert listed == declared, f"the menu lists {listed} cameras, the site node declares {declared}"
        # After dismissing menu, search button should be visible
        expect(self.events.search_button).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_select_duration(self):
        """Verify duration filter can be changed from default.

        Duration dropdown is disabled until a site is selected.

        Steps:
        1. Navigate to Events and select the test site.
           Expected: Duration dropdown becomes enabled after site selection.
        2. Open the duration dropdown and select Last 7 Days.
           Expected: The duration select reads Last 7 Days instead of Last 1 Hour.
        """
        self.events.navigate()
        self.events.wait_for_page_load()
        # Site must be selected first (duration is disabled without it)
        self.events.select_site(SITE_NAME)
        expect(self.page.locator(".MuiSelect-select").nth(2)).to_have_text("Last 1 Hour")
        self.events.select_duration("Last 7")
        expect(self.page.locator(".MuiSelect-select").nth(2)).to_have_text("Last 7 Days", timeout=5000)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_select_rule(self):
        """Verify rule type filter opens and a rule can be selected.

        The 'All Rules' dropdown is an optional filter -- not required
        for search, but allows narrowing results by rule type.

        Steps:
        1. Navigate to Events and open the rule type dropdown.
           Expected: The rule type option list opens.
        2. Select Intrusion Detection.
           Expected: The list closes and the selection applies.
        3. Verify the rule combobox shows the selected rule.
           Expected: The combobox text contains Intrusion Detection.
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

        Steps:
        1. Navigate to Events, select the test site and Last 7 Days.
           Expected: Filters are applied and search is available.
        2. Click the search button and wait for results.
           Expected: The loader runs and event thumbnails appear.
        3. Verify at least one event result is returned.
           Expected: The result grid shows one or more event thumbnails.
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
        """Verify event thumbnails have real images, not placeholders.

        Steps:
        1. Run an events search for the test site over Last 7 Days.
           Expected: Event thumbnails appear in the result grid.
        2. Inspect the first thumbnails' image sources.
           Expected: Every one of the first five is a blob or data image, none the No Image Available placeholder.
        """
        self.events.navigate()
        self.events.wait_for_page_load()
        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)
        results = self.events.event_results
        sources = [results.nth(i).get_attribute("src") or "" for i in range(min(results.count(), 5))]
        assert sources, "the search returned no event thumbnails"
        placeholders = [s for s in sources if "No_Image_Available" in s or not s]
        assert not placeholders, f"placeholder thumbnails among the first results: {placeholders}"
        real = [s for s in sources if s.startswith(("blob:", "data:image"))]
        assert real == sources, f"thumbnails that are neither blob nor data images: {[s[:40] for s in sources if s not in real]}"

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_pin_event(self):
        """Verify pinning an event updates the pinned clips counter.

        Steps:
        1. Run an events search for the test site over Last 7 Days.
           Expected: Event thumbnails appear in the result grid.
        2. Hover the first event card and click its pin icon.
           Expected: The pin icon appears on hover and accepts the click.
        3. Verify the pinned clips counter.
           Expected: The counter shows 1 pinned clip.
        """
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
        """Verify 'Review Pinned Clips' button appears after pinning.

        Steps:
        1. Run an events search for the test site over Last 7 Days.
           Expected: Event thumbnails appear in the result grid.
        2. Pin the first event.
           Expected: The pinned clips counter updates.
        3. Verify the Review Pinned Clips button.
           Expected: One enabled button reading Review Pinned Clips is shown once a clip is pinned.
        """
        self.events.navigate()
        self.events.wait_for_page_load()
        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)
        self.events.pin_event(0)
        expect(self.events.review_pinned_button).to_have_count(1, timeout=10000)
        expect(self.events.review_pinned_button).to_contain_text("Review Pinned Clips")
        expect(self.events.review_pinned_button).to_be_enabled()

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

        Steps:
        1. Run an unfiltered events search and capture the API responses.
           Expected: The response stream reveals a channel that has events.
        2. Reload Events, reapply the site and duration filters.
           Expected: A fresh search view is ready so the next search dispatches.
        3. Search again with the request intercepted to that single channel.
           Expected: The search request carries only the discovered channel.
        4. Verify the API result stream for the filtered search.
           Expected: Events are returned and every event belongs to the requested channel.
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

