"""Import new test cases into QA Touch through the public API.

Replaces the browser-driven import for NEW cases. Needs only the API key -
no browser, no session that expires, no reverse-engineered endpoints.

    python tools/qatouch_csv_import.py preview cases.csv --project <key>
    python tools/qatouch_csv_import.py import cases.csv --project <key>

Input is the CSV `tools/qatouch_cases_from_tests.py` writes from the test
docstrings. This tool translates it to the column names the public endpoint
wants.

What the endpoint can and cannot do (measured 2026-08-17):

  - CREATE ONLY. A case_key column is ignored and you get a duplicate. There
    is no public way to update a case, so never point this at cases that
    already exist.
  - It sets TAGS on create. That is the only way to write a tag through the
    public API - changing an existing case's tags needs the QA Touch web UI.
  - 100 cases per request. This tool chunks automatically.
  - Every column is mandatory. The controller indexes the row without
    checking, so a missing column fails the row with "Undefined index".
  - A failed row creates NOTHING and the error names the row and column. That
    makes preview genuinely safe and the failure output worth reading.

There is no delete API anywhere in QA Touch. A case imported by mistake has to
be removed by hand through the DELETE-REQUEST tag process. Preview first.
"""
from __future__ import annotations

import argparse
import csv
import functools
import io
import json
import os
import sys
from pathlib import Path

_print = print
print = functools.partial(_print, flush=True)
if sys.platform == "win32":
    import contextlib
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import requests

from config.products import home_project

API_URL = "https://api.qatouch.com/api/v1/testCase/import"
CHUNK_SIZE = 100

# The columns the public import endpoint requires. All of them, always.
# Discovered by walking the controller's own "Undefined index" errors.
API_COLUMNS = [
    "module_name", "title", "test_case_title", "description", "precondition",
    "test_data", "steps", "expected_result", "tags", "type", "priority",
    "mode", "estimate", "reference", "test_suite",
]

# Our canonical CSV column -> the endpoint's column. The browser import wizard
# and the public API disagree on names; this is the whole difference.
CANONICAL_TO_API = {
    "section_name": "module_name",     # wizard says section_name
    "title": "title",
    "test_description": "description",  # wizard's `description` is dropped
    "precondition": "precondition",
    "test_data": "test_data",
    "steps": "steps",
    "expected_result": "expected_result",
    "newtags": "tags",                 # wizard says newtags
    "test_type": "type",
    "test_priority": "priority",
    "test_mode": "mode",
    "estimate": "estimate",
    "reference": "reference",
    "test_suite": "test_suite",
}


# The friendly headers of the CSV tools/qatouch_cases_from_tests.py writes
# -> the endpoint's column. "Created By" has no home on the endpoint:
# dropped, no warning.
FRIENDLY_TO_API = {
    "Module_name": "module_name",
    "Test Case Title": "title",
    "Test Data": "test_data",
    "Estimate": "estimate",
    "Reference": "reference",
    "Precondition": "precondition",
    "Steps": "steps",
    "Expected_result": "expected_result",
    "Test Suite": "test_suite",
    "Tags": "tags",
    "Description": "description",
    "Type": "type",
    "Priority": "priority",
    "Mode": "mode",
}
DROPPED_QUIETLY = {"Created By"}


def load_rows(path: Path) -> list[dict]:
    """Read a CSV into a list of dicts, keeping blank cells as empty strings."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        return [{(k or "").strip(): (v or "") for k, v in row.items()}
                for row in csv.DictReader(f)]


def to_api_rows(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Translate canonical rows to API rows. Returns (rows, warnings)."""
    warnings: list[str] = []
    if not rows:
        return [], ["The CSV has no data rows."]

    present = set(rows[0])
    if "case_key" in present:
        warnings.append(
            "The CSV has a case_key column. The endpoint IGNORES it and creates "
            "duplicates - it cannot update. Remove those rows unless you really "
            "mean to create new cases.")

    # Accept our canonical names, the friendly authoring headers, or the
    # API names directly.
    mapping = {}
    for col in present:
        if col in CANONICAL_TO_API:
            mapping[col] = CANONICAL_TO_API[col]
        elif col in FRIENDLY_TO_API:
            mapping[col] = FRIENDLY_TO_API[col]
        elif col in API_COLUMNS:
            mapping[col] = col

    unmapped = sorted(present - set(mapping) - DROPPED_QUIETLY)
    if unmapped:
        warnings.append(f"Column(s) ignored, the endpoint has no home for them: {unmapped}")

    out = []
    carried = None
    for row in rows:
        api_row = {c: "" for c in API_COLUMNS}
        for src, dst in mapping.items():
            api_row[dst] = row.get(src, "")

        # Continuation rows carry only steps - our canonical format emits one
        # step per row with the metadata blank. The endpoint has no such
        # concept, so fold them into the previous case's steps.
        if not api_row["title"] and not api_row["module_name"] and api_row["steps"]:
            if carried is None:
                warnings.append("A step-only row appears before any case row; skipped.")
                continue
            carried["steps"] = f'{carried["steps"]}\n{api_row["steps"]}'.strip()
            if api_row["expected_result"]:
                carried["expected_result"] = (
                    f'{carried["expected_result"]}\n{api_row["expected_result"]}'.strip())
            continue

        # The endpoint wants the title in both columns.
        api_row["test_case_title"] = api_row["title"]
        out.append(api_row)
        carried = api_row

    return out, warnings


def build_csv(rows: list[dict]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(API_COLUMNS)
    for r in rows:
        writer.writerow([r.get(c, "") for c in API_COLUMNS])
    return buf.getvalue().encode("utf-8")


def post_chunk(project_key: str, payload: bytes) -> dict:
    resp = requests.post(
        API_URL,
        params={"projectKey": project_key},
        headers={"api-token": os.environ["QATOUCH_API_KEY"],
                 "domain": os.environ["QATOUCH_DOMAIN"]},
        files={"file": ("cases.csv", payload, "text/csv")},
        timeout=180,
    )
    if resp.status_code != 200:
        raise SystemExit(f"  HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def preview(path: Path) -> dict:
    """What `preview` prints, as data: rows read, cases, requests,
    warnings, the first API row, tagged cases, and cases with an empty
    title. Sends nothing. Other tools call this to check a CSV before
    they hand it on."""
    rows = load_rows(path)
    api_rows, warnings = to_api_rows(rows)
    return {
        "rows": len(rows),
        "cases": len(api_rows),
        "requests": (len(api_rows) + CHUNK_SIZE - 1) // CHUNK_SIZE,
        "warnings": warnings,
        "first": api_rows[0] if api_rows else None,
        "tagged": sum(1 for r in api_rows if r["tags"].strip()),
        "empty_titles": sum(1 for r in api_rows if not r["title"].strip()),
    }


def cmd_preview(args):
    result = preview(Path(args.csv))
    print(f"\n  CSV rows read:      {result['rows']}")
    print(f"  Cases to create:    {result['cases']}")
    print(f"  Requests (100 max): {result['requests']}")
    for w in result["warnings"]:
        print(f"\n  WARNING: {w}")
    if result["empty_titles"]:
        print(f"\n  WARNING: {result['empty_titles']} case(s) have an empty title. "
              "The title column was not recognised: check the header row.")
    if not result["first"]:
        return
    print("\n  First case as it will be sent:")
    for col in API_COLUMNS:
        value = str(result["first"].get(col, ""))
        shown = value.replace("\n", " / ")[:70]
        print(f"    {col:18s} {shown}")
    print(f"\n  Cases carrying tags: {result['tagged']}")
    print("\n  Preview only. Nothing sent.")
    print("  Remember: this endpoint CREATES. There is no delete API.")


def cmd_import(args):
    rows = load_rows(Path(args.csv))
    api_rows, warnings = to_api_rows(rows)
    for w in warnings:
        print(f"  WARNING: {w}")
    if not api_rows:
        print("  Nothing to import.")
        return

    print(f"\n  Creating {len(api_rows)} case(s) in {args.project}...")
    total_imported = 0
    total_failed = 0
    all_errors = []

    for start in range(0, len(api_rows), CHUNK_SIZE):
        chunk = api_rows[start:start + CHUNK_SIZE]
        n = start // CHUNK_SIZE + 1
        body = post_chunk(args.project, build_csv(chunk))
        imported = body.get("imported", 0)
        failed = body.get("failed", 0)
        total_imported += imported
        total_failed += failed
        errors = body.get("errors") or []
        all_errors.extend(errors)
        print(f"    chunk {n}: {imported} imported, {failed} failed")
        for e in errors[:5]:
            print(f"      row {e.get('row')}: {e.get('message', '')[:90]}")

    print(f"\n  Done. Imported {total_imported}, failed {total_failed}.")
    if all_errors:
        report = ROOT / "config" / "audit_reports" / "csv_import_errors.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(all_errors, indent=2), encoding="utf-8")
        print(f"  Full error list: {report.relative_to(ROOT)}")
        print("  Failed rows created nothing. Fix the CSV and re-run those rows only.")


def main():
    parser = argparse.ArgumentParser(
        description="Import NEW test cases into QA Touch via the public API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Input is")[0],
    )
    sub = parser.add_subparsers(dest="command")
    for name, help_text in [("preview", "Show what would be sent, send nothing"),
                            ("import", "Create the cases in QA Touch")]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("csv", help="Path to the canonical CSV")
        # The default: the project .env names in QATOUCH_PROJECT_ID, else the
        # one the UI root reports to (config/products.py).
        p.add_argument("--project",
                       default=os.environ.get("QATOUCH_PROJECT_ID") or home_project("tests/ui/"),
                       help="QA Touch project key (default: QATOUCH_PROJECT_ID, else the "
                            "UI root's project in config/products.py)")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    print(f"\n{'=' * 60}")
    print("  QA TOUCH CSV IMPORT (public API, create-only)")
    print(f"{'=' * 60}")
    {"preview": cmd_preview, "import": cmd_import}[args.command](args)


if __name__ == "__main__":
    main()
