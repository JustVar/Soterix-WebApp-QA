"""Media page clip and folder operation tests.

The Media list renders item names as inline text inputs (invisible
to text engines), with per-row action icons always visible in list
view. Vaulting MOVES a row between the Clips/Folders list and the
Vault tab. The rename success toast is the server acknowledgment -
the inline input updates optimistically and can show a rename that
never committed (all measured 08/12/2026).

Destructive operations on shared-tenant media (clip delete, folder
delete, grouping, and move to folder - grouping and moving relocate
the team's clips) stay skipped until the folder-delete semantics
are measured: whether deleting a folder deletes the clips inside
it. See the register.
"""
import pytest
from playwright.sync_api import expect

from tests.shared.pages.media_page import MediaPage

DESTRUCTIVE_SKIP = (
    "Operates on shared-tenant media with unmeasured delete semantics "
    "(does deleting a folder delete its clips?) - held until measured; "
    "see docs/TEST_REPAIRS.md"
)


class TestMediaClipOperations:
    """Tests for clip-level operations on the Media page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.media = MediaPage(self.page)
        self._cleanup_actions = []
        yield
        # Loud teardown: a restore that fails leaves the shared
        # tenant modified, which must surface as an error, not a print
        errors = []
        for action in reversed(self._cleanup_actions):
            try:
                action()
            except Exception as e:
                errors.append(str(e))
        if errors:
            raise RuntimeError(
                "Tenant restore failed: " + "; ".join(errors)
            )

    def _first_clip_or_skip(self) -> str:
        """Land on the Clips tab and return the first clip's name."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")
        if self.media.is_page_empty(timeout=5000):
            pytest.skip("No clips available in Media - cannot test operation")
        names = self.media.item_names()
        if not names:
            # A persisted grid view hides the inline name inputs;
            # one list-view flip self-heals before failing
            if self.media.list_view_button.is_visible():
                self.media.switch_to_list_view()
                names = self.media.item_names()
        if not names:
            pytest.fail(
                "Clips tab has content but no name inputs were read - "
                "the inline-input name pattern changed"
            )
        return names[0]

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_grouping(self):
        """Group clips into a folder (held: relocates team clips)."""
        pytest.skip(DESTRUCTIVE_SKIP)

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_rename(self):
        """Rename a clip and rename it back, verifying each commit.

        Round-trip: the shared tenant keeps its clip names. The
        success toast is the oracle for each direction (the inline
        value updates optimistically, so the attribute expects only
        confirm the optimistic render); the reload at the end is
        what proves both renames reached the server.
        """
        original = self._first_clip_or_skip()
        temp = f"{original}_t"

        def _restore():
            # A page load spends its one rename (known app behavior);
            # a hard reload re-arms it before the restore rename
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Clips")
            if temp in self.media.item_names():
                self.media.rename_item(temp, original)

        self._cleanup_actions.append(_restore)

        self.media.rename_item(original, temp)

        # The hard reload re-arms the rename (only one commits per
        # page load - measured, see Known app behavior) and proves
        # rename #1 reached the server
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")
        names = self.media.item_names()
        assert temp in names and original not in names, (
            f"Rename did not persist through reload: {names}"
        )

        self.media.rename_item(temp, original)

        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")
        names = self.media.item_names()
        assert original in names and temp not in names, (
            f"Rename back did not persist: {names}"
        )

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_delete(self):
        """Delete a clip (held: destroys shared-tenant media)."""
        pytest.skip(DESTRUCTIVE_SKIP)

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_move_to_folder(self):
        """Move a clip into a folder (held: relocates team clips)."""
        pytest.skip(DESTRUCTIVE_SKIP)

    @pytest.mark.ui
    @pytest.mark.media
    def test_clip_create_link(self):
        """Verify the Create Link dialog opens for a clip.

        The dialog is cancelled so no orphan link is left behind
        (there is no delete-link flow to clean one up).
        """
        name = self._first_clip_or_skip()
        self.media.open_create_link_dialog(name)

        # The helper raised on 'Add Link Name'; the new information
        # here is the rest of the dialog
        expect(self.page.get_by_text("Set Expiration").first)\
            .to_be_visible()
        expect(self.page.get_by_text("Duration:").first).to_be_visible()

        self.media.cancel_dialog()
        # Hidden, not count-0: this app keeps dialogs mounted in the
        # DOM after close
        expect(self.page.get_by_text("Add Link Name").first)\
            .to_be_hidden()

    @pytest.mark.ui
    @pytest.mark.media
    def test_add_clip_to_vault(self):
        """Vault a clip: its row moves from Clips to the Vault tab."""
        name = self._first_clip_or_skip()

        def _restore():
            # The page-load cache hides fresh vault state (known app
            # behavior); reload before reading it
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Vault")
            names = set(self.media.item_names())
            self.page.wait_for_timeout(1000)  # vault fetch settles
            names |= set(self.media.item_names())
            if name in names:
                self.media.remove_from_vault(name)

        self._cleanup_actions.append(_restore)

        self.media.add_to_vault(name)

        # The page-load cache keeps the Vault tab stale (known app
        # behavior); the reload makes its listing the real oracle
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")
        expect(self.page.locator(f"input[value='{name}']"))\
            .to_have_count(1, timeout=10000)

    @pytest.mark.ui
    @pytest.mark.media
    def test_remove_clip_from_vault(self):
        """Un-vault a clip: its row returns to the Clips tab.

        Self-sufficient: vaults a clip first, so the tenant needs no
        pre-vaulted state.
        """
        name = self._first_clip_or_skip()

        def _restore():
            # The page-load cache hides fresh vault state (known app
            # behavior); reload before reading it
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Vault")
            names = set(self.media.item_names())
            self.page.wait_for_timeout(1000)  # vault fetch settles
            names |= set(self.media.item_names())
            if name in names:
                self.media.remove_from_vault(name)

        self._cleanup_actions.append(_restore)
        self.media.add_to_vault(name)

        # Reload: the page-load cache keeps the Vault tab stale
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")
        expect(self.page.locator(f"input[value='{name}']"))\
            .to_have_count(1, timeout=10000)

        self.media.remove_from_vault(name)

        # Reload again: the flag-cleared proof is the fresh Vault
        # listing without the name, with the clip still in Clips
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")
        assert name not in self.media.item_names(), (
            f"'{name}' still listed in the Vault after removal"
        )
        self.media.click_tab("Clips")
        expect(self.page.locator(f"input[value='{name}']"))\
            .to_have_count(1, timeout=10000)


class TestMediaFolderOperations:
    """Tests for folder-level operations on the Media page.

    Folder rows are assumed to use the same inline name inputs as
    clips; the tenant had no folders when this was measured, so the
    first folder run adjudicates that assumption.
    """

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.media = MediaPage(self.page)
        self._cleanup_actions = []
        yield
        # Loud teardown: a restore that fails leaves the shared
        # tenant modified, which must surface as an error, not a print
        errors = []
        for action in reversed(self._cleanup_actions):
            try:
                action()
            except Exception as e:
                errors.append(str(e))
        if errors:
            raise RuntimeError(
                "Tenant restore failed: " + "; ".join(errors)
            )

    def _first_folder_or_skip(self) -> str:
        """Land on the Folders tab and return the first folder's name."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Folders")
        if self.media.is_page_empty(timeout=5000):
            pytest.skip("No folders in Media - cannot test operation")
        names = self.media.item_names()
        if not names:
            pytest.fail(
                "Folders tab has content but no name inputs were read - "
                "folder rows do not use the inline-input name pattern"
            )
        return names[0]

    @pytest.mark.ui
    @pytest.mark.media
    def test_folder_delete(self):
        """Delete a folder (held: unmeasured delete semantics)."""
        pytest.skip(DESTRUCTIVE_SKIP)

    @pytest.mark.ui
    @pytest.mark.media
    def test_folder_create_link(self):
        """Verify the Create Link dialog opens for a folder.

        Cancelled so no orphan link is left behind.
        """
        name = self._first_folder_or_skip()
        self.media.open_create_link_dialog(name)

        # The helper raised on 'Add Link Name'; assert further fields
        expect(self.page.get_by_text("Set Expiration").first)\
            .to_be_visible()

        self.media.cancel_dialog()
        # Hidden, not count-0: this app keeps dialogs mounted in the
        # DOM after close
        expect(self.page.get_by_text("Add Link Name").first)\
            .to_be_hidden()

    @pytest.mark.ui
    @pytest.mark.media
    def test_add_folder_to_vault(self):
        """Vault a folder: its row moves to the Vault tab."""
        name = self._first_folder_or_skip()

        def _restore():
            # The page-load cache hides fresh vault state (known app
            # behavior); reload before reading it
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Vault")
            names = set(self.media.item_names())
            self.page.wait_for_timeout(1000)  # vault fetch settles
            names |= set(self.media.item_names())
            if name in names:
                self.media.remove_from_vault(name)

        self._cleanup_actions.append(_restore)

        self.media.add_to_vault(name)

        # The page-load cache keeps the Vault tab stale (known app
        # behavior); the reload makes its listing the real oracle
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")
        expect(self.page.locator(f"input[value='{name}']"))\
            .to_have_count(1, timeout=10000)

    @pytest.mark.ui
    @pytest.mark.media
    def test_remove_folder_from_vault(self):
        """Un-vault a folder: its row returns to the Folders tab.

        Self-sufficient: vaults the folder first.
        """
        name = self._first_folder_or_skip()

        def _restore():
            # The page-load cache hides fresh vault state (known app
            # behavior); reload before reading it
            self.page.reload()
            self.media.navigate()
            self.media.select_date_filter("Last 30 Days")
            self.media.click_tab("Vault")
            names = set(self.media.item_names())
            self.page.wait_for_timeout(1000)  # vault fetch settles
            names |= set(self.media.item_names())
            if name in names:
                self.media.remove_from_vault(name)

        self._cleanup_actions.append(_restore)
        self.media.add_to_vault(name)

        # Reload: the page-load cache keeps the Vault tab stale
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")
        expect(self.page.locator(f"input[value='{name}']"))\
            .to_have_count(1, timeout=10000)

        self.media.remove_from_vault(name)

        # Reload again: the fresh Vault listing without the name is
        # the flag-cleared proof
        self.page.reload()
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")
        assert name not in self.media.item_names(), (
            f"'{name}' still listed in the Vault after removal"
        )
        self.media.click_tab("Folders")
        expect(self.page.locator(f"input[value='{name}']"))\
            .to_have_count(1, timeout=10000)

    @pytest.mark.ui
    @pytest.mark.media
    def test_folder_share(self):
        """Share a folder via email.

        The oracle lives in share_item: it raises when the success
        panel never appears.
        """
        name = self._first_folder_or_skip()
        self.media.share_item(name, "test@example.com")

    @pytest.mark.ui
    @pytest.mark.media
    def test_folder_export(self):
        """Export a folder; the export control leaving is the signal.

        The oracle lives in export_item: a stuck export control
        raises.
        """
        name = self._first_folder_or_skip()
        self.media.export_item(name)
