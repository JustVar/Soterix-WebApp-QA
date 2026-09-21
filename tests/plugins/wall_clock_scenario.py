"""The scenario tests/plugins/test_wall_clock.py runs in a subprocess: one test
whose teardown never returns, beside tests that pass. Not collected by the
offline suites (no test_ prefix); pytest collects it only when given its path."""
import time

import pytest


@pytest.fixture
def browser_that_stopped_answering():
    yield
    time.sleep(3600)  # why: stands for a teardown call on a dead browser, which never returns; no DOM here


def test_stuck_in_teardown(browser_that_stopped_answering):
    """Passes its body, then its teardown blocks for an hour."""
    assert True


@pytest.mark.parametrize("n", range(6))
def test_ordinary(n):
    """The rest of the run: each of these must still pass."""
    assert n >= 0
