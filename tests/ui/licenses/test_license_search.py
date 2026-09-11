"""License Search, Filter, and CSV Export tests.

The search box filters the Available table client-side by feature name
and by the Available count (its placeholder: 'Search by feature,
availability.'); a filter that matches nothing renders one row reading
'No Data!' (measured on both boxes 09/11/2026). The terms come from the
table itself, so the checks hold on any tenant.
"""
import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, expect

from tests.shared.pages.license_page import LicensePage


class TestLicenseSearch:
    """Tests for search and filter on Licenses page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.license = LicensePage(self.page)
        yield

    def _first_feature(self) -> dict:
        """The first feature row of the unfiltered table; the search terms come from it."""
        self.license.navigate()
        rows = self.license.available_rows()
        assert rows, "The Available table has no feature rows to search for"
        return rows[0]

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_search_with_valid_license_name(self):
        """Verify searching a feature's full name lists only rows carrying that name.

        Steps:
        1. Open Admin > Licenses and note the first feature's name.
           Expected: A named row in the Available table.
        2. Type that name into the search box.
           Expected: At least one row is listed, every listed row's feature contains the name, and no row reads No Data!.
        """
        first = self._first_feature()
        self.license.search(first["name"])
        assert not self.license.is_no_data(), f"'{first['name']}' filtered its own row away"
        rows = self.license.available_rows()
        assert rows, f"No feature row after searching {first['name']!r}"
        assert all(first["name"].lower() in r["name"].lower() for r in rows), (
            f"Rows after searching {first['name']!r}: {[r['name'] for r in rows]}")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_search_with_partial_keyword(self):
        """Verify a partial feature name filters to the rows containing it.

        Steps:
        1. Open Admin > Licenses and note the first feature's name.
           Expected: A named row in the Available table.
        2. Type the first four letters of that name into the search box.
           Expected: The first feature is still listed and every listed row contains those letters.
        """
        first = self._first_feature()
        part = first["name"][:4]
        self.license.search(part)
        rows = self.license.available_rows()
        assert any(r["name"] == first["name"] for r in rows), (
            f"{first['name']!r} dropped out when searching {part!r}: {[r['name'] for r in rows]}")
        assert all(part.lower() in r["name"].lower() for r in rows), (
            f"A row without {part!r} stayed listed: {[r['name'] for r in rows]}")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_search_with_license_key(self):
        """Verify searching an Available count lists the features with that count.

        The placeholder names 'availability' as a search field; the term is
        the first row's Available number, so it exists on every tenant.

        Steps:
        1. Open Admin > Licenses and note the first feature's Available number.
           Expected: A whole number.
        2. Type that number into the search box.
           Expected: The first feature is still listed and every listed row's Available (or its name) contains the number.
        """
        first = self._first_feature()
        term = str(first["available"])
        self.license.search(term)
        rows = self.license.available_rows()
        assert any(r["name"] == first["name"] for r in rows), (
            f"{first['name']!r} (Available {term}) dropped out when searching {term}: {rows}")
        assert all(term in str(r["available"]) or term in r["name"] for r in rows), (
            f"A row without {term} in its Available count or name stayed listed: {rows}")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_invalid_search_shows_no_results(self):
        """Verify a term that matches nothing leaves only the No Data! row.

        Steps:
        1. Open Admin > Licenses and type ZZZZNONEXISTENT999 into the search box.
           Expected: The table shows exactly one row and it reads No Data!; no feature row remains.
        """
        self._first_feature()
        self.license.search("ZZZZNONEXISTENT999")
        expect(self.page.locator("tr:has(td)")).to_have_count(1, timeout=10000)
        assert self.license.is_no_data(), f"Expected the No Data! row, got {self.license.data_rows()}"
        assert self.license.available_rows() == []

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_clear_search_restores_list(self):
        """Verify clearing the search brings back exactly the rows shown before it.

        Steps:
        1. Open Admin > Licenses and note every row of the Available table.
           Expected: At least one feature row.
        2. Type ZZZZNONEXISTENT999 into the search box.
           Expected: Only the No Data! row is shown.
        3. Clear the search box.
           Expected: The table shows the same rows as in step 1, in the same order.
        """
        self._first_feature()
        before = self.license.data_rows()
        self.license.search("ZZZZNONEXISTENT999")
        expect(self.page.locator("tr:has(td)")).to_have_count(1, timeout=10000)
        assert self.license.is_no_data()
        self.license.clear_search()
        expect(self.page.locator("tr:has(td)")).to_have_count(len(before), timeout=10000)
        assert self.license.data_rows() == before, "Clearing the search did not restore the same rows"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_empty_search_does_not_filter(self):
        """Verify an empty search term changes nothing in the table.

        Steps:
        1. Open Admin > Licenses and note every row of the Available table.
           Expected: At least one feature row.
        2. Click into the search box and leave it empty.
           Expected: The table still shows the same rows.
        """
        self._first_feature()
        before = self.license.data_rows()
        self.license.search("")
        assert self.license.data_rows() == before, "An empty search changed the rows"


class TestLicenseExport:
    """Tests for CSV export functionality on Licenses page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.license = LicensePage(self.page)
        yield

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_csv_download_option_available(self):
        """Verify the Licenses page offers one Download control, labelled as such.

        Steps:
        1. Open Admin > Licenses and look at the controls above the table.
           Expected: Exactly one download icon, whose alt text reads Download, is shown.
        """
        self.license.navigate()
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        icon = self.page.locator("img[src*='downloadLicense']")
        expect(icon).to_have_count(1)
        expect(icon.first).to_be_visible(timeout=10000)
        expect(icon.first).to_have_attribute("alt", "Download")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_csv_download_triggers_file(self):
        """Verify clicking Download produces a CSV export.

        Known app defect (09/11/2026, both boxes): the click produces no
        download, no request and no new page, whether the icon, its parent
        or a dispatched click is used. The test fails naming that until the
        app fix; a download that does arrive must be a .csv.

        Steps:
        1. Open Admin > Licenses and click the Download icon.
           Expected: The browser receives a file whose name ends in .csv.
        """
        self.license.navigate()
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        icon = self.page.locator("img[src*='downloadLicense']").first
        expect(icon).to_be_visible(timeout=10000)
        requests: list[str] = []
        self.page.on("request", lambda r: requests.append(r.url) if "/REST/" in r.url else None)
        try:
            with self.page.expect_download(timeout=15000) as download_info:
                icon.click()
            download = download_info.value
        except PlaywrightTimeoutError:
            raise AssertionError(
                "The Download icon produced no file in 15 s"
                + (f"; it sent {len(requests)} API request(s): {requests[:3]}" if requests
                   else " and sent no request at all (app defect - register, App defects)")
            ) from None
        assert download.suggested_filename.endswith(".csv"), (
            f"Expected a .csv export, got: {download.suggested_filename}")
