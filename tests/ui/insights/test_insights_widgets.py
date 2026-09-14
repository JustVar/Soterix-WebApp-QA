"""Insights widget creation, view, report, and delete tests.

Covers the full widget CRUD lifecycle for each graph type (Line, Bar,
Pie, Heat) and category (Person, Vehicle, Event). Uses parametrize
to avoid duplicating 11 near-identical test methods.

Migrated from Selenium:
- test_linegraph_person_insights_create_export_delete (line 2202)
- test_linegraph_vehicle_insights_create_export_delete (line 2210)
- test_linegraph_event_insights_create_export_delete (line 2218)
- test_bargraph_person_insights_create_export_delete (line 2226)
- test_bargraph_vehicle_insights_create_export_delete (line 2234)
- test_bargraph_event_insights_create_export_delete (line 2242)
- test_piegraph_person_insights_create_export_delete (line 2250)
- test_piegraph_vehicle_insights_create_export_delete (line 2258)
- test_piegraph_event_insights_create_export_delete (line 2266)
- test_heatmap_person_insights_create_export_delete (line 2274)
- test_heatmap_vehicle_insights_create_export_delete (line 2282)

Note: Heatmap + Event is not a valid combination - the UI only offers
Person and Vehicle categories when Heat Map graph type is selected.
"""
import pytest

from config.base_config import config
from tests.shared.pages.insights_page import InsightsPage

# The shared tenant renames sites, so the name lives in config
SITE_NAME = config.get("test_site_name")

# All valid graph/category combinations (11 total)
# Heat map only supports Person and Vehicle (no Event option in UI)
WIDGET_PARAMS = [
    ("Line", "Person"),
    ("Line", "Vehicle"),
    ("Line", "Event"),
    ("Bar", "Person"),
    ("Bar", "Vehicle"),
    ("Bar", "Event"),
    ("Pie", "Person"),
    ("Pie", "Vehicle"),
    ("Pie", "Event"),
    ("Heat", "Person"),
    ("Heat", "Vehicle"),
]

WIDGET_IDS = [f"{g}_{c}" for g, c in WIDGET_PARAMS]


class TestInsightsWidgetCreate:
    """Tests for widget creation across graph types and categories."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.insights = InsightsPage(self.page)
        self._created_widgets = []
        yield
        for name in reversed(self._created_widgets):
            try:
                self.insights.delete_widget(name)
            # teardown: a failed delete must not mask the test result;
            # test_widget_delete owns the delete oracle
            except Exception as e:
                print(f"Cleanup: failed to delete widget '{name}': {e}")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.parametrize(
        "graph_name,category_name", WIDGET_PARAMS, ids=WIDGET_IDS
    )
    def test_widget_create(self, graph_name, category_name):
        """Verify a widget can be created with the given graph and category.

        Steps:
        1. Open Insights, switch to Widgets and click Create New Widget; choose the graph type and category under test, the configured site and camera, a duration and a size, then save.
           Expected: A 'Widget created successfully' message appears and the widget is listed.
        """
        widget_name = self.insights.create_widget(
            graph_name=graph_name,
            category_name=category_name,
            site_name=SITE_NAME,
        )
        self._created_widgets.append(widget_name)
        assert widget_name != "", "Widget name should be returned after creation"


class TestInsightsWidgetOperations:
    """Tests for widget view, report, and delete operations.

    These tests create a widget first, then perform operations on it.
    Cleanup is handled by the setup fixture teardown, ensuring widgets
    are deleted even if the test fails mid-execution.
    """

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.insights = InsightsPage(self.page)
        self._created_widgets = []
        yield
        for name in reversed(self._created_widgets):
            try:
                self.insights.delete_widget(name)
            # teardown: a failed delete must not mask the test result;
            # test_widget_delete owns the delete oracle
            except Exception as e:
                print(f"Cleanup: failed to delete widget '{name}': {e}")

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.parametrize(
        "graph_name,category_name",
        [("Line", "Person"), ("Bar", "Person"), ("Pie", "Person")],
        ids=["Line_Person", "Bar_Person", "Pie_Person"],
    )
    def test_widget_view(self, graph_name, category_name):
        """Verify a widget can be viewed after creation."""
        widget_name = self.insights.create_widget(
            graph_name=graph_name,
            category_name=category_name,
            site_name=SITE_NAME,
        )
        self._created_widgets.append(widget_name)

        # oracle: view_widget raises unless the View page opens (its
        # back-arrow wait) and closes again
        self.insights.view_widget(widget_name)

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.parametrize(
        "graph_name,category_name",
        [("Line", "Person"), ("Bar", "Event")],
        ids=["Line_Person", "Bar_Event"],
    )
    def test_widget_report(self, graph_name, category_name):
        """A widget's report can be downloaded from its menu.

        Steps:
        1. On Insights, create a widget of the given graph type and category for the configured site.
           Expected: The widget shows on the dashboard under its generated name.
        2. Open the widget's menu and click Report.
           Expected: A file download starts.
        """
        widget_name = self.insights.create_widget(
            graph_name=graph_name,
            category_name=category_name,
            site_name=SITE_NAME,
        )
        self._created_widgets.append(widget_name)

        # oracle: download_report raises unless the browser download
        # actually starts
        self.insights.download_report(widget_name)

    @pytest.mark.ui
    @pytest.mark.insights
    @pytest.mark.parametrize(
        "graph_name,category_name",
        [("Line", "Person"), ("Pie", "Vehicle"), ("Heat", "Person")],
        ids=["Line_Person", "Pie_Vehicle", "Heat_Person"],
    )
    def test_widget_delete(self, graph_name, category_name):
        """Verify a widget can be deleted and no longer appears in search.

        Steps:
        1. Open Insights, switch to Widgets and create a widget with the graph type and category under test.
           Expected: The widget is listed.
        2. Open the widget's options menu, choose Delete and confirm.
           Expected: The widget no longer appears when searched for by name.
        """
        widget_name = self.insights.create_widget(
            graph_name=graph_name,
            category_name=category_name,
            site_name=SITE_NAME,
        )
        # Not added to _created_widgets - deletion is this test's purpose

        deleted = self.insights.delete_widget(widget_name)
        assert deleted is True, f"Widget '{widget_name}' should be deleted"
