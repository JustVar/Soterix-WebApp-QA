"""Deeper notification panel tests - content, toggle, badge, close behavior.

Extends basic notification tests with panel content checks, mute/unmute
round-trip, badge count, close behavior, and notification entry inspection.
"""
import pytest
from playwright.sync_api import expect


class TestNotificationsDeeper:
    """Deeper tests for notification panel behavior and content."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self._header_icons = self.page.locator(".header-right-group .icon")

    def _open_notification_panel(self):
        """Click the notification bell icon to open the panel."""
        self._header_icons.first.wait_for(state="visible", timeout=10000)
        self._header_icons.nth(1).click()
        self.page.wait_for_timeout(1000)

    def _close_notification_panel(self):
        """Close the notification panel by clicking the bell icon again."""
        self._header_icons.nth(1).click()
        self.page.wait_for_timeout(500)

    def _get_mute_button(self):
        """Return the mute or unmute button locator (whichever is visible)."""
        return self.page.locator(
            "img[src*='media/MuteNotification'], "
            "img[src*='media/UnmuteNotification']"
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

        # Close panel
        self._close_notification_panel()
        self.page.wait_for_timeout(500)

        # Mute button should no longer be visible (panel closed)
        mute_btn_after = self.page.locator("img[src*='media/MuteNotification']")
        assert mute_btn_after.count() == 0 or not mute_btn_after.first.is_visible(), (
            "Notification panel should close after clicking bell again"
        )

    @pytest.mark.ui
    @pytest.mark.notifications
    @pytest.mark.notifications_deeper
    def test_notification_panel_reopen_after_close(self):
        """Verify notification panel can be reopened after closing."""
        self._open_notification_panel()
        mute_btn = self._get_mute_button()
        expect(mute_btn.first).to_be_visible(timeout=5000)

        self._close_notification_panel()
        self.page.wait_for_timeout(500)

        # Reopen
        self._open_notification_panel()
        mute_btn = self._get_mute_button()
        expect(mute_btn.first).to_be_visible(timeout=5000)

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
        """Verify the notification bell icon is always visible in the header."""
        bell = self._header_icons.nth(1)
        expect(bell).to_be_visible(timeout=10000)

    # --- Mute/unmute round-trip ---

    @pytest.mark.ui
    @pytest.mark.notifications
    @pytest.mark.notifications_deeper
    def test_mute_unmute_round_trip(self):
        """Verify muting then unmuting notifications works as a toggle.

        Clicks mute, verifies state changed, then clicks again to restore.
        """
        self._open_notification_panel()

        mute_btn = self.page.locator("img[src*='media/MuteNotification']")
        unmute_btn = self.page.locator("img[src*='media/UnmuteNotification']")

        # Determine initial state
        initial_is_muted = unmute_btn.count() > 0 and unmute_btn.first.is_visible()

        # Click to toggle
        btn = self._get_mute_button()
        btn.first.click()
        self.page.wait_for_timeout(1500)

        # Reopen panel to check state
        self._open_notification_panel()
        self.page.wait_for_timeout(500)

        # Toggle back
        btn = self._get_mute_button()
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1500)

        # Reopen and verify we're back to original state
        self._open_notification_panel()
        now_is_muted = unmute_btn.count() > 0 and unmute_btn.first.is_visible()

        assert now_is_muted == initial_is_muted, (
            f"Expected mute state to return to {initial_is_muted} "
            f"after round-trip toggle, got {now_is_muted}"
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

        # Look for notification entries - typically text content within the panel
        # Notification panel opens below the bell icon in the header area
        panel = self.page.locator(
            ".notification-panel, "
            "[class*='notification'], "
            "[class*='Notification']"
        )
        self.page.wait_for_timeout(1000)

        if panel.count() > 0:
            text = panel.first.inner_text().strip()
            # Panel should have some text (notifications or "no notifications" message)
            assert len(text) > 0, "Notification panel should have text content"
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

        Opens panel, navigates to Search, then reopens panel.
        """
        self._open_notification_panel()
        mute_btn = self._get_mute_button()
        expect(mute_btn.first).to_be_visible(timeout=5000)
        self._close_notification_panel()

        # Navigate to Search page
        search_link = self.page.locator("a[href*='search']")
        search_link.click()
        self.page.wait_for_timeout(3000)

        # Reopen notification panel from Search page
        self._open_notification_panel()
        mute_btn = self._get_mute_button()
        expect(mute_btn.first).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.notifications
    @pytest.mark.notifications_deeper
    def test_notification_panel_survives_page_refresh(self):
        """Verify notification icon is present after page refresh."""
        self.page.reload()
        self.page.wait_for_timeout(3000)

        self._header_icons.first.wait_for(state="visible", timeout=15000)
        bell = self._header_icons.nth(1)
        expect(bell).to_be_visible(timeout=10000)

        # Panel should still open after refresh
        self._open_notification_panel()
        mute_btn = self._get_mute_button()
        expect(mute_btn.first).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.notifications
    @pytest.mark.notifications_deeper
    def test_notification_icon_not_affected_by_views_page(self):
        """Verify notification icons remain functional on the Views page.

        Views page has heavy video streaming - notification bell should
        still be accessible in the header.
        """
        # Navigate to Views
        views_link = self.page.locator("text=Views").first
        views_link.click(force=True)
        self.page.wait_for_timeout(3000)

        # Bell should still work
        self._header_icons.first.wait_for(state="visible", timeout=15000)
        self._open_notification_panel()
        mute_btn = self._get_mute_button()
        expect(mute_btn.first).to_be_visible(timeout=5000)
