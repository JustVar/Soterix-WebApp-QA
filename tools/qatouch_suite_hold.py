#!/usr/bin/env python3
"""Put QA Touch test cases on suite hold.

A suite hold removes cases from named suites (SMOKE / SANITY / REGRESSION)
without deleting the cases. QA Touch builds those suites from case tags, so
the hold removes the suite tag and records what it removed. One command puts
the tags back when the hold is lifted.

Current hold: PTZ modules are out of Sanity and Regression until further notice.

Commands:
    status    Show the live tag state of the matched cases (no browser needed)
    runs      Show which open test runs already contain the matched cases
    preview   Show exactly which tags would be removed (no browser needed)
    apply     Remove the suite tags and write a restore file (needs QA Touch login)
    restore   Put back the tags recorded in a restore file (needs QA Touch login)

Usage:
    python tools/qatouch_suite_hold.py status  --modules PTZ
    python tools/qatouch_suite_hold.py runs    --modules PTZ
    python tools/qatouch_suite_hold.py preview --modules PTZ --suites sanity,regression
    python tools/qatouch_suite_hold.py apply   --modules PTZ --suites sanity,regression
    python tools/qatouch_suite_hold.py restore --backup config/qatouch_suite_holds/<file>.json

Notes:
    - status, runs and preview read the public API only. They change nothing.
    - apply and restore open a browser. Log in to QA Touch when it asks.
    - apply writes a restore file to config/qatouch_suite_holds/ before it
      changes anything. Keep that file. It is the only record of the tags.
    - Tags control which cases go into NEW runs. Runs that already exist keep
      their cases. Use the 'runs' command to see which ones need manual work.
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
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

BASE_URL = "https://soterixsystems.qatouch.com"
PROJECT_KEY = os.environ.get("QATOUCH_PROJECT_ID", "JlW1")
AUTH_STATE_FILE = str(ROOT / "tools" / ".qatouch_auth_state.json")
TAG_IDS_FILE = ROOT / "config" / "qatouch_tag_ids.json"
HOLD_DIR = ROOT / "config" / "qatouch_suite_holds"

INTER_CALL_DELAY = 0.2
BURST_PAUSE = 10.0
BURST_THRESHOLD = 50
RETRY_BASE_DELAY = 30.0


def load_tag_ids() -> dict:
    """Load the tag name to QA Touch hash ID map."""
    if TAG_IDS_FILE.exists():
        with open(TAG_IDS_FILE, encoding="utf-8") as f:
            return {k.lower(): v for k, v in json.load(f).items()}
    return {"smoke": "99GQ", "sanity": "X1zZ", "regression": "MW0N"}


TAG_IDS = load_tag_ids()
ID_TO_TAG = {v: k for k, v in TAG_IDS.items()}


# -- Case lookup (public API, read only) ------------------------------

def with_retry(call, what: str, attempts: int = 5):
    """Run a QA Touch API call, backing off when the API returns 429.

    The public API rate-limits bursts. Waiting and retrying is enough.
    """
    from tools.qatouch_client import QATouchError

    delay = RETRY_BASE_DELAY
    for attempt in range(1, attempts + 1):
        try:
            return call()
        except QATouchError as exc:
            if "429" not in str(exc) or attempt == attempts:
                raise
            print(f"  Rate limited on {what}. Waiting {delay:.0f}s (attempt {attempt}/{attempts})...")
            time.sleep(delay)
            delay *= 2
    return None


def fetch_live_cases() -> list[dict]:
    """Fetch every test case from the QA Touch public API."""
    from tools.qatouch_client import QATouchClient

    client = QATouchClient()
    print(f"  Fetching live cases from project {PROJECT_KEY}...")
    cases = with_retry(lambda: client.list_all_test_cases(PROJECT_KEY), "case list")
    print(f"  Fetched {len(cases)} cases")
    return cases


def case_module(case: dict) -> str:
    """Read the module name. The public API and the snapshots use different keys."""
    return str(case.get("module_name") or case.get("module name") or "")


def case_tags(case: dict) -> list[str]:
    """Read the tag names on a case as lowercase strings."""
    tags = case.get("Tags")
    if tags is None:
        tags = case.get("NewTags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in tags.split(",") if t.strip()]
    return [str(t).strip().lower() for t in tags]


def select_cases(cases: list[dict], modules: str, keys: str) -> list[dict]:
    """Select cases by module name substring or by explicit case key."""
    if keys:
        wanted = {k.strip() for k in keys.split(",") if k.strip()}
        found = [c for c in cases if c.get("case_key") in wanted]
        missing = wanted - {c["case_key"] for c in found}
        for k in sorted(missing):
            print(f"  WARNING: case key {k} not found in QA Touch")
        return found

    if modules:
        needles = [m.strip().lower() for m in modules.split(",") if m.strip()]
        return [c for c in cases if any(n in case_module(c).lower() for n in needles)]

    print("  ERROR: provide --modules or --keys")
    return []


def plan_removals(selected: list[dict], suites: str) -> list[dict]:
    """Build the list of cases that carry at least one of the suite tags."""
    targets = [s.strip().lower() for s in suites.split(",") if s.strip()]
    unknown = [t for t in targets if t not in TAG_IDS]
    if unknown:
        print(f"  ERROR: unknown suite tag(s) {unknown} - not in {TAG_IDS_FILE.name}")
        return []

    plan = []
    for c in selected:
        present = case_tags(c)
        to_remove = [t for t in targets if t in present]
        if to_remove:
            plan.append({
                "case_key": c["case_key"],
                "case_code": c.get("case_code", ""),
                "module": case_module(c),
                "title": c.get("case_title", ""),
                "tags_before": present,
                "remove": to_remove,
            })
    return plan


def group_by_module(rows: list[dict]) -> dict:
    """Group plan rows by module name."""
    out: dict[str, list] = {}
    for r in rows:
        out.setdefault(r["module"], []).append(r)
    return out


# -- Auth (browser, needed for writes only) ---------------------------

def login(p):
    browser = p.chromium.launch(headless=False, slow_mo=50, args=["--start-maximized"])
    if os.path.exists(AUTH_STATE_FILE):
        print("  Loading saved auth state...")
        ctx = browser.new_context(
            storage_state=AUTH_STATE_FILE,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()
        page.goto(f"{BASE_URL}/v2#/new-projects", timeout=60000)
        time.sleep(5)
        url = page.url or ""
        if "/login" not in url and "qatouch.com" in url:
            print("  Auth state valid!")
            return browser, ctx, page
        print("  Auth expired -- need fresh login.")
        ctx.close()
        with contextlib.suppress(OSError):
            os.remove(AUTH_STATE_FILE)

    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()
    page.goto(f"{BASE_URL}/login", timeout=60000)
    page.bring_to_front()
    print()
    print("=" * 60)
    print("  BROWSER OPENED -- Please log in to QA Touch")
    print("  Waiting up to 600 seconds...")
    print("=" * 60)
    for i in range(200):
        time.sleep(3)
        if i % 20 == 0 and i > 0:
            with contextlib.suppress(Exception):
                page.bring_to_front()
            print(f"  Still waiting... ({i * 3}s elapsed)")
        url = page.url or ""
        if "/login" not in url and "qatouch.com" in url:
            print("  Login detected!")
            time.sleep(2)
            ctx.storage_state(path=AUTH_STATE_FILE)
            return browser, ctx, page
    browser.close()
    raise SystemExit("Login timeout after 600s")


# -- Internal API (browser session) -----------------------------------

CASE_EDIT_JS = """
    async ({caseKey, pid}) => {
        try {
            const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
            const resp = await fetch('/v1/case/edit/p/' + pid + '/cid/' + caseKey, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                    'X-XSRF-TOKEN': decodeURIComponent(token || '')
                },
                body: JSON.stringify({})
            });
            if (!resp.ok) return {error: 'HTTP ' + resp.status};
            const data = await resp.json();
            if (!data || !data.data) return {error: 'No data'};
            return data.data;
        } catch (e) {
            return {error: e.message};
        }
    }
"""

CASE_UPDATE_JS = """
    async ({caseKey, payload, pid}) => {
        try {
            const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
            const resp = await fetch('/v1/case/update/p/' + pid + '/cid/' + caseKey, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json;charset=UTF-8',
                    'Accept': 'application/json',
                    'X-XSRF-TOKEN': decodeURIComponent(token || '')
                },
                body: JSON.stringify(payload)
            });
            const text = await resp.text();
            return {status: resp.status, ok: resp.ok, body: text.substring(0, 500)};
        } catch (e) {
            return {error: e.message};
        }
    }
"""


def get_case_data(page, case_key: str) -> dict | None:
    """Read the full case record through /v1/case/edit."""
    result = page.evaluate(CASE_EDIT_JS, {"caseKey": case_key, "pid": PROJECT_KEY})
    if result and result.get("error"):
        return None
    return result


def update_case_newtags(page, case_key: str, case_data: dict, newtags: list[str]) -> dict:
    """Write a new newtags array through /v1/case/update.

    Clearing every tag needs newtags = [""], not []. Measured 2026-08-17:
    the endpoint answers {"status": true, "msg": "Case Updated Successfully"}
    for [], null and "" and changes nothing - it reads those as "field not
    supplied". A list holding one empty string is the explicit "no tags"
    signal. A non-empty list is honoured as given.
    """
    payload = dict(case_data)
    payload["newtags"] = list(newtags) if newtags else [""]
    for field in ["checkedRequirements", "gitlabcheckedRequirements", "detailArray"]:
        if field not in payload:
            payload[field] = []

    return page.evaluate(
        CASE_UPDATE_JS,
        {"caseKey": case_key, "payload": payload, "pid": PROJECT_KEY},
    )


def strip_tags_from_case(page, case_key: str, tag_names: list[str]) -> tuple[bool, str, list[str]]:
    """Remove the named tags from one case. Returns (ok, message, ids_removed)."""
    ids = [TAG_IDS[t] for t in tag_names if t in TAG_IDS]
    data = get_case_data(page, case_key)
    if not data:
        return False, "Failed to read case data", []

    current = data.get("newtags") or []
    removed = [i for i in ids if i in current]
    if not removed:
        return True, "Tags already absent", []

    kept = [t for t in current if t not in removed]
    result = update_case_newtags(page, case_key, data, kept)
    if not result.get("ok"):
        detail = str(result.get("body", result.get("error", "?")))[:200]
        return False, f"HTTP {result.get('status', '?')}: {detail}", []

    # The endpoint reports success even when it changed nothing, so confirm.
    time.sleep(0.4)
    after = get_case_data(page, case_key)
    still = [i for i in removed if i in ((after or {}).get("newtags") or [])]
    if still:
        names = ", ".join(ID_TO_TAG.get(i, i) for i in still)
        return False, f"Reported OK but {names} is still on the case", []
    names = ", ".join(ID_TO_TAG.get(i, i) for i in removed)
    return True, f"Removed {names}", removed


def add_tags_to_case(page, case_key: str, tag_ids: list[str]) -> tuple[bool, str]:
    """Add tag hash IDs back to one case, keeping whatever tags it has now."""
    data = get_case_data(page, case_key)
    if not data:
        return False, "Failed to read case data"

    current = data.get("newtags") or []
    missing = [i for i in tag_ids if i not in current]
    if not missing:
        return True, "Tags already present"

    result = update_case_newtags(page, case_key, data, list(current) + missing)
    if result.get("ok"):
        names = ", ".join(ID_TO_TAG.get(i, i) for i in missing)
        return True, f"Restored {names}"
    detail = str(result.get("body", result.get("error", "?")))[:200]
    return False, f"HTTP {result.get('status', '?')}: {detail}"


# -- Commands ---------------------------------------------------------

def cmd_status(_page, args):
    """Show the live tag state of the matched cases."""
    cases = fetch_live_cases()
    selected = select_cases(cases, args.modules, args.keys)
    if not selected:
        print("  No cases matched.")
        return

    print(f"\n  Matched cases: {len(selected)}")
    by_mod: dict[str, dict] = {}
    for c in selected:
        m = case_module(c)
        entry = by_mod.setdefault(m, {"total": 0, "tags": {}})
        entry["total"] += 1
        tags = case_tags(c)
        label = ", ".join(sorted(tags)) if tags else "(no tags)"
        entry["tags"][label] = entry["tags"].get(label, 0) + 1

    for m in sorted(by_mod):
        e = by_mod[m]
        print(f"\n  {m}  ({e['total']} cases)")
        for label in sorted(e["tags"], key=lambda x: -e["tags"][x]):
            print(f"      {e['tags'][label]:4d}  {label}")


def cmd_runs(_page, args):
    """Show which open test runs already contain the matched cases."""
    from tools.qatouch_client import QATouchClient

    cases = fetch_live_cases()
    selected = select_cases(cases, args.modules, args.keys)
    if not selected:
        print("  No cases matched.")
        return
    keys = {c["case_key"] for c in selected}

    client = QATouchClient()
    runs = with_retry(lambda: client.list_test_runs(PROJECT_KEY), "run list")
    print(f"\n  Checking {len(runs)} test runs for {len(keys)} matched cases...\n")
    hits = 0
    for r in runs:
        run_key = r.get("testrun_key") or r.get("test_run_key") or ""
        name = r.get("Name") or r.get("name") or ""
        status = r.get("Status") or r.get("status") or ""
        try:
            results = with_retry(
                lambda rk=run_key: client.get_all_test_run_results(PROJECT_KEY, rk),
                f"run {run_key}",
            )
        except Exception as exc:
            print(f"  {run_key}  ERROR reading run: {exc}")
            continue
        present = [x for x in results if x.get("case_id") in keys]
        flag = "  <-- contains matched cases" if present else ""
        if present:
            hits += 1
        print(f"  {run_key}  [{status:6s}]  {len(present):4d} / {len(results):5d}  {name}{flag}")

    if hits:
        print(f"\n  {hits} run(s) already contain the matched cases.")
        print("  Tag changes do NOT alter runs that already exist.")
        print("  Remove those cases in the QA Touch UI, or leave the runs as history.")


def cmd_preview(_page, args):
    """Show exactly which tags would be removed."""
    cases = fetch_live_cases()
    selected = select_cases(cases, args.modules, args.keys)
    if not selected:
        print("  No cases matched.")
        return

    plan = plan_removals(selected, args.suites)
    print(f"\n  Matched cases:      {len(selected)}")
    print(f"  Cases to change:    {len(plan)}")
    print(f"  Suite tags in hold: {args.suites}")
    if not plan:
        print("\n  Nothing to do. None of the matched cases carry those tags.")
        return

    for mod, rows in sorted(group_by_module(plan).items()):
        print(f"\n  {mod}  ({len(rows)} cases)")
        for r in rows:
            tags = ",".join(r["remove"])
            print(f"      {r['case_key']}  {r['case_code']:8s}  -{tags:12s}  {r['title'][:60]}")
    print("\n  Preview only. Nothing changed.")


def write_hold_file(path: Path, plan: list[dict], args, stamp: str):
    """Write the restore file that records every removed tag."""
    payload = {
        "created": stamp,
        "project_key": PROJECT_KEY,
        "label": args.label or args.modules,
        "modules": args.modules,
        "keys": args.keys,
        "suites": args.suites,
        "reason": args.reason,
        "tag_ids": TAG_IDS,
        "cases": plan,
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def cmd_apply(page, args):
    """Remove the suite tags from the matched cases."""
    cases = fetch_live_cases()
    selected = select_cases(cases, args.modules, args.keys)
    if not selected:
        print("  No cases matched.")
        return

    plan = plan_removals(selected, args.suites)
    print(f"\n  Matched cases:   {len(selected)}")
    print(f"  Cases to change: {len(plan)}")
    if not plan:
        print("\n  Nothing to do.")
        return

    HOLD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    label = (args.label or (args.modules or "cases").replace(",", "-")).strip().lower()
    backup = HOLD_DIR / f"hold_{label}_{stamp}.json"
    write_hold_file(backup, plan, args, stamp)
    print(f"  Restore file:    {backup.relative_to(ROOT)}")
    print("\n  Applying...\n")

    ok_count = 0
    fail_count = 0
    for i, row in enumerate(plan, 1):
        ok, msg, removed = strip_tags_from_case(page, row["case_key"], row["remove"])
        row["removed_ids"] = removed
        row["result"] = msg
        mark = "OK " if ok else "FAIL"
        print(f"  [{i:3d}/{len(plan)}] {mark} {row['case_key']}  {msg}  |  {row['title'][:50]}")
        if ok:
            ok_count += 1
        else:
            fail_count += 1
        write_hold_file(backup, plan, args, stamp)
        time.sleep(INTER_CALL_DELAY)
        if i % BURST_THRESHOLD == 0 and i < len(plan):
            print(f"  ... pausing {BURST_PAUSE}s after {i} calls")
            time.sleep(BURST_PAUSE)

    print(f"\n  Done. Changed {ok_count}, failed {fail_count}.")
    rel = backup.relative_to(ROOT)
    print(f"  Restore with: python tools/qatouch_suite_hold.py restore --backup {rel}")
    print("  Reminder: runs that already exist keep their cases. Check the 'runs' command.")


def cmd_restore(page, args):
    """Put back the tags recorded in a restore file."""
    path = Path(args.backup)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print(f"  ERROR: restore file not found: {path}")
        return

    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    rows = [r for r in payload.get("cases", []) if r.get("removed_ids")]
    print(f"\n  Restore file: {path.name}")
    print(f"  Hold reason:  {payload.get('reason') or '(none recorded)'}")
    print(f"  Cases to restore: {len(rows)}")
    if not rows:
        print("  Nothing recorded as removed. Nothing to do.")
        return

    if args.dry_run:
        for r in rows:
            names = ",".join(ID_TO_TAG.get(i, i) for i in r["removed_ids"])
            print(f"      {r['case_key']}  +{names}  {r['title'][:60]}")
        print("\n  Dry run. Nothing changed.")
        return

    ok_count = 0
    fail_count = 0
    for i, r in enumerate(rows, 1):
        ok, msg = add_tags_to_case(page, r["case_key"], r["removed_ids"])
        mark = "OK " if ok else "FAIL"
        print(f"  [{i:3d}/{len(rows)}] {mark} {r['case_key']}  {msg}  |  {r['title'][:50]}")
        if ok:
            ok_count += 1
        else:
            fail_count += 1
        time.sleep(INTER_CALL_DELAY)
        if i % BURST_THRESHOLD == 0 and i < len(rows):
            print(f"  ... pausing {BURST_PAUSE}s after {i} calls")
            time.sleep(BURST_PAUSE)

    print(f"\n  Done. Restored {ok_count}, failed {fail_count}.")


# Imported so there is one definition of the status names in the repo.
from tools.qatouch_client import STATUS_NAMES, normalize_status_name

# Accepts "not-applicable", "Not Applicable", "NOT APPLICABLE" alike.
STATUS_BY_NAME = {normalize_status_name(v).replace(" ", "-"): k
                  for k, v in STATUS_NAMES.items()}
UNEXECUTED = ("Untested", None, "")


def collect_run_rows(client, selected, run_filter):
    """Find every (case, run) pair for the selected cases.

    Uses one getTestRunlist call per case, which is far cheaper than paging
    the results of every run.
    """
    wanted = [r.strip().lower() for r in run_filter.split(",") if r.strip()]
    rows = []
    for i, c in enumerate(selected, 1):
        runs = with_retry(
            lambda ck=c["case_key"]: client.get_case_test_runs(ck),
            "runs for " + c["case_key"],
        )
        for r in runs or []:
            key = r.get("testrunkey") or ""
            name = r.get("name") or ""
            if wanted and not any(w in key.lower() or w in name.lower() for w in wanted):
                continue
            rows.append({
                "case_key": c["case_key"],
                "case_code": c.get("case_code", ""),
                "module": case_module(c),
                "title": c.get("case_title", ""),
                "run_key": key,
                "run_name": name,
                "result_key": r.get("resultKey"),
                "status_before": r.get("status"),
            })
        time.sleep(INTER_CALL_DELAY)
        if i % 15 == 0:
            print("  ...checked " + str(i) + "/" + str(len(selected)) + " cases")
    return rows


def summarise_rows(rows):
    """Print a per-run breakdown of current statuses."""
    by_run = {}
    for r in rows:
        e = by_run.setdefault(r["run_name"] or r["run_key"], {"key": r["run_key"], "st": {}})
        e["st"][r["status_before"]] = e["st"].get(r["status_before"], 0) + 1
    for name in sorted(by_run):
        e = by_run[name]
        total = sum(e["st"].values())
        detail = ", ".join(str(n) + " " + str(st)
                           for st, n in sorted(e["st"].items(), key=lambda x: -x[1]))
        print(f"  {e['key']}  {total:4d} cases  {name}")
        print("        " + detail)


def cmd_runs_mark(_page, args):
    """Set the matched cases to a status inside one or more test runs."""
    from tools.qatouch_client import QATouchClient, case_code_to_ref

    target = STATUS_BY_NAME.get(normalize_status_name(args.status).replace(" ", "-"))
    if not target:
        print("  ERROR: unknown status. Options: " + str(sorted(STATUS_BY_NAME)))
        return

    client = QATouchClient()
    cases = fetch_live_cases()
    selected = select_cases(cases, args.modules, args.keys)
    if not selected:
        print("  No cases matched.")
        return

    print("\n  Finding these " + str(len(selected)) + " cases inside test runs...")
    rows = collect_run_rows(client, selected, args.run)
    if not rows:
        print("  No matching (case, run) pairs found.")
        return

    print("\n  Found " + str(len(rows)) + " case-in-run rows:")
    summarise_rows(rows)

    want = normalize_status_name(STATUS_NAMES[target])
    todo = [r for r in rows
            if normalize_status_name(r["status_before"]) != want]
    print("\n  Target status: " + STATUS_NAMES[target])
    print("  Rows to change: " + str(len(todo))
          + " (skipping " + str(len(rows) - len(todo)) + " already set)")

    executed = [r for r in todo if r["status_before"] not in UNEXECUTED]
    if executed:
        print("\n  WARNING: " + str(len(executed)) + " row(s) already carry an execution")
        print("  result (Passed / Failed / Blocked). Changing them overwrites that record.")
        if not args.include_executed:
            print("  Skipping them. Pass --include-executed to change them anyway.")
            todo = [r for r in todo if r["status_before"] in UNEXECUTED]
            print("  Rows to change after skip: " + str(len(todo)))

    if not todo:
        print("\n  Nothing to do.")
        return

    if args.dry_run:
        for r in todo[:60]:
            print(f"      {r['run_key']}  {r['case_code']:8s}  "
                  f"{r['status_before']!s:15s} -> {STATUS_NAMES[target]}  {r['title'][:45]}")
        if len(todo) > 60:
            print("      ... and " + str(len(todo) - 60) + " more")
        print("\n  Dry run. Nothing changed.")
        return

    HOLD_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    label = (args.label or "runmark").strip().lower()
    backup = HOLD_DIR / ("runstatus_" + label + "_" + stamp + ".json")
    with open(backup, "w", encoding="utf-8") as f:
        json.dump({"created": stamp, "project_key": PROJECT_KEY, "target_status": target,
                   "reason": args.reason, "rows": todo}, f, indent=2)
    print("\n  Restore file: " + str(backup.relative_to(ROOT)))

    by_run = {}
    for r in todo:
        by_run.setdefault(r["run_key"], []).append(r)

    for run_key, group in by_run.items():
        payload = [{"case": case_code_to_ref(r["case_code"]), "status": target} for r in group]
        print("\n  " + run_key + ": sending " + str(len(payload)) + " updates...")
        try:
            with_retry(lambda rk=run_key, pl=payload:
                       client.update_test_run_results(PROJECT_KEY, rk, pl), "update " + run_key)
        except Exception as exc:
            print("    ERROR: " + str(exc)[:160])
            continue
        # This endpoint reports success even when nothing changed, so verify.
        time.sleep(2)
        sample = group[0]
        runs = with_retry(lambda ck=sample["case_key"]: client.get_case_test_runs(ck),
                          "verify read-back") or []
        now = next((x.get("status") for x in runs if x.get("testrunkey") == run_key), "?")
        ok = normalize_status_name(now) == normalize_status_name(STATUS_NAMES[target])
        print("    verify " + sample["case_code"] + ": " + str(sample["status_before"])
              + " -> " + str(now) + ("  OK" if ok else "  DID NOT APPLY"))

    print("\n  Done. Restore with: python tools/qatouch_suite_hold.py runs-restore --backup "
          + str(backup.relative_to(ROOT)))


def cmd_runs_restore(_page, args):
    """Put back the statuses recorded in a run-status restore file."""
    from tools.qatouch_client import QATouchClient, case_code_to_ref

    path = Path(args.backup)
    if not path.is_absolute():
        path = ROOT / path
    if not path.exists():
        print("  ERROR: restore file not found: " + str(path))
        return
    with open(path, encoding="utf-8") as f:
        payload = json.load(f)

    rows = payload.get("rows", [])
    print("\n  Restore file: " + path.name)
    print("  Rows to restore: " + str(len(rows)))
    if args.dry_run:
        for r in rows[:40]:
            print(f"      {r['run_key']}  {r['case_code']:8s}  -> {r['status_before']}")
        print("\n  Dry run. Nothing changed.")
        return

    client = QATouchClient()
    by_run = {}
    for r in rows:
        by_run.setdefault(r["run_key"], []).append(r)
    for run_key, group in by_run.items():
        out = []
        for r in group:
            code = STATUS_BY_NAME.get(
                normalize_status_name(r["status_before"]).replace(" ", "-"))
            if code:
                out.append({"case": case_code_to_ref(r["case_code"]), "status": code})
        if not out:
            continue
        print("  " + run_key + ": restoring " + str(len(out)) + " rows...")
        with_retry(lambda rk=run_key, pl=out:
                   client.update_test_run_results(PROJECT_KEY, rk, pl), "restore " + run_key)
    print("\n  Done.")


# -- Main -------------------------------------------------------------

EPILOG = """
Examples:
  See where PTZ cases stand today:
    python tools/qatouch_suite_hold.py status --modules PTZ

  See which existing runs already hold PTZ cases:
    python tools/qatouch_suite_hold.py runs --modules PTZ

  Preview the PTZ hold:
    python tools/qatouch_suite_hold.py preview --modules PTZ --suites sanity,regression

  Apply the PTZ hold:
    python tools/qatouch_suite_hold.py apply --modules PTZ --suites sanity,regression
        --label ptz --reason "PTZ out of Sanity and Regression until further notice"

  Lift the hold later:
    python tools/qatouch_suite_hold.py restore --backup config/qatouch_suite_holds/hold_ptz_STAMP.json
"""


def main():
    parser = argparse.ArgumentParser(
        description="QA Touch suite hold - remove cases from SANITY / REGRESSION suites, reversibly",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
    )
    sub = parser.add_subparsers(dest="command")

    def add_selectors(p, with_suites=True):
        p.add_argument("--modules", default="",
                       help="Module name substring(s), comma separated (e.g. PTZ)")
        p.add_argument("--keys", default="", help="Explicit case keys, comma separated")
        if with_suites:
            p.add_argument("--suites", default="sanity,regression",
                           help="Suite tags to remove (default: sanity,regression)")

    st = sub.add_parser("status", help="Show live tag state of matched cases")
    add_selectors(st, with_suites=False)

    rn = sub.add_parser("runs", help="Show open runs that already contain matched cases")
    add_selectors(rn, with_suites=False)

    pv = sub.add_parser("preview", help="Show which tags would be removed")
    add_selectors(pv)

    ap = sub.add_parser("apply", help="Remove suite tags and write a restore file")
    add_selectors(ap)
    ap.add_argument("--label", default="", help="Short name for the restore file (e.g. ptz)")
    ap.add_argument("--reason", default="", help="Why the hold exists - recorded in the restore file")

    rs = sub.add_parser("restore", help="Put back the tags from a restore file")
    rs.add_argument("--backup", required=True, help="Path to the restore file")
    rs.add_argument("--dry-run", action="store_true", help="Show what would be restored")

    rm = sub.add_parser("runs-mark",
                        help="Set matched cases to a status inside test runs")
    add_selectors(rm, with_suites=False)
    rm.add_argument("--run", default="", help="Run key or name substring(s), comma separated")
    rm.add_argument("--status", default="not-applicable",
                    help="Target status (default: not-applicable)")
    rm.add_argument("--include-executed", action="store_true",
                    help="Also overwrite rows that already have a Passed/Failed/Blocked result")
    rm.add_argument("--label", default="", help="Short name for the restore file")
    rm.add_argument("--reason", default="", help="Why - recorded in the restore file")
    rm.add_argument("--dry-run", action="store_true", help="Preview without changes")

    rr = sub.add_parser("runs-restore", help="Put back statuses from a run-status restore file")
    rr.add_argument("--backup", required=True, help="Path to the restore file")
    rr.add_argument("--dry-run", action="store_true", help="Show what would be restored")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    print(f"\n{'=' * 60}")
    print("  QA TOUCH SUITE HOLD")
    print(f"{'=' * 60}")

    # Read-only commands need no browser.
    if args.command in ("status", "runs", "preview", "runs-mark", "runs-restore"):
        handlers = {"status": cmd_status, "runs": cmd_runs, "preview": cmd_preview,
                    "runs-mark": cmd_runs_mark, "runs-restore": cmd_runs_restore}
        handlers[args.command](None, args)
        return

    if args.command == "restore" and args.dry_run:
        cmd_restore(None, args)
        return

    from playwright.sync_api import sync_playwright

    print("  Starting browser for QA Touch write access...")
    with sync_playwright() as p:
        browser, ctx, page = login(p)
        try:
            page.goto(f"{BASE_URL}/v2#/new-projects", timeout=30000)
            time.sleep(3)
            {"apply": cmd_apply, "restore": cmd_restore}[args.command](page, args)
        finally:
            ctx.close()
            browser.close()


if __name__ == "__main__":
    main()
