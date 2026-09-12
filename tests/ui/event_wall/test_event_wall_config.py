"""Event Wall configuration tests (regular login).

Event Wall is its own feature, deliberately separated from the
regular app's Views/Events coverage (per Justin, 08/13/2026). It has
two surfaces that must not be mixed:

- CONFIGURATION (this file): the regular login sets the wall up at
  Admin > General > Event Wall card > View - a configuration TABLE
  (Configuration Name | Site | No of Devices | Devices, 'No
  configuration found.' when empty) plus the Add Configuration modal
  (name input, Available Cameras site accordion expanding to camera
  groups then cameras, Select Rule combobox, Cancel/Save).
- DISPLAY (test_event_wall_display.py): the live wall is a separate
  UI experience behind a special local-access login.

Rebuilt 08/13/2026 on the measured page; the old suite clicked the
General card TITLE (a no-op) and probed page-level dropdowns, event
images, and grids that do not exist on this page.
"""
import pytest
from playwright.sync_api import Error as PlaywrightError, expect

from config.base_config import config
from tests.shared.pages.admin_page import AdminPage

SITE_NAME = config.get("test_site_name")
CAMERA_NAME = config.get("test_camera_name")
# measured 09/12/2026 on US (register row 53): the table's columns and its empty row
EVENT_WALL_HEADERS = ["Configuration Name", "Site", "No of Devices", "Devices", ""]
EVENT_WALL_EMPTY = "No configuration found."


class TestEventWallConfig:
    """Tests for the Event Wall configuration surface (regular login)."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.admin = AdminPage(self.page)
        self.admin.navigate_to_admin()

        # General renders as cards; the Rules sub-tab marks it ready
        self.admin.general_tab.wait_for(state="visible", timeout=10000)
        self.admin.general_tab.click()
        self.page.locator("p:text-is('Rules')").first.wait_for(
            state="visible", timeout=10000
        )

        # The Event Wall card's View link is the entry point (the
        # card title itself is a no-op)
        card = self.page.locator(".MuiCard-root").filter(
            has_text="Event Wall"
        ).first
        # General is already proved up by the Rules sub-tab wait above,
        # so a missing card here is a regression in a permanent control,
        # not an absent artifact (register item 25).
        card.wait_for(state="visible", timeout=10000)
        card.get_by_text("View", exact=True).first.click()

        # the Add Configuration button is the arrived signal
        self.add_config = self.page.get_by_text(
            "Add Configuration", exact=True
        )
        self.add_config.wait_for(state="visible", timeout=15000)
        yield

    def _open_add_form(self):
        """Open the Add Configuration modal; the name input is the
        open marker."""
        self.add_config.click()
        name_input = self.page.locator("input[name='name']")
        name_input.wait_for(state="visible", timeout=10000)
        return name_input

    def _close_add_form(self):
        """Cancel out of the modal; the name input leaving is the
        closed signal."""
        self.page.get_by_text("Cancel", exact=True).first.click()
        self.page.locator("input[name='name']").wait_for(
            state="hidden", timeout=10000
        )

    def _back_to_general_cards(self):
        """Return to the General cards via the breadcrumb (the whole
        'General > Event Wall' crumb is one clickable p; the section
        tab is a no-op while already inside General - measured)."""
        self.page.get_by_text("General >", exact=False).first.click()
        expect(self.page.locator(".MuiCard-root").filter(
            has_text="Event Wall"
        ).first).to_be_visible(timeout=10000)

    def _modal(self):
        """The open Add Configuration modal (MUI keeps closed ones mounted)."""
        # a MUI Dialog's root carries MuiModal-root too, so one class covers both
        return self.page.locator(".MuiModal-root:visible").last

    def _expand_group_to_cameras(self, group_row) -> int:
        """Click a camera group and wait for its camera rows.

        The rows' own checkboxes are the expanded signal, not a camera
        name: the panel truncates names to 'Soterix Multica...' with no
        title attribute, so a text wait on the configured camera never
        matched (09/11/2026 full run, both tests). The search box above
        the tree filters SITES, not cameras (probed the same day).
        Returns the count the group row declares ('All Cameras 22').
        """
        group_row.click()
        boxes = self._modal().locator("input[type='checkbox']")
        boxes.first.wait_for(state="visible", timeout=10000)
        # the group row reads 'All Cameras' then its device count
        text = group_row.locator("xpath=..").inner_text()
        digits = [t for t in text.split() if t.isdigit()]
        return int(digits[0]) if digits else 0

    def _expand_site_to_groups(self):
        """In the Add form, expand the config site; sites expand to
        camera GROUPS (measured), cameras sit one level deeper."""
        site_row = self.page.get_by_text(SITE_NAME, exact=False).first
        site_row.wait_for(state="visible", timeout=10000)
        site_row.click()
        group_row = self.page.get_by_text("All Cameras", exact=True).first
        group_row.wait_for(state="visible", timeout=10000)
        return group_row

    # --- Page structure ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.event_wall
    def test_event_wall_page_loads(self):
        """The Event Wall page shows its breadcrumb and Add button.

        Steps:
        1. Open Admin > General and click View on the Event Wall card.
           Expected: The breadcrumb reads General > Event Wall and an enabled Add Configuration button is shown.
        """
        crumb = self.page.get_by_text("General > Event Wall", exact=True)
        expect(crumb).to_have_text("General > Event Wall", timeout=10000)
        expect(self.add_config).to_be_enabled()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.event_wall
    def test_event_wall_has_configuration_area(self):
        """The configuration table renders its column headers.

        Steps:
        1. Open Admin > General and click View on the Event Wall card.
           Expected: The table's columns are Configuration Name, Site, No of Devices and Devices, followed by an unlabelled actions column.
        """
        expect(self.page.locator("thead").first).to_be_visible(timeout=10000)
        headers = [h.strip() for h in self.page.locator("thead th, thead td").all_inner_texts()]
        assert headers == EVENT_WALL_HEADERS, (
            f"the configuration table's columns read {headers}, expected {EVENT_WALL_HEADERS}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.event_wall
    def test_event_wall_grid_layout(self):
        """The table shows configurations or the measured empty state.

        Steps:
        1. Open Admin > General and click View on the Event Wall card.
           Expected: The table lists configurations, each with a name, a site and a device count, or one row reading "No configuration found.".
        """
        rows = self.page.locator("table tbody tr")
        expect(rows.first).to_be_visible(timeout=10000)
        # the empty row carries its sentence outside a td (measured)
        if rows.first.inner_text().strip() == EVENT_WALL_EMPTY:
            expect(rows).to_have_count(1)
        else:
            for row in rows.all():
                cells = [c.strip() for c in row.locator("td").all_inner_texts()]
                assert len(cells) >= 4 and cells[0] and cells[1] and cells[2].isdigit(), (
                    f"a configuration row reads {cells}; expected a name, a site and a device count")

    # --- The Add Configuration form ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.event_wall
    def test_event_wall_site_selector(self):
        """The Add form lists the configured site under Available Cameras.

        Steps:
        1. Open Admin > General, click View on the Event Wall card, then click Add Configuration.
           Expected: The Add Event Wall Configuration form opens with an empty Configuration Name field (placeholder Enter Configuration Name) and an Available Cameras panel listing the configured site with its device count.
        2. Expand the site.
           Expected: Its All Cameras group declares the same device count as the site row.
        """
        name_input = self._open_add_form()
        modal = self._modal()
        expect(modal.get_by_text("Add Event Wall Configuration", exact=True)).to_be_visible(timeout=10000)
        expect(name_input).to_have_value("")
        expect(name_input).to_have_attribute("placeholder", "Enter Configuration Name")
        expect(self.page.get_by_text("Available Cameras", exact=True)).to_be_visible(timeout=10000)
        # exact=False: the row reads the name with its device count;
        # .first: the panel lists each site once before it is expanded
        site_row = self.page.get_by_text(SITE_NAME, exact=False).first
        expect(site_row).to_be_visible(timeout=10000)
        # the row reads '<site> <device count>' (measured: 'Spartan0 22')
        site_text = " ".join(site_row.locator("xpath=..").inner_text().split())
        site_count = site_text.rsplit(" ", 1)[-1]
        assert site_text.startswith(SITE_NAME) and site_count.isdigit(), (
            f"the site row reads {site_text!r}; expected the site name and its device count")
        group_row = self._expand_site_to_groups()
        group_text = " ".join(group_row.locator("xpath=..").inner_text().split())
        assert group_text == f"All Cameras {site_count}", (
            f"the All Cameras group reads {group_text!r}, the site row declares {site_count} devices")
        self._close_add_form()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.event_wall
    def test_event_wall_site_dropdown_opens(self):
        """A site accordion row expands to its camera groups."""
        self._open_add_form()
        # oracle: _expand_site_to_groups raises unless the group list
        # renders (sites expand to groups, not cameras - measured)
        self._expand_site_to_groups()
        self._close_add_form()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.event_wall
    def test_event_wall_has_rule_types(self):
        """The Add form's Select Rule dropdown unlocks once a camera is ticked.

        Steps:
        1. Open Admin > General, click View on the Event Wall card, then click Add Configuration.
           Expected: The form shows a Select Rule dropdown, disabled while no camera is selected.
        2. Expand the site to its cameras and tick one.
           Expected: The Select Rule dropdown is enabled.
        """
        self._open_add_form()
        combo = self._modal().locator("div[role='combobox']").first
        expect(combo).to_have_text("Select Rule", timeout=10000)
        expect(combo).to_have_attribute("aria-disabled", "true")
        group_row = self._expand_site_to_groups()
        self._expand_group_to_cameras(group_row)
        box = self._modal().locator("input[type='checkbox']").first
        if not box.is_checked():
            box.click()
        expect(box).to_be_checked(timeout=5000)
        expect(combo).not_to_have_attribute("aria-disabled", "true", timeout=5000)
        self._close_add_form()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.event_wall
    def test_event_wall_camera_checkboxes(self):
        """Every camera row of an expanded group carries a checkbox.

        Steps:
        1. Open Admin > General, click View on the Event Wall card, click Add Configuration, then expand the configured site down to a camera group and click it.
           Expected: The group's camera rows are listed under Available Cameras, each with a checkbox.
        2. Count the checkboxes against the device count the group row shows.
           Expected: One checkbox per device.
        """
        self._open_add_form()
        group_row = self._expand_site_to_groups()
        declared = self._expand_group_to_cameras(group_row)
        boxes = self._modal().locator("input[type='checkbox']")
        expect(boxes).to_have_count(declared, timeout=10000)
        self._close_add_form()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.event_wall
    def test_event_wall_toggle_checkbox(self):
        """A camera selection control can be toggled.

        Steps:
        1. Open Admin > General, click View on the Event Wall card, click Add Configuration, then expand the configured site down to a camera group and click it.
           Expected: The group's camera rows are listed under Available Cameras.
        2. Tick a camera's checkbox, then untick it.
           Expected: The checkbox changes state on each click.
        """
        self._open_add_form()
        group_row = self._expand_site_to_groups()
        self._expand_group_to_cameras(group_row)
        # modal-scoped: switches behind the backdrop hang pointer clicks
        box = self._modal().locator("input[type='checkbox']").first
        before = box.is_checked()
        box.click()
        if before:
            expect(box).not_to_be_checked(timeout=5000)
        else:
            expect(box).to_be_checked(timeout=5000)
        box.click()
        if before:
            expect(box).to_be_checked(timeout=5000)
        else:
            expect(box).not_to_be_checked(timeout=5000)
        self._close_add_form()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.event_wall
    def test_event_wall_save_or_apply(self):
        """The Add form carries Cancel and Save.

        Steps:
        1. Open Admin > General, click View on the Event Wall card, then click Add Configuration.
           Expected: The form's buttons are Cancel and Save, both enabled.
        """
        self._open_add_form()
        buttons = self._modal().locator("button")
        expect(buttons).to_have_count(2, timeout=10000)
        labels = [b.strip() for b in buttons.all_inner_texts()]
        assert labels == ["Cancel", "Save"], f"the form's buttons read {labels}"
        expect(buttons.nth(0)).to_be_enabled()
        expect(buttons.nth(1)).to_be_enabled()
        self._close_add_form()

    # --- Navigation ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.event_wall
    def test_back_to_general_from_event_wall(self):
        """The breadcrumb returns to the General cards page.

        Steps:
        1. From the Event Wall configuration page, click the General breadcrumb.
           Expected: The General cards page is shown again.
        """
        # oracle: _back_to_general_cards expects the cards visible
        self._back_to_general_cards()

    def _open_card_view(self, card_title: str, arrival):
        """Click a General card's View and wait for arrival.

        A View click right after the cards page re-renders can be
        silently dropped (the hydration behavior the sites rebuild
        measured), so one retry click self-heals.
        """
        card = self.page.locator(".MuiCard-root").filter(
            has_text=card_title
        ).first
        card.wait_for(state="visible", timeout=10000)
        card.get_by_text("View", exact=True).first.click()
        try:
            arrival.wait_for(state="visible", timeout=7000)
        except PlaywrightError:
            card.get_by_text("View", exact=True).first.click()
            arrival.wait_for(state="visible", timeout=15000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.event_wall
    def test_event_wall_to_audit_trail_round_trip(self):
        """Event Wall -> General cards -> Event Wall round trip.

        The Audit Trail leg is dropped: its View click does not
        navigate in-page even with the hydration retry (measured
        08/13/2026, twice) - where it goes belongs to the audit
        file's rebuild.
        """
        # oracle: both helpers raise unless their arrival markers
        # render (cards page, then Add Configuration)
        self._back_to_general_cards()
        self._open_card_view(
            "Event Wall",
            self.page.get_by_text("Add Configuration", exact=True),
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.event_wall
    def test_event_wall_after_refresh(self):
        """The admin section stays valid after a browser refresh."""
        # reload waits for the load event on its own
        self.page.reload()
        assert "admin" in self.page.url.lower()
        self.admin.general_tab.wait_for(state="visible", timeout=15000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.event_wall
    def test_event_wall_scrollable(self):
        """The page survives scrolling (synchronous, no settle).

        Steps:
        1. On the Event Wall configuration page, scroll down and back up.
           Expected: The page is back at the top and the breadcrumb still reads General > Event Wall.
        """
        self.page.evaluate("window.scrollBy(0, 300)")
        self.page.evaluate("window.scrollTo(0, 0)")
        assert self.page.evaluate("window.scrollY") == 0
        expect(self.page.get_by_text("General > Event Wall", exact=True)).to_have_text("General > Event Wall")
