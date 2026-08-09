"""Insights test fixtures."""
import pytest

from tests.shared.pages.insights_page import InsightsPage


@pytest.fixture
def insights_page(authenticated_page):
    """Provide an InsightsPage instance (does not navigate automatically)."""
    return InsightsPage(authenticated_page)
