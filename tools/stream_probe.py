"""Report what a live camera tile actually receives, next to what the API says it should.

    python tools/stream_probe.py --camera "main gate"
    python tools/stream_probe.py --camera "main gate" --fullscreen --json out.json
    python tools/stream_probe.py --health --camera "main gate" --seconds 20
    python tools/stream_probe.py --health --all-cameras --no-browser --json out.json
    python tools/stream_probe.py --no-browser --camera "main gate"

Read-only: it logs in, drops the camera on a Views tile, watches the media
WebSocket for a few seconds, and reads channel settings from the internal
API. Nothing on the tenant is changed.

Modes:

  * facts (default): one camera, one row per delivery fact with its source.
  * --health: per channel, a table and JSON of online / first frame /
    fps / bitrate / resolution / codec / keyframe interval / timestamp
    gaps / latency / reconnects / analytics / audio / close reason /
    timeline status. `--all-cameras` covers every channel on the site.
    Metric definitions are in health_metrics().
  * --no-browser: open the media socket from Python (aiohttp) with the
    same URL and handshake the app uses, no browser at all. On its own it
    runs the authorisation experiment (which header or URL part lets
    frames flow); with --health it is the capture path.

How the stream is identified (probed 2026-08-25, docs/QA_THINGS_TO_KNOW.md
"Live stream delivery"):

  * The tile opens <media_host>/v3/api/ws?name=
    <site>/<channel>/<app>/<live>/<stream>/<timestamp>/<uuid> from the
    main thread and sends {"type":"mse","value":""}. media_host is the
    wss host in config/env/ (read from the browser's network tab).
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
import asyncio
import base64
import itertools
import json
import re
import statistics
import struct
import sys
import time
import uuid as uuid_mod
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from playwright.sync_api import sync_playwright

from config.base_config import config
from tests.shared.api.client import ApiError, InternalApi
from tests.shared.helpers.stream_health import chrome_args
from tests.shared.pages.login_page import LoginPage
from tests.shared.pages.views_page import ViewsPage

TILE = "[class*='video_container'][class*='new_video_player']"
MEDIA_WS = "/v3/api/ws"
TIMELINE_WS = "/ws/timeline/"


def stream_host() -> str:
    """The media socket host: media_host in config/env/, the wss host the
    app's live player opens. Not a constant: it differs per server."""
    host = str(config.get("media_host") or "").strip().rstrip("/")
    if not host:
        raise RuntimeError(
            "media_host is not set in config/env/: the wss host the app's live player opens "
            "(browser network tab on a playing tile, the request whose path is /v3/api/ws)")
    return host


def fill_site_and_camera_from_server() -> None:
    """Read the site and the camera config/env/ leaves blank, the way a test
    session does (tests/shared/api/discovery.py). Stops with the reason
    when the server cannot be read or a configured name is unknown."""
    from config.base_config import get_credentials
    from tests.shared.api import discovery
    if not discovery.needs_discovery(config):
        return
    try:
        record = discovery.fill_config(config, get_credentials())
    except discovery.DiscoveryError as exc:
        raise SystemExit(f"DISCOVERY: {exc}") from None
    print(f"[probe] site '{record['site_name']}' (siteId {record['site_id']}): {record['site_reason']}")
    print(f"[probe] camera '{record['camera']}': {record['camera_reason']}")
HANDSHAKE = '{"type":"mse","value":""}'
# The app sends this literal placeholder in the src= parameter (08/25)
SRC_PREFIX = "videonetics://<videoneticsAddr>/"
CODEC_TYPES = {8: "H.265"}  # only value seen so far; the H.264 value is not verified
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
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
    const rec = { url: String(url), recv: 0, sent: [], text: [], opened: performance.now(), close: null };
    P.ws.push(rec);
    ws.addEventListener('close', (ev) => {
      rec.close = { code: ev.code, reason: ev.reason, clean: ev.wasClean,
                    after_s: (performance.now() - rec.opened) / 1000 };
    });
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
    dropped: v.getVideoPlaybackQuality ? v.getVideoPlaybackQuality().droppedVideoFrames : null,
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
        # crop units (H.264 table 6-1): SubWidthC is 2 for 4:2:0 and 4:2:2,
        # SubHeightC is 2 for 4:2:0 only; monochrome and 4:4:4 use 1 on both
        # axes, and a field-coded picture doubles the vertical unit
        sub_w = 2 if chroma in (1, 2) else 1
        sub_h = 2 if chroma == 1 else 1
        unit_y = sub_h * (2 - frame_mbs_only)
        left, right, top, bottom = r.ue(), r.ue(), r.ue(), r.ue()
        width -= sub_w * (left + right)
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
    info = {"codec": "H.265 (HEVC)", "hvcc_profile_idc": c[1] & 0x1F, "hvcc_level_idc": c[12],
            "nal_length_size": (c[21] & 3) + 1}
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
    info = {"codec": "H.264 (AVC)", "avcc_profile_idc": c[1], "avcc_level_idc": c[3],
            "nal_length_size": (c[4] & 3) + 1}
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
    frag.update(_first_sample(buf, tfhd, trun))
    for typ, _hdr, body, box_end in boxes(buf):
        if typ == "mdat":
            frag["mdat"] = box_end - body
            frag["mdat_body"] = (body, box_end)
    return frag


def _u32(buf: bytes, off: int) -> int:
    return struct.unpack(">I", buf[off:off + 4])[0]


def _first_sample(buf: bytes, tfhd, trun) -> dict:
    """flags and duration of the fragment's first sample (trun, else tfhd defaults)."""
    out: dict = {"flags": None, "duration": None}
    tf = _u32(buf, tfhd[0]) & 0xFFFFFF
    off = tfhd[0] + 8
    if tf & 0x1:
        off += 8
    if tf & 0x2:
        off += 4
    if tf & 0x8:
        out["duration"] = _u32(buf, off)
        off += 4
    if tf & 0x10:
        off += 4
    if tf & 0x20:
        out["flags"] = _u32(buf, off)
    if not trun:
        return out
    tr = _u32(buf, trun[0]) & 0xFFFFFF
    count = _u32(buf, trun[0] + 4)
    off = trun[0] + 8
    if tr & 0x1:
        off += 4
    if tr & 0x4:
        out["flags"] = _u32(buf, off)
        off += 4
    if count:
        if tr & 0x100:
            out["duration"] = _u32(buf, off)
            off += 4
        if tr & 0x200:
            off += 4
        if tr & 0x400:
            out["flags"] = _u32(buf, off)
    return out


def keyframe_by_nal(buf: bytes, body: tuple[int, int], nal_len: int, hevc: bool) -> bool | None:
    """True when the mdat holds an IRAP (H.265 types 16-21) or IDR (H.264 type 5) NAL.

    None when the length-prefixed NAL walk breaks, so the caller can fall
    back to the sample flags.
    """
    off, end = body
    seen = False
    while off + nal_len < end:
        length = int.from_bytes(buf[off:off + nal_len], "big")
        if length == 0 or off + nal_len + length > end:
            return None if not seen else False
        head = buf[off + nal_len]
        nal_type = (head >> 1) & 0x3F if hevc else head & 0x1F
        if (hevc and 16 <= nal_type <= 21) or (not hevc and nal_type == 5):
            return True
        seen = True
        off += nal_len + length
    return False if seen else None


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
def _account() -> tuple[str, str, int]:
    """(user, password, site_id): the account and site the tests use, from
    config/env/ through get_credentials, so a probe reads the same tenant
    the tests drive."""
    from config.base_config import get_credentials
    creds = get_credentials()
    if not creds.get("email") or not creds.get("password"):
        raise SystemExit("QA_USER and QA_PASSWORD must be set in .env.")
    if creds.get("site_id") is None:
        raise SystemExit("default_site_id is not set in config/env/; pass --site-id.")
    return creds["email"], creds["password"], int(creds["site_id"])


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


class Capture:
    """Record every WebSocket a page opens, over CDP.

    Media sockets keep all frames; timeline sockets keep text frames only.
    Open time comes from the handshake request (CDP monotonic timestamp
    plus wallTime, which maps frame times onto the wall clock for the
    latency metric).
    """

    def __init__(self):
        self.urls: dict[str, str] = {}
        self.frames: dict[str, list] = {}
        self.opened: dict[str, tuple[float, float]] = {}
        self.closed: dict[str, float] = {}
        self.errors: dict[str, str] = {}

    def attach(self, ctx, page) -> None:
        cdp = ctx.new_cdp_session(page)
        cdp.send("Network.enable")
        cdp.on("Network.webSocketCreated", self._created)
        cdp.on("Network.webSocketWillSendHandshakeRequest", self._handshake)
        cdp.on("Network.webSocketFrameReceived", self._frame)
        cdp.on("Network.webSocketClosed", self._close)
        cdp.on("Network.webSocketFrameError", self._error)

    def _created(self, ev):
        self.urls[ev["requestId"]] = ev["url"]
        self.frames.setdefault(ev["url"], [])

    def _handshake(self, ev):
        url = self.urls.get(ev["requestId"])
        if url:
            self.opened[url] = (ev["timestamp"], ev["wallTime"])

    def _frame(self, ev):
        url = self.urls.get(ev["requestId"])
        if not url:
            return
        payload = ev["response"]
        entry = {"opcode": payload["opcode"], "t": ev["timestamp"]}
        if MEDIA_WS in url:
            if payload["opcode"] == 2:
                entry["data"] = base64.b64decode(payload["payloadData"])
            else:
                entry["text"] = payload["payloadData"]
        elif TIMELINE_WS in url and payload["opcode"] == 1:
            entry["text"] = payload["payloadData"]
        else:
            return
        self.frames[url].append(entry)

    def _close(self, ev):
        url = self.urls.get(ev["requestId"])
        if url:
            self.closed[url] = ev["timestamp"]

    def _error(self, ev):
        url = self.urls.get(ev["requestId"])
        if url:
            self.errors[url] = ev.get("errorMessage", "?")

    def media_urls(self) -> list[str]:
        return [u for u in self.frames if MEDIA_WS in u]


def open_browser(p, headed: bool, channel: str | None):
    """Launch, hook, log in and land on Views. Returns (browser, page, views, capture).

    The launch flags are the session's (CHROME_ARGS, stream_health.chrome_args),
    so the probe measures the browser the tests get.
    """
    browser = p.chromium.launch(headless=not headed, channel=channel, args=chrome_args())
    ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1600, "height": 900})
    ctx.add_init_script(HOOK)
    page = ctx.new_page()
    cap = Capture()
    cap.attach(ctx, page)
    page.goto(config["base_url"])
    LoginPage(page, config["base_url"]).login(*_account()[:2])
    page.wait_for_function("() => !window.location.href.includes('/auth/login')", timeout=60000)
    page.locator("text=Views").first.wait_for(state="visible", timeout=30000)
    views = ViewsPage(page)
    views.navigate()
    views.wait_for_page_load()
    views.expand_site_and_show_cameras(None)
    return browser, page, views, cap


def drop_camera(page, views, cap: Capture, camera: str, want: str | None,
                timeout_s: int = 20) -> bool:
    """Land the camera on a tile and wait for its media socket.

    Drag first, checkbox second: on 08/25 the drag landed the tile in
    three of four runs and consumed nothing in the fourth. The media
    socket names the channel it streams; one drag landed the neighbouring
    thumbnail (channel 121 for "main gate"), so the landed channel is
    checked against the API's id and the checkbox path adds the right
    camera to the next tile. Returns False when no socket for `want`
    opened within the timeout (the caller decides whether that is fatal).
    """
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

    def landed() -> set[str]:
        return {parse_ws_name(u).get("channel") for u in cap.media_urls()}

    def wait_for_socket() -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if landed() and (want is None or want in landed()):
                return True
            page.wait_for_timeout(250)
        return False

    if wait_for_socket():
        return True
    if want:
        print(f"[probe] the drop opened channel(s) {sorted(landed())}, not {want}; "
              "adding the camera through its checkbox")
        views.add_camera_via_checkbox(camera)
        return wait_for_socket()
    return False


def browser_facts(camera: str, seconds: int, fullscreen: bool, headed: bool,
                  channel: str | None = None, channel_id: int | None = None) -> dict:
    """Drop the camera on a tile and capture its media socket over CDP."""
    out = {"sockets": [], "tile": {}, "fullscreen": None}
    want = str(channel_id) if channel_id else None

    with sync_playwright() as p:
        browser, page, views, cap = open_browser(p, headed, channel)
        frames = cap.frames
        tile = page.locator(TILE).first
        if not drop_camera(page, views, cap, camera, want):
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
        out["tile"]["hook"] = _redact_hook(page.evaluate("() => window.__streamProbe"))

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
                fs["hook"] = _redact_hook(page.evaluate("() => window.__streamProbe"))
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


def _redact_hook(hook: dict | None) -> dict | None:
    """Trim the main-thread hook's socket list before it is written out.

    Media and timeline sockets are the evidence and stay whole. Any other
    socket the app opens is kept as a url without its query string and
    without the sent/received text, so a session token in a query
    parameter or a message body cannot land in the JSON.
    """
    if not hook:
        return hook
    ws = []
    for w in hook.get("ws", []):
        url = str(w.get("url", ""))
        if MEDIA_WS in url or TIMELINE_WS in url:
            ws.append(w)
            continue
        kept = {k: v for k, v in w.items() if k not in ("sent", "text")}
        kept["url"] = url.split("?", 1)[0]
        ws.append(kept)
    return {**hook, "ws": ws}


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


# --------------------------------------------------------------- health ---
def health_metrics(sockets: list[dict], timeline_text: list[str], cfg: dict | None) -> dict:
    """Health numbers for one channel from its captured media socket(s).

    `sockets` holds one dict per media socket opened for the channel in
    the window, in open order: {url, name, t_open, wall_open, frames,
    close, error}. Times share one monotonic clock; wall_open is the epoch
    time of the handshake. `cfg` is the getCameraStreamingParameters row
    for the stream index, or None.

    Definitions:
      online              a moof/mdat video fragment arrived in the window
      first_frame_ms      handshake request -> first video fragment
      frames              video fragments in the window (one sample each)
      fps_measured        (video samples - 1) / tfdt span of the video track
      bitrate_kbps        video mdat bytes * 8 / tfdt span / 1000
      resolution          SPS width x height after the conformance window
      codec               moov sample entry (hev1/hvc1 H.265, avc1/avc3 H.264)
      keyframe_interval_s mean tfdt distance between keyframes. A keyframe
                          is a fragment whose mdat holds an IRAP/IDR NAL
                          (exact); else sample_is_non_sync_sample == 0 in
                          the trun/tfhd flags; else an mdat above 3x the
                          median size (approximate). keyframe_method says
                          which one was used; keyframe_nal_unreadable is the
                          number of mdats the NAL walk could not read (they
                          count as non-keyframes while the rest read).
      timestamp_gaps      consecutive video tfdt deltas above 2x nominal;
                          nominal = 1000 / configured fps, else the median
      latency_ms          wall clock at receipt minus the analytics frame's
                          timeStamp, only when timeStamp is epoch-based
                          (within a day of now). Includes the clock offset
                          between this machine and the encoder.
      reconnects          media sockets opened for the channel on the measured
                          stream index, minus one; stream_indexes_seen lists
                          every index that opened (full screen adds stream 0)
      analytics_alive     at least one JSON counters frame arrived
      audio_fragments     fragments on the soun track
      close               close code / reason when the socket closed
      timeline            message type -> statuses on the timeline socket
    """
    # every key is set here so the JSON shape is the same for an offline
    # channel, a channel with no init segment, and a full capture
    out: dict = {
        "online": False, "first_frame_ms": None, "frames": 0, "binary_frames": 0,
        "fps_measured": None, "fps_configured": cfg.get("fps") if cfg else None,
        "bitrate_kbps_measured": None, "bitrate_kbps_configured": cfg.get("bitrate") if cfg else None,
        "span_s": None, "resolution_delivered": None,
        "resolution_configured": f"{cfg.get('width')}x{cfg.get('height')}" if cfg else None,
        "codec_delivered": None, "codec_configured": None, "keyframes": 0,
        "keyframe_interval_s": None, "keyframe_method": None, "keyframe_nal_unreadable": None,
        "timestamp_gaps": None, "latency_ms": None, "reconnects": 0, "stream_indexes_seen": [],
        "analytics_alive": False, "analytics_frames": 0, "counters_max": None,
        "audio_fragments": 0, "close": None, "socket_error": None, "timeline": {},
        "mismatches": [], "stream_index": None, "mime": None, "note": None,
    }
    if cfg:
        ct = cfg.get("codecType")
        out["codec_configured"] = f"{CODEC_TYPES.get(ct, 'unknown')} (codecType {ct})"
    out["timeline"] = {"error": None, **_timeline_summary(timeline_text)}
    if not sockets:
        out["note"] = "no media socket opened"
        return out

    primary = max(sockets, key=lambda s: sum(1 for f in s["frames"] if f["opcode"] == 2))
    stream = primary["name"].get("stream")
    out["stream_index"] = int(stream) if stream and stream.isdigit() else None
    seen = {s["name"].get("stream") for s in sockets}
    out["stream_indexes_seen"] = sorted(int(v) for v in seen if v and v.isdigit())
    # a socket on another stream index is a second player (full screen
    # opens stream 0 beside the tile's stream 1), not a reconnect
    out["reconnects"] = sum(1 for s in sockets if s["name"].get("stream") == stream) - 1
    out["close"] = primary.get("close")
    out["socket_error"] = primary.get("error")
    frames = primary["frames"]
    t_open = primary["t_open"] if primary["t_open"] is not None else (frames[0]["t"] if frames else None)

    init = None
    frags: list[dict] = []
    text: list[dict] = []
    for f in frames:
        if f["opcode"] != 2:
            text.append(f)
            continue
        out["binary_frames"] += 1
        data = f["data"]
        if data[4:8] == b"ftyp":
            init = parse_init_segment(data)
            continue
        frag = parse_fragment(data)
        if not frag:
            continue
        frag["t"] = f["t"]
        frag["data"] = data
        frags.append(frag)

    vinfo = (init or {}).get("video") or {}
    tracks = (init or {}).get("tracks", {})
    if init is None:
        # no init segment in the window (the capture started after it, or
        # the server never sent one): the track carrying the most bytes is
        # taken as video. Its timescale is unknown, so fps, bitrate and
        # keyframe interval stay None rather than wrong.
        bytes_by_track: dict[int, int] = {}
        for fr in frags:
            bytes_by_track[fr["track"]] = bytes_by_track.get(fr["track"], 0) + fr.get("mdat", 0)
        video_track = max(bytes_by_track, key=bytes_by_track.get) if bytes_by_track else None
        video = [fr for fr in frags if fr["track"] == video_track]
        timescale = None
        if frags:
            out["note"] = "no init segment; track chosen by size"
    else:
        handler = {tid: t.get("handler") for tid, t in tracks.items()}
        video = [fr for fr in frags if handler.get(fr["track"]) == "vide"]
        out["audio_fragments"] = sum(1 for fr in frags if handler.get(fr["track"]) == "soun")
        timescale = tracks.get(vinfo.get("track"), {}).get("timescale")

    sps = vinfo.get("sps") or {}
    if vinfo:
        out["codec_delivered"] = f"{vinfo.get('codec')} ({vinfo.get('entry')})"
    if sps:
        out["resolution_delivered"] = f"{sps['width']}x{sps['height']}"
    elif vinfo:
        out["resolution_delivered"] = f"coded {vinfo.get('coded_width')}x{vinfo.get('coded_height')}"
    if video:
        out["online"] = True
        if t_open is not None:
            out["first_frame_ms"] = round((video[0]["t"] - t_open) * 1000)
        out["frames"] = len(video)
        _video_rates(out, video, timescale, cfg)
        _keyframes(out, video, timescale, vinfo)
    _analytics(out, text, primary, t_open)
    _mismatches(out)
    return out


def _video_rates(out: dict, video: list[dict], timescale: int | None, cfg: dict | None) -> None:
    times = [v["time"] for v in video if "time" in v]
    samples = sum(v.get("samples", 0) for v in video)
    if timescale and len(times) > 1 and times[-1] != times[0]:
        span = (times[-1] - times[0]) / timescale
        out["span_s"] = round(span, 2)
        out["fps_measured"] = round((samples - 1) / span, 2) if samples > 1 else None
        out["bitrate_kbps_measured"] = round(sum(v.get("mdat", 0) for v in video) * 8 / span / 1000)
    deltas = ([(b - a) / timescale * 1000 for a, b in itertools.pairwise(times)]
              if timescale else [])
    if cfg and cfg.get("fps"):
        nominal, basis = 1000 / cfg["fps"], "1000 / configured fps"
    elif deltas:
        nominal, basis = statistics.median(deltas), "median tfdt delta (no configured fps)"
    else:
        nominal, basis = None, "no tfdt deltas"
    gaps = [d for d in deltas if nominal and d > 2 * nominal]
    out["timestamp_gaps"] = {
        "count": len(gaps), "nominal_ms": round(nominal, 1) if nominal else None, "basis": basis,
        "worst_delta_ms": round(max(deltas)) if deltas else None,
        "backwards": sum(1 for d in deltas if d < 0), "examples_ms": [round(g) for g in gaps[:10]],
    }


def _keyframes(out: dict, video: list[dict], timescale: int | None, vinfo: dict) -> None:
    flags: list[bool] | None = None
    if vinfo:
        # the NAL walk needs the codec and the length-prefix size from the
        # init segment; without them the walk would guess
        hevc = vinfo.get("entry") in ("hev1", "hvc1")
        nal_len = vinfo.get("nal_length_size", 4)
        by_nal = [keyframe_by_nal(v["data"], v["mdat_body"], nal_len, hevc) if "mdat_body" in v
                  else None for v in video]
        out["keyframe_nal_unreadable"] = sum(1 for k in by_nal if k is None)
        if any(k is not None for k in by_nal):
            # an unreadable mdat counts as a non-keyframe; the count above
            # says how many, so a partial walk is not a silent downgrade
            flags = [bool(k) for k in by_nal]
            out["keyframe_method"] = "IRAP/IDR NAL type inside each mdat (exact)"
    if flags is None and any(v.get("flags") is not None for v in video):
        flags = [v.get("flags") is not None and ((v["flags"] >> 16) & 1) == 0 for v in video]
        out["keyframe_method"] = "sample_is_non_sync_sample == 0 in trun/tfhd flags"
    elif flags is None:
        sizes = [v.get("mdat", 0) for v in video]
        median = statistics.median(sizes) if sizes else 0
        flags = [s > 3 * median for s in sizes]
        out["keyframe_method"] = "mdat larger than 3x the median (approximate)"
    key_times = [v.get("time") for v, k in zip(video, flags, strict=False) if k and "time" in v]
    out["keyframes"] = sum(1 for k in flags if k)
    if timescale and len(key_times) > 1:
        gaps = [(b - a) / timescale for a, b in itertools.pairwise(key_times)]
        out["keyframe_interval_s"] = round(statistics.mean(gaps), 2)


def _analytics(out: dict, text: list[dict], primary: dict, t_open: float | None) -> None:
    counters: list[tuple[float, dict]] = []
    for f in text:
        try:
            msg = json.loads(f["text"])
        except ValueError:
            continue
        if isinstance(msg, dict) and msg.get("type") == "mse":
            out["mime"] = msg.get("value")
            continue
        for row in msg if isinstance(msg, list) else [msg]:
            if isinstance(row, dict) and "timeStamp" in row:
                counters.append((f["t"], row))
    out["analytics_frames"] = len(counters)
    out["analytics_alive"] = bool(counters)
    if not counters:
        return
    out["counters_max"] = {k: max(r.get(k) or 0 for _, r in counters)
                           for k in ("vehicleCount", "peopleCount")}
    if primary.get("wall_open") is None or t_open is None:
        out["latency_ms"] = {"median": None, "basis": "no handshake wallTime for this socket"}
        return
    lat, basis = [], None
    for t, row in counters:
        stamp = row["timeStamp"]
        if not isinstance(stamp, int | float):
            basis = f"timeStamp is {type(stamp).__name__}, not numeric"
            break
        if 1e12 <= stamp <= 4e12:
            stamp_ms, basis = stamp, "timeStamp is epoch ms"
        elif 1e9 <= stamp <= 4e9:
            stamp_ms, basis = stamp * 1000, "timeStamp is epoch s"
        else:
            basis = f"timeStamp {stamp} is not epoch-based"
            break
        lat.append((primary["wall_open"] + (t - t_open)) * 1000 - stamp_ms)
    if lat and abs(statistics.median(lat)) < 86_400_000:
        out["latency_ms"] = {
            "median": round(statistics.median(lat)), "min": round(min(lat)), "max": round(max(lat)),
            "samples": len(lat), "basis": f"{basis} (verified within a day of the wall clock); "
            "wall clock at receipt minus timeStamp"}
    else:
        out["latency_ms"] = {"median": None, "basis": basis or "timeStamp more than a day off"}


def _mismatches(out: dict) -> None:
    fm, fc = out["fps_measured"], out["fps_configured"]
    if fm and fc and abs(fm - fc) / fc > 0.1:
        out["mismatches"].append(f"fps {fm} vs {fc}")
    rd, rc = out["resolution_delivered"], out["resolution_configured"]
    if rd and rc and not rd.startswith("coded") and rd != rc:
        out["mismatches"].append(f"resolution {rd} vs {rc}")
    cd, cc = out["codec_delivered"] or "", out["codec_configured"] or ""
    if cd and cc and "unknown" not in cc and cc.split(" ")[0] not in cd:
        out["mismatches"].append(f"codec {cd} vs {cc}")


def _timeline_summary(texts: list[str]) -> dict:
    seen: dict[str, list] = {}
    for txt in texts:
        try:
            msg = json.loads(txt)
        except ValueError:
            continue
        typ = msg.get("type") if isinstance(msg, dict) else None
        if not typ:
            continue
        body = msg.get(typ)
        if isinstance(body, dict):
            status = body.get("status", "?")
        elif isinstance(body, list):
            status = f"{len(body)} rows"
        else:
            status = "?"
        if status not in seen.setdefault(typ, []):
            seen[typ].append(status)
    return seen


def collect_sockets(cap: Capture, hook: dict | None, want_channel: str, exclude: set[str]) -> list[dict]:
    """Media socket bundles for one channel, close info merged from the hook by uuid."""
    hook_by_uuid = {}
    for w in (hook or {}).get("ws", []):
        m = UUID_RE.search(w["url"])
        if m:
            hook_by_uuid[m.group(0)] = w
    socks = []
    for url in cap.media_urls():
        if url in exclude:
            continue
        name = parse_ws_name(url)
        if name.get("channel") != want_channel:
            continue
        t_open, wall_open = cap.opened.get(url, (None, None))
        m = UUID_RE.search(url)
        hk = hook_by_uuid.get(m.group(0)) if m else None
        socks.append({"url": url, "name": name, "t_open": t_open, "wall_open": wall_open,
                      "frames": cap.frames[url], "close": (hk or {}).get("close"),
                      "closed_t": cap.closed.get(url), "error": cap.errors.get(url)})
    socks.sort(key=lambda s: s["t_open"] or 0)
    return socks


def browser_health(channels: list[dict], seconds: int, timeout_s: int, headed: bool,
                   browser_channel: str | None) -> dict[int, dict]:
    """Drop each camera on Views in turn and bundle its sockets. Returns id -> bundle."""
    results: dict[int, dict] = {}
    lower = [c["name"].strip().lower() for c in channels]
    with sync_playwright() as p:
        browser, page, views, cap = open_browser(p, headed, browser_channel)
        try:
            for i, ch in enumerate(channels):
                cid, name = ch["id"], ch["name"]
                bundle: dict = {"sockets": [], "timeline_text": [], "note": None}
                results[cid] = bundle
                if lower.index(name.strip().lower()) != i:
                    bundle["note"] = ("duplicate camera name: the tree drop cannot pick this id "
                                      "(use --no-browser)")
                    continue
                try:
                    _browser_capture_one(page, views, cap, cid, name, i > 0, seconds, timeout_s,
                                         bundle)
                except SystemExit as e:  # drop_camera gave up on this camera; the note says why
                    bundle["note"] = str(e)
                    continue
                except Exception as e:
                    # a Playwright timeout or a page crash on one camera must not
                    # end the sweep: it becomes this channel's note and the next
                    # camera still gets its turn
                    bundle["note"] = f"{type(e).__name__}: {str(e)[:120]}"
                    continue
                got = sum(1 for s in bundle["sockets"] for f in s["frames"] if f["opcode"] == 2)
                print(f"[health] {i + 1}/{len(channels)} {name} ({cid}): "
                      f"{len(bundle['sockets'])} socket(s), {got} binary frames")
        finally:
            browser.close()
    return results


def _browser_capture_one(page, views, cap: Capture, cid: int, name: str, reload: bool,
                         seconds: int, timeout_s: int, bundle: dict) -> None:
    """Land one camera on tile 0, hold the window, and fill its bundle from the capture."""
    if reload:
        # a full reload drops the previous tile so the next drop lands on tile 0
        page.reload()
        page.locator("text=Views").first.wait_for(state="visible", timeout=30000)
        views.navigate()
        views.wait_for_page_load()
        views.expand_site_and_show_cameras(None)
    before = set(cap.frames)
    if drop_camera(page, views, cap, name, str(cid), timeout_s):
        # the sample window itself: frames arrive on the socket, and no
        # DOM state marks its end
        page.wait_for_timeout(seconds * 1000)
    else:
        bundle["note"] = f"no media socket for channel {cid} within {timeout_s}s"
    hook = page.evaluate("() => window.__streamProbe")
    bundle["sockets"] = collect_sockets(cap, hook, str(cid), before)
    bundle["timeline_text"] = [
        f["text"] for u, fl in cap.frames.items()
        if TIMELINE_WS in u and u.endswith(f"/channel/{cid}") and u not in before
        for f in fl if "text" in f]


# --------------------------------------------------------------- direct ---
def media_url(site: int, channel: int, stream: int, app: int = 0, live: int = 1,
              timestamp: int = 0, uid: str | None = None, with_src: bool = True,
              with_name: bool = True) -> str:
    """The media socket URL the app builds (name= and src= carry the same path)."""
    uid = uid or str(uuid_mod.uuid4())
    name = f"{site}/{channel}/{app}/{live}/{stream}/{timestamp}/{uid}"
    params = []
    if with_name:
        params.append("name=" + quote(name, safe=""))
    if with_src:
        params.append("src=" + quote(SRC_PREFIX + name, safe=""))
    return f"{stream_host()}/v3/api/ws?" + "&".join(params)


async def direct_socket(url: str, headers: dict, seconds: float, handshake: str | None = HANDSHAKE) -> dict:
    """Open one WebSocket from Python, send the handshake, collect frames for `seconds`."""
    import aiohttp

    rec: dict = {"url": url, "name": parse_ws_name(url), "t_open": None, "wall_open": None,
                 "frames": [], "close": None, "error": None, "http_status": None}
    async with aiohttp.ClientSession() as session:
        rec["t_open"], rec["wall_open"] = time.monotonic(), time.time()
        try:
            # ssl=False skips certificate verification, the same allowance the
            # browser path makes with ignore_https_errors in open_browser
            ws = await asyncio.wait_for(
                session.ws_connect(url, headers=headers, ssl=False, autoping=True), 15)
        except aiohttp.WSServerHandshakeError as e:
            rec["error"] = f"handshake refused: HTTP {e.status} {e.message}"
            rec["http_status"] = e.status
            return rec
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"[:200]
            return rec
        rec["http_status"] = 101
        deadline = rec["t_open"] + seconds
        try:
            try:
                if handshake:
                    await ws.send_str(handshake)
            except aiohttp.ClientError as e:
                # the server can drop the socket before the handshake goes out
                rec["close"] = {"code": ws.close_code, "reason": str(e)[:120],
                                "type": "SEND_FAILED",
                                "after_s": round(time.monotonic() - rec["t_open"], 1)}
                return rec
            while (left := deadline - time.monotonic()) > 0:
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=left)
                except TimeoutError:
                    break
                except aiohttp.ClientError as e:
                    rec["error"] = f"{type(e).__name__}: {e}"[:200]
                    break
                now = time.monotonic()
                if msg.type == aiohttp.WSMsgType.BINARY:
                    rec["frames"].append({"opcode": 2, "t": now, "data": msg.data})
                elif msg.type == aiohttp.WSMsgType.TEXT:
                    rec["frames"].append({"opcode": 1, "t": now, "text": msg.data})
                else:
                    reason = msg.extra if isinstance(msg.extra, str) else str(msg.data)[:120]
                    rec["close"] = {"code": ws.close_code, "reason": reason, "type": msg.type.name,
                                    "after_s": round(now - rec["t_open"], 1)}
                    break
        finally:
            # closed on every exit (window over, server close, send or
            # receive error, cancel) so a socket the server keeps open
            # cannot outlive its sample
            if not ws.closed:
                await ws.close()
    return rec


def timeline_command() -> str:
    now_ms = int(time.time() * 1000)
    return json.dumps({"commandId": str(uuid_mod.uuid4()), "domainMin": now_ms - 3_600_000,
                       "domainMax": now_ms, "pivotPoint": 0, "displayMin": 0, "displayMax": 0})


async def direct_timeline(site: int, channel: int, headers: dict, seconds: float) -> dict:
    url = f"{stream_host()}/ws/timeline/site/{site}/channel/{channel}"
    return await direct_socket(url, headers, seconds, handshake=timeline_command())


def app_headers(token: str | None) -> dict:
    h = {"Origin": config["base_url"],
         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"}
    if token:
        h["Cookie"] = f"JSESSIONID={token}"
    return h


def direct_health(channels: list[dict], site: int, token: str, seconds: int,
                  stream: int) -> dict[int, dict]:
    """Open every channel's media and timeline sockets from Python, five at a time."""
    headers = app_headers(token)
    sem = asyncio.Semaphore(5)

    async def one(ch):
        async with sem:
            media, tl = await asyncio.gather(
                direct_socket(media_url(site, ch["id"], stream), headers, seconds),
                direct_timeline(site, ch["id"], headers, min(seconds, 8)))
        got = sum(1 for f in media["frames"] if f["opcode"] == 2)
        print(f"[health] {ch['name']} ({ch['id']}): {got} binary frames"
              + (f", error {media['error']}" if media["error"] else ""))
        return ch["id"], {"sockets": [media], "note": media["error"],
                          "timeline_text": [f["text"] for f in tl["frames"] if "text" in f],
                          "timeline_error": tl["error"]}

    async def run():
        # an exception from one channel's sockets must not end the sweep:
        # it becomes that channel's note and the other channels still report
        results = await asyncio.gather(*(one(c) for c in channels), return_exceptions=True)
        out: dict[int, dict] = {}
        for ch, res in zip(channels, results, strict=True):
            if isinstance(res, BaseException):
                out[ch["id"]] = {"sockets": [], "timeline_text": [], "timeline_error": None,
                                 "note": f"{type(res).__name__}: {res}"}
            else:
                out[res[0]] = res[1]
        return out

    return asyncio.run(run())


def browser_free_experiment(api: InternalApi, token: str, site: int, channel_id: int,
                            stream: int, seconds: int) -> dict:
    """Which part of the app's request lets media frames flow without a browser."""
    ua_only = {"User-Agent": app_headers(None)["User-Agent"]}
    variants = [
        ("app-like: Cookie JSESSIONID + Origin + src=", app_headers(token), True, None, None),
        ("no Cookie (Origin + src=)", app_headers(None), True, None, None),
        ("no Cookie, no Origin (src= only)", ua_only, True, None, None),
        ("bare: no Cookie, no Origin, no src=", ua_only, False, None, None),
        ("bare, no User-Agent", {}, False, None, None),
        ("uuid replaced by 'probe' (Origin, no Cookie)", app_headers(None), True, None, "probe"),
        ("src= only, no name= (Origin, no Cookie)", app_headers(None), True, False, None),
    ]

    async def run():
        rows = []
        for label, headers, with_src, with_name, uid in variants:
            url = media_url(site, channel_id, stream, uid=uid, with_src=with_src,
                            with_name=with_name is not False)
            rec = await direct_socket(url, headers, seconds)
            m = health_metrics([rec], [], None)
            rows.append({"variant": label, "url": UUID_RE.sub("<uuid>", url),
                         "http_status": rec["http_status"], "error": rec["error"],
                         "mime": m["mime"], "binary_frames": m["binary_frames"],
                         "video_fragments": m["frames"], "audio_fragments": m["audio_fragments"],
                         "analytics_frames": m["analytics_frames"],
                         "first_frame_ms": m["first_frame_ms"], "close": rec["close"]})
            print(f"[direct] {label}: http {rec['http_status']} mime={m['mime']!r} "
                  f"video {m['frames']} audio {m['audio_fragments']} analytics "
                  f"{m['analytics_frames']} close={rec['close']} error={rec['error']}")
        tl = await direct_timeline(site, channel_id, app_headers(None), 6)
        return rows, tl

    rows, tl = asyncio.run(run())
    return {
        "url_pattern": f"{stream_host()}/v3/api/ws?name=<site>/<channel>/0/1/<stream>/0/<uuid4>"
                       "&src=videonetics://<videoneticsAddr>/<same path>  "
                       "(app=0, live=1, timestamp=0 for live, uuid random v4; values from the "
                       "08/25 browser capture)",
        "handshake": HANDSHAKE,
        "login_cookie_domains": [(c.name, c.domain) for c in api.session.cookies],
        "variants": rows,
        "timeline": {"http_status": tl["http_status"], "error": tl["error"],
                     "messages": _timeline_summary([f["text"] for f in tl["frames"] if "text" in f]),
                     "headers": "Origin + User-Agent, no Cookie"},
    }


def print_health_table(rows: list[dict]) -> None:
    cols = [("channel", 24), ("online", 7), ("first_ms", 8), ("frames", 6), ("fps m/c", 12),
            ("kbps m/c", 11), ("res deliv/cfg", 22), ("codec", 8), ("kf_s", 5), ("gaps", 4),
            ("lat_ms", 7), ("recon", 5), ("analyt", 6), ("audio", 5), ("close", 22)]
    print("  ".join(h.ljust(w) for h, w in cols))
    print("-" * (sum(w for _, w in cols) + 2 * (len(cols) - 1)))
    for r in rows:
        lat = (r.get("latency_ms") or {}).get("median")
        gaps = (r.get("timestamp_gaps") or {}).get("count")
        close = r.get("close") or {}
        cells = [
            f"{r['name']} ({r['channel_id']})", str(r["online"]), _s(r["first_frame_ms"]),
            str(r["frames"]), f"{_s(r['fps_measured'])}/{_s(r['fps_configured'])}",
            f"{_s(r['bitrate_kbps_measured'])}/{_s(r['bitrate_kbps_configured'])}",
            f"{_s(r['resolution_delivered'])}/{_s(r['resolution_configured'])}",
            (r["codec_delivered"] or "-").split(" ")[0], _s(r["keyframe_interval_s"]), _s(gaps),
            _s(lat), str(r["reconnects"]), str(r["analytics_frames"]), str(r["audio_fragments"]),
            (f"{close.get('code')} {close.get('reason') or ''}"[:22] if close else "-"),
        ]
        print("  ".join(c[:w].ljust(w) for c, (_, w) in zip(cells, cols, strict=False)))
    for r in rows:
        if r.get("note") or r.get("mismatches"):
            print(f"  {r['name']} ({r['channel_id']}): "
                  + "; ".join(filter(None, [r.get("note"), *r.get("mismatches", [])])))


def _s(v) -> str:
    return "-" if v is None else str(v)


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


def pick_channels(api: InternalApi, site_id: int, camera: str | None, all_cameras: bool) -> list[dict]:
    channels = api.get(f"/REST/site/{site_id}/channel")
    if all_cameras:
        return sorted(channels, key=lambda c: c["id"])
    match = [c for c in channels if c.get("name", "").strip().lower() == camera.strip().lower()]
    if not match:
        match = [c for c in channels if camera.lower() in c.get("name", "").lower()]
    if not match:
        names = sorted(c.get("name") for c in channels)
        raise SystemExit(f"No channel named '{camera}' on site {site_id}. Present: {names}")
    return match[:1]


def run_health(args) -> int:
    seconds = args.seconds or 20
    api = InternalApi(config["base_url"], args.site_id)
    token = api.login(*_account()[:2])
    channels = pick_channels(api, args.site_id, args.camera, args.all_cameras)
    cfgs: dict[int, dict | None] = {}
    cfg_errors: dict[int, str] = {}
    stream = args.stream if args.no_browser else 1  # a tile always opens stream 1
    for ch in channels:
        try:
            rows = api.post(f"/REST/site/{args.site_id}/getCameraStreamingParameters",
                            {"channelId": ch["id"], "streamType": stream})
            cfgs[ch["id"]] = rows[0] if rows else None
        except ApiError as e:
            cfgs[ch["id"]] = None
            cfg_errors[ch["id"]] = str(e)
    print(f"[health] {len(channels)} channel(s), {seconds}s sample, "
          f"{'direct socket' if args.no_browser else 'browser tile'} capture, stream {stream}")
    started = time.monotonic()
    if args.no_browser:
        bundles = direct_health(channels, args.site_id, token, seconds, stream)
    else:
        bundles = browser_health(channels, seconds, args.timeout, args.headed, args.channel)
    elapsed = round(time.monotonic() - started)

    rows = []
    for ch in channels:
        b = bundles.get(ch["id"], {"sockets": [], "timeline_text": [], "note": "not captured"})
        m = health_metrics(b["sockets"], b["timeline_text"], cfgs.get(ch["id"]))
        m = {"channel_id": ch["id"], "name": ch["name"], "model": ch.get("model"), **m}
        notes = [n for n in (b.get("note"), m.get("note"), cfg_errors.get(ch["id"])) if n]
        m["note"] = "; ".join(notes) or None
        if b.get("timeline_error"):
            m["timeline"]["error"] = b["timeline_error"]
        rows.append(m)
    print()
    print_health_table(rows)
    online = sum(1 for r in rows if r["online"])
    print(f"\n{online} online, {len(rows) - online} offline of {len(rows)}; capture took {elapsed}s")
    if args.json:
        doc = {"mode": "health", "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
               "site_id": args.site_id, "sample_seconds": seconds,
               "capture": "direct aiohttp socket" if args.no_browser else "browser tile over CDP",
               "stream_index": stream, "capture_seconds": elapsed, "online": online,
               "offline": len(rows) - online, "channels": rows}
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(_jsonable(doc), indent=1), encoding="utf-8")
        print(f"health json: {args.json}")
    return 0


def run_experiment(args) -> int:
    seconds = args.seconds or 8
    api = InternalApi(config["base_url"], args.site_id)
    token = api.login(*_account()[:2])
    ch = pick_channels(api, args.site_id, args.camera, False)[0]
    print(f"[direct] channel {ch['id']} '{ch['name']}', stream {args.stream}, {seconds}s per variant")
    result = browser_free_experiment(api, token, args.site_id, ch["id"], args.stream, seconds)
    print(f"\nurl pattern: {result['url_pattern']}")
    print(f"login cookies: {result['login_cookie_domains']}")
    print(f"timeline socket (no cookie): http {result['timeline']['http_status']} "
          f"messages {result['timeline']['messages']} error {result['timeline']['error']}")
    working = [v["variant"] for v in result["variants"] if v["video_fragments"]]
    print(f"variants that delivered video: {working or 'none'}")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(_jsonable(result), indent=1), encoding="utf-8")
        print(f"experiment json: {args.json}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--camera", default=None,
                        help="camera name as shown in the Views tree (default: test_camera_name in "
                             "config/env/, or the camera the run reads from the server)")
    parser.add_argument("--site-id", type=int, default=None,
                        help="site to probe (default: default_site_id in config/env/)")
    parser.add_argument("--seconds", type=int, default=None,
                        help="capture window per player (facts: 12, health: 20, --no-browser "
                             "experiment: 8 per variant)")
    parser.add_argument("--fullscreen", action="store_true",
                        help="also open full screen (stream 0); facts mode only, ignored under "
                             "--health and --no-browser")
    parser.add_argument("--no-api", action="store_true",
                        help="skip the internal API reads; facts mode only, ignored under "
                             "--health and --no-browser (both always read the API)")
    parser.add_argument("--headed", action="store_true",
                        help="show the browser window; ignored under --no-browser")
    parser.add_argument("--channel", help="Playwright browser channel, e.g. chrome or msedge, "
                        "to check decode support outside the bundled Chromium; ignored under "
                        "--no-browser")
    parser.add_argument("--json", type=Path, help="write all raw facts here")
    parser.add_argument("--health", action="store_true",
                        help="per-channel health table instead of the facts rows")
    parser.add_argument("--all-cameras", action="store_true",
                        help="health for every channel on the site")
    parser.add_argument("--no-browser", action="store_true",
                        help="open the media socket from Python (aiohttp); alone it runs the "
                             "authorisation experiment, with --health it is the capture path")
    parser.add_argument("--stream", type=int, default=1,
                        help="stream index for --no-browser (1 = tile, 0 = full screen)")
    parser.add_argument("--timeout", type=int, default=20,
                        help="seconds to wait for the media socket before a channel is offline "
                             "(browser path only; --no-browser uses a fixed 15 s connect timeout)")
    args = parser.parse_args()
    if args.site_id is None:
        fill_site_and_camera_from_server()
        args.site_id = _account()[2]
    if not args.camera:
        args.camera = config.get("test_camera_name")

    if not args.camera and not (args.health and args.all_cameras):
        parser.error("--camera or --all-cameras (with --health) required")
    if args.no_browser and not args.health:
        return run_experiment(args)
    if args.health:
        return run_health(args)
    args.seconds = args.seconds or 12

    api_data = None
    if not args.no_api:
        api = InternalApi(config["base_url"], args.site_id)
        api.login(*_account()[:2])
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
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"api": api_data, "browser": _jsonable(bro), "rows": rows},
                                        indent=1), encoding="utf-8")
        print(f"\nraw facts: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
