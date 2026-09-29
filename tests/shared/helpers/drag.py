"""Drop one element on another, in the way that works on the machine that runs the test.

`drop(source, target)` does a real pointer drag (`Locator.drag_to`) on every
machine but one: headed Chrome on a Wayland display (a Linux runner started
with `--ozone-platform=wayland` in CHROME_ARGS). There, Chrome stops drawing in
the middle of some drags and never answers again. The drag call does not
return, its timeout does not fire, and each later call on that page hangs too,
the after-test screenshot included.

Measured on such a runner with the LPR camera playback class:
- Pointer drag: 4 of 4 class runs hung, each time inside the drag that plays
  the camera. Chrome's Wayland log shows 60 frames a second, then a frame
  callback from the display that Chrome does not answer, then silence. The
  display is healthy. No drag request reaches it, so it is not the display's
  drag-and-drop either.
- The same HTML5 drag events fired from JavaScript: 5 of 5 class runs finished,
  25 of 25 streams played, no hang. The app's drop handler accepts them for a
  camera row. It does not for an LPR widget card (the drop landed nothing), so
  try an element on a Wayland runner before you move its drag here.

The Views page object's `mouse_drag` and the 3 `drag_to` calls of the Views
tests use the same rule. Measured on the same runner with test_views_drag_drop
and test_views_subtabs: 16 of 16 JavaScript drops landed (a camera, a location,
a map, a channel, a saved view, an insight), no fallback was used, and no run
hung.

Windows Chrome ran the class 2 times with the pointer drag and no hang, so each
other machine keeps it: a pointer drag is what a user does, and it is the
stronger check.

`DRAG_MODE=js` or `DRAG_MODE=pointer` overrides the choice, for a diagnosis.
"""
from __future__ import annotations

import os
import shlex
from collections.abc import Mapping
from typing import Any

WAYLAND_FLAG = "--ozone-platform=wayland"
MODE_ENV = "DRAG_MODE"

# dragstart lets the app fill the DataTransfer, drop lets it read it back.
# The events carry the centre of their element, as a pointer drag's would.
JS_DROP = """([src, dst]) => {
  const dt = new DataTransfer();
  const at = el => { const r = el.getBoundingClientRect(); return {clientX: r.x + r.width / 2, clientY: r.y + r.height / 2}; };
  const fire = (el, type) => el.dispatchEvent(new DragEvent(type,
    Object.assign({bubbles: true, cancelable: true, composed: true, dataTransfer: dt}, at(el))));
  fire(src, 'dragstart'); fire(dst, 'dragenter'); fire(dst, 'dragover'); fire(dst, 'drop'); fire(src, 'dragend');
  return dt.types.length;
}"""


def drag_mode(environ: Mapping[str, str] | None = None) -> str:
    """'js' or 'pointer' for this process: the override, else 'js' only for Chrome on Wayland."""
    env = os.environ if environ is None else environ
    forced = (env.get(MODE_ENV) or "").strip().lower()
    if forced in ("js", "pointer"):
        return forced
    # split as the launch does (stream_health.chrome_args): --ozone-platform="wayland" reaches
    # Chrome with no quotes, and --ozone-platform-hint=wayland selects it too
    try:
        flags = shlex.split(env.get("CHROME_ARGS") or "")
    # an unbalanced quote: the launch reads the same text and fails loud there, so this only picks a mode
    except ValueError:
        flags = (env.get("CHROME_ARGS") or "").split()
    # hint=auto is not read as Wayland: on a laptop it selects what the desktop has
    on_wayland = any(f in (WAYLAND_FLAG, "--ozone-platform-hint=wayland") for f in flags)
    return "js" if on_wayland else "pointer"


def js_drop(source: Any, target: Any) -> int:
    """Fire the drag events from JavaScript. Returns how many data kinds the app put on the drag."""
    src = source.element_handle(timeout=10000)
    dst = target.element_handle(timeout=10000)
    kinds = source.page.evaluate(JS_DROP, [src, dst])
    print(f"[DRAG] drag events fired from JavaScript; data kinds set by the app: {kinds}")
    return int(kinds or 0)


def drop(source: Any, target: Any, *, force: bool = False, environ: Mapping[str, str] | None = None) -> None:
    """Drop `source` on `target`. The caller proves the result: a drop that lands nothing raises nothing here."""
    if drag_mode(environ) == "js":
        js_drop(source, target)
    elif force:
        source.drag_to(target, force=True)
    else:
        source.drag_to(target)
