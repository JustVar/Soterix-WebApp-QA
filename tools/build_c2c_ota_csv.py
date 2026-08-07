#!/usr/bin/env python3
"""Build canonical QA Touch import CSV from the refined C2C OTA workbook.

Source: C2C_OTA_Test_Cases_Refined.xlsx - 85 fully-authored OTA test cases in
a narrow 6-column format (TC ID, Module, Scenario, Precondition, Test Steps,
Expected Result).

Output: tests/data/c2c_ota_test_cases.csv in the same 15-column format as
tests/data/c2c_hardware_test_cases.csv, ready for QA Touch import into project
60W5 (C2C / Cloud 2 Cam).

Field expansion:
  TC ID            -> Reference (preserves C2C_OTA_001..085)
  Module           -> Module_name as "C2C OTA > <Module>", Test Suite "C2C OTA"
  Scenario         -> Test Case Title
  Precondition     -> Precondition (verbatim; source is generic)
  Test Steps       -> Steps (verbatim - already real, per-case)
  Expected Result  -> Expected_result (verbatim)
  Type             <- derived from Module (Functional/Negative/Security/Performance)
  Priority/Severity<- per-module heuristic; bumped to Critical for tamper/auth-bypass
  Tags             <- regression by default; smoke for must-pass happy paths
  Mode             <- Automation for Backend Validation + Security where pure software;
                       Manual for hands-on OTA flows
  Description      <- "<Type> ({Module}): <Scenario>"
  Test Data, Estimate, Created By  <- empty (not in source)

Usage:
    python tools/build_c2c_ota_csv.py            # write CSV
    python tools/build_c2c_ota_csv.py --dry-run
    python tools/build_c2c_ota_csv.py --src PATH --out PATH
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SRC = Path(r"C:\Users\JustinVarughese\Downloads\C2C_OTA_Test_Cases_Refined.xlsx")
DEFAULT_OUT = REPO / "tests" / "data" / "c2c_ota_test_cases.csv"

OUT_COLUMNS = [
    "Module_name", "Test Case Title", "Test Data", "Estimate", "Reference",
    "Precondition", "Steps", "Expected_result", "Test Suite", "Tags",
    "Description", "Type", "Priority", "Mode", "Created By",
]

TEST_SUITE = "C2C OTA"

# Per-module defaults: type, priority, severity (informational; canonical CSV
# carries only Priority), mode, base tags.
MODULE_CFG = {
    "Notification":          dict(type="Functional",  priority="Medium",  mode="Manual",     tags="regression"),
    "Partner OTA Update":    dict(type="Functional",  priority="High",    mode="Manual",     tags="regression"),
    "Customer Admin":        dict(type="Functional",  priority="Medium",  mode="Manual",     tags="regression"),
    "Backend Validation":    dict(type="Functional",  priority="High",    mode="Automation", tags="regression"),
    "Functional Validation": dict(type="Functional",  priority="Medium",  mode="Manual",     tags="regression"),
    "Negative Testing":      dict(type="Negative",    priority="Medium",  mode="Manual",     tags="regression"),
    "Performance":           dict(type="Performance", priority="Medium",  mode="Manual",     tags="regression"),
    "Security":              dict(type="Security",    priority="High",    mode="Automation", tags="regression"),
}

# Scenario keyword triggers
SMOKE_KEYWORDS = [
    "notification displayed",
    "update icon shown",
    "can initiate ota",
    "access to update",
    "package integrity",
]
CRITICAL_KEYWORDS = [
    "tampered", "tamper", "integrity", "unauthorized", "auth bypass",
    "injection", "xss", "replay", "privilege escalation", "rollback failure",
]


def _ascii(s: str) -> str:
    if not s:
        return s
    repl = {
        "-": " - ", "-": " - ",
        "'": "'", "'": "'",
        """: '"', """: '"',
        "...": "...", "�": "-",
        " ": " ",  # nbsp
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    return s


def read_source(path: Path) -> list[dict]:
    try:
        from openpyxl import load_workbook
    except ImportError:
        print("ERROR openpyxl is required: pip install openpyxl", file=sys.stderr)
        raise SystemExit(2)
    wb = load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    header = [c.value for c in ws[1]]
    expected = ["TC ID", "Module", "Scenario", "Precondition", "Test Steps", "Expected Result"]
    if header[:6] != expected:
        print(f"ERROR unexpected header: {header}", file=sys.stderr)
        raise SystemExit(2)
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or not any(c for c in r):
            continue
        rows.append({
            "tc_id":     (r[0] or "").strip() if isinstance(r[0], str) else (str(r[0]) if r[0] else ""),
            "module":    (r[1] or "").strip(),
            "scenario":  (r[2] or "").strip(),
            "precond":   (r[3] or "").strip(),
            "steps":     (r[4] or "").strip(),
            "expected":  (r[5] or "").strip(),
        })
    return rows


def build_rows(src: list[dict]) -> list[dict]:
    out = []
    for s in src:
        mod = s["module"]
        cfg = MODULE_CFG.get(mod, dict(type="Functional", priority="Medium", mode="Manual", tags="regression"))
        scenario = s["scenario"]
        low = scenario.lower()

        tags = cfg["tags"]
        if any(k in low for k in SMOKE_KEYWORDS) and "smoke" not in tags:
            tags = "smoke|" + tags

        priority = cfg["priority"]
        if any(k in low for k in CRITICAL_KEYWORDS):
            priority = "Critical"

        title = f"OTA - {scenario}"
        desc = f"{cfg['type']} ({mod}): {scenario}"

        out.append({
            "Module_name": f"C2C OTA > {mod}",
            "Test Case Title": _ascii(title),
            "Test Data": "",
            "Estimate": "",
            "Reference": s["tc_id"],
            "Precondition": _ascii(s["precond"]) or "Required environment and valid user access configured",
            "Steps": _ascii(s["steps"]),
            "Expected_result": _ascii(s["expected"]),
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

    src = read_source(args.src)
    rows = build_rows(src)

    print(f"Built {len(rows)} cases from {len(src)} source rows")
    print("Modules:")
    for k, v in sorted(Counter(r["Module_name"] for r in rows).items()):
        print(f"  {k}: {v}")
    print(f"Tags: {dict(Counter(r['Tags'] for r in rows))}")
    print(f"Modes: {dict(Counter(r['Mode'] for r in rows))}")
    print(f"Types: {dict(Counter(r['Type'] for r in rows))}")
    print(f"Priorities: {dict(Counter(r['Priority'] for r in rows))}")

    if args.dry_run:
        print("\n--dry-run: not writing. Sample case:")
        s = rows[0]
        for k in OUT_COLUMNS:
            v = str(s[k])
            print(f"  [{k}]: {v[:200]}")
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
