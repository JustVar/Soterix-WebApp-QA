"""Which camera a run drives, and why.

A run drives ONE camera, so its tests are comparable with each other and the
run page's history strip keeps its meaning. The run page reads the chosen
camera out of the run record and says when it changed, because a test that
fails on a camera it has never driven before is not the same news as a test
that started failing on the camera it always drove.

Three rules, in this order:

1. **A pin wins over everything.** TEST_CAMERA="Axis P3247-LV" reproduces a
   run exactly on the camera a person names.
2. **A run selected by a camera-specific marker gets that marker's camera.**
   Audio tests need a camera with a microphone, LPR tests need a plate
   camera. `pytest -m lpr` drives the camera config/env/ names for `lpr`
   under `camera_capabilities`. An empty map means the configured camera
   serves every marker.
3. **Everything else drives the configured camera**, test_camera_name in
   config/env/, or the camera the run read from the server when that key
   is blank (tests/shared/api/discovery.py).

The choice is deterministic, so every xdist worker and the controller reach
the same camera alone and the run record agrees with the tests.
"""
from __future__ import annotations

import os
import re

PIN_ENV = "TEST_CAMERA"

# Markers whose tests need a particular kind of camera. A server whose
# thermal, LPR or audio camera is a different device names it in
# camera_capabilities, or the marked tests drive a camera that cannot answer
# and the failure reads as an app bug.
CAMERA_SPECIFIC_MARKERS = ("lpr", "audio", "thermal", "ptz")


def pinned(environ=None) -> str | None:
    """The camera a person asked for by name, or None."""
    environ = os.environ if environ is None else environ
    name = (environ.get(PIN_ENV) or "").strip()
    return name or None


def capability_for(keywords, capabilities: dict | None) -> str | None:
    """The capability the run's markers demand, or None when they do not care.

    `capabilities` is config/env/ > camera_capabilities: a marker name mapped
    to the camera that satisfies it. `keywords` is what the run selects on:
    the words of the -m expression, or a test's own markers.
    """
    for name in sorted(capabilities or {}):
        if name in (keywords or {}):
            return name
    return None


def markexpr_words(markexpr: str | None) -> set[str]:
    """The marker names in a -m expression: 'lpr and not slow' -> {lpr, slow}."""
    return {w for w in re.findall(r"[A-Za-z_]\w*", markexpr or "") if w not in ("and", "or", "not")}


def choose(configured: str | None, environ=None,
           capability: str | None = None, capabilities: dict | None = None,
           configured_reason: str | None = None) -> dict:
    """Pick the camera and say why, as a record the run keeps.

    Never raises and never returns nothing: a capability nobody has listed
    falls back to the configured name, so a run that asks for what the server
    lacks leaves the suite exactly as it was and says so. `configured_reason`
    is how the configured camera came to be (the server named it), for the
    record.
    """
    def record(camera, reason):
        return {"camera": camera, "reason": reason, "configured": configured,
                "capability": capability}

    pin = pinned(environ)
    if pin:
        return record(pin, f"pinned by {PIN_ENV}")

    if capability:
        listed = (capabilities or {}).get(capability)
        listed = (listed[0] if listed else None) if isinstance(listed, list) else listed
        if listed:
            return record(str(listed).strip(), f"needs a camera with '{capability}'")
        return record(configured, f"no camera is listed for '{capability}' in "
                                  f"camera_capabilities; kept the configured camera")

    return record(configured, configured_reason or "the configured camera (test_camera_name in config/env/)")


def describe(pick: dict) -> str:
    """One line for the terminal summary, the way the stream guard prints its own."""
    if not pick:
        return "[CAMERA] no choice recorded"
    line = f"[CAMERA] '{pick.get('camera')}': {pick.get('reason')}"
    if pick.get("configured") and pick["configured"] != pick.get("camera"):
        line += f" (configured: '{pick['configured']}')"
    return line
