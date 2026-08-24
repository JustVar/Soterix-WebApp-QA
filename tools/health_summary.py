#!/usr/bin/env python3
"""Health summary across archived runs -- CLI.

    python run.py health                     # newest 20 runs of each target
    python run.py health 50                  # newest 50
    python tools/health_summary.py --last 50

Reads every reports/runs/*/summary.json (see plugins/run_archive.py),
writes reports/runs/health.html, and prints a compact table. The page
shows, over the window:
  - Verdict: one line per target in plain words, e.g. "Views: 96% pass
    rate over 20 runs, 1 test to watch."
  - Targets: one row per invocation target (the run folder's slug): runs,
    pass rate, mean run duration, advisory count (linked to the newest
    run's advisories), newest run and its exit status.
  - Modules: one row per test file under tests/: tests seen, results, pass
    rate, mean test duration.
  - Tests to watch: every test that failed at least once in the window,
    with its last 20 outcomes as a strip (oldest left), its flaky rate
    (failures / runs it was present in), the flaky label when it also
    passed in that window, and the date of its last failure. Sorted by
    flaky rate, highest first.

Pass rate is passed / (passed + failed + errors); skips do not count. The
window is the newest N runs of each target (default 20, the archive's own
per-target retention), so a target that runs rarely still has a row. The
per-run page (run.html) lists a run's slowest tests. This page keeps the
mean test duration per module.

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

from plugins.branding import favicon_link, header_logo  # noqa: E402
from plugins.run_archive import RUNS_DIR, _write_index  # noqa: E402
from plugins.run_report import (  # noqa: E402
    FAILURE_OUTCOMES,
    HISTORY_RUNS,
    PAGE_CSS,
    PASSED_OUTCOMES,
    RUN_DIR_RE,
    format_seconds,
    friendly_time,
    history_facts,
    module_of,
    plural,
    readable_title,
    render_strip,
    run_started,
    summary_tests,
)

DEFAULT_LAST = 20
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


def target_name(label: str) -> str:
    """The target in a reader's words.

    'tests/ui/views -m dragdrop' reads 'Views (dragdrop)', a file or node
    id target names its folder then the rest ('Admin
    (test_admin_sites.py)'), several targets join with ' + ', and no
    target reads 'All tests'.
    """
    paths, _, mark = label.partition(' -m ')
    names = []
    for path in paths.split():
        parts = [p for p in path.replace('\\', '/').split('/') if p]
        if parts[:1] == ['tests']:
            parts = parts[1:]
        if parts[:1] == ['ui']:
            parts = parts[1:]
        if not parts:
            names.append('All tests')
            continue
        head = parts[0].replace('_', ' ')
        name = head[:1].upper() + head[1:]
        rest = '/'.join(parts[1:])
        names.append(f'{name} ({rest})' if rest else name)
    text = ' + '.join(names) or 'All tests'
    return f'{text} ({mark})' if mark else text


def aggregate(runs: Iterable[dict], last_n: int = DEFAULT_LAST) -> dict:
    """Fold the window's summaries into the page's facts. Pure."""
    window = select_window(runs, last_n)
    targets: dict[str, dict] = {}
    modules: dict[str, dict] = {}
    # nodeid -> its results, newest first:
    # {'run', 'started', 'outcome', 'seconds', 'title', 'module'}
    history: dict[str, list[dict]] = {}

    for run in window:
        name, summary = run['name'], run['summary']
        slug = slug_of(name)
        counts = summary.get('counts') if isinstance(summary.get('counts'), dict) else {}
        advisories = summary.get('advisories') if isinstance(summary.get('advisories'), list) else []
        started = run_started(Path(name), summary)
        target = targets.setdefault(slug, {
            'slug': slug, 'target': _target_label(summary, slug), 'runs': 0, 'passed': 0,
            'failed': 0, 'durations': [], 'advisories': 0, 'runs_without_records': 0,
            'newest_run': name, 'newest_started': started,
            'newest_exit': summary.get('exitstatus'),
        })
        target['runs'] += 1
        target['passed'] += int(counts.get('passed', 0) or 0)
        target['failed'] += int(counts.get('failed', 0) or 0) + int(counts.get('errors', 0) or 0)
        target['advisories'] += len(advisories)
        if isinstance(summary.get('duration_s'), (int, float)):
            target['durations'].append(float(summary['duration_s']))
        rows = summary_tests(summary)
        if not rows:
            # A pre-schema-2 archive: its failures can name no test.
            target['runs_without_records'] += 1

        for row in rows:
            nodeid = str(row['nodeid'])
            module = str(row.get('module') or module_of(nodeid))
            outcome = str(row.get('outcome') or 'unknown')
            seconds = row['duration_s'] if isinstance(row.get('duration_s'), (int, float)) else None
            title = str(row.get('title') or readable_title(nodeid))
            history.setdefault(nodeid, []).append({
                'run': name, 'started': started, 'outcome': outcome, 'seconds': seconds,
                'title': title, 'module': module})
            mod = _module_row(modules, module)
            mod['tests'].add(nodeid)
            mod['run_names'].add(name)
            if outcome in PASSED_OUTCOMES:
                mod['passed'] += 1
            elif outcome in FAILURE_OUTCOMES:
                mod['failed'] += 1
            if seconds is not None:
                mod['durations'].append(float(seconds))

    # Every test that failed at least once in its strip, with the facts
    # the strip shows, and how many of them each target saw fail.
    watch = []
    watch_by_slug: dict[str, int] = {}
    for nodeid, results in history.items():
        facts = history_facts(results)
        if not facts['failed']:
            continue
        newest = results[0]
        watch.append({'nodeid': nodeid, 'title': newest['title'], 'module': newest['module'],
                      'facts': facts})
        for slug in {slug_of(b['run']) for b in facts['blocks'] if b['outcome'] in FAILURE_OUTCOMES}:
            watch_by_slug[slug] = watch_by_slug.get(slug, 0) + 1
    watch.sort(key=lambda w: (-(w['facts']['rate'] or 0.0), -w['facts']['failed'], w['nodeid']))

    target_rows = []
    for target in sorted(targets.values(), key=lambda t: t['target']):
        target_rows.append({
            'slug': target['slug'], 'target': target['target'],
            'name': target_name(target['target']), 'runs': target['runs'],
            'passed': target['passed'], 'failed': target['failed'],
            'pass_rate': _rate(target['passed'], target['failed']),
            'mean_duration_s': _mean(target['durations']),
            'advisories': target['advisories'], 'watch': watch_by_slug.get(target['slug'], 0),
            'runs_without_records': target['runs_without_records'],
            'newest_run': target['newest_run'], 'newest_started': target['newest_started'],
            'newest_exit': target['newest_exit'],
        })

    module_rows = []
    for mod in sorted(modules.values(), key=lambda m: m['module']):
        module_rows.append({
            'module': mod['module'], 'runs': len(mod['run_names']), 'tests': len(mod['tests']),
            'passed': mod['passed'], 'failed': mod['failed'],
            'pass_rate': _rate(mod['passed'], mod['failed']),
            'mean_duration_s': _mean(mod['durations']),
        })

    return {
        'window': {'last_n': last_n, 'runs': len(window),
                   'newest': window[0]['name'] if window else None,
                   'oldest': window[-1]['name'] if window else None},
        'targets': target_rows, 'modules': module_rows, 'watch': watch,
    }


def _module_row(modules: dict[str, dict], module: str) -> dict:
    return modules.setdefault(module, {
        'module': module, 'tests': set(), 'run_names': set(), 'passed': 0, 'failed': 0,
        'durations': []})


def health_verdict(agg: dict) -> list[str]:
    """One sentence per target in plain words, numbers exact:
    "Views: 96% pass rate over 20 runs, 1 test to watch." A target whose
    runs recorded no results reads "no results" in place of the rate. A
    target that failed only in runs archived before per-test records
    existed cannot name its tests, and says so instead of "0"."""
    lines = []
    for t in agg['targets']:
        rate = f"{_pct(t['pass_rate'])} pass rate" if t['pass_rate'] is not None else 'no results'
        if t['watch'] == 0 and t['failed'] and t['runs_without_records']:
            watch = (f"tests to watch unknown ({plural(t['runs_without_records'], 'run', 'runs')} "
                     f"without per-test records)")
        else:
            watch = plural(t['watch'], 'test to watch', 'tests to watch')
        lines.append(f"{t['name']}: {rate} over {plural(t['runs'], 'run', 'runs')}, {watch}.")
    return lines or ['No archived runs yet.']


# ---------------------------------------------------------------- render

def _pct(rate: float | None) -> str:
    return '-' if rate is None else f'{rate * 100:.0f}%'


def _secs(seconds: float | None) -> str:
    return '-' if seconds is None else format_seconds(seconds)


def _run_link(name: str) -> str:
    return f'<a href="{escape(name, quote=True)}/run.html">{escape(name)}</a>'


def _test_cell(row: dict) -> str:
    return f'{escape(row["title"])}<div class="nodeid">{escape(row["nodeid"])}</div>'


def _rate_cell(facts: dict) -> str:
    """'15% (3 of 20 failed)' plus the flaky label when the window also
    holds a pass. A test that never passed in the window is not flaky:
    it fails every time, and the label would hide that."""
    text = escape(f"{_pct(facts['rate'])} ({facts['failed']} of {facts['runs']} failed)")
    if facts['flaky']:
        text += ' <span class="chip delta flaky">flaky</span>'
    return f'<td class="num">{text}</td>'


def _failure_link(block: dict | None) -> str:
    if not block:
        return '-'
    return (f'<a href="{escape(str(block["run"]), quote=True)}/run.html">'
            f'{escape(friendly_time(block.get("started")))}</a>')


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
        _cell(f"{escape(t['name'])}<div class=\"nodeid\">{escape(t['target'])}</div>"),
        _num(str(t['runs'])), _num(_pct(t['pass_rate'])),
        _num(f"{t['passed']} / {t['failed']}"), _num(_secs(t['mean_duration_s'])),
        # The count spans the window. The link opens the newest run's lines.
        _num(str(t['advisories'])) if not t['advisories'] else
        f'<td class="num"><a href="{escape(t["newest_run"], quote=True)}/run.html#advisories">'
        f'{t["advisories"]}</a></td>',
        _cell(f"{_run_link(t['newest_run'])}<div class=\"case\">exit "
              f"{escape(str(t['newest_exit'])) if t['newest_exit'] is not None else '-'}</div>"),
    ] for t in agg['targets']]
    module_rows = [[
        _cell(f'<code>{escape(m["module"])}</code>'), _num(str(m['runs'])),
        _num(str(m['tests'])), _num(_pct(m['pass_rate'])),
        _num(f"{m['passed']} / {m['failed']}"), _num(_secs(m['mean_duration_s'])),
    ] for m in agg['modules']]
    watch_rows = [[
        _cell(_test_cell(w)), _cell(f'<code>{escape(w["module"])}</code>'),
        _cell(render_strip(w['facts'], '', with_text=False)),
        _rate_cell(w['facts']), _cell(_failure_link(w['facts']['last_failure'])),
    ] for w in agg['watch']]
    verdict = ''.join(f'<li>{escape(line)}</li>' for line in health_verdict(agg))
    # An empty table must not claim a clean window when the failures sit
    # in runs that carry no per-test records.
    unnamed = sum(t['runs_without_records'] for t in agg['targets']
                  if t['failed'] and t['watch'] == 0)
    no_watch = (f'No test named: the failures in this window are in {plural(unnamed, "run", "runs")} '
                'archived without per-test records.' if unnamed
                else 'None: no test failed in the window.')

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
{favicon_link()}
<style>
.brand-row {{ display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem; }}
.brand-row h1 {{ margin: 0; }}
.brand {{ display: block; }}{PAGE_CSS}</style>
</head>
<body>
<div class="brand-row">{header_logo()}<h1>Test health</h1></div>
<ul class="verdict">{verdict}</ul>
<p class="case">The newest {window['last_n']} runs of each target, from the run archive.{span}
Pass rate is passed / (passed + failed + errors); skips do not count.
Generated {escape(generated)}. Rebuild with <code>python run.py health</code>.</p>
<div class="meta"><a href="index.html">all runs</a></div>

<h2 id="targets">Targets ({len(agg['targets'])})</h2>
{_table(['Target', 'Runs', 'Pass rate', 'Passed / failed', 'Mean run', 'Advisories', 'Newest run'],
        target_rows, 'No archived runs yet. Run the suite once.')}

<h2 id="modules">Modules ({len(agg['modules'])})</h2>
{_table(['Module', 'Runs', 'Tests', 'Pass rate', 'Passed / failed', 'Mean test'],
        module_rows, 'No per-test records yet: they come from runs archived with schema 2.')}

<h2 id="watch">Tests to watch ({len(agg['watch'])})</h2>
<p class="case">Every test that failed at least once in its last {HISTORY_RUNS}
results. The strip shows those results, oldest left and newest right (hover a block for the run,
click it to open that run). The flaky rate is failures / runs the test was present in. A test is
flaky when that window holds both a pass and a failure.</p>
{_table(['Test', 'Module', 'Last runs', 'Flaky rate', 'Last failure'], watch_rows, no_watch)}
</body>
</html>
'''


def format_table(agg: dict) -> str:
    """The terminal view: the verdict, targets, modules, then the tests to watch."""
    window = agg['window']
    out = [f"Health: newest {window['last_n']} runs of each target, {window['runs']} runs in the window."]
    out.extend(health_verdict(agg))

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
    out.append(f"{'MODULE':<{NAME_WIDTH}} {'RUNS':>4} {'TESTS':>5} {'PASS':>5} {'MEAN':>9}")
    for m in agg['modules']:
        out.append(f"{cut(m['module']):<{NAME_WIDTH}} {m['runs']:>4} {m['tests']:>5} "
                   f"{_pct(m['pass_rate']):>5} {_secs(m['mean_duration_s']):>9}")
    if not agg['modules']:
        out.append('(no per-test records yet)')
    out.append('')
    out.append(f"Tests to watch ({len(agg['watch'])}):")
    for w in agg['watch']:
        facts = w['facts']
        last = facts['last_failure']['started'] if facts['last_failure'] else '-'
        out.append(f"  {_pct(facts['rate']):>4}  {facts['failed']}/{facts['runs']} failed  "
                   f"last {last}  {w['nodeid']}")
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
