"""Pins for the xlsx converters' Unicode map.

The map turns the typography QA's spreadsheets carry (en and em dashes,
smart quotes, arrows, non-breaking spaces) into plain ASCII before a
case reaches QA Touch. Its dash, arrow and single-quote keys were already
ASCII in the file's first commit (07/14/2026), and the 08/07 typography
sweep flattened the double quotes too, so until 09/14/2026 it rewrote
every plain hyphen as " - " and left the smart quotes alone, and nothing
said so. These pins hold the keys as the characters they name, written as
escapes here too so a sweep cannot flatten the pin.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import (  # noqa: E402
    qa_xlsx_to_canonical_csv as canonical,
    qa_xlsx_to_qatouch_csv as qatouch,
)

MODULES = [canonical, qatouch]
EN_DASH, LEFT_DQ, RIGHT_DQ, LEFT_SQ, RIGHT_SQ, ARROW = "\u2013", "\u201c", "\u201d", "\u2018", "\u2019", "\u2192"
EM_DASH, MINUS, REPLACEMENT, NBSP = "\u2014", "\u2212", "\ufffd", "\u00a0"


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_every_key_is_a_non_ascii_character(module):
    """The map has its ten entries and no ASCII key, which a sweep would leave behind."""
    ascii_keys = [k for k in module.UNICODE_FIXES if k.isascii()]
    assert ascii_keys == [], f"ASCII keys in UNICODE_FIXES: {ascii_keys}"
    assert len(module.UNICODE_FIXES) == 10


@pytest.mark.parametrize("module", MODULES, ids=lambda m: m.__name__.rsplit(".", 1)[-1])
def test_sanitize_rewrites_the_typography_and_nothing_else(module):
    """Every typographic key becomes its ASCII value, and plain ASCII text stays as it is."""
    typed = f"H.264{EN_DASH}only {LEFT_DQ}test{RIGHT_DQ} {LEFT_SQ}x{RIGHT_SQ} y"
    assert module.sanitize(typed) == 'H.264 - only "test" \'x\' y'
    assert module.sanitize(f"a{EM_DASH}b{MINUS}c{REPLACEMENT}d") == "a - b - c - d"
    assert module.sanitize(f"a{NBSP}b {ARROW} c") == "a b - c"
    assert module.sanitize("H.264-only 'x' \"y\" Admin -> Users") == "H.264-only 'x' \"y\" Admin -> Users"
