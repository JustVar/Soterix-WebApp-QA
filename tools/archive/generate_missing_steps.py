#!/usr/bin/env python3
"""Generate step definition JSON files for the 273 QA Touch cases missing local step files.

Reads step data from the CSV bulk update files (already synced to QA Touch) and writes
them into the existing step file structure under tests/steps/manual/.

Usage:
    python tools/generate_missing_steps.py analyze     # Show what would be created
    python tools/generate_missing_steps.py generate    # Create/update step files
    python tools/generate_missing_steps.py generate --dry-run  # Preview without writing
"""
from __future__ import annotations

import argparse
import csv
import functools
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

_print = print
print = functools.partial(_print, flush=True)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
STEPS_DIR = ROOT / "tests" / "steps" / "manual"
SNAPSHOT_FILE = ROOT / "config" / "qatouch_snapshots" / "snapshot_2026-03-02.json"

CSV_FILES = [
    os.path.expanduser("~/Downloads/QATouch_BulkUpdate_Part1.csv"),
    os.path.expanduser("~/Downloads/QATouch_BulkUpdate_Part2.csv"),
    os.path.expanduser("~/Downloads/QATouch_BulkUpdate_Part3.csv"),
]

# App area classification (same as qatouch_step_generator.py)
NAV_AREA_KEYWORDS: dict[str, list[str]] = {
    "admin": [
        "admin", "site detail", "site actions", "site name", "sites",
        "user", "role", "webhook", "channel", "integration",
        "audit trail", "system log", "license", "permission",
        "storage", "general", "rules", "delete user",
        "configuration", "settings",
    ],
    "views": [
        "view", "camera", "grid", "tile", "drag", "layout",
        "fullscreen", "playback", "ptz", "sequence", "bookmark",
        "audio", "snapshot", "overlay", "video", "share live",
        "devices tab", "my views", "empty grid", "live playback",
    ],
    "search": [
        "search", "category", "zone", "person", "vehicle",
        "duration", "time range", "custom date", "line",
        "date search", "date picker", "more filters",
        "camera search",
    ],
    "media": [
        "media", "clip", "vault", "folder", "export",
        "pin", "unpin", "move to folder", "pinned clips",
        "tab", "state persistence",
    ],
    "events": [
        "event", "notification", "alert",
    ],
    "insights": [
        "insight", "dashboard", "widget", "chart",
    ],
    "maps": [
        "map", "static map",
    ],
    "login": [
        "login", "logout", "session", "mfa", "multi-factor",
        "authentication", "password", "re-login", "security",
        "accessibility - login", "validation - login",
    ],
    "lpr": [
        "lpr",
    ],
}


def classify_area(module_name: str) -> str:
    """Classify module into app area."""
    lower = module_name.lower()
    for area, keywords in NAV_AREA_KEYWORDS.items():
        for kw in keywords:
            if kw in lower:
                return area
    return "other"


def safe_filename(module_name: str) -> str:
    """Convert module name to safe filename."""
    name = module_name.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name


def load_snapshot() -> dict[str, dict]:
    with open(SNAPSHOT_FILE, encoding="utf-8") as f:
        data = json.load(f)
    return {c["case_key"]: c for c in data.get("cases", [])}


def load_csv_cases(keys_needed: set[str]) -> dict[str, dict]:
    """Load CSV data for specific case keys."""
    cases = {}
    for csv_path in CSV_FILES:
        if not os.path.exists(csv_path):
            continue
        with open(csv_path, encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)  # skip header
            for row in reader:
                key = row[0].strip()
                if key not in keys_needed:
                    continue
                raw_steps = row[11].split("\n") if len(row) > 11 and row[11].strip() else []
                raw_expected = row[12].split("\n") if len(row) > 12 and row[12].strip() else []

                max_len = max(len(raw_steps), len(raw_expected))
                steps = []
                for i in range(max_len):
                    step_text = raw_steps[i].strip() if i < len(raw_steps) else ""
                    exp_text = raw_expected[i].strip() if i < len(raw_expected) else ""
                    if not step_text:
                        continue
                    steps.append({
                        "n": len(steps) + 1,
                        "action": step_text,
                        "expected": exp_text if exp_text else "",
                    })

                cases[key] = {
                    "title": row[5].strip() if len(row) > 5 else "",
                    "module": row[4].strip() if len(row) > 4 else "",
                    "steps": steps,
                }
    return cases


def get_existing_step_keys() -> set[str]:
    """Collect all case_keys from existing step files."""
    keys = set()
    for jf in STEPS_DIR.rglob("*.json"):
        if jf.name == "generated_metadata.json":
            continue
        try:
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "tests" in data:
                keys.update(data["tests"].keys())
        except Exception:
            pass
    return keys


def find_existing_file_for_module(module_name: str) -> Path | None:
    """Find an existing step file that contains this module."""
    for jf in STEPS_DIR.rglob("*.json"):
        if jf.name == "generated_metadata.json":
            continue
        try:
            with open(jf, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data.get("module_name") == module_name:
                return jf
        except Exception:
            pass
    return None


def analyze(snap: dict, csv_cases: dict, missing_keys: set):
    """Print analysis of what would be generated."""
    by_module = defaultdict(list)
    for key in missing_keys:
        mod = snap[key].get("module name", "Unknown")
        by_module[mod].append(key)

    append_count = 0
    new_file_count = 0
    modules_append = []
    modules_new = []

    for mod in sorted(by_module):
        existing = find_existing_file_for_module(mod)
        if existing:
            append_count += len(by_module[mod])
            modules_append.append((mod, len(by_module[mod]), str(existing.relative_to(ROOT))))
        else:
            new_file_count += len(by_module[mod])
            area = classify_area(mod)
            modules_new.append((mod, len(by_module[mod]), area))

    print(f"\n{'=' * 60}")
    print("  MISSING STEP FILE ANALYSIS")
    print(f"  Total missing cases: {len(missing_keys)}")
    print(f"  Modules affected: {len(by_module)}")
    print(f"  Cases to append to existing files: {append_count}")
    print(f"  Cases needing new files: {new_file_count}")
    print(f"{'=' * 60}")

    if modules_append:
        print(f"\n  APPEND to existing files ({len(modules_append)} modules, {append_count} cases):")
        for mod, count, path in sorted(modules_append, key=lambda x: -x[1]):
            print(f"    [{count:>2}] {mod} -> {path}")

    if modules_new:
        print(f"\n  NEW files needed ({len(modules_new)} modules, {new_file_count} cases):")
        for mod, count, area in sorted(modules_new, key=lambda x: -x[1]):
            print(f"    [{count:>2}] {mod} -> tests/steps/manual/{area}/{safe_filename(mod)}.json")

    # Show cases with 0 steps in CSV
    zero_step = [k for k in missing_keys if k in csv_cases and len(csv_cases[k]["steps"]) == 0]
    if zero_step:
        print(f"\n  WARNING: {len(zero_step)} cases have 0 steps in CSV:")
        for k in zero_step[:10]:
            print(f"    {k}: {snap[k].get('case_title', '')[:60]}")


def generate(snap: dict, csv_cases: dict, missing_keys: set, dry_run: bool = False):
    """Generate/update step files for missing cases."""
    by_module = defaultdict(list)
    for key in missing_keys:
        mod = snap[key].get("module name", "Unknown")
        by_module[mod].append(key)

    files_updated = 0
    files_created = 0
    cases_written = 0

    for mod in sorted(by_module):
        keys = by_module[mod]
        existing_file = find_existing_file_for_module(mod)

        if existing_file:
            # Append to existing file
            with open(existing_file, encoding="utf-8") as f:
                data = json.load(f)

            added = 0
            for key in keys:
                if key not in data["tests"] and key in csv_cases:
                    csv_case = csv_cases[key]
                    data["tests"][key] = {
                        "title": csv_case["title"],
                        "case_key": key,
                        "quality": "high",
                        "classification": "functional",
                        "steps": csv_case["steps"],
                    }
                    added += 1
                    cases_written += 1

            if added > 0:
                if not dry_run:
                    with open(existing_file, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                        f.write("\n")
                action = "would update" if dry_run else "updated"
                print(f"  {action}: {existing_file.relative_to(ROOT)} (+{added} cases)")
                files_updated += 1
        else:
            # Create new file
            area = classify_area(mod)
            area_dir = STEPS_DIR / area
            filename = safe_filename(mod) + ".json"
            filepath = area_dir / filename

            # Get module_key from snapshot
            module_key = snap[keys[0]].get("module_key", "")

            data = {
                "source": "csv-import",
                "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "module_name": mod,
                "module_key": module_key,
                "app_area": area,
                "nav_context": None,
                "test_file": None,
                "class": None,
                "tests": {},
            }

            for key in keys:
                if key in csv_cases:
                    csv_case = csv_cases[key]
                    data["tests"][key] = {
                        "title": csv_case["title"],
                        "case_key": key,
                        "quality": "high",
                        "classification": "functional",
                        "steps": csv_case["steps"],
                    }
                    cases_written += 1

            if not dry_run:
                area_dir.mkdir(parents=True, exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                    f.write("\n")
            action = "would create" if dry_run else "created"
            print(f"  {action}: {filepath.relative_to(ROOT)} ({len(data['tests'])} cases)")
            files_created += 1

    print(f"\n{'=' * 60}")
    prefix = "DRY RUN - " if dry_run else ""
    print(f"  {prefix}Files updated: {files_updated}")
    print(f"  {prefix}Files created: {files_created}")
    print(f"  {prefix}Cases written: {cases_written}")
    print(f"{'=' * 60}")


def main():
    parser = argparse.ArgumentParser(description="Generate missing step definition files")
    parser.add_argument("command", choices=["analyze", "generate"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    print("Loading data...")
    snap = load_snapshot()
    existing_keys = get_existing_step_keys()
    missing_keys = set(snap.keys()) - existing_keys

    print(f"  Snapshot: {len(snap)} cases")
    print(f"  Existing step files: {len(existing_keys)} cases")
    print(f"  Missing: {len(missing_keys)} cases")

    csv_cases = load_csv_cases(missing_keys)
    print(f"  CSV data loaded: {len(csv_cases)} cases")

    not_in_csv = missing_keys - set(csv_cases.keys())
    if not_in_csv:
        print(f"  WARNING: {len(not_in_csv)} missing cases not found in CSV")

    if args.command == "analyze":
        analyze(snap, csv_cases, missing_keys)
    elif args.command == "generate":
        generate(snap, csv_cases, missing_keys, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
