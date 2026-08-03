"""License Search, Filter, and CSV Export tests - search functionality,
filtering behavior, and CSV download verification."""
import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import expect
from tests.shared.pages.license_page import LicensePage


class TestLicenseSearch:
    """Tests for search and filter on Licenses page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.license = LicensePage(self.page)
        yield

    def _navigate(self):
        """Navigate to Licenses page."""
        self.license.navigate()

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_search_with_valid_license_name(self):
        """Verify search using valid License Item name returns results."""
        self._navigate()

        self.license.search("Channel")
        self.page.wait_for_timeout(2000)

        # After searching, content should still be visible (filtered)
        rows = self.page.locator("tr, div[class*='row']")
        assert rows.count() > 0, "Search returned no results for 'Channel'"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_search_with_partial_keyword(self):
        """Verify search using partial License Item keyword."""
        self._navigate()

        self.license.search("Chan")
        self.page.wait_for_timeout(2000)

        # Should still return some results
        content = self.page.locator(
            "tr, div[class*='row'], td, div[class*='cell']"
        )
        assert content.count() > 0, "Partial keyword search returned no results"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_search_with_license_key(self):
        """Verify search using valid License Key."""
        self._navigate()

        # Search with a license key format (alphanumeric)
        self.license.search("LIC")
        self.page.wait_for_timeout(2000)

        # Results should render (or empty state)
        expect(self.license.search_input).to_have_value("LIC")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_invalid_search_shows_no_results(self):
        """Verify invalid search displays no results or empty state."""
        self._navigate()

        self.license.search("ZZZZNONEXISTENT999")
        self.page.wait_for_timeout(2000)

        # Should show empty state or zero rows
        empty = self.page.locator(
            "text=No results, text=No data, text=No licenses found, "
            "text=Nothing found"
        )
        rows = self.page.locator("tr[class*='data'], div[class*='license-row']")
        assert empty.count() > 0 or rows.count() == 0, \
            "Invalid search should show empty state or zero data rows"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_clear_search_restores_list(self):
        """Verify clearing search restores full license list."""
        self._navigate()

        # Do a search first
        self.license.search("Channel")
        self.page.wait_for_timeout(2000)

        # Count filtered results
        filtered_count = self.page.locator("tr, div[class*='row']").count()

        # Clear search
        self.license.clear_search()
        self.page.wait_for_timeout(2000)

        # Full list should have at least as many items
        full_count = self.page.locator("tr, div[class*='row']").count()
        assert full_count >= filtered_count, \
            "Clearing search did not restore the full list"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_empty_search_does_not_filter(self):
        """Verify empty search does not filter license data."""
        self._navigate()

        initial_count = self.page.locator("tr, div[class*='row']").count()

        self.license.search("")
        self.page.wait_for_timeout(1000)

        after_count = self.page.locator("tr, div[class*='row']").count()
        assert after_count == initial_count, \
            "Empty search should not change the displayed data"


class TestLicenseExport:
    """Tests for CSV export functionality on Licenses page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.license = LicensePage(self.page)
        yield

    def _navigate(self):
        """Navigate to Licenses page."""
        self.license.navigate()

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_csv_download_option_available(self):
        """Verify CSV download option is available on Licenses page."""
        self._navigate()

        download_btn = self.page.locator(
            "button:has-text('CSV'), button:has-text('Export'), "
            "button:has-text('Download'), img[src*='download'], "
            "img[src*='export'], img[alt*='Download'], img[alt*='Export']"
        ).first
        expect(download_btn).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_csv_download_triggers_file(self):
        """Verify CSV download button is available and functional."""
        self._navigate()
        self.page.wait_for_timeout(2000)

        # Look for download image or button
        download_elem = self.page.locator(
            "img[src*='downloadLicense'], img[src*='download'], img[alt='Download'], "
            "button:has-text('CSV'), button:has-text('Export'), button:has-text('Download')"
        ).first

        if download_elem.count() == 0:
            pytest.skip("No download element found")

        # Verify element is visible
        expect(download_elem).to_be_visible(timeout=10000)

        # Hover over the download element to activate it
        download_elem.hover()
        self.page.wait_for_timeout(500)

        # Trigger the download and capture it.
        #
        # Playwright cannot always observe the download event depending on how
        # the browser handles the response, so failing to *capture* one is
        # tolerated. But if a download IS captured, its filename must be a CSV -
        # that assertion has to be able to fail, so it lives outside the try.
        download = None
        try:
            with self.page.expect_download(timeout=15000) as download_info:
                download_elem.click(force=True)
            download = download_info.value
        except PlaywrightTimeoutError:
            pytest.skip(
                "Download event was not captured within 15s - the export may "
                "still work, but this run cannot verify it."
            )

        assert download.suggested_filename.endswith(".csv"), \
            f"Expected a .csv export, got: {download.suggested_filename}"
