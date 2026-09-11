"""The session stream-health guard: does the box's test camera deliver
frames right now?

Nine of the seventeen web-app failures in the 09/11/2026 full US run were
one tenant condition read nine ways: the QA host delivered 0 frames on
every channel (the media API answered 1506 'Failed to read response from
the IVMS server'), so Save on a view sent no request, the player never
left readyState 0, a tile never streamed and the bookmarks panel listed
nothing. Each test timed out on its own wait and reported its own
symptom; nothing named the cause.

This module measures the cause once per session, the way
tools/stream_probe.py --health --no-browser does: one media socket from
Python to the box's configured test camera, a few seconds, count the
binary frames. conftest.py skips the tests marked `livestream` with the
measurement when the count is 0. A measurement that could not be made
(no login, no such channel, an exception) skips nothing and is printed:
a guard that cannot see must not hide tests.

The same rule as the box `without` map and require_items: a skip names a
measured fact, never a guess. STREAM_GUARD=off runs the tests anyway.
"""
from __future__ import annotations

import os

MARKER = "livestream"
GUARD_ENV = "STREAM_GUARD"
DEFAULT_SECONDS = 8
_OFF = {"0", "off", "false", "no"}


def guard_enabled(environ=None) -> bool:
    environ = os.environ if environ is None else environ
    return (environ.get(GUARD_ENV) or "").strip().lower() not in _OFF


def measure_stream(camera_name: str | None, seconds: int = DEFAULT_SECONDS) -> dict:
    """Frames the box's media socket delivers for `camera_name` in `seconds`.

    Returns {'camera', 'channel_id', 'frames', 'seconds', 'error', 'note'}.
    Never raises: an exception becomes `error`, and the guard then skips
    nothing. Imports the probe lazily so a session with no livestream
    test pays nothing.
    """
    out: dict = {"camera": camera_name, "channel_id": None, "frames": 0,
                 "seconds": int(seconds), "error": None, "note": None}
    if not camera_name:
        out["error"] = "no test_camera_name in config/env/ for this box"
        return out
    try:
        import asyncio

        from config.base_config import config, get_credentials
        from tests.shared.api.client import InternalApi
        from tools.stream_probe import app_headers, direct_socket, media_url

        creds = get_credentials()
        site_id = int(creds["site_id"])
        api = InternalApi(config["base_url"], site_id)
        token = api.login(creds["email"], creds["password"])
        channels = api.get(f"/REST/site/{site_id}/channel")
        wanted = camera_name.strip().lower()
        match = [c for c in channels if (c.get("name") or "").strip().lower() == wanted]
        if not match:
            match = [c for c in channels if wanted in (c.get("name") or "").lower()]
        if not match:
            out["error"] = (f"no channel named '{camera_name}' on site {site_id} "
                            f"({len(channels)} channels)")
            return out
        out["channel_id"] = int(match[0]["id"])
        rec = asyncio.run(direct_socket(media_url(site_id, out["channel_id"], 1),
                                        app_headers(token), float(seconds)))
        out["frames"] = sum(1 for f in rec.get("frames", []) if f.get("opcode") == 2)
        out["note"] = rec.get("error")
    except Exception as e:  # noqa: BLE001 - why: the guard reports what stopped the measurement and skips nothing
        out["error"] = f"{type(e).__name__}: {e}"[:200]
    return out


def stream_skip_reason(measure: dict, box_name: str) -> str | None:
    """The skip text for a measurement, or None to let the tests run.

    None when frames arrived, and None when the measurement failed: an
    unmeasured box is not a dead one. The text carries the camera, the
    channel, the count and the sample length, so the report says what was
    seen and where, on whose measurement.
    """
    if measure.get("error") or int(measure.get("frames") or 0) > 0:
        return None
    note = f"; media socket: {measure['note']}" if measure.get("note") else ""
    return (f"box {box_name}: the media socket for camera '{measure.get('camera')}' "
            f"(channel {measure.get('channel_id')}) delivered 0 frames in "
            f"{measure.get('seconds')} s{note}; the livestream tests need frames "
            f"(session stream-health guard, tests/shared/helpers/stream_health.py; "
            f"{GUARD_ENV}=off runs them anyway)")


def describe(measure: dict) -> str:
    """One line for the terminal, whatever the outcome."""
    if measure.get("error"):
        return f"[STREAM] guard could not measure '{measure.get('camera')}': {measure['error']} (no test skipped)"
    return (f"[STREAM] '{measure.get('camera')}' (channel {measure.get('channel_id')}): "
            f"{measure.get('frames')} frames in {measure.get('seconds')} s")
