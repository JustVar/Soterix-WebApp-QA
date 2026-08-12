"""Check test code against the house conventions (docs/CONVENTIONS.md).

Ruff checks Python style. This tool checks the rules ruff cannot see:
uncommented sleeps, in-test QA Touch markers, absolute count oracles,
icon locator guesses, hardcoded tenant names, except blocks that
swallow failures into prints, test bodies with no oracle, and
.first/.last picks on union selectors.

Every rule here started as a defect found in review; when a review
finds a new class, it gets a detector so the class cannot recur.

By default the tool checks only the lines ADDED since HEAD, so standing
debt in files you did not touch never blocks you. Untracked test files
are scanned in full.

Usage:
  python tools/convention_check.py              # added lines vs HEAD
  python tools/convention_check.py --base main~5
  python tools/convention_check.py --all        # whole repo: standing debt

Exit codes: 0 = clean (MEDIUM findings only warn), 1 = HIGH findings,
2 = tool error.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# Only test code is checked. tools/ and plugins/ have their own rules
# (see pyproject.toml per-file ignores).
INCLUDE_PREFIXES = ("tests/",)
EXCLUDE_PREFIXES = ("tests/legacy/",)

SLEEP_RE = re.compile(r"(?:wait_for_timeout|time\.sleep)\s*\(")
QATOUCH_RE = re.compile(r"@pytest\.mark\.qatouch")
ABS_COUNT_RE = re.compile(r"\.count\(\)\s*(?:>\s*0|>=\s*[01])\b")
IMG_SRC_RE = re.compile(r"img\[src\*?=")
TENANT_NAME_RE = re.compile(r"[\"'](?:Driver Site|Hanwha)")
# locator("a, b").first/.last - .last can resolve to a hidden copy in
# a different container (the video-canvas union lesson)
UNION_PICK_RE = re.compile(
    r"locator\(\s*[\"'][^\"']*,[^\"']*[\"']\s*\)\s*\.\s*(?:first|last)\b"
)
EXCEPT_RE = re.compile(r"^\s*except\b.*:")
TEST_DEF_RE = re.compile(r"^\s*def (test_\w+)")
# Anything in a test body that can fail the test
ORACLE_RE = re.compile(
    r"\bassert\b|\bexpect\s*\(|pytest\.(?:fail|raises|xfail)|"
    r"\.wait_for\s*\(|wait_for_function\s*\("
)


def line_is_excused(lines: list[str], idx: int) -> bool:
    """A sleep is excused by a why-comment: inline, or on the line above."""
    line = lines[idx]
    code_start = SLEEP_RE.search(line)
    if code_start and "#" in line[code_start.end():]:
        return True
    if idx > 0:
        return lines[idx - 1].strip().startswith("#")
    return False


def check_line(path: str, lines: list[str], idx: int) -> list[dict]:
    """Return findings for one line (0-based idx) of a file."""
    line = lines[idx]
    stripped = line.strip()
    if stripped.startswith("#"):
        return []
    findings = []

    if SLEEP_RE.search(line) and not line_is_excused(lines, idx):
        findings.append({
            "sev": "HIGH", "rule": "uncommented-sleep",
            "msg": "fixed sleep with no why-comment. Wait for the DOM "
                   "signal instead, or comment why no signal exists "
                   "(CONVENTIONS.md > Waits).",
        })
    if QATOUCH_RE.search(line):
        findings.append({
            "sev": "HIGH", "rule": "qatouch-marker-in-test",
            "msg": "QA Touch mappings belong in "
                   "config/qatouch_case_mapping.json, never in a test file.",
        })
    if ABS_COUNT_RE.search(line):
        findings.append({
            "sev": "MEDIUM", "rule": "absolute-count-oracle",
            "msg": "count() > 0 passes on pre-existing elements. Compare "
                   "against a baseline taken before the action, or use "
                   "expect(...).to_have_count().",
        })
    if IMG_SRC_RE.search(line):
        findings.append({
            "sev": "MEDIUM", "rule": "img-src-locator",
            "msg": "check for a data-testid before an img[src] guess. MUI "
                   "icons ship svg[data-testid='...Icon'] today.",
        })
    if TENANT_NAME_RE.search(line):
        findings.append({
            "sev": "MEDIUM", "rule": "hardcoded-tenant-name",
            "msg": "the shared tenant renames things. Use test_site_name / "
                   "test_camera_name from config/env/ instead.",
        })
    if UNION_PICK_RE.search(line):
        findings.append({
            "sev": "MEDIUM", "rule": "union-first-last",
            "msg": ".first/.last on a union selector can resolve to a "
                   "hidden copy of the OTHER selector. Split the union or "
                   "scope it to a container.",
        })

    for f in findings:
        f["path"], f["line"], f["text"] = path, idx + 1, stripped
    return findings


def _block_range(lines: list[str], idx: int) -> range:
    """Line indexes of the indented block that starts after line idx."""
    indent = len(lines[idx]) - len(lines[idx].lstrip())
    end = idx + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and (len(line) - len(line.lstrip())) <= indent:
            break
        end += 1
    return range(idx + 1, end)


def check_except_blocks(path: str, lines: list[str]) -> list[dict]:
    """Except blocks whose only content is print/pass/continue.

    A swallowed failure reads as a pass - the pattern behind every
    vacuous-green suite this repo has repaired. A why-comment on the
    except line (or the line above) excuses a deliberate best-effort
    block, cleanup paths mostly.
    """
    findings = []
    for idx, line in enumerate(lines):
        if not EXCEPT_RE.match(line):
            continue
        if "#" in line or (idx > 0 and lines[idx - 1].strip().startswith("#")):
            continue
        body = [lines[i].strip() for i in _block_range(lines, idx)]
        code = [s for s in body if s and not s.startswith("#")]
        if code and all(
            s.startswith(("print(", "pass", "continue")) for s in code
        ):
            findings.append({
                "sev": "MEDIUM", "rule": "except-swallow",
                "path": path, "line": idx + 1, "text": line.strip(),
                "msg": "except block only prints or passes: a real failure "
                       "reads as a pass. Re-raise, pytest.fail, or comment "
                       "why best-effort is correct here.",
            })
    return findings


def check_no_oracle_tests(path: str, lines: list[str]) -> list[dict]:
    """Test functions whose body can never fail.

    A body with no assert, no expect, no pytest.fail/raises, and no
    raising wait is green no matter what the app does. A body line
    mentioning 'oracle' excuses a deliberate delegation to a raising
    page-object call - the comment names where the failure comes from.
    """
    findings = []
    for idx, line in enumerate(lines):
        m = TEST_DEF_RE.match(line)
        if not m:
            continue
        body = [lines[i] for i in _block_range(lines, idx)]
        if any("oracle" in b.lower() for b in body):
            continue
        if not any(ORACLE_RE.search(b) for b in body):
            findings.append({
                "sev": "MEDIUM", "rule": "no-oracle-test",
                "path": path, "line": idx + 1, "text": line.strip(),
                "msg": f"{m.group(1)} has no assert/expect and no raising "
                       "wait in its body: it cannot fail. If the oracle "
                       "lives in a raising page-object call, comment which "
                       "call carries it.",
            })
    return findings


def wanted(path: str) -> bool:
    if not path.endswith(".py"):
        return False
    if not path.startswith(INCLUDE_PREFIXES):
        return False
    return not path.startswith(EXCLUDE_PREFIXES)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False, cwd=REPO
    )
    if result.returncode != 0:
        print(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        sys.exit(2)
    return result.stdout


def added_lines_since(base: str) -> dict[str, list[int]]:
    """Map path -> 1-based line numbers added since base (plus untracked)."""
    out = git("diff", "--unified=0", "--no-color", base, "--", "tests")
    added: dict[str, list[int]] = {}
    path = None
    new_line = 0
    for raw in out.splitlines():
        if raw.startswith("+++ b/"):
            path = raw[6:]
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", raw)
            new_line = int(m.group(1))
        elif raw.startswith("+") and not raw.startswith("+++"):
            if path and wanted(path):
                added.setdefault(path, []).append(new_line)
            new_line += 1

    untracked = git("ls-files", "--others", "--exclude-standard", "tests")
    for path in untracked.splitlines():
        path = path.strip()
        if path and wanted(path):
            n_lines = len(read_lines(path))
            added[path] = list(range(1, n_lines + 1))
    return added


def read_lines(path: str) -> list[str]:
    try:
        return (REPO / path).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="HEAD",
                        help="git ref to diff against (default HEAD)")
    parser.add_argument("--all", action="store_true",
                        help="scan every test file in full (standing debt)")
    args = parser.parse_args()

    findings: list[dict] = []
    if args.all:
        tracked = git("ls-files", "tests").splitlines()
        for path in tracked:
            if not wanted(path):
                continue
            lines = read_lines(path)
            for idx in range(len(lines)):
                findings.extend(check_line(path, lines, idx))
            findings.extend(check_except_blocks(path, lines))
            findings.extend(check_no_oracle_tests(path, lines))
    else:
        for path, line_nums in added_lines_since(args.base).items():
            lines = read_lines(path)
            added = set(line_nums)
            for n in line_nums:
                if n - 1 < len(lines):
                    findings.extend(check_line(path, lines, n - 1))
            # Block rules anchor on the except/def line; only blocks
            # the diff touched are reported
            for f in check_except_blocks(path, lines):
                if f["line"] in added:
                    findings.append(f)
            for f in check_no_oracle_tests(path, lines):
                block = _block_range(lines, f["line"] - 1)
                if f["line"] in added or any(
                    (i + 1) in added for i in block
                ):
                    findings.append(f)

    high = [f for f in findings if f["sev"] == "HIGH"]
    medium = [f for f in findings if f["sev"] == "MEDIUM"]
    for f in sorted(findings, key=lambda f: (f["sev"] != "HIGH", f["path"], f["line"])):
        print(f"[{f['sev']}] {f['path']}:{f['line']}  {f['rule']}")
        print(f"    {f['text'][:100]}")
        print(f"    {f['msg']}")

    scope = "whole repo" if args.all else f"lines added since {args.base}"
    print(f"\n{len(high)} HIGH, {len(medium)} MEDIUM ({scope}).")
    if high:
        print("HIGH findings block: fix them or comment the why.")
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
