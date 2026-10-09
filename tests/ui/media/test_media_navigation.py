"""Media page navigation and browsing tests.

Covers navigation, date filter, view switching, and tab navigation.
Every check reads a value the page shows: the URL, the date filter's
text, the selected tab's paint, the item layout, the names a search
returns (all measured on the app).

Migrated from Selenium:
- test_navigate_to_media_page (line 5827)
- test_media_select_filter (line 5841)
- test_media_switch_to_grid_view (line 5871)
- test_media_validate_my_media (line 5887)
- test_media_validate_shared_with_me (line 5904)
- test_media_all_tab (line 5923)
- test_media_clips_tab (line 5947)
- test_media_export_folder (line 6385) - Vault tab portion
- test_media_search_clip (line 6421)
"""
import re

import pytest
from playwright.sync_api import expect

from tests.shared.pages.media_page import MediaPage


class TestMediaNavigation:
    """Tests for Media page navigation and browsing."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.media = MediaPage(self.page)

    def _items_or_skip(self) -> list[str]:
        """The listed item names, or a skip that says the list is empty.

        The page is proved up first (the date filter is on screen), so an
        empty list is the tenant's state, not a broken page.
        """
        expect(self.media.date_filter).to_be_visible(timeout=10000)
        names = self.media.item_names()
        if not names:
            assert self.media.is_page_empty(timeout=5000), (
                "the Media list shows neither items nor its empty state")
            pytest.skip("the Media list is empty for the last 30 days on this tenant "
                        "(the empty state is shown), so there is no layout to measure")
        return names

    # --- Navigation ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.smoke
    def test_navigate_to_media_page(self):
        """Verify navigation to the Media page via the sidebar.

        Steps:
        1. Click Media in the left sidebar.
           Expected: The address ends in /media and the date filter reads Today, its default.
        """
        self.media.navigate()
        expect(self.page).to_have_url(re.compile(r"/media/?$"))
        expect(self.media.date_filter).to_have_text("Today", timeout=10000)

    # --- Date filter ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_select_date_filter(self):
        """Verify selecting 'Last 30 Days' from the date filter dropdown.

        Steps:
        1. Open Media and choose Last 30 Days in the date filter.
           Expected: The date filter reads Last 30 Days instead of Today.
        """
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        expect(self.media.date_filter).to_have_text("Last 30 Days", timeout=5000)

    # --- View toggle ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_switch_to_grid_view(self):
        """Verify switching from list to grid view.

        Steps:
        1. Open Media, choose Last 30 Days and click the grid view button.
           Expected: The grid button reads pressed and the items move from one column into several.
        """
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self._items_or_skip()
        before = self.media.view_columns()
        assert before == 1, f"the list view lays the items out in {before} columns, not 1"
        self.media.switch_to_grid_view()
        after = self.media.view_columns()
        assert after > 1, f"after switching to grid view the items still sit in {after} column(s)"

    # --- Tab navigation ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_all_tab(self):
        """Verify the All tab loads and shows content or empty state.

        Steps:
        1. Open Media, set the date filter to Last 30 Days and click the All tab.
           Expected: The All tab is painted as selected and the page shows items or its empty state.
        """
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("All")
        # the oracle: expect_tab_selected raises with the tab's paint when it is
        # not the selected one, and _content_or_empty_state expects the empty text
        self.media.expect_tab_selected("All")
        self._content_or_empty_state()

    @pytest.mark.ui
    @pytest.mark.media
    def test_my_media_tab(self):
        """Verify the My Media tab loads.

        Steps:
        1. Open Media, set the date filter to Last 30 Days and click the My Media tab.
           Expected: The My Media tab is painted as selected and All is not.
        """
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("My Media")
        self.media.expect_tab_selected("My Media")
        assert not self.media.tab_is_selected("All"), "All stays painted as selected beside My Media"

    @pytest.mark.ui
    @pytest.mark.media
    def test_shared_with_me_tab(self):
        """Verify the Shared with me tab loads.

        Steps:
        1. Open Media, set the date filter to Last 30 Days and click the Shared with me tab.
           Expected: The Shared with me tab is painted as selected and the page shows items or its empty state.
        """
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Shared with me")
        # the oracle: expect_tab_selected raises with the tab's paint when it is
        # not the selected one, and _content_or_empty_state expects the empty text
        self.media.expect_tab_selected("Shared with me")
        self._content_or_empty_state()

    @pytest.mark.ui
    @pytest.mark.media
    def test_clips_tab(self):
        """Verify the Clips tab loads and shows content or empty state.

        Steps:
        1. Open Media, set the date filter to Last 30 Days and click the Clips tab.
           Expected: The Clips tab is painted as selected and the page shows items or its empty state.
        """
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")
        # the oracle: expect_tab_selected raises with the tab's paint when it is
        # not the selected one, and _content_or_empty_state expects the empty text
        self.media.expect_tab_selected("Clips")
        self._content_or_empty_state()

    @pytest.mark.ui
    @pytest.mark.media
    def test_folders_tab(self):
        """Verify the Folders tab loads.

        Steps:
        1. Open Media, set the date filter to Last 30 Days and click the Folders tab.
           Expected: The Folders tab is painted as selected and the page shows items or its empty state.
        """
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Folders")
        # the oracle: expect_tab_selected raises with the tab's paint when it is
        # not the selected one, and _content_or_empty_state expects the empty text
        self.media.expect_tab_selected("Folders")
        self._content_or_empty_state()

    @pytest.mark.ui
    @pytest.mark.media
    def test_vault_tab(self):
        """Verify the Vault tab loads.

        Steps:
        1. Open Media, set the date filter to Last 30 Days and click the Vault tab.
           Expected: The Vault tab is painted as selected and the page shows items or its empty state.
        """
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")
        # the oracle: expect_tab_selected raises with the tab's paint when it is
        # not the selected one, and _content_or_empty_state expects the empty text
        self.media.expect_tab_selected("Vault")
        self._content_or_empty_state()

    # --- Search ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_search_media(self):
        """Verify searching media by title.

        Steps:
        1. Open Media, choose Last 30 Days and note the first clip's name.
           Expected: The list shows at least one item.
        2. Type that name in the search field and press Enter.
           Expected: The list shows that item and nothing that does not carry the name (the search needs three characters or more; a shorter query is ignored by the page).
        """
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        names = self._items_or_skip()
        query = names[0]
        self.media.search_media(query)
        expect(self.media.search_input).to_have_value(query)
        results = self.media.item_names()
        assert query in results, f"searching {query!r} returned {results}"
        strangers = [n for n in results if query.lower() not in n.lower()]
        assert not strangers, f"searching {query!r} also returned {strangers}"

    def _content_or_empty_state(self) -> None:
        """The tab shows items, or its empty state; nothing in between."""
        names = self.media.item_names()
        if not names:
            expect(self.media.no_results_text).to_have_text(MediaPage.EMPTY_STATE, timeout=10000)
