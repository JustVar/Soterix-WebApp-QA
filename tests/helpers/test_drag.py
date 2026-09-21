"""Pins for tests/shared/helpers/drag.py: which machine gets which drag, and what each one calls."""
from __future__ import annotations

import pytest

from tests.shared.helpers import drag


class FakePage:
    def __init__(self):
        self.calls = []

    def evaluate(self, script, args):
        self.calls.append((script, args))
        return 1


class FakeLocator:
    def __init__(self, page, name):
        self.page, self.name, self.dragged = page, name, []

    def element_handle(self, timeout=None):
        return f"handle:{self.name}"

    def drag_to(self, target, **kwargs):
        self.dragged.append((target.name, kwargs))


@pytest.mark.parametrize(("environ", "mode"), [
    ({}, "pointer"),
    ({"CHROME_ARGS": ""}, "pointer"),
    ({"CHROME_ARGS": "--ozone-platform=wayland"}, "js"),
    ({"CHROME_ARGS": "--foo --ozone-platform=wayland --bar"}, "js"),
    ({"CHROME_ARGS": "--ozone-platform=x11"}, "pointer"),
    ({"CHROME_ARGS": '--ozone-platform="wayland"'}, "js"),
    ({"CHROME_ARGS": "--ozone-platform-hint=wayland"}, "js"),
    ({"CHROME_ARGS": "--ozone-platform-hint=auto"}, "pointer"),
    ({"CHROME_ARGS": "--user-data-dir=/tmp/--ozone-platform=wayland-notes"}, "pointer"),
    ({"CHROME_ARGS": "--ozone-platform=wayland", "DRAG_MODE": "pointer"}, "pointer"),
    ({"DRAG_MODE": "JS"}, "js"),
    ({"DRAG_MODE": "sideways"}, "pointer"),
])
def test_only_chrome_on_wayland_gets_the_javascript_drag(environ, mode):
    """A laptop keeps the pointer drag; the box's Wayland flag selects JavaScript; DRAG_MODE overrides; a bad value changes nothing."""
    assert drag.drag_mode(environ) == mode


def test_the_pointer_drag_is_playwrights_own_and_passes_force_only_when_asked():
    """drop() calls drag_to with no extra argument, and with force=True for the forced retry."""
    page = FakePage()
    src, dst = FakeLocator(page, "camera"), FakeLocator(page, "tile")
    drag.drop(src, dst, environ={})
    drag.drop(src, dst, force=True, environ={})
    assert src.dragged == [("tile", {}), ("tile", {"force": True})]
    assert page.calls == []


def test_the_javascript_drag_fires_the_five_events_on_the_two_elements():
    """One evaluate call with the source and the target, in the order a browser fires a drag, and no pointer drag."""
    page = FakePage()
    src, dst = FakeLocator(page, "camera"), FakeLocator(page, "tile")
    drag.drop(src, dst, environ={"CHROME_ARGS": "--ozone-platform=wayland"})
    assert src.dragged == []
    (script, args), = page.calls
    assert args == ["handle:camera", "handle:tile"]
    order = [script.index(f"'{name}'") for name in ("dragstart", "dragenter", "dragover", "drop", "dragend")]
    assert order == sorted(order)
