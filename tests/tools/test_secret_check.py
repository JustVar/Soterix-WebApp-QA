"""Pins for tools/secret_check.py: which .env keys count as secrets, how a value
is found in text, how the staged diff is read, and what the gate prints."""
from __future__ import annotations

from tools import secret_check as sc

ENV = """
# comment
QA_US_USER=test-auto-qa@example.com
QA_US_PASSWORD=Sup3rSecret!
QATOUCH_API_KEY=abcdef0123456789
QATOUCH_PROJECT_ID=JlW1
C2C_CAMERA_USER=root
C2C_CAMERA_PASS="Lab-Cam-9"
SHORT_PASS=ab
PLACEHOLDER_TOKEN=changeme
AZURE_SECRET_EXPIRES=2026-07-22
API_TOKEN_URL=https://login.example.com/oauth2/token
export SMTP_SECRET='quoted-value-here'
"""


def test_secret_values_keeps_credential_keys_and_drops_the_rest():
    """Passwords, keys, tokens and secrets with real values are the secrets; users, ids,
    short and placeholder values, dates and URLs named by their key are not."""
    assert sc.secret_values(ENV) == {
        'QA_US_PASSWORD': 'Sup3rSecret!', 'QATOUCH_API_KEY': 'abcdef0123456789',
        'C2C_CAMERA_PASS': 'Lab-Cam-9', 'SMTP_SECRET': 'quoted-value-here'}


def test_find_secrets_names_the_key_and_line_never_the_value():
    """A finding says which .env key's value sits on which line; the value itself is not in the finding."""
    secrets = sc.secret_values(ENV)
    text = 'step: Authenticate with root/Lab-Cam-9 via Basic Auth\nnext line\nkey abcdef0123456789 here\n'
    found = sc.find_secrets(text, secrets, 'config/snap.json')
    assert found == [{'path': 'config/snap.json', 'line': 1, 'key': 'C2C_CAMERA_PASS'},
                     {'path': 'config/snap.json', 'line': 3, 'key': 'QATOUCH_API_KEY'}]
    assert all('Lab-Cam-9' not in str(f) for f in found)


def test_staged_added_lines_reads_paths_and_new_line_numbers(monkeypatch):
    """Only added lines count, each with its line number in the new file."""
    diff = '\n'.join([
        'diff --git a/tests/c2c/conftest.py b/tests/c2c/conftest.py',
        '--- a/tests/c2c/conftest.py', '+++ b/tests/c2c/conftest.py',
        '@@ -10,2 +10,3 @@', ' context', '+    "password": camera_config["Lab-Cam-9"],', ' more',
        '@@ -40 +41 @@', '-old', '+new',
    ])
    monkeypatch.setattr(sc, '_git', lambda *a: diff)
    added = sc.staged_added_lines()
    assert added == {'tests/c2c/conftest.py': [(11, '    "password": camera_config["Lab-Cam-9"],'), (41, 'new')]}
    findings = sc.check_staged(sc.secret_values(ENV))
    assert findings == [{'path': 'tests/c2c/conftest.py', 'line': 11, 'key': 'C2C_CAMERA_PASS'}]


def test_main_blocks_on_a_staged_secret_and_passes_a_clean_diff(tmp_path, monkeypatch, capsys):
    """Exit 1 with the key named when a staged line carries a value; exit 0 and a count otherwise."""
    env = tmp_path / '.env'
    env.write_text(ENV, encoding='utf-8')
    monkeypatch.setattr(sc, 'staged_added_lines', lambda: {'docs/x.md': [(3, 'password is Sup3rSecret! ok')]})
    assert sc.main(['--env', str(env)]) == 1
    out = capsys.readouterr().out
    assert '[SECRET] docs/x.md:3  carries the value of QA_US_PASSWORD from .env' in out
    assert 'Sup3rSecret' not in out
    monkeypatch.setattr(sc, 'staged_added_lines', lambda: {'docs/x.md': [(3, 'nothing to see')]})
    assert sc.main(['--env', str(env)]) == 0
    assert 'carry none of the 4 credential values' in capsys.readouterr().out


def test_main_is_quiet_without_an_env_file(tmp_path, capsys):
    """A machine with no .env has nothing to compare against and must not block."""
    assert sc.main(['--env', str(tmp_path / 'missing.env')]) == 0
    assert 'nothing to compare' in capsys.readouterr().out


def test_secret_values_reads_the_file_the_way_the_suite_does():
    """An inline comment and an escaped quote are not a part of the value, and an all-digit password is a secret."""
    text = 'QA_PASSWORD=Hunter22x # the india one\nCAM_PASSWORD=12345678\nAPI_TOKEN="ab\\"cdefgh"\nRETRY_KEY=12345678\n'
    assert sc.secret_values(text) == {'QA_PASSWORD': 'Hunter22x', 'CAM_PASSWORD': '12345678', 'API_TOKEN': 'ab"cdefgh'}


def test_an_all_digit_value_is_a_secret_only_under_a_key_that_ends_in_a_password_word():
    """C2C_CAMERA_PASS and QA_PASSWORD keep their digits; PASSWORD_MIN_LENGTH and BYPASS_TIMEOUT_MS are settings, not secrets."""
    text = ("C2C_CAMERA_PASS=12345678\nQA_PASSWORD=87654321\nPASSWORD_MIN_LENGTH=12345678\n"
            "BYPASS_TIMEOUT_MS=120000\nPASS_RATE_THRESHOLD=100000\n")
    assert sc.secret_values(text) == {"C2C_CAMERA_PASS": "12345678", "QA_PASSWORD": "87654321"}


def test_a_value_that_names_a_variable_is_kept_as_written():
    """dotenv interpolates by default. With it on, ${HOME}/x resolved to this machine's real home
    path, stopped looking like a placeholder, and the scan then masked that path out of every
    published log (audit 09/22/2026). The value stays literal, so only the literal can match."""
    import os
    home = os.path.expanduser("~")
    values = sc.secret_values("INTERP_PASSWORD=${HOME}/xyzzy\n")
    assert values == {"INTERP_PASSWORD": "${HOME}/xyzzy"}
    assert all(home not in v for v in values.values())
    # a bare ${...} is still read as a placeholder and dropped
    assert sc.secret_values("QA_PASSWORD=${NOT_SET}\n") == {}
