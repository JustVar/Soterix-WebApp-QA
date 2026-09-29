"""Check test code against the house conventions (docs/CONVENTIONS.md).

Ruff checks Python style. This tool checks the rules ruff cannot see:
uncommented sleeps, in-test QA Touch markers, absolute count oracles,
icon locator guesses, hardcoded tenant names, except blocks that
swallow failures into prints, skips raised from an except handler,
skip reasons that guess at the app, test bodies with no oracle, early
test-body returns (vacuous passes), .first/.last picks on union
selectors, new tests that land without a title, without a
"Steps:" block, or without a QA Touch mapping row, Jira ticket keys
anywhere in code, comments, or docstrings, except handlers with no
why-comment that neither re-raise nor fail, DOM waits of a minute or
more, .first on a text lookup, and test bodies whose only oracle is
that something is visible.

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
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MAPPING_PATH = REPO / "config" / "qatouch_case_mapping.json"

# Only test code is checked. tools/ and plugins/ have their own rules
# (see pyproject.toml per-file ignores).
INCLUDE_PREFIXES = ("tests/",)
EXCLUDE_PREFIXES = ()
# The tests QA Touch cases are generated for and mapped to: the product
# roots (config/products.py), never the tooling and plugin pins.
sys.path.insert(0, str(REPO))
from config.products import PRODUCT_ROOTS, product_root

PRODUCT_PREFIXES = tuple(PRODUCT_ROOTS)

SLEEP_RE = re.compile(r"(?:wait_for_timeout|time\.sleep)\s*\(")
TICKET_RE = re.compile(r"\bNC-\d+\b")
QATOUCH_RE = re.compile(r"@pytest\.mark\.qatouch")
# The flaky mark is pytest-rerunfailures' own: it retries on any failure,
# once even bare. A hidden retry no run page ever sees. The label is
# `intermittent`.
FLAKY_MARK_RE = re.compile(r"\bmark\.flaky\b")   # @pytest.mark.flaky, pytestmark =, marks=, an alias
ABS_COUNT_RE = re.compile(r"\.count\(\)\s*(?:>\s*0|>=\s*[01])\b")
IMG_SRC_RE = re.compile(r"img\[src\*?=")

# A site or camera name written into a test couples the test to one
# server. The rule is built from the active env file's names, so it fires
# on the server the team has, whatever its names are.


def tenant_name_pattern(names: list[str | None] | None = None) -> re.Pattern[str] | None:
    """A pattern for a quoted site or camera name, or None when no name is
    known. Without `names` the active env file's test_site_name and
    test_camera_name are read (config/env/<ENV>.py). A name is escaped, so
    one with regex characters matches itself."""
    if names is None:
        try:
            from config.base_config import config
        except Exception:
            return None   # no env file loads: the rule is off, the other rules still run
        names = [config.get("test_site_name"), config.get("test_camera_name")]
    kept = [n for n in names if n]
    if not kept:
        return None
    return re.compile(r"[\"'](?:" + "|".join(re.escape(n) for n in kept) + ")")


_tenant_cache: list[re.Pattern[str] | None] = []


def _active_tenant_pattern() -> re.Pattern[str] | None:
    if not _tenant_cache:
        _tenant_cache.append(tenant_name_pattern())
    return _tenant_cache[0]


# locator("a, b").first/.last - .last can resolve to a hidden copy in
# a different container (the video-canvas union lesson)
UNION_PICK_RE = re.compile(
    r"locator\(\s*[\"'][^\"']*,[^\"']*[\"']\s*\)\s*\.\s*(?:first|last)\b"
)
EXCEPT_RE = re.compile(r"^\s*except\b.*:")
SKIP_RE = re.compile(r"\bpytest\.skip\s*\(")
# A skip reason that hedges about the app records a guess, not a
# measurement: the run then reports "not supported" for a locator
# that simply moved. Measure it with tools/explore_app.py and say
# what IS there.
SPECULATIVE_SKIP_RE = re.compile(
    r"\b(?:may|might|maybe|possibly|probably|perhaps|seems|likely)\b"
    r"|\bnot supported\b|\bwork differently\b",
    re.IGNORECASE,
)
TEST_DEF_RE = re.compile(r"^\s*def (test_\w+)")
CLASS_DEF_RE = re.compile(r"^(\s*)class (\w+)")
DOCSTRING_OPEN_RE = re.compile(r"""^[rRuUbB]{0,2}("{3}|'{3}|"|')""")
# The block tools/qatouch_cases_from_tests.py reads the case from
STEPS_HEADER_RE = re.compile(r"^\s*Steps:\s*$", re.MULTILINE)
PARAM_SUFFIX_RE = re.compile(r"\[.*\]$")
# Anything in a test body that can fail the test. expect.soft counts:
# pytest-playwright collects soft failures per test and raises them
# in an ExceptionGroup at test end.
ORACLE_RE = re.compile(
    r"\bassert\b|\bexpect\s*\(|\bexpect\.soft\s*\(|"
    r"pytest\.(?:fail|raises|xfail)|"
    r"\.wait_for\s*\(|wait_for_(?:function|url|selector)\s*\(|"
    # each of these raises when the thing does not happen: a download, a response, a popup,
    # a mock that was not called. wait_for_timeout is a sleep, and is not here.
    r"\bexpect_(?:download|response|request|popup|event|navigation|file_chooser|console_message)\s*\(|"
    r"\.assert_(?:called|any_call|has_calls|not_called|awaited)\w*\s*\("
)
# An oracle that says what CHANGED, not just that something is on screen:
# a comparison, a text/count/url/attribute expectation, a negative
# expectation, a state, or an explicit failure. Everything ORACLE_RE
# matches that this does not is presence only (visible, attached, a wait).
STRONG_ORACLE_RE = re.compile(
    r"\bassert\b[^#]*(?:==|!=|<=|>=|<|>|\bin\b|\bnot\b|\bis\b)|"
    r"to_have_\w+|to_contain_text|not_to_\w+|"
    r"to_be_(?:checked|disabled|enabled|editable|empty|focused|hidden|in_viewport)|"
    r"pytest\.(?:fail|raises)|wait_for\s*\(\s*state\s*=\s*[\"'](?:hidden|detached)"
)
# Two ways a presence check read as strong until 09/18/2026 (25 product tests):
# the message of an assert holds "not" or "in" ('"Create List button not
# found"'), and `count() > 0` holds a comparison. The message is cut off
# before the line is judged, and an absolute count alone is presence.
ASSERT_MESSAGE_RE = re.compile(r""",\s*\(?\s*[fFrR]?["'].*$""")
ABSOLUTE_SIZE_RE = re.compile(
    r"\.count\(\)\s*(?:>\s*0|>=\s*1|!=\s*0)|\blen\([^)]*\)\s*(?:>\s*0|>=\s*1|!=\s*0)")


def is_strong_oracle(line: str) -> bool:
    """True when the line says what changed: see STRONG_ORACLE_RE, minus the 2 leaks above."""
    code = ASSERT_MESSAGE_RE.sub("", line) if re.search(r"\bassert\b", line) else line
    if ABSOLUTE_SIZE_RE.search(code) and not re.search(r"\band\b|\bor\b", code):
        return False
    return bool(STRONG_ORACLE_RE.search(code))


# A DOM wait of a minute or more: 60000-99999 or any six-digit timeout.
LONG_WAIT_RE = re.compile(
    r"\.(?:wait_for|to_be_visible|to_be_attached|to_be_hidden|wait_for_selector|"
    r"wait_for_url|wait_for_load_state|wait_for_function)\s*\([^)]*"
    r"timeout\s*=\s*(?:[6-9]\d{4}|\d{6,})\b"
)
# .first on a text lookup: identity by substring.
TEXT_FIRST_RE = re.compile(r"(?:get_by_text\s*\(|has_text\s*=)[^\n]*\.first\b")


def line_is_excused(lines: list[str], idx: int, pattern=SLEEP_RE) -> bool:
    """A finding is excused by a why-comment: inline, or on the line above.

    Shared by the sleep rule and the img-src rule: both mark a thing that
    is sometimes the only honest option, and the comment is the proof
    that someone checked.
    """
    line = lines[idx]
    code_start = pattern.search(line)
    if code_start and "#" in line[code_start.end():]:
        return True
    if idx > 0:
        return lines[idx - 1].strip().startswith("#")
    return False


def inside_triple_quote(lines: list[str], idx: int) -> bool:
    """Whether line idx sits inside a multi-line string (docstring prose or
    a JS block passed to evaluate): a locator pattern quoted there is not a
    locator, and a why-comment cannot be placed inside it."""
    opened = 0
    for line in lines[:idx]:
        opened += line.count('''"""''') + line.count("'''")
    return opened % 2 == 1


def test_has_title(lines: list[str], idx: int) -> bool:
    """Whether the def at idx is followed by a docstring (the signature may
    span lines; the first statement after the closing ':' must open a string)."""
    j = idx
    while j < len(lines) and not lines[j].rstrip().endswith(':'):
        j += 1
    j += 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines):
        return False
    first = lines[j].strip()
    return first.startswith(('"', "'", 'r"', "r'"))


def test_docstring(lines: list[str], idx: int) -> str:
    """The docstring of the def at idx, "" when it has none."""
    j = idx
    while j < len(lines) and not lines[j].rstrip().endswith(':'):
        j += 1
    j += 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines):
        return ""
    first = lines[j].strip()
    m = DOCSTRING_OPEN_RE.match(first)
    if not m:
        return ""
    quote = m.group(1)
    body = first[m.end():]
    if quote in body:
        return body[:body.index(quote)]
    if len(quote) == 1:
        return body
    out = [body]
    for k in range(j + 1, len(lines)):
        if quote in lines[k]:
            out.append(lines[k][:lines[k].index(quote)])
            break
        out.append(lines[k])
    return "\n".join(out)


def test_nodeid(path: str, lines: list[str], idx: int) -> str:
    """file::Class::name for the def at idx, or file::name outside a
    class. The class is the nearest one above with less indentation."""
    name = TEST_DEF_RE.match(lines[idx]).group(1)
    indent = len(lines[idx]) - len(lines[idx].lstrip())
    if indent:
        for j in range(idx - 1, -1, -1):
            m = CLASS_DEF_RE.match(lines[j])
            if m and len(m.group(1)) < indent:
                return f"{path}::{m.group(2)}::{name}"
    return f"{path}::{name}"


_mapped_cache: dict[Path, set[str]] = {}


def mapped_tests(path: Path = MAPPING_PATH) -> set[str]:
    """Node ids in the mapping file with their [param] suffix removed,
    so a parametrized test counts as mapped when any of its ids is.
    A missing or unreadable file maps nothing, and the mapping rule
    then stays silent (see product_has_mapping)."""
    if path not in _mapped_cache:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            bases = {PARAM_SUFFIX_RE.sub("", n) for n in data.get("mappings", {})}
        except (OSError, ValueError):
            bases = set()
        _mapped_cache[path] = bases
    return _mapped_cache[path]


def product_has_mapping(path: str, mapped: set[str]) -> bool:
    """Whether the mapping file holds any row for the product root `path`
    sits under. A fresh project has no rows yet, and the mapping rule
    must not turn every new test into a warning there."""
    root = product_root(path)
    return bool(root) and any(m.startswith(root) for m in mapped)


def check_line(path: str, lines: list[str], idx: int,
               mapped: set[str] | None = None,
               tenant_re: re.Pattern[str] | None = None) -> list[dict]:
    """Return findings for one line (0-based idx) of a file.

    mapped is the set of mapped node ids (params stripped). None reads
    the live mapping file. tenant_re is the hardcoded-tenant-name
    pattern. None reads the active env file's names."""
    line = lines[idx]
    stripped = line.strip()
    findings = []
    # Checked before the comment/docstring early-returns: ticket keys
    # live exactly there, and they go stale wherever they live
    if TICKET_RE.search(line):
        findings.append({
            "sev": "MEDIUM", "rule": "ticket-in-code",
            "msg": "Jira keys go stale in code. Describe the behavior in "
                   "the comment and keep the ticket in the tracker "
                   "(CONVENTIONS.md > Code notes).",
        })
    if stripped.startswith("#") or inside_triple_quote(lines, idx):
        for f in findings:
            f["path"], f["line"], f["text"] = path, idx + 1, stripped
        return findings

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
    if FLAKY_MARK_RE.search(line):
        findings.append({
            "sev": "HIGH", "rule": "flaky-marker",
            "msg": "the flaky mark is pytest-rerunfailures' own: it retries on ANY "
                   "failure, once even bare, and hides it from the run page. Label "
                   "with intermittent; only run.py --retry-streams reruns "
                   "(CONVENTIONS.md > Reruns).",
        })
    if ABS_COUNT_RE.search(line):
        findings.append({
            "sev": "MEDIUM", "rule": "absolute-count-oracle",
            "msg": "count() > 0 passes on pre-existing elements. Compare "
                   "against a baseline taken before the action, or use "
                   "expect(...).to_have_count().",
        })
    if IMG_SRC_RE.search(line) and not line_is_excused(lines, idx, IMG_SRC_RE):
        findings.append({
            "sev": "MEDIUM", "rule": "img-src-locator",
            "msg": "is this a MUI icon? then use svg[data-testid='...Icon'] "
                   "(present on Events/Admin). A Next.js img asset keeps its "
                   "src basename - its alt text is empty or wrong on this "
                   "app - and says so in a why-comment "
                   "(CONVENTIONS.md > Locators).",
        })
    if TEST_DEF_RE.match(line):
        nodeid = test_nodeid(path, lines, idx)
        if not test_has_title(lines, idx):
            findings.append({
                "sev": "MEDIUM", "rule": "test-without-title",
                "msg": "no docstring: the run report shows a test's docstring first "
                       "line as its readable title. Add one sentence that says what "
                       "the test proves (CONVENTIONS.md > Adding a test).",
            })
    # A QA Touch case exists for UI tests only: the tooling and plugin
    # pins under tests/tools and tests/plugins have no case to map
    if TEST_DEF_RE.match(line) and path.startswith(PRODUCT_PREFIXES):
        if not STEPS_HEADER_RE.search(test_docstring(lines, idx)):
            findings.append({
                "sev": "MEDIUM", "rule": "test-without-steps",
                "msg": "no Steps: block in the docstring: the QA Touch case is "
                       "generated from it. Add 'Steps:' with numbered tester "
                       "steps and an Expected: line under each "
                       "(CONVENTIONS.md > Adding a test).",
            })
        mapped_set = mapped if mapped is not None else mapped_tests()
        # silent until the product has a mapping row: a fresh QA Touch
        # project starts with none, and the first cases come from these tests
        if nodeid not in mapped_set and product_has_mapping(path, mapped_set):
            findings.append({
                "sev": "MEDIUM", "rule": "test-without-mapping",
                "msg": "new test has no QA Touch case: python "
                       f"tools/qatouch_cases_from_tests.py --test {nodeid}, "
                       "import, then --after-import "
                       "(CONVENTIONS.md > Adding a test).",
            })
    pattern = tenant_re if tenant_re is not None else _active_tenant_pattern()
    if pattern is not None and pattern.search(line):
        findings.append({
            "sev": "MEDIUM", "rule": "hardcoded-tenant-name",
            "msg": "a site or camera name in a test ties it to one server. "
                   "Use test_site_name / test_camera_name from config/env/ instead.",
        })
    if UNION_PICK_RE.search(line):
        findings.append({
            "sev": "MEDIUM", "rule": "union-first-last",
            "msg": ".first/.last on a union selector can resolve to a "
                   "hidden copy of the OTHER selector. Split the union or "
                   "scope it to a container.",
        })
    if LONG_WAIT_RE.search(line) and not line_is_excused(lines, idx, LONG_WAIT_RE):
        findings.append({
            "sev": "MEDIUM", "rule": "long-blind-wait",
            "msg": "a DOM wait of a minute or more hides what the server said: "
                   "on a server with no events the wait runs out and reports a "
                   "timeout, not the answer. Follow the request instead "
                   "(tests/shared/helpers/search_job.py), or comment why the "
                   "wait is that long.",
        })
    if TEXT_FIRST_RE.search(line) and not line_is_excused(lines, idx, TEXT_FIRST_RE):
        findings.append({
            "sev": "MEDIUM", "rule": "first-on-text-lookup",
            "msg": ".first on a text lookup picks whichever element mentions "
                   "the words first (the wrong camera, the wrong rule). "
                   "Match exactly (exact=True, "
                   "title=, span[title=]) or scope to the row, or comment "
                   "why the first match is the one.",
        })

    for f in findings:
        f["path"], f["line"], f["text"] = path, idx + 1, stripped
    return findings


_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")


def _block_range(lines: list[str], idx: int) -> range:
    """Line indexes of the indented block that starts after line idx.

    A signature over several lines closes with `):` at the def's own indent. Read as the
    end of the block, that line gave the def an empty body: a real test was "a test with
    no oracle", and a bare return in it was never seen. The block starts after the line
    that closes the brackets.
    """
    indent = len(lines[idx]) - len(lines[idx].lstrip())
    depth, start = 0, idx
    while start < len(lines):
        # strings first: a default like color="#fff" or label="(" would otherwise cut the
        # signature short, and the def would read as a body-less test
        code = _QUOTED_RE.sub("", lines[start]).split("#", 1)[0]
        depth += sum(code.count(ch) for ch in "([{") - sum(code.count(ch) for ch in ")]}")
        if depth <= 0:
            break
        start += 1
    idx = min(start, len(lines) - 1)
    end = idx + 1
    while end < len(lines):
        line = lines[end]
        if line.strip() and (len(line) - len(line.lstrip())) <= indent:
            break
        end += 1
    return range(idx + 1, end)


def _is_fixture(lines: list[str], idx: int) -> bool:
    """True when the def at idx has a pytest.fixture decorator: a fixture named test_* is not a test."""
    i = idx - 1
    # walk up over the decorator lines (and the lines of a decorator that spans several)
    # only the decorator lines above the def: a module constant that merely mentions the word
    # must not exempt a real test
    while (i >= 0 and lines[i].strip().startswith(("@", ")", "]", "}"))) or (
            i >= 0 and lines[i].strip() and lines[i][:1] in (" ", "	") and i < idx and lines[i].strip().endswith(",")):
        if "pytest.fixture" in lines[i] or lines[i].strip().startswith("@fixture"):
            return True
        i -= 1
    return False


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


# Locator calls that wait for their element, 30 s by default. keyboard.press
# waits for nothing and is left out below.
_WAITING_ACTIONS = {
    "click", "dblclick", "hover", "tap", "fill", "check", "uncheck",
    "select_option", "press", "wait_for", "inner_text", "text_content",
    "get_attribute", "scroll_into_view_if_needed",
}
_RAISING_CALLS = {"fail", "skip", "xfail", "exit"}


def _handler_swallows(handler: ast.ExceptHandler) -> bool:
    """True when nothing in the handler raises, fails or skips."""
    for node in ast.walk(handler):
        if isinstance(node, ast.Raise):
            return False
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr in _RAISING_CALLS):
            return False
    return True


def check_swallowed_default_timeout(path: str, lines: list[str]) -> list[dict]:
    """A waiting action with no timeout=, in a try whose handlers swallow.

    When the element is absent the action waits Playwright's default 30 s,
    the handler hides the timeout, and the test passes 30 s slower each time.
    InsightsPage.navigate did this on every widget search: 7 minutes of each
    full run, for months, behind green results. Ask first (is_visible(),
    count()) or give the action a short timeout=.
    """
    try:
        tree = ast.parse("\n".join(lines))
    except SyntaxError:
        return []
    findings = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Try) and node.handlers
                and all(_handler_swallows(h) for h in node.handlers)):
            continue
        for stmt in node.body:
            for call in ast.walk(stmt):
                if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                        and call.func.attr in _WAITING_ACTIONS):
                    continue
                if any(k.arg == "timeout" for k in call.keywords):
                    continue
                owner = call.func.value
                if isinstance(owner, ast.Attribute) and owner.attr == "keyboard":
                    continue
                findings.append({
                    "sev": "MEDIUM", "rule": "swallowed-default-timeout",
                    "path": path, "line": call.lineno,
                    "text": lines[call.lineno - 1].strip(),
                    "msg": f".{call.func.attr}() has no timeout= and its try swallows "
                           "the failure: an absent element costs a silent 30 s. Ask "
                           "first (is_visible(), count()) or pass a short timeout=.",
                })
    return findings


def check_skip_in_except(path: str, lines: list[str]) -> list[dict]:
    """pytest.skip raised from an except handler.

    The except-swallow rule catches a handler that prints or passes.
    A handler that skips is the same defect wearing a report: the run
    says "not supported" where the app actually raised, and nobody
    reads a skip as a failure. One review found five of these, a drag
    that threw and a dialog that never opened among them, each reported
    for weeks as a missing feature.

    A why-comment on the except line (or the line above) excuses the
    deliberate ones: a fixture that skips because the environment is
    genuinely absent, not because a step failed.
    """
    findings = []
    for idx, line in enumerate(lines):
        if not EXCEPT_RE.match(line):
            continue
        if "#" in line or (idx > 0 and lines[idx - 1].strip().startswith("#")):
            continue
        for i in _block_range(lines, idx):
            if SKIP_RE.search(lines[i]) and not inside_triple_quote(lines, i):
                findings.append({
                    "sev": "HIGH", "rule": "skip-in-except",
                    "path": path, "line": i + 1, "text": lines[i].strip(),
                    "msg": "pytest.skip inside an except block: the app "
                           "raised and the run reports SKIP. Let it fail, "
                           "or comment why absence - not failure - is what "
                           "this handler caught.",
                })
                break
    return findings


def check_speculative_skips(path: str, lines: list[str]) -> list[dict]:
    """Skip reasons that guess at the app instead of stating a measurement.

    "may not be supported in current app version" is a hypothesis
    written into a green run. The reason line is the only record a
    reader gets, so it has to say what was measured and what was on
    screen instead. Probe it (tools/explore_app.py) and write the
    finding, or let the test fail.
    """
    findings = []
    for idx, line in enumerate(lines):
        if not SKIP_RE.search(line):
            continue
        if inside_triple_quote(lines, idx):
            continue
        # the reason can run onto the following lines
        block = " ".join(
            lines[i] for i in range(idx, min(idx + 4, len(lines)))
        )
        reason = block[block.index("pytest.skip"):]
        if SPECULATIVE_SKIP_RE.search(reason):
            findings.append({
                "sev": "MEDIUM", "rule": "speculative-skip-reason",
                "path": path, "line": idx + 1, "text": line.strip(),
                "msg": "skip reason guesses at the app (may/might/not "
                       "supported). State what was measured and what was "
                       "on screen instead, or let the test fail.",
            })
    return findings


def check_no_oracle_tests(path: str, lines: list[str]) -> list[dict]:
    """Test functions whose body can never fail.

    A body with no assert, no expect, no pytest.fail/raises, and no
    raising wait is green no matter what the app does. A body line
    mentioning 'oracle' excuses a deliberate delegation to a raising
    page-object call - the comment names where the failure comes from.

    Only files that pytest collects (test_*.py): a scenario file that a pin
    runs in a subprocess holds bodies that pass or die on purpose.
    """
    findings = []
    if not Path(path).name.startswith("test_"):
        return findings
    for idx, line in enumerate(lines):
        m = TEST_DEF_RE.match(line)
        if not m:
            continue
        # a def quoted inside a string (a tool's own pins carry sample
        # test files) is not a test
        if inside_triple_quote(lines, idx) or _is_fixture(lines, idx):
            continue
        body = [lines[i] for i in _block_range(lines, idx)]
        if any("oracle" in b.lower() for b in body):
            continue
        # A body whose only statement is pytest.skip is an explicit
        # hold: it reports SKIP every run and can never pass green
        code = [
            b.strip() for b in body
            if b.strip() and not b.strip().startswith(("#", '"', "'"))
        ]
        if code and all(
            s.startswith(("pytest.skip", ")")) for s in code
        ):
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


def check_except_without_why(path: str, lines: list[str]) -> list[dict]:
    """Except handlers that neither re-raise nor fail and carry no why.

    A handler that returns False, sets None, continues or passes turns
    the app's failure into a branch the test never reports. A review of
    the suite found 135 such handlers, 107 with no comment; each is a
    place a real defect reads as a pass. A why-comment on the except line or the
    line above excuses the deliberate ones; a body that raises,
    pytest.fails or asserts needs none.
    """
    findings = []
    for idx, line in enumerate(lines):
        if not EXCEPT_RE.match(line) or inside_triple_quote(lines, idx):
            continue
        if "#" in line or (idx > 0 and lines[idx - 1].strip().startswith("#")):
            continue
        body = [lines[i].strip() for i in _block_range(lines, idx)]
        code = [s for s in body if s and not s.startswith("#")]
        if any(re.match(r"raise\b|pytest\.fail\s*\(|assert\b", s) for s in code):
            continue
        findings.append({
            "sev": "HIGH", "rule": "except-without-why",
            "path": path, "line": idx + 1, "text": line.strip(),
            "msg": "except handler with no why-comment that neither re-raises "
                   "nor fails: the app's failure becomes a branch the test "
                   "never reports. Re-raise, pytest.fail, or comment on the "
                   "except line why this branch is the right answer "
                   "(CONVENTIONS.md > Missing artifacts and skips).",
        })
    return findings


def check_presence_only_tests(path: str, lines: list[str]) -> list[dict]:
    """Test bodies whose every oracle is that something is visible.

    More than half of the product tests read this way when the rule was
    added: they prove the page shows a thing, not that the action changed
    it, and most of them restate the wait
    their own setup already made. A strong oracle compares a value, a
    count against a baseline, a URL, a text, or a state, or expects a
    negative. A body line mentioning 'oracle' excuses a deliberate
    delegation to a raising page-object call.

    Product tests only: a tool or plugin pin that asserts a startswith
    reads as presence to this heuristic, and the oracle scale was
    written for tests of the product.
    """
    findings = []
    if not path.startswith(PRODUCT_PREFIXES):
        return findings
    for idx, line in enumerate(lines):
        m = TEST_DEF_RE.match(line)
        if not m or inside_triple_quote(lines, idx):
            continue
        body = [lines[i] for i in _block_range(lines, idx)]
        if any("oracle" in b.lower() for b in body):
            continue
        code = [b for b in body if b.strip() and not b.strip().startswith(("#", '"', "'"))]
        if not any(ORACLE_RE.search(b) for b in code):
            continue  # no-oracle-test reports this one
        if any(is_strong_oracle(b) for b in code):
            continue
        findings.append({
            "sev": "MEDIUM", "rule": "presence-only-oracle",
            "path": path, "line": idx + 1, "text": line.strip(),
            "msg": f"{m.group(1)} only checks that something is visible or "
                   "attached. Say what the action changed: compare a value, a "
                   "count against a baseline, a URL, a text, a state, or expect "
                   "a negative (CONVENTIONS.md > Adding a test).",
        })
    return findings


def check_early_exit_tests(path: str, lines: list[str]) -> list[dict]:
    """Bare return statements inside test bodies.

    A test that returns early passes with its remaining steps and
    asserts never run - the class behind the LPR camera selection
    file, whose three tests hunted a panel on the wrong page, printed
    INFO, and returned green for months. Static oracle checks cannot
    see unreachable asserts, so the return itself is the tell. A
    why-comment on the return line (or the line above) excuses a
    deliberate one.
    """
    findings = []
    for idx, line in enumerate(lines):
        if not TEST_DEF_RE.match(line) or _is_fixture(lines, idx):
            continue
        # returns inside functions NESTED in the test body (response
        # listeners, local helpers) are those functions' own control
        # flow, not test exits. The nested block comes from _block_range,
        # so a nested signature over several lines is read whole.
        nested_end = -1
        for i in _block_range(lines, idx):
            if i <= nested_end:
                continue
            body_line = lines[i]
            stripped = body_line.strip()
            if re.match(r"(?:async\s+)?def \w+", stripped):
                nested = _block_range(lines, i)
                nested_end = nested.stop - 1
                continue
            if not re.match(r"^\s*return\b", body_line):
                continue
            # a docstring line can open with the word 'return'.
            # inside_triple_quote is a fence-parity count: a preceding
            # line with an odd number of quote fences flips it for the
            # rest of the file - acceptable for a lint heuristic, and
            # pinned by the rule's self-tests
            if inside_triple_quote(lines, i):
                continue
            if "#" in body_line or (
                i > 0 and lines[i - 1].strip().startswith("#")
            ):
                continue
            findings.append({
                "sev": "MEDIUM", "rule": "early-exit-pass",
                "path": path, "line": i + 1, "text": body_line.strip(),
                "msg": "return inside a test body: everything after "
                       "it never runs and the test passes vacuously. "
                       "Use pytest.skip/fail, or comment why the "
                       "return is safe.",
            })
    return findings


def wanted(path: str) -> bool:
    if not path.endswith(".py"):
        return False
    if not path.startswith(INCLUDE_PREFIXES):
        return False
    return not path.startswith(EXCLUDE_PREFIXES)


def git(*args: str) -> str:
    # utf-8, not the console's code page: a diff carrying smart quotes
    # crashed the reader thread on Windows (cp1252) and the hook blocked
    # the commit that fixed it
    result = subprocess.run(
        ["git", *args], capture_output=True, text=True, check=False, cwd=REPO,
        encoding="utf-8", errors="replace",
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
            findings.extend(check_except_without_why(path, lines))
            findings.extend(check_skip_in_except(path, lines))
            findings.extend(check_swallowed_default_timeout(path, lines))
            findings.extend(check_speculative_skips(path, lines))
            findings.extend(check_no_oracle_tests(path, lines))
            findings.extend(check_presence_only_tests(path, lines))
            findings.extend(check_early_exit_tests(path, lines))
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
            # both skip rules anchor on the skip line itself
            for f in check_skip_in_except(path, lines):
                if f["line"] in added:
                    findings.append(f)
            for f in check_speculative_skips(path, lines):
                if f["line"] in added:
                    findings.append(f)
            # anchors on the action's own line
            for f in check_swallowed_default_timeout(path, lines):
                if f["line"] in added:
                    findings.append(f)
            for f in check_no_oracle_tests(path, lines) + check_presence_only_tests(path, lines):
                block = _block_range(lines, f["line"] - 1)
                if f["line"] in added or any(
                    (i + 1) in added for i in block
                ):
                    findings.append(f)
            # the except rule anchors on the except line
            for f in check_except_without_why(path, lines):
                if f["line"] in added:
                    findings.append(f)
            # early-exit findings anchor on the return line itself
            for f in check_early_exit_tests(path, lines):
                if f["line"] in added:
                    findings.append(f)
        # A NEW test lands with its Steps block (CONVENTIONS.md > Adding a
        # test): on added lines that rule blocks. Whole-repo scans keep it
        # a warning, because existing tests still owe theirs.
        # The swallowed default timeout blocks on added lines for the same
        # reason: the existing sites are standing debt, a new one is a choice.
        for f in findings:
            # presence-only-oracle blocks too: its standing debt is 0, so a new one is a choice.
            if f["rule"] in ("test-without-steps", "swallowed-default-timeout", "presence-only-oracle",
                             "no-oracle-test", "early-exit-pass"):
                f["sev"] = "HIGH"

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
