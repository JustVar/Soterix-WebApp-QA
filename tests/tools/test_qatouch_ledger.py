"""Pins for tools/qatouch_ledger.py: one row per project per snapshot date, the
counts a row carries, the merge rule, where snapshots live, and the table."""
from __future__ import annotations

from tools import qatouch_ledger as ql


def case(key, type_='Functional', module='m1', steps=True):
    return {'case_key': key, 'Type': type_, 'module_key': module,
            'Steps': [{'step': 'do'}] if steps else []}


SNAP = {'snapshot_date': '2026-09-08', 'project_key': 'JlW1', 'cases': [
    case('AAA111'), case('BBB222', 'Acceptance', 'm2'), case('CCC333', steps=False), case('DDD444', module='m2')]}


def test_count_row_carries_cases_steps_automation_modules_and_types():
    """A row counts the snapshot's cases, those with steps, those the mapping automates, its modules and types."""
    row = ql.count_row(SNAP, automated_keys={'AAA111', 'DDD444', 'ZZZ999'})
    assert row == {'date': '2026-09-08', 'project_key': 'JlW1', 'product': 'NexaiQ-Core',
                   'cases': 4, 'modules': 2, 'with_steps': 3, 'automated': 2,
                   'by_type': {'Acceptance': 1, 'Functional': 3}, 'source': 'snapshot'}


def test_other_projects_are_named_by_the_products_map():
    """A subproject snapshot is named after its product; an unknown key stays a key."""
    assert ql.count_row({**SNAP, 'project_key': '60W5'}, set())['product'] == 'NexaiQ-Camera 2 Cloud'
    assert ql.count_row({**SNAP, 'project_key': 'ZZZZ'}, set())['product'] == 'ZZZZ'


def test_mapped_keys_reads_every_case_key_in_the_mapping():
    """Keys come from every mapping row that has one, whatever its project."""
    assert ql.mapped_keys({'t1': {'case_key': 'A'}, 't2': {'case_key': 'B'}, 't3': {}, 't4': None}) == {'A', 'B'}


def test_merge_keeps_one_row_per_project_per_date_in_order():
    """A same-day row for the same project is replaced; other projects and dates stay, sorted."""
    a = ql.count_row(SNAP, set())
    b = ql.count_row({**SNAP, 'project_key': '60W5'}, set())
    later = ql.count_row({**SNAP, 'snapshot_date': '2026-09-09'}, {'AAA111'})
    again = ql.count_row(SNAP, {'AAA111', 'BBB222'})
    history = ql.merge(ql.merge(ql.merge(ql.merge([], later), a), b), again)
    assert [(r['date'], r['project_key'], r['automated']) for r in history] == [
        ('2026-09-08', '60W5', 0), ('2026-09-08', 'JlW1', 2), ('2026-09-09', 'JlW1', 1)]


def test_snapshot_files_pair_each_file_with_its_project(tmp_path):
    """Flat files are the default project; a subdirectory's files are that project."""
    (tmp_path / 'snapshot_2026-02-20.json').write_text('{}')
    (tmp_path / 'snapshot_2026-09-08.json').write_text('{}')
    (tmp_path / '60W5').mkdir()
    (tmp_path / '60W5' / 'snapshot_2026-09-08.json').write_text('{}')
    (tmp_path / 'notes.txt').write_text('x')
    found = [(k, p.name) for k, p in ql.snapshot_files(tmp_path)]
    assert found == [('JlW1', 'snapshot_2026-02-20.json'), ('60W5', 'snapshot_2026-09-08.json'),
                     ('JlW1', 'snapshot_2026-09-08.json')]


def test_growth_table_has_a_column_per_product_and_sums_each_date():
    """The table lists dates newest first, one column per product, '-' where a product has no snapshot."""
    history = [ql.count_row({**SNAP, 'snapshot_date': '2026-02-20'}, set()),
               ql.count_row(SNAP, {'AAA111'}),
               ql.count_row({**SNAP, 'project_key': '60W5', 'cases': SNAP['cases'][:1]}, set())]
    lines = ql.render_growth(history)
    header = next(line for line in lines if line.startswith('| Date'))
    assert header == '| Date | NexaiQ-Camera 2 Cloud | NexaiQ-Core | Total cases | Automated |'
    rows = [line for line in lines if line.startswith('| 2026')]
    assert rows == ['| 2026-09-08 | 1 | 4 | 5 | 1 |', '| 2026-02-20 | - | 4 | 4 | 0 |']
    assert 'No QA Touch ledger yet' in ' '.join(ql.render_growth([]))


def test_record_writes_the_row_through_the_ledger_file(tmp_path, monkeypatch):
    """record() appends a row to the ledger file using the real mapping's keys."""
    monkeypatch.setattr(ql, 'mapped_keys', lambda mapping=None: {'AAA111'})
    ledger = tmp_path / 'qatouch_counts.jsonl'
    row = ql.record(SNAP, ledger)
    assert row['automated'] == 1
    assert ql.load_history(ledger) == [row]
    ql.record({**SNAP, 'cases': SNAP['cases'][:2]}, ledger)
    assert [r['cases'] for r in ql.load_history(ledger)] == [2]
