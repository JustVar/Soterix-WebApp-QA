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
ENV_SECRETS = {'QA_PASSWORD': 'Tr1cky-Value-77', 'CAMERA_PASS': 'Sp&rt<an"0!x'}

LEFT_ALONE = [
    "login_data = {'email': 'qa@example.com', 'password': '***'}",
    '"password": "***"',
    '"password_env": "QA_PASSWORD",',
    'QA_PASSWORD is not set in .env',
    '<input type="password" name="password" placeholder="Password">',
    "password = '{password}'",
    "password: '<your password>'",
    'the JSESSIONID cookie was dropped by the server',
    'Authorization: Bearer <token>',
    'x-vsaas-key header is missing',
    'waiting for locator("input[type=\'password\']") to be visible',
    'password: "Enter your password"',
    '<input placeholder="Password" password="required field">',
    'autocomplete="current-password" name="password" value=""',
    '3 passed, 1 failed in 12.4s',
    'bypass=true&compass=north',
    # the run page's own script: the pass/fail key of a JS object, once masked to `pass: '***'`
    # in every run folder
    "var NAMES = {fail: 'Failed', skip: 'Skipped', pass: 'Passed', unkn: 'Unknown', all: 'All'};",
    "var WORDS = {fail: 'failed', skip: 'were skipped', pass: 'passed'};",
    "{'pass': 'ok', 'fail': 'bad'}",
    'password=***&next=/home',
    'see https://playwright.dev/python/docs/api/class-page#page-goto for the options',
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
    ('the form was sent with Tr1cky-Value-77 in it', '.env value of QA_PASSWORD', 'Tr1cky-Value-77'),
    # the forms a report gives a traceback (run.html once held the first one, unseen)
    ('E  {&quot;email&quot;: &quot;qa@example.com&quot;, &quot;password&quot;: &quot;hunter2-long&quot;}', 'password value', 'hunter2-long'),
    ('E  {&#x27;password&#x27;: &#x27;hunter2-long&#x27;}', 'password value', 'hunter2-long'),
    ('data-jsonblob="{&#34;password&#34;: &#34;hunter2-long&#34;}"', 'password value', 'hunter2-long'),
    ('"longrepr": "{\\"password\\": \\"hunter2-long\\"}"', 'password value', 'hunter2-long'),
    ('"password":"hunter2-long"', 'password value', 'hunter2-long'),
    ("'user_password': 'hunter2-long'", 'password value', 'hunter2-long'),
    ("pwd='hunter2-long'", 'password value', 'hunter2-long'),
    # bare values: a URL, a form body, an env line
    ('POST /login?username=justin&password=Hunter22xyz HTTP/1.1', 'password value', 'Hunter22xyz'),
    ('QA_PASSWORD=Hunter22xyz', 'password value', 'Hunter22xyz'),
    # cookies and tokens in their other shapes
    ("{'name': 'JSESSIONID', 'value': '" + COOKIE + "', 'domain': 'x'}", 'session cookie', COOKIE),
    ('{"name": "JSESSIONID", "value": "' + COOKIE + '"}', 'session cookie', COOKIE),
    ('Set-Cookie: JSESSIONID=ABC123DEF456; HttpOnly', 'session cookie', 'ABC123DEF456'),
    ('Authorization: Basic YWRtaW46aHVudGVyMg==', 'basic auth', 'YWRtaW46aHVudGVyMg'),
    ('opening rtsp://admin:hunter2-long@192.0.2.50/stream1', 'password in a URL', 'hunter2-long'),
    # a .env value with HTML, URL and JSON special characters, in each form
    ('<td>Sp&amp;rt&lt;an&quot;0!x</td>', '.env value of CAMERA_PASS', 'Sp&amp;rt&lt;an&quot;0!x'),
    ('body: user=root&pw=Sp%26rt%3Can%220%21x', '.env value of CAMERA_PASS', 'Sp%26rt%3Can%220%21x'),
    ('"text": "typed Sp&rt<an\\"0!x"', '.env value of CAMERA_PASS', 'Sp&rt<an\\"0!x'),
]


@pytest.mark.parametrize(('line', 'what', 'secret'), FOUND)
def test_a_secret_is_named_and_masked_and_the_rest_of_the_line_stays(line, what, secret):
    """The finding names the kind, the clean text has no secret, and the words around it are still there."""
    clean, found = es.scan_text('first line\n' + line, ENV_SECRETS)
    assert {(f['line'], f['what']) for f in found} == {(2, what)}
    assert secret not in clean
    assert es.MASK in clean
    assert clean.startswith('first line\n' + line[:line.index(secret)])   # the words before the secret stay


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
    """Without --redact the files stay as they are and the exit code is 1."""
    run = _run_folder(tmp_path)
    before = (run / 'log' / 'test_login.log').read_text(encoding='utf-8')
    assert es.main([str(run), '--env', str(tmp_path / 'no.env')]) == 1
    assert (run / 'log' / 'test_login.log').read_text(encoding='utf-8') == before
    out = capsys.readouterr().out
    assert 'test_login.log:1  password value' in out
    assert 'hunter2-long' not in out


def test_redact_cleans_the_file_and_leaves_the_zip_alone(tmp_path, capsys):
    """--redact masks the secret, leaves the zip alone, exits 0, and a second pass finds nothing."""
    run = _run_folder(tmp_path)
    env = tmp_path / 'test.env'
    env.write_text('QA_PASSWORD=Tr1cky-Value-77\n', encoding='utf-8')
    assert es.main([str(run), '--redact', '--env', str(env)]) == 0
    assert 'hunter2-long' not in (run / 'log' / 'test_login.log').read_text(encoding='utf-8')
    assert (run / 'traces' / 'a-trace.zip').read_bytes().endswith(COOKIE.encode())
    assert '1 secret(s) redacted' in capsys.readouterr().out
    assert es.main([str(run), '--env', str(env)]) == 0
    assert '0 secret(s) found' in capsys.readouterr().out


def test_a_missing_folder_is_a_tool_error(tmp_path):
    """A path that is not a folder exits 2 and scans nothing."""
    assert es.main([str(tmp_path / 'missing')]) == 2


def test_a_redacted_file_keeps_its_line_endings(tmp_path):
    """Only the secret's bytes change: CRLF stays CRLF, LF stays LF, a lone CR stays."""
    run = tmp_path / 'runs' / '2026-09-18_09-00-06__tests-ui'
    run.mkdir(parents=True)
    raw = b"a\r\n'password': 'hunter2-long'\r\nprogress\rdone\nb\n"
    (run / 'x.log').write_bytes(raw)
    found, errors = es.scan_run(run, {}, redact=True)
    assert len(found) == 1
    assert errors == []
    assert (run / 'x.log').read_bytes() == raw.replace(b'hunter2-long', b'***')


def test_a_file_that_cannot_be_written_fails_loud_and_scans_the_other_files(tmp_path, monkeypatch, capsys):
    """A secret in a file that refuses the write: exit 2, the error names the file, the other file is still cleaned."""
    run = tmp_path / 'runs' / '2026-09-17_09-00-06__tests-ui'
    run.mkdir(parents=True)
    (run / 'x.log').write_text("'password': 'hunter2-long'", encoding='utf-8')
    (run / 'y.log').write_text("'password': 'hunter2-long' again", encoding='utf-8')
    real_open = open

    def refuse_write(path, mode='r', *args, **kwargs):
        if 'w' in mode and str(path).endswith('x.log'):
            raise PermissionError(13, 'read-only')
        return real_open(path, mode, *args, **kwargs)

    env = tmp_path / 'test.env'
    env.write_text('QA_PASSWORD=Tr1cky-Value-77' + chr(10), encoding='utf-8')
    monkeypatch.setattr('builtins.open', refuse_write)
    assert es.main([str(run), '--redact', '--env', str(env)]) == 2
    assert 'hunter2-long' not in (run / 'y.log').read_text(encoding='utf-8')
    captured = capsys.readouterr()
    assert 'x.log' in captured.err
    assert 'could not be written' in captured.err
    assert 'hunter2-long' not in captured.out + captured.err


def test_a_pass_with_no_secret_values_still_masks_by_shape(tmp_path, capsys):
    """With no .env the scan reads shapes only, says so, and still redacts a password-shaped value."""
    run = _run_folder(tmp_path)
    assert es.main([str(run), '--redact', '--env', str(tmp_path / 'no.env')]) == 0
    assert 'hunter2-long' not in (run / 'log' / 'test_login.log').read_text(encoding='utf-8')
    assert 'patterns only' in capsys.readouterr().err


def test_a_long_line_with_no_secret_is_read_in_a_moment():
    """A 200 KB run of letters took 110 s with the unanchored URL pattern."""
    import time
    start = time.perf_counter()
    clean, found = es.scan_text('a' * 200_000 + ' rtsp://admin:Hunter22x@192.0.2.9/live', {})
    assert time.perf_counter() - start < 5
    assert [f['what'] for f in found] == ['password in a URL']
    assert 'Hunter22x' not in clean


@pytest.mark.parametrize("line", [
    "192.0.2.9-rtsp://admin:Hunter22x@192.0.2.9/live",
    "camera-stream-endpoint-rtsp://admin:Hunter22x@192.0.2.9/live",
    "2026-09-21T10:25:54.rtsp://admin:Hunter22x@cam/live",
    "https://oauth2:" + "e" * 403 + "@gitlab.example.test/repo.git",
])
def test_a_password_in_a_url_is_found_whatever_stands_before_the_scheme(line):
    """A bounded scheme was fast and missed each of these; the literal :// finds them."""
    clean, found = es.scan_text(line, {})
    assert [f["what"] for f in found] == ["password in a URL"]
    assert "Hunter22x" not in clean
    assert "e" * 403 not in clean


def test_an_all_digit_secret_is_masked_only_on_its_own():
    """A 6-digit password masked as a bare substring ate ids, epochs and durations in every run folder."""
    clean, found = es.scan_text("id 9912345678 epoch 1712345600 password 123456 here", {"CAMERA_PASS": "123456"})
    assert "9912345678" in clean
    assert "1712345600" in clean
    assert "password *** here" in clean
    assert [f["what"] for f in found] == [".env value of CAMERA_PASS"]
