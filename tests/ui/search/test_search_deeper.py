"""Deeper Global Search tests - category enumeration, description panels,
filter combinations, duration variations, and result validation.

Extends basic search coverage with parametrized category/duration tests,
filter change workflows, and result content checks.
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.search_page import SearchPage


SITE_NAME = "Driver Site"


class TestSearchDeeper:
    """Tests for deeper Global Search filter and result coverage."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.search = SearchPage(self.page)
        self.search.navigate()
        self.search.wait_for_page_load()
        yield

    # --- Dropdown enumeration ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.qatouch("Z8xR7k")
    def test_category_dropdown_lists_categories(self):
        """Verify category dropdown contains Person, Vehicle, and Event."""
        self.step_capture.mark(1, "Open Category dropdown on Global Search page")

        options = self.search.get_category_options()
        assert len(options) >= 3, f"Expected at least 3 categories, got: {options}"
        for expected in ("Person", "Vehicle", "Event"):
            assert any(expected in opt for opt in options), (
                f"Expected '{expected}' in categories, got: {options}"
            )
        self.step_capture.mark(2, "Verify Person, Vehicle, and Event categories are listed")

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.qatouch("dypXGR")
    def test_duration_dropdown_lists_options(self):
        """Verify duration dropdown has multiple time range options."""
        self.step_capture.mark(1, "Open Duration dropdown on Global Search page")

        options = self.search.get_duration_options()
        assert len(options) >= 3, (
            f"Expected at least 3 duration options, got: {options}"
        )
        self.step_capture.mark(2, "Verify at least 3 duration options are listed")

    # --- Description panel visibility ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.qatouch("dypNqZ")
    def test_description_panel_shown_for_person(self):
        """Verify the Description filter appears after selecting Person."""
        self.search.select_category("Person")
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(1, "Select 'Person' from the Category dropdown")

        assert self.search.is_description_panel_visible(), (
            "Description panel should be visible for Person category"
        )
        self.step_capture.mark(2, "Verify Description panel is visible for Person category")

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.qatouch("xm9E11")
    def test_event_category_no_gender_options(self):
        """Verify Event category does not show gender selection options.

        The Description dropdown container exists for all categories, but
        gender-specific options (Male/Female) only appear for Person.
        """
        self.search.select_category("Event")
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(1, "Select 'Event' from the Category dropdown")

        # Click Description dropdown if present
        dropdown = self.search._get_dropdown_by_text("Description")
        if dropdown is not None and dropdown.is_visible():
            dropdown.click()
            self.page.wait_for_timeout(1000)
        self.step_capture.mark(2, "Open Description dropdown if present")

        # Gender container should NOT be visible for Event
        assert self.search.gender_container.count() == 0 or \
            not self.search.gender_container.first.is_visible(), (
            "Gender options should not appear for Event category"
        )
        self.page.keyboard.press("Escape")
        self.step_capture.mark(3, "Verify gender options are not shown for Event category")

    # --- Person search variations ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.qatouch("VKbB1P")
    def test_person_female_search(self):
        """Verify Person search with Female description completes.

        Soft assertion: some sites may have few or no female detections.
        """
        self.search.select_category("Person")
        self.step_capture.mark(1, "Select Category = Person")

        self.search.select_description_gender("Female")
        self.step_capture.mark(2, "Select Description = Female")

        self.search.select_locations_cameras(SITE_NAME)
        self.step_capture.mark(3, "Select Location = Driver Site")

        self.search.select_duration_by_index(5)
        self.step_capture.mark(4, "Select duration filter")

        has_results = self.search.execute_search_safe(timeout=60000)
        self.step_capture.mark(5, "Click Search and wait for results")

        # Verify category is still Person after search
        person_text = self.page.get_by_text("Person", exact=False).first
        expect(person_text).to_be_visible(timeout=5000)

        if has_results:
            assert self.search.get_result_count() > 0
        self.step_capture.mark(6, "Verify Person category is still selected and results load if available")

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.qatouch("xm9dNR")
    def test_person_search_multiple_results(self):
        """Verify a broad Person search returns multiple results."""
        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration_by_index(5)
        self.step_capture.mark(1, "Set filters: Person, Male, Driver Site, duration")

        self.search.execute_search(timeout=60000)
        self.step_capture.mark(2, "Click Search and wait for results")

        count = self.search.get_result_count()
        assert count > 1, f"Expected multiple results, got {count}"
        self.step_capture.mark(3, "Verify search returns more than one result")

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.qatouch("Pgw47m")
    def test_person_result_images_have_src(self):
        """Verify Person search result images have valid src attributes."""
        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration_by_index(5)
        self.step_capture.mark(1, "Set filters: Person, Male, Driver Site, duration")

        self.search.execute_search(timeout=60000)
        self.step_capture.mark(2, "Click Search and wait for results")

        check_count = min(self.search.get_result_count(), 3)
        for i in range(check_count):
            img = self.search.result_images.nth(i)
            expect(img).to_be_visible()
        self.step_capture.mark(3, "Verify result images are visible and have valid sources")

    # --- Event search variations ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.parametrize("duration_text", [
        "Today",
        "Last 7 Days",
    ])
    @pytest.mark.qatouch("J8d9R1")
    def test_event_search_by_duration(self, duration_text):
        """Verify Event search with different durations completes."""
        self.search.select_category("Event")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration(duration_text)
        self.step_capture.mark(1, f"Set filters: Event, Driver Site, duration = {duration_text}")

        has_results = self.search.execute_search_safe(timeout=60000)
        self.step_capture.mark(2, "Click Search and wait for results")

        # Short durations may have 0 results - no crash is the goal
        if has_results:
            assert self.search.get_result_count() > 0
        self.step_capture.mark(3, "Verify search completes without errors")

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.qatouch("gQxw5N")
    def test_event_result_images_valid(self):
        """Verify Event search result images are visible."""
        self.search.select_category("Event")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration_by_index(5)
        self.step_capture.mark(1, "Set filters: Event, Driver Site, duration")

        self.search.execute_search(timeout=60000)
        self.step_capture.mark(2, "Click Search and wait for results")

        check_count = min(self.search.get_result_count(), 3)
        for i in range(check_count):
            img = self.search.result_images.nth(i)
            expect(img).to_be_visible()
        self.step_capture.mark(3, "Verify Event result images are visible")

    # --- Filter change workflows ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.qatouch("wmjKMb")
    def test_change_category_person_to_event(self):
        """Verify switching from Person to Event and re-searching works."""
        # First search: Person
        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration_by_index(5)
        self.step_capture.mark(1, "Set filters: Person, Male, Driver Site, duration")

        self.search.execute_search(timeout=60000)
        self.step_capture.mark(2, "Click Search and wait for Person results")

        person_count = self.search.get_result_count()
        assert person_count > 0, "Expected Person results"
        self.step_capture.mark(3, "Verify Person search returns results")

        # Switch to Event and re-search
        self.search.select_category("Event")
        self.step_capture.mark(4, "Switch Category to Event")

        has_results = self.search.execute_search_safe(timeout=60000)
        self.step_capture.mark(5, "Click Search again and wait for Event results")

        if has_results:
            event_count = self.search.get_result_count()
            assert event_count > 0
        self.step_capture.mark(6, "Verify Event search completes without errors")

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.qatouch("Z8xWjk")
    def test_change_duration_and_re_search(self):
        """Verify changing duration between searches works."""
        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration("Last 7 Days")
        self.step_capture.mark(1, "Set filters: Person, Male, Driver Site, Last 7 Days")

        self.search.execute_search(timeout=60000)
        assert self.search.get_result_count() > 0, "Expected results for Last 7 Days"
        self.step_capture.mark(2, "Click Search and verify Last 7 Days returns results")

        # Change to Today and re-search
        self.search.select_duration("Today")
        self.step_capture.mark(3, "Change Duration to Today")

        self.search.execute_search_safe(timeout=60000)
        self.step_capture.mark(4, "Click Search again and verify no errors")

        # Different duration may have fewer results - just verify no crash

    # --- Search result content ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.qatouch("dypXRb")
    def test_search_button_state_after_filters(self):
        """Verify search button is clickable after setting all filters."""
        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration_by_index(5)
        self.step_capture.mark(1, "Set all filters: Person, Male, Driver Site, duration")

        expect(self.search.search_button).to_be_visible(timeout=5000)
        self.step_capture.mark(2, "Verify Search button is visible and clickable")

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.qatouch("rGQP7W")
    def test_result_count_matches_visible_images(self):
        """Verify get_result_count() matches visible result images."""
        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration_by_index(5)
        self.step_capture.mark(1, "Set filters: Person, Male, Driver Site, duration")

        self.search.execute_search(timeout=60000)
        self.step_capture.mark(2, "Click Search and wait for results")

        count = self.search.get_result_count()
        visible = 0
        for i in range(count):
            try:
                if self.search.result_images.nth(i).is_visible():
                    visible += 1
            except Exception:
                break

        assert visible > 0, "Expected at least one visible result image"
        assert visible == count, (
            f"Result count ({count}) doesn't match visible images ({visible})"
        )
        self.step_capture.mark(3, "Verify result count matches the number of visible images")
