#!/usr/bin/env python3
"""Phase A RESUME - metadata-copy only for the 214 PP cases already created in 70l1.

Phase A (migrate_pp_cases_phase_a.py) ran on 2026-06-24 and successfully CREATED
214 target cases in 70l1 (codes TR0248-TR0461, split across 3 just-created modules):
  - eVMel  Admin > Users               (86 cases)
  - vKvWz  Admin > Platform Management (102 cases)
  - bRP8R  Admin > Audit Trail         (26 cases)

The follow-up metadata-copy phase failed for every case - the title-based lookup
in find_target_case_by_title() returned None for all 214 (page-ordering assumption
wrong + brittle byte-exact title compare + 429 storm with no loop-level backoff).
So every target case in 70l1 is currently a BARE shell: title only, no description,
no precondition, no reference, no type/priority/mode, no tags.

This RESUME tool finishes the metadata copy WITHOUT creating any new cases.

Strategy (see the recon notes that ship with this script):
  1. ONE full enumeration of JlW1 cases - group by source module_key in memory.
     Filter to the 3 source modules (0yxeN, EGdBv, 6ynx8).
  2. ONE full enumeration of 70l1 cases - group by (target_module_key, normalized_title).
  3. Lookup target by (target_module_key, normalized_title) - no per-case REST calls.
     Normalization: html.unescape(t).strip().
  4. For each match, fetch source + target /v1/case/edit, build the overlay payload
     via build_target_update_payload(), POST /v1/case/update, tolerate the
     500-on-success quirk via update_succeeded().
  5. Crash-safe log written after every record (full rewrite of the in-memory list).

CLI:
  python tools/migrate_pp_cases_phase_a_resume.py
    [--limit N]                  process only first N matched source cases
    [--dry-run]                  read source+target, build payload, skip the POST
    [--auth-state-file PATH]     Playwright storage state (default .qatouch_auth_state.json)
    [--rate-ms 1300]             sleep between internal calls
    [--resume-from N]            skip first N source cases (1-indexed) before processing
    [--skip-source-modules CSV]  skip these source module keys (e.g. "0yxeN,EGdBv")

Outputs:
  logs/pp_migration_phase_a_resume_{YYYYMMDD-HHMMSS}.json - per-case record.

No new cases are created. No JlW1 mutation. No deletion.
"""
from __future__ import annotations

import argparse
import functools
import html
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

_print = print
print = functools.partial(_print, flush=True)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── sys.path bootstrap (mirrors phase-A) ────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent  # playwright-soterix-qa repo root
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "tools") not in sys.path:
    sys.path.insert(0, str(ROOT / "tools"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from playwright.sync_api import sync_playwright

# Pull in everything reusable from the phase-A script - all pure helpers,
# no global state, verified at lines 306-460 of migrate_pp_cases_phase_a.py.
from migrate_pp_cases_phase_a import (  # noqa: E402
    # browser + auth
    open_browser,
    DEFAULT_AUTH_STATE,
    # internal API wrappers
    internal_get_case,
    internal_update_case,
    update_succeeded,
    # payload construction
    build_target_update_payload,
    # REST helpers
    load_rest_creds,
    fetch_all_project_cases,
    # constants
    SOURCE_PROJECT,
    TARGET_PROJECT,
)

# ── Local constants ─────────────────────────────────────────────────────────
LOG_DIR = ROOT / "logs"

# Per recon: 3 source modules in JlW1 -> 3 newly-created target modules in 70l1.
# Total newly-created target cases = 214 (TR0248-TR0461, contiguous).
SOURCE_MODULE_KEYS = ("0yxeN", "EGdBv", "6ynx8")

SOURCE_MODULE_NAMES: dict[str, str] = {
    "0yxeN": "Users",
    "EGdBv": "Platform Management",
    "6ynx8": "Audit_Trail",
}

# Hardcoded per recon - these are the just-created target modules in 70l1.
# Confirmed counts: eVMel=86, vKvWz=102, bRP8R=26 = 214 total.
TARGET_MODULE_FOR_SOURCE: dict[str, str] = {
    "0yxeN": "eVMel",  # Users
    "EGdBv": "vKvWz",  # Platform Management
    "6ynx8": "bRP8R",  # Audit Trail
}

TARGET_MODULE_NAMES: dict[str, str] = {
    "eVMel": "Admin > Users",
    "vKvWz": "Admin > Platform Management",
    "bRP8R": "Admin > Audit Trail",
}

EXPECTED_TARGET_COUNT: dict[str, int] = {
    "eVMel": 86,
    "vKvWz": 102,
    "bRP8R": 26,
}


# ── Title normalization (defends against QA Touch's silent escaping/whitespace) ─
def normalize_title(t: str | None) -> str:
    """Make titles comparable across the create round-trip.

    QA Touch silently HTML-escapes and trims whitespace on titles when they
    round-trip through the create endpoint, so the listed case_title is not
    byte-identical to the source title we passed in. This is what broke
    find_target_case_by_title() in the original phase-A run.
    """
    if not t:
        return ""
    return html.unescape(t).strip()


# ── In-memory target index ──────────────────────────────────────────────────
def build_target_index(target_cases: list[dict]) -> dict[str, dict[str, list[dict]]]:
    """Build {target_module_key: {normalized_title: [case, ...]}}.

    Stores a LIST per title so we can detect (and skip) duplicate titles
    within a module - recon says duplicates_within_module=false, but we
    defend in case the live state differs.
    """
    out: dict[str, dict[str, list[dict]]] = {}
    for c in target_cases:
        mk = c.get("module_key") or c.get("section_key") or ""
        if mk not in TARGET_MODULE_FOR_SOURCE.values():
            continue
        title_norm = normalize_title(c.get("case_title") or c.get("caseTitle") or "")
        if not title_norm:
            continue
        out.setdefault(mk, {}).setdefault(title_norm, []).append(c)
    return out


def report_target_index(idx: dict[str, dict[str, list[dict]]]) -> None:
    """Print per-module counts and call out any duplicate titles."""
    print("  Target index by module (just-created cases in 70l1):")
    for tmk in TARGET_MODULE_FOR_SOURCE.values():
        per_title = idx.get(tmk, {})
        total = sum(len(v) for v in per_title.values())
        unique = len(per_title)
        expected = EXPECTED_TARGET_COUNT[tmk]
        dupes = [t for t, v in per_title.items() if len(v) > 1]
        marker = "" if total == expected else f"  (EXPECTED {expected})"
        print(f"    {tmk}  {TARGET_MODULE_NAMES[tmk]:34s}  "
              f"unique_titles={unique:3d}  total_cases={total:3d}{marker}")
        if dupes:
            print(f"      WARN: {len(dupes)} duplicate titles in {tmk} - will be skipped:")
            for d in dupes[:5]:
                print(f"        - {d[:80]}")
            if len(dupes) > 5:
                print(f"        ... and {len(dupes) - 5} more")


# ── Per-case work ───────────────────────────────────────────────────────────
def process_one(page, source_case: dict, target_case: dict,
                target_section_key: str, dry_run: bool,
                rate_seconds: float) -> dict:
    """Read source + target edit forms, build payload, POST update. Return log entry."""
    source_key = source_case.get("case_key") or source_case.get("caseKey")
    source_code = source_case.get("case_code") or source_case.get("caseCode") or ""
    source_title = source_case.get("case_title") or source_case.get("caseTitle") or ""
    source_module_key = source_case.get("module_key") or source_case.get("section_key") or ""

    target_key = target_case.get("case_key") or target_case.get("caseKey")
    target_code = target_case.get("case_code") or target_case.get("caseCode") or ""

    entry: dict[str, Any] = {
        "source_key": source_key,
        "source_module_key": source_module_key,
        "source_module_name": SOURCE_MODULE_NAMES.get(source_module_key, ""),
        "source_case_code": source_code,
        "source_title": source_title,
        "target_key": target_key,
        "target_module_key": target_section_key,
        "target_module_name": TARGET_MODULE_NAMES.get(target_section_key, ""),
        "target_case_code": target_code,
        "status": "pending",
        "http_status": None,
        "errors": [],
    }

    # 1. Read source edit form
    src_edit = internal_get_case(page, SOURCE_PROJECT, source_key)
    if not src_edit or src_edit.get("__error"):
        entry["status"] = "failed"
        entry["errors"].append(f"source edit read failed: {src_edit}")
        return entry

    time.sleep(rate_seconds)

    # 2. Read target edit form
    tgt_edit = internal_get_case(page, TARGET_PROJECT, target_key)
    if not tgt_edit or tgt_edit.get("__error"):
        entry["status"] = "failed"
        entry["errors"].append(f"target edit read failed: {tgt_edit}")
        return entry

    # 3. Build overlay payload
    payload = build_target_update_payload(tgt_edit, src_edit, target_section_key)

    if dry_run:
        entry["status"] = "dry_run_payload_built"
        entry["payload_keys"] = sorted(payload.keys())
        return entry

    time.sleep(rate_seconds)

    # 4. POST update - tolerate 500-on-success quirk
    upd = internal_update_case(page, TARGET_PROJECT, target_key, payload)
    entry["http_status"] = upd.get("status")
    entry["response_body_excerpt"] = (upd.get("body") or "")[:300]

    if update_succeeded(upd):
        entry["status"] = "metadata_copied"
        return entry

    entry["status"] = "failed"
    entry["errors"].append(
        f"metadata update did not confirm success: status={upd.get('status')} "
        f"body={(upd.get('body') or '')[:200]}"
    )
    return entry


# ── Logging ─────────────────────────────────────────────────────────────────
def make_log_path(run_started: datetime) -> Path:
    stamp = run_started.strftime("%Y%m%d-%H%M%S")
    return LOG_DIR / f"pp_migration_phase_a_resume_{stamp}.json"


def write_log(log_path: Path, entries: list[dict]) -> None:
    """Atomic-ish write: rewrite the full list to disk after every record."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = log_path.with_suffix(log_path.suffix + ".tmp")
    tmp.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    tmp.replace(log_path)


# ── Orchestration ───────────────────────────────────────────────────────────
def run(args) -> int:
    auth_state_file = Path(args.auth_state_file) if args.auth_state_file else DEFAULT_AUTH_STATE
    rate_seconds = max(0.0, args.rate_ms / 1000.0)
    dry_run = bool(args.dry_run)
    resume_from = max(0, int(args.resume_from or 0))
    skip_mods = {
        s.strip() for s in (args.skip_source_modules or "").split(",") if s.strip()
    }

    run_started = datetime.now()
    log_path = make_log_path(run_started)

    print("=" * 70)
    print("  PARTNER PORTAL MIGRATION - Phase A RESUME (metadata copy only)")
    print(f"  source project:    {SOURCE_PROJECT}  (NexaiQ-Core)")
    print(f"  target project:    {TARGET_PROJECT}  (Partner Admin)")
    print(f"  auth state:        {auth_state_file}")
    print(f"  rate:              {args.rate_ms}ms between internal calls")
    print(f"  dry-run:           {dry_run}")
    print(f"  resume-from:       {resume_from}")
    if skip_mods:
        print(f"  skipping modules:  {sorted(skip_mods)}")
    if args.limit:
        print(f"  limit:             first {args.limit} matched source cases")
    print(f"  log path:          {log_path}")
    print("=" * 70)

    token, domain = load_rest_creds()

    # Step 1 - enumerate source project (JlW1), group by source module_key.
    print("\n[1/4] Fetching ALL source cases from JlW1 (single enumeration)...")
    source_cases = fetch_all_project_cases(SOURCE_PROJECT, token, domain)
    print(f"  Source enumeration: {len(source_cases)} total cases in JlW1")

    source_by_mod: dict[str, list[dict]] = {k: [] for k in SOURCE_MODULE_KEYS}
    for c in source_cases:
        mk = c.get("module_key") or c.get("section_key") or ""
        if mk in source_by_mod:
            source_by_mod[mk].append(c)
    for mk in SOURCE_MODULE_KEYS:
        print(f"    {mk}  {SOURCE_MODULE_NAMES[mk]:24s}  "
              f"found {len(source_by_mod[mk]):3d} cases")

    # Step 2 - enumerate target project (70l1), index by (module_key, title).
    print("\n[2/4] Fetching ALL target cases from 70l1 (single enumeration)...")
    target_cases = fetch_all_project_cases(TARGET_PROJECT, token, domain)
    print(f"  Target enumeration: {len(target_cases)} total cases in 70l1")
    target_index = build_target_index(target_cases)
    report_target_index(target_index)

    # Step 3 - match each source case to its target by (target_module, normalized_title).
    print("\n[3/4] Matching source cases to target cases (in-memory join)...")
    work: list[tuple[dict, dict, str]] = []  # (source_case, target_case, target_section_key)
    unmatched_entries: list[dict] = []

    for src_mod_key in SOURCE_MODULE_KEYS:
        if src_mod_key in skip_mods:
            print(f"    skipping source module {src_mod_key} per --skip-source-modules")
            continue
        tgt_mod_key = TARGET_MODULE_FOR_SOURCE[src_mod_key]
        per_title = target_index.get(tgt_mod_key, {})
        matched = 0
        for src in source_by_mod[src_mod_key]:
            src_title = normalize_title(
                src.get("case_title") or src.get("caseTitle") or ""
            )
            if not src_title:
                unmatched_entries.append({
                    "source_key": src.get("case_key"),
                    "source_module_key": src_mod_key,
                    "source_module_name": SOURCE_MODULE_NAMES[src_mod_key],
                    "source_case_code": src.get("case_code", ""),
                    "source_title": src.get("case_title", ""),
                    "target_module_key": tgt_mod_key,
                    "target_module_name": TARGET_MODULE_NAMES[tgt_mod_key],
                    "status": "unmatched_empty_title",
                    "errors": ["source case has empty title"],
                })
                continue
            candidates = per_title.get(src_title, [])
            if len(candidates) == 0:
                unmatched_entries.append({
                    "source_key": src.get("case_key"),
                    "source_module_key": src_mod_key,
                    "source_module_name": SOURCE_MODULE_NAMES[src_mod_key],
                    "source_case_code": src.get("case_code", ""),
                    "source_title": src.get("case_title", ""),
                    "target_module_key": tgt_mod_key,
                    "target_module_name": TARGET_MODULE_NAMES[tgt_mod_key],
                    "status": "unmatched_no_target_for_title",
                    "errors": ["no target case with matching title in target module"],
                })
                continue
            if len(candidates) > 1:
                # Recon says no duplicates; defend defensively.
                unmatched_entries.append({
                    "source_key": src.get("case_key"),
                    "source_module_key": src_mod_key,
                    "source_module_name": SOURCE_MODULE_NAMES[src_mod_key],
                    "source_case_code": src.get("case_code", ""),
                    "source_title": src.get("case_title", ""),
                    "target_module_key": tgt_mod_key,
                    "target_module_name": TARGET_MODULE_NAMES[tgt_mod_key],
                    "status": "unmatched_ambiguous",
                    "errors": [
                        f"{len(candidates)} target cases share this title in module - refusing to guess",
                        f"target_keys: {[c.get('case_key') for c in candidates]}",
                    ],
                })
                continue
            work.append((src, candidates[0], tgt_mod_key))
            matched += 1
        print(f"    {src_mod_key} -> {tgt_mod_key}: matched {matched} / "
              f"{len(source_by_mod[src_mod_key])} source cases")

    if resume_from > 0:
        skipped = work[:resume_from]
        work = work[resume_from:]
        print(f"  --resume-from {resume_from}: skipping {len(skipped)} matched cases")
    if args.limit:
        work = work[: args.limit]

    print(f"\n  Cases to update this run: {len(work)}")
    print(f"  Unmatched cases (logged, no update attempted): {len(unmatched_entries)}")

    # Step 4 - launch browser + run the metadata copy
    print("\n[4/4] Launching browser for internal /v1/case/edit + /v1/case/update...")
    log_entries: list[dict] = list(unmatched_entries)  # log unmatched up front
    if log_entries:
        write_log(log_path, log_entries)

    counts = {
        "metadata_copied": 0,
        "failed": 0,
        "dry_run_payload_built": 0,
    }
    rollup_every = 25

    with sync_playwright() as p:
        browser, ctx, page = open_browser(p, auth_state_file)
        try:
            total = len(work)
            for idx, (src, tgt, tgt_mod_key) in enumerate(work, 1):
                src_title = src.get("case_title") or src.get("caseTitle") or ""
                src_mod_key = src.get("module_key") or ""
                src_mod_name = SOURCE_MODULE_NAMES.get(src_mod_key, "?")

                entry = process_one(
                    page=page,
                    source_case=src,
                    target_case=tgt,
                    target_section_key=tgt_mod_key,
                    dry_run=dry_run,
                    rate_seconds=rate_seconds,
                )
                log_entries.append(entry)

                status = entry["status"]
                if status in counts:
                    counts[status] += 1
                else:
                    counts["failed"] += 1

                short_status = {
                    "metadata_copied": "OK",
                    "dry_run_payload_built": "DRY",
                    "failed": "FAIL",
                }.get(status, status.upper())

                print(f"  [{idx}/{total}] {src_mod_name}: "
                      f"{src_title[:55]:55s} -> {short_status}")
                if entry.get("errors"):
                    for err in entry["errors"]:
                        print(f"       err: {err[:200]}")

                # Atomic-ish crash-safe write after every record.
                write_log(log_path, log_entries)
                time.sleep(rate_seconds)

                if idx % rollup_every == 0:
                    print(f"  --- rollup at {idx}/{total}: "
                          f"OK={counts['metadata_copied']}  "
                          f"DRY={counts['dry_run_payload_built']}  "
                          f"FAIL={counts['failed']}  "
                          f"UNMATCHED={len(unmatched_entries)} ---")
        finally:
            browser.close()

    # ── Summary ─────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  PHASE A RESUME - SUMMARY")
    print(f"  Source cases enumerated:   {len(source_cases)}")
    print(f"  Target cases enumerated:   {len(target_cases)}")
    print(f"  Matched (attempted):       {len(work)}")
    print(f"  Unmatched (logged only):   {len(unmatched_entries)}")
    if dry_run:
        print(f"  Dry-run payloads built:    {counts['dry_run_payload_built']}")
    else:
        print(f"  Metadata copied:           {counts['metadata_copied']}")
    print(f"  Failed:                    {counts['failed']}")
    try:
        rel = log_path.relative_to(ROOT)
        print(f"  Log written to:            {rel}")
    except ValueError:
        print(f"  Log written to:            {log_path}")
    print("=" * 70)
    print("\n  No new cases were created. No JlW1 cases were deleted.")

    exit_clean = counts["failed"] == 0 and len(unmatched_entries) == 0
    return 0 if exit_clean else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Phase A RESUME - finish metadata copy for the 214 cases "
                    "already created in 70l1 (no new creates, no deletes).",
    )
    ap.add_argument("--limit", type=int, default=0,
                    help="Process only the first N matched source cases.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Read source+target and build payload, but skip the POST.")
    ap.add_argument("--auth-state-file", default=str(DEFAULT_AUTH_STATE),
                    help=f"Playwright storage state file (default: {DEFAULT_AUTH_STATE}).")
    ap.add_argument("--rate-ms", type=int, default=1300,
                    help="Milliseconds between internal calls (default 1300).")
    ap.add_argument("--resume-from", type=int, default=0,
                    help="Skip the first N matched source cases (1-indexed restart).")
    ap.add_argument("--skip-source-modules", default="",
                    help="Comma-separated source module keys to skip "
                         "(e.g. '0yxeN,EGdBv').")
    args = ap.parse_args()
    return run(args)


if __name__ == "__main__":
    sys.exit(main())
