"""Admin Sites tests - navigation, search, view toggle, status, versions,
camera sorting, camera group CRUD."""
import datetime
import re

import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.pages.admin_page import AdminPage


class TestAdminSites:
    """Tests for Admin > Sites section."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.admin = AdminPage(self.page)
        self._created_groups = []
        yield
        # Cleanup: delete created groups by name so runs do not leak
        # AutoTest groups into the shared tenant. Best effort: the
        # dropdown may already be closed when a test fails mid-flow.
        for group_name in self._created_groups:
            try:
                self.admin.open_groups_dropdown()
                if not self.admin.delete_camera_group_by_name(group_name):
                    print(f"Cleanup: group '{group_name}' not found")
            except Exception as e:
                print(f"Cleanup: could not delete '{group_name}': {e}")

    def _navigate_to_sites(self):
        """Helper to navigate to Admin > Sites."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_sites()

    def _appears(self, locator, timeout: int = 5000) -> bool:
        """Bounded wait for an optional element; False on timeout.

        Replaces instant count() checks that race the page render when
        deciding whether to skip.
        """
        try:
            locator.first.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def _open_first_site(self):
        """Click the first real site card, or skip when none is present.

        Site cards are identified structurally: the card header holds the
        site name paragraph next to an Options icon. A text exclusion list
        rots as the sidebar grows new entries - the old list let this
        helper click the sidebar's Dashboard entry (caught in trace,
        2026-08-07).
        """
        headers = self.page.locator(
            "*:has(> p.MuiTypography-root):has(img[alt='Options'])"
        )
        try:
            headers.first.wait_for(state="visible", timeout=10000)
        except Exception:
            pytest.skip("No site cards found on the Sites page")
        name = headers.first.locator("p.MuiTypography-root").first.inner_text().strip()
        if not name:
            pytest.skip("Site card has no readable name")
        self.admin.click_site(name)

    def _skip_if_redesigned_detail(self):
        """Legacy drift guard kept for test_camera_sorting only.

        Its 'Add Devices' marker no longer renders on the current
        detail page, so this never skips; the sorting test still
        exits honestly on its own sort-icon check. The other detail
        tests were rebuilt against the current layout and no longer
        call this.
        """
        try:
            self.page.get_by_text("Add Devices").first.wait_for(
                state="visible", timeout=3000
            )
            redesigned = True
        except Exception:
            redesigned = False
        if redesigned:
            pytest.skip(
                "Site detail page changed again (Add Devices layout) - "
                "the sorting test targets the current layout"
            )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_navigate_to_admin_sites(self):
        """Verify navigating to Admin > Sites loads the site list."""
        self._navigate_to_sites()

        expect(self.admin.sites_tab.first).to_be_visible(timeout=10000)
        # Verify Sites content loaded - look for site cards or search
        site_content = self.page.locator(
            "input[placeholder*='Search'], img[alt='Online'], img[alt='Offline']"
        ).first
        expect(site_content).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_search_site(self):
        """Verify the search input filters sites by name."""
        self._navigate_to_sites()

        # Search for the configured site's first word, never a
        # hardcoded name (the tenant renames sites)
        site_term = config.get("test_site_name", "site").split()[0]
        self.admin.search_site(site_term)

        search_field = self.page.locator(
            "input[placeholder*='Search']"
        ).first
        expect(search_field).to_have_value(site_term)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_toggle_grid_list_view(self):
        """Verify toggling between grid and list view on the Sites page."""
        self._navigate_to_sites()

        # Toggle to list view
        if self._appears(self.admin.list_view_toggle):
            self.admin.toggle_to_list_view()

        # Toggle back to grid view
        if self._appears(self.admin.grid_view_toggle):
            self.admin.toggle_to_grid_view()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_check_site_status(self):
        """Verify sites display Online/Offline status indicators."""
        self._navigate_to_sites()

        # Wait for the first indicator; get_site_statuses reads counts once
        if not self._appears(self.admin.online_status_icons) and \
                not self._appears(self.admin.offline_status_icons, timeout=2000):
            pytest.fail("No site status indicators found")

        statuses = self.admin.get_site_statuses()
        assert statuses[0]["total"] > 0, "No site status indicators found"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_site_versions(self):
        """Verify sites display version information."""
        self._navigate_to_sites()

        # Wait for version text; get_site_versions reads counts once
        version_elements = self.page.locator("p:has-text('Version:')")
        assert self._appears(version_elements, timeout=10000), \
            "No version info found on Sites page"

        versions = self.admin.get_site_versions()
        assert len(versions) > 0, "No version info found on Sites page"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_navigate_to_online_site(self):
        """Verify clicking a site card navigates into the site detail view."""
        self._navigate_to_sites()

        if not self._appears(self.admin.online_status_icons):
            pytest.skip("No online sites found")

        self._open_first_site()

        # click_site already waited for the Groups label; the
        # independent proof of navigation is the LIST unmounting -
        # its per-site 'Version:' lines exist only there
        expect(self.page.get_by_text("Groups:", exact=True).first)\
            .to_be_visible(timeout=10000)
        expect(
            self.page.locator("p:has-text('Version:')")
        ).to_have_count(0, timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_camera_sorting(self):
        """Verify A-Z and Z-A camera sorting within a site."""
        self._navigate_to_sites()

        # Navigate into a site first
        if not self._appears(self.admin.online_status_icons):
            pytest.skip("No online sites to test camera sorting")

        self._open_first_site()
        self._skip_if_redesigned_detail()

        # Sort A-Z
        if not self._appears(self.admin.sort_az_icon):
            pytest.skip("Sort icons not found in site detail")

        self.admin.click_sort_az()
        names_az = self.admin.get_camera_names()
        assert names_az, (
            "Sort ran but no camera names were read from the detail list"
        )

        # Sort Z-A
        self.admin.click_sort_za()
        names_za = self.admin.get_camera_names()

        # Verify sorting order differs
        if len(names_az) > 1:
            assert names_az != names_za, (
                "A-Z and Z-A sort returned same order"
            )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_create_camera_group(self):
        """Verify creating a new camera group with camera selection."""
        self._navigate_to_sites()
        self._open_first_site()

        # Group management lives in the Groups dropdown since 2026-08.
        # click_site already failed loud if the detail (and its Groups
        # label) never rendered, so no skip guard belongs here.
        self.admin.open_groups_dropdown()

        timestamp = datetime.datetime.now().strftime("%H%M%S")
        group_name = f"AutoTest Group {timestamp}"
        self._created_groups.append(group_name)

        # Search term for cameras to add: the configured camera name,
        # never a hardcoded vendor name (the tenant renames cameras)
        camera_search = config.get("test_camera_name", "camera")
        self.admin.create_camera_group(group_name, camera_search=camera_search)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_edit_camera_group(self):
        """Verify editing a camera group name."""
        self._navigate_to_sites()
        self._open_first_site()

        # Group management lives in the Groups dropdown since 2026-08.
        # click_site already failed loud if the detail (and its Groups
        # label) never rendered, so no skip guard belongs here.
        self.admin.open_groups_dropdown()

        # Create our own group and rename THAT: renaming the last
        # existing group mutates team-owned data on the shared tenant
        timestamp = datetime.datetime.now().strftime("%H%M%S")
        group_name = f"AutoTest Group {timestamp}"
        self._created_groups.append(group_name)
        camera_search = config.get("test_camera_name", "camera")
        self.admin.create_camera_group(group_name, camera_search=camera_search)

        self.admin.open_groups_dropdown()
        new_name = f"AutoTest Edited {timestamp}"
        self._created_groups.append(new_name)
        assert self.admin.edit_camera_group_by_name(group_name, new_name), (
            f"Created group '{group_name}' not found for rename"
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_delete_camera_group(self):
        """Verify deleting a camera group with Yes confirmation."""
        self._navigate_to_sites()
        self._open_first_site()

        # Group management lives in the Groups dropdown since 2026-08.
        # click_site already failed loud if the detail (and its Groups
        # label) never rendered, so no skip guard belongs here.
        self.admin.open_groups_dropdown()

        # Create our own group and delete THAT: deleting the last
        # existing group destroys team-owned data on the shared tenant
        timestamp = datetime.datetime.now().strftime("%H%M%S")
        group_name = f"AutoTest Group {timestamp}"
        camera_search = config.get("test_camera_name", "camera")
        self.admin.create_camera_group(group_name, camera_search=camera_search)

        self.admin.open_groups_dropdown()
        assert self.admin.delete_camera_group_by_name(group_name), (
            f"Created group '{group_name}' not found for delete"
        )

        # The named row leaving the list is the delete signal
        expect(
            self.page.get_by_text(group_name, exact=True)
        ).to_have_count(0, timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_search_inside_site(self):
        """Verify searching for cameras within a site detail view.

        The redesigned detail lists cameras as name + IP rows with a
        per-camera panel. Searching the configured camera's full name
        must leave exactly its row.
        """
        site_name = config.get("test_site_name", "")
        camera = config.get("test_camera_name", "")
        if not site_name or not camera:
            pytest.skip(
                "test_site_name / test_camera_name not configured "
                "for this ENV (see config/env/)"
            )

        self._navigate_to_sites()
        if not self._appears(self.page.locator(
                f"p.MuiTypography-root:text-is('{site_name}')")):
            pytest.skip(f"Site '{site_name}' not on the Sites page")
        self.admin.click_site(site_name)

        # Camera rows render async after the detail marker; each row
        # carries an 'IP: <addr>' line, unlike the panel's bare 'IP:'.
        # The baseline count settles over two matching reads so a
        # half-hydrated list cannot seed it.
        ip_rows = self.page.get_by_text(re.compile(r"IP: \d"))
        expect(ip_rows.first).to_be_visible(timeout=15000)
        row_count = ip_rows.count()
        for _ in range(8):
            self.page.wait_for_timeout(250)  # settle tick, not a blind sleep
            now = ip_rows.count()
            if now == row_count:
                break
            row_count = now

        if row_count < 2:
            pytest.skip(
                "Site lists fewer than two cameras - the filter "
                "count oracle cannot discriminate a dead search"
            )

        self.admin.search_inside_site(camera)

        # The full unique name filters to exactly one row: the count
        # settling at 1 is the filter-applied signal, and the name
        # check pins WHICH row survived
        expect(ip_rows).to_have_count(1, timeout=10000)
        expect(
            self.page.get_by_text(camera, exact=True).first
        ).to_be_visible(timeout=10000)

        # Clearing restores the list
        self.admin.search_inside_site("")
        expect(ip_rows).to_have_count(row_count, timeout=10000)
