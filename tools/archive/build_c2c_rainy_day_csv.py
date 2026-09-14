#!/usr/bin/env python3
"""Build canonical QA Touch import CSV from the C2C rainy-day scenario list.

Source: a short scenario list (ID, Category, Scenario, Notes) of negative /
edge-case ("rainy day") tests for the Cloud 2 Cam (C2C) project.

Output: tests/data/c2c_rainy_day_test_cases.csv in the same column format as
tests/data/c2c_hardware_test_cases.csv, so it can be imported into QA Touch
project 60W5 and then step-split via tools/qatouch_c2c_step_split.py.

This is NOT a dumb templater: each category has a fault-injection-shaped step
pattern appropriate to that class of test, and the scenario title + any Notes
hint are folded into the steps, test data, and expected results so every case
reads specifically.

Usage:
    python tools/build_c2c_rainy_day_csv.py            # write CSV
    python tools/build_c2c_rainy_day_csv.py --dry-run  # print summary only
    python tools/build_c2c_rainy_day_csv.py --src PATH --out PATH
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SRC = Path(r"C:\path\to\Soterix\c2c_rainy_day_tests_v2.csv")
DEFAULT_OUT = REPO / "tests" / "data" / "c2c_rainy_day_test_cases.csv"

OUT_COLUMNS = [
    "Module_name", "Test Case Title", "Test Data", "Estimate", "Reference",
    "Precondition", "Steps", "Expected_result", "Test Suite", "Tags",
    "Description", "Type", "Priority", "Mode", "Created By",
]

TEST_SUITE = "C2C Rainy Day"

# ── Category configuration ────────────────────────────────────────────────
# Each entry: precondition, type, default priority, default tags, mode, and a
# step/expected builder. Builders receive (scenario, notes) and return
# (steps:list[str], expected:list[str], test_data:str).

def _ascii(s: str) -> str:
    """Normalize smart punctuation to ASCII so QA Touch import never mojibakes."""
    if not s:
        return s
    repl = {
        "\u2013": " - ", "\u2014": " - ",  # en/em dash
        "\u2018": "'", "\u2019": "'",        # smart single quotes
        "\u201c": '"', "\u201d": '"',        # smart double quotes
        "\u2026": "...", "\ufffd": "-",      # ellipsis, replacement char
        "\u00a0": " ",                        # nbsp (keys escaped: a typography sweep flattened them once)
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    return s


def _join(lines: list[str]) -> str:
    return "\n".join(_ascii(x) for x in lines)


def auth_steps(scenario, notes):
    steps = [
        "1. Log in to the Cloud 2 Cam web app as a user with an active session and at least one online camera",
        "2. Open a live view so a protected resource is actively in use",
        f"3. Induce the condition under test: {scenario.lower()}",
        "4. Without reloading, attempt a protected action (refresh stream, open settings, request a clip)",
        "5. Reload the page / re-open the app and repeat the protected action",
        "6. Observe the auth handling, any error messaging, and audit/log entries",
    ]
    expected = [
        "2. Live view loads and streams normally before the condition is induced",
        "4. The in-flight action is blocked the moment the credential is no longer valid - no stale data is served",
        "5. The user is cleanly redirected to re-authenticate (login / token refresh) rather than seeing a broken page or a silent failure",
        "6. No protected content leaks after the auth state changes; the event is recorded in the audit log",
    ]
    return steps, expected, "Valid user account; one or more cameras online and streaming"


def security_steps(scenario, notes):
    steps = [
        "1. Authenticate to the Cloud 2 Cam app/API as a low-privilege (or attacker-controlled) user",
        f"2. Identify the target surface for: {scenario}",
        "3. Craft the malicious input / request for the attack described in the scenario",
        "4. Submit the payload through the UI field or directly against the API endpoint",
        "5. Observe the immediate response, what gets persisted, and how it renders when later viewed",
        "6. Check audit logs and confirm no cross-tenant or privilege boundary was crossed",
    ]
    expected = [
        "4. The input is rejected or sanitized server-side; the request does not succeed in its malicious intent",
        "5. No script executes, no SQL is interpreted, no other tenant's/user's resource is returned or mutated",
        "6. The attempt is logged; the system remains stable and returns a safe, non-revealing error",
    ]
    td = (notes or "").strip() or "Attacker tooling (Burp/curl); a second tenant or low-privilege account for boundary checks"
    return steps, expected, td


def api_steps(scenario, notes):
    steps = [
        "1. Obtain a valid API token for a Cloud 2 Cam integration client",
        f"2. Set up the request load for: {scenario}",
        "3. Issue requests at and beyond the documented rate/volume limit",
        "4. Observe response codes, headers, and server stability",
    ]
    expected = [
        "3. Requests within the limit succeed (2xx)",
        "4. Requests over the limit are throttled with HTTP 429 and a Retry-After header; the service stays healthy and recovers when load drops",
    ]
    return steps, expected, (notes or "").strip() or "API base URL + valid integration token"


def qr_steps(scenario, notes):
    steps = [
        "1. Prepare the provisioning QR code for the condition under test",
        "2. Open the Cloud 2 Cam mobile app and start the QR provisioning flow",
        f"3. Scan the QR under the scenario condition: {scenario}",
        "4. Observe app behavior, resulting site/camera state, and any error messaging",
    ]
    expected = [
        "3. The scan is processed (or rejected) according to the scenario",
        "4. Happy paths load the correct site/cameras; invalid/expired/replayed/mismatched codes produce a clear, specific error and provision nothing",
    ]
    return steps, expected, (notes or "").strip() or "Valid + invalid/expired provisioning QR codes; mobile app installed"


def firmware_steps(scenario, notes):
    steps = [
        "1. Enroll a camera to Cloud 2 Cam and confirm it appears online",
        f"2. Put the camera/license/firmware into the state under test: {scenario}",
        "3. Attempt to view live and recorded video and inspect plugin/branding state",
        "4. Observe streaming behavior, any block, and the message shown to the user",
    ]
    expected = [
        "3. Behavior matches the licensing/firmware state",
        "4. Valid license/firmware streams normally with correct branding/plugins; invalid/expired/mismatched state blocks playback with a clear, actionable message - never a silent black screen",
    ]
    return steps, expected, (notes or "").strip() or "Camera with controllable license/firmware/plugin state (dev-issued)"


def camera_steps(scenario, notes):
    steps = [
        "1. Confirm the camera is online and streaming live to Cloud 2 Cam",
        "2. Have a user actively viewing the live feed",
        f"3. On the real device, induce the fault: {scenario}",
        "4. Observe the live view, recording state, and UI status indicator during and after the fault",
        "5. Resolve the fault and confirm recovery",
    ]
    expected = [
        "3-4. The UI reflects the fault promptly and accurately (offline badge, last-frame, or specific warning) without crashing or freezing the whole app",
        "5. The camera recovers cleanly once the fault is cleared; streaming and recording resume without manual restart of the app",
    ]
    return steps, expected, (notes or "").strip() or "Physical camera on the bench with power/lens/IR access"


def sdcard_steps(scenario, notes):
    steps = [
        f"1. Seat the SD card per the scenario: {scenario}",
        "2. Bring the camera online and confirm recording configuration",
        "3. Generate motion events and let continuous recording run long enough to observe the behavior",
        "4. Verify clips/events are saved, inspect retention depth, and check for any warning shown to the user",
        "5. For rotation/eviction cases, fill the card and confirm oldest-first overwrite",
    ]
    expected = [
        "3-4. Recording and event capture behave as the scenario dictates",
        "4. WD Purple cards record + retain as expected and report retention accurately; non-WD/no-card cases behave per design (silent where specified) with no false warnings",
        "5. At capacity, the oldest footage is evicted while the newest is retained - no crash, no gap in current recording",
    ]
    return steps, expected, (notes or "").strip() or "SD cards of the capacities/brands named in the scenario"


def ui_steps(scenario, notes):
    steps = [
        "1. Log in to the Cloud 2 Cam app with representative data loaded",
        f"2. Perform the UI interaction under test: {scenario}",
        "3. Observe responsiveness, rendering, and any error or freeze",
        "4. Confirm the underlying operation completes correctly despite the stress",
    ]
    expected = [
        "2-3. The UI stays responsive and renders correctly; rapid/throttled/background conditions degrade gracefully (spinners, resumable transfers) rather than crashing",
        "4. The operation completes or fails with a clear, recoverable state - no corrupted view or lost work",
    ]
    return steps, expected, (notes or "").strip()


def concurrency_steps(scenario, notes):
    steps = [
        "1. Set up two actors (two devices, two users, or a user + a background event) against the same camera/resource",
        f"2. Trigger the concurrent operation: {scenario}",
        "3. Have both actors act as simultaneously as possible",
        "4. Observe the resulting state on both sides and in the backend",
    ]
    expected = [
        "3-4. The system resolves the race deterministically (last-write-wins, optimistic lock, or clear conflict prompt) with no data corruption",
        "4. Neither actor sees a crash or an inconsistent view; the persisted state is coherent and explainable",
    ]
    return steps, expected, (notes or "").strip() or "Two browser sessions / devices with access to the same camera"


def webhook_steps(scenario, notes):
    steps = [
        "1. Configure a webhook subscription pointing at a controllable mock receiver",
        f"2. Configure the receiver to reproduce the condition: {scenario}",
        "3. Trigger source events (e.g. motion) that fire the webhook",
        "4. Observe delivery attempts, retry/backoff behavior, and the receiver's view of ordering/duplication",
    ]
    expected = [
        "4. Failures (500/timeout/slow) trigger bounded retry with backoff; duplicates are de-duplicated by idempotency key; out-of-order delivery is tolerated or correctable - the producer never wedges or drops events silently",
    ]
    return steps, expected, (notes or "").strip() or "Mock webhook receiver with configurable latency/status/ordering"


def network_steps(scenario, notes):
    steps = [
        "1. Establish a baseline: camera online, streaming live, recording to cloud",
        f"2. Using the tooling noted, inject the network fault: {scenario}",
        "3. Observe stream, recording, and UI status during the fault window",
        "4. Restore normal network conditions",
        "5. Verify the camera reconnects and any gap is handled per design",
    ]
    expected = [
        "3. The fault is surfaced accurately (offline/degraded indicator); the app does not hang or crash",
        "5. On restoration the camera reconnects automatically, buffered/edge recordings reconcile, and no manual intervention is required",
    ]
    return steps, expected, (notes or "").strip() or "Network fault-injection tooling (tc/netem, Clumsy, configurable firewall/DNS/NAT lab)"


def video_steps(scenario, notes):
    steps = [
        f"1. Produce or feed the video condition under test: {scenario}",
        "2. Ingest the stream/clip into Cloud 2 Cam (live and/or recorded path)",
        "3. Play back, scrub, and export the affected footage",
        "4. Observe decoder behavior, timestamps, and export integrity",
    ]
    expected = [
        "3-4. Corrupt/odd input is handled gracefully - the player skips or reports bad segments instead of crashing; timestamps stay monotonic; exports of valid ranges succeed",
        "4. DST/timezone and very-long-clip cases preserve correct wall-clock alignment and complete without truncation",
    ]
    return steps, expected, (notes or "").strip() or "Crafted/fuzzed media files or a synthetic frame source"


def generic_steps(scenario, notes):
    steps = [
        "1. Prepare the Cloud 2 Cam environment and any data/hardware the scenario requires",
        f"2. Execute the scenario: {scenario}",
        "3. Observe system behavior, output, and user-visible state",
        "4. Verify the result against the scenario's success criterion",
    ]
    expected = [
        "3-4. The system behaves correctly for this scenario with no crash, data loss, or misleading state",
    ]
    return steps, expected, (notes or "").strip()


CATEGORY = {
    "Auth":            dict(builder=auth_steps,        type="Functional",  priority="High",     mode="Manual",     tags="regression"),
    "Security":        dict(builder=security_steps,    type="Security",    priority="High",     mode="Automation", tags="regression"),
    "API":             dict(builder=api_steps,         type="Functional",  priority="Medium",   mode="Automation", tags="regression"),
    "QR Provisioning": dict(builder=qr_steps,          type="Functional",  priority="High",     mode="Manual",     tags="regression"),
    "Firmware":        dict(builder=firmware_steps,    type="Functional",  priority="High",     mode="Manual",     tags="regression"),
    "Camera":          dict(builder=camera_steps,      type="Functional",  priority="High",     mode="Manual",     tags="regression"),
    "SD Card":         dict(builder=sdcard_steps,      type="Functional",  priority="High",     mode="Manual",     tags="regression"),
    "UI":              dict(builder=ui_steps,          type="Functional",  priority="Medium",   mode="Manual",     tags="regression"),
    "Concurrency":     dict(builder=concurrency_steps, type="Functional",  priority="Medium",   mode="Manual",     tags="regression"),
    "Webhook":         dict(builder=webhook_steps,     type="Functional",  priority="Medium",   mode="Automation", tags="regression"),
    "Multi-region":    dict(builder=generic_steps,     type="Functional",  priority="Medium",   mode="Manual",     tags="regression"),
    "Network":         dict(builder=network_steps,     type="Functional",  priority="High",     mode="Manual",     tags="regression"),
    "Video":           dict(builder=video_steps,       type="Functional",  priority="Medium",   mode="Manual",     tags="regression"),
    "PVA":             dict(builder=generic_steps,     type="Functional",  priority="High",     mode="Manual",     tags="regression"),
    "Upload":          dict(builder=generic_steps,     type="Functional",  priority="Medium",   mode="Manual",     tags="regression"),
    "Provisioning":    dict(builder=qr_steps,          type="Functional",  priority="High",     mode="Manual",     tags="smoke|regression"),
    "Performance":     dict(builder=generic_steps,     type="Performance", priority="Medium",   mode="Manual",     tags="regression"),
}

# Scenario keywords that bump a case onto the smoke lane (must-pass baselines).
SMOKE_KEYWORDS = ["baseline must-pass", "happy path", "license valid", "branding correct", "site loads"]
CRITICAL_KEYWORDS = ["idor", "injection", "tenant boundary", "cross-region", "csrf", "xss", "replay"]


def build_rows(src_rows: list[dict]) -> list[dict]:
    out = []
    for r in src_rows:
        cat = (r.get("Category") or "").strip()
        scenario = (r.get("Scenario") or "").strip()
        notes = (r.get("Notes") or "").strip()
        sid = (r.get("ID") or "").strip()
        if not scenario:
            continue
        cfg = CATEGORY.get(cat, dict(builder=generic_steps, type="Functional",
                                     priority="Medium", mode="Manual", tags="regression"))
        steps, expected, test_data = cfg["builder"](scenario, notes)

        tags = cfg["tags"]
        priority = cfg["priority"]
        low = f"{scenario} {notes}".lower()
        if any(k in low for k in SMOKE_KEYWORDS) and "smoke" not in tags:
            tags = "smoke|" + tags
        if any(k in low for k in CRITICAL_KEYWORDS):
            priority = "Critical"

        title = f"Rainy day - {scenario}"
        desc = f"Negative/edge-case ({cat}): {scenario}."
        if notes:
            desc += f" Method/Note: {notes}"

        out.append({
            "Module_name": f"C2C Rainy Day > {cat}",
            "Test Case Title": _ascii(title),
            "Test Data": _ascii(test_data),
            "Estimate": "",
            "Reference": f"C2C_RD_{int(sid):03d}" if sid.isdigit() else f"C2C_RD_{sid}",
            "Precondition": "Cloud 2 Cam environment available with the camera(s), accounts, and tooling the scenario requires.",
            "Steps": _join(steps),
            "Expected_result": _join(expected),
            "Test Suite": TEST_SUITE,
            "Tags": tags,
            "Description": _ascii(desc),
            "Type": cfg["type"],
            "Priority": priority,
            "Mode": cfg["mode"],
            "Created By": "",
        })
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, default=DEFAULT_SRC)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if not args.src.exists():
        print(f"ERROR source not found: {args.src}", file=sys.stderr)
        return 1

    with args.src.open(encoding="utf-8-sig") as f:
        src_rows = list(csv.DictReader(f))

    rows = build_rows(src_rows)

    from collections import Counter
    cats = Counter(r["Module_name"] for r in rows)
    tags = Counter(r["Tags"] for r in rows)
    modes = Counter(r["Mode"] for r in rows)
    types = Counter(r["Type"] for r in rows)
    print(f"Built {len(rows)} cases from {len(src_rows)} source rows")
    print("Modules:")
    for k, v in sorted(cats.items()):
        print(f"  {k}: {v}")
    print(f"Tags: {dict(tags)}")
    print(f"Modes: {dict(modes)}")
    print(f"Types: {dict(types)}")

    if args.dry_run:
        print("\n--dry-run: not writing. Sample case:")
        s = rows[0]
        for k in OUT_COLUMNS:
            print(f"  [{k}]: {s[k][:160]}")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    print(f"\nOK wrote {len(rows)} rows -> {args.out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
