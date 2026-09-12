"""Admin General section tests - sidebar navigation, tab switching,
sub-sections (Audit Trail, Event Wall), and dashboard structure.

Covers the Admin General sub-tabs that are not part of Users, Sites,
or Rules test suites. Every check reads a value the page shows: the
header's tab labels, the selected tab's paint (its box paints
rgb(3, 23, 31); the address stays /admin for every tab), the General
cards' titles, blurbs and View buttons, the audit trail's breadcrumb
and column headers (measured 09/12/2026 on US; register row 53).
"""
import re

import pytest
from playwright.sync_api import expect

from tests.shared.pages.admin_page import AdminPage


class TestAdminGeneral:
    """Tests for Admin General section navigation and content."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.admin = AdminPage(self.page)
        self.admin.navigate_to_admin()
        yield

    def _open_general(self):
        """Click the General tab; the Rules sub-tab signals it rendered.

        .first is required: 'Rules' appears in the admin sidebar and in the
        General sub-nav, so the bare locator violates strict mode.
        """
        self.admin.general_tab.click()
        expect(
            self.page.locator("p:text-is('Rules')").first
        ).to_be_visible(timeout=10000)

    # --- Admin sidebar structure ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_admin_sidebar_tabs_visible(self):
        """Verify the admin header lists its tabs in order.

        Steps:
        1. Open Admin and read the header's tab labels left to right.
           Expected: Sites, Users and General appear in that order among Dashboard, Sites, Users, Maps, Integrations, Rules, General, LPR and Licenses.
        """
        expect(self.admin.users_tab.first).to_be_visible(timeout=10000)
        names = self.admin.admin_tab_names()
        core = [n for n in names if n in ("Sites", "Users", "General")]
        assert core == ["Sites", "Users", "General"], (
            f"the admin header reads {names}; Sites, Users and General should be there in that order")
        strangers = [n for n in names if n not in AdminPage.ADMIN_TABS]
        assert not strangers, f"the admin header carries tabs this suite does not know: {strangers}"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_navigate_to_general(self):
        """Verify clicking General tab opens the General section.

        Steps:
        1. Click the General tab.
           Expected: General is painted as the selected tab and its cards are listed: Deployment, Audit Trail, System Logs, Multi-Factor Authentication and Event Wall.
        """
        self.admin.general_tab.wait_for(state="visible", timeout=10000)
        self._open_general()
        self.admin.expect_admin_tab_selected("General")
        titles = self.admin.general_card_titles()
        assert titles == list(AdminPage.GENERAL_CARDS), (
            f"General lists the cards {titles}, expected {list(AdminPage.GENERAL_CARDS)}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_general_section_has_rules_tab(self):
        """Verify the General section contains the Rules sub-tab."""
        # oracle: _open_general expects the Rules sub-tab visible
        self._open_general()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_general_section_has_audit_trail(self):
        """Verify the General section's Audit Trail card.

        Steps:
        1. Open Admin > General and read the Audit Trail card.
           Expected: Its blurb starts "Monitor and review all activities" and it carries one View button.
        """
        self._open_general()
        card = self.admin.general_card("Audit Trail")
        expect(card).to_contain_text("Monitor and review all activities", timeout=10000)
        expect(card.locator("button")).to_have_count(1)
        expect(card.locator("button")).to_have_text("View")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_general_section_has_event_wall(self):
        """Verify the General section's Event Wall card.

        Steps:
        1. Open Admin > General and read the Event Wall card.
           Expected: Its blurb reads "Manage event wall configuration." and it carries one View button.
        """
        self._open_general()
        card = self.admin.general_card("Event Wall")
        expect(card).to_contain_text("Manage event wall configuration.", timeout=10000)
        expect(card.locator("button")).to_have_count(1)
        expect(card.locator("button")).to_have_text("View")

    # --- Tab switching ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_switch_users_to_sites(self):
        """Verify switching from Users tab to Sites tab works.

        Steps:
        1. Open Admin > Users, then click Sites.
           Expected: Sites is painted as the selected tab, Users is not, and the Sites search field shows its Search placeholder.
        """
        self.admin.navigate_to_users()
        self.admin.navigate_to_sites()
        self.admin.expect_admin_tab_selected("Sites")
        assert not self.admin.admin_tab_is_selected("Users"), "Users stays painted as selected beside Sites"
        search = self.page.locator("input[placeholder*='Search']").first
        expect(search).to_be_visible(timeout=10000)
        expect(search).to_have_attribute("placeholder", re.compile(r"^Search\s*$"))

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_switch_sites_to_general(self):
        """Verify switching from Sites tab to General tab works."""
        # oracle: _open_general expects the Rules sub-tab visible
        # after the switch away from Sites
        self.admin.navigate_to_sites()
        self._open_general()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_round_trip_users_general_users(self):
        """Verify navigating Users -> General -> Users round-trip works.

        Steps:
        1. Open Admin > Users, click General, then click Users again.
           Expected: Users is painted as the selected tab, General is not, and the Add User button is back.
        """
        self.admin.navigate_to_users()
        self._open_general()
        self.admin.expect_admin_tab_selected("General")
        self.admin.navigate_to_users()
        self.admin.expect_admin_tab_selected("Users")
        assert not self.admin.admin_tab_is_selected("General"), "General stays painted as selected beside Users"
        expect(self.admin.add_user_button).to_be_visible(timeout=10000)

    # --- Audit Trail navigation ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_open_audit_trail(self):
        """Verify the Audit Trail card's View button opens the audit log.

        Steps:
        1. Open Admin > General and click View on the Audit Trail card.
           Expected: The breadcrumb reads General > Audit Trail and the table's columns are Username, Role Type, Date & Time, IP and Action.
        """
        self._open_general()
        # exact=True: the card blurb contains 'review', so a substring
        # 'View' match clicks prose instead of the button
        self.admin.general_card("Audit Trail").get_by_text("View", exact=True).first.click()
        crumb = self.page.get_by_text(AdminPage.AUDIT_TRAIL_CRUMB, exact=True)
        expect(crumb).to_have_text(AdminPage.AUDIT_TRAIL_CRUMB, timeout=15000)
        headers = self.admin.audit_trail_headers()
        assert headers == list(AdminPage.AUDIT_TRAIL_HEADERS), (
            f"the audit table's columns read {headers}, expected {list(AdminPage.AUDIT_TRAIL_HEADERS)}")

    # --- Event Wall navigation ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_open_event_wall(self):
        """Verify clicking Event Wall opens the event wall view."""
        self._open_general()
        # _open_general has already proved the section rendered, so a
        # missing Event Wall entry is a regression in a permanent
        # control, not an absent artifact (register item 25).
        event_wall = self.page.get_by_text("Event Wall", exact=False).first
        event_wall.wait_for(state="visible", timeout=10000)
        event_wall.click()
        # Event Wall should show some content
        content = self.page.locator("[class*='event'], [class*='wall']")
        try:
            expect(content.first).to_be_visible(timeout=15000)
        except AssertionError:
            assert self.page.locator("img").count() > 5, \
                "Event Wall page should have visible content"

    # --- Admin page refresh ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_general
    def test_admin_page_after_refresh(self):
        """Verify the Admin page loads correctly after a browser refresh.

        Steps:
        1. On Admin, refresh the browser.
           Expected: The address still ends in /admin and the header lists Sites, Users and General in that order.
        """
        self.page.reload()
        expect(self.page).to_have_url(re.compile(r"/admin/?$"))
        expect(self.admin.users_tab.first).to_be_visible(timeout=15000)
        names = self.admin.admin_tab_names()
        core = [n for n in names if n in ("Sites", "Users", "General")]
        assert core == ["Sites", "Users", "General"], f"after the refresh the admin header reads {names}"
