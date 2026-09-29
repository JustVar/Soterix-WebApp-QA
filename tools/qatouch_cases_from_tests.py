"""Generate QA Touch cases from test docstrings, and map them after import.

A test's docstring is its QA Touch case. The first line is the title.
The "Steps:" block holds the numbered tester steps, and each "Expected:"
line holds what the tester sees after a step. A human writes those
lines. This tool copies them into the canonical CSV that
tools/qatouch_csv_import.py sends. It never invents a step: a test
with no "Steps:" block is listed as "needs steps" and gets no row.

    python tools/qatouch_cases_from_tests.py --unmapped
    python tools/qatouch_cases_from_tests.py --shared-keys
    python tools/qatouch_cases_from_tests.py --weak-mappings
    python tools/qatouch_cases_from_tests.py --dead-keys
    python tools/qatouch_cases_from_tests.py --test tests/ui/x.py::TestX::test_y
    python tools/qatouch_cases_from_tests.py --file tests/ui/admin/test_lpr_views.py
    python tools/qatouch_csv_import.py preview logs/qatouch_new_cases_<date>.csv
    python tools/qatouch_csv_import.py import logs/qatouch_new_cases_<date>.csv
    python tools/qatouch_cases_from_tests.py --after-import logs/qatouch_new_cases_<date>.csv

--shared-keys is the worklist for splitting a case key claimed by more
than one test. For each such key it puts
the case's own title beside each claimant's title, ranks the claimants
by how well their title matches the case's, and says which of the
others already have a Steps block (a case can be made now) and which
need one written first. A weak best match means the mapping is wrong,
not just shared - the bulk match by title collapsed unrelated tests
onto one case. It writes logs/qatouch_shared_keys_<date>.json.

--weak-mappings is a REVIEW ORDER, not a verdict: every mapped test
whose title reads unlike its case's, least alike first. Measured
09/08/2026, the least-alike pairs were mostly the same case in other
words ("empty username and password stays on the login page" against
"login fails when both fields are empty"), so the score cannot say a
mapping is wrong - only a person reading the pair can. Use it after
the shared keys are split, when a wrong mapping has one claimant and
--shared-keys can no longer see it. Writes
logs/qatouch_weak_mappings_<date>.json.

Selection (any mix, node ids are de-duplicated):

  --unmapped     tests under the product roots with no row in the mapping file
  --dead-keys    tests whose mapping row points at a case no snapshot holds
  --test         one node id, repeatable
  --file         every test in one file
  --exclude-dir  a module to skip (repeatable; none by default)

Output: logs/qatouch_new_cases_<date>.csv, one row per test in the
column order tools/qatouch_csv_import.py reads, plus
logs/qatouch_new_cases_<date>.md to read before the import. The
Reference column carries the node id without its [param] suffix. That
is the join key: --after-import reads the project's cases back through
the read-only client, matches Reference to node id, and writes the
mapping rows (reviewed: true, source: "generated"). A parametrized test
gets one row per parameter id, the way the mapping already stores them.

This tool reads QA Touch and writes only under logs/ and the mapping
file. The import is the owner's command.
"""
from __future__ import annotations

import argparse
import ast
import csv
import datetime as dt
import itertools
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from config.products import PRODUCT_ROOTS, area_of, home_project

# --after-import reads the project back through the API; the key
# lives in .env like the import tool's does
load_dotenv(ROOT / '.env')

from plugins.run_report import readable_title
from tools import qatouch_mapping as qm
from tools.qatouch_mapping_audit import (
    collect_tests,
    dead_key_nodeids,
    latest_snapshot,
    load_cases,
    unmapped_nodeids,
)

TESTS_ROOTS = [ROOT / p.rstrip('/') for p in PRODUCT_ROOTS]   # config/products.py
LOGS_DIR = ROOT / 'logs'
DEFAULT_PROJECT = 'JlW1'
# Modules skipped unless --exclude-dir names others. A product root that
# reports to a second QA Touch project would be listed here.
DEFAULT_EXCLUDE: tuple[str, ...] = ()

# The header of the import CSV, in its order. The importer
# (tools/qatouch_csv_import.py) maps these names to the endpoint's columns.
COLUMNS = [
    'Module_name', 'Test Case Title', 'Test Data', 'Estimate', 'Reference',
    'Precondition', 'Steps', 'Expected_result', 'Test Suite', 'Tags',
    'Description', 'Type', 'Priority', 'Mode', 'Created By',
]

PRECONDITION = (
    'Logged in as an Admin user on the QA tenant. The configured site '
    'and camera exist (config/env/qa.py).'
)
PRECONDITION_BY_AREA = {
    'login': 'The QA tenant login page is open and no user is logged in '
             '(config/env/qa.py).',
}
TYPE = 'Regression'
PRIORITY = 'Medium'
MODE = 'Automation'

# Words in a folder, file, or class name that read as acronyms, and the
# words a module name keeps in lower case.
ACRONYMS = {'lpr': 'LPR', 'ptz': 'PTZ', 'ldap': 'LDAP',
            'ui': 'UI', 'api': 'API', 'ai': 'AI', 'vca': 'VCA', 'osd': 'OSD',
            'roi': 'ROI', 'rtsp': 'RTSP'}
SMALL_WORDS = {'and', 'or', 'of', 'to', 'in', 'for'}

STEPS_HEADER_RE = re.compile(r'^\s*Steps:\s*$')
STEP_RE = re.compile(r'^\s*(\d+)[.)]\s+(.*\S)\s*$')
EXPECTED_RE = re.compile(r'^\s*Expected:\s*(.*?)\s*$')

# The browser parameter pytest-playwright puts on every node id.
BROWSER = 'chromium'


# ------------------------------------------------------------ docstrings

@dataclass
class Step:
    text: str
    expected: str = ''


@dataclass
class ParsedDoc:
    title: str
    steps: list[Step] = field(default_factory=list)
    problem: str = ''   # why no case can be made, empty when it can

    @property
    def ok(self) -> bool:
        return not self.problem


def parse_docstring(doc: str | None, nodeid: str) -> ParsedDoc:
    """Title, steps, and expected results from a test docstring.

    The block starts at a line that reads "Steps:". Each "N. text" line
    is a step. An "Expected:" line belongs to the step above it, and a
    plain line continues whatever came last (step or expected). The
    block runs to the end of the docstring.
    """
    title = readable_title(nodeid, doc).rstrip('.')
    lines = (doc or '').splitlines()
    start = next((i for i, line in enumerate(lines) if STEPS_HEADER_RE.match(line)), None)
    if start is None:
        return ParsedDoc(title, problem='no Steps: block')

    steps: list[Step] = []
    last = ''   # 'step' or 'expected': where a plain line continues
    for line in lines[start + 1:]:
        if not line.strip():
            continue
        m = STEP_RE.match(line)
        if m:
            steps.append(Step(m.group(2).strip()))
            last = 'step'
            continue
        m = EXPECTED_RE.match(line)
        if m and steps:
            text = m.group(1).strip()
            steps[-1].expected = f'{steps[-1].expected} {text}'.strip()
            last = 'expected'
            continue
        if steps and last == 'expected':
            steps[-1].expected = f'{steps[-1].expected} {line.strip()}'.strip()
        elif steps:
            steps[-1].text = f'{steps[-1].text} {line.strip()}'

    if not steps:
        return ParsedDoc(title, problem='Steps: block has no numbered line')
    if not any(s.expected for s in steps):
        return ParsedDoc(title, steps, problem='no Expected: line')
    return ParsedDoc(title, steps)


# ------------------------------------------------------------ test scan

@dataclass
class TestInfo:
    nodeid: str          # base node id, no [param]
    file: str
    area: str
    class_name: str
    func_name: str
    docstring: str
    skipped: bool
    param_ids: list[str] | None   # None: parametrized but not derivable
    parametrized: bool
    classes_in_file: int = 1


def _is_skip_mark(node: ast.AST) -> bool:
    """pytest.mark.skip or pytest.mark.skip(...)."""
    if isinstance(node, ast.Call):
        node = node.func
    return (isinstance(node, ast.Attribute) and node.attr == 'skip'
            and isinstance(node.value, ast.Attribute) and node.value.attr == 'mark')


def _module_skipped(tree: ast.Module) -> bool:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == 'pytestmark' for t in node.targets):
            continue
        marks = node.value.elts if isinstance(node.value, ast.List | ast.Tuple) else [node.value]
        if any(_is_skip_mark(m) for m in marks):
            return True
    return False


_SAFE_NODES = (
    ast.Expression, ast.Constant, ast.List, ast.Tuple, ast.Name, ast.Load,
    ast.ListComp, ast.comprehension, ast.JoinedStr, ast.FormattedValue,
    ast.BinOp, ast.Add, ast.Mod, ast.Subscript, ast.Slice, ast.Store,
)


def _safe_eval(node: ast.AST, env: dict):
    """Evaluate a literal-only expression (lists, tuples, f-strings,
    comprehensions over them). Raises ValueError for anything else, so
    a call or attribute in a parametrize list never runs."""
    for sub in ast.walk(node):
        if not isinstance(sub, _SAFE_NODES):
            raise ValueError(f'unsafe node {type(sub).__name__}')
    code = compile(ast.Expression(body=node), '<parametrize>', 'eval')
    # the walk above admits literals and comprehensions only, so this
    # eval cannot call anything; an unknown name raises NameError
    return eval(code, {'__builtins__': {}}, dict(env))


def _module_env(tree: ast.Module) -> dict:
    """Module-level names bound to literal-only values, in order."""
    env: dict = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name):
            try:
                env[node.targets[0].id] = _safe_eval(node.value, env)
            except (ValueError, SyntaxError, TypeError, NameError):
                continue
    return env


def _pytest_id(value, argname: str, index: int) -> str:
    """The id pytest gives one argument value when no ids= is passed."""
    if isinstance(value, str):
        return value
    if isinstance(value, bool | int | float) or value is None:
        return str(value)
    return f'{argname}{index}'


def _param_ids(decorators: list[ast.AST], env: dict) -> tuple[bool, list[str] | None]:
    """(parametrized, ids) for a function's parametrize decorators.

    Stacked decorators multiply the way pytest applies them: the one
    nearest the function first. ids is None when a value list or ids=
    is not a literal this tool can read."""
    sets: list[list[str]] = []
    for deco in decorators:
        if not isinstance(deco, ast.Call) or not isinstance(deco.func, ast.Attribute) \
                or deco.func.attr != 'parametrize':
            continue
        if len(deco.args) < 2:
            return True, None
        try:
            names = _safe_eval(deco.args[0], env)
            values = _safe_eval(deco.args[1], env)
            ids = None
            for kw in deco.keywords:
                if kw.arg == 'ids':
                    ids = _safe_eval(kw.value, env)
        except (ValueError, SyntaxError, TypeError, NameError):
            return True, None
        if isinstance(names, str):
            names = [n.strip() for n in names.split(',')]
        names = list(names)
        if ids is not None:
            sets.append([str(i) for i in ids])
            continue
        derived = []
        for index, value in enumerate(values):
            parts = list(value) if len(names) > 1 and isinstance(value, list | tuple) \
                else [value]
            derived.append('-'.join(
                _pytest_id(v, n, index) for v, n in zip(parts, names, strict=False)))
        sets.append(derived)
    if not sets:
        return False, []
    # decorators are listed outermost first; pytest applies the nearest
    # one first, so its id comes first in the joined id
    ordered = list(reversed(sets))
    return True, ['-'.join(combo) for combo in itertools.product(*ordered)]


def scan_file(path: Path, root: Path = ROOT) -> dict[str, TestInfo]:
    """Every test function in one file, keyed by base node id."""
    rel = path.relative_to(root).as_posix()
    area = area_of(rel) or ''
    tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=rel)
    env = _module_env(tree)
    file_skipped = _module_skipped(tree)
    n_classes = sum(1 for n in tree.body
                    if isinstance(n, ast.ClassDef) and n.name.startswith('Test'))
    found: dict[str, TestInfo] = {}

    def add(fn: ast.FunctionDef | ast.AsyncFunctionDef, class_name: str,
            class_skipped: bool, class_decorators: list[ast.AST]) -> None:
        prefix = f'{class_name}::' if class_name else ''
        nodeid = f'{rel}::{prefix}{fn.name}'
        parametrized, ids = _param_ids(class_decorators + fn.decorator_list, env)
        found[nodeid] = TestInfo(
            nodeid=nodeid, file=rel, area=area, class_name=class_name,
            func_name=fn.name, docstring=ast.get_docstring(fn) or '',
            skipped=file_skipped or class_skipped
            or any(_is_skip_mark(d) for d in fn.decorator_list),
            param_ids=ids, parametrized=parametrized, classes_in_file=n_classes,
        )

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith('test'):
                add(node, '', False, [])
        elif isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
            class_skipped = any(_is_skip_mark(d) for d in node.decorator_list)
            for sub in node.body:
                if isinstance(sub, ast.FunctionDef | ast.AsyncFunctionDef) \
                        and sub.name.startswith('test'):
                    add(sub, node.name, class_skipped, node.decorator_list)
    return found


def scan_tests(root: Path | None = None, repo: Path | None = None) -> dict[str, TestInfo]:
    """Every test function under the product roots, keyed by base node id."""
    roots = [root] if root else TESTS_ROOTS
    repo = repo or ROOT
    found: dict[str, TestInfo] = {}
    for r in roots:
        for path in sorted(r.rglob('test_*.py')):
            found.update(scan_file(path, repo))
    return found


# ------------------------------------------------------------ case rows

def _words(name: str) -> list[str]:
    """snake_case or CamelCase to title words, acronyms kept."""
    if '_' in name or name.islower():
        raw = [w for w in name.split('_') if w]
    else:
        raw = re.findall(r'[A-Z]+(?=[A-Z][a-z]|\b)|[A-Z]?[a-z0-9]+', name)
    words = [ACRONYMS.get(w.lower(), w.capitalize()) for w in raw]
    return [w.lower() if i and w.lower() in SMALL_WORDS else w for i, w in enumerate(words)]


def module_name(nodeid: str, classes_in_file: int = 1) -> str:
    """"Admin > LPR Navigation": folder and file stem, plus the class when
    the file holds more than one Test class. A level drops the words it
    repeats from the level above."""
    path, *rest = nodeid.split('::')
    area = area_of(path) or ''
    stem = re.sub(r'^test_?', '', Path(path).stem)
    area_words = _words(area) if area else []
    stem_words = _words(stem)
    if stem_words[:len(area_words)] == area_words:
        stem_words = stem_words[len(area_words):]
    levels = [w for w in (' '.join(area_words), ' '.join(stem_words)) if w]
    if len(rest) == 2 and classes_in_file > 1:
        class_words = _words(re.sub(r'^Test', '', rest[0]))
        lead = set(area_words) | set(stem_words[:1])
        while class_words and class_words[0] in lead:
            class_words = class_words[1:]
        if class_words and ' '.join(class_words) not in levels:
            levels.append(' '.join(class_words))
    return ' > '.join(levels)


def build_row(info: TestInfo, parsed: ParsedDoc, today: str) -> dict[str, str]:
    """One canonical CSV row. Steps and Expected_result hold one line per
    step, "-" where a step has no expected result, so the phase 5
    splitter reads them as a per-step vector."""
    steps = '\n'.join(f'Step {i}: {s.text}' for i, s in enumerate(parsed.steps, 1))
    expected = '\n'.join(s.expected or '-' for s in parsed.steps)
    # an existing label only: the import endpoint fails a row that carries
    # a label the project has never seen (measured 09/14/2026, docs/
    # QA_TOUCH_INTEGRATION.md); Mode=Automation is the automation marker
    tags = ['regression']
    skipped_note = ' (skipped in the suite)' if info.skipped else ''
    if info.parametrized:
        test_data = ', '.join(info.param_ids) if info.param_ids \
            else 'parametrized (ids not readable statically)'
    else:
        test_data = 'N/A'
    return {
        'Module_name': module_name(info.nodeid, info.classes_in_file),
        'Test Case Title': parsed.title,
        'Test Data': test_data,
        'Estimate': '',
        'Reference': info.nodeid,
        'Precondition': PRECONDITION_BY_AREA.get(info.area, PRECONDITION),
        'Steps': steps,
        'Expected_result': expected,
        'Test Suite': '',
        'Tags': ';'.join(t for t in tags if t),
        'Description': f'Generated from {info.nodeid} on {today}{skipped_note}',
        'Type': TYPE,
        'Priority': PRIORITY,
        'Mode': MODE,
        'Created By': '',
    }


def write_csv(rows: list[dict[str, str]], path: Path) -> None:
    with open(path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(rows: list[dict[str, str]], needs: list[tuple[str, str]],
                   path: Path, today: str) -> None:
    out = [f'# QA Touch cases generated from tests ({today})', '',
           f'{len(rows)} case(s) ready. {len(needs)} test(s) need steps.', '']
    for row in rows:
        out += [f'## {row["Test Case Title"]}', '',
                f'- Module: {row["Module_name"]}',
                f'- Reference: {row["Reference"]}',
                f'- Test data: {row["Test Data"]}',
                f'- Tags: {row["Tags"]}', '']
        expected = row['Expected_result'].split('\n')
        for i, step in enumerate(row['Steps'].split('\n')):
            out.append(step)
            if expected[i] != '-':
                out.append(f'    Expected: {expected[i]}')
        out.append('')
    if needs:
        out += ['## Needs steps (no row written)', '']
        out += [f'- {nodeid}: {why}' for nodeid, why in needs]
        out.append('')
    path.write_text('\n'.join(out), encoding='utf-8')


# ------------------------------------------------------------ selection

def _title_words(text: str) -> str:
    """Lower-cased title without the filler the bulk match matched on."""
    words = (text or '').lower().replace('.', ' ').split()
    return ' '.join(w for w in words if w not in ('verify', 'that', 'the', 'a', 'an', 'is'))


def rank_claimants(case_title: str, claimants: list[tuple[str, str, bool]]) -> list[dict]:
    """Pure: the claimants of one key, best title match first.

    claimants  (nodeid, test title, has_steps)
    Returns dicts {nodeid, title, has_steps, score}. The first is the
    proposed owner; a first score under WEAK_OWNER means no claimant is
    the case (the mapping is wrong, not merely shared).
    """
    import difflib
    ranked = []
    for nodeid, title, has_steps in claimants:
        score = difflib.SequenceMatcher(
            None, _title_words(case_title), _title_words(title)).ratio()
        ranked.append({'nodeid': nodeid, 'title': title,
                       'has_steps': has_steps, 'score': round(score, 2)})
    ranked.sort(key=lambda r: (-r['score'], r['nodeid']))
    return ranked


WEAK_OWNER = 0.45


def shared_keys_worklist(mapping: dict, cases: dict, tests: dict[str, TestInfo]) -> list[dict]:
    """Every case key claimed by more than one test, with its ranked claimants."""
    claims: dict[str, list[str]] = {}
    for nodeid, row in mapping.items():
        key = (row or {}).get('case_key')
        if not key:
            continue
        base = qm.function_base(nodeid)
        claims.setdefault(key, [])
        if base not in claims[key]:
            claims[key].append(base)
    out = []
    for key, nodeids in claims.items():
        if len(nodeids) < 2:
            continue
        case = cases.get(key, {})
        claimants = []
        for nodeid in nodeids:
            info = tests.get(nodeid)
            doc = parse_docstring(info.docstring, nodeid) if info else None
            claimants.append((nodeid,
                              doc.title if doc else '<test not found>',
                              bool(doc and doc.ok)))
        ranked = rank_claimants(case.get('case_title', ''), claimants)
        out.append({'key': key,
                    'case_title': case.get('case_title', '<not in snapshot>'),
                    'module': case.get('module_name', ''),
                    'owner': ranked[0], 'others': ranked[1:],
                    'owner_weak': ranked[0]['score'] < WEAK_OWNER})
    out.sort(key=lambda r: (-len(r['others']), r['key']))
    return out


def weak_mappings(mapping: dict, cases: dict, tests: dict[str, TestInfo]) -> list[dict]:
    """Pure: every mapped test whose title scores under WEAK_OWNER against its case."""
    out = []
    seen = set()
    for nodeid, row in mapping.items():
        key = (row or {}).get('case_key')
        base = qm.function_base(nodeid)
        if not key or base in seen:
            continue
        seen.add(base)
        info = tests.get(base)
        if info is None:
            continue
        doc = parse_docstring(info.docstring, base)
        case = cases.get(key)
        if case is None:
            out.append({'nodeid': base, 'key': key, 'score': 0.0,
                        'test_title': doc.title, 'case_title': '<not in snapshot>',
                        'module': ''})
            continue
        ranked = rank_claimants(case.get('case_title', ''), [(base, doc.title, doc.ok)])
        if ranked[0]['score'] < WEAK_OWNER:
            out.append({'nodeid': base, 'key': key, 'score': ranked[0]['score'],
                        'test_title': doc.title, 'case_title': case.get('case_title', ''),
                        'module': case.get('module_name', '')})
    out.sort(key=lambda r: (r['score'], r['nodeid']))
    return out


def cmd_weak_mappings(args) -> int:
    from tools.qatouch_mapping_audit import latest_snapshot
    tests = scan_tests()
    mapping = qm.load_raw(args.mapping).get('mappings', {})
    snap_path = latest_snapshot()
    cases = {}
    if snap_path:
        cases = {c['case_key']: c
                 for c in json.loads(snap_path.read_text(encoding='utf-8')).get('cases') or []}
    rows = weak_mappings(mapping, cases, tests)
    LOGS_DIR.mkdir(exist_ok=True)
    out = LOGS_DIR / f'qatouch_weak_mappings_{dt.date.today().isoformat()}.json'
    out.write_text(json.dumps(rows, indent=1), encoding='utf-8')
    missing = [r for r in rows if r['case_title'] == '<not in snapshot>']
    print(f'Mappings to review (titles read differently, least alike first): {len(rows)} of {len({qm.function_base(n) for n in mapping})} mapped tests '
          f'(snapshot: {snap_path.name if snap_path else "none"}; '
          f'{len(missing)} point at a case the snapshot does not hold - refresh it)')
    print(f'  written: {out}')
    print()
    for r in rows:
        print(f"{r['key']}  {r['score']:.2f}  [{r['module']}]")
        print(f"    test: {r['test_title'][:70]}")
        print(f"    case: {r['case_title'][:70]}")
        print(f"          {r['nodeid'].replace('tests/ui/', '')}")
    return 0


def cmd_shared_keys(args) -> int:
    from tools.qatouch_mapping_audit import latest_snapshot
    tests = scan_tests()
    mapping = qm.load_raw(args.mapping).get('mappings', {})
    snap_path = latest_snapshot()
    cases = {}
    if snap_path:
        cases = {c['case_key']: c
                 for c in json.loads(snap_path.read_text(encoding='utf-8')).get('cases') or []}
    rows = shared_keys_worklist(mapping, cases, tests)
    LOGS_DIR.mkdir(exist_ok=True)
    out = LOGS_DIR / f'qatouch_shared_keys_{dt.date.today().isoformat()}.json'
    out.write_text(json.dumps(rows, indent=1), encoding='utf-8')
    others = [o for r in rows for o in r['others']]
    ready = [o for o in others if o['has_steps']]
    weak = [r for r in rows if r['owner_weak']]
    print(f'Shared keys: {len(rows)}  (snapshot: {snap_path.name if snap_path else "none"})')
    print(f'  tests needing their own case: {len(others)}  '
          f'- with a Steps block now: {len(ready)}  - need steps first: {len(others) - len(ready)}')
    print(f'  keys where no claimant matches the case (mapping wrong): {len(weak)}')
    print(f'  written: {out}')
    print()
    for r in rows:
        flag = '  MAPPING WRONG' if r['owner_weak'] else ''
        print(f"{r['key']}  [{r['module']}]  case: {r['case_title'][:64]}{flag}")
        o = r['owner']
        print(f"    owner {o['score']:.2f}  {o['nodeid'].replace('tests/ui/', '')}")
        for o in r['others']:
            need = 'steps ok   ' if o['has_steps'] else 'NEEDS STEPS'
            print(f"    new   {o['score']:.2f}  {need}  {o['nodeid'].replace('tests/ui/', '')}")
    return 0


def select_nodeids(args, tests: dict[str, TestInfo]) -> list[str]:
    """Base node ids the flags name, de-duplicated, excluded folders out."""
    chosen: set[str] = set()
    mappings = qm.load_raw(args.mapping).get('mappings', {})
    # collect_tests is the audit tool's view of the tree: same keys
    audit_tests = collect_tests()
    if args.unmapped:
        chosen.update(unmapped_nodeids(audit_tests, mappings))
    if args.dead_keys:
        cases_path = args.cases or latest_snapshot()
        if not cases_path or not Path(cases_path).exists():
            raise SystemExit('No case snapshot found. Pass --cases, or take one: '
                             'pass --cases with a snapshot-shaped JSON file')
        cases, _label = load_cases(Path(cases_path))
        chosen.update(dead_key_nodeids(audit_tests, mappings, cases))
    for nodeid in args.test or []:
        chosen.add(qm.function_base(nodeid.replace('\\', '/')))
    for file in args.file or []:
        rel = Path(file).as_posix()
        chosen.update(n for n in tests if n.split('::')[0] == rel)
    excluded = set(args.exclude_dir or [])
    return sorted(n for n in chosen
                  if not (tests.get(n) and tests[n].area in excluded))


def generate(args) -> int:
    tests = scan_tests()
    nodeids = select_nodeids(args, tests)
    if not nodeids:
        print('Nothing selected. Use --unmapped, --dead-keys, --test, or --file.')
        return 2
    today = dt.date.today().isoformat()
    rows: list[dict[str, str]] = []
    needs: list[tuple[str, str]] = []
    for nodeid in nodeids:
        info = tests.get(nodeid)
        if info is None:
            needs.append((nodeid, 'test not found under the product roots'))
            continue
        parsed = parse_docstring(info.docstring, nodeid)
        if not parsed.ok:
            needs.append((nodeid, parsed.problem))
            continue
        rows.append(build_row(info, parsed, today))

    LOGS_DIR.mkdir(exist_ok=True)
    csv_path = LOGS_DIR / f'qatouch_new_cases_{today}.csv'
    md_path = LOGS_DIR / f'qatouch_new_cases_{today}.md'
    write_csv(rows, csv_path)
    write_markdown(rows, needs, md_path, today)

    per_module: dict[str, int] = {}
    for row in rows:
        per_module[row['Module_name']] = per_module.get(row['Module_name'], 0) + 1
    print(f'\n  Selected:     {len(nodeids)} test(s)')
    print(f'  Cases ready:  {len(rows)}')
    for module, n in sorted(per_module.items()):
        print(f'    {n:3d}  {module}')
    print(f'  Needs steps:  {len(needs)}')
    for nodeid, why in needs:
        print(f'    {nodeid}: {why}')
    print(f'\n  CSV:      {csv_path.relative_to(ROOT).as_posix()}')
    print(f'  Preview:  {md_path.relative_to(ROOT).as_posix()}')
    print(f'\n  Next: python tools/qatouch_csv_import.py preview '
          f'{csv_path.relative_to(ROOT).as_posix()} --project {args.project}')
    return 0


# ------------------------------------------------------------ after import

REFERENCE_FIELDS = ('References', 'reference', 'Reference', 'refLink', 'ref_link')


def case_reference(case: dict) -> str:
    for name in REFERENCE_FIELDS:
        value = case.get(name)
        if value:
            return str(value).strip()
    return ''


def match_cases(rows: list[dict[str, str]], cases: list[dict]
                ) -> tuple[dict[str, dict], list[str], dict[str, list[str]]]:
    """Reference -> case for the CSV rows, plus the references no case
    carries and the references more than one case carries (a
    re-import made duplicates: the owner picks, this tool does not)."""
    by_ref: dict[str, list[dict]] = {}
    for case in cases:
        ref = case_reference(case)
        if ref:
            by_ref.setdefault(ref, []).append(case)
    matched: dict[str, dict] = {}
    missing: list[str] = []
    ambiguous: dict[str, list[str]] = {}
    for row in rows:
        ref = row['Reference'].strip()
        hits = by_ref.get(ref, [])
        if len(hits) == 1:
            matched[ref] = hits[0]
        elif not hits:
            missing.append(ref)
        else:
            ambiguous[ref] = [str(c.get('case_key')) for c in hits]
    return matched, missing, ambiguous


def mapping_rows(reference: str, case: dict, info: TestInfo | None,
                 project: str | None = None) -> dict[str, dict]:
    """nodeid -> mapping entry for one created case.

    Node ids carry the browser param the way the mapping stores them:
    base[chromium], or base[chromium-<id>] per parameter id. When the
    ids could not be read, the bare base is written: the reporter's
    variant lookup strips the params and still finds it.

    A case created in a project other than the test's home project
    (a Core test's Neurosen case) goes under `case_keys`, keyed by that
    project; the plain `case_key` stays the home project's."""
    key = str(case.get('case_key') or '')
    foreign = bool(project) and project != home_project(reference)
    entry = {
        'case_key': '' if foreign else key,
        **({'case_keys': {project: key}} if foreign else {}),
        'case_title': str(case.get('case_title') or '').strip(),
        'score': 1.0,
        'module': str(case.get('module_name') or case.get('module name') or '').strip(),
        'auto_matched': False,
        'reviewed': True,
        'source': 'generated',
    }
    if info is None or not info.parametrized:
        keys = [f'{reference}[{BROWSER}]']
    elif info.param_ids:
        keys = [f'{reference}[{BROWSER}-{pid}]' for pid in info.param_ids]
    else:
        keys = [reference]
    return {k: dict(entry) for k in keys}


def after_import(args) -> int:
    csv_path = Path(args.after_import)
    with open(csv_path, encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print(f'{csv_path} has no rows.')
        return 2

    if args.cases:
        data = json.loads(Path(args.cases).read_text(encoding='utf-8'))
        cases = data.get('cases', data) if isinstance(data, dict) else data
        source = str(args.cases)
    else:
        from tools.qatouch_client import QATouchClient
        cases = QATouchClient().list_all_test_cases(args.project)
        source = f'QA Touch project {args.project}'
    print(f'\n  Cases read: {len(cases)} from {source}')

    matched, missing, ambiguous = match_cases(rows, cases)
    tests = scan_tests()
    data = qm.load_raw(args.mapping)
    mappings = data.setdefault('mappings', {})
    written = 0
    replaced = 0
    keys: list[str] = []
    for ref, case in matched.items():
        info = tests.get(ref)
        old = [n for n in mappings if qm.function_base(n) == ref]
        if args.project != home_project(ref) and old:
            # A case in another project for a test that already has its
            # home rows: add the key under case_keys, keep everything else.
            for n in old:
                mappings[n].setdefault('case_keys', {})[args.project] = str(case.get('case_key') or '')
            written += len(old)
            keys.append(str(case.get('case_key')))
            continue
        # a dead-key row keyed by an old param id would survive beside
        # the new rows: drop every row of this function first
        for n in old:
            del mappings[n]
        replaced += len(old)
        new_rows = mapping_rows(ref, case, info, project=args.project)
        mappings.update(new_rows)
        written += len(new_rows)
        keys.append(str(case.get('case_key')))
    if written and not args.dry_run:
        qm.save_raw(data, args.mapping)

    print(f'  Matched:    {len(matched)} case(s) -> {written} mapping row(s) '
          f'({replaced} old row(s) replaced)'
          f'{" [dry run, nothing saved]" if args.dry_run else ""}')
    if missing:
        print(f'  No case carries these {len(missing)} reference(s) - not imported yet, '
              'or the import dropped the Reference column:')
        for ref in missing:
            print(f'    {ref}')
    if ambiguous:
        print(f'  {len(ambiguous)} reference(s) match MORE than one case (duplicate '
              'import?). Not mapped; pick one and edit the mapping by hand:')
        for ref, dup in ambiguous.items():
            print(f'    {ref}: {", ".join(dup)}')
    if keys:
        # Measured 09/08/2026: cases created through the API importer
        # arrive with their steps already split (14 of 14 matched their
        # docstrings), so the phase-5 splitter is for the UI-upload path
        # only - and its own case listing answered 404 that day.
        print('\n  Steps arrive split through this path; no phase-5 split is needed.')
    return 0 if not (missing or ambiguous) else 1


# ------------------------------------------------------------ cli

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Generate QA Touch cases from test docstrings; map them after import.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split('Selection', 1)[0],
    )
    parser.add_argument('--weak-mappings', action='store_true',
                        help='every mapped test whose title does not read like its '
                             "case's; writes logs/qatouch_weak_mappings_<date>.json")
    parser.add_argument('--shared-keys', action='store_true',
                        help='worklist of case keys claimed by more than one test; '
                             'writes logs/qatouch_shared_keys_<date>.json')
    parser.add_argument('--unmapped', action='store_true',
                        help='tests under the product roots with no mapping row')
    parser.add_argument('--dead-keys', action='store_true',
                        help='tests whose mapped case is in no snapshot')
    parser.add_argument('--test', action='append', metavar='NODEID',
                        help='one node id (repeatable)')
    parser.add_argument('--file', action='append', metavar='PATH',
                        help='every test in one file (repeatable)')
    parser.add_argument('--project', default=DEFAULT_PROJECT,
                        help=f'QA Touch project key (default {DEFAULT_PROJECT})')
    parser.add_argument('--exclude-dir', action='append', metavar='DIR',
                        help='module to skip (repeatable; none by default)')
    parser.add_argument('--cases', type=Path, default=None,
                        help='snapshot-shaped JSON of cases (default: newest snapshot; '
                             'with --after-import: use instead of reading QA Touch)')
    parser.add_argument('--mapping', type=Path, default=qm.MAPPING_PATH,
                        help='mapping file (default: the live one)')
    parser.add_argument('--after-import', metavar='CSV',
                        help='match the CSV rows to created cases and write the mapping')
    parser.add_argument('--dry-run', action='store_true',
                        help='with --after-import: report, do not save the mapping')
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.exclude_dir is None:
        args.exclude_dir = list(DEFAULT_EXCLUDE)
    args.exclude_dir = [d for d in args.exclude_dir if d != 'none']
    if args.after_import:
        return after_import(args)
    if args.shared_keys:
        return cmd_shared_keys(args)
    if args.weak_mappings:
        return cmd_weak_mappings(args)
    return generate(args)


if __name__ == '__main__':
    sys.exit(main())
