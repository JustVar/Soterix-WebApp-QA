import pytest

# Place for shared fixtures (browser wrappers, test data builders)

@pytest.fixture(scope="session")
def example_shared_fixture():
    return {"example": True}
