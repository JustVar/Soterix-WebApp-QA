"""Media page clip and folder operation tests.

Covers clip grouping, rename, delete, move to folder, create link,
vault add/remove, folder operations, and share/export.

Migrated from Selenium:
- test_media_clip_grouping (line 5972)
- test_media_move_clip_to_existing_folder (line 6014)
- test_media_delete_folder (line 6077)
- test_media_create_link_folder (line 6107)
- test_media_clip_rename (line 6138)
- test_media_clip_delete (line 6197)
- test_media_add_clip_to_vault (line 6224)
- test_media_remove_clip_from_vault (line 6250)
- test_media_create_link_clip (line 6282)
- test_media_add_folder_to_vault (line 6310)
- test_media_share_folder (line 6349)
- test_media_export_folder (line 6385)

Note: These operations require existing media content (clips/folders).
If the Media page is empty, clip/folder operations will be skipped.
"""
import pytest
from tests.shared.pages.media_page import MediaPage


class TestMediaClipOperations:
    """Tests for clip-level operations on the Media page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.media = MediaPage(self.page)
        self._cleanup_actions = []
        yield
        for action in reversed(self._cleanup_actions):
            try:
                action()
            except Exception:
                pass

    def _navigate_to_clips(self):
        """Navigate to Media page and switch to Clips tab."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")

    def _skip_if_empty(self):
        """Skip test if the current tab has no content."""
        if self.media.is_page_empty(timeout=5000):
            pytest.skip("No clips available in Media - cannot test operation")

    # --- Clip grouping ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("eJqXyg")
    def test_clip_grouping(self):
        """Verify clips can be grouped into a folder.

        Selects a clip, clicks 'Group Clips', confirms to create
        a folder with the default name.
        """
        self._navigate_to_clips()
        self._skip_if_empty()
        self.step_capture.mark(1, "Navigate to Media Clips tab and verify clips exist")

        self.media.select_clip_by_index(1)
        self.step_capture.mark(2, "Select a clip by index")

        self.media.group_clips()
        self.step_capture.mark(3, "Group selected clips into a folder")

        def _cleanup_folder():
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Folders")
            if not self.media.is_page_empty(timeout=5000):
                self.media.delete_item()

        self._cleanup_actions.append(_cleanup_folder)
        self.media.click_tab("Clips")

    # --- Clip rename ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("K4n9dr")
    def test_clip_rename(self):
        """Verify a clip can be renamed via the options menu."""
        self._navigate_to_clips()
        self._skip_if_empty()
        self.step_capture.mark(1, "Navigate to Media Clips tab and verify clips exist")

        self.media.rename_item("Renamed clip")
        self.step_capture.mark(2, "Rename the clip to 'Renamed clip'")

        def _cleanup_rename():
            self._navigate_to_clips()
            if not self.media.is_page_empty(timeout=5000):
                self.media.rename_item("Clip")

        self._cleanup_actions.append(_cleanup_rename)

    # --- Clip delete ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("jPnpWx")
    def test_clip_delete(self):
        """Verify a clip can be deleted via the options menu."""
        self._navigate_to_clips()
        self._skip_if_empty()
        self.step_capture.mark(1, "Navigate to Media Clips tab and verify clips exist")

        self.media.delete_item()
        self.step_capture.mark(2, "Delete the clip via options menu")

    # --- Clip move to folder ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("21zWE4")
    def test_clip_move_to_folder(self):
        """Verify a clip can be moved to an existing folder.

        Requires at least one folder to exist (created by clip grouping
        or another operation). Skips if no folders are available.
        Cleanup: N/A -- no move-back method available in page object.
        """
        self._navigate_to_clips()
        self._skip_if_empty()
        self.step_capture.mark(1, "Navigate to Media Clips tab and verify clips exist")

        self.media.select_clip_by_index(1)
        self.step_capture.mark(2, "Select a clip by index")

        moved = self.media.move_clip_to_folder()
        if not moved:
            pytest.skip("No folders available to move clip into")
        self.step_capture.mark(3, "Move the selected clip to an existing folder")

    # --- Clip create link ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("68lDR7")
    def test_clip_create_link(self):
        """Verify a shareable link can be created for a clip.

        Cleanup: N/A -- no delete-link method available in page object.
        """
        self._navigate_to_clips()
        self._skip_if_empty()
        self.step_capture.mark(1, "Navigate to Media Clips tab and verify clips exist")

        self.media.create_link_for_item()
        self.step_capture.mark(2, "Create a shareable link for the clip")

    # --- Vault operations ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("dyp4KK")
    def test_add_clip_to_vault(self):
        """Verify a clip can be added to the Vault."""
        self._navigate_to_clips()
        self._skip_if_empty()
        self.step_capture.mark(1, "Navigate to Media Clips tab and verify clips exist")

        self.media.add_to_vault()
        self.step_capture.mark(2, "Add the clip to the Vault")

        self._cleanup_actions.append(lambda: self.media.remove_from_vault())

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("gQxXl3")
    def test_remove_clip_from_vault(self):
        """Verify a clip can be removed from the Vault."""
        self._navigate_to_clips()
        self._skip_if_empty()
        self.step_capture.mark(1, "Navigate to Media Clips tab and verify clips exist")

        # The 'Remove from Vault' icon only appears for items already in vault
        remove_icon = self.page.locator("img[alt='Remove from Vault']")
        if remove_icon.count() == 0:
            pytest.skip("No clips in vault - 'Remove from Vault' icon not found")

        self.media.remove_from_vault()
        self.step_capture.mark(2, "Remove the clip from the Vault")


class TestMediaFolderOperations:
    """Tests for folder-level operations on the Media page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.media = MediaPage(self.page)
        self._cleanup_actions = []
        yield
        for action in reversed(self._cleanup_actions):
            try:
                action()
            except Exception:
                pass

    def _navigate_to_folders(self):
        """Navigate to Media page and switch to Folders tab."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Folders")

    def _skip_if_empty(self):
        """Skip test if the Folders tab has no content."""
        if self.media.is_page_empty(timeout=5000):
            pytest.skip("No folders in Media - cannot test operation")

    # --- Folder delete ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("xm9d51")
    def test_folder_delete(self):
        """Verify a folder can be deleted via the options menu."""
        self._navigate_to_folders()
        self._skip_if_empty()
        self.step_capture.mark(1, "Navigate to Media Folders tab and verify folders exist")

        self.media.delete_item()
        self.step_capture.mark(2, "Delete the folder via options menu")

    # --- Folder create link ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("Pgw9D6")
    def test_folder_create_link(self):
        """Verify a shareable link can be created for a folder.

        Cleanup: N/A -- no delete-link method available in page object.
        """
        self._navigate_to_folders()
        self._skip_if_empty()
        self.step_capture.mark(1, "Navigate to Media Folders tab and verify folders exist")

        self.media.create_link_for_item()
        self.step_capture.mark(2, "Create a shareable link for the folder")

    # --- Folder vault ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("bj0XG9")
    def test_add_folder_to_vault(self):
        """Verify a folder can be added to the Vault."""
        self._navigate_to_folders()
        self._skip_if_empty()
        self.step_capture.mark(1, "Navigate to Media Folders tab and verify folders exist")

        self.media.add_to_vault()
        self.step_capture.mark(2, "Add the folder to the Vault")

        self._cleanup_actions.append(lambda: self.media.remove_from_vault())

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("J8d93L")
    def test_remove_folder_from_vault(self):
        """Verify a folder can be removed from the Vault."""
        self._navigate_to_folders()
        self._skip_if_empty()
        self.step_capture.mark(1, "Navigate to Media Folders tab and verify folders exist")

        # The 'Remove from Vault' icon only appears for items already in vault
        remove_icon = self.page.locator("img[alt='Remove from Vault']")
        if remove_icon.count() == 0:
            pytest.skip("No folders in vault - 'Remove from Vault' icon not found")

        self.media.remove_from_vault()
        self.step_capture.mark(2, "Remove the folder from the Vault")

    # --- Folder share ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("Nj3r6e")
    def test_folder_share(self):
        """Verify a folder can be shared via email.

        Cleanup: N/A -- no unshare method available in page object.
        """
        self._navigate_to_folders()
        self._skip_if_empty()
        self.step_capture.mark(1, "Navigate to Media Folders tab and verify folders exist")

        self.media.share_folder("test@example.com")
        self.step_capture.mark(2, "Share the folder via email")

    # --- Folder export ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("21zWNl")
    def test_folder_export(self):
        """Verify a folder can be exported."""
        self._navigate_to_folders()
        self._skip_if_empty()
        self.step_capture.mark(1, "Navigate to Media Folders tab and verify folders exist")

        self.media.export_folder()
        self.step_capture.mark(2, "Export the folder")
