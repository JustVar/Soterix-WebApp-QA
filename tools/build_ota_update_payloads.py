#!/usr/bin/env python3
"""Build per-case update payloads for the 85 OTA cases in QA Touch project 60W5.

Output: tools/.ota_update_payloads.json - one entry per case, ready for
the QA Touch update_test_case endpoint (direct REST POST).

For each existing OTA case (identified by case_title starting with 'OTA -'):
  - Look up the matching row in tests/data/c2c_ota_test_cases.csv by title.
  - Build the update payload with:
      reference        (the C2C_OTA_xxx ID lost during CSV import)
      newtags          (array form; smoke + regression where applicable)
      type             (Functional/Negative/Security/Performance)
      priority         (Critical/High/Medium)
      mode             (Manual/Automation)
      description      (lost during CSV import)
      precondition     (re-asserted)
      test_data        (empty for OTA)
      steps_template   (per-step array; replaces the merged single-row step)

Step splitting strategy:
  - The source Steps cell is numbered ("1. Login...\n2. Navigate...\n...")
  - The source Expected_result is a single summary sentence covering the case.
  - We attach the summary as the FINAL step's expectedResult.
  - Intermediate steps get a deterministic, non-empty expectedResult derived
    from the step text (action-result heuristic). The update schema rejects empty
    expectedResults, so this is mandatory.

Reads QA Touch token + domain from the environment / .env
(QATOUCH_API_TOKEN + QATOUCH_DOMAIN).

Usage:
    python tools/build_ota_update_payloads.py
    python tools/build_ota_update_payloads.py --dry-run    # print summary only
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CSV_PATH = REPO / "tests" / "data" / "c2c_ota_test_cases.csv"
OUT_PATH = REPO / "tools" / ".ota_update_payloads.json"
PROJECT_KEY = "60W5"


def load_qatouch_creds() -> tuple[str, str]:
    """Read the QA Touch REST api-token + short domain from the environment / .env."""
    token = os.environ.get("QATOUCH_API_TOKEN") or os.environ.get("QATOUCH_API_KEY")
    domain = os.environ.get("QATOUCH_DOMAIN")
    if not token or not domain:
        raise SystemExit(
            "Missing QA Touch REST credentials.\n"
            "Set QATOUCH_API_TOKEN + QATOUCH_DOMAIN in your .env at the repo "
            "root (see .env.template)."
        )
    return token, domain


def rest_get(path: str, token: str, domain: str) -> dict:
    req = urllib.request.Request(
        f"https://api.qatouch.com/api/v1/{path}",
        headers={
            "api-token": token,
            "domain": domain,
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_all_ota_cases(token: str, domain: str) -> list[dict]:
    """Page through getAllTestCases and return only OTA cases (title starts 'OTA -')."""
    cases = []
    page = 1
    while page <= 12:
        try:
            r = rest_get(f"getAllTestCases/{PROJECT_KEY}?page={page}", token, domain)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} on page {page} - stopping", file=sys.stderr)
            break
        data = r.get("data", []) or []
        if not data:
            break
        cases.extend(data)
        if not r.get("link", {}).get("next"):
            break
        page += 1
    return [c for c in cases if (c.get("case_title") or "").startswith("OTA -")]


def split_steps(merged: str) -> list[str]:
    """Split a numbered-multi-line step block into a list of step strings."""
    if not merged:
        return []
    lines = [ln.strip() for ln in merged.splitlines() if ln.strip()]
    out: list[str] = []
    for ln in lines:
        m = re.match(r"^\d+\.\s*(.+)$", ln)
        out.append(m.group(1).strip() if m else ln)
    return out


def derive_intermediate_expected(step_text: str) -> str:
    """Produce a non-empty, generic-but-coherent expected for an intermediate step.

    The update schema forbids empty expectedResults. We synthesize a short result
    that mirrors the step's verb so each row reads sensibly in the UI.
    """
    s = step_text.lower()
    if s.startswith(("login", "log in", "authenticate")):
        return "Login succeeds; user lands on the appropriate landing page."
    if s.startswith(("navigate", "go to", "open", "browse")):
        return "Navigation completes; the target section is displayed."
    if s.startswith(("locate", "find", "look for", "identify")):
        return "Target item is found and visible on screen."
    if s.startswith(("select", "click", "press", "tap", "choose")):
        return "Selection is registered; UI updates to reflect the action."
    if s.startswith(("observe", "monitor", "watch", "wait")):
        return "Observation step; expected behavior occurs."
    if s.startswith(("verify", "confirm", "validate", "check", "review")):
        return "Validation passes for the criterion under check."
    if s.startswith(("enter", "type", "input", "provide")):
        return "Input is accepted without error."
    if s.startswith(("attempt", "try", "push", "trigger")):
        return "Action is initiated; system processes the request."
    return "Step completes successfully; ready to proceed."


def build_steps_template(steps_cell: str, summary_expected: str) -> list[dict]:
    """Return list of {step, expectedResult} dicts. Summary expected lives on the last step."""
    steps = split_steps(steps_cell)
    if not steps:
        return []
    out = []
    for i, s in enumerate(steps):
        is_last = i == len(steps) - 1
        expected = summary_expected.strip() if is_last and summary_expected.strip() else derive_intermediate_expected(s)
        out.append({"step": s, "expectedResult": expected})
    return out


def tags_to_array(pipe_str: str) -> list[str]:
    return [t.strip() for t in (pipe_str or "").split("|") if t.strip()]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not CSV_PATH.exists():
        print(f"ERROR CSV not found: {CSV_PATH}", file=sys.stderr)
        return 1

    csv_rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    by_title = {r["Test Case Title"]: r for r in csv_rows}
    print(f"Loaded {len(csv_rows)} rows from CSV; {len(by_title)} unique titles")

    token, domain = load_qatouch_creds()
    print(f"Fetching OTA cases from QA Touch project {PROJECT_KEY}...")
    qt_cases = fetch_all_ota_cases(token, domain)
    print(f"Found {len(qt_cases)} OTA cases in QA Touch")

    payloads = []
    matched = unmatched = 0
    for c in qt_cases:
        title = c["case_title"]
        row = by_title.get(title)
        if not row:
            unmatched += 1
            print(f"  [no CSV match] {c['case_code']}: {title!r}")
            continue
        matched += 1
        payloads.append({
            "_csv_reference": row["Reference"],
            "_csv_module": row["Module_name"],
            "_case_code": c["case_code"],
            "projectKey": PROJECT_KEY,
            "caseKey": c["case_key"],
            "caseTitle": title,
            "reference": row["Reference"],
            "newtags": tags_to_array(row["Tags"]),
            "type": row["Type"],
            "priority": row["Priority"],
            "mode": row["Mode"],
            "description": row["Description"],
            "precondition": row["Precondition"],
            "test_data": row["Test Data"],
            "steps_template": build_steps_template(row["Steps"], row["Expected_result"]),
        })

    print(f"\nMatched: {matched} | Unmatched: {unmatched}")
    print(f"Distinct tags: {sorted({tuple(p['newtags']) for p in payloads})}")
    print(f"Distinct types: {sorted({p['type'] for p in payloads})}")
    print(f"Distinct priorities: {sorted({p['priority'] for p in payloads})}")
    print(f"Distinct modes: {sorted({p['mode'] for p in payloads})}")
    avg_steps = sum(len(p["steps_template"]) for p in payloads) / max(1, len(payloads))
    print(f"Avg steps per case: {avg_steps:.1f}")

    if args.dry_run:
        sample = payloads[0]
        print("\nSample payload (one case):")
        print(json.dumps(sample, indent=2)[:2000])
        return 0

    OUT_PATH.write_text(json.dumps(payloads, indent=2), encoding="utf-8")
    print(f"\nOK wrote {len(payloads)} payloads -> {OUT_PATH.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
