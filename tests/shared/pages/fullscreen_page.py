"""Full Screen Video Player Page Object Model.

Models the full screen overlay that appears when zooming into a single
video tile. Includes player controls, bookmark panel, and export/share
dialogs.
"""
import datetime
import re
import time

from playwright.sync_api import Error as PlaywrightError, Page, expect

# The player's media element, re-queried on every poll so a re-mounted
# element (the refresh link swaps the blob src) still counts. Where
# several tiles keep a video mounted, the one filling the most screen
# is the full screen player (probed 08/25/2026: one video.player at
# 1280x720, readyState 4, currentTime +1.6s per 1.5s sample).
_PLAYER_VIDEO_JS = """
    () => {
        const area = v => { const r = v.getBoundingClientRect(); return r.width * r.height; };
        const vids = Array.from(document.querySelectorAll('video.player'))
            .filter(v => v.getClientRects().length)
            .sort((a, b) => area(b) - area(a));
        return vids[0] || null;
    }
"""
_VIDEO_STATE_JS = f"""
    () => {{
        const pick = {_PLAYER_VIDEO_JS};
        const v = pick();
        return {{
            count: document.querySelectorAll('video.player').length,
            ready: v ? v.readyState : 0,
            t: v ? v.currentTime : 0,
        }};
    }}
"""
_VIDEO_PLAYING_JS = f"""
    (t0) => {{
        const pick = {_PLAYER_VIDEO_JS};
        const v = pick();
        return !!v && v.readyState >= 3 && v.currentTime > t0;
    }}
"""


class FullScreenPage:
    """Page object for the full screen video player and bookmarks panel."""

    def __init__(self, page: Page):
        self.page = page

        # Player controls
        self.video_container = page.locator("[class*='video_container'][class*='new_video_player']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.fullscreen_button = page.locator("img[src*='media/Zoom.']")
        # exitFullScreen appears twice in DOM - hidden one in sidebar, visible one in .top_container
        self.exit_fullscreen_button = page.locator(".top_container img[src*='exitFullScreen']")
        self.loader = page.locator(".MuiCircularProgress-root")
        self.streaming_failed = page.locator("text=failed to load")
        # the player's <video>; the grid tile paints a canvas and keeps
        # its video at readyState 0, so the playing oracle below is for
        # full screen only (probed 08/25/2026)
        self.video = page.locator("video.player")
        # the camera name in the player's top bar (probed 08/25/2026:
        # .top_container > .box1 > .box holds 'main gate')
        self.camera_name_box = page.locator(".top_container .box")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.live_indicator = page.locator("img[src*='media/Live.']")

        # Timeline/playback controls (different icons in live vs archive mode)
        # In LIVE mode: pause-disable-mode icons (disabled)
        # In ARCHIVE mode: play/pause icons (active)
        self.pause_icon_live = page.locator("img[src*='media/pause-disable-mode']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.pause_icon_archive = page.locator("img[src*='media/pause-icon']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.play_icon = page.locator("img[src*='media/play']").first

        # Bottom control bar
        self.control_container = page.locator(".control_Container")
        self.bottom_controls = page.locator(".bottom-control-group")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.volume_control = page.locator("img[src*='media/volumn']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.share_icon = page.locator(".bottom-control-group img[src*='media/icon-share']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.settings_icon = page.locator("img[src*='media/Setting']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
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
            pass
        # every spinner must clear: a bare wait on the union is a
        # strict-mode violation when two spinners overlap (a tile
        # placeholder plus the player's), so wait on the count
        try:
            expect(self.loader).to_have_count(0, timeout=timeout)
        except AssertionError:
            # Name where the spinner lives so a spinner outside the
            # player (a list loading below the fold) reads as such
            print(f"[FULLSCREEN] spinner(s) still present after {timeout / 1000:.0f}s: "
                  f"{self._spinner_homes()}")
            raise

    def _spinner_homes(self) -> list:
        """The nearest classed ancestors of every spinner: a diagnostic
        for the loader wait, so its failure names the spinner's home."""
        try:
            return self.loader.evaluate_all("""els => els.map(el => {
                const chain = [];
                let node = el.parentElement;
                while (node && chain.length < 4) {
                    if (node.className && typeof node.className === 'string') {
                        chain.push(node.className.split(' ').slice(0, 2).join('.'));
                    }
                    node = node.parentElement;
                }
                const r = el.getBoundingClientRect();
                return chain.join(' < ') + ` @${Math.round(r.x)},${Math.round(r.y)}`;
            })""")
        # the diagnostic must not mask the wait's own failure
        except Exception as exc:  # noqa: BLE001
            return [f"unreadable: {str(exc)[:80]}"]

    def assert_stream_playing(self, timeout_ms: int = 30000) -> None:
        """Fail unless the player's video is really playing.

        The loader clearing only proves the spinner left: the tenant's
        stream can stay black, or raise the failure overlay, with no
        spinner up. Playing is the media element's own word: readyState
        >= 3 (a frame decoded and more buffered) and currentTime past a
        first sample. The failure names the camera, both samples, and
        the overlay text when it is up - that text is what
        run.py --retry-streams matches, so a dead stream with no
        overlay never reruns.
        """
        started = time.monotonic()
        first = self._video_state()
        try:
            self.page.wait_for_function(
                _VIDEO_PLAYING_JS, arg=first["t"], timeout=timeout_ms
            )
        except PlaywrightError:
            last = self._video_state()
            overlay = ""
            try:
                if (self.streaming_failed.count()
                        and self.streaming_failed.first.is_visible()):
                    overlay = "; the player shows 'The camera failed to load'"
            # the overlay read only decorates the message
            except PlaywrightError:
                pass
            raise AssertionError(
                f"[PLAYER] stream never played for camera "
                f"'{self.player_camera_name()}' within {timeout_ms / 1000:.0f}s: "
                f"readyState {first['ready']} -> {last['ready']}, "
                f"currentTime {first['t']:.2f} -> {last['t']:.2f}, "
                f"{last['count']} video element(s){overlay}"
            ) from None
        last = self._video_state()
        print(f"[PLAYER] stream playing for '{self.player_camera_name()}' "
              f"after {time.monotonic() - started:.1f}s: readyState "
              f"{last['ready']}, currentTime {first['t']:.2f} -> {last['t']:.2f}")

    def _video_state(self) -> dict:
        """One read of the player video: element count, readyState,
        currentTime. Zeros when no video is on screen."""
        return self.page.evaluate(_VIDEO_STATE_JS)

    def player_camera_name(self) -> str:
        """The camera name the player's top bar shows; the configured
        test camera when the bar is not readable."""
        try:
            names = [t.strip() for t in self.camera_name_box.all_inner_texts()]
            names = [n for n in names if n]
            if names:
                return names[0]
        # a torn-down page still gets a named failure
        except PlaywrightError:
            pass
        from config.base_config import config
        return config.get("test_camera_name") or "unknown camera"

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
        # The failure overlay ('The camera failed to load') sits over
        # the controls and intercepts the toggle click - two runs on
        # 08/24/2026 died exactly there. Its refresh link is the
        # user-path recovery; a stream that stays failed raises a
        # clear error instead of a click timeout.
        self.recover_stream_if_failed()
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
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
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
        # one last read closes the final-tick race: a completion landing
        # during the last poll sleep must not read as a timeout - and the
        # diagnostic below derives from this same read, so the message
        # can never contradict the decision
        signal = self._export_completion_signal()
        if signal:
            print(f"[EXPORT] completed in {elapsed:.0f}s ({signal})")
            return
        raise TimeoutError(
            f"[EXPORT] no completion signal after {elapsed:.0f}s "
            "(progress bar still visible or unreadable, no success toast)"
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
        # either element can detach between reads; '' = not complete
        # yet (see docstring)
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
