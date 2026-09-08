"""Pins for tools/tenant_cleanup.py.

This tool deletes. It read QA_USER directly, so `BOX=us ... --apply`
logged into India and would have deleted from the wrong tenant
(register item 30; item 23 was the same defect in explore_app.py).
These pin the account choice, because the failure is silent - a run
against the wrong tenant looks exactly like a run against the right
one until the data is gone.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import tenant_cleanup as tc  # noqa: E402


def test_the_active_box_account_wins(monkeypatch):
    """get_credentials decides, so BOX picks the tenant."""
    monkeypatch.setattr(
        tc, 'get_credentials',
        lambda: {'email': 'us-account@example.com', 'password': 'us-pw'},
    )
    monkeypatch.setenv('QA_USER', 'india-account@example.com')
    monkeypatch.setenv('QA_PASSWORD', 'india-pw')
    assert tc.active_account() == ('us-account@example.com', 'us-pw')


def test_falls_back_to_qa_user_when_the_box_has_no_account(monkeypatch):
    """A config with no box definitions keeps working."""
    def _raise():
        raise KeyError('no boxes here')
    monkeypatch.setattr(tc, 'get_credentials', _raise)
    monkeypatch.setenv('QA_USER', 'default@example.com')
    monkeypatch.setenv('QA_PASSWORD', 'default-pw')
    assert tc.active_account() == ('default@example.com', 'default-pw')


def test_no_account_at_all_exits_instead_of_guessing(monkeypatch):
    """A destructive tool with no credentials stops; it never guesses."""
    monkeypatch.setattr(tc, 'get_credentials', lambda: {})
    monkeypatch.delenv('QA_USER', raising=False)
    monkeypatch.delenv('QA_PASSWORD', raising=False)
    with pytest.raises(SystemExit) as e:
        tc.active_account()
    assert 'box' in str(e.value).lower()


def test_an_empty_box_account_does_not_beat_the_fallback(monkeypatch):
    """A box entry present but blank must not log in as nobody."""
    monkeypatch.setattr(
        tc, 'get_credentials', lambda: {'email': '', 'password': ''})
    monkeypatch.setenv('QA_USER', 'default@example.com')
    monkeypatch.setenv('QA_PASSWORD', 'default-pw')
    assert tc.active_account() == ('default@example.com', 'default-pw')


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
    card = "JV\nJustin Varughese\nEnterprise Super Admin\njustin@soterixsystems.com"
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
