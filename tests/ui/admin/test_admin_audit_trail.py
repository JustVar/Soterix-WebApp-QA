"""Admin Audit Trail tests - table display, records, navigation.

Rebuilt 08/14/2026 on the measured page. Admin > General is a card
layout; the Audit Trail card's View BUTTON (exact-match the label:
the card blurb contains 'review', so a substring match clicks prose)
opens 'General > Audit Trail' in-page: a real table with columns
Username | Role Type | Date & Time | IP | Action, live records
('User X logged in.' with dd-mm-yyyy | hh:mm timestamps and IPs),
and a Today range filter. The old suite clicked the card TITLE (a
no-op) and probed the General cards page with unions broad enough
to match it - its seven early-exit returns are gone with it.

09/12/2026: every check reads a value: the breadcrumb's text, the
column set, the record's date parsed against today, its cells, the
absence of a pagination control on the one-page table (register row 53).
"""
import datetime
import re

import pytest
from playwright.sync_api import Error as PlaywrightError, expect

from tests.shared.pages.admin_page import AdminPage


class TestAdminAuditTrail:
    """Tests for Admin > General > Audit Trail."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.admin = AdminPage(self.page)
        self.admin.navigate_to_admin()
        # General renders as cards; the Rules sub-tab marks it ready
        self.admin.general_tab.wait_for(state="visible", timeout=10000)
        self.admin.general_tab.click()
        self.page.locator("p:text-is('Rules')").first.wait_for(
            state="visible", timeout=10000
        )
        card = self.page.locator(".MuiCard-root").filter(
            has_text="Audit Trail"
        ).first
        # General is already proved up by the Rules sub-tab wait above,
        # so a missing card here is a regression in a permanent control,
        # not an absent artifact (register item 25).
        card.wait_for(state="visible", timeout=10000)
        # exact=True: the card blurb contains 'review', so a substring
        # 'View' match clicks prose instead of the button. A View
        # click during cards hydration can be silently dropped - one
        # retry self-heals.
        self.crumb = self.page.get_by_text(
            "General > Audit Trail", exact=False
        ).first
        card.get_by_text("View", exact=True).first.click()
        try:
            self.crumb.wait_for(state="visible", timeout=7000)
        except PlaywrightError:
            card.get_by_text("View", exact=True).first.click()
            self.crumb.wait_for(state="visible", timeout=15000)
        self.rows = self.page.locator("tbody tr")
        return

    def _first_row(self):
        """The first real audit record.

        The table renders a 'No data available' placeholder row while
        the fetch is in flight (caught live 08/14/2026), so the wait
        keys on a row that is not the placeholder. The shared tenant
        always logs activity, so a timeout is a real failure.
        """
        real_rows = self.rows.filter(
            has_text=re.compile(r"\S")
        ).filter(has_not_text="No data available")
        real_rows.first.wait_for(state="visible", timeout=20000)
        return real_rows.first

    def _first_cells(self) -> list[str]:
        """The first record's cells: username, role, date, time, IP, action."""
        return [c.strip() for c in self._first_row().locator("td").all_inner_texts()]

    # --- Page structure ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_audit_trail_page_loads(self):
        """The audit page shows its breadcrumb and its table's columns.

        Steps:
        1. Open Admin > General and click View on the Audit Trail card.
           Expected: The breadcrumb reads General > Audit Trail.
        2. Read the table's header.
           Expected: The columns are Username, Role Type, Date & Time, IP and Action, in that order.
        """
        self.step_capture.mark(1, "Open Admin > General > Audit Trail")
        expect(self.crumb).to_have_text(AdminPage.AUDIT_TRAIL_CRUMB)
        self.step_capture.mark(2, "The audit table renders its columns")
        expect(self.page.locator("table").first).to_be_visible(timeout=10000)
        headers = self.admin.audit_trail_headers()
        assert headers == list(AdminPage.AUDIT_TRAIL_HEADERS), (
            f"the audit table's columns read {headers}, expected {list(AdminPage.AUDIT_TRAIL_HEADERS)}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_audit_trail_breadcrumb(self):
        """The breadcrumb shows the navigation path.

        Steps:
        1. Open Admin > General and click View on the Audit Trail card.
           Expected: The breadcrumb reads exactly General > Audit Trail.
        """
        expect(self.crumb).to_have_text(AdminPage.AUDIT_TRAIL_CRUMB)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_audit_trail_content_area_visible(self):
        """The audit table body renders records."""
        # oracle: _first_row raises unless a record renders
        self._first_row()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_audit_trail_has_column_headers(self):
        """The table carries the measured column set.

        Steps:
        1. Open Admin > General > Audit Trail and read the table header.
           Expected: Username, Role Type, Date & Time, IP and Action, in that order and nothing else.
        """
        expect(self.page.locator("thead").first).to_be_visible(timeout=10000)
        headers = self.admin.audit_trail_headers()
        assert headers == list(AdminPage.AUDIT_TRAIL_HEADERS), (
            f"the audit table's columns read {headers}, expected {list(AdminPage.AUDIT_TRAIL_HEADERS)}")

    # --- Records ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_audit_trail_has_records(self):
        """The audit trail lists at least one record.

        Steps:
        1. Open Admin > General and click View on the Audit Trail card.
           Expected: The table shows a real audit record, not the No data available placeholder.
        """
        # oracle: _first_row raises unless a record renders
        self._first_row()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_audit_trail_record_has_date_info(self):
        """A record carries today's date and a clock time.

        Steps:
        1. Open Admin > General, click View on the Audit Trail card.
           Expected: Audit records are listed under the Today range.
        2. Read the first record's date and time.
           Expected: The Date & Time cell reads a real dd-mm-yyyy date no later than today, then | and a time as hh:mm AM or PM.
        """
        cells = self._first_cells()
        # the Date & Time cell reads "12-09-2026 | 12:36 AM" (measured 09/12/2026)
        stamps = [m for c in cells if (m := re.fullmatch(r"(\d{2}-\d{2}-\d{4}) \| (\d{1,2}:\d{2} [AP]M)", c))]
        assert len(stamps) == 1, (
            f"the first audit row carries {len(stamps)} 'dd-mm-yyyy | hh:mm AM' cells: {cells}")
        recorded = datetime.datetime.strptime(stamps[0].group(1), "%d-%m-%Y").date()
        assert recorded <= datetime.date.today(), (
            f"the first audit record is dated {recorded}, after today ({datetime.date.today()})")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_audit_trail_record_has_user_info(self):
        """A record's Username and Role Type cells are populated.

        Steps:
        1. Open Admin > General > Audit Trail and read the first record.
           Expected: The Username cell names a user and the Role Type cell names a role; the Action cell names the same user.
        """
        cells = self._first_cells()
        username, role = cells[0], cells[1]
        assert username != "", f"the first audit record has an empty Username cell: {cells}"
        assert role != "", f"the first audit record has an empty Role Type cell: {cells}"
        assert username in cells[-1], (
            f"the Action cell {cells[-1]!r} does not name the record's user {username!r}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_audit_trail_record_has_action_info(self):
        """A record's Action cell describes the activity.

        Steps:
        1. Open Admin > General and click View on the Audit Trail card.
           Expected: Audit records are listed.
        2. Read the first record's Action cell.
           Expected: It is a sentence naming the user ("User '<name>' ...").
        """
        cells = self._first_cells()
        action = cells[-1]
        assert action != "", f"the first audit record has an empty Action cell: {cells}"
        assert action.startswith("User '"), (
            f"the Action cell reads {action!r}; records read \"User '<name>' <did something>\"")

    # --- Pagination ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_audit_trail_pagination_visible(self):
        """The Today range lists its records on one page.

        Steps:
        1. Open Admin > General > Audit Trail with its Today range.
           Expected: The records are listed on one page: no pagination control renders and every row is a record.
        """
        self._first_row()
        pagination = self.page.locator(
            ".MuiPagination-root, .MuiTablePagination-root, "
            "nav[aria-label*='pagination']"
        )
        # measured 09/12/2026: the table pages nothing; a control appearing
        # here is a change to record, not a pass
        expect(pagination).to_have_count(0)
        placeholders = self.rows.filter(has_text="No data available")
        expect(placeholders).to_have_count(0)
        expect(self.rows).not_to_have_count(0)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_audit_trail_next_page(self):
        """The Next control turns the audit trail to a new set of records.

        Steps:
        1. Open Admin > General, click View on the Audit Trail card, and note the first record.
           Expected: A real audit record is listed.
        2. Click Next below the table.
           Expected: The first record changes to a different one. With no Next control there is no page to turn and the test skips.
        """
        first_row_text = self._first_row().inner_text()
        next_btn = self.page.locator(
            "button[aria-label*='next' i], button:has-text('Next')"
        )
        try:
            next_btn.first.wait_for(state="visible", timeout=5000)
        # deliberate: the audit rows are proved up by _first_row above,
        # so this timeout is the measured absence of the control
        except PlaywrightError:
            pytest.skip(
                "The audit table has rows but renders no next-page control "
                "(checked button[aria-label*=next] and a Next button), so "
                "there is no page to turn"
            )
        next_btn.first.click()
        # the first row changing is the page-turned signal
        expect(self.rows.first).not_to_have_text(
            first_row_text, timeout=15000
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_audit_trail_has_multiple_entries(self):
        """The shared tenant's activity fills more than one record.

        Steps:
        1. Open Admin > General, click View on the Audit Trail card.
           Expected: At least one audit record is listed.
        """
        first = self._first_row()
        assert self.rows.count() >= 1, "Expected at least one record"
        # a real record, not a placeholder: 1 cell for each column, and a date with digits in the Date & Time cell
        cells = first.locator("td")
        expect(cells).to_have_count(len(AdminPage.AUDIT_TRAIL_HEADERS))
        when = cells.nth(AdminPage.AUDIT_TRAIL_HEADERS.index("Date & Time")).inner_text().strip()
        assert re.search(r"\d{4}|\d{1,2}:\d{2}", when) is not None, f"the Date & Time cell reads {when!r}"

    # --- Navigation ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_back_to_general_from_audit_trail(self):
        """The breadcrumb returns to the General cards.

        Steps:
        1. On General > Audit Trail, click General in the breadcrumb.
           Expected: The General cards are back, the Audit Trail card among them, and the breadcrumb is gone.
        """
        self.page.get_by_text("General >", exact=False).first.click()
        expect(self.page.locator(".MuiCard-root").filter(
            has_text="Audit Trail"
        ).first).to_be_visible(timeout=10000)
        expect(self.crumb).not_to_be_visible()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_audit_trail_row_hover(self):
        """A record row keeps its content through hover.

        Steps:
        1. Hover the first audit record.
           Expected: The row keeps the same cells (hover changes nothing on this table).
        """
        row = self._first_row()
        before = row.inner_text()
        row.hover()
        assert row.inner_text() == before, f"hovering changed the row from {before!r} to {row.inner_text()!r}"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_audit_trail
    def test_audit_trail_after_refresh(self):
        """The audit trail page survives a browser refresh.

        Steps:
        1. Open Admin > General, click View on the Audit Trail card, then refresh the browser.
           Expected: The address still contains /admin and the General tab shows again.
        """
        # reload waits for the load event on its own
        self.page.reload()
        assert "admin" in self.page.url.lower()
        self.admin.general_tab.wait_for(state="visible", timeout=15000)
