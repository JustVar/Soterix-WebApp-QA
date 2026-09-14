"""
qa_post_import_split_and_position.py
=====================================

Post-import step splitter + last-step expected-result placer.

Phase 5 of the QA Touch import pipeline (see docs/qa_import_pipeline.md).

Why this script exists
----------------------
The QA Touch CSV importer (phase 3) collapses our multi-line `Steps` cell
(which contains `Step 1: ...\\nStep 2: ...\\n...\\nStep N: ...`) into a single
merged "Step 1" row in the case's Steps tab (see
docs/local/qa_touch_integration.md:417-419). This tool:

  1. For each case in scope:
       a. Reads /v1/case/edit -> data.caseStep[*].id  (the existing merged
          step row IDs).
       b. Parses the canonical CSV's `Steps` cell on \\n into N step texts.
          Strips the "Step N: " prefix.
       c. Parses the canonical CSV's `Expected_result` cell on \\n. Because
          the converter padded with "-" sentinels on steps 1..N-1 and put the
          case-level expected on step N, we use that vector directly. If the
          source CSV is "old style" (one expected per step), we use that
          vector as-is.
       d. Deletes the existing caseStep rows via /v1/steps/delete.
       e. Saves N new step rows via /v1/steps/save, in position order, each
          with description = step_text and expected_result = the matching
          line (which will be "-" for steps 1..N-1 and the real assertion for
          step N).
       f. Verifies via /v1/case/edit that caseStep count == N. Mismatch is
          logged as verify_mismatch (the case is left as-is - re-run with
          --only-titles to fix).

  2. Idempotency: if the case already has N rows AND the LAST row's expected
     looks like the case-level expected (i.e. it is non-empty AND non-"-"),
     skip the case. Lets re-runs be safe.

Auth model: Playwright Chromium headed (slow_mo=50). XSRF-TOKEN cookie
harvested from document.cookie and sent as X-XSRF-TOKEN header. Auth state
cached at tools/.qatouch_auth_state.json. Headless mode is known to fail.

Rate limits (per qatouch_c2c_step_split.py precedent):
  INTER_CALL_DELAY  = 0.15s between every /v1/* call
  INTER_CASE_DELAY  = 0.3s  between cases
  RATE_LIMIT_PAUSE  = 15.0s on HTTP 429, then retry the save once

CLI
---
    python tools/qa_post_import_split_and_position.py \\
        --project-key 70l1 \\
        --csv tests/data/<release>_<module>_canonical.csv \\
      [ --module-key MOD123 ]      # restrict to one module
      [ --case-keys KEY1,KEY2 ]    # restrict to specific case keys
      [ --only-titles "t1,t2" ]    # restrict by title substring (any-of)
      [ --limit N ]                # process at most N cases
      [ --dry-run ]                # do not call /v1/steps/save or /delete
      [ --resume-from N ]          # skip the first N matched cases
      [ --auth-state-file PATH ]
      [ --rate-ms 150 ]            # override INTER_CALL_DELAY (in ms)
      [ --inter-step-ms 0 ]        # extra delay between create_step calls
"""
from __future__ import annotations

import argparse
import csv
import functools
import html as html_mod
import os
import re
import sys
import time
from pathlib import Path

_print = print
print = functools.partial(_print, flush=True)
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv  # type: ignore[import]
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("ERROR: playwright required. pip install playwright && playwright install chromium")
    sys.exit(1)


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

BASE_URL = "https://soterixsystems.qatouch.com"
DEFAULT_AUTH_STATE = str(ROOT / "tools" / ".qatouch_auth_state.json")

INTER_CALL_DELAY = 0.15
INTER_CASE_DELAY = 0.3
RATE_LIMIT_PAUSE = 15.0


# --------------------------------------------------------------------------- #
# CSV loader - keyed by Test Case Title (the backfill's match key)
# --------------------------------------------------------------------------- #

def load_csv_by_title(csv_path: str) -> dict[str, dict]:
    """Return {title: {module, steps:[str], expecteds:[str], reference}}.

    Steps cell format (canonical, from qa_xlsx_to_qatouch_csv.py):
        "Step 1: <text>\\nStep 2: <text>\\n...\\nStep N: <text>"
    Expected_result cell format:
        "-\\n-\\n...\\n<full case-level expected on the last line>"
        (or a single string if only 1 step)

    We strip the "Step N: " prefix and the "1. " numbered-list prefix (in case
    the CSV came from an older converter run).
    """
    cases: dict[str, dict] = {}
    # Accept both vendor-canonical slugs (post 2026-06-26 converter rename) and
    # the legacy friendly headers so historical canonical CSVs keep working.
    def get_col(row: dict[str, str], canonical: str, legacy: str) -> str:
        val = row.get(canonical)
        if val is None or val == "":
            val = row.get(legacy)
        return (val or "").strip()

    with open(csv_path, encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            title = get_col(row, "title", "Test Case Title")
            if not title:
                continue

            raw_steps = get_col(row, "steps", "Steps")
            raw_expected = get_col(row, "expected_result", "Expected_result")

            # Split on LF (the converter writes literal LFs inside the quoted cell).
            step_lines = [s for s in raw_steps.split("\n") if s.strip()] if raw_steps else []
            expected_lines = raw_expected.split("\n") if raw_expected else []

            steps: list[str] = []
            for line in step_lines:
                t = line.strip()
                # Strip "Step N: " prefix (canonical converter format).
                t = re.sub(r"^Step\s*\d+\s*[:\.\)]\s*", "", t, flags=re.IGNORECASE)
                # Strip any leftover "N. " numbering (older converter / hand-edits).
                t = re.sub(r"^\d+\s*[\.\):-]\s*", "", t)
                if t:
                    steps.append(t)

            if not steps:
                continue

            # Build per-step expected vector of length len(steps).
            # If expected_lines is shorter, pad with "-" on the left (steps 1..N-1)
            # so the LAST step receives the real expected text.
            n = len(steps)
            if len(expected_lines) >= n:
                expecteds = [e.strip() for e in expected_lines[:n]]
            elif len(expected_lines) == 1:
                # Single-blob expected -> place on last step, "-" on the rest.
                expecteds = ["-"] * (n - 1) + [expected_lines[0].strip() or "-"]
            else:
                # Some intermediate count: keep what we have on the leading steps
                # (preserving any per-step text the author wrote) and force the
                # LAST line into the LAST step slot.
                head = [e.strip() for e in expected_lines[:-1]]
                last = expected_lines[-1].strip() or "-"
                # Pad head with "-" up to n-1, then put last on slot n-1.
                while len(head) < n - 1:
                    head.append("-")
                head = head[:n - 1]
                expecteds = head + [last]

            cases[title] = {
                "module":     get_col(row, "section_name", "Module_name"),
                "steps":      steps,
                "expecteds":  expecteds,
                "reference":  get_col(row, "reference", "Reference"),
            }
    return cases


# --------------------------------------------------------------------------- #
# HTML round-trip (the rich-text editor needs this exact escape pattern)
# --------------------------------------------------------------------------- #

def escape_for_html(text: str) -> str:
    """Round-trip unescape -> escape(quote=False). Matches qatouch_c2c_step_split.py
    lines 115-117 and qatouch_step_api.py lines 144-151.

    Why round-trip: the converter HTML-escaped < and > when writing the CSV
    (TR0028/TR0029 defense). When we push back through /v1/steps/save the
    server wraps in <p>...</p> for the rich-text editor; if we leave the
    pre-escaped &lt; in the body, the editor renders the literal "&lt;" text
    instead of "<". So we unescape first (to get back the literal < character)
    then re-escape (so the server sees a clean &lt;) - net: the editor
    displays the original "<" character correctly.
    """
    plain = html_mod.unescape(text)
    return html_mod.escape(plain, quote=False)


# --------------------------------------------------------------------------- #
# Playwright login (lifted from qatouch_c2c_step_split.py)
# --------------------------------------------------------------------------- #

def _is_logged_in(page) -> bool:
    url = page.url or ""
    if any(x in url for x in ("/dashboard", "/project", "/testCase",
                              "/modules", "/new-projects", "/case/list")):
        return True
    for sel in ('text="Dashboard"', 'text="Project List"'):
        try:
            if page.locator(sel).first.is_visible(timeout=500):
                return True
        except Exception:
            pass
    return False


def login(p, auth_state_file: str):
    browser = p.chromium.launch(headless=False, slow_mo=50)

    if os.path.exists(auth_state_file):
        print("  Loading saved auth state...")
        ctx = browser.new_context(
            storage_state=auth_state_file,
            viewport={"width": 1400, "height": 900},
        )
        page = ctx.new_page()
        page.goto(f"{BASE_URL}/v2#/new-projects", timeout=60000)
        time.sleep(5)
        if _is_logged_in(page):
            print("  Auth state valid!")
            return browser, ctx, page
        ctx.close()
        try:
            os.remove(auth_state_file)
        except OSError:
            pass

    ctx = browser.new_context(viewport={"width": 1400, "height": 900})
    page = ctx.new_page()
    page.goto(f"{BASE_URL}/login", timeout=60000)
    print()
    print("=" * 60)
    print("  BROWSER OPENED -- please log in to QA Touch")
    print("  Waiting up to 300 seconds...")
    print("=" * 60)
    for _ in range(100):
        time.sleep(3)
        if _is_logged_in(page):
            print("  Login detected!")
            time.sleep(2)
            ctx.storage_state(path=auth_state_file)
            return browser, ctx, page
    browser.close()
    raise SystemExit("Login timeout after 300s")


# --------------------------------------------------------------------------- #
# QA Touch internal API wrappers - all go through page.evaluate (fetch)
# --------------------------------------------------------------------------- #

def fetch_project_cases(page, project_key: str) -> list[dict]:
    """Paginate /v1/case/list/p/{projectKey} until empty. Returns list of
    {key, title, module}."""
    all_cases: list[dict] = []
    page_num = 1
    while True:
        result = page.evaluate(
            """async ([pid, pageNum]) => {
                try {
                    const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
                    const resp = await fetch('/v1/case/list/p/' + pid + '?page=' + pageNum, {
                        method: 'GET',
                        headers: {
                            'Accept': 'application/json',
                            'X-XSRF-TOKEN': decodeURIComponent(token || '')
                        }
                    });
                    if (!resp.ok) return { error: 'HTTP ' + resp.status };
                    return await resp.json();
                } catch (e) {
                    return { error: e.message };
                }
            }""",
            [project_key, page_num],
        )
        if result.get("error"):
            print(f"  ERROR fetching page {page_num}: {result['error']}")
            break

        cases = (result.get("data") or {}).get("cases", []) or []
        if not cases:
            cases = (result.get("data") or {}).get("testcases", []) or []
        if not cases:
            cases = result.get("cases", []) or []
        if not cases:
            break

        for c in cases:
            all_cases.append({
                "key": c.get("case_key") or c.get("key") or c.get("id"),
                "title": c.get("case_title") or c.get("title") or c.get("name", ""),
                "module": c.get("module_name") or c.get("module", ""),
                "module_key": c.get("module_key") or c.get("mid") or "",
            })
        print(f"  Fetched page {page_num}: {len(cases)} cases (running total: {len(all_cases)})")
        page_num += 1
        if page_num > 50:
            break
        time.sleep(0.2)
    return all_cases


def get_case_steps(page, project_key: str, case_key: str) -> list[dict]:
    """POST /v1/case/edit -> data.caseStep[*]. Returns full step rows so we
    can read both id and existing expected_result text (for idempotency check)."""
    result = page.evaluate(
        """async ([pid, caseKey]) => {
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
                if (!resp.ok) return { error: 'HTTP ' + resp.status, steps: [] };
                const data = await resp.json();
                const steps = data && data.data && data.data.caseStep
                    ? data.data.caseStep : [];
                return { steps: steps };
            } catch (e) {
                return { error: e.message, steps: [] };
            }
        }""",
        [project_key, case_key],
    )
    if result.get("error"):
        return []
    return result.get("steps") or []


def delete_step(page, step_id: str) -> bool:
    result = page.evaluate(
        """async (stepId) => {
            try {
                const resp = await fetch('/v1/steps/delete/mid/' + stepId + '?type=true');
                return { ok: resp.ok, status: resp.status };
            } catch (e) {
                return { ok: false, error: e.message };
            }
        }""",
        step_id,
    )
    return bool(result.get("ok"))


def create_step(page, project_key: str, case_key: str,
                step_desc: str, expected: str) -> dict:
    # Note: /v1/steps/save does NOT exhibit the /v1/case/update 500-on-success
    # quirk (see ok_500_quirk in backfill_qa_touch_metadata.py:18-20). Status
    # 200 means saved; treat any non-200 as a real failure - no body-content
    # special-case needed here.
    safe_desc = escape_for_html(step_desc)
    safe_exp = escape_for_html(expected)
    return page.evaluate(
        """async ([pid, cid, desc, exp]) => {
            try {
                const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
                const resp = await fetch('/v1/steps/save', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json',
                        'X-XSRF-TOKEN': decodeURIComponent(token || '')
                    },
                    body: JSON.stringify({
                        cid: cid,
                        pid: pid,
                        step_description: '<p>' + desc + '</p>',
                        expected_result: '<p>' + exp + '</p>'
                    })
                });
                const body = await resp.text();
                return {
                    ok: resp.ok,
                    status: resp.status,
                    rateLimited: resp.status === 429,
                    body: body.substring(0, 300),
                };
            } catch (e) {
                return { ok: false, error: e.message };
            }
        }""",
        [project_key, case_key, safe_desc, safe_exp],
    )


# --------------------------------------------------------------------------- #
# Per-case sync
# --------------------------------------------------------------------------- #

def _last_step_has_real_expected(steps: list[dict]) -> bool:
    """Idempotency probe - true if the LAST existing step's expected_result is
    non-empty AND not just the "-" sentinel. We strip HTML tags + whitespace
    before checking.
    """
    if not steps:
        return False
    last = steps[-1] or {}
    exp = last.get("expected_result") or last.get("expected") or ""
    plain = re.sub(r"<[^>]+>", "", str(exp)).strip()
    return bool(plain) and plain != "-"


def sync_case(
    page,
    project_key: str,
    case_key: str,
    title: str,
    steps: list[str],
    expecteds: list[str],
    dry_run: bool,
    inter_call_delay: float,
    inter_step_delay: float,
) -> dict:
    """Split one case. Returns {status, deleted, created, error}."""
    result = {"status": "ok", "deleted": 0, "created": 0,
              "skipped_idempotent": False, "error": ""}

    if len(expecteds) != len(steps):
        # Pad/truncate defensively (should not happen if load_csv_by_title is correct).
        if len(expecteds) < len(steps):
            expecteds = expecteds + ["-"] * (len(steps) - len(expecteds))
        else:
            expecteds = expecteds[:len(steps)]

    # ---- Idempotency check ----
    existing = get_case_steps(page, project_key, case_key)
    if (len(existing) == len(steps)
            and _last_step_has_real_expected(existing)):
        result["status"] = "skipped_idempotent"
        result["skipped_idempotent"] = True
        return result

    if dry_run:
        result["created"] = len(steps)
        return result

    # ---- Delete existing rows ----
    for s in existing:
        sid = s.get("id")
        if sid and delete_step(page, sid):
            result["deleted"] += 1
        time.sleep(inter_call_delay)

    # ---- Save N new rows ----
    for i, (step_text, exp_text) in enumerate(zip(steps, expecteds), 1):
        r = create_step(page, project_key, case_key, step_text, exp_text)
        if r.get("rateLimited"):
            print(f"    Rate limited at step {i}/{len(steps)} - sleeping {RATE_LIMIT_PAUSE}s")
            time.sleep(RATE_LIMIT_PAUSE)
            r = create_step(page, project_key, case_key, step_text, exp_text)
        if r.get("ok"):
            result["created"] += 1
        else:
            err = r.get("error") or f"HTTP {r.get('status')}"
            if result["status"] == "ok":
                result["status"] = "partial"
                result["error"] = f"step {i}: {err}"
        time.sleep(inter_call_delay + inter_step_delay)

    # ---- Verify ----
    time.sleep(0.5)
    verify = get_case_steps(page, project_key, case_key)
    if len(verify) != len(steps):
        result["status"] = "verify_mismatch"
        result["error"] = f"expected {len(steps)} steps, got {len(verify)}"

    return result


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #

def select_targets(
    csv_cases: dict[str, dict],
    qt_cases: list[dict],
    module_key: str | None,
    case_keys: list[str] | None,
    only_titles: list[str] | None,
    limit: int | None,
    resume_from: int,
) -> list[tuple[str, str, dict]]:
    """Return ordered list of (case_key, title, csv_payload) tuples."""
    # Build QA Touch title -> case map.
    qt_by_title: dict[str, dict] = {}
    for c in qt_cases:
        if c.get("key") and c.get("title"):
            qt_by_title[c["title"]] = c

    only_filters = [t.lower() for t in (only_titles or []) if t]
    case_key_set = set(case_keys or [])

    targets: list[tuple[str, str, dict]] = []
    for title, payload in csv_cases.items():
        qt = qt_by_title.get(title)
        if not qt:
            continue
        if case_key_set and qt["key"] not in case_key_set:
            continue
        if module_key and qt.get("module_key") != module_key:
            continue
        if only_filters and not any(f in title.lower() for f in only_filters):
            continue
        targets.append((qt["key"], title, payload))

    if resume_from > 0:
        targets = targets[resume_from:]
    if limit:
        targets = targets[:limit]
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project-key", required=True,
                        help="QA Touch projectKey (e.g. 70l1)")
    parser.add_argument("--csv", required=True,
                        help="Canonical CSV produced by qa_xlsx_to_qatouch_csv.py")
    parser.add_argument("--module-key", default=None,
                        help="Restrict to cases whose module_key matches")
    parser.add_argument("--case-keys", default=None,
                        help="Comma-separated list of case keys to process")
    parser.add_argument("--only-titles", default=None,
                        help="Comma-separated substrings; match any case whose "
                             "title contains one of these (case-insensitive)")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most this many matched cases")
    parser.add_argument("--dry-run", action="store_true",
                        help="Do not call /v1/steps/save or /v1/steps/delete; "
                             "still calls /v1/case/edit and /v1/case/list to "
                             "show the match plan.")
    parser.add_argument("--resume-from", type=int, default=0,
                        help="Skip the first N matched cases")
    parser.add_argument("--auth-state-file", default=DEFAULT_AUTH_STATE)
    parser.add_argument("--rate-ms", type=int, default=int(INTER_CALL_DELAY * 1000),
                        help="Override inter-call delay (ms)")
    parser.add_argument("--inter-step-ms", type=int, default=0,
                        help="Extra delay between /v1/steps/save calls (ms)")
    args = parser.parse_args(argv)

    if not os.path.isfile(args.csv):
        print(f"ERROR: csv not found: {args.csv}", file=sys.stderr)
        return 1

    inter_call_delay = max(0.0, args.rate_ms / 1000.0)
    inter_step_delay = max(0.0, args.inter_step_ms / 1000.0)

    case_keys = [k.strip() for k in args.case_keys.split(",")] if args.case_keys else None
    only_titles = [t.strip() for t in args.only_titles.split(",")] if args.only_titles else None

    csv_cases = load_csv_by_title(args.csv)
    print(f"=== Loaded {len(csv_cases)} cases from CSV ===")

    with sync_playwright() as p:
        browser, _ctx, page = login(p, args.auth_state_file)
        try:
            print(f"\n=== Fetching cases from QA Touch (project {args.project_key}) ===")
            qt_cases = fetch_project_cases(page, args.project_key)
            print(f"  Total cases in project: {len(qt_cases)}")

            targets = select_targets(
                csv_cases, qt_cases,
                module_key=args.module_key,
                case_keys=case_keys,
                only_titles=only_titles,
                limit=args.limit,
                resume_from=args.resume_from,
            )

            unmatched = [t for t in csv_cases if t not in {c["title"] for c in qt_cases}]
            if unmatched:
                print(f"\n  WARN: {len(unmatched)} CSV titles not found in QA Touch:")
                for t in unmatched[:10]:
                    print(f"    - {t}")
                if len(unmatched) > 10:
                    print(f"    ...and {len(unmatched) - 10} more")

            print(f"\n=== Processing {len(targets)} cases "
                  f"(dry-run={args.dry_run}) ===\n")

            summary = {"ok": 0, "partial": 0, "verify_mismatch": 0,
                       "skipped_idempotent": 0, "error": 0}
            for i, (case_key, title, payload) in enumerate(targets, 1):
                print(f"[{i:3}/{len(targets)}] {case_key}  {title[:65]}")
                r = sync_case(
                    page=page,
                    project_key=args.project_key,
                    case_key=case_key,
                    title=title,
                    steps=payload["steps"],
                    expecteds=payload["expecteds"],
                    dry_run=args.dry_run,
                    inter_call_delay=inter_call_delay,
                    inter_step_delay=inter_step_delay,
                )
                status = r["status"]
                summary[status] = summary.get(status, 0) + 1
                detail = (f"  ({r['error']})" if r.get("error") else "")
                print(f"           {status.upper()}: "
                      f"deleted={r['deleted']}, created={r['created']}/{len(payload['steps'])}"
                      + detail)
                time.sleep(INTER_CASE_DELAY)

            print("\n=== Summary ===")
            for k, v in summary.items():
                print(f"  {k}: {v}")
        finally:
            browser.close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
