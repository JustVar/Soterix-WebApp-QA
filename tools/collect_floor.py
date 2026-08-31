#!/usr/bin/env python3
"""Fail when this repo collects fewer tests than it used to.

The gate lives in soterix_qa_shared.gates.collect_floor, which carries the
reasoning and the tests. This file is the part that is specific to this
repository: which suites are watched.

Usage:
  python tools/collect_floor.py            # check against the floor
  python tools/collect_floor.py --update   # record the current counts

The floor is config/collect_floor.json, committed. Going up is always fine.
Going down needs a reason in the commit message.
"""
from __future__ import annotations

import sys
from pathlib import Path

from soterix_qa_shared.gates import collect_floor

ROOT = Path(__file__).resolve().parent.parent

# 'whole repo' is bare pytest, what a developer runs. The offline suites are
# what the collect gate runs with no browser installed, and are the pair most
# likely to shrink by a path typo, because they are named explicitly.
SUITES = {
    'whole repo': [],
    'offline suites': ['tests/plugins', 'tests/tools'],
}

if __name__ == '__main__':
    sys.exit(collect_floor.main(sys.argv[1:], root=ROOT, suites=SUITES))
