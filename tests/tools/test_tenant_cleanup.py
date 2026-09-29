"""Pins for tools/tenant_cleanup.py.

This tool deletes. The account choice is pinned because the failure is
silent: a run against the wrong tenant looks exactly like a run against
the right one until the data is gone. So the tool reads its account from
get_credentials() and nowhere else, and stops when the pair is empty.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import tenant_cleanup as tc  # noqa: E402


def test_the_account_comes_from_get_credentials_only(monkeypatch):
    """get_credentials decides; a QA_USER set beside it is never read directly."""
    monkeypatch.setattr(
        tc, 'get_credentials',
        lambda: {'email': 'the-account@example.com', 'password': 'the-pw'},
    )
    monkeypatch.setenv('QA_USER', 'other-account@example.com')
    monkeypatch.setenv('QA_PASSWORD', 'other-pw')
    assert tc.active_account() == ('the-account@example.com', 'the-pw')


def test_no_account_at_all_exits_instead_of_guessing(monkeypatch):
    """A destructive tool with no credentials stops and names the keys; it never guesses."""
    monkeypatch.setattr(tc, 'get_credentials', lambda: {})
    monkeypatch.setenv('QA_USER', 'someone@example.com')
    monkeypatch.setenv('QA_PASSWORD', 'pw')
    with pytest.raises(SystemExit) as e:
        tc.active_account()
    assert 'QA_USER' in str(e.value)
    assert 'QA_PASSWORD' in str(e.value)


def test_an_empty_pair_does_not_log_in_as_nobody(monkeypatch):
    """A present but blank pair stops the run the same way."""
    monkeypatch.setattr(tc, 'get_credentials', lambda: {'email': '', 'password': ''})
    with pytest.raises(SystemExit):
        tc.active_account()
    monkeypatch.setattr(tc, 'get_credentials', lambda: {'email': 'a@example.com', 'password': ''})
    with pytest.raises(SystemExit):
        tc.active_account()


# ---------------------------------------------------------------- user cards

def test_card_reader_finds_the_name_below_the_first_line():
    """The first line is the avatar's initials, not the name.

    The old reader matched ^AutoTest against line 0 only, so it saw
    "AP" and reported no leftovers with ten users on screen.
    """
    card = "\n".join([
        "AP", "", "AutoTest Playwright", "", "Remote User", "Supervisor",
        "", "testuser_2026_09_04_09_06_26@example.com",
    ])
    assert tc.user_email_from_card(card) == "testuser_2026_09_04_09_06_26@example.com"


def test_card_reader_ignores_a_real_user():
    """A tenant user's card is never a cleanup candidate."""
    card = "JV\nSome Person\nEnterprise Super Admin\nperson@example.com"
    assert tc.user_email_from_card(card) is None


def test_card_reader_returns_none_without_an_email():
    """No e-mail means no unique handle, so the card is not actionable."""
    assert tc.user_email_from_card("AP\nAutoTest Playwright\nRemote User") is None


def test_card_reader_survives_empty_text():
    """An empty or missing card yields no candidate, never an exception."""
    assert tc.user_email_from_card("") is None
    assert tc.user_email_from_card(None) is None


# ------------------------------------------------------------ rule / group names

def test_rule_matcher_accepts_the_suites_names_truncated_or_not():
    """The rules list cuts the name cell short; the match is start-anchored."""
    for name in ("Owned_Auto_20260904_094850",
                 "Entry-Exit_Auto_20260904_125217",
                 "Owned_Auto_20260904_09...",
                 "Intrusion_Detection_Auto_20260904_1..."):
        assert tc.is_automation_rule(name), name


def test_rule_matcher_rejects_a_real_rule_with_auto_in_its_name():
    """Digits after _Auto_ are the suite's stamp; a human name has none."""
    for name in ("Zone_Auto_Detect", "Auto_", "Occupancy", "", None):
        assert not tc.is_automation_rule(name), name


def test_group_matcher_is_exact_on_the_suites_shape():
    """AutoGroup_<digits> and nothing looser."""
    assert tc.is_automation_group("AutoGroup_0941158049")
    for name in ("AutoGroup_", "AutoGroup_x", "Sales AutoGroup_1", "", None):
        assert not tc.is_automation_group(name), name


def test_bookmark_matcher_accepts_the_suites_names_only():
    """The app's default name and the suite's own three shapes; nothing else."""
    for name in ('New Bookmark', 'AutoTest BM 101530', 'AutoTest Bookmark 101530', 'DEL_20260825145554', 'Test bookmark'):
        assert tc.is_automation_bookmark(name) is True, name
    for name in ('Grant walking by', 'Bookmark', 'New Bookmark 2', 'AutoTest BM', '', None):
        assert tc.is_automation_bookmark(name) is False, name


def test_bookmark_candidates_take_only_the_accounts_live_default_rows():
    """Another user's 'New Bookmark' and a soft-deleted row are never candidates."""
    rows = [
        {'bookmarkId': 1, 'userId': 'auto@example.com', 'comment': 'New Bookmark', 'deletedAt': -1},
        {'bookmarkId': 2, 'userId': 'auto@example.com', 'comment': 'DEL_1', 'deletedAt': 1750000000000},
        {'bookmarkId': 3, 'userId': 'real@example.com', 'comment': 'New Bookmark', 'deletedAt': -1},
        {'bookmarkId': 4, 'userId': 'auto@example.com', 'comment': 'Grant walking by', 'deletedAt': -1},
        {'bookmarkId': 5, 'userId': 'auto@example.com', 'comment': 'AutoTest BM 1', 'deletedAt': None},
    ]
    mine, others = tc.bookmark_candidates(rows, 'auto@example.com')
    assert [r['bookmarkId'] for r in mine] == [1, 5]
    assert [r['bookmarkId'] for r in others] == [3, 4]
