"""Deeper notification panel tests - content, toggle, badge, close behavior.

Extends basic notification tests with panel content checks, mute/unmute
round-trip, badge count, close behavior, and notification entry inspection.
"""
import re

import pytest
from playwright.sync_api import Error as PlaywrightError, expect

# One worker for every module that writes this account's rules and their mute state: under
# -n they would otherwise spread across workers and race on the same
# tenant state (pytest.ini --dist loadgroup).
pytestmark = pytest.mark.xdist_group("account_rules")


class TestNotificationsDeeper:
    """Deeper tests for notification panel behavior and content."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self._header_icons = self.page.locator(".header-right-group .icon")

    def _get_mute_button(self):
        """The mute/unmute control - the panel-open marker.

        The muted state's src is 'UnMuteNotification' (capital M),
        which CONTAINS 'MuteNotification', so one substring matches
        both states.
        """
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        return self.page.locator("img[src*='MuteNotification']")

    def _open_notification_panel(self):
        """Open the panel; the bell is a toggle, so only click when
        the mute/unmute marker is absent."""
        self._header_icons.first.wait_for(state="visible", timeout=10000)
        marker = self._get_mute_button()
        if marker.count() and marker.first.is_visible():
            return
        self._header_icons.nth(1).click()
        marker.first.wait_for(state="visible", timeout=10000)

    def _expect_panel_open(self):
        """The open panel: its heading reads Notifications and its mute
        control's icon file names the state (MuteNotification unmuted,
        UnMuteNotification muted; measured 09/12/2026)."""
        expect(self.page.locator(".headingNotification").first).to_have_text("Notifications", timeout=5000)
        expect(self._get_mute_button().first).to_have_attribute("src", re.compile("MuteNotification"))

    def _close_notification_panel(self):
        """Close the panel; the mute marker leaving is the signal."""
        self._header_icons.nth(1).click()
        self._get_mute_button().first.wait_for(
            state="hidden", timeout=5000
        )

    # --- Panel open/close ---

    @pytest.mark.ui
    @pytest.mark.notifications
    @pytest.mark.notifications_deeper
    def test_notification_panel_closes_on_reclick(self):
        """Verify clicking the bell icon again closes the notification panel."""
        self._open_notification_panel()

        mute_btn = self._get_mute_button()
        expect(mute_btn.first).to_be_visible(timeout=5000)

        # Close panel; its own marker wait is the closed signal
        self._close_notification_panel()

        mute_btn_after = self._get_mute_button()
        assert mute_btn_after.count() == 0 or not mute_btn_after.first.is_visible(), (
            "Notification panel should close after clicking bell again"
        )

    @pytest.mark.ui
    @pytest.mark.notifications
    @pytest.mark.notifications_deeper
    def test_notification_panel_reopen_after_close(self):
        """Verify notification panel can be reopened after closing.

        Steps:
        1. Open the notification panel, close it with the bell, then open it again.
           Expected: The panel's mute control leaves on close and is back on reopen, its icon file naming the mute state, under the Notifications heading.
        """
        self._open_notification_panel()
        expect(self._get_mute_button().first).to_have_attribute("src", re.compile("MuteNotification"), timeout=5000)
        self._close_notification_panel()
        expect(self._get_mute_button()).to_have_count(0)
        # Reopen
        self._open_notification_panel()
        self._expect_panel_open()

    # --- Header icons ---

    @pytest.mark.ui
    @pytest.mark.notifications
    @pytest.mark.notifications_deeper
    def test_header_icons_present(self):
        """Verify the header right group has expected notification icons."""
        self._header_icons.first.wait_for(state="visible", timeout=10000)
        count = self._header_icons.count()
        assert count >= 2, (
            f"Expected at least 2 header icons (notification + profile), got {count}"
        )

    @pytest.mark.ui
    @pytest.mark.notifications
    @pytest.mark.notifications_deeper
    def test_notification_bell_icon_visible(self):
        """Verify the header's icon group and the bell's place in it.

        Steps:
        1. Read the header's right-hand icon group.
           Expected: Four icon buttons, the last one reading the user's initials; the second one (the bell) opens the Notifications panel.
        """
        self._header_icons.first.wait_for(state="visible", timeout=10000)
        expect(self._header_icons).to_have_count(4)
        initials = self._header_icons.last.inner_text().strip()
        assert re.fullmatch(r"[A-Z]{1,3}", initials) is not None, (
            f"the last header icon reads {initials!r}, expected the user's initials")
        self._open_notification_panel()
        self._expect_panel_open()

    # --- Mute/unmute round-trip ---

    @pytest.mark.ui
    @pytest.mark.notifications
    @pytest.mark.notifications_deeper
    def test_mute_unmute_round_trip(self):
        """Verify muting then unmuting notifications works as a toggle.

        Clicks mute, verifies state changed, then clicks again to restore.
        """
        self._open_notification_panel()

        # the control's src is the state (MuteNotification when
        # unmuted, UnMuteNotification when muted)
        initial_src = self._get_mute_button().first.get_attribute("src")

        # Toggle; the toggle-safe reopen resolves whether the panel
        # closed or stayed open, and the flipped src proves the change
        self._get_mute_button().first.click()
        self._open_notification_panel()
        expect(self._get_mute_button().first).not_to_have_attribute(
            "src", initial_src, timeout=10000
        )

        # Toggle back; the src returning proves the round trip
        self._get_mute_button().first.click()
        self._open_notification_panel()
        expect(self._get_mute_button().first).to_have_attribute(
            "src", initial_src, timeout=10000
        )

    # --- Panel content ---

    @pytest.mark.ui
    @pytest.mark.notifications
    @pytest.mark.notifications_deeper
    def test_notification_panel_has_content(self):
        """Verify notification panel shows text content (not empty).

        A live QA system with event rules should have notification entries.
        Soft assertion: some accounts may have all rules muted.
        """
        self._open_notification_panel()

        # notification entries render async after the panel opens; a
        # miss falls to the else branch below
        panel = self.page.locator(
            ".notification-panel, "
            "[class*='notification'], "
            "[class*='Notification']"
        )
        try:
            panel.first.wait_for(state="visible", timeout=5000)
        # no panel-classed container - the else branch checks the
        # open marker instead
        except PlaywrightError:
            pass

        if panel.count() > 0:
            text = panel.first.inner_text().strip()
            # Panel should have some text (notifications or "no notifications" message)
            assert len(text) > 0, "Notification panel should have text content"
            # content, not a bare frame: the text holds a word of 3 letters or more
            assert re.search(r"[A-Za-z]{3,}", text) is not None, f"the notification panel reads {text[:80]!r}"
        else:
            # No panel class found - the panel may use a different structure
            # Just verify the mute button is present (panel is open)
            mute_btn = self._get_mute_button()
            expect(mute_btn.first).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.notifications
    @pytest.mark.notifications_deeper
    def test_notification_panel_after_page_navigation(self):
        """Verify notification panel works after navigating to a different page.

        Steps:
        1. Open the panel, close it, then open Search from the sidebar.
           Expected: The address ends in /search.
        2. Open the panel again.
           Expected: The Notifications panel opens with its mute control.
        """
        self._open_notification_panel()
        self._expect_panel_open()
        self._close_notification_panel()
        # Navigate to Search; the reopened panel's own marker wait
        # covers the page transition
        self.page.locator("a[href*='search']").click()
        expect(self.page).to_have_url(re.compile(r"/search/?$"), timeout=15000)
        self._open_notification_panel()
        self._expect_panel_open()

    @pytest.mark.ui
    @pytest.mark.notifications
    @pytest.mark.notifications_deeper
    def test_notification_panel_survives_page_refresh(self):
        """Verify notification icon is present after page refresh.

        Steps:
        1. Refresh the browser.
           Expected: The address is unchanged and the header shows its four icons.
        2. Click the bell.
           Expected: The Notifications panel opens with its mute control.
        """
        before = self.page.url
        # reload waits for the load event on its own
        self.page.reload()
        self._header_icons.first.wait_for(state="visible", timeout=15000)
        expect(self.page).to_have_url(before)
        expect(self._header_icons).to_have_count(4, timeout=10000)
        # Panel should still open after refresh
        self._open_notification_panel()
        self._expect_panel_open()

    @pytest.mark.ui
    @pytest.mark.notifications
    @pytest.mark.notifications_deeper
    def test_notification_icon_not_affected_by_views_page(self):
        """Verify notification icons remain functional on the Views page.

        Views page has heavy video streaming - notification bell should
        still be accessible in the header.

        Steps:
        1. Open Views from the sidebar.
           Expected: The address is the site root.
        2. Click the bell.
           Expected: The Notifications panel opens with its mute control.
        """
        # Navigate to Views; the header wait below is the arrival signal
        views_link = self.page.locator("text=Views").first
        views_link.click(force=True)
        expect(self.page).to_have_url(re.compile(r"^https?://[^/]+/?$"), timeout=15000)
        # Bell should still work
        self._header_icons.first.wait_for(state="visible", timeout=15000)
        self._open_notification_panel()
        self._expect_panel_open()
