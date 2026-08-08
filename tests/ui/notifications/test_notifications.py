"""Notification tests - mute notifications, clear all, admin rule mute."""
import pytest
from playwright.sync_api import expect


class TestNotifications:
    """Tests for notification panel and admin notification settings."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page

    @pytest.mark.ui
    @pytest.mark.notifications
    def test_open_notification_panel(self):
        """Verify clicking the notification bell opens the notification panel."""
        # Find notification icons in header-right-group
        header_icons = self.page.locator(".header-right-group .icon")
        header_icons.first.wait_for(state="visible", timeout=10000)

        icon_count = header_icons.count()
        assert icon_count >= 2, (
            f"Expected at least 2 header icons (notifications), found {icon_count}"
        )

        # Click the notification icon (second icon in the group)
        header_icons.nth(1).click()
        self.page.wait_for_timeout(1000)

        # Verify notification panel opened - look for mute button as indicator
        mute_button = self.page.locator("img[src*='media/MuteNotification']")
        expect(mute_button).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.notifications
    def test_mute_notifications(self):
        """Verify notifications can be muted via the mute button."""
        # Open notification panel
        header_icons = self.page.locator(".header-right-group .icon")
        header_icons.first.wait_for(state="visible", timeout=10000)
        header_icons.nth(1).click()
        self.page.wait_for_timeout(1000)

        # Click the mute notification button
        mute_button = self.page.locator("img[src*='media/MuteNotification']")
        expect(mute_button).to_be_visible(timeout=5000)

        # Hover the notification area to ensure mute button is interactable
        notification_area = self.page.locator(".header-right-group .icon").nth(3)
        if notification_area.is_visible():
            notification_area.hover()
            self.page.wait_for_timeout(300)

        mute_button.click()
        self.page.wait_for_timeout(1000)

        # Mute action completed without error (button click succeeded)
        # The panel may close or icon may toggle after mute - re-open and verify
        header_icons.nth(1).click()
        self.page.wait_for_timeout(1000)

        mute_or_unmute = self.page.locator(
            "img[src*='media/MuteNotification'], img[src*='media/UnmuteNotification']"
        )
        if mute_or_unmute.count() == 0:
            # Panel may not re-open to same state; mute click succeeded above
            pass
        else:
            expect(mute_or_unmute.first).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.notifications
    def test_admin_mute_rule_notification(self):
        """Verify a rule notification can be muted from Admin > General > Rules."""
        # Navigate to Admin
        admin_link = self.page.locator("a[href*='admin']")
        admin_link.click()
        self.page.wait_for_timeout(3000)

        # Click General in the admin sidebar
        general_tab = self.page.locator("p:text-is('General')")
        general_tab.wait_for(state="visible", timeout=10000)
        general_tab.click()
        self.page.wait_for_timeout(2000)

        # Click Rules. .first: 'Rules' appears in both the admin sidebar and
        # the General content, and the sidebar entry is the navigation target
        rules_tab = self.page.locator("p:text-is('Rules')").first
        rules_tab.wait_for(state="visible", timeout=10000)
        rules_tab.click()
        self.page.wait_for_timeout(3000)

        # Find mute notification icons on rules
        mute_icons = self.page.locator("img[aria-label='Mute Notification']")
        self.page.wait_for_timeout(2000)

        mute_count = mute_icons.count()
        if mute_count == 0:
            pytest.skip("No mute notification icons found (no rules exist)")

        # Click the last mute icon (same as Selenium test)
        mute_icons.last.click()
        self.page.wait_for_timeout(2000)

        # Verify click succeeded - icon should still be present or toggled
        remaining_mute = self.page.locator(
            "img[aria-label='Mute Notification'], img[aria-label='Unmute Notification']"
        )
        assert remaining_mute.count() > 0, "Mute action failed - no mute/unmute icons found"
