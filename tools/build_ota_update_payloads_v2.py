#!/usr/bin/env python3
"""V2: Build per-case update payloads for the 85 OTA cases using QA Touch's
INTERNAL /v1/case/update endpoint (the one the UI actually uses).

Discovered via UI scrape (2026-06-24):

  POST /v1/case/update/p/{projectKey}/cid/{caseKey}
  Headers: X-XSRF-TOKEN (cookie value), Cookie: laravel_session (HttpOnly)
  Body: full edit-form JSON (type/priority/tags = encrypted enc_id strings)
  Response: {"status":true,"msg":"Case Updated Successfully", ...}

This script writes tools/.ota_update_payloads_v2.json - to be consumed by
a small browser-side runner that has the live authenticated session.

Type/Priority/Tag enc_ids (from /v1/add/case/meta/p/60W5):

  Type:      Functional=GNxna, Regression=rg3rN, Performance=l7PmX,
             Acceptance=zgryX, Other=EERzG, Automation=nl7g6
  Priority:  Critical=bkRmQ, High=Z1BPp, Medium=Rq6v1, Low=dBxg0
  Newtags:   smoke=99GQ, sanity=X1zZ, regression=MW0N, future=ea5n

OTA CSV uses Type=Negative/Security which aren't in QA Touch's enum, so:
  Negative -> Functional (negative tests ARE functional)
  Security -> Other (closest fit)
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
OUT_PATH = REPO / "tools" / ".ota_update_payloads_v2.json"
PROJECT_KEY = "60W5"

TYPE_ENC = {
    "Functional": "GNxna",
    "Negative": "GNxna",      # not in QA Touch enum -> Functional
    "Security": "EERzG",      # not in QA Touch enum -> Other
    "Performance": "l7PmX",
    "Regression": "rg3rN",
    "Acceptance": "zgryX",
    "Automation": "nl7g6",
}
PRIORITY_ENC = {
    "Critical": "bkRmQ",
    "High": "Z1BPp",
    "Medium": "Rq6v1",
    "Low": "dBxg0",
}
TAG_ENC = {
    "smoke": "99GQ",
    "sanity": "X1zZ",
    "regression": "MW0N",
    "future": "ea5n",
}


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
        headers={"api-token": token, "domain": domain, "Accept": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_ota_cases(token: str, domain: str) -> list[dict]:
    cases = []
    page = 1
    while page <= 12:
        try:
            r = rest_get(f"getAllTestCases/{PROJECT_KEY}?page={page}", token, domain)
        except urllib.error.HTTPError as e:
            print(f"  HTTP {e.code} on page {page}", file=sys.stderr)
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
    if not merged:
        return []
    out = []
    for ln in merged.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        m = re.match(r"^\d+[\.\)]\s*(.+)$", ln)
        out.append(m.group(1).strip() if m else ln)
    return out


def derive_intermediate_expected(s: str) -> str:
    low = s.lower()
    if low.startswith(("login", "log in", "authenticate")):
        return "Login succeeds; user lands on the appropriate landing page."
    if low.startswith(("navigate", "go to", "open", "browse")):
        return "Navigation completes; the target section is displayed."
    if low.startswith(("locate", "find", "look for", "identify")):
        return "Target item is found and visible on screen."
    if low.startswith(("select", "click", "press", "tap", "choose")):
        return "Selection is registered; UI updates to reflect the action."
    if low.startswith(("observe", "monitor", "watch", "wait")):
        return "Observation step; expected behavior occurs."
    if low.startswith(("verify", "confirm", "validate", "check", "review")):
        return "Validation passes for the criterion under check."
    if low.startswith(("enter", "type", "input", "provide")):
        return "Input is accepted without error."
    if low.startswith(("attempt", "try", "push", "trigger")):
        return "Action is initiated; system processes the request."
    return "Step completes successfully; ready to proceed."


def build_steps_array(steps_cell: str, summary_expected: str) -> list[dict]:
    """Return list of step records. QA Touch wraps step/description in <p>...</p>."""
    steps = split_steps(steps_cell)
    out = []
    for i, s in enumerate(steps):
        is_last = i == len(steps) - 1
        exp = summary_expected.strip() if is_last and summary_expected.strip() else derive_intermediate_expected(s)
        out.append({
            "step": f"<p>{s}</p>",
            "description": f"<p>{exp}</p>",  # field name is misleading; this is the EXPECTED RESULT
            "position": i + 1,
            "from_reusable_step": 0,
        })
    return out


def tags_to_enc_ids(pipe_str: str) -> list[str]:
    out = []
    for raw in (pipe_str or "").split("|"):
        t = raw.strip().lower()
        enc = TAG_ENC.get(t)
        if enc:
            out.append(enc)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    csv_rows = list(csv.DictReader(CSV_PATH.open(encoding="utf-8")))
    by_title = {r["Test Case Title"]: r for r in csv_rows}
    print(f"CSV rows: {len(csv_rows)}")

    token, domain = load_qatouch_creds()
    print(f"Fetching OTA cases from project {PROJECT_KEY}...")
    qt_cases = fetch_ota_cases(token, domain)
    print(f"OTA cases in QA Touch: {len(qt_cases)}")

    payloads = []
    skipped = 0
    for c in qt_cases:
        title = c["case_title"]
        row = by_title.get(title)
        if not row:
            skipped += 1
            continue
        type_enc = TYPE_ENC.get(row["Type"], "GNxna")
        pri_enc = PRIORITY_ENC.get(row["Priority"], "Rq6v1")
        tags = tags_to_enc_ids(row["Tags"])
        mode = (row["Mode"] or "manual").lower()
        # QA Touch uses lowercase "manual"/"automation"
        if mode == "manual":
            mode_val = "manual"
        elif mode == "automation":
            mode_val = "automation"
        else:
            mode_val = ""
        payloads.append({
            "_ref": row["Reference"],
            "_module": row["Module_name"],
            "caseKey": c["case_key"],
            "reference": row["Reference"],
            "type": type_enc,
            "priority": pri_enc,
            "mode": mode_val,
            "newtags": tags,
            "description": row["Description"],
            "precondition": row["Precondition"],
            "test_data": row["Test Data"],
            "steps": build_steps_array(row["Steps"], row["Expected_result"]),
        })

    print(f"Built {len(payloads)} payloads, {skipped} skipped (no CSV match)")
    print(f"Tag combos: {sorted({tuple(p['newtags']) for p in payloads})}")
    print(f"Type enc_ids: {sorted({p['type'] for p in payloads})}")
    print(f"Priority enc_ids: {sorted({p['priority'] for p in payloads})}")
    print(f"Mode values: {sorted({p['mode'] for p in payloads})}")
    avg_steps = sum(len(p["steps"]) for p in payloads) / max(1, len(payloads))
    print(f"Avg steps per case: {avg_steps:.1f}")

    if args.dry_run:
        print("\nSample (C2C_OTA_036):")
        s = next((p for p in payloads if p["_ref"] == "C2C_OTA_036"), payloads[0])
        print(json.dumps(s, indent=2)[:1200])
        return 0

    OUT_PATH.write_text(json.dumps(payloads, indent=2), encoding="utf-8")
    print(f"\nOK wrote {len(payloads)} payloads -> {OUT_PATH.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
