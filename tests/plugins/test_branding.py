"""The branding assets this repo commits.

The behaviour of soterix_qa_shared.reporting.branding is tested in the
package, against files a fixture writes. What cannot move there is whether
THIS repo's real logo files are present and readable: the package has no
copy of them, and a missing one leaves every HTML report with a broken
image.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins import branding  # noqa: E402


def test_repo_assets_are_present():
    """The committed branding files exist and are PNGs."""
    for p in (branding.WIDE_LOGO, branding.SQUARE_LOGO):
        assert (REPO_ROOT / p).read_bytes().startswith(b'\x89PNG'), p
