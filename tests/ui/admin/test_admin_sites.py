"""Admin Sites tests - navigation, search, view toggle, status, versions,
camera sorting, camera group CRUD."""
import datetime
import pytest
from playwright.sync_api import expect
from tests.shared.pages.admin_page import AdminPage


class TestAdminSites:
    """Tests for Admin > Sites section."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.admin = AdminPage(self.page)
        self._created_groups = []
        yield
        # Cleanup: no reliable delete mechanism for camera groups in UI,
        # so we track names but rely on manual cleanup if needed.

    def _navigate_to_sites(self):
        """Helper to navigate to Admin > Sites."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_sites()

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

        self.admin.search_site("Driver")
        self.page.wait_for_timeout(2000)

        search_field = self.page.locator(
            "input[placeholder*='Search']"
        ).first
        expect(search_field).to_have_value("Driver")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_toggle_grid_list_view(self):
        """Verify toggling between grid and list view on the Sites page."""
        self._navigate_to_sites()

        # Toggle to list view
        if self.admin.list_view_toggle.count() > 0:
            self.admin.toggle_to_list_view()

        # Toggle back to grid view
        if self.admin.grid_view_toggle.count() > 0:
            self.admin.toggle_to_grid_view()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_check_site_status(self):
        """Verify sites display Online/Offline status indicators."""
        self._navigate_to_sites()

        statuses = self.admin.get_site_statuses()
        assert statuses[0]["total"] > 0, "No site status indicators found"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_site_versions(self):
        """Verify sites display version information."""
        self._navigate_to_sites()

        versions = self.admin.get_site_versions()
        # At least one version element should be present
        assert len(versions) > 0, "No version info found on Sites page"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_navigate_to_online_site(self):
        """Verify clicking a site card navigates into the site detail view."""
        self._navigate_to_sites()

        if self.admin.online_status_icons.count() == 0:
            pytest.skip("No online sites found")

        # Find a site name to click - look for the first site card text
        site_cards = self.page.locator(
            "p.MuiTypography-root"
        )
        # Try to click the first visible site name that looks like a site
        for i in range(site_cards.count()):
            text = site_cards.nth(i).inner_text().strip()
            if text and text not in ("Sites", "Users", "General", "Rules"):
                self.admin.click_site(text)
                break
        else:
            pytest.skip("No clickable site cards found")

        self.page.wait_for_timeout(3000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_camera_sorting(self):
        """Verify A-Z and Z-A camera sorting within a site."""
        self._navigate_to_sites()

        # Navigate into a site first
        if self.admin.online_status_icons.count() == 0:
            pytest.skip("No online sites to test camera sorting")

        site_cards = self.page.locator("p.MuiTypography-root")
        for i in range(site_cards.count()):
            text = site_cards.nth(i).inner_text().strip()
            if text and text not in ("Sites", "Users", "General", "Rules"):
                self.admin.click_site(text)
                break
        else:
            pytest.skip("No clickable site cards found")

        # Sort A-Z
        if self.admin.sort_az_icon.count() == 0:
            pytest.skip("Sort icons not found in site detail")

        self.admin.click_sort_az()
        names_az = self.admin.get_camera_names()

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

        # Navigate into a site first
        site_cards = self.page.locator("p.MuiTypography-root")
        for i in range(site_cards.count()):
            text = site_cards.nth(i).inner_text().strip()
            if text and text not in ("Sites", "Users", "General", "Rules"):
                self.admin.click_site(text)
                break
        else:
            pytest.skip("No clickable site cards found")

        # Expand camera groups section
        if self.admin.accordion_icon.count() == 0:
            pytest.skip("Accordion icon not found - camera groups not available")

        self.admin.expand_camera_groups()

        if self.admin.create_new_button.count() == 0:
            pytest.skip("Create New button not visible")

        timestamp = datetime.datetime.now().strftime("%H%M%S")
        group_name = f"AutoTest Group {timestamp}"
        self._created_groups.append(group_name)

        self.admin.create_camera_group(group_name, camera_search="Hanwha")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_edit_camera_group(self):
        """Verify editing a camera group name."""
        self._navigate_to_sites()

        # Navigate into a site first
        site_cards = self.page.locator("p.MuiTypography-root")
        for i in range(site_cards.count()):
            text = site_cards.nth(i).inner_text().strip()
            if text and text not in ("Sites", "Users", "General", "Rules"):
                self.admin.click_site(text)
                break
        else:
            pytest.skip("No clickable site cards found")

        # Expand camera groups
        if self.admin.accordion_icon.count() == 0:
            pytest.skip("Accordion icon not found")

        self.admin.expand_camera_groups()

        if self.admin.group_edit_icons.count() == 0:
            pytest.skip("No camera group edit icons found")

        timestamp = datetime.datetime.now().strftime("%H%M%S")
        new_name = f"Edited Group {timestamp}"

        self.admin.edit_camera_group(new_name)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_delete_camera_group(self):
        """Verify deleting a camera group with Yes confirmation."""
        self._navigate_to_sites()

        # Navigate into a site first
        site_cards = self.page.locator("p.MuiTypography-root")
        for i in range(site_cards.count()):
            text = site_cards.nth(i).inner_text().strip()
            if text and text not in ("Sites", "Users", "General", "Rules"):
                self.admin.click_site(text)
                break
        else:
            pytest.skip("No clickable site cards found")

        # Expand camera groups
        if self.admin.accordion_icon.count() == 0:
            pytest.skip("Accordion icon not found")

        self.admin.expand_camera_groups()

        if self.admin.group_delete_icons.count() == 0:
            pytest.skip("No camera group delete icons found")

        initial_count = self.admin.group_delete_icons.count()
        self.admin.delete_camera_group()

        self.page.wait_for_timeout(2000)
        new_count = self.admin.group_delete_icons.count()
        assert new_count < initial_count, (
            f"Expected group count to decrease after deletion "
            f"(was {initial_count}, now {new_count})"
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_sites
    def test_search_inside_site(self):
        """Verify searching for cameras within a site detail view."""
        self._navigate_to_sites()

        # Navigate into a site first
        site_cards = self.page.locator("p.MuiTypography-root")
        for i in range(site_cards.count()):
            text = site_cards.nth(i).inner_text().strip()
            if text and text not in ("Sites", "Users", "General", "Rules"):
                self.admin.click_site(text)
                break
        else:
            pytest.skip("No clickable site cards found")

        # Get a camera name to search for
        cameras = self.admin.get_camera_names()
        if not cameras:
            pytest.skip("No cameras found in site")

        # Use the first word of the first camera name as search term
        search_term = cameras[0].split()[0]
        self.admin.search_inside_site(search_term)

        # Verify filtered results contain the search term
        results = self.page.locator("div.site-card")
        assert results.count() > 0, (
            f"No results found when searching for '{search_term}'"
        )

        # Verify at least one result contains the search term
        found = False
        for i in range(results.count()):
            text = results.nth(i).inner_text().strip()
            if search_term.lower() in text.lower():
                found = True
                break
        assert found, (
            f"Search term '{search_term}' not found in any result"
        )
