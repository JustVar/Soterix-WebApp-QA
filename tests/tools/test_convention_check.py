"""Pins for tools/convention_check.py.

The checker runs on added lines only, so a rule that misfires blocks
nobody but a rule that goes quiet lets a class of defect back in. These
pin the new-test rules (title, Steps block, QA Touch mapping) and the
helpers they stand on, with the mapping passed in so no test reads the
live file.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import convention_check as cc  # noqa: E402

PATH = 'tests/ui/thing/test_thing.py'

CLASS_TEST = '''\
import pytest


class TestThing:
    @pytest.mark.ui
    def test_full(self):
        """Verify the thing.

        Steps:
        1. Do the thing.
           Expected: The thing is done.
        """
        assert True

    def test_no_steps(self):
        """Verify the other thing."""
        assert True

    def test_untitled(self):
        assert True


def test_plain(page):
    """Verify a plain function test.

    Steps:
    1. Look.
       Expected: See.
    """
    assert True
'''.splitlines()


def _def_line(name: str) -> int:
    return next(i for i, line in enumerate(CLASS_TEST) if f'def {name}(' in line)


def _rules(name: str, mapped: set[str]) -> list[str]:
    return [f['rule'] for f in cc.check_line(PATH, CLASS_TEST, _def_line(name), mapped=mapped)]


# ---------------------------------------------------------------- helpers

def test_test_nodeid_finds_the_enclosing_class():
    """A method gets file::Class::name, a plain function file::name."""
    assert cc.test_nodeid(PATH, CLASS_TEST, _def_line('test_full')) == \
        f'{PATH}::TestThing::test_full'
    assert cc.test_nodeid(PATH, CLASS_TEST, _def_line('test_plain')) == f'{PATH}::test_plain'


def test_test_docstring_reads_multi_and_single_line():
    """The docstring reader handles triple-quoted blocks, one-liners, and none."""
    doc = cc.test_docstring(CLASS_TEST, _def_line('test_full'))
    assert doc.startswith('Verify the thing.')
    assert 'Steps:' in doc
    assert cc.test_docstring(CLASS_TEST, _def_line('test_no_steps')) == 'Verify the other thing.'
    assert cc.test_docstring(CLASS_TEST, _def_line('test_untitled')) == ''


def test_mapped_tests_strips_params(tmp_path):
    """Mapped node ids lose their [param] suffix; an unreadable file maps nothing."""
    p = tmp_path / 'mapping.json'
    p.write_text('{"mappings": {"tests/a.py::TestA::test_x[chromium]": {"case_key": "K"},'
                 ' "tests/a.py::test_y[chromium-Line_Person]": {"case_key": "K2"}}}',
                 encoding='utf-8')
    assert cc.mapped_tests(p) == {'tests/a.py::TestA::test_x', 'tests/a.py::test_y'}
    missing = tmp_path / 'none.json'
    assert cc.mapped_tests(missing) == set()


# ---------------------------------------------------------------- rules

def test_mapped_test_with_steps_is_clean():
    """A titled, stepped, mapped test raises no def-line finding."""
    mapped = {f'{PATH}::TestThing::test_full', f'{PATH}::test_plain'}
    assert _rules('test_full', mapped) == []
    assert _rules('test_plain', mapped) == []


def test_unmapped_test_names_the_generator_command():
    """The mapping finding carries the exact generator command for the node id."""
    findings = cc.check_line(PATH, CLASS_TEST, _def_line('test_full'), mapped=set())
    assert [f['rule'] for f in findings] == ['test-without-mapping']
    assert findings[0]['sev'] == 'MEDIUM'
    assert f'--test {PATH}::TestThing::test_full' in findings[0]['msg']
    assert 'after-import' in findings[0]['msg']


def test_missing_steps_block_is_flagged():
    """A docstring with a title but no Steps: block is flagged once."""
    mapped = {f'{PATH}::TestThing::test_no_steps'}
    assert _rules('test_no_steps', mapped) == ['test-without-steps']


def test_missing_docstring_flags_title_and_steps():
    """No docstring means no title and no steps: both findings, one fix."""
    mapped = {f'{PATH}::TestThing::test_untitled'}
    assert _rules('test_untitled', mapped) == ['test-without-title', 'test-without-steps']


def test_parametrized_function_counts_as_mapped_by_any_id():
    """The mapping stores one row per parameter id; the function is mapped
    when any row belongs to it (params are stripped by mapped_tests)."""
    lines = [
        '@pytest.mark.parametrize("x", [1, 2])',
        'def test_p(x):',
        '    """Verify p.',
        '',
        '    Steps:',
        '    1. Go.',
        '       Expected: Gone.',
        '    """',
        '    assert x',
    ]
    bases = {cc.PARAM_SUFFIX_RE.sub('', 'tests/ui/x/test_x.py::test_p[chromium-1]')}
    assert [f['rule'] for f in cc.check_line('tests/ui/x/test_x.py', lines, 1, mapped=bases)] == []


def test_case_rules_apply_to_ui_tests_only():
    """A tooling pin under tests/tools has no QA Touch case: only the
    title rule applies there."""
    lines = ['def test_pin():', '    assert True']
    rules = [f['rule'] for f in cc.check_line('tests/tools/test_x.py', lines, 0, mapped=set())]
    assert rules == ['test-without-title']
    rules = [f['rule'] for f in cc.check_line('tests/ui/x/test_x.py', lines, 0, mapped=set())]
    assert rules == ['test-without-title', 'test-without-steps', 'test-without-mapping']


def test_no_oracle_rule_skips_defs_quoted_in_strings():
    """A sample test file held in a string is data, not a test body."""
    lines = ['SAMPLE = """', 'def test_quoted():', '    pass', '"""',
             'def test_real():', '    """T."""', '    pass']
    names = [f['text'] for f in cc.check_no_oracle_tests(PATH, lines)]
    assert names == ['def test_real():']


def test_existing_rules_still_fire():
    """The sleep rule did not move when the def rules grew."""
    # built by concatenation so the checker's own scan of this file
    # does not read the pattern as a finding
    lines = ['def test_s():', '    """T."""', '    page.wait_for_' + 'timeout(500)']
    rules = [f['rule'] for f in cc.check_line(PATH, lines, 2, mapped=set())]
    assert rules == ['uncommented-sleep']


def test_ticket_rule_fires_in_comment_docstring_and_code():
    for line in ['# see NC-' + '12345 for details',
                 '"""NC-' + '9 tripwire"""',
                 'pytest.skip("NC-' + '20325 broke this")']:
        rules = [f['rule'] for f in cc.check_line('x.py', [line], 0)]
        assert 'ticket-in-code' in rules, line


def test_ticket_rule_ignores_the_bare_project_key():
    assert not cc.check_line('x.py', ['JIRA_PROJECT_KEY = "NC"'], 0)


def test_ticket_finding_in_comment_carries_path_and_line():
    finding = cc.check_line('x.py', ['# NC-' + '1 stale'], 0)[0]
    assert (finding['path'], finding['line']) == ('x.py', 1)


def test_early_exit_ignores_docstring_lines_opening_with_return():
    lines = [
        'def test_ungroup(page):',
        '    """Remove From Folder must',
        '    return the clip un-deleted."""',
        '    assert page',
    ]
    assert not cc.check_early_exit_tests('x.py', lines)


def test_early_exit_still_flags_a_bare_return():
    lines = [
        'def test_vacuous(page):',
        '    """Title."""',
        '    return',
        '    assert page',
    ]
    rules = [f['rule'] for f in cc.check_early_exit_tests('x.py', lines)]
    assert rules == ['early-exit-pass']
