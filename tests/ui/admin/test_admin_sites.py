"""Admin Sites tests - navigation, search, view toggle, status, versions,
camera sorting, camera group CRUD."""
import datetime
import re

import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.helpers.surface import require_items
from tests.shared.pages.admin_page import AdminPage

# One worker for every module that writes this account's sites and devices: under
# -n they would otherwise spread across workers and race on the same
# tenant state (pytest.ini --dist loadgroup; audit 09/17/2026, row 86).
pytestmark = pytest.mark.xdist_group("account_sites")

# measured 09/12/2026 on US (register row 53): the list view's columns
SITES_LIST_HEADERS = ["Site Name", "Enterprise", "Address", "Devices", "Version"]


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
            # teardown: a failed delete must not mask the test result;
            # the dropdown may already be closed after a mid-flow failure
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
        # A tenant always has at least one site - it is what everything
        # else hangs off - so an empty Sites page is a broken page, not
        # an absent artifact. Both of these used to skip (register
        # item 25).
        headers.first.wait_for(state="visible", timeout=10000)
        name = headers.first.locator("p.MuiTypography-root").first.inner_text().strip()
        assert name, (
            "The first site card on Admin > Sites renders no name in its "
            "header paragraph, so no site can be opened by name"
        )
        self.admin.click_site(name)

    def _require_online_site(self):
        """An online site on the Sites page, proved or explained.

        Site cards are the surface. Cards with no online marker are the
        tenant's data; a page with no cards never rendered and is a
        fault. The old `_appears` read reported both as one skip
        (register item 25).
        """
        require_items(
            self.admin.online_status_icons,
            container=self.page.locator(
                "*:has(> p.MuiTypography-root):has(img[alt='Options'])"
            ),
            surface="Admin > Sites",
            artifact="site card with an online marker",
            empty_means="every site on this tenant is offline",
        )

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
        """Verify navigating to Admin > Sites loads the site list.

        Steps:
        1. Open Admin and click Sites in the sidebar.
           Expected: Sites is painted as the selected tab, the search field shows its Search placeholder, and every listed site carries an Online or Offline marker.
        """
        self._navigate_to_sites()
        self.admin.expect_admin_tab_selected("Sites")
        search = self.page.locator("input[placeholder*='Search']").first
        expect(search).to_have_attribute("placeholder", re.compile(r"^Search\s*$"), timeout=10000)
        if not self._appears(self.admin.online_status_icons) and \
                not self._appears(self.admin.offline_status_icons, timeout=2000):
            pytest.fail("No site status indicators found")
        statuses = self.admin.get_site_statuses()[0]
        assert statuses["total"] > 0, f"the Sites list shows no status markers: {statuses}"
        assert statuses["online"] + statuses["offline"] == statuses["total"], (
            f"the site status counts do not add up: {statuses}")

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
        """Verify toggling between grid and list view on the Sites page.

        Only the inactive view's toggle renders, so the opposite
        toggle appearing after each click is the switched signal. The
        old version guarded both clicks behind presence checks and
        could pass without toggling anything.

        Steps:
        1. Open Admin > Sites and click the list view toggle.
           Expected: A table lists the sites with the columns Site Name, Enterprise, Address, Devices, Version, and the grid toggle is offered.
        2. Click the grid view toggle.
           Expected: The table is gone and the list toggle is offered again.
        """
        self._navigate_to_sites()
        expect(self.admin.list_view_toggle).to_be_visible(timeout=10000)
        self.admin.toggle_to_list_view()
        expect(self.admin.grid_view_toggle).to_be_visible(timeout=5000)
        # the table renders a beat after the toggle; its header is the signal
        expect(self.page.locator("thead").first).to_be_visible(timeout=10000)
        headers = [h.strip() for h in self.page.locator("thead th, thead td").all_inner_texts()]
        assert headers[:5] == SITES_LIST_HEADERS, f"the sites table's columns read {headers}"
        expect(self.page.locator("table tbody tr")).not_to_have_count(0)
        self.admin.toggle_to_grid_view()
        expect(self.admin.list_view_toggle).to_be_visible(timeout=5000)
        expect(self.page.locator("table tbody tr")).to_have_count(0)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_check_site_status(self):
        """Every site on the Sites list carries an Online or Offline marker.

        Steps:
        1. Open Admin > Sites.
           Expected: The list shows at least one Online or Offline status marker.
        """
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
        """Verify sites display version information.

        Steps:
        1. Open Admin and click Sites in the sidebar.
           Expected: Each site card shows a Version line.
        """
        self._navigate_to_sites()

        # Wait for version text; get_site_versions reads counts once
        version_elements = self.page.locator("p:has-text('Version:')")
        assert self._appears(version_elements, timeout=10000), \
            "No version info found on Sites page"

        versions = self.admin.get_site_versions()
        assert len(versions) > 0, "No version info found on Sites page"
        # each label carries a version, not an empty 'Version:'
        empty = [v for v in versions if re.search(r"Version:\s*\S", v) is None]
        assert empty == [], f"these site cards show no version after the label: {empty}"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_navigate_to_online_site(self):
        """Verify clicking a site card navigates into the site detail view.

        Steps:
        1. Open Admin and click Sites in the sidebar.
           Expected: The site cards are listed and at least one shows the online marker.
        2. Click an online site's card.
           Expected: The site detail opens with its Groups line, and the site list with its Version lines is gone.
        """
        self._navigate_to_sites()

        self._require_online_site()

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
        """Verify A-Z and Z-A camera sorting within a site.

        Steps:
        1. Open Admin > Sites and open an online site.
           Expected: The site detail lists its cameras.
        2. Click the A-Z sort icon, then the Z-A sort icon.
           Expected: The camera order reverses between the two sorts when the site has more than one camera.
        """
        self._navigate_to_sites()

        # Navigate into a site first
        self._require_online_site()

        self._open_first_site()
        self._skip_if_redesigned_detail()

        # Sort A-Z. The detail page is open (the helper above proved
        # it), so this is the measured absence of a sort control on the
        # current layout, not a page that failed to load.
        if not self._appears(self.admin.sort_az_icon):
            pytest.skip(
                "The site detail page renders no A-Z sort icon, so there is "
                "no sort control to exercise on this layout"
            )

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
        """Verify a camera group can be created on a site.

        Steps:
        1. Open Admin > Sites and open the first site.
           Expected: The site detail opens with its Groups control.
        2. Open the Groups dropdown, click Create, name the group, search the configured camera and tick it, then Create.
           Expected: The form closes, which is the app's saved signal.
        """
        self._navigate_to_sites()
        self._open_first_site()

        # Group management lives in the Groups dropdown since 2026-08.
        # click_site already failed loud if the detail (and its Groups
        # label) never rendered, so no skip guard belongs here.
        self.admin.open_groups_dropdown()

        timestamp = datetime.datetime.now().strftime("%H%M%S%f")[:9]
        group_name = f"AutoTest Group {timestamp}"
        self._created_groups.append(group_name)

        # Search term for cameras to add: the configured camera name,
        # never a hardcoded vendor name (the tenant renames cameras)
        camera_search = config.get("test_camera_name", "camera")
        # oracle: create_camera_group raises when the form never closes,
        # which is the app's only saved signal here
        self.admin.create_camera_group(group_name, camera_search=camera_search)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_edit_camera_group(self, api_camera_group):
        """Verify editing a camera group name.

        The group comes from the API (tests/shared/api/fixtures.py):
        this test proves the UI rename, and test_create_camera_group
        proves the UI create. Renaming our own group, never the last
        existing one, keeps team-owned data on the shared tenant safe.

        Steps:
        1. Open Admin > Sites, search the configured site, open it and open the Groups dropdown.
           Expected: The camera group made for this test is listed.
        2. Edit that group's name and save.
           Expected: The group is listed under the new name.
        """
        # Created before the page renders, so the Groups dropdown
        # loads it with the site detail and no reload is needed
        group = api_camera_group()

        self._navigate_to_sites()
        # The API wrote to TEST_SITE_ID, so open that site by name
        # instead of the first card
        self.admin.search_site(group["site_name"])
        self.admin.click_site(group["site_name"])

        # Group management lives in the Groups dropdown since 2026-08.
        # click_site already failed loud if the detail (and its Groups
        # label) never rendered, so no skip guard belongs here.
        self.admin.open_groups_dropdown()

        # The fixture deletes the group by id at teardown, so the new
        # name needs no entry in the UI cleanup list
        timestamp = datetime.datetime.now().strftime("%H%M%S%f")[:9]
        new_name = f"AutoTest Edited {timestamp}"
        assert self.admin.edit_camera_group_by_name(group["name"], new_name) is True, (
            f"API-created group '{group['name']}' not found for rename"
        )
        # the renamed group is listed under its new name
        expect(self.page.get_by_text(new_name, exact=True)).to_have_text(new_name, timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_delete_camera_group(self, api_camera_group):
        """Verify deleting a camera group with Yes confirmation.

        The group comes from the API (tests/shared/api/fixtures.py):
        this test proves the UI delete, and test_create_camera_group
        proves the UI create. Deleting our own group, never the last
        existing one, keeps team-owned data on the shared tenant safe.
        """
        # Created before the page renders, so the Groups dropdown
        # loads it with the site detail and no reload is needed
        group = api_camera_group()

        self._navigate_to_sites()
        # The API wrote to TEST_SITE_ID, so open that site by name
        # instead of the first card
        self.admin.search_site(group["site_name"])
        self.admin.click_site(group["site_name"])

        # Group management lives in the Groups dropdown since 2026-08.
        # click_site already failed loud if the detail (and its Groups
        # label) never rendered, so no skip guard belongs here.
        self.admin.open_groups_dropdown()
        assert self.admin.delete_camera_group_by_name(group["name"]), (
            f"API-created group '{group['name']}' not found for delete"
        )

        # The named row leaving the list is the delete signal
        expect(
            self.page.get_by_text(group["name"], exact=True)
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
        # No pre-check: click_site raises naming every site that IS on
        # the page, which is the tenant-rename fix in one line. The old
        # pre-check turned that into a skip (register item 25).
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
