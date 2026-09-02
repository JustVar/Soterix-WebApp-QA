#!/usr/bin/env python3
"""The test-to-case mapping, with a review gate and a rename guard.

config/qatouch_case_mapping.json links pytest nodeids to QA Touch cases.
Most of its rows were AUTO-MATCHED by word overlap - guesses, not links.
Now that uploads actually land (08/17), an unreviewed guess writes real
Pass/Fail onto a case no test verifies. So:

  A mapping row is a PROPOSAL until a human marks it reviewed.
  Only reviewed rows are used by the reporter, run_suite and mode sync.

Rows also break silently on rename: the mapping is keyed by nodeid, so
renaming a test orphans its row and the case quietly stops receiving
results. `check` finds those statically (no pytest start-up).

    python tools/qatouch_mapping.py status              # counts
    python tools/qatouch_mapping.py check               # exit 1 on orphaned rows
    python tools/qatouch_mapping.py list-unreviewed     # what needs review
    python tools/qatouch_mapping.py mark-reviewed --file tests/ui/views/test_views_basic.py
    python tools/qatouch_mapping.py mark-reviewed --nodeid <nodeid>
    python tools/qatouch_mapping.py unmark --nodeid <nodeid>

Marking reviewed is a statement that YOU checked the test really verifies
that case. Mark a whole file only after reading its rows.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAPPING_PATH = ROOT / 'config' / 'qatouch_case_mapping.json'

_PARAM_RE = re.compile(r'\[.*\]$')


def load_raw(path: Path = MAPPING_PATH) -> dict:
    """The whole mapping file, as stored."""
    if not path.exists():
        raise FileNotFoundError(
            f'Mapping file missing: {path}. Build it: python tools/qatouch_mapper.py build')
    return json.loads(path.read_text(encoding='utf-8'))


def save_raw(data: dict, path: Path = MAPPING_PATH) -> None:
    mappings = data.get('mappings', {})
    data['total_mapped'] = len(mappings)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')


def reviewed_lookup(path: Path = MAPPING_PATH) -> tuple[dict[str, str], dict[str, int]]:
    """nodeid -> case_key for REVIEWED rows only, plus counts for reporting.

    counts: {'total', 'reviewed', 'unreviewed'} - print them wherever the
    lookup is used, so skipped rows are never silent.
    """
    mappings = load_raw(path).get('mappings', {})
    reviewed = {n: e['case_key'] for n, e in mappings.items() if e.get('reviewed') is True}
    return reviewed, {
        'total': len(mappings),
        'reviewed': len(reviewed),
        'unreviewed': len(mappings) - len(reviewed),
    }


# function_base and base_keyed are duplicated in soterix-qa-shared
# (soterix_qa_shared/qatouch/mapping.py) - the reporter there needs them.
# Re-export from the package when convenient.
#
# Until then: change BOTH, or neither. Nothing detects the drift, and the
# docstrings had already diverged within a day of the copy being made - which
# is how long it takes.
def function_base(nodeid: str) -> str:
    """Strip the [param] suffix: file::Class::test_x[chromium] -> file::Class::test_x."""
    return _PARAM_RE.sub('', nodeid)


def nodeids_in_file(file_path: Path, rel: str) -> tuple[set[str], str | None]:
    """Test node ids defined in one file, without params, and any parse error.

    Parsed with ast, so nothing imports or runs. Class-aware, and it
    recurses into nested classes, because a method's node id carries its
    class path: that is what makes a class rename visible.

    Reads bytes rather than text so ast honours a source's own coding
    declaration. Reading as utf-8 raised UnicodeDecodeError on a latin-1
    file, and UnicodeDecodeError is a ValueError, so neither OSError nor
    SyntaxError caught it and the guard crashed instead of reporting.

    Returns (nodeids, error). A file that cannot be read or parsed yields
    an empty set AND an error string, so the caller can say "could not
    parse" instead of reporting every row in that file as a rename.
    """
    try:
        tree = ast.parse(file_path.read_bytes(), filename=rel)
    except FileNotFoundError:
        return set(), None                      # a deleted file IS a real orphan
    except (OSError, SyntaxError, ValueError) as exc:
        return set(), f'{type(exc).__name__}: {exc}'

    found: set[str] = set()

    def walk(node: ast.AST, prefix: str) -> None:
        for child in node.body:
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                found.add(f'{rel}::{prefix}{child.name}')
            elif isinstance(child, ast.ClassDef):
                walk(child, f'{prefix}{child.name}::')

    walk(tree, '')
    return found, None


def orphaned_nodeids(path: Path = MAPPING_PATH, root: Path = ROOT) -> list[str]:
    """Mapping rows whose test no longer exists, found WITHOUT running pytest.

    A row is orphaned when the file it names no longer defines that exact
    test: a rename, a move, a class rename, or a delete happened, and the
    case silently stops receiving results.

    Each referenced file is parsed with ast and the WHOLE node id is
    compared, class segment included. The previous implementation searched
    the file's text for `def <function>`, which saw neither the class nor a
    move: renaming a class silenced 12 of 121 reviewed rows while this
    guard still reported all-clear. Measured against four realistic
    refactors, the text check caught none and this one catches all four.
    """
    orphans, _ = orphaned_and_unparseable(path, root)
    return orphans


def orphaned_and_unparseable(
    path: Path = MAPPING_PATH, root: Path = ROOT,
) -> tuple[list[str], dict[str, str]]:
    """Orphaned rows, and the files that could not be parsed.

    Kept separate on purpose. A file with a syntax error yields no node
    ids, so folding it into the orphan list reports every row in it as a
    rename and hides the real cause: a typo in a work-in-progress file
    would print a wall of phantom renames.
    """
    mappings = load_raw(path).get('mappings', {})
    orphans: list[str] = []
    unparseable: dict[str, str] = {}
    file_cache: dict[str, set[str]] = {}
    for nodeid in mappings:
        rel = nodeid.split('::')[0]
        if rel not in file_cache:
            found, error = nodeids_in_file(root / rel, rel)
            file_cache[rel] = found
            if error:
                unparseable[rel] = error
        if rel in unparseable:
            continue
        if function_base(nodeid) not in file_cache[rel]:
            orphans.append(nodeid)
    return orphans, unparseable


def base_keyed(mapping: dict[str, str]) -> dict[str, str]:
    """function_base(nodeid) -> case_key, for rows that agree.

    Mapping keys carry the parametrization they were generated under: 377
    of 378 rows end in [chromium], because that is what pytest.ini pins.
    The reporter strips the param from the RUNTIME nodeid but the stored
    key keeps it, so running under another browser matched 0 of 121
    reviewed rows, and an Appium suite (no bracket at all) would match
    none either.

    Collapsing both sides to the bare function makes the mapping
    parametrization-agnostic. A base whose rows disagree on the case key is
    left out: that is a genuine ambiguity the exact match must settle, and
    guessing would write a status onto the wrong case.
    """
    collapsed: dict[str, str] = {}
    conflicting: set[str] = set()
    for nodeid, case_key in mapping.items():
        base = function_base(nodeid)
        if base in collapsed and collapsed[base] != case_key:
            conflicting.add(base)
        collapsed[base] = case_key
    for base in conflicting:
        collapsed.pop(base, None)
    return collapsed


def shared_across_functions(mappings: dict) -> dict[str, list[str]]:
    """case_key -> nodeids, for keys claimed by MORE THAN ONE test function.

    Params of one function sharing a case is normal; different functions
    (worse, different files) sharing one case means at least one row is a
    bad guess - the case's result would be overwritten by an unrelated test.
    """
    by_key: dict[str, set[str]] = {}
    rows: dict[str, list[str]] = {}
    for nodeid, e in mappings.items():
        k = e['case_key']
        by_key.setdefault(k, set()).add(function_base(nodeid))
        rows.setdefault(k, []).append(nodeid)
    return {k: rows[k] for k, bases in by_key.items() if len(bases) > 1}


# ---------------------------------------------------------------- commands

def cmd_status(_args) -> int:
    data = load_raw()
    mappings = data.get('mappings', {})
    _, counts = reviewed_lookup()
    shared = shared_across_functions(mappings)
    orphans = orphaned_nodeids()
    print(f'\n  Rows:                {counts["total"]}')
    print(f'  Reviewed (usable):   {counts["reviewed"]}')
    print(f'  Unreviewed:          {counts["unreviewed"]}   <- proposals; nothing uploads for these')
    print(f'  Orphaned (renamed):  {len(orphans)}')
    print(f'  Cases shared across different test functions: {len(shared)}')
    if orphans:
        print('\n  Orphaned rows (fix the nodeid or delete the row):')
        for n in orphans[:10]:
            print(f'    {n}')
    return 0


def cmd_check(_args) -> int:
    """Exit 1 when a mapped test no longer exists. For hooks and run_suite."""
    orphans = orphaned_nodeids()
    if orphans:
        print(f'MAPPING RENAME GUARD: {len(orphans)} mapped test(s) no longer exist. '
              f'A renamed test silently stops reporting to its case.')
        for n in orphans:
            print(f'  {n}')
        print('Fix: update the nodeid in config/qatouch_case_mapping.json, or delete the row.')
        return 1
    print('Mapping rename guard: all mapped tests exist.')
    return 0


def cmd_list_unreviewed(_args) -> int:
    mappings = load_raw().get('mappings', {})
    rows = [(n, e) for n, e in sorted(mappings.items()) if e.get('reviewed') is not True]
    print(f'\n  {len(rows)} unreviewed row(s). Review = confirm the test really '
          f'verifies the case, then mark-reviewed.\n')
    for n, e in rows:
        print(f'  {e["case_key"]}  score={e.get("score", "?"):<5} {n}')
        print(f'      -> {e.get("case_title", "?")[:75]}')
    return 0


def _mark(nodeids: list[str], value: bool) -> int:
    data = load_raw()
    mappings = data.get('mappings', {})
    missing = [n for n in nodeids if n not in mappings]
    if missing:
        print('Not in the mapping:')
        for n in missing:
            print(f'  {n}')
        return 2
    for n in nodeids:
        mappings[n]['reviewed'] = value
    save_raw(data)
    print(f'{"Marked" if value else "Unmarked"} {len(nodeids)} row(s).')
    return 0


def cmd_mark(args) -> int:
    mappings = load_raw().get('mappings', {})
    if args.nodeid:
        return _mark([args.nodeid], True)
    if args.file:
        prefix = args.file.replace('\\', '/')
        hits = [n for n in mappings if n.replace('\\', '/').startswith(prefix)]
        if not hits:
            print(f'No mapping rows under {prefix}')
            return 2
        print(f'Marking {len(hits)} row(s) under {prefix} as reviewed.')
        return _mark(hits, True)
    print('Give --nodeid or --file.')
    return 2


def cmd_unmark(args) -> int:
    return _mark([args.nodeid], False)


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Review gate and rename guard for the test-to-case mapping')
    sub = parser.add_subparsers(dest='command')
    sub.add_parser('status', help='Counts: reviewed / unreviewed / orphaned / shared')
    sub.add_parser('check', help='Exit 1 when a mapped test no longer exists')
    sub.add_parser('list-unreviewed', help='Rows waiting for human review')
    m = sub.add_parser('mark-reviewed', help='Mark rows reviewed after checking them')
    m.add_argument('--nodeid', default='', help='One exact nodeid')
    m.add_argument('--file', default='', help='Every row whose nodeid starts with this path')
    u = sub.add_parser('unmark', help='Return a row to proposal status')
    u.add_argument('--nodeid', required=True)
    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return 0
    return {'status': cmd_status, 'check': cmd_check,
            'list-unreviewed': cmd_list_unreviewed,
            'mark-reviewed': cmd_mark, 'unmark': cmd_unmark}[args.command](args)


if __name__ == '__main__':
    sys.exit(main())
