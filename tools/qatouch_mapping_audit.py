"""Audit the test-to-case mapping against the test tree and QA Touch.

config/qatouch_case_mapping.json links pytest node ids to QA Touch cases.
A wrong row uploads a real Pass/Fail onto a case the test never verifies,
and the run report shows the wrong case title under the test. This tool
finds the rows that look wrong, without running a test and without
touching QA Touch. It reads, scores, and reports. It never writes.

For every mapping row it lines up three things:

  1. The test's readable title (first docstring line, as run.html shows it).
  2. The case title cached in the mapping row.
  3. The case title in the newest QA Touch snapshot of the test's own
     project (the web-app project at the top of the snapshots folder, or
     a file you pass; a second product root's project in a folder named
     for its key).

and reports:

  stale      the node id names a test that is not in the tree any more
  dead key   the case key is in no snapshot: the case was deleted
  drift      the cached title differs from the snapshot title (rename)
  suspect    test title and case title share too few words (below the
             threshold), with the best-matching cases as candidates
  shared     one case key claimed by more than one test function
  unmapped   tests under the product roots with no mapping row (counts only)

The score is the larger of a word-overlap ratio and difflib's sequence
ratio on the two titles, 0 to 1. It is a hint, not a verdict: a row that
scores low may still be right, because a docstring and a case title can
describe one behaviour in different words. Read the row before changing
it. Rows are never changed here; edit the JSON by hand or with
tools/qatouch_mapping.py.

    python tools/qatouch_mapping_audit.py                 # text report
    python tools/qatouch_mapping_audit.py --json          # machine-readable
    python tools/qatouch_mapping_audit.py --threshold 0.5 --candidates 5
    python tools/qatouch_mapping_audit.py --cases path/to/cases.json

--cases takes any JSON file with a top-level "cases" list in the snapshot
shape (config/qatouch_snapshots/*.json, or a fresh read-only pull). The
default is the newest snapshot. Exit code 0 always: this is a report.
"""
from __future__ import annotations

import argparse
import ast
import difflib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import products
from config.products import PRODUCT_ROOTS, area_of
from plugins.run_report import readable_title
from tools.qatouch_mapping import MAPPING_PATH, function_base, load_raw

SNAPSHOTS_DIR = ROOT / 'config' / 'qatouch_snapshots'
# Which QA Touch project a test's cases live in, by the test's root
# (config/products.py). The web-app project's snapshots sit at the top of
# the snapshots folder. A second product root's project keeps its
# snapshots in a folder named for its key. Reading only the top folder
# once called every row of a second project dead.
DEFAULT_PROJECT = PRODUCT_ROOTS[products.SHARED_ROOT]


def project_for(path_or_nodeid: str) -> str:
    """The QA Touch project key a test file's cases belong to."""
    return products.home_project(str(path_or_nodeid).split('::', 1)[0])


def other_projects() -> list[str]:
    """The project keys of the product roots other than the web-app root."""
    return sorted(set(products.PRODUCT_ROOTS.values()) - {DEFAULT_PROJECT})


TESTS_ROOTS = [ROOT / p.rstrip('/') for p in PRODUCT_ROOTS]   # config/products.py

DEFAULT_THRESHOLD = 0.45
DEFAULT_CANDIDATES = 3

# Words that carry no meaning for matching a test to a case. Nearly every
# case title starts "Verify ..." and many test docstrings start with an
# article, so these would inflate every score alike.
STOP_WORDS = frozenset((
    'verify', 'verifies', 'verified', 'that', 'the', 'a', 'an', 'is', 'are',
    'of', 'to', 'in', 'on', 'and', 'or', 'with', 'from', 'for', 'by', 'as',
    'at', 'be', 'it', 'its', 'this', 'can', 'when', 'after', 'works',
    'correctly', 'expected', 'behaves', 'functionality', 'general', 'check',
    'checks', 'ensure', 'ensures',
))

# Words in a module name that say which area a test file belongs to.
# Keyed by the module (config/products.py area_of). Used only to rank candidates.
AREA_WORDS = {
    'admin': ('admin', 'user', 'users', 'site', 'sites', 'rule', 'rules',
              'audit', 'general', 'event wall', 'camera group'),
    'chats': ('chat', 'chats', 'message', 'group'),
    'event_wall': ('event wall',),
    'events': ('event', 'events'),
    'insights': ('insight', 'insights', 'widget', 'widgets', 'dashboard'),
    'licenses': ('license', 'licenses', 'licence'),
    'login': ('login', 'logout', 'sign', 'authentication', 'password'),
    'maps': ('map', 'maps'),
    'media': ('media', 'folder', 'folders', 'clip', 'clips'),
    'notifications': ('notification', 'notifications'),
    'search': ('search',),
    'sequences': ('sequence', 'sequences'),
    'views': ('view', 'views', 'tile', 'camera', 'playback', 'bookmark',
              'fullscreen', 'ptz'),
}


# ------------------------------------------------------------------ inputs

def collect_tests(root: Path | None = None) -> dict[str, dict]:
    """Every test function under root (default: every product root), keyed
    by base node id (no params).

    Parsed with ast, so nothing imports or runs. The title is the first
    docstring line, exactly as the run report shows it.
    """
    tests: dict[str, dict] = {}
    roots = [root] if root else TESTS_ROOTS
    for path in sorted(p for r in roots for p in r.rglob('test_*.py')):
        rel = path.relative_to(ROOT).as_posix()
        area = area_of(rel) or ''
        tree = ast.parse(path.read_text(encoding='utf-8-sig'), filename=rel)

        def add(prefix: str, fn: ast.AST, rel=rel, area=area) -> None:
            nodeid = f'{rel}::{prefix}{fn.name}'
            tests[nodeid] = {
                'nodeid': nodeid,
                'file': rel,
                'area': area,
                'project': project_for(rel),
                'title': readable_title(nodeid, ast.get_docstring(fn)),
            }

        for node in tree.body:
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                if node.name.startswith('test'):
                    add('', node)
            elif isinstance(node, ast.ClassDef) and node.name.startswith('Test'):
                for sub in node.body:
                    if isinstance(sub, ast.FunctionDef | ast.AsyncFunctionDef) \
                            and sub.name.startswith('test'):
                        add(f'{node.name}::', sub)
    return tests


def latest_snapshot() -> Path | None:
    """The newest web-app project snapshot (the top of the snapshots folder)."""
    files = sorted(SNAPSHOTS_DIR.glob('snapshot_*.json'))
    return files[-1] if files else None


def latest_snapshots() -> dict[str, Path]:
    """project key -> its newest snapshot, for every project a test root maps to."""
    found: dict[str, Path] = {}
    top = latest_snapshot()
    if top:
        found[DEFAULT_PROJECT] = top
    for project in other_projects():
        files = sorted((SNAPSHOTS_DIR / project).glob('snapshot_*.json'))
        if files:
            found[project] = files[-1]
    return found


def load_all_cases(paths: dict[str, Path]) -> tuple[dict[str, dict], str]:
    """Every project's cases in one dict, each tagged with its project,
    plus one label naming the files."""
    cases: dict[str, dict] = {}
    labels = []
    for project, path in sorted(paths.items()):
        loaded, label = load_cases(path)
        for case in loaded.values():
            case['project'] = project
        cases.update(loaded)
        labels.append(f'{project}: {label}')
    return cases, ' + '.join(labels)


def load_cases(path: Path) -> tuple[dict[str, dict], str]:
    """case_key -> {key, title, module} from a snapshot-shaped file, plus
    the label to print for where the cases came from."""
    data = json.loads(path.read_text(encoding='utf-8'))
    cases: dict[str, dict] = {}
    for c in data.get('cases', []):
        key = str(c.get('case_key') or '')
        if not key:
            continue
        cases[key] = {
            'key': key,
            'title': str(c.get('case_title') or '').strip(),
            'module': str(c.get('module_name') or c.get('module name') or '').strip(),
        }
    stamp = data.get('snapshot_time') or data.get('snapshot_date') \
        or data.get('pulled') or ''
    label = f'{path.name} ({stamp})' if stamp else path.name
    return cases, label


# ----------------------------------------------------------------- scoring

def _words(text: str) -> set[str]:
    return {w for w in re.findall(r'[a-z0-9]+', text.lower()) if w not in STOP_WORDS}


def _overlap(a: str, b: str) -> float:
    """Word overlap (Jaccard) of two titles, stop words removed."""
    wa, wb = _words(a), _words(b)
    return len(wa & wb) / len(wa | wb) if (wa | wb) else 0.0


def similarity(a: str, b: str) -> float:
    """0 to 1. The larger of word overlap (Jaccard) and difflib's ratio."""
    ratio = difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()
    return round(max(_overlap(a, b), ratio), 2)


# difflib is slow on 3000 titles. Word overlap ranks the whole catalogue,
# and only this many leaders get the full score.
SHORTLIST = 40


def candidates(test: dict, cases: dict[str, dict], limit: int) -> list[dict]:
    """The cases whose titles best match the test title, best first.

    A case in a module named for the test's area ranks a little higher,
    so a Views test prefers a Views case over a same-worded Media case.
    """
    words = AREA_WORDS.get(test['area'], ())
    # a test's candidates come from its own project: a test of a second
    # product is never offered a web-app case, however alike the titles read
    project = test.get('project')
    pool = [c for c in cases.values() if not project or c.get('project', project) == project]
    leaders = sorted(pool, key=lambda c: -_overlap(test['title'], c['title']))[:SHORTLIST]
    scored = []
    for c in leaders:
        score = similarity(test['title'], c['title'])
        module = c['module'].lower()
        if words and any(w in module for w in words):
            score = round(score + 0.1, 2)
        scored.append((score, c))
    scored.sort(key=lambda sc: (-sc[0], sc[1]['title']))
    return [{'key': c['key'], 'title': c['title'], 'module': c['module'],
             'score': s} for s, c in scored[:limit]]


# ------------------------------------------------------------------- audit

def unmapped_nodeids(tests: dict[str, dict], mappings: dict) -> list[str]:
    """Base node ids of tests with no mapping row, params ignored.

    Shared with tools/qatouch_cases_from_tests.py --unmapped, so both
    tools name the same set.
    """
    mapped_bases = {function_base(n) for n in mappings}
    return sorted(n for n in tests if n not in mapped_bases)


def dead_key_nodeids(tests: dict[str, dict], mappings: dict,
                     cases: dict[str, dict]) -> list[str]:
    """Base node ids of live tests whose mapped case is in no snapshot.

    The case was deleted, so the row points at nothing. Shared with
    tools/qatouch_cases_from_tests.py --dead-keys.
    """
    dead = set()
    for nodeid, entry in mappings.items():
        base = function_base(nodeid)
        if base in tests and str(entry.get('case_key') or '') not in cases:
            dead.add(base)
    return sorted(dead)


def audit(mapping: dict, tests: dict[str, dict], cases: dict[str, dict],
          threshold: float, limit: int) -> dict:
    mappings = mapping.get('mappings', {})
    rows = []
    by_key: dict[str, set[str]] = {}
    for nodeid, entry in mappings.items():
        base = function_base(nodeid)
        test = tests.get(base)
        key = str(entry.get('case_key') or '')
        case = cases.get(key)
        cached = str(entry.get('case_title') or '').strip()
        current = case['title'] if case else ''
        by_key.setdefault(key, set()).add(base)
        row = {
            'nodeid': nodeid,
            'file': base.split('::', 1)[0],
            'test_title': test['title'] if test else '',
            'case_key': key,
            'cached_title': cached,
            'snapshot_title': current,
            'module': case['module'] if case else str(entry.get('module') or ''),
            'reviewed': entry.get('reviewed') is True,
            'stale': test is None,
            'dead_key': case is None,
            'drift': bool(case) and current != cached,
            'score': None,
            'candidates': [],
        }
        if test:
            row['score'] = similarity(test['title'], current or cached)
            if row['score'] < threshold or row['dead_key']:
                row['candidates'] = candidates(test, cases, limit)
        rows.append(row)

    shared = {k: sorted(bases) for k, bases in by_key.items() if len(bases) > 1}
    unmapped = unmapped_nodeids(tests, mappings)
    unmapped_by_area: dict[str, int] = {}
    for n in unmapped:
        area = tests[n]['area']
        unmapped_by_area[area] = unmapped_by_area.get(area, 0) + 1

    suspects = [r for r in rows if not r['stale'] and not r['dead_key']
                and r['score'] is not None and r['score'] < threshold]
    return {
        'threshold': threshold,
        'counts': {
            'entries': len(rows),
            'tests': len(tests),
            'stale': sum(r['stale'] for r in rows),
            'dead_key': sum(r['dead_key'] for r in rows),
            'drift': sum(r['drift'] for r in rows),
            'suspect': len(suspects),
            'suspect_reviewed': sum(r['reviewed'] for r in suspects),
            'shared_keys': len(shared),
            'unmapped': len(unmapped),
        },
        'unmapped_by_area': dict(sorted(unmapped_by_area.items())),
        'stale': [r['nodeid'] for r in rows if r['stale']],
        'dead_key': [r for r in rows if r['dead_key'] and not r['stale']],
        'drift': [r for r in rows if r['drift']],
        'suspects': sorted(suspects, key=lambda r: (r['score'], r['nodeid'])),
        'shared': shared,
        'rows': rows,
    }


# ------------------------------------------------------------------ output

def _print_row(r: dict) -> None:
    flag = 'reviewed' if r['reviewed'] else 'unreviewed'
    print(f'  {r["score"]!s:>5}  {flag:<10} {r["nodeid"]}')
    print(f'         test: {r["test_title"]}')
    print(f'         case: {r["case_key"]}: {r["snapshot_title"] or r["cached_title"]}'
          f'  [{r["module"]}]')
    for c in r['candidates']:
        print(f'           -> {c["score"]:.2f} {c["key"]}: {c["title"]}  [{c["module"]}]')


def print_report(result: dict, source: str, show_rows: bool) -> None:
    c = result['counts']
    print(f'\nQA Touch mapping audit   cases: {source}')
    print(f'  Mapping rows:          {c["entries"]}')
    print(f'  Tests (product roots): {c["tests"]}')
    print(f'  Stale rows:            {c["stale"]}   (test no longer exists)')
    print(f'  Dead case keys:        {c["dead_key"]}   (case not in the snapshot)')
    print(f'  Title drift:           {c["drift"]}   (case renamed since the row was cached)')
    print(f'  Suspect rows:          {c["suspect"]}   (score below {result["threshold"]}; '
          f'{c["suspect_reviewed"]} of them reviewed)')
    print(f'  Shared case keys:      {c["shared_keys"]}   (claimed by more than one test function)')
    print(f'  Unmapped tests:        {c["unmapped"]}   {result["unmapped_by_area"]}')

    if result['stale']:
        print('\nStale rows:')
        for n in result['stale']:
            print(f'  {n}')
    if result['dead_key']:
        print('\nDead case keys (the case is gone; the row needs a new case):')
        for r in result['dead_key']:
            _print_row(r)
    if result['drift']:
        print('\nTitle drift (cached title is out of date, key unchanged):')
        for r in result['drift']:
            print(f'  {r["case_key"]}  {r["nodeid"]}')
            print(f'         cached:   {r["cached_title"]}')
            print(f'         snapshot: {r["snapshot_title"]}')
    if result['suspects']:
        print('\nSuspect rows (lowest score first, best candidates under each):')
        for r in result['suspects']:
            _print_row(r)
    if result['shared']:
        print('\nShared case keys:')
        for key, bases in result['shared'].items():
            print(f'  {key}  ({len(bases)} functions)')
            for b in bases:
                print(f'      {b}')
    if show_rows:
        print('\nAll rows (score, key, node id, test title | case title):')
        for r in result['rows']:
            print(f'  {r["score"]!s:>5}  {r["case_key"]}  {r["nodeid"]}')
            print(f'         {r["test_title"]} | {r["snapshot_title"] or r["cached_title"]}')


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Read-only audit of config/qatouch_case_mapping.json')
    parser.add_argument('--json', action='store_true', help='Emit the result as JSON')
    parser.add_argument('--threshold', type=float, default=DEFAULT_THRESHOLD,
                        help=f'Rows scoring below this are suspect (default {DEFAULT_THRESHOLD})')
    parser.add_argument('--candidates', type=int, default=DEFAULT_CANDIDATES,
                        help=f'Best-matching cases to list per suspect (default {DEFAULT_CANDIDATES})')
    parser.add_argument('--cases', type=Path, default=None,
                        help='Snapshot-shaped JSON of cases (default: newest snapshot)')
    parser.add_argument('--mapping', type=Path, default=MAPPING_PATH,
                        help='Mapping file to audit (default: the live one)')
    parser.add_argument('--all-rows', action='store_true',
                        help='Text mode: also list every row with its score')
    args = parser.parse_args()

    paths = latest_snapshots()
    if args.cases:
        paths[DEFAULT_PROJECT] = args.cases
    if DEFAULT_PROJECT not in paths or not paths[DEFAULT_PROJECT].exists():
        print('No case snapshot found under config/qatouch_snapshots/. '
              'Pass --cases with a snapshot-shaped JSON file.', file=sys.stderr)
        return 2
    cases, source = load_all_cases(paths)
    result = audit(load_raw(args.mapping), collect_tests(), cases,
                   args.threshold, args.candidates)
    result['source'] = source
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_report(result, source, args.all_rows)
    return 0


if __name__ == '__main__':
    sys.exit(main())
