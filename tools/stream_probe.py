#!/usr/bin/env python3
"""Report what a live camera tile actually receives, next to what the API says it should.

    python tools/stream_probe.py --camera "main gate"
    python tools/stream_probe.py --camera "main gate" --fullscreen --json out.json

Read-only: it logs in, drops the camera on a Views tile, watches the media
WebSocket for a few seconds, and reads channel settings from the internal
API. Nothing on the tenant is changed.

How the stream is identified (probed 2026-08-25, docs/QA_THINGS_TO_KNOW.md
"Live stream delivery"):

  * The tile opens wss://media.example.invalid/v3/api/ws?name=
    <site>/<channel>/<app>/<live>/<stream>/<timestamp>/<uuid> from the
    main thread and sends {"type":"mse","value":""}.
  * The server answers one TEXT frame naming the MediaSource mime type,
    e.g. video/mp4; codecs="hvc1.1.6.L153.B0,flac", then BINARY frames:
    an fMP4 init segment (ftyp + moov) and moof/mdat fragments, with JSON
    text frames of per-frame counters in between.
  * The codec, coded size and audio track come from the moov sample
    entries (hev1/hvc1 = H.265, avc1/avc3 = H.264, fLaC/mp4a = audio).
    The exact picture size comes from the SPS inside hvcC/avcC. Frame rate
    and bitrate come from the moof fragments' tfdt/trun/mdat.

Frames are captured over CDP (Network.webSocketFrameReceived); Playwright's
page.on("websocket") did not surface them in an earlier probe.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import struct
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")

from playwright.sync_api import sync_playwright  # noqa: E402

from config.base_config import config  # noqa: E402
from tests.shared.api.client import ApiError, InternalApi  # noqa: E402
from tests.shared.pages.login_page import LoginPage  # noqa: E402
from tests.shared.pages.views_page import ViewsPage  # noqa: E402

TILE = "[class*='video_container'][class*='new_video_player']"
MEDIA_WS = "/v3/api/ws"
# /REST/site/recordingstream names the stream indexes 0..6; the tile
# opens index 1 and full screen index 0 (matched by resolution, 08/25)
STREAM_NAMES = {0: "major", 1: "minor", 2: "third", 3: "jpeg snap", 6: "fourth"}
VIDEO_ENTRIES = ("hvc1", "hev1", "avc1", "avc3")
AUDIO_ENTRIES = ("fLaC", "mp4a", "Opus", "ulaw", "alaw")

# Main-thread hook: records the MediaSource mime the app registers and
# the first text frames of every WebSocket, so the mime announcement is
# available even if CDP capture starts late.
HOOK = r"""
(() => {
  const P = window.__streamProbe = { ws: [], mse: [] };
  const OWS = window.WebSocket;
  window.WebSocket = function(url, protocols) {
    const ws = protocols === undefined ? new OWS(url) : new OWS(url, protocols);
    const rec = { url: String(url), recv: 0, sent: [], text: [] };
    P.ws.push(rec);
    const osend = ws.send.bind(ws);
    ws.send = function(d) {
      if (rec.sent.length < 10) rec.sent.push(typeof d === 'string' ? d.slice(0, 300) : '<binary>');
      return osend(d);
    };
    ws.addEventListener('message', (ev) => {
      rec.recv++;
      if (typeof ev.data === 'string' && rec.text.length < 5) rec.text.push(ev.data.slice(0, 300));
    });
    return ws;
  };
  window.WebSocket.prototype = OWS.prototype;
  for (const k of ['CONNECTING', 'OPEN', 'CLOSING', 'CLOSED']) window.WebSocket[k] = OWS[k];
  const add = MediaSource.prototype.addSourceBuffer;
  MediaSource.prototype.addSourceBuffer = function(mime) { P.mse.push(mime); return add.call(this, mime); };
})();
"""

VIDEO_STATE_BODY = """
Array.from(root.querySelectorAll('video')).map(v => ({
    cls: v.className, ready: v.readyState, w: v.videoWidth, h: v.videoHeight,
    muted: v.muted, t: v.currentTime,
    frames: v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality().totalVideoFrames : null,
    audioBytes: v.webkitAudioDecodedByteCount}))
"""
VIDEO_STATE_JS = "() => { const root = document; return (" + VIDEO_STATE_BODY.strip() + "); }"
TILE_VIDEO_STATE_JS = "root => (" + VIDEO_STATE_BODY.strip() + ")"

# visible icon assets only: the tile also holds a data-URI snapshot <img>
ICONS_JS = """
(sel) => Array.from(document.querySelectorAll(sel + ' img'))
    .filter(i => i.offsetWidth > 0 && /\\.(svg|png)/.test(i.getAttribute('src') || ''))
    .map(i => (i.getAttribute('src') || '').split('/').pop().split('.')[0])
"""


# ---------------------------------------------------------------- bits ---
class Bits:
    """MSB-first bit reader with Exp-Golomb helpers (SPS parsing)."""

    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def u(self, n: int) -> int:
        v = 0
        for _ in range(n):
            byte = self.data[self.pos >> 3]
            v = (v << 1) | ((byte >> (7 - (self.pos & 7))) & 1)
            self.pos += 1
        return v

    def ue(self) -> int:
        zeros = 0
        while self.u(1) == 0:
            zeros += 1
            if zeros > 32:
                raise ValueError("bad exp-golomb")
        return (1 << zeros) - 1 + self.u(zeros) if zeros else 0

    def se(self) -> int:
        k = self.ue()
        return (k + 1) // 2 if k % 2 else -(k // 2)


def unescape_nal(nal: bytes) -> bytes:
    """Drop emulation-prevention bytes (00 00 03 -> 00 00)."""
    out = bytearray()
    zeros = 0
    for b in nal:
        if zeros >= 2 and b == 3:
            zeros = 0
            continue
        out.append(b)
        zeros = zeros + 1 if b == 0 else 0
    return bytes(out)


def parse_hevc_sps(nal: bytes) -> dict:
    """Picture size and level from an H.265 SPS NAL (with its 2-byte header)."""
    r = Bits(unescape_nal(nal[2:]))
    r.u(4)
    max_sub_layers = r.u(3)
    r.u(1)
    r.u(2)
    tier = r.u(1)
    profile_idc = r.u(5)
    r.u(32)
    r.u(48)
    level_idc = r.u(8)
    present = [(r.u(1), r.u(1)) for _ in range(max_sub_layers)]
    if max_sub_layers:
        for _ in range(max_sub_layers, 8):
            r.u(2)
    for prof, lvl in present:
        if prof:
            r.u(88)
        if lvl:
            r.u(8)
    r.ue()
    chroma = r.ue()
    if chroma == 3:
        r.u(1)
    width = r.ue()
    height = r.ue()
    if r.u(1):
        sub_w = 2 if chroma in (1, 2) else 1
        sub_h = 2 if chroma == 1 else 1
        left, right, top, bottom = r.ue(), r.ue(), r.ue(), r.ue()
        width -= sub_w * (left + right)
        height -= sub_h * (top + bottom)
    return {"width": width, "height": height, "profile_idc": profile_idc,
            "tier": tier, "level": level_idc / 30}


def parse_h264_sps(nal: bytes) -> dict:
    """Picture size and level from an H.264 SPS NAL (with its 1-byte header)."""
    r = Bits(unescape_nal(nal[1:]))
    profile_idc = r.u(8)
    r.u(8)
    level_idc = r.u(8)
    r.ue()
    chroma = 1
    if profile_idc in (100, 110, 122, 244, 44, 83, 86, 118, 128, 138, 139, 134, 135):
        chroma = r.ue()
        if chroma == 3:
            r.u(1)
        r.ue()
        r.ue()
        r.u(1)
        if r.u(1):
            for i in range(8 if chroma != 3 else 12):
                if r.u(1):
                    last, nxt = 8, 8
                    for _ in range(16 if i < 6 else 64):
                        if nxt:
                            nxt = (last + r.se() + 256) % 256
                        last = last if nxt == 0 else nxt
    r.ue()
    poc_type = r.ue()
    if poc_type == 0:
        r.ue()
    elif poc_type == 1:
        r.u(1)
        r.se()
        r.se()
        for _ in range(r.ue()):
            r.se()
    r.ue()
    r.u(1)
    width_mbs = r.ue() + 1
    height_units = r.ue() + 1
    frame_mbs_only = r.u(1)
    if not frame_mbs_only:
        r.u(1)
    r.u(1)
    width = width_mbs * 16
    height = (2 - frame_mbs_only) * height_units * 16
    if r.u(1):
        unit_x = 1 if chroma in (0, 3) else 2
        unit_y = (1 if chroma in (0, 3) else 2) * (2 - frame_mbs_only)
        left, right, top, bottom = r.ue(), r.ue(), r.ue(), r.ue()
        width -= unit_x * (left + right)
        height -= unit_y * (top + bottom)
    return {"width": width, "height": height, "profile_idc": profile_idc, "level": level_idc / 10}


# ----------------------------------------------------------------- mp4 ---
def boxes(buf: bytes, start: int = 0, end: int | None = None):
    """Yield (type, header_size, body_start, box_end) for the boxes in buf[start:end]."""
    end = len(buf) if end is None else end
    off = start
    while off + 8 <= end:
        size, typ = struct.unpack(">I4s", buf[off:off + 8])
        hdr = 8
        if size == 1:
            size = struct.unpack(">Q", buf[off + 8:off + 16])[0]
            hdr = 16
        elif size == 0:
            size = end - off
        if size < 8 or off + size > end:
            return
        yield typ.decode("latin1", "replace"), hdr, off + hdr, off + size
        off += size


def find_box(buf: bytes, path: list[str], start: int = 0, end: int | None = None):
    """Return (body_start, box_end) of the first box at the nested path."""
    for typ, _hdr, body, box_end in boxes(buf, start, end):
        if typ == path[0]:
            if len(path) == 1:
                return body, box_end
            return find_box(buf, path[1:], body, box_end)
    return None


def parse_init_segment(buf: bytes) -> dict:
    """Codec, coded size, SPS size, audio entry and track map from ftyp+moov."""
    out = {"tracks": {}, "video": None, "audio": None}
    ftyp = find_box(buf, ["ftyp"])
    if ftyp:
        out["brand"] = buf[ftyp[0]:ftyp[0] + 4].decode("latin1")
    moov = find_box(buf, ["moov"])
    if not moov:
        return out
    for typ, _hdr, body, box_end in boxes(buf, *moov):
        if typ != "trak":
            continue
        tkhd = find_box(buf, ["tkhd"], body, box_end)
        version = buf[tkhd[0]]
        track_id = struct.unpack(">I", buf[tkhd[0] + (20 if version else 12):][:4])[0]
        hdlr = find_box(buf, ["mdia", "hdlr"], body, box_end)
        handler = buf[hdlr[0] + 8:hdlr[0] + 12].decode("latin1")
        mdhd = find_box(buf, ["mdia", "mdhd"], body, box_end)
        mv = buf[mdhd[0]]
        timescale = struct.unpack(">I", buf[mdhd[0] + (20 if mv else 12):][:4])[0]
        out["tracks"][track_id] = {"handler": handler, "timescale": timescale}
        stsd = find_box(buf, ["mdia", "minf", "stbl", "stsd"], body, box_end)
        for entry, _h, ebody, eend in boxes(buf, stsd[0] + 8, stsd[1]):
            if entry in VIDEO_ENTRIES:
                w, h = struct.unpack(">HH", buf[ebody + 24:ebody + 28])
                video = {"entry": entry, "coded_width": w, "coded_height": h, "track": track_id}
                for child, _ch, cbody, cend in boxes(buf, ebody + 78, eend):
                    if child == "hvcC":
                        video.update(_hvcc(buf[cbody:cend]))
                    elif child == "avcC":
                        video.update(_avcc(buf[cbody:cend]))
                out["video"] = video
            elif entry in AUDIO_ENTRIES:
                channels, bits = struct.unpack(">HH", buf[ebody + 16:ebody + 20])
                rate = struct.unpack(">I", buf[ebody + 24:ebody + 28])[0] >> 16
                out["audio"] = {"entry": entry, "channels": channels, "bits": bits,
                                "sample_rate": rate, "track": track_id}
    return out


def _hvcc(c: bytes) -> dict:
    info = {"codec": "H.265 (HEVC)", "hvcc_profile_idc": c[1] & 0x1F, "hvcc_level_idc": c[12]}
    off = 23
    for _ in range(c[22]):
        nal_type = c[off] & 0x3F
        count = struct.unpack(">H", c[off + 1:off + 3])[0]
        off += 3
        for _ in range(count):
            length = struct.unpack(">H", c[off:off + 2])[0]
            nal = c[off + 2:off + 2 + length]
            off += 2 + length
            if nal_type == 33 and "sps" not in info:
                try:
                    info["sps"] = parse_hevc_sps(nal)
                except Exception as e:  # a parse miss is a fact, not a crash
                    info["sps_error"] = str(e)
    return info


def _avcc(c: bytes) -> dict:
    info = {"codec": "H.264 (AVC)", "avcc_profile_idc": c[1], "avcc_level_idc": c[3]}
    off = 6
    for _ in range(c[5] & 0x1F):
        length = struct.unpack(">H", c[off:off + 2])[0]
        nal = c[off + 2:off + 2 + length]
        off += 2 + length
        if "sps" not in info:
            try:
                info["sps"] = parse_h264_sps(nal)
            except Exception as e:  # a parse miss is a fact, not a crash
                info["sps_error"] = str(e)
    return info


def parse_fragment(buf: bytes) -> dict | None:
    """track id, decode time, sample count and mdat size of one moof+mdat frame."""
    moof = find_box(buf, ["moof"])
    if not moof:
        return None
    traf = find_box(buf, ["traf"], *moof)
    if not traf:
        return None
    tfhd = find_box(buf, ["tfhd"], *traf)
    tfdt = find_box(buf, ["tfdt"], *traf)
    trun = find_box(buf, ["trun"], *traf)
    frag = {"track": struct.unpack(">I", buf[tfhd[0] + 4:tfhd[0] + 8])[0]}
    if tfdt:
        v = buf[tfdt[0]]
        frag["time"] = (struct.unpack(">Q", buf[tfdt[0] + 4:tfdt[0] + 12])[0] if v
                        else struct.unpack(">I", buf[tfdt[0] + 4:tfdt[0] + 8])[0])
    frag["samples"] = struct.unpack(">I", buf[trun[0] + 4:trun[0] + 8])[0] if trun else 0
    for typ, _hdr, body, box_end in boxes(buf):
        if typ == "mdat":
            frag["mdat"] = box_end - body
    return frag


def summarize_frames(frames: list[dict]) -> dict:
    """Split one socket's frames into the mime line, init segment and per-track stats."""
    summary = {"mime": None, "init": None, "text_frames": 0, "binary_frames": 0, "tracks": {}}
    init_bytes = None
    for f in frames:
        if f["opcode"] != 2:
            summary["text_frames"] += 1
            if not summary["mime"]:
                try:
                    msg = json.loads(f["text"])
                except ValueError:
                    msg = None
                if isinstance(msg, dict) and msg.get("type") == "mse" and msg.get("value"):
                    summary["mime"] = msg["value"]
            continue
        summary["binary_frames"] += 1
        data = f["data"]
        if data[4:8] == b"ftyp" and init_bytes is None:
            init_bytes = data
            summary["init"] = parse_init_segment(data)
            continue
        frag = parse_fragment(data)
        if not frag:
            continue
        t = summary["tracks"].setdefault(frag["track"], {"fragments": 0, "samples": 0, "bytes": 0,
                                                          "first_time": None, "last_time": None})
        t["fragments"] += 1
        t["samples"] += frag.get("samples", 0)
        t["bytes"] += frag.get("mdat", 0)
        if "time" in frag:
            t["first_time"] = frag["time"] if t["first_time"] is None else t["first_time"]
            t["last_time"] = frag["time"]
    init = summary["init"] or {}
    for track_id, t in summary["tracks"].items():
        meta = init.get("tracks", {}).get(track_id, {})
        t["handler"] = meta.get("handler")
        ts = meta.get("timescale")
        if ts and t["first_time"] is not None and t["last_time"] != t["first_time"]:
            span = (t["last_time"] - t["first_time"]) / ts
            # the last fragment's own duration is unknown, so span covers
            # samples - last fragment; close enough for a rate
            t["seconds"] = round(span, 2)
            t["rate"] = round((t["samples"] - 1) / span, 2) if t["samples"] > 1 else None
            t["kbps"] = round(t["bytes"] * 8 / span / 1000) if span else None
    return summary


# ------------------------------------------------------------------ api ---
def api_facts(api: InternalApi, site_id: int, camera: str) -> dict:
    """Channel record and configured stream settings for the named camera."""
    channels = api.get(f"/REST/site/{site_id}/channel")
    match = [c for c in channels if c.get("name", "").strip().lower() == camera.strip().lower()]
    if not match:
        match = [c for c in channels if camera.lower() in c.get("name", "").lower()]
    if not match:
        names = sorted(c.get("name") for c in channels)
        raise SystemExit(f"No channel named '{camera}' on site {site_id}. Present: {names}")
    ch = match[0]
    facts = {
        "channel_id": ch["id"], "name": ch["name"], "model": ch.get("model"),
        "model_number": ch.get("param4"), "audio_grabbing": ch.get("audioGrabbing"),
        "channel_type": ch.get("channelType"), "configuration_type": ch.get("configurationType"),
        "streams": {}, "audio": None, "presets": None, "ptz_position": None, "errors": [],
    }
    cid = ch["id"]
    for stream in (0, 1):
        try:
            rows = api.post(f"/REST/site/{site_id}/getCameraStreamingParameters",
                            {"channelId": cid, "streamType": stream})
            facts["streams"][stream] = rows[0] if rows else None
        except ApiError as e:
            facts["errors"].append(f"getCameraStreamingParameters stream {stream}: {e}")
    try:
        rows = api.post(f"/REST/site/{site_id}/camera/audio/streaming",
                        {"channelId": cid, "streamType": 0})
        facts["audio"] = rows[0] if rows else None
    except ApiError as e:
        facts["errors"].append(f"camera/audio/streaming: {e}")
    try:
        facts["presets"] = api.get(f"/REST/site/{site_id}/channel/{cid}/preset")
    except ApiError as e:
        facts["errors"].append(f"preset: {e}")
    try:
        rows = api.get(f"/REST/site/{site_id}/channel/{cid}/getcurrentptzposition")
        facts["ptz_position"] = rows[0] if rows else None
    except ApiError as e:
        facts["errors"].append(f"getcurrentptzposition: {e}")
    return facts


# -------------------------------------------------------------- browser ---
def parse_ws_name(url: str) -> dict:
    """site/channel/app/live/stream/timestamp/uuid from the media socket url."""
    m = re.search(r"[?&]name=([^&]+)", url)
    if not m:
        return {}
    parts = m.group(1).replace("%2F", "/").split("/")
    keys = ["site", "channel", "app", "live", "stream", "timestamp", "uuid"]
    return dict(zip(keys, parts, strict=False))


def browser_facts(camera: str, seconds: int, fullscreen: bool, headed: bool,
                  channel: str | None = None, channel_id: int | None = None) -> dict:
    """Drop the camera on a tile and capture its media socket over CDP."""
    sockets: dict[str, str] = {}
    frames: dict[str, list] = {}
    out = {"sockets": [], "tile": {}, "fullscreen": None}

    def on_created(ev):
        sockets[ev["requestId"]] = ev["url"]
        frames.setdefault(ev["url"], [])

    def on_frame(ev):
        url = sockets.get(ev["requestId"])
        if not url or MEDIA_WS not in url:
            return
        payload = ev["response"]
        entry = {"opcode": payload["opcode"], "t": ev["timestamp"]}
        if payload["opcode"] == 2:
            entry["data"] = base64.b64decode(payload["payloadData"])
        else:
            entry["text"] = payload["payloadData"]
        frames[url].append(entry)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed, channel=channel)
        ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1600, "height": 900})
        ctx.add_init_script(HOOK)
        page = ctx.new_page()
        cdp = ctx.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.on("Network.webSocketCreated", on_created)
        cdp.on("Network.webSocketFrameReceived", on_frame)

        page.goto(config["base_url"])
        LoginPage(page, config["base_url"]).login(os.environ["QA_USER"], os.environ["QA_PASSWORD"])
        page.wait_for_function("() => !window.location.href.includes('/auth/login')", timeout=60000)
        page.locator("text=Views").first.wait_for(state="visible", timeout=30000)
        views = ViewsPage(page)
        views.navigate()
        views.wait_for_page_load()
        views.expand_site_and_show_cameras(None)
        # drag first, checkbox second: on 08/25 the drag landed the tile
        # in three of four runs and consumed nothing in the fourth
        tile = page.locator(TILE).first
        for attempt in ("drag", "checkbox"):
            try:
                if attempt == "drag":
                    views.drag_camera_to_tile_by_name(camera)
                else:
                    views.add_camera_via_checkbox(camera)
                tile.wait_for(state="attached", timeout=10000)
                break
            except Exception as e:  # the next attempt is the fallback
                print(f"[probe] {attempt} did not land a tile ({str(e)[:120]})")
        else:
            raise SystemExit(f"'{camera}' never landed on a tile; nothing to capture")

        # The media socket names the channel it streams. On 08/25 one
        # drag landed the neighbouring thumbnail (channel 121 for "main
        # gate"), so the landed channel is checked against the API's id
        # and the checkbox path adds the right camera to the next tile.
        want = str(channel_id) if channel_id else None

        def landed() -> set[str]:
            return {parse_ws_name(u).get("channel") for u in frames if MEDIA_WS in u}

        def wait_for_socket() -> bool:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if landed() and (want is None or want in landed()):
                    return True
                page.wait_for_timeout(250)
            return False

        if not wait_for_socket() and want:
            print(f"[probe] the drop opened channel(s) {sorted(landed())}, not {want}; "
                  "adding the camera through its checkbox")
            views.add_camera_via_checkbox(camera)
            if not wait_for_socket():
                raise SystemExit(f"no media socket for channel {want} opened within 20s")
        out["want_channel"] = want
        # the capture window starts when the media socket opens, so a
        # slow tile does not eat the window
        page.wait_for_timeout(seconds * 1000)

        out["tile"]["video"] = tile.evaluate(TILE_VIDEO_STATE_JS)
        tile.hover()
        page.wait_for_timeout(800)
        out["tile"]["icons"] = page.evaluate(ICONS_JS, TILE)
        out["tile"]["menu"] = _read_tile_menu(page, tile)
        out["tile"]["hook"] = page.evaluate("() => window.__streamProbe")

        if fullscreen:
            fs = {"entered": False}
            try:
                views.enter_fullscreen_on_tile(0)
                fs["entered"] = True
                page.wait_for_timeout(seconds * 1000)
                fs["video"] = page.evaluate(VIDEO_STATE_JS)
                fs["icons"] = page.evaluate(ICONS_JS, ".top_container, .control_Container, .bottom-control-group")
                fs["ptz_elements"] = page.evaluate(
                    "() => Array.from(document.querySelectorAll(\"[class*='ptz' i]\"))"
                    ".filter(e => e.offsetWidth > 0).map(e => e.className)")
                fs["hook"] = page.evaluate("() => window.__streamProbe")
            except Exception as e:  # full screen is optional evidence
                fs["error"] = str(e)[:300]
            out["fullscreen"] = fs

        mimes = [s["mime"] for s in (summarize_frames(f) for f in frames.values()) if s["mime"]]
        out["mime_supported"] = {
            m: page.evaluate("m => MediaSource.isTypeSupported(m)", m) for m in mimes}
        browser.close()

    for url, fl in frames.items():
        summary = summarize_frames(fl)
        summary["url"] = re.sub(r"[0-9a-f]{8}-[0-9a-f-]{27}", "<uuid>", url)
        summary["name"] = parse_ws_name(url)
        out["sockets"].append(summary)
    return out


def _read_tile_menu(page, tile) -> list[str]:
    """Open the tile's three-dot menu, read its items, close it again."""
    dots = tile.locator("img[src*='3-dot']")
    if not dots.count():
        return []
    try:
        dots.first.click(timeout=3000)
        page.wait_for_timeout(500)
        items = page.evaluate(
            "() => Array.from(document.querySelectorAll('[role=menuitem], li, .MuiMenuItem-root'))"
            ".filter(e => e.offsetWidth > 0).map(e => e.innerText.trim()).filter(Boolean)")
        page.keyboard.press("Escape")
        return items[:20]
    except Exception as e:  # the menu is optional evidence
        return [f"<menu read failed: {str(e)[:80]}>"]


# --------------------------------------------------------------- report ---
def codec_from_mime(mime: str | None) -> str | None:
    if not mime:
        return None
    m = re.search(r'codecs="?([^",]+)', mime)
    tag = m.group(1) if m else mime
    if tag.startswith(("hvc1", "hev1")):
        return f"H.265 ({tag})"
    if tag.startswith(("avc1", "avc3")):
        return f"H.264 ({tag})"
    return tag


def fmt_stream(s: dict | None) -> str:
    if not s:
        return "-"
    return (f"codecType {s.get('codecType')} {s.get('width')}x{s.get('height')} "
            f"{s.get('fps')} fps {s.get('bitrate')} kbps")


def build_rows(api: dict | None, bro: dict) -> list[tuple[str, str, str]]:
    rows = []
    want = bro.get("want_channel")
    socks = [s for s in bro["sockets"] if (s["binary_frames"] or s["mime"])
             and (want is None or s["name"].get("channel") == want)]
    tile_sock = next((s for s in socks if s["name"].get("stream") == "1"), socks[0] if socks else None)
    if not tile_sock:
        rows.append(("transport", "no media WebSocket frames captured", "CDP Network domain"))
        return rows
    name = tile_sock["name"]
    stream_idx = int(name.get("stream", -1)) if name.get("stream", "").isdigit() else None
    host = re.sub(r"\?.*", "", tile_sock["url"])
    rows.append(("transport", f"WebSocket {host}?name={'/'.join(name.values())}",
                 "CDP Network.webSocketCreated"))
    rows.append(("stream requested",
                 f"site {name.get('site')} channel {name.get('channel')} stream index {stream_idx}"
                 f" ({STREAM_NAMES.get(stream_idx, '?')})", "media socket url name= path"))
    init = tile_sock["init"] or {}
    video = init.get("video") or {}
    audio = init.get("audio")
    rows.append(("container", f"fMP4 via MediaSource, brand {init.get('brand')}"
                 f" ({tile_sock['binary_frames']} binary / {tile_sock['text_frames']} text frames)",
                 "first binary frame ftyp + app addSourceBuffer"))
    rows.append(("mse mime", tile_sock["mime"] or "-", "first text frame {type:mse}"))
    supported = bro.get("mime_supported", {}).get(tile_sock["mime"])
    rows.append(("browser can decode", str(supported), "MediaSource.isTypeSupported in the test browser"))
    sps = video.get("sps") or {}
    rows.append(("video codec (delivered)",
                 f"{video.get('codec', codec_from_mime(tile_sock['mime']))} sample entry {video.get('entry')}"
                 + (f", SPS profile {sps.get('profile_idc')} level {sps.get('level')}" if sps else ""),
                 "moov stsd + hvcC/avcC SPS"))
    if api:
        rows.append(("video codec (configured)", f"major: {fmt_stream(api['streams'].get(0))}; "
                     f"minor: {fmt_stream(api['streams'].get(1))}",
                     "POST getCameraStreamingParameters"))
    res = (f"{sps['width']}x{sps['height']} (coded {video.get('coded_width')}x{video.get('coded_height')})"
           if sps else f"coded {video.get('coded_width')}x{video.get('coded_height')}")
    rows.append(("resolution (delivered)", res, "SPS conformance window / stsd"))
    if api and stream_idx in api["streams"] and api["streams"][stream_idx]:
        s = api["streams"][stream_idx]
        rows.append(("resolution (configured)", f"{s.get('width')}x{s.get('height')} for stream {stream_idx}",
                     "POST getCameraStreamingParameters"))
    vtrack = next((t for t in tile_sock["tracks"].values() if t.get("handler") == "vide"), None)
    if vtrack:
        rows.append(("fps / bitrate (delivered)",
                     f"{vtrack.get('rate')} fps, {vtrack.get('kbps')} kbps over {vtrack.get('seconds')}s "
                     f"({vtrack['fragments']} fragments)", "moof tfdt/trun/mdat"))
    if api and stream_idx in api["streams"] and api["streams"][stream_idx]:
        s = api["streams"][stream_idx]
        rows.append(("fps / bitrate (configured)", f"{s.get('fps')} fps, {s.get('bitrate')} kbps",
                     "POST getCameraStreamingParameters"))
    atrack = next((t for t in tile_sock["tracks"].values() if t.get("handler") == "soun"), None)
    if audio:
        rows.append(("audio (delivered)",
                     f"track {audio['entry']} {audio['channels']}ch {audio['bits']}bit {audio['sample_rate']}Hz, "
                     f"{atrack['fragments'] if atrack else 0} fragments {atrack.get('kbps') if atrack else 0} kbps",
                     "moov stsd + moof"))
    else:
        rows.append(("audio (delivered)", "no audio track in init segment", "moov stsd"))
    if api:
        a = api["audio"] or {}
        rows.append(("audio (configured)",
                     f"audioGrabbing={api['audio_grabbing']}, camera codec {a.get('encodingName')} "
                     f"{a.get('samplerate')}Hz", "GET channel + POST camera/audio/streaming"))
    tile_video = (bro["tile"].get("video") or [{}])[0]
    rows.append(("tile player", f"readyState {tile_video.get('ready')} {tile_video.get('w')}x{tile_video.get('h')} "
                 f"muted={tile_video.get('muted')} frames={tile_video.get('frames')}", "<video> in the tile"))
    rows.append(("tile controls", ", ".join(bro["tile"].get("icons") or []), "img names under the tile"))
    if bro["tile"].get("menu"):
        rows.append(("tile menu", " | ".join(bro["tile"]["menu"]), "three-dot menu items"))
    if api:
        presets = api["presets"]
        pos = api["ptz_position"] or {}
        rows.append(("PTZ (api)", f"channelType={api['channel_type']}, presets={presets}, "
                     f"position pan={pos.get('pan')} tilt={pos.get('tilt')} zoom={pos.get('zoom')}",
                     "GET channel, preset, getcurrentptzposition"))
    fs = bro.get("fullscreen")
    if fs and fs.get("entered"):
        fs_sock = next((s for s in socks if s["name"].get("stream") == "0"), None)
        fs_video = (fs.get("video") or [{}])[0]
        rows.append(("full screen player", f"readyState {fs_video.get('ready')} {fs_video.get('w')}x{fs_video.get('h')}"
                     + (f"; socket stream 0: {fs_sock['mime']}, coded "
                        f"{(fs_sock['init'] or {}).get('video', {}).get('coded_width')}x"
                        f"{(fs_sock['init'] or {}).get('video', {}).get('coded_height')}" if fs_sock else ""),
                     "video.player + second media socket"))
        rows.append(("PTZ (ui)", f"ptz elements: {fs.get('ptz_elements') or 'none'}; "
                     f"controls: {', '.join(fs.get('icons') or [])}", "full screen DOM"))
    elif fs:
        rows.append(("full screen", f"not entered: {fs.get('error')}", "-"))
    return rows


def print_table(rows: list[tuple[str, str, str]]) -> None:
    width = max(len(r[0]) for r in rows)
    print(f"{'fact'.ljust(width)}  value  [source]")
    print("-" * (width + 40))
    for fact, value, source in rows:
        print(f"{fact.ljust(width)}  {value}  [{source}]")


def _jsonable(o):
    if isinstance(o, bytes):
        return f"<{len(o)} bytes>"
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_jsonable(v) for v in o]
    return o


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--camera", default=config.get("test_camera_name"),
                        help="camera name as shown in the Views tree")
    parser.add_argument("--site-id", type=int, default=int(os.environ.get("TEST_SITE_ID", "16")))
    parser.add_argument("--seconds", type=int, default=12, help="capture window per player")
    parser.add_argument("--fullscreen", action="store_true", help="also open full screen (stream 0)")
    parser.add_argument("--no-api", action="store_true", help="skip the internal API reads")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--channel", help="Playwright browser channel, e.g. chrome or msedge, "
                        "to check decode support outside the bundled Chromium")
    parser.add_argument("--json", type=Path, help="write all raw facts here")
    args = parser.parse_args()

    api_data = None
    if not args.no_api:
        api = InternalApi(config["base_url"], args.site_id)
        api.login(os.environ["QA_USER"], os.environ["QA_PASSWORD"])
        api_data = api_facts(api, args.site_id, args.camera)
        print(f"[probe] channel {api_data['channel_id']} '{api_data['name']}' "
              f"{api_data['model']} {api_data['model_number']}")
    started = time.monotonic()
    bro = browser_facts(args.camera, args.seconds, args.fullscreen, args.headed, args.channel,
                        api_data["channel_id"] if api_data else None)
    print(f"[probe] browser capture took {time.monotonic() - started:.0f}s\n")

    rows = build_rows(api_data, bro)
    print_table(rows)
    if api_data and api_data["errors"]:
        print("\napi reads that failed:")
        for err in api_data["errors"]:
            print("  -", err)
    if args.json:
        args.json.write_text(json.dumps({"api": api_data, "browser": _jsonable(bro), "rows": rows},
                                        indent=1), encoding="utf-8")
        print(f"\nraw facts: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
