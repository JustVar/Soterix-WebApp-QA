"""LPR insight widget tests - creation, LPR panel lookup, drop-to-tile.

Rebuilt 08/13/2026. The old file's creation flow was dead code inside
an except branch (the test clicked Insights and passed vacuously), so
no widget ever existed and the two dependent tests skipped forever.
Widgets are created through the shared InsightsPage flow with the
License Plate Recognition description; the LPR camera page lists them
in its Widgets panel, where cards drag onto tiles. There is no
checkbox on the redesigned panel - the select affordance is
drag-to-tile (measured 08/13/2026), and placement is session-scoped,
so it resets on reload without cleanup.
"""
import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.pages.insights_page import InsightsPage
from tests.shared.pages.lpr_page import LprPage

# One worker for every module that writes this account's dashboards and widgets (the insights modules write the same): under
# -n they would otherwise spread across workers and race on the same
# tenant state (pytest.ini --dist loadgroup; audit 09/17/2026, row 86).
pytestmark = pytest.mark.xdist_group("account_insights")


# The shared tenant renames sites, so the name lives in config
SITE_NAME = config.get("test_site_name")
LPR_DESCRIPTION = "License Plate Recognition"


class TestLprWidgets:
    """Tests for LPR insight widget functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.insights = InsightsPage(self.page)
        self.lpr = LprPage(self.page)
        self._created_widgets = []
        yield
        for name in reversed(self._created_widgets):
            try:
                self.insights.delete_widget(name)
            # cleanup is best-effort: the verdict is already decided,
            # and a leak here prints for the tenant mop-up list
            except Exception as e:
                print(f"Cleanup: failed to delete widget '{name}': {e}")

    def _create_lpr_widget(self) -> str:
        """Create an Event/LPR widget through the Insights flow.

        create_widget raises unless the success toast confirms the
        widget was created.
        """
        name = self.insights.create_widget(
            graph_name="Line",
            category_name="Event",
            site_name=SITE_NAME,
            description_name=LPR_DESCRIPTION,
        )
        self._created_widgets.append(name)
        return name

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_create_new_insight_widget(self):
        """Create an LPR insight widget with the shared Insights flow.

        Steps:
        1. Click Insights in the left sidebar, then click the Widgets tab.
           Expected: The Widgets tab opens with a Create New Widget button.
        2. Click Create New Widget and enter a unique widget name.
           Expected: The widget form shows the name.
        3. Choose Line as the graph type, Event as the category, and License Plate Recognition as the description, then choose the configured test site.
           Expected: The form shows the chosen values.
        4. Click Save.
           Expected: A toast confirms the widget was created and the widget is listed by its name.
        """
        self.step_capture.mark(1, "Create a widget with the LPR description")
        name = self._create_lpr_widget()
        assert name != "", "Widget name should be returned after creation"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_verify_widget_in_lpr_dropdown(self):
        """A created LPR widget appears in the camera page Widgets panel.

        Steps:
        1. On Insights, create a Line widget for the Event category with the License Plate Recognition description and the configured test site.
           Expected: A toast confirms the widget was created.
        2. Click LPR in the left sidebar.
           Expected: The LPR camera page opens.
        3. Click the Widgets header.
           Expected: The Widgets panel opens and shows widget cards.
        4. Type the widget name in the panel's Search field.
           Expected: Exactly one card is listed, and it carries the widget name.
        """
        self.step_capture.mark(1, "Create a widget with the LPR description")
        name = self._create_lpr_widget()

        self.step_capture.mark(2, "Open the LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(3, "Open the Widgets panel")
        self.lpr.open_widgets_panel()

        self.step_capture.mark(4, f"Search '{name}' and expect its card")
        card = self.lpr.search_widgets(name)
        expect(card).to_have_count(1, timeout=15000)
        expect(card.first).to_be_visible()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_select_widget_checkbox(self):
        """Place a widget on the LPR page by dragging its card to a tile.

        The checkbox this test once clicked does not exist on the
        redesigned panel (measured 08/13/2026); cards drag onto tiles
        the way cameras do. Placement is session-scoped, so the tile
        resets next session without cleanup.

        Steps:
        1. On Insights, create a Line widget for the Event category with the License Plate Recognition description and the configured test site.
           Expected: A toast confirms the widget was created.
        2. Click LPR in the left sidebar.
           Expected: The LPR camera page opens.
        3. Click the Widgets header, then type the widget name in the panel's Search field.
           Expected: The widget card is listed.
        4. Drag the card onto the last empty tile.
           Expected: The tile fills with the widget and one fewer empty tile remains.
        """
        self.step_capture.mark(1, "Create a widget with the LPR description")
        name = self._create_lpr_widget()

        self.step_capture.mark(2, "Open the LPR camera page")
        self.lpr.ensure_lpr_camera_page()

        self.step_capture.mark(3, "Open the Widgets panel")
        self.lpr.open_widgets_panel()

        self.step_capture.mark(4, "Search the widget")
        self.lpr.search_widgets(name)

        # This module is in account_insights (it creates widgets), and a module holds 1 group.
        # The drop uses the tiles of the LPR camera page, whose layout the account_lpr modules
        # change on a different worker. It needs 1 empty tile, and the layout test plays no
        # camera, so each layout it sets has one. Not measured under a race:
        # tests/plugins/test_xdist_groups.py names this file as the known case.
        self.step_capture.mark(5, "Drag the card onto the last empty tile")
        # oracle: drop_widget_on_tile raises unless a tile is consumed
        # and the widget renders outside the panel
        self.lpr.drop_widget_on_tile(name)
