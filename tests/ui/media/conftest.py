"""Media test fixtures."""
import pytest

from tests.shared.pages.media_page import MediaPage


@pytest.fixture
def media_page(authenticated_page):
    """Provide a MediaPage navigated to the Media page."""
    page = authenticated_page
    media = MediaPage(page)
    media.navigate()
    return media
