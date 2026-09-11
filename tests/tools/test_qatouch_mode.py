"""Pins for tools/qatouch_mode.py: the mapping keys it acts on belong to
the project it is pointed at, never to every project in the file."""
from __future__ import annotations

from tools import qatouch_mode as qmode


def test_keys_for_project_reads_only_that_projects_keys():
    """Plain keys go by the test's home root; per-project maps by their own project."""
    reviewed = {
        'tests/ui/a.py::test_core[chromium]': 'CORE1',
        'tests/ui/b.py::test_both[chromium]': {'JlW1': 'CORE2', 'P0BK': 'NEURO2'},
        'tests/c2c/test_c.py::test_cam': 'CAM1',
    }
    assert qmode.keys_for_project(reviewed, 'JlW1') == {'CORE1': ['tests/ui/a.py::test_core[chromium]'],
                                                       'CORE2': ['tests/ui/b.py::test_both[chromium]']}
    assert qmode.keys_for_project(reviewed, '60W5') == {'CAM1': ['tests/c2c/test_c.py::test_cam']}
    assert qmode.keys_for_project(reviewed, 'P0BK') == {'NEURO2': ['tests/ui/b.py::test_both[chromium]']}
    assert qmode.keys_for_project(reviewed, '70l1') == {}
