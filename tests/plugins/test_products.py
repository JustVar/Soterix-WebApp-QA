"""Unit tests for plugins/products.py.

The project table against the doc's spellings, the name lookup, the
precedence of `product_for` (marker, path rule, mapping default,
environment, NexaiQ-Core), and the run label for one product or a mix.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins import products  # noqa: E402

CORE = 'tests/ui/views/test_views_basic.py::TestViews::test_open[chromium]'
C2C = 'tests/ui/c2c/test_c2c_camera.py::TestCamera::test_reboot[chromium]'


def test_table_matches_the_integration_doc():
    """The table carries the doc's six projects, spelled as the doc spells them."""
    doc = (REPO_ROOT / 'docs' / 'QA_TOUCH_INTEGRATION.md').read_text(encoding='utf-8')
    section = doc.split('## QA Touch projects', 1)[1].split('\n## ', 1)[0]
    rows = re.findall(r'^\| ([^|]+?) \| `(\w+)` \|', section, flags=re.MULTILINE)
    assert dict((key, name) for name, key in rows) == products.PRODUCTS
    assert products.PRODUCTS == {
        'JlW1': 'NexaiQ-Core', 'P0BK': 'NexaiQ-Neurosen', '60w8': 'NexaiQ-Technician App',
        '70l1': 'NexaiQ-Partner Admin Tool', 'K5kB': 'NexiaQ-Mobile',
        '60W5': 'NexaiQ-Camera 2 Cloud'}


def test_product_name_known_unknown_and_empty():
    """A known key names its product. An unknown key stays visible as itself."""
    assert products.product_name('JlW1') == 'NexaiQ-Core'
    assert products.product_name('60W5') == 'NexaiQ-Camera 2 Cloud'
    assert products.product_name('ZZZ9') == 'ZZZ9'
    assert products.product_name('') == ''
    assert products.product_name(None) == ''


@pytest.mark.parametrize(('nodeid', 'marker', 'default', 'env', 'key'), [
    (C2C, 'P0BK', 'K5kB', '70l1', 'P0BK'),     # the marker beats everything
    (C2C, None, 'K5kB', '70l1', '60W5'),       # the path rule beats the mapping default
    ('tests\\ui\\c2c\\test_x.py::test_a', None, None, None, '60W5'),  # backslashes too
    (CORE, None, 'K5kB', '70l1', 'K5kB'),      # the mapping default beats the environment
    (CORE, None, None, '70l1', '70l1'),        # the environment beats the built-in default
    (CORE, None, None, '  ', 'JlW1'),          # a blank environment value is no value
    (CORE, None, None, None, 'JlW1'),          # nothing set: NexaiQ-Core
    ('tests/ui/c2c_extra/test_x.py::test_a', None, None, None, 'JlW1'),  # the rule wants the folder
    ('', None, None, None, 'JlW1'),
])
def test_product_for_precedence(monkeypatch, nodeid, marker, default, env, key):
    """Marker, then the c2c path rule, then the mapping default, then the
    environment, then NexaiQ-Core."""
    if env is None:
        monkeypatch.delenv(products.ENV_VAR, raising=False)
    else:
        monkeypatch.setenv(products.ENV_VAR, env)
    assert products.product_for(nodeid, marker, default) == key


def test_run_product_single_mixed_and_none():
    """One name when the tests agree, a sorted "Mixed:" label otherwise."""
    assert products.run_product(['NexaiQ-Core', 'NexaiQ-Core']) == 'NexaiQ-Core'
    mixed = products.run_product(['NexaiQ-Core', 'NexaiQ-Camera 2 Cloud', '', 'NexaiQ-Core'])
    assert mixed == 'Mixed: NexaiQ-Camera 2 Cloud, NexaiQ-Core'
    assert products.is_mixed(mixed)
    assert not products.is_mixed('NexaiQ-Core')
    assert not products.is_mixed('')
    assert products.run_product([]) == ''
    assert products.run_product(['', None]) == ''
