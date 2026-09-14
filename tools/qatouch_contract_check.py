#!/usr/bin/env python3
"""Check that the QA Touch API still looks the way our code expects.

QA Touch changes its API without announcing it. In March 2026 it renamed the
test-case response fields. Nothing broke loudly - our tools kept running and
quietly reported "Unknown" for five months. The vendor's own OpenAPI spec
documents no response fields at all, so no document could have warned us.

This is the canary. It compares the live API against a recorded baseline and
exits non-zero the moment anything drifts. Run it on a schedule.

Checks:
    fields      Case records still carry the field names our code reads
    aliases     Our client still adds the legacy field names
    statuses    Result status codes still mean what we think
    tags        Tag IDs in config still match the tags in use
    endpoints   The endpoints we depend on still answer

Usage:
    python tools/qatouch_contract_check.py                # check, exit 1 on drift
    python tools/qatouch_contract_check.py --verbose      # show every check
    python tools/qatouch_contract_check.py --update       # re-record the baseline

Exit codes:
    0  everything matches the baseline
    1  drift found - read the output, then fix the code or --update the baseline
    2  could not run the check (network, auth, config)

When a check fails, decide which is wrong. If QA Touch changed something we
must follow, fix our code first, then --update. Never --update to silence a
failure you have not understood.
"""
from __future__ import annotations

import argparse
import contextlib
import functools
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

_print = print
print = functools.partial(_print, flush=True)
if sys.platform == "win32":
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

BASELINE_PATH = ROOT / "config" / "qatouch_contract_baseline.json"
TAG_IDS_PATH = ROOT / "config" / "qatouch_tag_ids.json"
PROJECT_KEY = os.environ.get("QATOUCH_PROJECT_ID", "JlW1")

# Fields our code reads off a test case. Losing any of these breaks something.
REQUIRED_CASE_FIELDS = [
    "case_key", "case_code", "case_title", "module_name", "module_key",
    "Priority", "Type", "Tags", "Steps",
]

# Field names our client back-fills for older tools and snapshots.
REQUIRED_ALIAS_FIELDS = ["module name", "NewTags", "created date", "updated date"]

# As spelled by getAvailableStatuses. Result reads spell 6 and 7 with a space
# instead of a hyphen ("Not Applicable"), so compare through
# normalize_status_name rather than ==. Measured 2026-08-17.
EXPECTED_STATUSES = {
    1: "Passed", 2: "Untested", 3: "Blocked", 4: "Retest",
    5: "Failed", 6: "Not-Applicable", 7: "In-Progress", 8: "Hold",
}


class Result:
    """One check outcome."""

    def __init__(self, name: str):
        self.name = name
        self.problems: list[str] = []
        self.notes: list[str] = []

    def fail(self, msg: str):
        self.problems.append(msg)

    def note(self, msg: str):
        self.notes.append(msg)

    @property
    def ok(self) -> bool:
        return not self.problems


def load_baseline() -> dict:
    if not BASELINE_PATH.exists():
        return {}
    with open(BASELINE_PATH, encoding="utf-8") as f:
        return json.load(f)


def save_baseline(data: dict):
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BASELINE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def fetch_sample(client, size: int = 3) -> list[dict]:
    """Fetch a small page of cases. One page is enough to see the shape."""
    page = client.list_test_cases(PROJECT_KEY, page=1)
    return (page.get("data") or [])[:size]


# -- Checks ------------------------------------------------------------

def check_fields(sample: list[dict], baseline: dict) -> tuple[Result, list]:
    r = Result("fields")
    if not sample:
        r.fail("The API returned no test cases, so the shape cannot be checked.")
        return r, []

    seen = sorted({k for c in sample for k in c})
    for field in REQUIRED_CASE_FIELDS:
        if not any(field in c for c in sample):
            r.fail(f"Field '{field}' is gone from the case response. "
                   f"Anything reading it now silently gets nothing.")

    for c in sample:
        if "Tags" in c and not isinstance(c["Tags"], list):
            r.fail(f"'Tags' is {type(c['Tags']).__name__}, expected a list. "
                   f"It was a comma-joined string before March 2026.")
            break

    known = baseline.get("case_fields")
    if known:
        added = [f for f in seen if f not in known]
        removed = [f for f in known if f not in seen]
        if added:
            r.note(f"New field(s) since the baseline: {added}")
        if removed:
            r.fail(f"Field(s) present in the baseline but missing now: {removed}")
    return r, seen


def check_aliases(client) -> Result:
    r = Result("aliases")
    from tools.qatouch_client import add_legacy_case_aliases

    sample = fetch_sample(client, size=1)
    if not sample:
        r.fail("No case returned, cannot check the legacy aliases.")
        return r
    case = add_legacy_case_aliases(dict(sample[0]))
    for field in REQUIRED_ALIAS_FIELDS:
        if field not in case:
            r.fail(f"add_legacy_case_aliases no longer produces '{field}'. "
                   f"Tools and snapshots that read the old names will break.")
    return r


def check_statuses(client) -> tuple[Result, dict]:
    r = Result("statuses")
    import requests

    from tools.qatouch_client import normalize_status_name

    url = "https://api.qatouch.com/api/v1/testRuns/getAvailableStatuses"
    resp = requests.get(url, headers=client.session.headers, timeout=30)
    if resp.status_code != 200:
        r.fail(f"getAvailableStatuses returned HTTP {resp.status_code}.")
        return r, {}
    live = {int(x["status_key"]): x["status"] for x in resp.json().get("data", [])}
    for code, name in EXPECTED_STATUSES.items():
        if code not in live:
            r.fail(f"Status code {code} ({name}) no longer exists.")
        elif normalize_status_name(live[code]) != normalize_status_name(name):
            r.fail(f"Status code {code} is now '{live[code]}', was '{name}'. "
                   f"Every hard-coded status in our tools is suspect.")
        elif live[code] != name:
            r.note(f"Status {code} respelled: '{name}' -> '{live[code]}' "
                   f"(same meaning, normaliser absorbs it)")
    for code, name in live.items():
        if code not in EXPECTED_STATUSES:
            r.note(f"New status {code} = '{name}'")
    return r, live


def check_tags(sample_all: list[dict]) -> Result:
    r = Result("tags")
    if not TAG_IDS_PATH.exists():
        r.fail(f"{TAG_IDS_PATH.name} is missing. Tag tooling cannot resolve IDs.")
        return r
    with open(TAG_IDS_PATH, encoding="utf-8") as f:
        configured = {k.lower() for k in json.load(f)}
    live = {str(t).lower() for c in sample_all for t in (c.get("Tags") or [])}
    missing = [t for t in ("smoke", "sanity", "regression") if t not in configured]
    if missing:
        r.fail(f"Suite tag(s) absent from config: {missing}")
    unknown = sorted(live - configured)
    if unknown:
        r.note(f"Tag(s) in use but not in config: {unknown}")
    return r


def check_endpoints(client) -> tuple[Result, dict]:
    r = Result("endpoints")
    import requests

    sample = fetch_sample(client, size=1)
    case_key = sample[0]["case_key"] if sample else "XXXXXX"
    targets = {
        "getAllTestCases": f"/api/v1/getAllTestCases/{PROJECT_KEY}?page=1",
        "getAllTestRuns": f"/api/v1/getAllTestRuns/{PROJECT_KEY}",
        "getAllModules": f"/api/v1/getAllModules/{PROJECT_KEY}?page=1",
        "getTestRunlist": f"/api/v1/getTestRunlist/{case_key}",
        "getAvailableStatuses": "/api/v1/testRuns/getAvailableStatuses",
    }
    codes = {}
    for name, path in targets.items():
        try:
            resp = requests.get("https://api.qatouch.com" + path,
                                headers=client.session.headers, timeout=30)
            codes[name] = resp.status_code
            if resp.status_code != 200:
                r.fail(f"{name} returned HTTP {resp.status_code}, expected 200.")
        except Exception as exc:
            codes[name] = "error"
            r.fail(f"{name} could not be reached: {exc}")
        time.sleep(0.3)
    return r, codes


# -- Main --------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Check the QA Touch API against our recorded baseline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage:")[-1],
    )
    parser.add_argument("--update", action="store_true",
                        help="Re-record the baseline from the live API")
    parser.add_argument("--verbose", action="store_true",
                        help="Show every check, not just the failures")
    args = parser.parse_args()

    print()
    print("=" * 64)
    print("  QA TOUCH API CONTRACT CHECK")
    print("=" * 64)

    try:
        from tools.qatouch_client import QATouchClient
        client = QATouchClient()
    except Exception as exc:
        print(f"  Could not build the API client: {exc}")
        return 2

    baseline = load_baseline()
    if baseline.get("recorded"):
        print(f"  Baseline recorded: {baseline['recorded']}")
    else:
        print("  No baseline yet. Run with --update once you trust the current API.")

    try:
        sample = fetch_sample(client, size=3)
        page = client.list_test_cases(PROJECT_KEY, page=1)
        all_sample = page.get("data") or []
    except Exception as exc:
        print(f"  Could not read test cases: {exc}")
        return 2

    results = []
    fields_r, seen_fields = check_fields(sample, baseline)
    results.append(fields_r)
    results.append(check_aliases(client))
    status_r, live_statuses = check_statuses(client)
    results.append(status_r)
    results.append(check_tags(all_sample))
    endpoint_r, endpoint_codes = check_endpoints(client)
    results.append(endpoint_r)

    print()
    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        print(f"  [{mark}] {r.name}")
        for p in r.problems:
            print(f"         {p}")
        if r.notes and (args.verbose or not r.ok):
            for n in r.notes:
                print(f"         note: {n}")

    failed = [r for r in results if not r.ok]
    print()
    print(f"  {len(results) - len(failed)}/{len(results)} checks passed.")

    if args.update:
        save_baseline({
            "recorded": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "project_key": PROJECT_KEY,
            "case_fields": seen_fields,
            "statuses": {str(k): v for k, v in live_statuses.items()},
            "endpoint_status_codes": endpoint_codes,
        })
        print(f"  Baseline written to {BASELINE_PATH.relative_to(ROOT)}")
        return 0

    if failed:
        print()
        print("  The API drifted. Work out which side is wrong before you act.")
        print("  Fix our code to match, THEN re-record with --update.")
        print("  Do not --update to silence a failure you have not understood.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
