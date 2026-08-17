#!/usr/bin/env python3
"""Detect merged-step cases in a QA Touch project (READ-ONLY audit).

Walks every case in a target project, classifies each as one of:

    merged   - single caseStep row whose HTML body contains >= 3 in-line
               "Step N:" prefixes. Canonical example: NAT-239's 6-step case
               imported as a single blob.
    split    - caseStep.length > 1. Already broken into rows. No action.
    empty    - caseStep.length == 0. Usually template=1 (exploratory) cases.
               Bucketed separately so the operator can spot any real cases
               that lost their steps entirely.
    single   - caseStep.length == 1 with 0-2 prefix markers. A legitimate
               one-step case (e.g. "Click Save and verify the toast").
    error    - /v1/case/edit fetch failed (HTTP non-200 or unparseable).

The merged-detection signature mirrors the canonical splitter at
    tools/qa_post_import_split_and_position.py:146

    STEP_PREFIX_RE = re.compile(r"(?im)^\\s*Step\\s*\\d+\\s*[:\\.\\)]\\s*")

Threshold >= 3 markers protects a legitimate single-step case that happens
to say "see Step 1 above" once or twice (false-positive guard).

NO MUTATIONS. The script never POSTs to /v1/case/update, never creates
modules, never edits step rows. It only paginates the REST list endpoint
and POSTs to /v1/case/edit (which is read-only - empty body returns the
current edit-form snapshot).

Auth
----
This tool needs BOTH auth shapes because the two endpoints it touches
use different auth:

  REST GET /api/v1/getAllTestCases/{projectKey}?page=N
      headers: api-token + domain
      Loaded from the environment / .env (QATOUCH_API_TOKEN +
      QATOUCH_DOMAIN), same as
      tools/migrate_pp_cases_phase_a.py:load_rest_creds.

  Internal POST /v1/case/edit/p/{projectKey}/cid/{caseKey}
      headers: X-XSRF-TOKEN + Cookie
      Loaded from tools/.qatouch_creds.json (same shape as
      tools/run_partner_admin_backfill.py). Refresh with:
          python tools/qatouch_norun_update.py test

Both must be valid. The pre-flight does a lightweight GET /v2 against the
internal-auth domain and a single REST page-1 list against the REST creds
before touching any case.

Output
------
A manifest JSON at --out (default: logs/merged_steps_manifest_{project}_{ts}.json).
Atomic per-record rewrite - a Ctrl-C never leaves a half-written file, and
you can review partial results during a long run.

Manifest shape:
    {
      "header": {
        "started_at":  "...",
        "ended_at":    "...",
        "project_key": "70l1",
        "module_keys": ["KZkZB", ...] or null,   # null == all modules
        "limit":       0,
        "resume_from": 0,
        "rate_ms":     800,
        "summary":     {"merged": N, "split": N, "empty": N,
                        "single": N, "error": N, "by_module": {...}},
      },
      "records": [
        {
          "i":                      1,
          "project_key":            "70l1",
          "module_key":             "KZkZB",
          "module_name":            "Partner Portal Admin",
          "case_key":               "...",
          "case_code":              "NAT-239",
          "case_title":             "...",
          "classification":         "merged" | "split" | "empty" | "single" | "error",
          "step_count":             1,
          "parsed_step_markers":    6,
          "step_excerpt":           "Step 1: ... (first 200 chars)",
          "expected_result_excerpt": "... (first 100 chars)",
          "http_status":            200,
          "error":                  null,
        },
        ...
      ]
    }

Exit codes
----------
    0  scan completed (even if classifications include errors)
    1  scan interrupted (Ctrl-C) - partial manifest preserved
    2  fatal pre-flight error (auth missing/stale, project not found)
"""
from __future__ import annotations

import argparse
import functools
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

# ----------------------------------------------------------------------------
# Print plumbing - flush every line so long runs stream cleanly in CI/Windows.
# ----------------------------------------------------------------------------
_print = print
print = functools.partial(_print, flush=True)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

REPO = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO / "tools"
DEFAULT_CREDS_FILE = TOOLS_DIR / ".qatouch_creds.json"
DEFAULT_LOG_DIR = REPO / "logs"
REST_BASE = "https://api.qatouch.com"

# Canonical merged-step signature - same regex shape and threshold as the
# splitter at tools/qa_post_import_split_and_position.py:146.
STEP_PREFIX_RE = re.compile(r"(?im)^\s*Step\s*\d+\s*[:\.\)]\s*")
MERGED_THRESHOLD = 3

REFRESH_INSTRUCTIONS = (
    "QA Touch internal-auth appears stale (verify GET returned 401/403).\n"
    "Refresh it with:\n"
    "    python tools/qatouch_norun_update.py test\n"
    "That drives a logged-in browser, refreshes tools/.qatouch_auth_state.json,\n"
    "and rewrites tools/.qatouch_creds.json. Then re-run this script."
)


# ----------------------------------------------------------------------------
# Auth: REST (api-token + domain) and internal (cookie + XSRF)
# ----------------------------------------------------------------------------
class AuthCreds:
    """Internal /v1/case/* auth - cookie + XSRF token."""

    def __init__(self, xsrf_token: str, cookie_header: str, domain: str):
        self.xsrf_token = xsrf_token
        self.cookie_header = cookie_header
        self.domain = domain

    @classmethod
    def load(cls, path: Path) -> AuthCreds:
        if not path.exists():
            print(
                f"Auth creds file not found: {path}\n"
                "Generate it with:\n"
                "    python tools/qatouch_norun_update.py test",
                file=sys.stderr,
            )
            raise SystemExit(2)
        data = json.loads(path.read_text(encoding="utf-8"))
        for key in ("xsrf_token", "cookie_header", "domain"):
            if not data.get(key):
                print(
                    f"Auth creds file missing required field: {key}",
                    file=sys.stderr,
                )
                raise SystemExit(2)
        return cls(data["xsrf_token"], data["cookie_header"], data["domain"])


def load_rest_creds() -> tuple[str, str]:
    """Load REST api-token + domain from the environment / .env.

    Mirrors tools/migrate_pp_cases_phase_a.py:load_rest_creds so credential
    resolution works the same way everywhere.
    """
    token = os.environ.get("QATOUCH_API_TOKEN") or os.environ.get("QATOUCH_API_KEY")
    domain = os.environ.get("QATOUCH_DOMAIN")
    if not token or not domain:
        print(
            "Missing QA Touch REST credentials.\n"
            "Set both of these in your .env at the repo root (or export them):\n"
            "    QATOUCH_API_TOKEN=<your REST api-token>\n"
            "    QATOUCH_DOMAIN=soterixsystems\n"
            "See .env.template for the full list.",
            file=sys.stderr,
        )
        raise SystemExit(2)
    return token, domain


# ----------------------------------------------------------------------------
# HTTP plumbing
# ----------------------------------------------------------------------------
def _internal_headers(creds: AuthCreds) -> dict[str, str]:
    base = f"https://{creds.domain}"
    return {
        "Content-Type": "application/json;charset=UTF-8",
        "Accept": "application/json",
        "X-XSRF-TOKEN": creds.xsrf_token,
        "Cookie": creds.cookie_header,
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        ),
        "Origin": base,
        "Referer": f"{base}/v2",
    }


def _http_request(
    method: str,
    url: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
    timeout: int = 30,
) -> tuple[int, bytes]:
    """Plain urllib request that swallows HTTPError (we want the body for 4xx/5xx)."""
    req = urllib.request.Request(url, method=method, data=body, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        body_bytes = b""
        try:
            body_bytes = e.read()
        except Exception:
            pass
        return e.code, body_bytes
    except urllib.error.URLError as e:
        return 0, f"URLError: {getattr(e, 'reason', e)}".encode()


def rest_get(
    path: str, token: str, domain: str, timeout: int = 30
) -> tuple[int, dict | str]:
    """REST GET via api-token + domain headers. Returns (status, parsed_or_text)."""
    url = f"{REST_BASE}{path}"
    headers = {
        "api-token": token,
        "domain": domain,
        "Accept": "application/json",
    }
    status, raw = _http_request("GET", url, headers=headers, timeout=timeout)
    text = raw.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, text


def internal_post(
    creds: AuthCreds, path: str, json_body: dict[str, Any]
) -> tuple[int, dict | str]:
    """POST to QA Touch internal endpoint via XSRF + Cookie auth."""
    url = f"https://{creds.domain}{path}"
    body = json.dumps(json_body).encode("utf-8")
    status, raw = _http_request(
        "POST", url, headers=_internal_headers(creds), body=body
    )
    text = raw.decode("utf-8", errors="replace")
    try:
        return status, json.loads(text)
    except json.JSONDecodeError:
        return status, text


# ----------------------------------------------------------------------------
# Pre-flight verification
# ----------------------------------------------------------------------------
def verify_internal_auth(creds: AuthCreds) -> tuple[bool, str]:
    """GET /v2 with the lightweight HTML-accept shape used by the helper.

    Mirrors run_partner_admin_backfill.verify_auth - 401/403 are the canonical
    stale-auth signal; other non-2xx (except 404) is a soft warning.
    """
    url = f"https://{creds.domain}/v2"
    common = _internal_headers(creds)
    headers = {
        "Cookie": common["Cookie"],
        "X-XSRF-TOKEN": common["X-XSRF-TOKEN"],
        "User-Agent": common["User-Agent"],
        "Accept": "text/html,application/json",
    }
    status, raw = _http_request("GET", url, headers=headers)
    if status in (401, 403):
        return False, f"verify GET /v2 returned HTTP {status} (stale auth)"
    if status == 0:
        return False, raw.decode("utf-8", errors="replace")
    if status >= 400 and status != 404:
        return True, (
            f"verify GET /v2 returned HTTP {status} - non-fatal, "
            "cookies may still work for /v1/case/* endpoints"
        )
    return True, f"verify GET /v2 returned HTTP {status}"


def verify_rest_auth(
    token: str, domain: str, project_key: str
) -> tuple[bool, str]:
    """Hit page 1 of getAllTestCases to confirm REST creds work."""
    status, body = rest_get(
        f"/api/v1/getAllTestCases/{project_key}?page=1", token, domain
    )
    if status in (401, 403):
        return False, (
            f"REST verify GET getAllTestCases/{project_key} returned HTTP "
            f"{status} (bad api-token / domain)"
        )
    if status == 404:
        return False, (
            f"REST verify GET getAllTestCases/{project_key} returned 404 "
            "(project key not found?)"
        )
    if status != 200 or not isinstance(body, dict):
        return False, (
            f"REST verify GET getAllTestCases/{project_key} returned HTTP "
            f"{status} body={str(body)[:200]}"
        )
    return True, f"REST verify OK (HTTP 200, project={project_key})"


# ----------------------------------------------------------------------------
# Case listing - paginate REST getAllTestCases
# ----------------------------------------------------------------------------
def iter_cases(
    project_key: str,
    token: str,
    domain: str,
    rate_ms: int,
    module_filter: set[str] | None,
) -> list[dict]:
    """Paginate /api/v1/getAllTestCases/{project_key}?page=N. 50 per page.

    Stops when a page returns an empty data array. Applies module_filter if
    set. Each case dict is normalized to:
        {case_key, case_code, case_title, module_key, module_name}
    """
    all_cases: list[dict] = []
    page = 1
    while True:
        status, body = rest_get(
            f"/api/v1/getAllTestCases/{project_key}?page={page}", token, domain
        )
        if status == 429:
            print(
                f"  REST 429 on listing page {page} - sleeping 10s then retrying once"
            )
            time.sleep(10)
            status, body = rest_get(
                f"/api/v1/getAllTestCases/{project_key}?page={page}", token, domain
            )
        if status != 200 or not isinstance(body, dict):
            print(
                f"  WARN: listing page {page} failed (HTTP {status}); "
                "stopping pagination",
                file=sys.stderr,
            )
            break
        batch = body.get("data") or []
        if not batch:
            break
        for c in batch:
            mk = c.get("module_key") or c.get("section_key") or ""
            if module_filter is not None and mk not in module_filter:
                continue
            all_cases.append({
                "case_key": c.get("case_key") or c.get("caseKey") or "",
                "case_code": c.get("case_code") or c.get("caseCode") or "",
                "case_title": c.get("case_title") or c.get("caseTitle") or "",
                "module_key": mk,
                "module_name": c.get("module") or c.get("moduleName") or "",
            })
        page += 1
        if rate_ms > 0:
            time.sleep(rate_ms / 1000.0)
    return all_cases


# ----------------------------------------------------------------------------
# Classification: per recon signature
# ----------------------------------------------------------------------------
def html_to_text(html: str | None) -> str:
    return re.sub(r"<[^>]+>", "\n", html or "").replace("\xa0", " ")


def classify_case_steps(case_steps: list[dict]) -> tuple[str, int, int, str, str]:
    """Return (classification, step_count, marker_count, step_excerpt, expected_excerpt).

    classification in {"merged", "split", "empty", "single"}.
    """
    step_count = len(case_steps)

    if step_count == 0:
        return "empty", 0, 0, "", ""

    if step_count > 1:
        # Already split - peek at first row for the excerpt.
        first = case_steps[0]
        body = first.get("step") or first.get("step_description") or ""
        expected = first.get("expected_result") or first.get("expectedResult") or ""
        return (
            "split",
            step_count,
            0,
            html_to_text(body)[:200].strip(),
            html_to_text(expected)[:100].strip(),
        )

    # Exactly one row - count "Step N:" markers in the body.
    only = case_steps[0]
    body = only.get("step") or only.get("step_description") or ""
    expected = only.get("expected_result") or only.get("expectedResult") or ""
    text = html_to_text(body)
    marker_count = len(STEP_PREFIX_RE.findall(text))
    classification = "merged" if marker_count >= MERGED_THRESHOLD else "single"
    return (
        classification,
        1,
        marker_count,
        text[:200].strip(),
        html_to_text(expected)[:100].strip(),
    )


def fetch_case_steps(
    creds: AuthCreds, project_key: str, case_key: str
) -> tuple[int, list[dict] | None, str | None]:
    """POST /v1/case/edit/p/{pk}/cid/{ck} -> (status, caseStep_list, error_msg)."""
    status, body = internal_post(
        creds, f"/v1/case/edit/p/{project_key}/cid/{case_key}", {}
    )
    if status == 429:
        print(
            f"  internal 429 on /v1/case/edit cid={case_key} - sleeping 10s then retrying once"
        )
        time.sleep(10)
        status, body = internal_post(
            creds, f"/v1/case/edit/p/{project_key}/cid/{case_key}", {}
        )
    if status in (401, 403):
        return status, None, f"stale internal auth (HTTP {status})"
    if status != 200 or not isinstance(body, dict):
        return status, None, f"unexpected response (HTTP {status})"
    data = body.get("data") if isinstance(body.get("data"), dict) else body
    if not isinstance(data, dict):
        return status, None, "response body missing 'data' dict"
    steps = data.get("caseStep") or data.get("case_steps") or []
    if not isinstance(steps, list):
        steps = []
    return status, steps, None


# ----------------------------------------------------------------------------
# Manifest writer - atomic rewrite per record
# ----------------------------------------------------------------------------
class Manifest:
    def __init__(self, path: Path, header: dict):
        self.path = path
        self.header = header
        self.records: list[dict] = []
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._flush()

    def append(self, record: dict) -> None:
        self.records.append(record)
        self._flush()

    def update_header(self, **kv: Any) -> None:
        self.header.update(kv)
        self._flush()

    def _flush(self) -> None:
        payload = {"header": self.header, "records": self.records}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.path)


# ----------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument(
        "--project-key",
        default="70l1",
        help="QA Touch project key (default: 70l1).",
    )
    ap.add_argument(
        "--module-key",
        default="",
        help=(
            "Comma-separated module_key filter. Only cases whose module_key "
            "is in this set are audited. Leave empty to scan ALL modules."
        ),
    )
    ap.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Audit at most N cases after --resume-from (0 = all).",
    )
    ap.add_argument(
        "--resume-from",
        type=int,
        default=0,
        help="Skip the first N cases (1-based). Use after a mid-run abort.",
    )
    ap.add_argument(
        "--creds-file",
        type=Path,
        default=DEFAULT_CREDS_FILE,
        help=f"Internal-auth creds JSON (default: {DEFAULT_CREDS_FILE}).",
    )
    ap.add_argument(
        "--rate-ms",
        type=int,
        default=800,
        help=(
            "Inter-call delay in milliseconds (default: 800, ~1.25 req/s). "
            "Reads are cheaper than writes so this is lighter than the backfill default."
        ),
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=None,
        help=(
            "Manifest output path (default: "
            "logs/merged_steps_manifest_{project}_{YYYYMMDD-HHMMSS}.json)"
        ),
    )
    ap.add_argument(
        "--skip-verify",
        action="store_true",
        help="Skip pre-flight auth checks (not recommended).",
    )
    args = ap.parse_args()

    project_key = args.project_key
    module_filter: set[str] | None = None
    if args.module_key.strip():
        module_filter = {
            m.strip() for m in args.module_key.split(",") if m.strip()
        }

    # --- Pre-flight: load both auth shapes
    rest_token, rest_domain = load_rest_creds()
    creds = AuthCreds.load(args.creds_file)

    print(f"  Project key:    {project_key}")
    print(f"  Module filter:  {sorted(module_filter) if module_filter else 'ALL'}")
    print(f"  REST domain:    {rest_domain}")
    print(f"  Internal domain:{creds.domain}")
    print(f"  Creds file:     {args.creds_file}")
    print(f"  Rate ms:        {args.rate_ms}")
    print(f"  Resume from:    {args.resume_from}")
    print(f"  Limit:          {args.limit if args.limit > 0 else 'all'}")

    if not args.skip_verify:
        ok, msg = verify_internal_auth(creds)
        if not ok:
            print(f"  Pre-flight FAILED (internal): {msg}", file=sys.stderr)
            print(file=sys.stderr)
            print(REFRESH_INSTRUCTIONS, file=sys.stderr)
            return 2
        print(f"  Pre-flight OK (internal): {msg}")

        ok, msg = verify_rest_auth(rest_token, rest_domain, project_key)
        if not ok:
            print(f"  Pre-flight FAILED (REST):     {msg}", file=sys.stderr)
            print(
                "  Check QATOUCH_API_TOKEN + QATOUCH_DOMAIN in your .env.",
                file=sys.stderr,
            )
            return 2
        print(f"  Pre-flight OK (REST):     {msg}")

    # --- Build the case list (paginate REST)
    print()
    print("  Listing cases via REST getAllTestCases (50/page)...")
    cases = iter_cases(
        project_key, rest_token, rest_domain, args.rate_ms, module_filter
    )
    if not cases:
        print(
            "  No cases returned. Check --project-key / --module-key filters.",
            file=sys.stderr,
        )
        return 2
    print(f"  Found {len(cases)} cases matching filters.")

    # --- Slice via resume-from / limit
    start_idx = max(0, args.resume_from)
    sliced = cases[start_idx:]
    if args.limit > 0:
        sliced = sliced[: args.limit]
    if not sliced:
        print("  Nothing to process after applying --resume-from / --limit.")
        return 0

    # --- Open manifest
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    if args.out:
        out_path = args.out
    else:
        out_path = DEFAULT_LOG_DIR / f"merged_steps_manifest_{project_key}_{ts}.json"

    summary: dict[str, Any] = {
        "total_cases":  len(cases),
        "to_process":   len(sliced),
        "merged":       0,
        "split":        0,
        "empty":        0,
        "single":       0,
        "error":        0,
        "skipped":      start_idx,
        "by_module":    {},   # module_key -> per-classification counts
    }
    header = {
        "started_at":   datetime.now().isoformat(timespec="seconds"),
        "project_key":  project_key,
        "module_keys":  sorted(module_filter) if module_filter else None,
        "creds_file":   str(args.creds_file),
        "rate_ms":      args.rate_ms,
        "resume_from":  args.resume_from,
        "limit":        args.limit,
        "skip_verify":  args.skip_verify,
        "summary":      summary,
    }
    manifest = Manifest(out_path, header)
    print(f"  Manifest:       {out_path}")
    print()

    def bump_module(mk: str, mname: str, label: str) -> None:
        bucket = summary["by_module"].setdefault(
            mk, {"module_name": mname, "merged": 0, "split": 0,
                 "empty": 0, "single": 0, "error": 0}
        )
        bucket[label] = bucket.get(label, 0) + 1

    n_total_full = len(cases)
    n_total_slice = len(sliced)
    interrupted = False
    last_logged_i = start_idx

    try:
        for offset, case in enumerate(sliced):
            i = start_idx + offset + 1  # 1-based into full case list
            case_key = case["case_key"]
            case_code = case["case_code"]
            case_title = case["case_title"]
            module_key = case["module_key"]
            module_name = case["module_name"]

            rec: dict[str, Any] = {
                "i":                       i,
                "project_key":             project_key,
                "module_key":              module_key,
                "module_name":             module_name,
                "case_key":                case_key,
                "case_code":               case_code,
                "case_title":              case_title,
                "classification":          None,
                "step_count":              0,
                "parsed_step_markers":     0,
                "step_excerpt":            "",
                "expected_result_excerpt": "",
                "http_status":             None,
                "error":                   None,
            }

            if not case_key:
                rec["classification"] = "error"
                rec["error"] = "case missing case_key in listing"
                summary["error"] += 1
                bump_module(module_key, module_name, "error")
                manifest.append(rec)
                last_logged_i = i
                print(
                    f"  [{i}/{n_total_full}] {module_name}: "
                    f"{(case_title or '?')[:50]} -> ERROR (no case_key)"
                )
                time.sleep(args.rate_ms / 1000.0)
                continue

            status, steps, err = fetch_case_steps(creds, project_key, case_key)
            rec["http_status"] = status

            if status in (401, 403):
                # Stale internal auth - abort cleanly with a resume hint.
                print(
                    f"  [{i}/{n_total_full}] {module_name}: "
                    f"HTTP {status} - internal auth stale. Aborting.",
                    file=sys.stderr,
                )
                print(file=sys.stderr)
                print(REFRESH_INSTRUCTIONS, file=sys.stderr)
                print(
                    f"  After refresh, resume with: --resume-from {last_logged_i}",
                    file=sys.stderr,
                )
                rec["classification"] = "error"
                rec["error"] = err
                summary["error"] += 1
                bump_module(module_key, module_name, "error")
                manifest.append(rec)
                manifest.update_header(
                    ended_at=datetime.now().isoformat(timespec="seconds"),
                    interrupted=True,
                    abort_reason=f"stale internal auth (HTTP {status})",
                    summary=summary,
                )
                return 2

            if err is not None or steps is None:
                rec["classification"] = "error"
                rec["error"] = err or "no steps returned"
                summary["error"] += 1
                bump_module(module_key, module_name, "error")
                manifest.append(rec)
                last_logged_i = i
                print(
                    f"  [{i}/{n_total_full}] {module_name}: "
                    f"{(case_title or case_key)[:50]} -> ERROR ({err})"
                )
                time.sleep(args.rate_ms / 1000.0)
                continue

            cls, step_count, marker_count, step_excerpt, expected_excerpt = (
                classify_case_steps(steps)
            )
            rec["classification"] = cls
            rec["step_count"] = step_count
            rec["parsed_step_markers"] = marker_count
            rec["step_excerpt"] = step_excerpt
            rec["expected_result_excerpt"] = expected_excerpt

            summary[cls] = summary.get(cls, 0) + 1
            bump_module(module_key, module_name, cls)
            manifest.append(rec)
            last_logged_i = i

            print(
                f"  [{i}/{n_total_full}] {module_name}: "
                f"{(case_title or case_key)[:50]} -> "
                f"{cls.upper()} (rows={step_count}, markers={marker_count})"
            )

            # Periodic rollup every 50 audited cases.
            if (offset + 1) % 50 == 0:
                print(
                    f"  ---- progress: [{i}/{n_total_full}] "
                    f"merged={summary['merged']} split={summary['split']} "
                    f"single={summary['single']} empty={summary['empty']} "
                    f"error={summary['error']}"
                )

            time.sleep(args.rate_ms / 1000.0)
    except KeyboardInterrupt:
        interrupted = True
        print()
        print(f"  Interrupted by user. Partial manifest preserved at: {out_path}")
        print(f"  Resume with: --resume-from {last_logged_i}")

    manifest.update_header(
        ended_at=datetime.now().isoformat(timespec="seconds"),
        interrupted=interrupted,
        summary=summary,
    )

    # --- Final report
    print()
    print("=" * 64)
    print(f"  MERGED-STEPS AUDIT SUMMARY (project={project_key})")
    print("=" * 64)
    print(f"  Total cases found:     {summary['total_cases']}")
    print(f"  Processed:             {summary['to_process']}")
    print(f"  Skipped (resume-from): {summary['skipped']}")
    print(f"  Merged:                {summary['merged']}")
    print(f"  Split (already done):  {summary['split']}")
    print(f"  Single (legitimate):   {summary['single']}")
    print(f"  Empty (exploratory):   {summary['empty']}")
    print(f"  Errors:                {summary['error']}")
    print(f"  Manifest:              {out_path}")
    print("=" * 64)
    if summary["by_module"]:
        print()
        print("  Per-module breakdown:")
        for mk in sorted(
            summary["by_module"],
            key=lambda k: -summary["by_module"][k].get("merged", 0),
        ):
            b = summary["by_module"][mk]
            print(
                f"    {mk}  {b['module_name'][:40]:<40}  "
                f"merged={b['merged']:3d}  split={b['split']:3d}  "
                f"single={b['single']:3d}  empty={b['empty']:3d}  "
                f"error={b['error']:3d}"
            )

    return 1 if interrupted else 0


if __name__ == "__main__":
    sys.exit(main())
