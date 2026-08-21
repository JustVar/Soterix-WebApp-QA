"""Full Screen Video Player Page Object Model.

Models the full screen overlay that appears when zooming into a single
video tile. Includes player controls, bookmark panel, and export/share
dialogs.
"""
import datetime
import re
import time

from playwright.sync_api import Error as PlaywrightError, Page, expect


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
        # export completion toast: the same .successfull-container the
        # share flow raises (share_success below); the export text filter
        # keeps an unrelated success toast from reading as completion
        self.export_success_toast = page.locator(".successfull-container").filter(
            has_text=re.compile(r"export", re.IGNORECASE)
        )

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
        # the loader may already have cleared; the count-zero expect
        # below is the oracle
        except Exception:
            pass  # Loader may have already finished
        # every spinner must clear: a bare wait on the union is a
        # strict-mode violation when two spinners overlap (a tile
        # placeholder plus the player's), so wait on the count
        expect(self.loader).to_have_count(0, timeout=timeout)

    def is_streaming(self) -> bool:
        """Return True if video appears to be streaming (no loader, no error)."""
        loader_hidden = self.loader.count() == 0 or not self.loader.first.is_visible()
        # visibility, not count: a recovered failure overlay can stay
        # mounted hidden
        no_failure = (self.streaming_failed.count() == 0
                      or not self.streaming_failed.first.is_visible())
        return loader_hidden and no_failure

    def recover_stream_if_failed(self, timeout: int = 60000) -> bool:
        """Click the failure overlay's refresh link when the player
        shows 'The camera failed to load'.

        The live player intermittently raises that overlay even with
        a live frame rendering behind it (measured 08/13/2026); the
        refresh link is the user-path recovery. Loose case-insensitive
        match because the link label is not stable ('Rafresh' on the
        current build). Returns True when a recovery click was made
        and the overlay left; raises if the overlay stays.
        """
        if (self.streaming_failed.count() == 0
                or not self.streaming_failed.first.is_visible()):
            return False
        refresh = self.page.get_by_text(
            re.compile(r"r.fresh", re.IGNORECASE)
        )
        if refresh.count() == 0:
            return False
        refresh.first.click()
        self.streaming_failed.first.wait_for(
            state="hidden", timeout=timeout
        )
        return True

    def is_live_mode(self) -> bool:
        """Return True if the player is in live streaming mode."""
        return self.live_indicator.count() > 0 and self.live_indicator.is_visible()

    def exit_fullscreen(self):
        """Click exit fullscreen button to return to the views grid."""
        self.exit_fullscreen_button.click()

    # --- Bookmarks panel methods ---

    def open_bookmarks_panel(self):
        """Open the bookmarks panel via the dots icon.

        The dots icon is a toggle: only click when no bookmark row is
        showing, or an open panel closes. The panel has no marker of
        its own besides its rows, and an empty panel is legitimate,
        so a bounded first-row wait is the open signal (a miss is not
        an error - callers check has_bookmarks).
        """
        if self.bookmark_items.count() and self.bookmark_items.first.is_visible():
            return
        self.bookmarks_toggle.click()
        try:
            self.bookmark_items.first.wait_for(state="visible", timeout=5000)
        # an empty panel renders no rows; callers decide via has_bookmarks
        except PlaywrightError:
            pass

    def close_bookmarks_panel(self):
        """Close the bookmarks panel via the dots icon (toggle); the
        rows leaving is the closed signal when any were showing."""
        # state read for the close signal: any visible row now
        first_row = self.bookmark_items.first
        had_rows = first_row.is_visible() if first_row.count() else False
        self.bookmarks_toggle.click()
        if had_rows:
            self.bookmark_items.first.wait_for(state="hidden", timeout=5000)

    def get_bookmark_count(self) -> int:
        """Return the number of bookmark items visible in the panel."""
        return self.bookmark_items.count()

    def has_bookmarks(self) -> bool:
        """Return True if at least one bookmark exists."""
        return self.bookmark_items.count() > 0

    def play_bookmark(self, index: int = 0):
        """Click a bookmark to navigate to its snapshot position.

        Flow: Click bookmark -> Navigate to timestamp -> Wait for stream to load
        """
        self.bookmark_items.nth(index).click()

        # the stream-loaded wait is the navigated signal
        self.wait_for_stream_loaded(timeout=30000)

    def open_bookmark_options(self, index: int = 0):
        """Open the 3-dot options menu on a specific bookmark."""
        option_icon = self.bookmark_items.nth(index).locator("img[src*='media/optionIcon']")
        option_icon.click()
        self.bookmark_options.first.wait_for(state="visible", timeout=5000)

    # --- Bookmark operations ---

    def export_bookmark(self, index: int = 0, filename: str = None):
        """Export a bookmark via the options menu.

        Completion is the export progress bar no longer visible; the
        success toast up at the same time is reported as the stronger
        signal. The toast alone never completes the wait: its text
        filter is a substring match, so a toast that only acknowledges
        the export request would read as completion while the bar still
        runs. In-suite tenant load made a 120s bar wait flaky (bar
        visible the full 120s on 08/21/2026 while manual export and a
        standalone run passed), so the wait polls up to 180s and prints
        the signal that fired and the elapsed time.
        """
        if filename is None:
            filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        self.open_bookmark_options(index)
        self.bookmark_options.nth(1).click()

        # the popup's own visible wait is the opened signal
        self.export_popup.wait_for(state="visible", timeout=10000)
        self.export_filename_input.fill(filename)
        self.export_save_to_media_toggle.click()
        self.export_button.click()
        started = time.monotonic()

        # the bar appearing proves the export started; an export can
        # finish before this wait samples the bar, so the success toast
        # already up also counts - bar-hidden alone does not, because a
        # bar that never appeared means the export never started
        try:
            self.export_progress_bar.wait_for(state="visible", timeout=10000)
        except PlaywrightError:
            if self._export_completion_signal() != "success toast":
                raise

        deadline = time.monotonic() + 180.0
        while time.monotonic() < deadline:
            signal = self._export_completion_signal()
            if signal:
                print(f"[EXPORT] completed in "
                      f"{time.monotonic() - started:.0f}s ({signal})")
                return
            self.page.wait_for_timeout(250)  # poll tick for bar-hidden or toast

        elapsed = time.monotonic() - started
        try:
            bar_visible = (self.export_progress_bar.count() > 0
                           and self.export_progress_bar.first.is_visible())
        # probe: the bar can detach between the count and visibility
        # reads; report that as not visible
        except PlaywrightError:
            bar_visible = False
        raise TimeoutError(
            f"[EXPORT] no completion signal after {elapsed:.0f}s (progress bar "
            f"{'still visible' if bar_visible else 'not visible'}, no success toast)"
        )

    def _export_completion_signal(self) -> str:
        """Return the export completion signal that is up, or ''.

        The bar no longer visible is the completion signal; the toast
        up at the same time upgrades the label. The toast never counts
        while the bar is still visible: its text filter is a substring
        match, so a toast that only acknowledges the export request
        would otherwise complete the poll mid-export. The probe
        swallows Playwright errors because either element can detach
        between the count and visibility reads; '' only means "not
        complete yet" to export_bookmark's poll, which re-reads on the
        next tick.
        """
        try:
            if (self.export_progress_bar.count()
                    and self.export_progress_bar.first.is_visible()):
                return ""
            if (self.export_success_toast.count()
                    and self.export_success_toast.first.is_visible()):
                return "success toast"
            return "progress bar hidden"
        except PlaywrightError:
            pass
        return ""

    def share_bookmark(self, index: int = 0, email: str = "test@example.com",
                       filename: str = None):
        """Share a bookmark via the options menu."""
        if filename is None:
            filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        self.open_bookmark_options(index)
        self.bookmark_options.nth(2).click()

        # the popup's own visible wait is the opened signal
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

        # the rename input's own visible wait is the opened signal
        self.rename_input.wait_for(state="visible", timeout=10000)
        self.rename_input.fill("")
        self.rename_input.fill(new_name)
        self.save_button.click()

        # the input leaving is the saved signal
        self.rename_input.wait_for(state="hidden", timeout=10000)
        return new_name

    def delete_bookmark(self, index: int = 0):
        """Delete a bookmark via the options menu with confirmation."""
        self.open_bookmark_options(index)
        self.bookmark_options.nth(3).click()

        # the confirm control's own wait is the dialog-open signal
        self.delete_confirm_button.wait_for(state="visible", timeout=10000)
        self.delete_confirm_button.click()

    def verify_bookmark_deleted(self, bookmark_name: str, timeout: int = 10000):
        """Verify a bookmark with the given name is no longer visible."""
        # Target the bookmark item container to avoid strict mode violations
        deleted_element = self.bookmark_items.filter(has_text=bookmark_name)
        deleted_element.wait_for(state="hidden", timeout=timeout)
