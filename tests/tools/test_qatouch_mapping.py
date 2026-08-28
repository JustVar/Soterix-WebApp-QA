"""Pins for the mapping review gate and rename guard (tools/qatouch_mapping.py).

Added 2026-08-20 with the gate itself (audit M2): 330/378 mapping rows were
word-overlap guesses, and once uploads actually land a guess writes a real
status onto a case no test verifies. These pin the two rules that stop that:
only reviewed rows reach consumers, and a renamed test is caught statically.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import qatouch_mapping as qm  # noqa: E402


def _write_mapping(tmp_path, mappings):
    p = tmp_path / 'mapping.json'
    p.write_text(json.dumps({'version': 1, 'mappings': mappings}), encoding='utf-8')
    return p


def test_reviewed_lookup_filters_proposals(tmp_path):
    """Only rows with reviewed set to exactly True reach the reviewed lookup."""
    p = _write_mapping(tmp_path, {
        'tests/a.py::test_one': {'case_key': 'K1', 'reviewed': True},
        'tests/a.py::test_two': {'case_key': 'K2', 'reviewed': False},
        'tests/a.py::test_three': {'case_key': 'K3'},          # absent = proposal
        'tests/a.py::test_four': {'case_key': 'K4', 'reviewed': 'yes'},  # truthy != True
    })
    reviewed, counts = qm.reviewed_lookup(p)
    assert reviewed == {'tests/a.py::test_one': 'K1'}
    assert counts == {'total': 4, 'reviewed': 1, 'unreviewed': 3}


def test_orphaned_nodeids_catches_renames(tmp_path):
    """A mapped test whose function or file is gone is reported as an orphan."""
    tdir = tmp_path / 'tests'
    tdir.mkdir()
    (tdir / 'a.py').write_text('def test_alive():\n    pass\n', encoding='utf-8')
    p = _write_mapping(tmp_path, {
        'tests/a.py::test_alive[chromium]': {'case_key': 'K1'},   # exists (param stripped)
        'tests/a.py::test_renamed': {'case_key': 'K2'},           # gone from the file
        'tests/deleted.py::test_gone': {'case_key': 'K3'},        # file gone
    })
    orphans = qm.orphaned_nodeids(p, root=tmp_path)
    assert sorted(orphans) == ['tests/a.py::test_renamed', 'tests/deleted.py::test_gone']


def test_shared_across_functions_ignores_params_of_one_function(tmp_path):
    """A case key shared by two functions is flagged, but not one shared across params."""
    mappings = {
        'tests/a.py::test_x[chrome]': {'case_key': 'SHARED_OK'},
        'tests/a.py::test_x[firefox]': {'case_key': 'SHARED_OK'},   # same function - fine
        'tests/a.py::test_y': {'case_key': 'COLLIDE'},
        'tests/b.py::test_z': {'case_key': 'COLLIDE'},              # different functions - flag
    }
    shared = qm.shared_across_functions(mappings)
    assert 'SHARED_OK' not in shared
    assert sorted(shared['COLLIDE']) == ['tests/a.py::test_y', 'tests/b.py::test_z']


def test_real_mapping_has_no_orphans_and_gate_is_seeded():
    """The live file: every mapped test exists, and the bootstrap ran."""
    _reviewed, counts = qm.reviewed_lookup()
    assert counts['reviewed'] > 0, 'review gate not bootstrapped'
    assert qm.orphaned_nodeids() == [], 'a mapped test was renamed or deleted'


def test_orphaned_nodeids_catches_a_class_rename(tmp_path):
    """A renamed class orphans its methods.

    The previous text-based guard searched only for `def <function>`, so a
    class rename left it reporting all-clear while the mapped case stopped
    receiving results.
    """
    tdir = tmp_path / 'tests'
    tdir.mkdir()
    (tdir / 'test_a.py').write_text(
        'class TestWidget:\n    def test_alpha(self):\n        pass\n', encoding='utf-8')
    p = _write_mapping(tmp_path, {
        'tests/test_a.py::TestThing::test_alpha': {'case_key': 'K1'},   # class was renamed
        'tests/test_a.py::TestWidget::test_alpha': {'case_key': 'K2'},  # current name
    })
    assert qm.orphaned_nodeids(p, root=tmp_path) == ['tests/test_a.py::TestThing::test_alpha']


def test_orphaned_nodeids_catches_a_move_between_files(tmp_path):
    """A test that moved to another file orphans its old node id."""
    tdir = tmp_path / 'tests'
    tdir.mkdir()
    (tdir / 'test_old.py').write_text('def test_kept():\n    pass\n', encoding='utf-8')
    (tdir / 'test_new.py').write_text('def test_moved():\n    pass\n', encoding='utf-8')
    p = _write_mapping(tmp_path, {
        'tests/test_old.py::test_kept': {'case_key': 'K1'},
        'tests/test_old.py::test_moved': {'case_key': 'K2'},   # now lives in test_new.py
    })
    assert qm.orphaned_nodeids(p, root=tmp_path) == ['tests/test_old.py::test_moved']


def test_nodeids_in_file_handles_a_non_utf8_source(tmp_path):
    """A latin-1 source with a coding declaration parses instead of crashing.

    Reading as utf-8 raised UnicodeDecodeError, which is a ValueError and
    so was caught by neither OSError nor SyntaxError: the guard crashed
    rather than reporting.
    """
    tdir = tmp_path / 'tests'
    tdir.mkdir()
    f = tdir / 'test_latin.py'
    f.write_bytes('# -*- coding: latin-1 -*-\n# caf\xe9\ndef test_x():\n    pass\n'.encode('latin-1'))
    found, error = qm.nodeids_in_file(f, 'tests/test_latin.py')
    assert error is None
    assert found == {'tests/test_latin.py::test_x'}


def test_orphaned_nodeids_sees_a_nested_class(tmp_path):
    """A test in a nested class is found, not reported as an orphan."""
    tdir = tmp_path / 'tests'
    tdir.mkdir()
    (tdir / 'test_a.py').write_text(
        'class TestOuter:\n'
        '    class TestInner:\n'
        '        def test_deep(self):\n'
        '            pass\n', encoding='utf-8')
    p = _write_mapping(tmp_path, {
        'tests/test_a.py::TestOuter::TestInner::test_deep': {'case_key': 'K1'},
    })
    assert qm.orphaned_nodeids(p, root=tmp_path) == []


def test_a_syntax_error_is_reported_separately_not_as_orphans(tmp_path):
    """A file that cannot be parsed does not become a wall of phantom renames."""
    tdir = tmp_path / 'tests'
    tdir.mkdir()
    (tdir / 'test_broken.py').write_text('def test_a(:\n    pass\n', encoding='utf-8')
    p = _write_mapping(tmp_path, {
        'tests/test_broken.py::test_a': {'case_key': 'K1'},
        'tests/test_broken.py::test_b': {'case_key': 'K2'},
    })
    orphans, unparseable = qm.orphaned_and_unparseable(p, root=tmp_path)
    assert orphans == []
    assert 'tests/test_broken.py' in unparseable
    assert 'SyntaxError' in unparseable['tests/test_broken.py']


def test_base_keyed_collapses_the_parametrization():
    """A stored [chromium] key resolves for any parametrization.

    377 of 378 mapping rows carry [chromium] because pytest.ini pins it.
    The reporter stripped the param from the runtime nodeid but not from
    the stored key, so a run under another browser matched 0 of 121
    reviewed rows.
    """
    mapping = {
        'tests/a.py::test_x[chromium]': 'K1',
        'tests/a.py::test_y': 'K2',
    }
    base = qm.base_keyed(mapping)
    assert base['tests/a.py::test_x'] == 'K1'   # firefox / no-param now resolve
    assert base['tests/a.py::test_y'] == 'K2'


def test_base_keyed_agrees_across_params_of_one_function():
    """Params of one function pointing at one case collapse to that case."""
    mapping = {
        'tests/a.py::test_x[chromium]': 'K1',
        'tests/a.py::test_x[firefox]': 'K1',
    }
    assert qm.base_keyed(mapping) == {'tests/a.py::test_x': 'K1'}


def test_base_keyed_drops_an_ambiguous_base():
    """Params of one function pointing at DIFFERENT cases are left out.

    Guessing would write a status onto the wrong case; the exact match has
    to settle it.
    """
    mapping = {
        'tests/a.py::test_x[chromium]': 'K1',
        'tests/a.py::test_x[firefox]': 'K2',
        'tests/a.py::test_y[chromium]': 'K3',
    }
    base = qm.base_keyed(mapping)
    assert 'tests/a.py::test_x' not in base
    assert base['tests/a.py::test_y'] == 'K3'
