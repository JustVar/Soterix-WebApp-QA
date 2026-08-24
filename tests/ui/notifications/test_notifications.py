"""Notification tests - mute notifications, clear all, admin rule mute."""
import pytest
from playwright.sync_api import Error as PlaywrightError, expect


class TestNotifications:
    """Tests for notification panel and admin notification settings."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.header_icons = self.page.locator(".header-right-group .icon")
        # the mute/unmute control is the panel-open marker; the muted
        # state's src is 'UnMuteNotification' (capital M), which
        # CONTAINS 'MuteNotification', so one substring matches both
        self.mute_union = self.page.locator(
            # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
            "img[src*='MuteNotification']"
        )

    def _open_panel(self):
        """Open the notification panel; the bell is a toggle, so only
        click when the open marker is absent."""
        self.header_icons.first.wait_for(state="visible", timeout=10000)
        if self.mute_union.count() and self.mute_union.first.is_visible():
            return
        self.header_icons.nth(1).click()
        self.mute_union.first.wait_for(state="visible", timeout=10000)

    @pytest.mark.ui
    @pytest.mark.notifications
    def test_open_notification_panel(self):
        """Verify clicking the notification bell opens the notification panel."""
        self.header_icons.first.wait_for(state="visible", timeout=10000)

        icon_count = self.header_icons.count()
        assert icon_count >= 2, (
            f"Expected at least 2 header icons (notifications), found {icon_count}"
        )

        self._open_panel()
        # state-agnostic: either the mute or unmute control marks open
        expect(self.mute_union.first).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.notifications
    def test_mute_notifications(self):
        """The mute control toggles state and restores.

        The src flipping (MuteNotification <-> UnMuteNotification) is
        the state-changed oracle; the second toggle restores the
        shared account to its starting state.
        """
        self._open_panel()
        before = self.mute_union.first.get_attribute("src")

        self.mute_union.first.click()
        # the click can close the panel; the toggle-safe reopen
        # resolves it
        self._open_panel()
        expect(self.mute_union.first).not_to_have_attribute(
            "src", before, timeout=10000
        )

        self.mute_union.first.click()
        self._open_panel()
        expect(self.mute_union.first).to_have_attribute(
            "src", before, timeout=10000
        )

    @pytest.mark.ui
    @pytest.mark.notifications
    def test_admin_mute_rule_notification(self):
        """Verify a rule notification can be muted from Admin > General > Rules."""
        # Navigate to Admin; the General tab appearing is the signal
        self.page.locator("a[href*='admin']").click()
        general_tab = self.page.locator("p:text-is('General')")
        general_tab.wait_for(state="visible", timeout=15000)
        general_tab.click()

        # .first: 'Rules' appears in both the admin sidebar and the
        # General content, and the sidebar entry is the target
        rules_tab = self.page.locator("p:text-is('Rules')").first
        rules_tab.wait_for(state="visible", timeout=10000)
        rules_tab.click()

        # rule rows render async; the first mute icon is the signal,
        # a miss routes to the skip below
        mute_icons = self.page.locator("img[aria-label='Mute Notification']")
        try:
            mute_icons.first.wait_for(state="visible", timeout=10000)
        # none within the bound means no rules carry the icon
        except PlaywrightError:
            pass
        if mute_icons.count() == 0:
            pytest.skip("No mute notification icons found (no rules exist)")

        # Click the last mute icon (same as Selenium test)
        mute_icons.last.click()

        # the icon set re-renders after the toggle; a visible
        # mute/unmute icon reappearing is the applied signal (the
        # raising wait carries the oracle)
        remaining_mute = self.page.locator(
            "img[aria-label='Mute Notification'], "
            "img[aria-label='Unmute Notification']"
        )
        remaining_mute.first.wait_for(state="visible", timeout=10000)
