#!/usr/bin/env python3
"""Write docs/TEST_INVENTORY.md: every product test in this repo, by product and module.

The question it answers is "what do we actually test?", asked 09/08/2026 when
a stale README line said 1,416 tests. The honest number is the count of test
FUNCTIONS under tests/ui; pytest's collected count multiplies the c2c tests
over the camera registry and every UI test over the browser. Pins under
tests/tools, tests/plugins and tests/helpers test the harness, not the
product, and are not listed here.

Usage:
  python tools/test_inventory.py            # rewrite docs/TEST_INVENTORY.md
  python tools/test_inventory.py --check    # exit 1 when the file is stale
  python tools/test_inventory.py --record   # append today's counts to the ledger, then rewrite
  python tools/test_inventory.py --backfill # rebuild the ledger's history from git, then rewrite

Each row names the test, its title (the docstring's first line), whether it
carries a human-written Steps block, and its QA Touch case key(s) from
config/qatouch_case_mapping.json. Titles come from the docstrings, so a poor
title here is a poor docstring there. The file carries no date, so --check
can compare it byte for byte; the counts in it are the record.

Growth is tracked in history/test_counts.jsonl: one row per recording with
the test-function count per product and per module. --record appends a row
only when the counts moved, so the ledger reads as a history of change.
--backfill counts the tests at the last commit of every week since the
Python suites began (02/2026), by `git grep` on each commit, so the curve
does not start on the day someone first asked for it. The sibling API repo
(../Soterix-API-QA) is counted as its own product when it is checked out
beside this one; the API tests lived under tests/api/ here until 08/07/2026.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plugins import products  # noqa: E402  (the shim configures this repo's path rules)
from tools import (  # noqa: E402
    qatouch_ledger,
    qatouch_mapping as qm,
)
from tools.qatouch_cases_from_tests import TestInfo, parse_docstring, scan_tests  # noqa: E402

OUT = ROOT / 'docs' / 'TEST_INVENTORY.md'
HISTORY = ROOT / 'history' / 'test_counts.jsonl'
API_REPO = ROOT.parent / 'Soterix-API-QA'
NO_TITLE = '(no docstring)'

PRODUCT_CORE = 'NexaiQ-Core'
PRODUCT_C2C = 'NexaiQ-Camera 2 Cloud'
PRODUCT_API = 'NexaiQ-Core API'
# The first week that held Python product tests. Before it the repo carried
# the JavaScript prototype and the Selenium suite, neither counted here.
BACKFILL_FROM = dt.date(2026, 2, 1)
TEST_DEF_PATTERN = r'^\s*(async )?def test_'
# Directories under tests/ that pin the harness rather than a product.
HARNESS_DIRS = ('tests/legacy', 'tests/tools/', 'tests/plugins/', 'tests/helpers/',
                'tests/unit/', 'tests/shared/', 'tests/data/', 'tests/steps/')


@dataclass(frozen=True)
class Row:
    product: str
    module: str
    nodeid: str
    title: str
    has_steps: bool
    case_keys: tuple[str, ...]
    parametrized: bool

    @property
    def file(self) -> str:
        return self.nodeid.partition('::')[0]


# Every test that is not a product test, by where it lives, and what it is.
# A test file under tests/ that matches none of these and no product rule
# shows up on the page as "unclassified", so nothing sits uncounted.
OTHER_KINDS: tuple[tuple[str, str, str], ...] = (
    ('tests/tools/', 'Pins for the repo tools (tools/*.py): QA Touch import and mapping, convention '
                     'checker, tenant cleanup, run CLI, inventory. Collected by bare pytest.', 'yes'),
    ('tests/plugins/', 'Pins for the pytest plugins and the shims over the shared package: run guard, '
                       'archive, report media, env guard, products. Collected by bare pytest.', 'yes'),
    ('tests/helpers/', 'Pins for tests/shared/helpers (surface, search_job). Collected by bare pytest.', 'yes'),
    ('tests/legacy/', 'Retired Selenium-era login and web-client tests, kept for reference. Excluded from '
                      'collection by pytest.ini norecursedirs.', 'no'),
    ('legacy-selenium-tests/', 'The pre-migration Selenium suite. Excluded from collection.', 'no'),
)
SIBLING_KINDS: tuple[tuple[Path, str, str], ...] = (
    (ROOT.parent / 'soterix-qa-shared' / 'tests',
     'Pins for the shared QA package (QA Touch client, result reporter, run archive and report, gates). '
     'Run in that repo; this repo pins a release tag.', 'soterix-qa-shared'),
    (API_REPO / 'tests' / 'plugins',
     'Pins for the API repo\'s own plugins and shims. Run in that repo.', 'Soterix-API-QA'),
)


def product_of(nodeid: str) -> str:
    key = products.product_for(nodeid)
    return products.PRODUCTS.get(key, key)


def inventory_rows(tests: dict[str, TestInfo], mapping: dict[str, dict]) -> list[Row]:
    """One row per test function, sorted by product, module and node id."""
    keys: dict[str, set[str]] = defaultdict(set)
    for name, row in mapping.items():
        if (row or {}).get('case_key'):
            keys[qm.function_base(name)].add(row['case_key'])
    rows = []
    for nodeid, info in tests.items():
        doc = parse_docstring(info.docstring, nodeid)
        # parse_docstring names a docstring-less test after its function
        # ("No doc" for test_no_doc), the same title QA Touch would get
        rows.append(Row(
            product=product_of(nodeid),
            module=info.area,
            nodeid=nodeid,
            title=(doc.title or '').strip() or NO_TITLE,
            has_steps=bool(doc.steps) and not doc.problem,
            case_keys=tuple(sorted(keys.get(nodeid, ()))),
            parametrized=info.parametrized,
        ))
    return sorted(rows, key=lambda r: (r.product, r.module, r.nodeid))


def _cell(text: str) -> str:
    return text.replace('|', '\\|').replace('\n', ' ').strip()


def _short(nodeid: str) -> str:
    file, _, rest = nodeid.partition('::')
    return f"{Path(file).name}::{rest}"


def render(rows: list[Row], history: list[dict] | None = None,
           other: list[dict] | None = None, qatouch_history: list[dict] | None = None) -> str:
    """The Markdown page. Totals first, then growth (tests, then QA Touch cases),
    then the non-product tests, then one table per product and module."""
    by_product: dict[str, list[Row]] = defaultdict(list)
    for r in rows:
        by_product[r.product].append(r)
    out = [
        '# Product test inventory',
        '',
        'Every test in this repo that exercises a product, by product and module.',
        'Generated by `python tools/test_inventory.py` from the test files, their',
        'docstrings and `config/qatouch_case_mapping.json`; rerun it after adding',
        'or renaming a test (`--check` tells you when it is stale). Tests that pin',
        'the harness rather than a product are counted separately under "Harness',
        'and other tests", so every test file under tests/ is accounted for once.',
        'Pytest collects more items than there are rows here: the c2c tests',
        'parametrize over the camera registry and every UI test carries the',
        'browser parameter.',
        '',
        '| Product | Modules | Files | Test functions | With Steps | Mapped to QA Touch |',
        '|---|---|---|---|---|---|',
    ]
    for product, prows in sorted(by_product.items()):
        modules = len({r.module for r in prows})
        files = len({r.file for r in prows})
        out.append(f"| {product} | {modules} | {files} | {len(prows)} | "
                   f"{sum(r.has_steps for r in prows)} | {sum(bool(r.case_keys) for r in prows)} |")
    out.append(f"| **Total** | | **{len({r.file for r in rows})}** | **{len(rows)}** | "
               f"**{sum(r.has_steps for r in rows)}** | **{sum(bool(r.case_keys) for r in rows)}** |")
    out.append('')
    out += render_growth(history or [])
    out += qatouch_ledger.render_growth(qatouch_history or [])
    out += render_other(other or [])
    for product, prows in sorted(by_product.items()):
        out += [f'## {product}', '']
        by_module: dict[str, list[Row]] = defaultdict(list)
        for r in prows:
            by_module[r.module].append(r)
        for module, mrows in sorted(by_module.items()):
            files = len({r.file for r in mrows})
            out += [f'### {module} ({len(mrows)} tests in {files} file{"s" if files != 1 else ""})', '',
                    '| Test | Title | Steps | QA Touch |', '|---|---|---|---|']
            for r in mrows:
                test = _cell(_short(r.nodeid)) + (' (parametrized)' if r.parametrized else '')
                out.append(f"| `{test}` | {_cell(r.title)} | {'yes' if r.has_steps else '-'} | "
                           f"{', '.join(r.case_keys) or '-'} |")
            out.append('')
    return '\n'.join(out).rstrip('\n') + '\n'


# --- growth: the ledger -------------------------------------------------------
#
# A ledger row is {"date", "commit", "source", "products": {name: {"functions",
# "steps", "mapped"}}, "modules": {module: functions}}. "steps" and "mapped"
# are null on backfilled rows: they need the docstrings and the mapping file
# as they were, and the function count is the growth question.


def classify(path: str) -> str | None:
    """The product a test file counts toward, at any point in the repo's history.

    None for harness pins, the legacy suites and anything outside tests/.
    The API suites lived under tests/api/ here until 08/07/2026 and under
    tests/internal_api and tests/integration_api in the sibling repo since.
    """
    p = path.replace('\\', '/')
    if not p.startswith('tests/') or p.startswith(HARNESS_DIRS):
        return None
    if p.startswith('tests/ui/c2c/'):
        return PRODUCT_C2C
    if p.startswith('tests/ui/'):
        return PRODUCT_CORE
    # tests/smoke/ is the API repo's first layout (08/07-08/19/2026), before
    # its suites were split into internal_api and integration_api
    if p.startswith(('tests/api/', 'tests/internal_api/', 'tests/integration_api/', 'tests/smoke/')):
        return PRODUCT_API
    return None


def module_of(path: str) -> str | None:
    """The tests/ui module a file belongs to ('admin', 'c2c'), else None."""
    parts = path.replace('\\', '/').split('/')
    return parts[2] if len(parts) > 3 and parts[:2] == ['tests', 'ui'] else None


def counts_from_files(file_counts: dict[str, int]) -> tuple[dict[str, int], dict[str, int]]:
    """Per-product and per-module test-function totals from {file: count}."""
    products: dict[str, int] = defaultdict(int)
    modules: dict[str, int] = defaultdict(int)
    for path, count in file_counts.items():
        product = classify(path)
        if product is None or not count:
            continue
        products[product] += count
        module = module_of(path)
        if module:
            modules[module] += count
    return dict(sorted(products.items())), dict(sorted(modules.items()))


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True,
                            text=True, encoding='utf-8', errors='replace', check=False)
    return result.stdout if result.returncode == 0 else ''


def git_test_counts(repo: Path, commit: str) -> dict[str, int]:
    """{file: test functions} at a commit, by git grep; no checkout needed."""
    out = _git(repo, 'grep', '-c', '-E', TEST_DEF_PATTERN, commit, '--', 'tests/')
    counts: dict[str, int] = {}
    for line in out.splitlines():
        # "<commit>:<path>:<count>"
        _, _, rest = line.partition(':')
        path, _, count = rest.rpartition(':')
        if path.endswith('.py') and Path(path).name.startswith('test_') and count.isdigit():
            counts[path] = int(count)
    return counts


def weekly_commits(repo: Path, since: dt.date, paths: tuple[str, ...] = ('tests',)) -> list[tuple[dt.date, str]]:
    """The last mainline commit of every ISO week that touched `paths`, oldest first.

    --first-parent keeps to the branch's own line: without it the walk
    visits merged side branches, whose trees can be weeks behind (a row
    with no c2c tests appeared between two rows that had them).
    """
    out = _git(repo, 'log', '--first-parent', f'--since={since.isoformat()}', '--format=%as %h', '--', *paths)
    by_week: dict[tuple[int, int], tuple[dt.date, str]] = {}
    for line in out.splitlines():
        day, _, commit = line.partition(' ')
        date = dt.date.fromisoformat(day)
        week = date.isocalendar()[:2]
        if week not in by_week or date > by_week[week][0]:
            by_week[week] = (date, commit)
    return sorted(by_week.values())


def api_repo_counts(at: dt.date | None = None) -> dict[str, int] | None:
    """The sibling API repo's {file: count} at HEAD, or at its last commit on
    or before `at`. None when the repo is not checked out beside this one."""
    if not (API_REPO / '.git').exists():
        return None
    commit = 'HEAD'
    if at is not None:
        found = _git(API_REPO, 'log', '-1', f'--until={at.isoformat()}T23:59:59', '--format=%h', '--', 'tests').strip()
        if not found:
            return {}
        commit = found
    return git_test_counts(API_REPO, commit)


def _merge_api(products: dict[str, int], api_counts: dict[str, int] | None) -> dict[str, int]:
    if api_counts:
        api_products, _ = counts_from_files(api_counts)
        products = dict(products)
        products[PRODUCT_API] = products.get(PRODUCT_API, 0) + api_products.get(PRODUCT_API, 0)
    return dict(sorted(products.items()))


def files_by_product(file_counts: dict[str, int]) -> dict[str, int]:
    """How many test FILES each product has, from {file: count}."""
    files: dict[str, set[str]] = defaultdict(set)
    for path, count in file_counts.items():
        product = classify(path)
        if product is not None and count:
            files[product].add(path)
    return {k: len(v) for k, v in sorted(files.items())}


def ledger_row(date: dt.date, commit: str, source: str, products: dict[str, int],
               modules: dict[str, int], detail: dict[str, dict] | None = None,
               files: dict[str, int] | None = None) -> dict:
    return {
        'date': date.isoformat(), 'commit': commit, 'source': source,
        'products': {name: {'functions': n,
                            'files': (files or {}).get(name),
                            'steps': (detail or {}).get(name, {}).get('steps'),
                            'mapped': (detail or {}).get(name, {}).get('mapped')}
                     for name, n in sorted(products.items())},
        'modules': dict(sorted(modules.items())),
    }


def backfill(repo: Path = ROOT, since: dt.date = BACKFILL_FROM) -> list[dict]:
    """Ledger rows for the last commit of every week since `since`."""
    rows = []
    for date, commit in weekly_commits(repo, since):
        here = git_test_counts(repo, commit)
        api = api_repo_counts(at=date) or {}
        products, modules = counts_from_files(here)
        products = _merge_api(products, api)
        files = files_by_product({**here, **api})
        rows.append(ledger_row(date, commit, 'backfill', products, modules, files=files))
    return rows


def snapshot_row(inventory: list[Row], date: dt.date, commit: str) -> dict:
    """Today's ledger row from the rendered inventory rows, with steps and mapping."""
    products: dict[str, int] = defaultdict(int)
    modules: dict[str, int] = defaultdict(int)
    files: dict[str, set[str]] = defaultdict(set)
    detail: dict[str, dict] = defaultdict(lambda: {'steps': 0, 'mapped': 0})
    for r in inventory:
        products[r.product] += 1
        modules[r.module] += 1
        files[r.product].add(r.file)
        detail[r.product]['steps'] += int(r.has_steps)
        detail[r.product]['mapped'] += int(bool(r.case_keys))
    api = api_repo_counts() or {}
    merged = _merge_api(dict(products), api)
    file_counts = {k: len(v) for k, v in files.items()}
    file_counts.update(files_by_product(api))
    return ledger_row(date, commit, 'record', merged, dict(modules), detail, files=file_counts)


def same_counts(a: dict, b: dict) -> bool:
    """True when two rows count the same tests (dates and commits aside)."""
    fa = {k: v['functions'] for k, v in a.get('products', {}).items()}
    fb = {k: v['functions'] for k, v in b.get('products', {}).items()}
    return fa == fb and a.get('modules') == b.get('modules')


def merge_record(history: list[dict], row: dict) -> tuple[list[dict], str]:
    """Where a new recorded row goes: replacing the same day's last row (a
    backfilled row for today lacks the Steps and mapping counts the record
    carries, and two recordings in one day are one day's state), nowhere
    when the counts did not move, else appended. Returns the new history and
    one word saying which."""
    if history and history[-1]['date'] == row['date']:
        return [*history[:-1], row], 'replaced'
    if history and same_counts(history[-1], row):
        return history, 'unchanged'
    return [*history, row], 'appended'


def load_history(path: Path = HISTORY) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def save_history(rows: list[dict], path: Path = HISTORY) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows), encoding='utf-8', newline='\n')


def render_growth(history: list[dict]) -> list[str]:
    """The Growth section: one line per ledger row, newest first."""
    if not history:
        return ['## Growth', '', 'No ledger yet. `python tools/test_inventory.py --backfill` builds one from git.', '']
    products = sorted({p for row in history for p in row.get('products', {})})
    out = ['## Growth', '',
           'Test functions per product at the last commit of each week (`history/test_counts.jsonl`).',
           'Rows marked record also carry how many tests had Steps and a QA Touch case that day;',
           'backfilled rows count functions only. Append a row with `--record` after a batch of tests lands.',
           '',
           '| Date | Commit | ' + ' | '.join(products) + ' | Total | Files | With Steps | Mapped | Source |',
           '|---|---|' + '---|' * len(products) + '---|---|---|---|---|']
    for row in sorted(history, key=lambda r: (r['date'], r['commit']), reverse=True):
        counts = row.get('products', {})
        total = sum(v['functions'] for v in counts.values())
        files = [v.get('files') for v in counts.values() if v.get('files') is not None]
        steps = [v.get('steps') for v in counts.values() if v.get('steps') is not None]
        mapped = [v.get('mapped') for v in counts.values() if v.get('mapped') is not None]
        cells = [str(counts[p]['functions']) if p in counts else '-' for p in products]
        out.append(f"| {row['date']} | {row['commit']} | " + ' | '.join(cells)
                   + f" | {total} | {sum(files) if files else '-'} | {sum(steps) if steps else '-'}"
                   + f" | {sum(mapped) if mapped else '-'} | {row.get('source', '-')} |")
    out.append('')
    return out


# --- the other tests -----------------------------------------------------------


def count_functions(path: Path) -> int:
    """Test functions in one file, by the same pattern git grep uses."""
    import re
    try:
        text = path.read_text(encoding='utf-8', errors='replace')
    except OSError:
        return 0
    return len(re.findall(TEST_DEF_PATTERN, text, re.M))


def other_kinds(file_counts: dict[str, int],
                siblings: list[tuple[str, dict[str, int], str, str]] | None = None) -> list[dict]:
    """Group every non-product test file into a kind: {where, files, functions, what, collected}.

    `file_counts` is {repo-relative path: test functions} for this repo, product
    files included (they are skipped here). `siblings` are (label, file_counts,
    description, collected) for repos checked out beside this one. A file that
    is neither a product test nor a known kind lands in an "unclassified" kind
    named after its directory, so it is seen rather than lost.
    """
    kinds: dict[str, dict] = {}
    for path, count in sorted(file_counts.items()):
        p = path.replace('\\', '/')
        if classify(p) is not None or not Path(p).name.startswith('test_') or not p.endswith('.py'):
            continue
        known = next((kind for kind in OTHER_KINDS if p.startswith(kind[0])), None)
        if known:
            key, what, collected = known
        else:
            key = 'unclassified: ' + '/'.join(p.split('/')[:-1]) + '/'
            what = 'Not a product test by tools/test_inventory.py and not a known kind: add a rule for it.'
            collected = 'yes' if p.startswith('tests/') else 'no'
        kind = kinds.setdefault(key, {'where': key, 'files': 0, 'functions': 0, 'what': what, 'collected': collected})
        kind['files'] += 1
        kind['functions'] += count
    for label, counts, what, collected in siblings or []:
        files = [c for c in counts.values() if c]
        kinds[label] = {'where': label, 'files': len(files), 'functions': sum(files), 'what': what, 'collected': collected}
    return list(kinds.values())


def collect_other(root: Path = ROOT) -> list[dict]:
    """Walk this repo's test files and the sibling repos' pins."""
    file_counts: dict[str, int] = {}
    for base in ('tests', 'legacy-selenium-tests'):
        for path in sorted((root / base).rglob('test_*.py')):
            file_counts[path.relative_to(root).as_posix()] = count_functions(path)
    siblings = []
    for folder, what, label in SIBLING_KINDS:
        if folder.exists():
            counts = {p.as_posix(): count_functions(p) for p in sorted(folder.rglob('test_*.py'))}
            siblings.append((label, counts, what, f'in {label}'))
    return other_kinds(file_counts, siblings)


def render_other(kinds: list[dict]) -> list[str]:
    """The section that keeps the non-product tests from going uncounted."""
    out = ['## Harness and other tests', '',
           'Tests that are not product tests, so the product counts above stay honest and',
           'nothing is lost. "Collected" says whether bare `pytest` in this repo runs them.',
           '',
           '| Where | Files | Test functions | Collected | What they are |', '|---|---|---|---|---|']
    for k in kinds:
        flag = ' **(unclassified)**' if k['where'].startswith('unclassified') else ''
        out.append(f"| `{k['where']}`{flag} | {k['files']} | {k['functions']} | {k['collected']} | {_cell(k['what'])} |")
    if kinds:
        here = [k for k in kinds if not k['collected'].startswith('in ')]
        out.append(f"| **This repo** | **{sum(k['files'] for k in here)}** | **{sum(k['functions'] for k in here)}** | | |")
    out.append('')
    return out


# --- entry points --------------------------------------------------------------


def current_rows() -> list[Row]:
    tests = scan_tests()
    mapping = qm.load_raw().get('mappings', {})
    return inventory_rows(tests, mapping)


def build(history_path: Path = HISTORY) -> str:
    return render(current_rows(), load_history(history_path), collect_other(),
                  qatouch_ledger.load_history())


def head_commit(repo: Path = ROOT) -> str:
    return _git(repo, 'rev-parse', '--short', 'HEAD').strip() or 'unknown'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', type=Path, default=OUT)
    parser.add_argument('--history', type=Path, default=HISTORY)
    parser.add_argument('--check', action='store_true',
                        help='exit 1 when the file on disk differs from what would be written')
    parser.add_argument('--record', action='store_true',
                        help="append today's counts to the ledger when they moved, then rewrite")
    parser.add_argument('--backfill', action='store_true',
                        help='rebuild the backfilled part of the ledger from git, keep recorded rows, then rewrite')
    args = parser.parse_args(argv)

    if args.backfill:
        # one recorded row per day survives: the last one written that day
        kept = list({r['date']: r for r in load_history(args.history) if r.get('source') == 'record'}.values())
        # a recorded row for a commit outranks the backfilled one: it carries
        # the Steps and mapping counts too
        recorded_at = {(r['date'], r['commit']) for r in kept}
        rows = [r for r in backfill() if (r['date'], r['commit']) not in recorded_at]
        save_history(sorted(rows + kept, key=lambda r: (r['date'], r['commit'])), args.history)
        print(f'backfilled {len(rows)} weekly rows into {args.history} (kept {len(kept)} recorded)')
    if args.record:
        history = load_history(args.history)
        row = snapshot_row(current_rows(), dt.date.today(), head_commit())
        history, what = merge_record(history, row)
        if what == 'unchanged':
            print(f'ledger unchanged: the counts match the last row ({history[-1]["date"]})')
        else:
            save_history(history, args.history)
            print(f"{what} {row['date']} {row['commit']}: " + ', '.join(
                f"{k} {v['functions']}" for k, v in row['products'].items()))

    text = build(args.history)
    if args.check:
        current = args.out.read_text(encoding='utf-8').replace('\r\n', '\n') if args.out.exists() else ''
        if current != text:
            print(f'{args.out} is stale. Run: python tools/test_inventory.py')
            return 1
        print(f'{args.out} is current.')
        return 0
    args.out.write_text(text, encoding='utf-8', newline='\n')
    # product rows only: harness rows start with a directory, not test_
    rows = text.count('\n| `test_')
    print(f'wrote {args.out} ({rows} product tests)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
