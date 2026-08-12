"""Open the app logged in and explore it - the probe harness.

This is the tool that cracked the assign-modal and favorites repairs
(see docs/TEST_REPAIRS.md): it reuses the repo's page objects and auth
so an exploration session starts where a test would, without pytest.

Usage:
  python tools/explore_app.py                  # interactive REPL
  python tools/explore_app.py probe.py         # run a probe script
  python tools/explore_app.py --headed         # watch the browser

In the REPL or probe script these names are in scope:
  page      - the Playwright page, logged in, on the app
  config    - the active env config dict
  pw        - the sync_playwright handle
  snap      - snap("label") saves a screenshot to reports/probe_shots/
              and prints its path

Probe scripts are plain Python run with exec(); print what you learn.
Snap at every decision point: a screenshot settles layout questions
(what covers what, where a panel floats) that DOM dumps argue about.

Lessons already paid for (keep them in mind when probing):
- position:fixed overlays (MUI modals) have offsetParent === null, so
  offsetParent-based visibility filters MISS them. Probe with
  getComputedStyle or Playwright's is_visible instead.
- The Views camera tree collapses itself a few seconds after
  expansion. Probe state decays; act immediately or re-expand.
- A leftover modal backdrop blocks every later click. Close what you
  open.
"""
import argparse
import code
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
os.chdir(REPO)
load_dotenv()

from config.base_config import config  # noqa: E402
from tests.shared.pages.login_page import LoginPage  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("script", nargs="?",
                        help="probe script to run (default: REPL)")
    parser.add_argument("--headed", action="store_true",
                        help="show the browser window")
    args = parser.parse_args()

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        state = ".auth_state.json"
        context = (browser.new_context(storage_state=state)
                   if Path(state).exists() else browser.new_context())
        page = context.new_page()
        page.goto(config["base_url"], wait_until="domcontentloaded")
        page.wait_for_timeout(4000)  # app bootstrap has no ready signal
        if "/auth/login" in page.url:
            print("[EXPLORE] Cached session stale, logging in fresh")
            LoginPage(page).login(
                os.environ["QA_USER"], os.environ["QA_PASSWORD"]
            )

        shots = REPO / "reports" / "probe_shots"
        counter = {"n": 0}

        def snap(label: str = "probe") -> str:
            """Save a screenshot; the path prints so it can be opened."""
            shots.mkdir(parents=True, exist_ok=True)
            counter["n"] += 1
            path = shots / f"{label}_{counter['n']:02d}.png"
            page.screenshot(path=str(path))
            print(f"[SNAP] {path}")
            return str(path)

        scope = {"page": page, "config": config, "pw": pw, "snap": snap}
        if args.script:
            source = Path(args.script).read_text(encoding="utf-8")
            exec(compile(source, args.script, "exec"), scope)  # noqa: S102
        else:
            code.interact(
                banner="page, config, pw are in scope. Ctrl-Z to exit.",
                local=scope,
            )
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
