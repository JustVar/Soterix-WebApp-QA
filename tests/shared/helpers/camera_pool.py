"""Which camera a run drives, and why.

Until now every run drove one camera per box, named in config/env/. The US
tenant has 16 online cameras across 7 vendors (Avigilon, Axis, Hanwha, Uniview,
Vivotek, i-Pro, Onvif), and the suite exercised one of them, so a bug in any
other vendor's playback was invisible to us. Customers use all of them.

Three rules, in this order:

1. **A test that needs a particular camera gets that camera.** Audio tests need
   a camera with a microphone, LPR tests need a plate camera. Those are named in
   config/env/ under `camera_capabilities` and are never rotated.
2. **A pin wins over everything.** TEST_CAMERA="Axis P3247-LV" reproduces a run
   exactly, which is what makes a rotated failure worth reporting.
3. **Everything else rotates, one camera per run, by the day.** Not at random:
   random cannot be reasoned about, can miss a camera for weeks, and makes a
   red result unreadable. A run drives ONE camera so its tests are comparable
   with each other, and the day picks it so every run that day agrees and the
   nightly walks the pool.

The rotation is deliberately coarse. The run page reads the chosen camera out of
the run record and says when it changed, because a test that fails on a camera
it has never driven before is not the same news as a test that started failing
on the camera it always drove.
"""
from __future__ import annotations

import os
from datetime import UTC, date, datetime

PIN_ENV = "TEST_CAMERA"
ROTATE_ENV = "TEST_CAMERA_ROTATE"
_OFF = {"0", "off", "false", "no"}

# Markers whose tests need a particular kind of camera. A box that rotates must
# name cameras for every one of these its tests actually run, or the rotation
# points a plate test at a camera with no plates and the failure reads as an app
# bug. test_camera_pool.py holds a box to this.
CAMERA_SPECIFIC_MARKERS = ("lpr", "audio", "thermal", "ptz")


def rotation_enabled(environ=None) -> bool:
    """Rotation is OFF until the run page names the camera it drove.

    Deliberate sequencing, not caution for its own sake. Rotating first would
    make a red test ambiguous: nobody could tell a regression from a camera this
    test has never driven before, and an unreadable suite is worse than a
    narrow one. Turn it on per run with TEST_CAMERA_ROTATE=1 to try it.

    Flip this default to on once the run page carries the camera and marks it
    when it changes (register row 129).
    """
    environ = os.environ if environ is None else environ
    value = (environ.get(ROTATE_ENV) or "").strip().lower()
    return bool(value) and value not in _OFF


def pinned(environ=None) -> str | None:
    """The camera a person asked for by name, or None."""
    environ = os.environ if environ is None else environ
    name = (environ.get(PIN_ENV) or "").strip()
    return name or None


def rotation_index(when: date | datetime | None = None) -> int:
    """A number that changes once a day and never goes backwards.

    The date, not a random seed or a run counter: two runs on one day pick the
    same camera, so a morning failure can be re-run in the afternoon and mean
    the same thing, and nobody has to store a counter anywhere.
    """
    when = when or datetime.now(UTC).date()
    if isinstance(when, datetime):
        when = when.date()
    return when.toordinal()


def online_names(pool) -> list[str]:
    """The online cameras of a probe's channel list, in a stable order.

    Sorted by name, not by the order the tenant returned them: the tenant's
    order changes when a camera is added, which would silently re-point the
    rotation at everything.
    """
    out = []
    for ch in pool or []:
        if not isinstance(ch, dict) or not ch.get("online"):
            continue
        name = (ch.get("name") or "").strip()
        if name:
            out.append(name)
    return sorted(set(out))


def capability_for(keywords, capabilities: dict | None) -> str | None:
    """The capability this test's markers demand, or None when it does not care.

    `capabilities` is config/env/ > camera_capabilities: a marker name mapped to
    the cameras that satisfy it. A test carrying that marker is not rotated.
    """
    for name in sorted(capabilities or {}):
        if name in (keywords or {}):
            return name
    return None


def choose(pool, configured: str | None, when=None, environ=None,
           capability: str | None = None, capabilities: dict | None = None) -> dict:
    """Pick the camera and say why, as a record the run keeps.

    Never raises and never returns nothing: an unmeasured pool, an empty one or
    a capability with no online camera all fall back to the configured name, so
    a rotation that cannot run leaves the suite exactly as it was.
    """
    def record(camera, reason, **extra):
        return {"camera": camera, "reason": reason, "configured": configured,
                "rotated": False, "capability": capability, **extra}

    pin = pinned(environ)
    if pin:
        return record(pin, f"pinned by {PIN_ENV}")

    if capability:
        allowed = [c for c in ((capabilities or {}).get(capability) or []) if c]
        online = set(online_names(pool))
        # Only filter by the pool when there IS a pool: an unmeasured pool must
        # not turn every capability into a fallback.
        usable = [c for c in allowed if c in online] if online else allowed
        if usable:
            return record(sorted(usable)[0], f"needs a camera with '{capability}'",
                          choices=len(usable))
        if allowed:
            return record(configured, f"no online camera has '{capability}'; "
                                      f"kept the configured camera", choices=0)
        return record(configured, f"no camera is listed for '{capability}' in "
                                  f"camera_capabilities; kept the configured camera")

    if not rotation_enabled(environ):
        return record(configured, f"rotation is off ({ROTATE_ENV})")

    names = online_names(pool)
    if not names:
        return record(configured, "no online camera was measured; kept the configured camera")
    if len(names) == 1:
        return record(names[0], "1 online camera, so nothing to rotate", pool=1)

    index = rotation_index(when)
    chosen = names[index % len(names)]
    return record(chosen, f"rotated over {len(names)} online cameras (day {index})",
                  rotated=True, pool=len(names), index=index % len(names))


def pool_path(box: str, root=None):
    """Where a box's measured pool is kept."""
    from pathlib import Path
    # parents[3] is the repo root: this file is tests/shared/helpers/camera_pool.py,
    # so parents[2] is `tests` and pointed the lookup at tests/tests/data, which
    # found nothing and fell back silently to the configured camera.
    root = Path(root) if root else Path(__file__).resolve().parents[3]
    return root / "tests" / "data" / f"camera_pool_{(box or '').strip().lower()}.json"


def load_pool(box: str, root=None) -> list:
    """The box's last measured channel list, or [] when there is none.

    Read from a file, not measured here. Measuring 22 cameras costs 20 s, which
    a run does not spend to learn something that changes weekly, and the file is
    committed so a rotation is reviewable and repeatable.

    A stale file cannot cause a false failure: the stream guard measures THE
    CHOSEN camera at session start, and skips the livestream tests with the
    frame count when it is dark. Refresh with

        BOX=us python tools/stream_probe.py --health --all-cameras --no-browser \\
            --seconds 4 --json tests/data/camera_pool_us.json
    """
    import json
    path = pool_path(box, root)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):  # why: a box with no pool file, or a half-written one, must leave the suite as it was rather than take the run down; the caller reads [] as "unmeasured", keeps the configured camera and says so
        return []
    channels = data.get("channels") if isinstance(data, dict) else data
    return channels if isinstance(channels, list) else []


def describe(pick: dict) -> str:
    """One line for the terminal summary, the way the stream guard prints its own."""
    if not pick:
        return "[CAMERA] no choice recorded"
    line = f"[CAMERA] '{pick.get('camera')}': {pick.get('reason')}"
    if pick.get("rotated") and pick.get("configured") and pick["configured"] != pick.get("camera"):
        line += f" (configured: '{pick['configured']}')"
    return line
