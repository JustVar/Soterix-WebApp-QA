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
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.media = MediaPage(self.page)
        self._cleanup_actions = []
        yield
        for action in reversed(self._cleanup_actions):
            try:
                action()
            except Exception as e:
                print(f"Cleanup: action failed: {e}")

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
    def test_clip_grouping(self):
        """Verify clips can be grouped into a folder.

        Selects a clip, clicks 'Group Clips', confirms to create
        a folder with the default name.
        """
        self._navigate_to_clips()
        self._skip_if_empty()

        self.media.select_clip_by_index(1)
        self.media.group_clips()

        # Folder cleanup is intentionally deferred to test_clip_move_to_folder
        # so the folder is available for the move operation.
        self.media.click_tab("Clips")

    # --- Clip rename ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_rename(self):
        """Verify a clip can be renamed via the options menu."""
        self._navigate_to_clips()
        self._skip_if_empty()

        self.media.rename_item("Renamed clip")

        def _cleanup_rename():
            self._navigate_to_clips()
            if not self.media.is_page_empty(timeout=5000):
                self.media.rename_item("Clip")

        self._cleanup_actions.append(_cleanup_rename)

    # --- Clip delete ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_delete(self):
        """Verify a clip can be deleted via the options menu."""
        self._navigate_to_clips()
        self._skip_if_empty()

        self.media.delete_item()

    # --- Clip move to folder ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_move_to_folder(self):
        """Verify a clip can be moved to an existing folder.

        Uses the folder created by test_clip_grouping (no cleanup there).
        Cleans up the folder after the move.
        """
        self._navigate_to_clips()
        self._skip_if_empty()

        self.media.select_clip_by_index(1)
        moved = self.media.move_clip_to_folder()
        if not moved:
            pytest.skip("No folders available to move clip into")

        def _cleanup_folder():
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Folders")
            if not self.media.is_page_empty(timeout=5000):
                self.media.delete_item()

        self._cleanup_actions.append(_cleanup_folder)

    # --- Clip create link ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_create_link(self):
        """Verify a shareable link can be created for a clip.

        Cleanup: N/A -- no delete-link method available in page object.
        """
        self._navigate_to_clips()
        self._skip_if_empty()

        self.media.create_link_for_item()

    # --- Vault operations ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_add_clip_to_vault(self):
        """Verify a clip can be added to the Vault."""
        self._navigate_to_clips()
        self._skip_if_empty()

        self.media.add_to_vault()
        self._cleanup_actions.append(lambda: self.media.remove_from_vault())

    @pytest.mark.ui
    @pytest.mark.media
    def test_remove_clip_from_vault(self):
        """Verify a clip can be removed from the Vault."""
        self._navigate_to_clips()
        self._skip_if_empty()

        # The 'Remove from Vault' icon only appears for items already in vault
        remove_icon = self.page.locator("img[alt='Remove from Vault']")
        if remove_icon.count() == 0:
            pytest.skip("No clips in vault - 'Remove from Vault' icon not found")

        self.media.remove_from_vault()


class TestMediaFolderOperations:
    """Tests for folder-level operations on the Media page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.media = MediaPage(self.page)
        self._cleanup_actions = []
        yield
        for action in reversed(self._cleanup_actions):
            try:
                action()
            except Exception as e:
                print(f"Cleanup: action failed: {e}")

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
    def test_folder_delete(self):
        """Verify a folder can be deleted via the options menu."""
        self._navigate_to_folders()
        self._skip_if_empty()

        self.media.delete_item()

    # --- Folder create link ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_folder_create_link(self):
        """Verify a shareable link can be created for a folder.

        Cleanup: N/A -- no delete-link method available in page object.
        """
        self._navigate_to_folders()
        self._skip_if_empty()

        self.media.create_link_for_item()

    # --- Folder vault ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_add_folder_to_vault(self):
        """Verify a folder can be added to the Vault."""
        self._navigate_to_folders()
        self._skip_if_empty()

        self.media.add_to_vault()
        self._cleanup_actions.append(lambda: self.media.remove_from_vault())

    @pytest.mark.ui
    @pytest.mark.media
    def test_remove_folder_from_vault(self):
        """Verify a folder can be removed from the Vault."""
        self._navigate_to_folders()
        self._skip_if_empty()

        # The 'Remove from Vault' icon only appears for items already in vault
        remove_icon = self.page.locator("img[alt='Remove from Vault']")
        if remove_icon.count() == 0:
            pytest.skip("No folders in vault - 'Remove from Vault' icon not found")

        self.media.remove_from_vault()

    # --- Folder share ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_folder_share(self):
        """Verify a folder can be shared via email.

        Cleanup: N/A -- no unshare method available in page object.
        """
        self._navigate_to_folders()
        self._skip_if_empty()

        self.media.share_folder("test@example.com")

    # --- Folder export ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_folder_export(self):
        """Verify a folder can be exported."""
        self._navigate_to_folders()
        self._skip_if_empty()

        self.media.export_folder()
