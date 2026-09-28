"""Say what a run found where people read: one Slack message a day, one line per
run, and the runs that should have happened and did not.

Until now a nightly that failed, or never ran, was found by somebody opening
the archive. This posts to the webhook in .env (SLACK_WEBHOOK_URL) a header
with the date and one line per run folder of today that has not been announced
yet. Each line leads with the number that needs a person, "N to look at", then
the known defects, the counts, the camera and a link. A state file keeps the
announced names, so the nightly can announce at its end and an 11:00 UTC sweep
can catch what it missed without saying anything twice.

    python tools/announce_run.py --archive /data/qa/runs --state /data/qa/ci/announced.json \\
        --expect india us c2c spartan20 [--dry-run] [--date 2026-09-25]

Exit 0: posted (or dry run). 1: the post failed. 2: no webhook. Never prints the webhook.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

BASE_URL = "http://10.2.0.2/qa-runs/"
WEBHOOK_ENV = "SLACK_WEBHOOK_URL"
# The order the lines take: the boxes, the lab cameras, then the Windows machine.
ORDER = {"india": 0, "us": 1, "c2c": 2}
# How each run is written: the boxes and the lab cameras as names, not config keys.
NAMES = {"india": "India", "us": "US", "c2c": "C2C", "spartan20": "Spartan20"}
RED = ":red_circle:"
GREEN = ":large_green_circle:"
WARN = ":warning:"


def webhook(environ=None, env_file: Path | None = None) -> str | None:
    """The webhook from the environment, else from .env. Never printed."""
    environ = os.environ if environ is None else environ
    url = (environ.get(WEBHOOK_ENV) or "").strip()
    if url:
        return url
    try:
        from dotenv import dotenv_values
        return (dotenv_values(env_file or ENV_FILE).get(WEBHOOK_ENV) or "").strip() or None
    except Exception:
        return None


ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_summary(folder: Path) -> dict | None:
    try:
        data = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):  # why: a folder with no readable record is not a run to announce; the sweep names it as missing when it was expected
        return None
    return data if isinstance(data, dict) else None


def provenance(summary: dict) -> dict:
    p = summary.get("provenance")
    return p if isinstance(p, dict) else {}


def kind_of(name: str, prov: dict) -> str:
    """Which expected run a folder satisfies: c2c, spartan20, india or us."""
    if "__tests-c2c" in name:
        return "c2c"
    if str(prov.get("host") or "").lower() == "spartan20":
        return "spartan20"
    return str(prov.get("box") or "").lower() or "unknown"


def label_of(name: str, prov: dict) -> str:
    """What the line calls the run: the box, and the machine when it is not the usual one."""
    kind = kind_of(name, prov)
    if kind == "c2c":
        return NAMES["c2c"]
    box = str(prov.get("box") or "").lower() or "unknown"
    box = NAMES.get(box, box)
    # The Windows machine runs a box too; "us, from spartan20" hid an india leg
    # behind a us label for 3 days (09/26-09/28/2026).
    return f"{box} · {NAMES['spartan20']}" if kind == "spartan20" else box


def sort_key(name: str, prov: dict) -> tuple:
    kind = kind_of(name, prov)
    box = str(prov.get("box") or "").lower()
    return (ORDER.get(kind, 3), ORDER.get(box, 9), name)


def tests_of(summary: dict) -> list[dict]:
    t = summary.get("tests") or []
    return list(t.values()) if isinstance(t, dict) else [x for x in t if isinstance(x, dict)]


def line_for(name: str, summary: dict, base_url: str = BASE_URL) -> str:
    """One Slack line, leading with the number that needs a person.

    `N to look at` is the failures the register does not already explain; it is
    the number a reader acts on, so it comes first and in bold. The known
    defects follow as a count, then passed and skipped, the camera, the link.
    A record archived before the known-defect field existed says `N failed`
    instead, because "0 known" would be a claim nobody measured.
    """
    prov = provenance(summary)
    counts = summary.get("counts") if isinstance(summary.get("counts"), dict) else {}
    tests = tests_of(summary)
    failed = int(counts.get("failed") or 0) + int(counts.get("errors") or 0)
    red = [t for t in tests if str(t.get("outcome") or "").lower() in ("failed", "error")]
    has_known_field = any("known_defect" in t for t in tests)
    known = sum(1 for t in red if isinstance(t.get("known_defect"), dict))
    look = len(red) - known if has_known_field else failed

    if not failed:
        lead, mark = "Nothing to look at", GREEN
    elif has_known_field:
        lead = f"*{look} to look at*" if look else "Nothing to look at"
        mark = RED if look else GREEN
    else:
        lead, mark = f"*{failed} failed*", RED
    parts = [lead]
    if has_known_field and known:
        parts.append(f"{known} known")
    parts.append(f"{int(counts.get('passed') or 0)} passed")
    parts.append(f"{int(counts.get('skipped') or 0)} skipped")
    # No camera on the c2c line: that run drives the lab cameras by registry,
    # and the record's camera is the box default, which means nothing there.
    if prov.get("camera") and kind_of(name, prov) != "c2c":
        parts.append(str(prov["camera"]))
    parts.append(f"<{base_url}{name}/run.html|Run page>")
    return f"{mark} *{label_of(name, prov)}* — " + " · ".join(parts)


def header(day: str) -> str:
    try:
        d = date.fromisoformat(day)
        return f"*QA runs — {d.strftime('%a %d %b %Y')}*"
    except ValueError:
        return f"*QA runs — {day}*"


def todays_runs(archive: Path, day: str) -> list[tuple[str, dict]]:
    out = []
    for folder in sorted(archive.glob(f"{day}_*")):
        if folder.is_dir():
            summary = load_summary(folder)
            if summary is not None:
                out.append((folder.name, summary))
    return sorted(out, key=lambda ns: sort_key(ns[0], provenance(ns[1])))


def load_state(path: Path | None) -> set[str]:
    if not path:
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {str(x) for x in data} if isinstance(data, list) else set()
    except (OSError, ValueError):  # why: no state yet is the first run; a broken file is a fresh start, which repeats at most one day's lines
        return set()


def save_state(path: Path | None, names: set[str]) -> None:
    if path:
        path.write_text(json.dumps(sorted(names), indent=0) + "\n", encoding="utf-8")


def compose(archive: Path, day: str, expect: list[str], announced: set[str], now_utc: str,
            base_url: str = BASE_URL) -> tuple[str, list[str]]:
    """The message and the names it announces. '' when there is nothing to say."""
    runs = todays_runs(archive, day)
    seen = {kind_of(n, provenance(s)) for n, s in runs}
    fresh = [(n, s) for n, s in runs if n not in announced]
    lines = [line_for(n, s, base_url) for n, s in fresh]
    names = [n for n, _ in fresh]
    missing = [k for k in expect if k not in seen]
    marker = f"missing:{day}"
    if missing and marker not in announced:
        lines.append(f"{WARN} *Missing today:* {', '.join(NAMES.get(k, k) for k in missing)} — no run folder for {day} in the archive at {now_utc} UTC")
        names.append(marker)
    if not lines:
        return "", []
    return "\n".join([header(day), *lines]), names


def post(url: str, text: str, timeout: int = 15) -> int:
    """POST the message; the HTTP status, or 0 when the request itself failed."""
    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return int(r.status)
    except urllib.error.HTTPError as e:
        return int(e.code)
    except (urllib.error.URLError, OSError, ValueError) as e:  # why: say the class, never the URL, and let the caller return 1
        print(f"announce: the post failed: {type(e).__name__}")
        return 0


def main(argv=None, environ=None, sender=post, env_file: Path | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--archive", required=True, type=Path, help="the served runs directory")
    ap.add_argument("--state", type=Path, help="JSON list of the names already announced")
    ap.add_argument("--expect", nargs="*", default=[], help="runs that must exist today: india us c2c spartan20")
    ap.add_argument("--date", help="YYYY-MM-DD, default today (UTC)")
    ap.add_argument("--base-url", default=BASE_URL)
    ap.add_argument("--dry-run", action="store_true", help="print the message, post nothing, record nothing")
    a = ap.parse_args(argv)

    now = datetime.now(UTC)
    day = a.date or now.strftime("%Y-%m-%d")
    announced = load_state(a.state)
    text, names = compose(a.archive, day, a.expect, announced, now.strftime("%H:%M"), a.base_url)
    if not text:
        print(f"announce: nothing new for {day}")
        return 0
    print(text)
    if a.dry_run:
        return 0
    url = webhook(environ, env_file)
    if not url:
        print(f"announce: {WEBHOOK_ENV} is not set in the environment or .env; nothing posted")
        return 2
    status = sender(url, text)
    if status != 200:
        print(f"announce: Slack answered HTTP {status}; nothing recorded, the sweep will try again")
        return 1
    save_state(a.state, announced | set(names))
    print(f"announce: posted {len(names)} line(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
