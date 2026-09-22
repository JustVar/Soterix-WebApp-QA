#!/usr/bin/env python3
"""Measure one livestream on one browser: the Chrome this machine launches, or a Chrome that a
Playwright server on another machine launches (`--ws ws://host:3000/`).

    BOX=us python tools/livestream_bench.py                      # this machine's Chrome, headless
    BOX=us python tools/livestream_bench.py --headed
    BOX=us python tools/livestream_bench.py --ws ws://10.2.0.39:3000/ --headed --seconds 20

Read-only on the tenant: it logs in, drops the box's test camera on a Views tile, and reads the
tile's <video> for `--seconds`. It prints one JSON line: whether the browser decodes the codec,
the seconds to the first frame, the frames in the window, the restarts of the stream, the frame
rate over the last 10 s, the wall time of login and navigation, and the time of one screenshot.
The livestream tests need the frame rate;
the rest says what a remote browser costs (measured 09/22/2026 for the Windows runner question).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.base_config import config
from tests.shared.helpers.stream_health import MSE_TYPES, chrome_args
from tests.shared.pages.login_page import LoginPage
from tests.shared.pages.views_page import ViewsPage
from tools.stream_probe import TILE, VIDEO_STATE_JS, _account


def open_browser(p, args):
    """Launch here, or connect to the server named by --ws: the server launches the Chrome."""
    if args.ws:
        options = {"channel": "chrome", "headless": not args.headed}
        if chrome_args():
            options["args"] = chrome_args()
        endpoint = f"{args.ws}?browser=chromium&launch-options={quote(json.dumps(options))}"
        return p.chromium.connect(endpoint, timeout=60000)
    return p.chromium.launch(channel="chrome", headless=not args.headed, args=chrome_args())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ws", help="a Playwright server's endpoint; the browser runs there")
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--seconds", type=int, default=15, help="how long to watch the tile")
    parser.add_argument("--camera", default=config.get("test_camera_name"))
    args = parser.parse_args()
    from playwright.sync_api import sync_playwright

    out: dict = {"where": args.ws or "local", "headed": args.headed, "camera": args.camera, "box": os.environ.get("BOX")}
    with sync_playwright() as p:
        t0 = time.perf_counter()
        browser = open_browser(p, args)
        out["connect_s"] = round(time.perf_counter() - t0, 1)
        out["browser"] = browser.version
        ctx = browser.new_context(ignore_https_errors=True, viewport={"width": 1600, "height": 900})
        page = ctx.new_page()
        page.goto("about:blank")
        out["decodes"] = {codec: page.evaluate(
            "types => types.some(t => window.MediaSource && MediaSource.isTypeSupported(t))", types)
            for codec, types in MSE_TYPES.items()}
        t1 = time.perf_counter()
        page.goto(config["base_url"])
        LoginPage(page, config["base_url"]).login(*_account()[:2])
        page.wait_for_function("() => !window.location.href.includes('/auth/login')", timeout=60000)
        views = ViewsPage(page)
        views.navigate()
        views.wait_for_page_load()
        views.expand_site_and_show_cameras(None)
        out["login_and_views_s"] = round(time.perf_counter() - t1, 1)
        t2 = time.perf_counter()
        views.add_camera_via_checkbox(args.camera)
        page.locator(TILE).first.wait_for(state="attached", timeout=15000)
        first = None
        total, last, restarts, rate_samples = 0, 0, 0, []
        while time.perf_counter() - t2 < args.seconds:
            time.sleep(1)
            videos = page.evaluate(VIDEO_STATE_JS)
            frames = max((v.get("frames") or 0) for v in videos) if videos else 0
            if frames and first is None:
                first = round(time.perf_counter() - t2, 1)
            # the player replaces its <video> when the stream reconnects, and the count starts again
            if frames < last:
                restarts += 1
                last = 0
            total += frames - last
            last = frames
            rate_samples.append((time.perf_counter() - t2, total))
        out["first_frame_s"] = first
        out["frames"] = total
        out["restarts"] = restarts
        # the rate over the last 10 s, when the stream was up for them
        window = [(t, f) for t, f in rate_samples if t >= rate_samples[-1][0] - 10]
        out["fps"] = round((window[-1][1] - window[0][1]) / (window[-1][0] - window[0][0]), 1) if len(window) > 1 else None
        t3 = time.perf_counter()
        page.screenshot(path=str(ROOT / "logs" / "livestream_bench.png"))
        out["screenshot_s"] = round(time.perf_counter() - t3, 2)
        browser.close()
    print(json.dumps(out))
    return 0 if out.get("fps") else 1


if __name__ == "__main__":
    sys.exit(main())
