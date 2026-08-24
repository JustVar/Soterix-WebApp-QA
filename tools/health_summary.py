#!/usr/bin/env python3
"""Health summary across archived runs -- CLI.

    python run.py health                     # newest 20 runs of each target
    python run.py health 50                  # newest 50
    python tools/health_summary.py --last 50

Reads every reports/runs/*/summary.json (see plugins/run_archive.py),
writes reports/runs/health.html, and prints a compact table. The page
shows, over the window:
  - Targets: one row per invocation target (the run folder's slug): runs,
    pass rate, mean run duration, advisory count, newest run and its exit
    status.
  - Modules: one row per test file under tests/: tests seen, results, pass
    rate, mean test duration, advisory count.
  - Flaky candidates: tests that both passed and failed in the window.
  - Newly failing: tests whose newest result fails after a pass.
  - Slowest tests: by mean duration.

Pass rate is passed / (passed + failed + errors); skips do not count. The
window is the newest N runs of each target (default 20, the archive's own
per-target retention), so a target that runs rarely still has a row.

Summaries written before schema 2 carry no per-test records: they count
toward the target rows only. Stdlib only, and read-only on the archive
except for health.html and the index link to it.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from datetime import datetime
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from plugins.run_archive import RUNS_DIR, _write_index  # noqa: E402
from plugins.run_report import (  # noqa: E402
    FAILURE_OUTCOMES,
    PAGE_CSS,
    PASSED_OUTCOMES,
    RUN_DIR_RE,
    format_seconds,
    module_of,
    readable_title,
    summary_tests,
)

DEFAULT_LAST = 20
SLOWEST_COUNT = 10
# The terminal table stays readable at 100 columns.
NAME_WIDTH = 44


# ---------------------------------------------------------------- load

def load_runs(runs_dir: Path) -> list[dict]:
    """Every run folder with a readable summary.json, newest first."""
    runs = []
    if not runs_dir.is_dir():
        return runs
    for folder in runs_dir.iterdir():
        if not folder.is_dir() or not RUN_DIR_RE.match(folder.name):
            continue
        try:
            loaded = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if isinstance(loaded, dict):
            runs.append({'name': folder.name, 'summary': loaded})
    return sorted(runs, key=lambda r: r['name'], reverse=True)


def slug_of(name: str) -> str:
    return name.partition('__')[2]


def select_window(runs: Iterable[dict], last_n: int = DEFAULT_LAST) -> list[dict]:
    """The newest `last_n` runs of each target, newest first overall."""
    seen: dict[str, int] = {}
    window = []
    for run in sorted(runs, key=lambda r: r['name'], reverse=True):
        slug = slug_of(run['name'])
        if seen.get(slug, 0) < last_n:
            seen[slug] = seen.get(slug, 0) + 1
            window.append(run)
    return window


# ---------------------------------------------------------------- aggregate

def _rate(passed: int, failed: int) -> float | None:
    total = passed + failed
    return round(passed / total, 3) if total else None


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 1) if values else None


def _target_label(summary: dict, slug: str) -> str:
    label = ' '.join(str(t) for t in (summary.get('target') or []))
    if summary.get('markexpr'):
        label = f'{label} -m {summary["markexpr"]}'.strip()
    return label or slug


def aggregate(runs: Iterable[dict], last_n: int = DEFAULT_LAST) -> dict:
    """Fold the window's summaries into the page's facts. Pure."""
    window = select_window(runs, last_n)
    targets: dict[str, dict] = {}
    modules: dict[str, dict] = {}
    # nodeid -> its results, newest first: {'run', 'outcome', 'seconds', 'title', 'module'}
    history: dict[str, list[dict]] = {}

    for run in window:
        name, summary = run['name'], run['summary']
        slug = slug_of(name)
        counts = summary.get('counts') if isinstance(summary.get('counts'), dict) else {}
        advisories = summary.get('advisories') if isinstance(summary.get('advisories'), list) else []
        target = targets.setdefault(slug, {
            'slug': slug, 'target': _target_label(summary, slug), 'runs': 0, 'passed': 0,
            'failed': 0, 'durations': [], 'advisories': 0, 'newest_run': name,
            'newest_started': summary.get('started') or name.partition('__')[0].replace('_', ' '),
            'newest_exit': summary.get('exitstatus'),
        })
        target['runs'] += 1
        target['passed'] += int(counts.get('passed', 0) or 0)
        target['failed'] += int(counts.get('failed', 0) or 0) + int(counts.get('errors', 0) or 0)
        target['advisories'] += len(advisories)
        if isinstance(summary.get('duration_s'), (int, float)):
            target['durations'].append(float(summary['duration_s']))

        for item in advisories:
            test = str(item.get('test', '')) if isinstance(item, dict) else ''
            if test:
                _module_row(modules, module_of(test))['advisories'] += 1

        for row in summary_tests(summary):
            nodeid = str(row['nodeid'])
            module = str(row.get('module') or module_of(nodeid))
            outcome = str(row.get('outcome') or 'unknown')
            seconds = row['duration_s'] if isinstance(row.get('duration_s'), (int, float)) else None
            title = str(row.get('title') or readable_title(nodeid))
            history.setdefault(nodeid, []).append({
                'run': name, 'outcome': outcome, 'seconds': seconds, 'title': title,
                'module': module})
            mod = _module_row(modules, module)
            mod['tests'].add(nodeid)
            mod['run_names'].add(name)
            if outcome in PASSED_OUTCOMES:
                mod['passed'] += 1
            elif outcome in FAILURE_OUTCOMES:
                mod['failed'] += 1
            if seconds is not None:
                mod['durations'].append(float(seconds))

    target_rows = []
    for target in sorted(targets.values(), key=lambda t: t['target']):
        target_rows.append({
            'slug': target['slug'], 'target': target['target'], 'runs': target['runs'],
            'passed': target['passed'], 'failed': target['failed'],
            'pass_rate': _rate(target['passed'], target['failed']),
            'mean_duration_s': _mean(target['durations']),
            'advisories': target['advisories'], 'newest_run': target['newest_run'],
            'newest_started': target['newest_started'], 'newest_exit': target['newest_exit'],
        })

    module_rows = []
    for mod in sorted(modules.values(), key=lambda m: m['module']):
        module_rows.append({
            'module': mod['module'], 'runs': len(mod['run_names']), 'tests': len(mod['tests']),
            'passed': mod['passed'], 'failed': mod['failed'],
            'pass_rate': _rate(mod['passed'], mod['failed']),
            'mean_duration_s': _mean(mod['durations']), 'advisories': mod['advisories'],
        })

    flaky, newly_failing, timed = [], [], []
    for nodeid, results in history.items():
        newest = results[0]
        passed = sum(1 for r in results if r['outcome'] in PASSED_OUTCOMES)
        failed = sum(1 for r in results if r['outcome'] in FAILURE_OUTCOMES)
        facts = {'nodeid': nodeid, 'title': newest['title'], 'module': newest['module']}
        if passed and failed:
            flaky.append({**facts, 'runs': len(results), 'passed': passed, 'failed': failed,
                          'last_outcome': newest['outcome'], 'last_run': newest['run']})
        if (newest['outcome'] in FAILURE_OUTCOMES and len(results) > 1
                and results[1]['outcome'] in PASSED_OUTCOMES):
            newly_failing.append({**facts, 'run': newest['run'], 'previous_run': results[1]['run']})
        seconds = [float(r['seconds']) for r in results if r['seconds'] is not None]
        if seconds:
            timed.append({**facts, 'runs': len(seconds), 'mean_s': _mean(seconds),
                          'max_s': round(max(seconds), 1)})

    flaky.sort(key=lambda f: (-f['failed'], -f['runs'], f['nodeid']))
    newly_failing.sort(key=lambda f: (f['run'], f['nodeid']), reverse=True)
    timed.sort(key=lambda t: (-(t['mean_s'] or 0.0), t['nodeid']))

    return {
        'window': {'last_n': last_n, 'runs': len(window),
                   'newest': window[0]['name'] if window else None,
                   'oldest': window[-1]['name'] if window else None},
        'targets': target_rows, 'modules': module_rows, 'flaky': flaky,
        'newly_failing': newly_failing, 'slowest': timed[:SLOWEST_COUNT],
    }


def _module_row(modules: dict[str, dict], module: str) -> dict:
    return modules.setdefault(module, {
        'module': module, 'tests': set(), 'run_names': set(), 'passed': 0, 'failed': 0,
        'durations': [], 'advisories': 0})


# ---------------------------------------------------------------- render

def _pct(rate: float | None) -> str:
    return '-' if rate is None else f'{rate * 100:.0f}%'


def _secs(seconds: float | None) -> str:
    return '-' if seconds is None else format_seconds(seconds)


def _run_link(name: str) -> str:
    return f'<a href="{escape(name, quote=True)}/run.html">{escape(name)}</a>'


def _test_cell(row: dict) -> str:
    return (f'{escape(row["title"])}<div class="nodeid">{escape(row["nodeid"])}</div>'
            f'<div class="case">{escape(row["module"])}</div>')


def _table(headers: list[str], rows: list[list[str]], empty: str) -> str:
    if not rows:
        return f'<p class="empty">{escape(empty)}</p>'
    head = ''.join(f'<th>{escape(h)}</th>' for h in headers)
    body = ''.join('<tr>' + ''.join(cells) + '</tr>' for cells in rows)
    return f'<table class="facts-table"><tr>{head}</tr>{body}</table>'


def _num(text: str) -> str:
    return f'<td class="num">{escape(text)}</td>'


def _cell(inner: str) -> str:
    return f'<td>{inner}</td>'


def render_health(agg: dict, generated: str | None = None) -> str:
    """The health.html page from aggregate()'s facts. Pure."""
    window = agg['window']
    generated = generated or datetime.now().isoformat(timespec='seconds')
    target_rows = [[
        _cell(escape(t['target'])), _num(str(t['runs'])), _num(_pct(t['pass_rate'])),
        _num(f"{t['passed']} / {t['failed']}"), _num(_secs(t['mean_duration_s'])),
        _num(str(t['advisories'])),
        _cell(f"{_run_link(t['newest_run'])}<div class=\"case\">exit "
              f"{escape(str(t['newest_exit'])) if t['newest_exit'] is not None else '-'}</div>"),
    ] for t in agg['targets']]
    module_rows = [[
        _cell(f'<code>{escape(m["module"])}</code>'), _num(str(m['runs'])),
        _num(str(m['tests'])), _num(_pct(m['pass_rate'])),
        _num(f"{m['passed']} / {m['failed']}"), _num(_secs(m['mean_duration_s'])),
        _num(str(m['advisories'])),
    ] for m in agg['modules']]
    flaky_rows = [[
        _cell(_test_cell(f)), _num(f"{f['passed']} / {f['failed']} of {f['runs']}"),
        _cell(f"{escape(f['last_outcome'])} in {_run_link(f['last_run'])}"),
    ] for f in agg['flaky']]
    newly_rows = [[
        _cell(_test_cell(n)), _cell(_run_link(n['run'])), _cell(_run_link(n['previous_run'])),
    ] for n in agg['newly_failing']]
    slow_rows = [[
        _num(_secs(s['mean_s'])), _num(_secs(s['max_s'])), _num(str(s['runs'])),
        _cell(_test_cell(s)),
    ] for s in agg['slowest']]

    span = ''
    if window['runs']:
        span = (f" Window: {window['runs']} runs, from <code>{escape(str(window['oldest']))}</code>"
                f" to <code>{escape(str(window['newest']))}</code>.")
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test health</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<h1>Test health</h1>
<p class="case">The newest {window['last_n']} runs of each target, from the run archive.{span}
Pass rate is passed / (passed + failed + errors); skips do not count.
Generated {escape(generated)}. Rebuild with <code>python run.py health</code>.</p>
<div class="meta"><a href="index.html">all runs</a></div>

<h2 id="targets">Targets ({len(agg['targets'])})</h2>
{_table(['Target', 'Runs', 'Pass rate', 'Passed / failed', 'Mean run', 'Advisories', 'Newest run'],
        target_rows, 'No archived runs yet. Run the suite once.')}

<h2 id="modules">Modules ({len(agg['modules'])})</h2>
{_table(['Module', 'Runs', 'Tests', 'Pass rate', 'Passed / failed', 'Mean test', 'Advisories'],
        module_rows, 'No per-test records yet: they come from runs archived with schema 2.')}

<h2 id="flaky">Flaky candidates ({len(agg['flaky'])})</h2>
<p class="case">Tests that both passed and failed in the window.</p>
{_table(['Test', 'Passed / failed of runs', 'Latest'], flaky_rows, 'None.')}

<h2 id="newly-failing">Newly failing ({len(agg['newly_failing'])})</h2>
<p class="case">Tests whose newest result fails after a pass in the run before.</p>
{_table(['Test', 'Failed in', 'Passed in'], newly_rows, 'None.')}

<h2 id="slowest">Slowest tests ({len(agg['slowest'])})</h2>
{_table(['Mean', 'Max', 'Runs', 'Test'], slow_rows, 'No per-test timing yet.')}
</body>
</html>
'''


def format_table(agg: dict) -> str:
    """The terminal view: targets, modules, then the three test lists."""
    window = agg['window']
    out = [f"Health: newest {window['last_n']} runs of each target, {window['runs']} runs in the window."]

    def cut(text: str) -> str:
        return text if len(text) <= NAME_WIDTH else text[:NAME_WIDTH - 3] + '...'

    out.append('')
    out.append(f"{'TARGET':<{NAME_WIDTH}} {'RUNS':>4} {'PASS':>5} {'MEAN':>9} {'ADV':>4}  NEWEST")
    for t in agg['targets']:
        out.append(f"{cut(t['target']):<{NAME_WIDTH}} {t['runs']:>4} {_pct(t['pass_rate']):>5} "
                   f"{_secs(t['mean_duration_s']):>9} {t['advisories']:>4}  "
                   f"{t['newest_started']} exit {t['newest_exit'] if t['newest_exit'] is not None else '-'}")
    if not agg['targets']:
        out.append('(no archived runs)')
    out.append('')
    out.append(f"{'MODULE':<{NAME_WIDTH}} {'RUNS':>4} {'TESTS':>5} {'PASS':>5} {'MEAN':>9} {'ADV':>4}")
    for m in agg['modules']:
        out.append(f"{cut(m['module']):<{NAME_WIDTH}} {m['runs']:>4} {m['tests']:>5} "
                   f"{_pct(m['pass_rate']):>5} {_secs(m['mean_duration_s']):>9} {m['advisories']:>4}")
    if not agg['modules']:
        out.append('(no per-test records yet)')
    out.append('')
    out.append(f"Flaky candidates ({len(agg['flaky'])}):")
    out.extend(f"  {f['passed']}/{f['failed']} of {f['runs']}  {f['nodeid']}" for f in agg['flaky'])
    out.append(f"Newly failing ({len(agg['newly_failing'])}):")
    out.extend(f"  {n['nodeid']}  (failed in {n['run']})" for n in agg['newly_failing'])
    out.append(f"Slowest ({len(agg['slowest'])}):")
    out.extend(f"  {_secs(s['mean_s']):>9} mean  {s['nodeid']}" for s in agg['slowest'])
    return '\n'.join(out)


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog='health_summary.py', description=__doc__.split('\n\n', 1)[1],
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--last', type=int, default=DEFAULT_LAST,
                        help=f'newest runs of each target to read (default {DEFAULT_LAST})')
    parser.add_argument('--runs-dir', type=Path, default=RUNS_DIR,
                        help=f'the run archive (default {RUNS_DIR})')
    args = parser.parse_args(argv)
    if args.last < 1:
        parser.error('--last must be 1 or more')

    runs = load_runs(args.runs_dir)
    agg = aggregate(runs, args.last)
    print(format_table(agg))
    if not runs:
        print(f'\nNo archived runs under {args.runs_dir}. Run the suite once.')
        return 0
    page = args.runs_dir / 'health.html'
    page.write_text(render_health(agg), encoding='utf-8')
    # The index links health.html once it exists.
    _write_index(args.runs_dir)
    print(f'\nHealth page: {page.resolve()}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
