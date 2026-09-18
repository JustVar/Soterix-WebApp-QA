"""Pins for tools/evidence_scan.py: what it must leave alone comes first.

The text that looks most like a secret and is not one is the spec: a mask,
an env KEY name, a password input in HTML, a template variable. A scan that
redacts those makes the evidence unreadable and gets switched off.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from tools import evidence_scan as es  # noqa: E402

COOKIE = 'A1B2C3D4E5F60718293A4B5C6D7E8F90'
ENV_SECRETS = {'QA_INDIA_PASSWORD': 'Tr1cky-Value-77'}

LEFT_ALONE = [
    "login_data = {'email': 'qa@example.com', 'password': '***'}",
    '"password": "***"',
    '"password_env": "QA_INDIA_PASSWORD",',
    'QA_INDIA_PASSWORD is not set in .env',
    '<input type="password" name="password" placeholder="Password">',
    "password = '{password}'",
    "password: '<your password>'",
    'the JSESSIONID cookie was dropped by the server',
    'Authorization: Bearer <token>',
    'x-vsaas-key header is missing',
    'waiting for locator("input[type=\'password\']") to be visible',
]


@pytest.mark.parametrize('line', LEFT_ALONE)
def test_text_that_only_looks_like_a_secret_is_left_alone(line):
    """A mask, a key name, a password field and a template pass through with no finding and no change."""
    clean, found = es.scan_text(line, ENV_SECRETS)
    assert found == []
    assert clean == line


FOUND = [
    ('Cookie: JSESSIONID=' + COOKIE + '; Path=/', 'session cookie', COOKIE),
    ("'JSESSIONID': '" + COOKIE + "'", 'session cookie', COOKIE),
    ('Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.payload-part.sig-part_0123', 'bearer token', 'eyJhbGciOiJIUzI1NiJ9'),
    ("headers = {'x-vsaas-key': 'k3y-0123456789abcdef'}", 'integration key', 'k3y-0123456789abcdef'),
    ("login_data = {'email': 'qa@example.com', 'password': 'hunter2-long'}", 'password value', 'hunter2-long'),
    ('the form was sent with Tr1cky-Value-77 in it', '.env value of QA_INDIA_PASSWORD', 'Tr1cky-Value-77'),
]


@pytest.mark.parametrize(('line', 'what', 'secret'), FOUND)
def test_a_secret_is_named_and_masked_and_the_rest_of_the_line_stays(line, what, secret):
    """The finding names the kind, the clean text has no secret, and the words around it are still there."""
    clean, found = es.scan_text('first line\n' + line, ENV_SECRETS)
    assert [(f['line'], f['what']) for f in found] == [(2, what)]
    assert secret not in clean
    assert es.MASK in clean
    assert clean.startswith('first line\n' + line[:8])


def test_a_finding_never_holds_the_value():
    """What the tool prints is built from the findings, so no finding field may carry a secret."""
    for line, _what, secret in FOUND:
        _clean, found = es.scan_text(line, ENV_SECRETS)
        assert all(secret not in str(v) for f in found for v in f.values())


def _run_folder(tmp_path: Path) -> Path:
    run = tmp_path / 'runs' / '2026-09-18_09-00-06__tests-ui'
    (run / 'log').mkdir(parents=True)
    (run / 'log' / 'test_login.log').write_text("E   {'password': 'hunter2-long'}\n", encoding='utf-8')
    (run / 'summary.json').write_text('{"passed": 3}\n', encoding='utf-8')
    (run / 'traces').mkdir()
    (run / 'traces' / 'a-trace.zip').write_bytes(b'JSESSIONID=' + COOKIE.encode())
    return run


def test_report_mode_exits_1_and_writes_nothing(tmp_path, capsys):
    """Without --redact the files stay as they are, no marker appears, and the exit code is 1."""
    run = _run_folder(tmp_path)
    before = (run / 'log' / 'test_login.log').read_text(encoding='utf-8')
    assert es.main([str(run), '--env', str(tmp_path / 'no.env')]) == 1
    assert (run / 'log' / 'test_login.log').read_text(encoding='utf-8') == before
    assert not (run / es.DONE_MARKER).exists()
    out = capsys.readouterr().out
    assert 'test_login.log:1  password value' in out
    assert 'hunter2-long' not in out


def test_redact_cleans_the_file_marks_the_folder_and_skips_it_next_time(tmp_path, capsys):
    """--redact masks the secret, leaves the zip alone, exits 0, and a second pass reads 0 folders."""
    run = _run_folder(tmp_path)
    runs = run.parent
    assert es.main(['--runs-dir', str(runs), '--redact', '--env', str(tmp_path / 'no.env')]) == 0
    assert 'hunter2-long' not in (run / 'log' / 'test_login.log').read_text(encoding='utf-8')
    assert (run / 'traces' / 'a-trace.zip').read_bytes().endswith(COOKIE.encode())
    assert (run / es.DONE_MARKER).exists()
    capsys.readouterr()
    assert es.main(['--runs-dir', str(runs), '--redact', '--env', str(tmp_path / 'no.env')]) == 0
    assert '0 run folder(s) read' in capsys.readouterr().out


def test_no_target_or_two_targets_is_a_tool_error(tmp_path):
    """One run folder or --runs-dir, not none and not the two."""
    assert es.main([]) == 2
    assert es.main([str(tmp_path), '--runs-dir', str(tmp_path)]) == 2
