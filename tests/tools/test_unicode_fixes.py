"""Pins for the xlsx converters' Unicode map.

The map turns the typography QA's spreadsheets carry (en and em dashes,
smart quotes, arrows, non-breaking spaces) into plain ASCII before a
case reaches QA Touch. Two typography sweeps of the source had flattened
its literal keys to ASCII, so from 08/2026 to 09/14/2026 it rewrote every
plain hyphen as " - " and left the smart quotes alone, and nothing said
so. These pins hold the keys as the characters they name. The characters
are written as escapes here too, so the same sweep cannot flatten the pin.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import qa_xlsx_to_canonical_csv as canonical  # noqa: E402
from tools import qa_xlsx_to_qatouch_csv as qatouch  # noqa: E402

MODULES = [canonical, qatouch]
EN_DASH, LEFT_DQ, RIGHT_DQ, LEFT_SQ, RIGHT_SQ, ARROW = "\u2013", "\u201c", "\u201d", "\u2018", "\u2019", "\u2192"


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_every_key_is_a_non_ascii_character(module):
    """An ASCII key means a sweep flattened the map again."""
    ascii_keys = [k for k in module.UNICODE_FIXES if k.isascii()]
    assert ascii_keys == [], f"ASCII keys in UNICODE_FIXES: {ascii_keys}"
    assert len(module.UNICODE_FIXES) == 10


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_sanitize_rewrites_the_typography_and_nothing_else(module):
    """Dashes become ' - ', quotes straighten, the arrow becomes a dash;
    a plain hyphen and plain quotes stay as they are."""
    typed = f"H.264{EN_DASH}only {LEFT_DQ}test{RIGHT_DQ} {LEFT_SQ}x{RIGHT_SQ} y"
    assert module.sanitize(typed) == 'H.264 - only "test" \'x\' y'
    assert module.sanitize("H.264-only 'x' \"y\"") == "H.264-only 'x' \"y\""
    assert module.sanitize(f"a {ARROW} b") == "a - b"
