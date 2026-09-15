"""Pins for the Maps site option lookup.

The dropdown cuts a long site name in the DOM itself, so the row reads
'Example Corporat...' and the full name is nowhere in it. The lookup
matches the row a tester would click: the name as shown, or a truncation
the asked-for name starts with. An ambiguous head matches nothing, so the
caller reports the drift instead of opening the wrong site.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.shared.pages.maps_page import MapsPage  # noqa: E402

SITES = ["Newtown Action Area", "Example Corporat...", "Virtual edge Box", "PVA_Test"]


class FakeMaps:
    """A MapsPage with its option names supplied, nothing else."""

    def __init__(self, names):
        self._names = names

    site_option_names = property(lambda self: lambda: self._names)
    ELLIPSIS_RE = MapsPage.ELLIPSIS_RE
    _site_option_index = MapsPage._site_option_index


@pytest.mark.parametrize(("site", "expected"), [
    ("Newtown Action Area", 0),
    ("Example Corporate Office", 1),
    ("Virtual edge Box", 2),
    ("PVA_Test", 3),
])
def test_a_site_is_found_whether_its_row_is_cut_or_not(site, expected):
    """The full name matches its row, and a cut row matches the name it is the head of."""
    assert FakeMaps(SITES)._site_option_index(site) == expected


def test_a_site_the_dropdown_does_not_offer_is_not_found():
    """A missing site returns None so the caller can name what is offered."""
    assert FakeMaps(SITES)._site_option_index("Dallas City") is None


def test_a_head_two_sites_share_matches_nothing():
    """Two cut rows with the same head are ambiguous: better no pick than the wrong site."""
    twins = ["Example Corporat...", "Example Corporat..."]
    assert FakeMaps(twins)._site_option_index("Example Corporate Office") is None


def test_the_unicode_ellipsis_counts_too():
    """The app has used both forms; either marks a cut row."""
    assert FakeMaps(["Example Corporat…"])._site_option_index(
        "Example Corporate Office") == 0


def test_a_cut_row_does_not_match_an_unrelated_name():
    """The head has to be the head of the name asked for."""
    assert FakeMaps(["Example Corporat..."])._site_option_index("Newtown Action Area") is None
