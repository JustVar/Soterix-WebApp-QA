"""The project table, checked against this repo's own documentation.

The behaviour of soterix_qa_shared.reporting.products is tested in the
package. What cannot move there is the table's agreement with
docs/QA_TOUCH_INTEGRATION.md: the doc lives here, and a project key that
drifts from it sends a run's results to the wrong QA Touch project.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins import products  # noqa: E402


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
