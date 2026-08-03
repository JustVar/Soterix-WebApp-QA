#!/usr/bin/env python3
"""Discover C2C camera specs from the live devices and emit the test registry.

The C2C tests assert model, manufacturer, max resolution and max framerate
against what the camera reports, so those values have to come from the devices
themselves - a hand-typed registry silently rots the moment the lab re-addresses
or swaps hardware.

This logs into each camera's Setup > System Information page, scrapes the fields
the tests rely on, and writes a ready-to-use tests/data/c2c_cameras.yaml.

Usage:
    # Discover from an inventory CSV (model,serial,ip,mac,rtsp)
    python tools/discover_c2c_cameras.py --inventory c2c_inventory.csv

    # Or straight from a list of IPs
    python tools/discover_c2c_cameras.py --ips 10.2.0.116 10.2.0.117

    # Preview without writing the registry
    python tools/discover_c2c_cameras.py --ips 10.2.0.116 --dry-run

Credentials come from C2C_CAMERA_USER / C2C_CAMERA_PASS, defaulting to the
lab's shared login. Unreachable cameras are recorded as enabled: false with a
note, rather than being dropped - the lab rotates devices in and out.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import socket
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "tests" / "data" / "c2c_cameras.yaml"

USER = os.environ.get("C2C_CAMERA_USER", "root")
PASSWORD = os.environ.get("C2C_CAMERA_PASS", "***REMOVED***")

PROBE_TIMEOUT = 2.0
NAV_TIMEOUT = 20000


def reachable(ip: str, port: int = 80) -> bool:
    """Quick TCP check so we do not wait out a full navigation timeout."""
    try:
        with socket.create_connection((ip, port), timeout=PROBE_TIMEOUT):
            return True
    except OSError:
        return False


def slug(model: str, ip: str) -> str:
    """Stable, readable test id for a camera."""
    base = (model or "cam").strip().lower().replace(" ", "-").replace("/", "-")
    return f"{base}-{ip.rsplit('.', 1)[-1]}"


def scrape_system_info(page, ip: str) -> dict:
    """Read Setup > System Information for one camera."""
    page.goto(
        f"http://{ip}/cgi-bin/admin/setup_main.cgi",
        wait_until="domcontentloaded",
        timeout=NAV_TIMEOUT,
    )
    page.locator("text='SYSTEM'").first.click()
    page.wait_for_timeout(500)
    page.locator("text='SYSTEM INFORMATION'").first.click()
    page.wait_for_timeout(1000)

    fields = [
        "Model name", "Serial number", "Manufacturer", "Max resolution",
        "Max framerate", "Photo resistor(CDS)", "Alarm in", "Relay out",
        "Audio", "Optical zoom", "Digital zoom", "PTZ", "AI", "ONVIF",
    ]
    info: dict[str, str | None] = {}
    for field in fields:
        try:
            row = page.locator(f"text='{field}'").first.locator("..")
            info[field] = row.locator("td").last.inner_text().strip()
        except Exception:
            info[field] = None
    return info


def discover_one(browser, cam: dict) -> dict:
    """Return the registry entry for one camera, reachable or not."""
    ip = cam["ip"]
    entry = {
        "id": cam.get("id") or slug(cam.get("model", ""), ip),
        "ip": ip,
        "user": USER,
        "password": PASSWORD,
    }
    for k in ("mac", "serial", "rtsp"):
        if cam.get(k):
            entry[k] = cam[k]

    if not reachable(ip):
        entry["enabled"] = False
        entry["note"] = "unreachable at discovery time - no TCP connect on :80"
        entry["model"] = cam.get("model") or "UNKNOWN"
        return entry

    context = browser.new_context(
        http_credentials={"username": USER, "password": PASSWORD},
        ignore_https_errors=True,
    )
    try:
        page = context.new_page()
        info = scrape_system_info(page, ip)
        entry["enabled"] = True
        entry["model"] = info.get("Model name") or cam.get("model") or "UNKNOWN"
        entry["manufacturer"] = info.get("Manufacturer") or "UNKNOWN"
        entry["max_resolution"] = info.get("Max resolution") or "UNKNOWN"
        # "30 fps" -> 30
        fr = (info.get("Max framerate") or "").split()
        entry["max_framerate"] = int(fr[0]) if fr and fr[0].isdigit() else None
        if info.get("Serial number"):
            entry["serial"] = info["Serial number"]
        if info.get("ONVIF"):
            entry["onvif_version"] = info["ONVIF"]
        entry["features"] = {
            "audio": info.get("Audio"),
            "optical_zoom": info.get("Optical zoom"),
            "digital_zoom": info.get("Digital zoom"),
            "ptz": info.get("PTZ"),
            "ai": info.get("AI"),
            "alarm_in": info.get("Alarm in"),
            "relay_out": info.get("Relay out"),
            "cds": info.get("Photo resistor(CDS)"),
        }
        entry["_raw"] = info
    except Exception as e:
        entry["enabled"] = False
        entry["note"] = f"reachable but discovery failed: {type(e).__name__}: {e}"
        entry["model"] = cam.get("model") or "UNKNOWN"
    finally:
        context.close()
    return entry


def load_inventory(path: Path) -> list[dict]:
    """Read model,serial,ip,mac,rtsp rows. Repeated IPs collapse to one camera
    with a channel count (multi-lens devices list one RTSP URL per lens)."""
    cams: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ip = (row.get("ip") or "").strip()
            if not ip:
                continue
            cam = cams.setdefault(ip, {
                "ip": ip,
                "model": (row.get("model") or "").strip(),
                "serial": (row.get("serial") or "").strip(),
                "mac": (row.get("mac") or "").strip(),
                "channels": 0,
            })
            if (row.get("rtsp") or "").strip():
                cam["channels"] += 1
    return list(cams.values())


def to_yaml(entries: list[dict]) -> str:
    """Render the registry. Written by hand so the output keeps the comments
    and field order a human reader expects."""
    out = [
        "# C2C Camera Registry - GENERATED",
        f"# Produced by tools/discover_c2c_cameras.py on {datetime.now():%Y-%m-%d %H:%M}.",
        "#",
        "# Values under each camera were read from the device's",
        "# Setup > System Information page, not typed by hand. Re-run the tool",
        "# after the lab re-addresses or swaps hardware rather than editing here:",
        "#     python tools/discover_c2c_cameras.py --inventory <inventory.csv>",
        "#",
        "# enabled: false marks a camera that did not answer at discovery time.",
        "# Set it true once the device is back and re-run discovery to fill specs.",
        "",
        "cameras:",
    ]
    for e in entries:
        out.append(f"  - id: {e['id']}")
        out.append(f"    enabled: {str(e.get('enabled', False)).lower()}")
        out.append(f"    ip: {e['ip']}")
        out.append(f"    user: {e['user']}")
        out.append(f'    password: "{e["password"]}"')
        out.append(f"    model: {e.get('model', 'UNKNOWN')}")
        for key in ("serial", "mac"):
            if e.get(key):
                out.append(f"    {key}: {e[key]}")
        if e.get("manufacturer"):
            out.append(f"    manufacturer: {e['manufacturer']}")
        if e.get("max_resolution"):
            out.append(f"    max_resolution: {e['max_resolution']}")
        if e.get("max_framerate") is not None:
            out.append(f"    max_framerate: {e['max_framerate']}")
        lenses = e.get("lens_count", 1)
        out.append(f"    lens_count: {lenses}")
        out.append(f"    multi_lens: {str(lenses > 1).lower()}")
        if lenses > 1:
            out.append(f"    total_lenses: {lenses}")
        out.append(f"    expected_license: {e.get('expected_license', 'ProAI 1ch')}")
        out.append(f"    expected_license_count: {e.get('expected_license_count', lenses)}")
        if e.get("onvif_version"):
            out.append(f'    onvif_version: "{e["onvif_version"]}"')
        if e.get("features") and any(e["features"].values()):
            out.append("    features:")
            for k, v in e["features"].items():
                if v:
                    out.append(f"      {k}: {v}")
        if e.get("note"):
            out.append(f"    # {e['note']}")
        out.append("")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--inventory", type=Path, help="CSV: model,serial,ip,mac,rtsp")
    src.add_argument("--ips", nargs="+", help="Explicit IP list")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true", help="Print, do not write")
    ap.add_argument("--json", type=Path, help="Also dump raw scrape results here")
    args = ap.parse_args()

    cams = (load_inventory(args.inventory) if args.inventory
            else [{"ip": ip, "channels": 1} for ip in args.ips])
    print(f"discovering {len(cams)} camera(s) as {USER}...\n")

    from playwright.sync_api import sync_playwright

    entries = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            for cam in sorted(cams, key=lambda c: [int(p) for p in c["ip"].split(".")]):
                cam["lens_count"] = max(1, cam.get("channels", 1))
                entry = discover_one(browser, cam)
                entry["lens_count"] = cam["lens_count"]
                entry["expected_license_count"] = cam["lens_count"]
                state = "OK " if entry.get("enabled") else "SKIP"
                print(f"  [{state}] {entry['ip']:12} {entry.get('model','?'):18} "
                      f"{entry.get('max_resolution','') or ''} "
                      f"{entry.get('note','')}")
                entries.append(entry)
        finally:
            browser.close()

    ok = sum(1 for e in entries if e.get("enabled"))
    print(f"\ndiscovered {ok}/{len(entries)} reachable")

    if args.json:
        args.json.write_text(json.dumps(entries, indent=2, default=str), encoding="utf-8")
        print(f"raw results -> {args.json}")

    for e in entries:
        e.pop("_raw", None)
    yaml_text = to_yaml(entries)

    if args.dry_run:
        print("\n--- would write ---\n")
        print(yaml_text)
    else:
        args.out.write_text(yaml_text, encoding="utf-8")
        print(f"registry -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
