"""Full Screen Video Player Page Object Model.

Models the full screen overlay that appears when zooming into a single
video tile. Includes player controls, bookmark panel, and export/share
dialogs.
"""
import datetime
from playwright.sync_api import Page, expect


class FullScreenPage:
    """Page object for the full screen video player and bookmarks panel."""

    def __init__(self, page: Page):
        self.page = page

        # Player controls
        self.video_container = page.locator("[class*='video_container'][class*='new_video_player']")
        self.fullscreen_button = page.locator("img[src*='media/Zoom.']")
        # exitFullScreen appears twice in DOM - hidden one in sidebar, visible one in .top_container
        self.exit_fullscreen_button = page.locator(".top_container img[src*='exitFullScreen']")
        self.loader = page.locator(".MuiCircularProgress-root")
        self.streaming_failed = page.locator("text=failed to load")
        self.live_indicator = page.locator("img[src*='media/Live.']")

        # Timeline/playback controls (different icons in live vs archive mode)
        # In LIVE mode: pause-disable-mode icons (disabled)
        # In ARCHIVE mode: play/pause icons (active)
        self.pause_icon_live = page.locator("img[src*='media/pause-disable-mode']")
        self.pause_icon_archive = page.locator("img[src*='media/pause-icon']")
        self.play_icon = page.locator("img[src*='media/play']").first

        # Bottom control bar
        self.control_container = page.locator(".control_Container")
        self.bottom_controls = page.locator(".bottom-control-group")
        self.volume_control = page.locator("img[src*='media/volumn']")
        self.share_icon = page.locator(".bottom-control-group img[src*='media/icon-share']")
        self.settings_icon = page.locator("img[src*='media/Setting']")
        self.overlays_icon = page.locator("img[src*='media/overlays']")

        # Bookmarks panel
        self.bookmarks_toggle = page.locator("img[src*='media/dotsIcon']")
        self.bookmark_items = page.locator(".bookmarkVideoContainer")
        self.bookmark_options = page.locator(".edit-delete-option")

        # Rename dialog
        self.rename_input = page.locator("#comment_input")
        self.save_button = page.locator("button:has-text('Save')")

        # Delete confirmation
        self.delete_confirm_button = page.locator(".yes_button")

        # Export dialog
        self.export_popup = page.locator(".export_main_container_popup")
        self.export_filename_input = page.locator(".export_main_container_popup #name")
        self.export_save_to_media_toggle = page.locator(
            ".export_main_container_popup .PrivateSwitchBase-input"
        )
        self.export_button = page.locator(".save_button_export")
        self.export_progress_bar = page.locator(".export-progress-bar")

        # Share dialog
        self.share_popup = page.locator(".share_main_container")
        self.share_email_input = page.locator(".share_main_container input[name='email']")
        self.share_filename_input = page.locator(".share_main_container #name")
        self.share_save_to_media_toggle = page.locator(
            ".share_main_container .PrivateSwitchBase-input"
        )
        self.share_button = page.locator(".save_button_share")
        self.share_success = page.locator(".successfull-container")

    # --- Player methods ---

    def wait_for_stream_loaded(self, timeout: int = 120000):
        """Wait for the CircularProgress loader to disappear."""
        try:
            self.loader.first.wait_for(state="visible", timeout=5000)
        except Exception:
            pass  # Loader may have already finished
        self.loader.wait_for(state="hidden", timeout=timeout)

    def is_streaming(self) -> bool:
        """Return True if video appears to be streaming (no loader, no error)."""
        loader_hidden = self.loader.count() == 0 or not self.loader.first.is_visible()
        no_failure = self.streaming_failed.count() == 0
        return loader_hidden and no_failure

    def is_live_mode(self) -> bool:
        """Return True if the player is in live streaming mode."""
        return self.live_indicator.count() > 0 and self.live_indicator.is_visible()

    def exit_fullscreen(self):
        """Click exit fullscreen button to return to the views grid."""
        self.exit_fullscreen_button.click()

    # --- Bookmarks panel methods ---

    def open_bookmarks_panel(self):
        """Open the bookmarks panel via the dots icon."""
        self.bookmarks_toggle.click()
        self.page.wait_for_timeout(1000)

    def close_bookmarks_panel(self):
        """Close the bookmarks panel via the dots icon (toggle)."""
        self.bookmarks_toggle.click()
        self.page.wait_for_timeout(500)

    def get_bookmark_count(self) -> int:
        """Return the number of bookmark items visible in the panel."""
        return self.bookmark_items.count()

    def has_bookmarks(self) -> bool:
        """Return True if at least one bookmark exists."""
        return self.bookmark_items.count() > 0

    def play_bookmark(self, index: int = 0):
        """Click a bookmark to play it."""
        self.bookmark_items.nth(index).click()
        self.page.wait_for_timeout(2000)

    def open_bookmark_options(self, index: int = 0):
        """Open the 3-dot options menu on a specific bookmark."""
        option_icon = self.bookmark_items.nth(index).locator("img[src*='media/optionIcon']")
        option_icon.click()
        self.bookmark_options.first.wait_for(state="visible", timeout=5000)

    # --- Bookmark operations ---

    def export_bookmark(self, index: int = 0, filename: str = None):
        """Export a bookmark via the options menu."""
        if filename is None:
            filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        self.open_bookmark_options(index)
        self.bookmark_options.nth(1).click()
        self.page.wait_for_timeout(1000)

        self.export_popup.wait_for(state="visible", timeout=10000)
        self.export_filename_input.fill(filename)
        self.export_save_to_media_toggle.click()
        self.export_button.click()

        self.export_progress_bar.wait_for(state="visible", timeout=10000)
        self.export_progress_bar.wait_for(state="hidden", timeout=120000)

    def share_bookmark(self, index: int = 0, email: str = "test@example.com",
                       filename: str = None):
        """Share a bookmark via the options menu."""
        if filename is None:
            filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        self.open_bookmark_options(index)
        self.bookmark_options.nth(2).click()
        self.page.wait_for_timeout(1000)

        self.share_popup.wait_for(state="visible", timeout=10000)
        self.share_email_input.fill(email)
        self.share_filename_input.fill(filename)
        self.share_save_to_media_toggle.click()
        self.share_button.click()

        self.share_success.wait_for(state="visible", timeout=30000)

    def rename_bookmark(self, index: int = 0, new_name: str = None) -> str:
        """Rename a bookmark via the options menu. Returns the new name."""
        if new_name is None:
            new_name = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        self.open_bookmark_options(index)
        self.bookmark_options.nth(0).click()
        self.page.wait_for_timeout(500)

        self.rename_input.wait_for(state="visible", timeout=5000)
        self.rename_input.fill("")
        self.rename_input.fill(new_name)
        self.save_button.click()

        self.page.wait_for_timeout(2000)
        return new_name

    def delete_bookmark(self, index: int = 0):
        """Delete a bookmark via the options menu with confirmation."""
        self.open_bookmark_options(index)
        self.bookmark_options.nth(3).click()
        self.page.wait_for_timeout(500)

        self.delete_confirm_button.click()

    def verify_bookmark_deleted(self, bookmark_name: str, timeout: int = 10000):
        """Verify a bookmark with the given name is no longer visible."""
        deleted_element = self.page.locator(f"text={bookmark_name}")
        deleted_element.wait_for(state="hidden", timeout=timeout)
