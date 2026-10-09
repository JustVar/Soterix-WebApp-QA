"""Events deeper filter tests - rule types, durations, combinations, pin lifecycle.

Extends the basic Events search coverage with parametrized filter variations,
filter combination workflows, and pin/unpin event lifecycle.
"""
import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.helpers.shown_name import shown_as
from tests.shared.pages.events_page import EventsPage

# The app runs one search job per account and offers no cancel: every
# searching module shares this xdist group so --dist loadgroup runs them
# on one worker, and tests/shared/helpers/search_gap.py spaces the searches.
pytestmark = pytest.mark.xdist_group("account_search")

SITE_NAME = config.get("test_site_name")





class TestEventsFilters:
    """Tests for Events page filter variations and combinations."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.events = EventsPage(self.page)
        self.page.reload()
        self.events.navigate()
        self.events.wait_for_page_load()
        return

    # --- Site dropdown ---

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_filters
    @pytest.mark.smoke
    def test_site_dropdown_lists_available_sites(self):
        """Verify site dropdown shows at least one selectable site."""
        sites = self.events.get_site_options()
        assert len(sites) > 0, "Expected at least one site in the dropdown"
        # the list is the account's sites: the configured test site is one of them, and no site shows 2 times
        site_name = config.get("test_site_name")
        assert site_name in sites, f"the site dropdown lists {sites}, and the test site {site_name!r} is not one of them"
        assert len(sites) == len(set(sites)), f"the site dropdown lists a site 2 times: {sites}"

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_filters
    def test_site_selection_shows_site_name(self):
        """Verify selecting a site enables rules dropdown (site selection confirmed).

        Steps:
        1. Open Events and open the site dropdown.
           Expected: At least one site is listed.
        2. Select a site.
           Expected: The rule dropdown becomes available and lists rules.
        """
        # Get initial sites to verify we can select one
        initial_sites = self.events.get_site_options()
        assert len(initial_sites) > 0, "At least one site should be available"

        self.events.select_site(None)
        # the selection shows: the 'Select Site' placeholder is gone, and the page reads the
        # name of the site that was picked (the app can cut a long name and add an ellipsis)
        expect(self.events.site_dropdown).to_have_count(0, timeout=10000)
        expect(self.page.get_by_text(shown_as(config.get("test_site_name"))).first).to_be_visible()

        # After site selection, rules dropdown should be enabled with options
        rules = self.events.get_rule_options()
        assert len(rules) > 0, f"Rules should be available after site selection. Sites found: {initial_sites}, Rules: {rules}"

    # --- Rule types ---

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_filters
    def test_rule_dropdown_lists_available_rules(self):
        """Verify rule dropdown shows multiple rule type options.

        Rules may only populate after a site is selected.
        """
        self.events.select_site(None)

        rules = self.events.get_rule_options()
        assert len(rules) >= 2, f"Expected multiple rule types, got: {rules}"

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_filters
    def test_search_intrusion_detection(self):
        """Verify searching with Intrusion Detection rule returns results."""
        self.events.select_site(None)
        self.events.select_rule("Intrusion Detection")
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        count = self.events.get_event_count()
        assert count > 0, "Expected results for Intrusion Detection + Last 7 Days"

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_filters
    def test_search_with_different_rule(self):
        """Verify searching with a non-default rule type completes.

        Discovers available rules dynamically and tests one that isn't
        Intrusion Detection. Soft assertion since some rules may have
        no events in the time range.
        """
        self.events.select_site(None)

        rules = self.events.get_rule_options()
        # "All Rules" is always offered, so seeing it proves the dropdown
        # loaded; without that proof an empty read and a broken dropdown
        # skipped alike.
        assert "All Rules" in rules, (
            f"The Events rule dropdown did not load: it offers {rules}, "
            f"which does not include the standing 'All Rules' entry"
        )
        other_rules = [r for r in rules
                       if r not in ("All Rules", "Intrusion Detection")]
        if not other_rules:
            pytest.skip(
                f"The Events rule dropdown offers only {rules}: this tenant "
                f"has no other rule type to filter by"
            )

        self.events.select_rule(other_rules[0])
        self.events.select_duration("Last 7")

        has_results = self.events.search_events_safe(timeout=60000)

        # Verify rule is shown in filter bar
        combo_text = self.page.locator('[role="combobox"]').first.inner_text()
        assert other_rules[0] in combo_text, \
            f"Expected '{other_rules[0]}' in combobox, got '{combo_text}'"

    # --- Duration options ---

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_filters
    @pytest.mark.parametrize("duration_text,label_check", [
        ("Last 1", "Last 1"),
        ("Last 3", "Last 3"),
        ("Last 7", "Last 7"),
    ])
    def test_search_by_duration(self, duration_text, label_check):
        """Verify searching with different duration options works."""
        self.events.select_site(None)
        self.events.select_duration(duration_text)

        # Verify duration label is visible
        duration_label = self.page.get_by_text(label_check, exact=False).first
        expect(duration_label).to_be_visible(timeout=5000)

        has_results = self.events.search_events_safe(timeout=60000)

        # Short durations may have 0 results - that's OK, no crash is the goal
        if has_results:
            assert self.events.get_event_count() > 0

    # --- Filter combinations ---

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_filters
    def test_rule_and_duration_combined(self):
        """Verify combining a specific rule and duration filters together."""
        self.events.select_site(None)
        self.events.select_rule("Intrusion Detection")
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        count = self.events.get_event_count()
        assert count > 0, "Expected results for Intrusion Detection + Last 7 Days"

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_filters
    def test_change_duration_and_re_search(self):
        """Verify changing duration between searches works."""
        self.events.select_site(None)
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)
        assert self.events.get_event_count() > 0, "Expected results for Last 7"

        # Change to Last 3 and re-search
        self.events.select_duration("Last 3")
        self.events.search_events_safe(timeout=60000)

        # Different duration may have fewer results - just verify no crash

    # --- Pin lifecycle ---

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_filters
    def test_pin_multiple_events(self):
        """Verify pinning multiple events increments the counter."""
        self.events.select_site(None)
        self.events.select_rule("Intrusion Detection")
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        count = self.events.get_event_count()
        if count < 2:
            pytest.skip(
                f"The Intrusion Detection search over the last 7 days "
                f"returned {count} event(s); pinning two needs two"
            )

        self.events.pin_event(0)
        pinned_text = self.events.get_pinned_count_text()
        assert "1" in pinned_text, f"Expected 1 pin, got '{pinned_text}'"

        self.events.pin_event(1)
        pinned_text = self.events.get_pinned_count_text()
        assert "2" in pinned_text, f"Expected 2 pins, got '{pinned_text}'"

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_filters
    def test_unpin_event_via_second_pin(self):
        """Pinning three events shows a pinned count of three.

        Steps:
        1. On Events, pick the site, the Intrusion Detection rule and Last 7 days, and search.
           Expected: The results list at least three events. With fewer the test skips naming the count.
        2. Pin the first, second and third event.
           Expected: The pinned counter reads 3.
        """
        self.events.select_site(None)
        self.events.select_rule("Intrusion Detection")
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        count = self.events.get_event_count()
        if count < 3:
            pytest.skip(
                f"The Intrusion Detection search over the last 7 days "
                f"returned {count} event(s); the pin counter needs three"
            )

        self.events.pin_event(0)
        self.events.pin_event(1)
        self.events.pin_event(2)

        pinned_text = self.events.get_pinned_count_text()
        assert "3" in pinned_text, f"Expected 3 pins, got '{pinned_text}'"

    # --- Event result content ---

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_filters
    def test_event_results_have_thumbnails(self):
        """Verify event results display thumbnail images."""
        self.events.select_site(None)
        self.events.select_rule("Intrusion Detection")
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        # Check first few events have visible thumbnail images
        count = min(self.events.get_event_count(), 3)
        for i in range(count):
            img = self.events.event_results.nth(i)
            expect(img).to_be_visible()
            src = img.get_attribute("src") or ""
            scheme = src.split(":", 1)[0]
            assert scheme in ("blob", "data", "http", "https"), (
                f"Event {i} thumbnail's source is {src[:40]!r}, not an image")
            assert img.evaluate("e => e.naturalWidth") > 0, f"Event {i} thumbnail never decoded"
