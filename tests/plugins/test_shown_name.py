"""Pins for matching a name the app shows cut short (Maps, Event Wall)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.shared.helpers.shown_name import is_shown_as, shown_as  # noqa: E402

NAME = "Example Corporate Office"


@pytest.mark.parametrize("text", [
    "Example Corporate Office",
    "Example Corporate Off...",
    "Example Corporat...",
    "Example Corporate Off…",
    "  Videonetics   Corporate Office ",
])
def test_the_name_and_its_cuts_match(text):
    """The full name, and any cut of it ending in an ellipsis, is the site."""
    assert is_shown_as(text, NAME)
    assert shown_as(NAME).match(" ".join(text.split()))


@pytest.mark.parametrize("text", [
    "Example Corporate Office 12",   # the count belongs to a sibling
    "Example Corporate Offices",     # a different, longer name
    "Example Corp",                  # cut with no ellipsis: some other name
    "Newtown Action Area",
    "Video...",                          # a head shorter than MIN_HEAD
    "Example Corporate Off... 12",
])
def test_anything_else_does_not_match(text):
    """Neither a longer name, a sibling count, a bare prefix, nor a too-short head is the site."""
    assert not is_shown_as(text, NAME)
    assert not shown_as(NAME).match(text)
