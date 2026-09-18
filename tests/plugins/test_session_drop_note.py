"""Pins for the session-drop note conftest appends to a failure.

Three failures in the 09/16/2026 nightly read as locator timeouts; their
screenshots showed the login screen, because the app had answered 401 to
a live session and bounced the page to login mid-test. The note names
that mechanism in the traceback itself, and only there: a failure on any
other page, a passing test, a setup failure and a page already closed
get nothing.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import conftest  # noqa: E402


class FakePage:
    def __init__(self, url):
        self._url = url

    @property
    def url(self):
        if self._url is None:
            raise RuntimeError("Target page, context or browser has been closed")
        return self._url


class FakeItem:
    def __init__(self, page=None):
        if page is not None:
            self.qa_page = page


class FakeReport:
    def __init__(self, when="call", failed=True):
        self.when = when
        self.failed = failed


LOGIN = "https://qa.example.invalid/auth/login?_rsc=g8pty"
MAPS = "https://qa.example.invalid/maps"


def test_a_failure_on_the_login_screen_gets_the_note():
    """The call failed and the page's URL is the login screen: the note names the session drop."""
    note = conftest._session_drop_note(FakeItem(FakePage(LOGIN)), FakeReport())
    assert note == conftest.SESSION_DROP_NOTE
    assert "401" in note
    assert "login screen" in note


def test_a_setup_failure_on_the_login_screen_gets_the_note_too():
    """A fixture layered on authenticated_page that navigates in setup bounces the same
    way; measured without a note on 09/18/2026, so the setup phase counts now."""
    note = conftest._session_drop_note(FakeItem(FakePage(LOGIN)), FakeReport(when="setup"))
    assert note == conftest.SESSION_DROP_NOTE


@pytest.mark.parametrize(("item", "rep"), [
    pytest.param(FakeItem(FakePage(MAPS)), FakeReport(), id="failed elsewhere"),
    pytest.param(FakeItem(FakePage(LOGIN)), FakeReport(failed=False), id="passed on login"),
    pytest.param(FakeItem(FakePage(LOGIN)), FakeReport(when="teardown"), id="teardown phase"),
    pytest.param(FakeItem(), FakeReport(), id="no page stashed"),
    pytest.param(FakeItem(FakePage(None)), FakeReport(), id="page already closed"),
])
def test_every_other_failure_shape_gets_nothing(item, rep):
    """Only a failed call whose open page shows the login screen is a session drop."""
    assert conftest._session_drop_note(item, rep) is None


class FakeLongrepr:
    def __init__(self):
        self.sections = []

    def addsection(self, name, content, sep="-"):
        self.sections.append((name, content))


class FakeOutcome:
    def __init__(self, rep):
        self._rep = rep

    def get_result(self):
        return self._rep


def _run_hook(item, rep):
    """Drive the hookwrapper the way pluggy does: enter, then hand it the outcome."""
    gen = conftest.pytest_runtest_makereport(item, call=None)
    next(gen)
    try:
        gen.send(FakeOutcome(rep))
    # the hookwrapper returns after the send; StopIteration is its normal end, not a fault
    except StopIteration:
        pass


def test_the_hook_appends_the_note_to_the_traceback():
    """A failed call on the login screen ends up with one 'session' section on its longrepr."""
    item, rep = FakeItem(FakePage(LOGIN)), FakeReport()
    rep.longrepr = FakeLongrepr()
    _run_hook(item, rep)
    assert rep.longrepr.sections == [("session", conftest.SESSION_DROP_NOTE)]
    assert item.rep_call is rep


def test_the_hook_leaves_other_failures_alone():
    """A failure elsewhere keeps a bare traceback, and the report is still stashed on the item."""
    item, rep = FakeItem(FakePage(MAPS)), FakeReport()
    rep.longrepr = FakeLongrepr()
    _run_hook(item, rep)
    assert rep.longrepr.sections == []
    assert item.rep_call is rep


def test_a_longrepr_without_addsection_is_left_as_it_is():
    """A skip or a string longrepr has no addsection; the hook must not crash on it."""
    item, rep = FakeItem(FakePage(LOGIN)), FakeReport()
    rep.longrepr = "plain text"
    _run_hook(item, rep)
    assert rep.longrepr == "plain text"
