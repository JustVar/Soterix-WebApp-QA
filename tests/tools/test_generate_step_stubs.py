"""Pins for tools/generate_step_stubs.py --from-docstrings.

The sidecar is what sync-steps writes into QA Touch, so it has to say
what the docstring says and never invent a step. These pin the merge:
a Steps block replaces title and steps and keeps the case_key, a
missing block keeps the old entry and is reported, a removed test is
dropped and reported.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import generate_step_stubs as gs  # noqa: E402
from tools.qatouch_cases_from_tests import ParsedDoc, Step  # noqa: E402

OLD = {
    'test_file': 'tests/ui/x/test_x.py',
    'class': 'TestX',
    'tests': {
        'test_a': {'title': 'Old A', 'case_key': 'KeyA',
                   'steps': [{'n': 1, 'action': 'stale', 'expected': 'stale'}]},
        'test_b': {'title': 'Old B', 'case_key': 'KeyB',
                   'steps': [{'n': 1, 'action': 'kept', 'expected': 'kept'}]},
        'test_gone': {'title': 'Gone', 'case_key': 'KeyG', 'steps': []},
    },
}


def test_a_steps_block_replaces_title_and_steps_and_keeps_the_key():
    """The docstring wins for title and steps; the key is untouched."""
    parsed = {
        'test_a': ParsedDoc('New A', [Step('Open it', 'It opens'), Step('Close it', 'It closes')]),
        'test_b': ParsedDoc('B', problem='no Steps: block'),
    }
    tests, _needs, _dropped = gs.merge_from_docstrings(OLD, parsed)
    assert tests['test_a'] == {
        'title': 'New A', 'case_key': 'KeyA',
        'steps': [{'n': 1, 'action': 'Open it', 'expected': 'It opens'},
                  {'n': 2, 'action': 'Close it', 'expected': 'It closes'}],
    }


def test_a_missing_steps_block_keeps_the_old_entry_and_is_reported():
    """Nothing is invented: the old steps stay and the test is named."""
    parsed = {'test_b': ParsedDoc('B', problem='no Steps: block')}
    tests, needs, _dropped = gs.merge_from_docstrings(OLD, parsed)
    assert tests['test_b']['steps'] == [{'n': 1, 'action': 'kept', 'expected': 'kept'}]
    assert tests['test_b']['case_key'] == 'KeyB'
    assert needs == ['test_b: no Steps: block']


def test_a_test_that_left_the_file_is_dropped_and_reported():
    """The mapping file keeps the key; the sidecar follows the test file."""
    parsed = {'test_a': ParsedDoc('A', [Step('s', 'e')])}
    tests, _needs, dropped = gs.merge_from_docstrings(OLD, parsed)
    assert 'test_gone' not in tests
    assert dropped == ['test_b', 'test_gone']


def test_a_brand_new_test_gets_an_empty_key():
    """No sidecar yet: entries are built and the key waits for the mapping."""
    parsed = {'test_new': ParsedDoc('New', [Step('s', 'e')])}
    tests, needs, dropped = gs.merge_from_docstrings(None, parsed)
    assert tests == {'test_new': {'title': 'New', 'case_key': '',
                                  'steps': [{'n': 1, 'action': 's', 'expected': 'e'}]}}
    assert needs == []
    assert dropped == []


def test_the_mapping_files_key_wins_over_the_sidecars():
    """The mapping file is canonical; a stale sidecar key must not be synced."""
    parsed = {'test_a': ParsedDoc('A', [Step('s', 'e')])}
    tests, _needs, _dropped = gs.merge_from_docstrings(OLD, parsed, keys={'test_a': 'Canon'})
    assert tests['test_a']['case_key'] == 'Canon'


def test_a_sidecar_key_survives_when_the_mapping_has_none():
    """No mapping row yet: the sidecar's key is the only one there is."""
    parsed = {'test_a': ParsedDoc('A', [Step('s', 'e')])}
    tests, _needs, _dropped = gs.merge_from_docstrings(OLD, parsed, keys={})
    assert tests['test_a']['case_key'] == 'KeyA'


def test_mapping_keys_reads_one_file_and_counts_claims(tmp_path):
    """Keys come back by bare function name; claims span the whole mapping."""
    mapping = tmp_path / 'm.json'
    mapping.write_text(json.dumps({'mappings': {
        'tests/ui/x/test_x.py::TestX::test_a[chromium]': {'case_key': 'K1'},
        'tests/ui/x/test_x.py::TestX::test_b[chromium]': {'case_key': 'K2'},
        'tests/ui/y/test_y.py::TestY::test_c[chromium]': {'case_key': 'K2'},
    }}), encoding='utf-8')
    keys, claims = gs.mapping_keys(gs.ROOT / 'tests' / 'ui' / 'x' / 'test_x.py', mapping)
    assert keys == {'test_a': 'K1', 'test_b': 'K2'}
    assert claims['K2'] == ['tests/ui/x/test_x.py::TestX::test_b',
                           'tests/ui/y/test_y.py::TestY::test_c']
