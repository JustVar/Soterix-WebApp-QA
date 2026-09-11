#!/usr/bin/env python3
"""Track QA Touch case counts per project over time: history/qatouch_counts.jsonl.

The QA Touch twin of history/test_counts.jsonl. Each row is one project on
one snapshot date: how many cases it holds, how many carry steps, how many
are automated (their key is in config/qatouch_case_mapping.json), the
module count and the split by case type. Together with the test ledger it
answers "how are the suites growing, and how much of QA Touch does the
automation cover", per product, week by week.

`qatouch_analytics.py snapshot` appends a row for every project it
snapshots. --backfill rebuilds the ledger from every snapshot on disk (the
default project's flat files and the per-project subdirectories), so the
history starts at the first snapshot (02/2026), not the day the ledger was
asked for.

Usage:
  python tools/qatouch_ledger.py             # print the ledger
  python tools/qatouch_ledger.py --backfill  # rebuild it from the snapshots on disk
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from plugins import products  # noqa: E402
from tools import qatouch_mapping as qm  # noqa: E402

HISTORY = ROOT / 'history' / 'qatouch_counts.jsonl'
SNAPSHOTS_DIR = ROOT / 'config' / 'qatouch_snapshots'
DEFAULT_PROJECT_KEY = 'JlW1'


def product_name(project_key: str) -> str:
    return products.PRODUCTS.get(project_key, project_key)


def mapped_keys(mapping: dict | None = None) -> set[str]:
    """Every case key the automation maps to, across projects."""
    rows = (mapping if mapping is not None else qm.load_raw().get('mappings', {}))
    return {r['case_key'] for r in rows.values() if (r or {}).get('case_key')}


def count_row(snapshot: dict, automated_keys: set[str], *,
              date: str | None = None, project_key: str | None = None) -> dict:
    """One ledger row from one snapshot.

    `date` and `project_key` are fallbacks for the oldest snapshots, which
    carry neither field: the backfill takes them from the file's name and
    its directory.
    """
    cases = snapshot.get('cases') or []
    key = snapshot.get('project_key') or project_key or DEFAULT_PROJECT_KEY
    by_type = Counter((c.get('Type') or 'Unspecified') for c in cases)
    modules = {c.get('module_key') or c.get('module_name') or '' for c in cases} - {''}
    return {
        'date': snapshot.get('snapshot_date') or date,
        'project_key': key,
        'product': product_name(key),
        'cases': len(cases),
        'modules': len(modules),
        'with_steps': sum(1 for c in cases if c.get('Steps')),
        'automated': sum(1 for c in cases if c.get('case_key') in automated_keys),
        'by_type': dict(sorted(by_type.items())),
        'source': 'snapshot',
    }


def merge(history: list[dict], row: dict) -> list[dict]:
    """One row per project per date: a same-day row for the project is replaced."""
    kept = [r for r in history if (r['date'], r['project_key']) != (row['date'], row['project_key'])]
    return sorted([*kept, row], key=lambda r: (r['date'], r['project_key']))


def snapshot_files(snapshots_dir: Path = SNAPSHOTS_DIR) -> list[tuple[str, Path]]:
    """(project_key, path) for every snapshot on disk, oldest first.

    The default project's snapshots are the flat snapshot_<date>.json files;
    every other project's live in a subdirectory named by its key (see
    qatouch_analytics.snapshot_path for why).
    """
    found = [(DEFAULT_PROJECT_KEY, p) for p in snapshots_dir.glob('snapshot_*.json')]
    for sub in snapshots_dir.iterdir() if snapshots_dir.is_dir() else []:
        if sub.is_dir():
            found += [(sub.name, p) for p in sub.glob('snapshot_*.json')]
    return sorted(found, key=lambda t: (t[1].name, t[0]))


def load_history(path: Path = HISTORY) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def save_history(rows: list[dict], path: Path = HISTORY) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, sort_keys=True) + '\n' for r in rows), encoding='utf-8', newline='\n')


def record(snapshot: dict, path: Path = HISTORY) -> dict:
    """Append (or replace) the row for this snapshot; called after each snapshot is written."""
    row = count_row(snapshot, mapped_keys())
    save_history(merge(load_history(path), row), path)
    return row


def backfill(snapshots_dir: Path = SNAPSHOTS_DIR) -> list[dict]:
    """Rows for every snapshot on disk. The automated count uses today's
    mapping for every date: the mapping file has no history of its own."""
    keys = mapped_keys()
    rows: list[dict] = []
    for project_key, path in snapshot_files(snapshots_dir):
        snapshot = json.loads(path.read_text(encoding='utf-8'))
        # snapshot_<date>.json: the oldest files name their date nowhere else
        date = path.stem.partition('_')[2]
        rows = merge(rows, count_row(snapshot, keys, date=date, project_key=project_key))
    return rows


def render_growth(history: list[dict]) -> list[str]:
    """Markdown: QA Touch cases per product by snapshot date, newest first."""
    if not history:
        return ['### QA Touch cases per project', '',
                'No QA Touch ledger yet. `python tools/qatouch_ledger.py --backfill` builds one from the snapshots.', '']
    by_date: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in history:
        by_date[r['date']][r['product']] = r
    names = sorted({r['product'] for r in history})
    out = ['### QA Touch cases per project', '',
           'Cases per QA Touch project at each snapshot (`history/qatouch_counts.jsonl`,',
           'appended by `qatouch_analytics.py snapshot`). "Automated" is the cases whose key',
           'the mapping file points a test at; a product with no snapshot that day shows "-".',
           '',
           '| Date | ' + ' | '.join(names) + ' | Total cases | Automated |',
           '|---|' + '---|' * len(names) + '---|---|']
    for date in sorted(by_date, reverse=True):
        rows = by_date[date]
        cells = [str(rows[n]['cases']) if n in rows else '-' for n in names]
        total = sum(r['cases'] for r in rows.values())
        automated = sum(r['automated'] for r in rows.values())
        out.append(f"| {date} | " + ' | '.join(cells) + f" | {total} | {automated} |")
    out.append('')
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--backfill', action='store_true', help='rebuild the ledger from every snapshot on disk')
    parser.add_argument('--history', type=Path, default=HISTORY)
    args = parser.parse_args(argv)
    if args.backfill:
        rows = backfill()
        save_history(rows, args.history)
        print(f'backfilled {len(rows)} rows into {args.history}')
    for r in load_history(args.history):
        print(f"{r['date']}  {r['project_key']:5s} {r['product']:28s} cases {r['cases']:5d}  "
              f"steps {r['with_steps']:5d}  automated {r['automated']:4d}  modules {r['modules']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
