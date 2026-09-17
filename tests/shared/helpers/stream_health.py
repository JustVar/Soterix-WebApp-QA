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
import shlex

MARKER = "livestream"
GUARD_ENV = "STREAM_GUARD"
DEFAULT_SECONDS = 8
_OFF = {"0", "off", "false", "no"}


def guard_enabled(environ=None) -> bool:
    environ = os.environ if environ is None else environ
    return (environ.get(GUARD_ENV) or "").strip().lower() not in _OFF


CHROME_ARGS_ENV = "CHROME_ARGS"


def chrome_args(environ=None) -> list[str]:
    """Extra Chrome launch flags for this session, from CHROME_ARGS.

    One variable feeds every Chrome the suite opens: the test session
    (conftest's browser_type_launch_args), this guard's decode check and
    tools/stream_probe.py, so what the guard measures is the browser the
    tests get. spartan1 sets it in deploy/spartan1/nightly.sh: Chrome on
    Linux decodes the tenants' H.265 only through the GPU's VA-API
    decoder, and only on its Wayland backend (measured 09/17/2026,
    deploy/spartan1/README.md). Empty when unset.
    """
    environ = os.environ if environ is None else environ
    return shlex.split(environ.get(CHROME_ARGS_ENV) or "")


def launch_args_with_chrome_flags(base: dict, environ=None) -> dict:
    """The session's browser launch options with CHROME_ARGS appended to
    their args; the options untouched when the variable is empty."""
    extra = chrome_args(environ)
    if not extra:
        return base
    return {**base, "args": [*base.get("args", []), *extra]}


# What a tile's player asks MediaSource for, per codec the tenant streams.
# The tags are the ones the tenant's init segments carry (stream_probe
# parses hvcC/avcC); H.265 is tried as both hvc1 and hev1.
MSE_TYPES = {
    "H.265": ['video/mp4; codecs="hvc1.1.6.L93.B0"', 'video/mp4; codecs="hev1.1.6.L93.B0"'],
    "H.264": ['video/mp4; codecs="avc1.42E01E"'],
}
# The tenant's codecType values seen so far: 8 on main gate (Newtown), 2 on
# the Thermal-* lenses (Videonetics, 09/17/2026); the socket's own init
# segment showed hvc1 for both, so both are H.265. The map is only the
# fallback: codec_from_frames reads the truth from the frames.
CODEC_TYPES = {8: "H.265", 2: "H.265"}


def codec_from_frames(frames: list) -> str | None:
    """The codec the media socket actually delivers, read from the fMP4
    init segment (ftyp+moov sample entry: hvc1/hev1 is H.265, avc1/avc3
    H.264) in the first binary frames; None when none parses. The channel
    parameter map is not to be trusted alone: an unmapped codecType read
    as "unknown", the decode check gave no verdict, the guard let the
    livestream tests run, and three of four workers died on a tile Linux
    Chrome could not decode (india, 09/17/2026, the four-hour run cap).
    """
    init = b"".join(f.get("data") or b"" for f in (frames or [])[:3] if f.get("opcode") == 2)
    if not init:
        return None
    try:
        from tools.stream_probe import parse_init_segment
        seen = (parse_init_segment(init) or {}).get("codec") or ""
    except Exception:  # why: an init segment that does not parse leaves the parameter map's codec in place
        return None
    if "265" in seen:
        return "H.265"
    if "264" in seen:
        return "H.264"
    return None


def measure_stream(camera_name: str | None, seconds: int = DEFAULT_SECONDS) -> dict:
    """Frames the box's media socket delivers for `camera_name` in `seconds`,
    and the codec the channel is configured to stream.

    Returns {'camera', 'channel_id', 'frames', 'seconds', 'codec', 'error',
    'note'}. Never raises: an exception becomes `error`, and the guard then
    skips nothing. Imports the probe lazily so a session with no livestream
    test pays nothing.
    """
    out: dict = {"camera": camera_name, "channel_id": None, "frames": 0,
                 "seconds": int(seconds), "codec": None, "error": None, "note": None}
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
        try:
            rows = api.post(f"/REST/site/{site_id}/getCameraStreamingParameters",
                            {"channelId": out["channel_id"], "streamType": 1})
            ct = (rows[0] if rows else {}).get("codecType")
            out["codec"] = CODEC_TYPES.get(ct, f"codecType {ct}") if ct is not None else None
        except Exception as e:  # why: the codec is a second fact; without it the decode check is skipped, the frame count still counts
            out["note"] = f"codec unread: {type(e).__name__}"
        rec = asyncio.run(direct_socket(media_url(site_id, out["channel_id"], 1),
                                        app_headers(token), float(seconds)))
        out["frames"] = sum(1 for f in rec.get("frames", []) if f.get("opcode") == 2)
        out["note"] = rec.get("error") or out["note"]
        seen = codec_from_frames(rec.get("frames", []))
        if seen:
            out["codec_param"] = out["codec"]
            out["codec"] = seen
    except Exception as e:  # why: the guard reports what stopped the measurement and skips nothing
        out["error"] = f"{type(e).__name__}: {e}"[:200]
    return out


def decode_check(codec: str | None, channel: str | None, headed: bool = False) -> dict:
    """Can the session's browser decode `codec` through MediaSource?

    Chrome on Windows and Mac decodes H.265 out of the box. Chrome on
    Linux has no software H.265 decoder: it answers false to
    MediaSource.isTypeSupported for hvc1 and hev1 unless it reaches a GPU
    decoder through VA-API, which it does only on its Wayland backend
    with the flags spartan1 sets in CHROME_ARGS (measured 09/17/2026,
    deploy/spartan1/README.md). So the check opens Chrome the way the
    tests will: the session's flags, headed when the session is. A tile's
    player on a browser that answered false never leaves readyState 0,
    whatever the socket delivers.
    Returns {'decodes': True | False | None, 'browser': str | None}; None
    when the codec is unknown or the check could not run.
    """
    types = MSE_TYPES.get(codec or "")
    if not types:
        return {"decodes": None, "browser": None}
    try:
        import platform

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(channel=channel or None, headless=not headed, args=chrome_args())
            page = browser.new_page()
            page.goto("about:blank")
            supported = page.evaluate(
                "types => types.some(t => window.MediaSource && MediaSource.isTypeSupported(t))", types)
            name = f"{'Chrome' if channel == 'chrome' else 'Chromium'} {browser.version} on {platform.system()}"
            browser.close()
        return {"decodes": bool(supported), "browser": name}
    except Exception as e:  # why: a check that could not run is 'unknown', which skips nothing
        return {"decodes": None, "browser": f"check failed: {type(e).__name__}"}


def assess(camera_name: str | None, channel: str | None, seconds: int = DEFAULT_SECONDS,
           headed: bool = False) -> dict:
    """The two facts the guard needs: the socket's frame count and whether
    the browser the tests get (channel, CHROME_ARGS, headed) can decode
    what the channel streams."""
    measure = measure_stream(camera_name, seconds)
    measure.update(decode_check(measure.get("codec"), channel, headed=headed) if not measure.get("error")
                   else {"decodes": None, "browser": None})
    return measure


def stream_skip_reason(measure: dict, box_name: str) -> str | None:
    """The skip text for a measurement, or None to let the tests run.

    None when frames arrived, and None when the measurement failed: an
    unmeasured box is not a dead one. The text carries the camera, the
    channel, the count and the sample length, so the report says what was
    seen and where, on whose measurement.
    """
    if measure.get("error"):
        return None
    tail = (f" (session stream-health guard, tests/shared/helpers/stream_health.py; "
            f"{GUARD_ENV}=off runs them anyway)")
    if measure.get("decodes") is False:
        return (f"box {box_name} streams {measure.get('codec')} on camera '{measure.get('camera')}' "
                f"and this browser ({measure.get('browser')}) cannot decode it: MediaSource.isTypeSupported "
                f"is false, so a tile's player never leaves readyState 0; the livestream tests need a "
                f"runner whose Chrome decodes {measure.get('codec')}: Windows, Mac, or spartan1 headed on "
                f"its Weston display (deploy/spartan1/README.md){tail}")
    if int(measure.get("frames") or 0) > 0 and measure.get("decodes") is None:
        # No verdict is not a green light: running a livestream test against
        # a tile the browser may never decode hangs the driver on the
        # after-test screenshot and ends the worker (three of four died,
        # india 09/17/2026). Skip, and say what could not be confirmed.
        why = (f"its codec is unknown ({measure.get('codec') or 'unread'})" if not MSE_TYPES.get(measure.get("codec") or "")
               else f"the decode check did not run ({measure.get('browser') or 'no browser answer'})")
        return (f"box {box_name} streams frames on camera '{measure.get('camera')}' but whether this "
                f"browser decodes them could not be confirmed: {why}. The livestream tests skip rather "
                f"than run against a tile that may never play{tail}")
    if int(measure.get("frames") or 0) > 0:
        return None
    note = f"; media socket: {measure['note']}" if measure.get("note") else ""
    return (f"box {box_name}: the media socket for camera '{measure.get('camera')}' "
            f"(channel {measure.get('channel_id')}) delivered 0 frames in "
            f"{measure.get('seconds')} s{note}; the livestream tests need frames{tail}")


def describe(measure: dict) -> str:
    """One line for the terminal, whatever the outcome."""
    if measure.get("error"):
        return f"[STREAM] guard could not measure '{measure.get('camera')}': {measure['error']} (no test skipped)"
    decode = ("" if measure.get("decodes") is None
              else f"; {measure.get('browser')} decodes {measure.get('codec')}: {'yes' if measure.get('decodes') else 'NO'}")
    return (f"[STREAM] '{measure.get('camera')}' (channel {measure.get('channel_id')}, {measure.get('codec') or 'codec unknown'}): "
            f"{measure.get('frames')} frames in {measure.get('seconds')} s{decode}")
