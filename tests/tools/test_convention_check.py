"""Pins for tools/convention_check.py.

The checker runs on added lines only, so a rule that misfires blocks
nobody but a rule that goes quiet lets a class of defect back in. These
pin the new-test rules (title, Steps block, QA Touch mapping), the
tenant-name rule and the helpers they stand on, with the mapping and the
tenant names passed in so no test reads the live files.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

from tools import convention_check as cc  # noqa: E402

PATH = 'tests/ui/thing/test_thing.py'
# One mapped row for the product, so the mapping rule is armed (it stays
# silent for a product with no rows at all)
ARMED = {'tests/ui/other/test_other.py::test_mapped'}

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
    return [f['rule'] for f in cc.check_line(PATH, CLASS_TEST, _def_line(name), mapped=mapped | ARMED)]


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
    findings = cc.check_line(PATH, CLASS_TEST, _def_line('test_full'), mapped=ARMED)
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
    rules = [f['rule'] for f in cc.check_line('tests/tools/test_x.py', lines, 0, mapped=ARMED)]
    assert rules == ['test-without-title']
    rules = [f['rule'] for f in cc.check_line('tests/ui/x/test_x.py', lines, 0, mapped=ARMED)]
    assert rules == ['test-without-title', 'test-without-steps', 'test-without-mapping']


def test_mapping_rule_is_silent_for_a_product_with_no_rows():
    """A fresh QA Touch project has no mapping rows yet. The rule waits
    for the first row of the product instead of flagging every test."""
    lines = ['def test_pin():', '    """Title."""', '    assert True']
    rules = [f['rule'] for f in cc.check_line('tests/ui/x/test_x.py', lines, 0, mapped=set())]
    assert rules == ['test-without-steps']
    assert cc.product_has_mapping('tests/ui/x/test_x.py', set()) is False
    assert cc.product_has_mapping('tests/ui/x/test_x.py', ARMED) is True
    assert cc.product_has_mapping('tests/tools/test_x.py', ARMED) is False


def test_tenant_name_rule_reads_the_configured_names_and_escapes_them():
    """The rule fires on the configured site and camera names, quoted, and
    a name with regex characters matches itself and nothing else. The
    names here are invented, so the live rule never fires on this pin."""
    pattern = cc.tenant_name_pattern(['Harbour Office', 'Dock Cam (1+1)'])
    lines = ['    page.get_by_text("Harbour Office")',
             "    site = 'Dock Cam (1+1)'",
             "    site = 'Dock Cam 11'",
             '    page.get_by_text(config["test_site_name"])']
    hits = [f['line'] for i in range(len(lines))
            for f in cc.check_line('tests/ui/x/test_x.py', lines, i, mapped=set(), tenant_re=pattern)
            if f['rule'] == 'hardcoded-tenant-name']
    assert hits == [1, 2]
    assert cc.tenant_name_pattern([None, '']) is None


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
    rules = [f['rule'] for f in cc.check_line(PATH, lines, 2, mapped=set(), tenant_re=cc.tenant_name_pattern([]))]
    assert rules == ['uncommented-sleep']


def test_ticket_rule_fires_in_comment_docstring_and_code():
    """A ticket key is flagged wherever it sits: comment, docstring, code."""
    for line in ['# see NC-' + '12345 for details',
                 '"""NC-' + '9 tripwire"""',
                 'pytest.skip("NC-' + '20325 broke this")']:
        rules = [f['rule'] for f in cc.check_line('x.py', [line], 0)]
        assert 'ticket-in-code' in rules, line


def test_ticket_rule_ignores_the_bare_project_key():
    """The bare project key is configuration, not a ticket reference."""
    assert not cc.check_line('x.py', ['JIRA_PROJECT_KEY = "NC"'], 0)


def test_ticket_finding_in_comment_carries_path_and_line():
    """A comment-line finding still names its file and line."""
    finding = cc.check_line('x.py', ['# NC-' + '1 stale'], 0)[0]
    assert (finding['path'], finding['line']) == ('x.py', 1)


def test_early_exit_ignores_docstring_lines_opening_with_return():
    """A docstring line may open with the word return."""
    lines = [
        'def test_ungroup(page):',
        '    """Remove From Folder must',
        '    return the clip un-deleted."""',
        '    assert page',
    ]
    assert not cc.check_early_exit_tests('x.py', lines)


def test_early_exit_still_flags_a_bare_return():
    """A real bare return in a test body stays flagged."""
    lines = [
        'def test_vacuous(page):',
        '    """Title."""',
        '    return',
        '    assert page',
    ]
    rules = [f['rule'] for f in cc.check_early_exit_tests('x.py', lines)]
    assert rules == ['early-exit-pass']


def test_skip_in_except_is_flagged_high():
    """A handler that skips reports the app's failure as SKIP."""
    lines = [
        'def test_drag(page):',
        '    """Title."""',
        '    try:',
        '        page.drag()',
        '    except Exception as e:',
        '        pytest.' + 'skip(f"drag not supported: {e}")',
    ]
    findings = cc.check_skip_in_except('x.py', lines)
    assert [f['rule'] for f in findings] == ['skip-in-except']
    assert findings[0]['sev'] == 'HIGH'
    assert findings[0]['line'] == 6


def test_skip_in_except_excused_by_a_why_comment():
    """A commented handler is the deliberate one: absence, not failure."""
    lines = [
        '    # the wall account is not provisioned on this tenant',
        '    except LookupError:',
        '        pytest.' + 'skip("no wall account")',
    ]
    assert not cc.check_skip_in_except('x.py', lines)


def test_speculative_skip_reasons_are_flagged():
    """A hedged reason records a guess, not a measurement."""
    for reason in ['"feature may not be supported"',
                   '"drag not supported in this version"',
                   '"channel add can work differently here"']:
        lines = ['    pytest.' + f'skip({reason})']
        rules = [f['rule'] for f in cc.check_speculative_skips('x.py', lines)]
        assert rules == ['speculative-skip-reason'], reason


def test_measured_skip_reason_is_clean():
    """A reason that states what was measured raises nothing."""
    lines = ['    pytest.' + 'skip("Licenses > Assigned rendered its empty '
             'state: this tenant has no assigned licence")']
    assert not cc.check_speculative_skips('x.py', lines)


def test_speculative_reason_read_across_wrapped_lines():
    """A reason wrapped onto the next line is still read."""
    lines = [
        '        pytest.' + 'skip(',
        '            "No map card has cameras - may be a selector issue"',
        '        )',
    ]
    rules = [f['rule'] for f in cc.check_speculative_skips('x.py', lines)]
    assert rules == ['speculative-skip-reason']


# ---------------------------------------------------------------------------
# 09/11/2026: the four rules the coverage assessment earned
# ---------------------------------------------------------------------------

def test_except_without_why_is_high_unless_the_handler_raises_or_is_explained():
    """A bare handler that returns False is HIGH; a raising one or a commented one is not."""
    silent = ['def go(self):', '    try:', '        self.x()', '    except Exception:', '        return False']
    assert [(f['rule'], f['sev'], f['line']) for f in cc.check_except_without_why('p.py', silent)] == [
        ('except-without-why', 'HIGH', 4)]
    raising = ['def go(self):', '    try:', '        self.x()', '    except PlaywrightError as e:',
               '        raise AssertionError(f"x: {e}") from None']
    assert cc.check_except_without_why('p.py', raising) == []
    failing = ['def go(self):', '    try:', '        self.x()', '    except Exception:', '        pytest.fail("x")']
    assert cc.check_except_without_why('p.py', failing) == []
    explained = ['def go(self):', '    try:', '        self.x()',
                 '    except Exception:  # why: the toast is optional, the row count below is the oracle',
                 '        pass']
    assert cc.check_except_without_why('p.py', explained) == []
    explained_above = ['def go(self):', '    try:', '        self.x()',
                       '    # the loader is optional; the container wait is the arrival signal',
                       '    except Exception:', '        pass']
    assert cc.check_except_without_why('p.py', explained_above) == []


def test_presence_only_oracle_flags_visibility_only_bodies():
    """A body whose only checks are visibility is flagged; a comparison, a negative or a text expectation clears it."""
    weak = ['def test_panel(self):', '    """Title."""', '    self.page.click()',
            '    expect(self.panel).to_be_visible()', '    assert self.rows.first.is_visible()']
    assert [(f['rule'], f['sev']) for f in cc.check_presence_only_tests(PATH, weak)] == [
        ('presence-only-oracle', 'MEDIUM')]
    for strong_line in ('    expect(self.rows).to_have_count(before + 1)',
                        '    assert name in self.titles()',
                        '    expect(self.panel).not_to_be_visible()',
                        '    expect(self.title).to_have_text("Main Gate")',
                        '    expect(self.page).to_have_url(re.compile("/insights"))'):
        strong = [*weak[:-1], strong_line]
        assert cc.check_presence_only_tests(PATH, strong) == [], strong_line


def test_presence_only_is_for_product_tests_only():
    """A pin under tests/tools or tests/plugins is never read on the oracle scale."""
    weak = ['def test_panel(self):', '    """Title."""', '    self.page.click()',
            '    expect(self.panel).to_be_visible()']
    assert cc.check_presence_only_tests('tests/tools/test_x.py', weak) == []
    assert cc.check_presence_only_tests('tests/plugins/test_x.py', weak) == []
    assert [f['rule'] for f in cc.check_presence_only_tests('tests/ui/x/test_x.py', weak)] == [
        'presence-only-oracle']


def test_presence_only_leaves_no_oracle_bodies_and_delegations_alone():
    """No oracle at all belongs to no-oracle-test; an 'oracle' comment names a raising call."""
    none = ['def test_a(self):', '    """Title."""', '    self.page.click()']
    assert cc.check_presence_only_tests(PATH, none) == []
    assert [f['rule'] for f in cc.check_no_oracle_tests(PATH, none)] == ['no-oracle-test']
    delegated = ['def test_b(self):', '    """Title."""',
                 '    # oracle: delete_group raises when the row survives the refresh',
                 '    self.chat.delete_group(name)', '    expect(self.panel).to_be_visible()']
    assert cc.check_presence_only_tests(PATH, delegated) == []


def test_long_blind_wait_flags_a_minute_and_spares_thirty_seconds():
    """A 60 s or longer DOM wait is flagged unless commented; 30 s is not."""
    lines = ['        self.result_images.first.wait_for(state="visible", timeout=' + '60000)',
             '        self.loader.wait_for(state="hidden", timeout=' + '120000)',
             '        expect(self.replay).to_be_visible(timeout=30000)',
             '        # the export job itself runs a minute; its progress bar has no request to follow',
             '        self.progress.wait_for(state="hidden", timeout=' + '90000)']
    hits = [f['line'] for f in [f for i in range(len(lines)) for f in cc.check_line('p.py', lines, i)]
            if f['rule'] == 'long-blind-wait']
    assert hits == [1, 2]


def test_first_on_text_lookup_flags_substring_identity():
    """.first on get_by_text or has_text is flagged unless commented; exact and scoped lookups are not."""
    lines = ['        row = self.page.get_by_' + 'text("main gate").first',
             '        card = self.cards.filter(has_' + 'text=name).first.click()',
             '        row = self.page.get_by_text("main gate", exact=True)',
             '        cell = self.rows.filter(has=self.page.locator("span[title=\'main gate\']")).first',
             '        # the tenant has exactly one card with this word; measured 09/11',
             '        card = self.cards.filter(has_' + 'text="Gate").first']
    hits = [f['line'] for f in [f for i in range(len(lines)) for f in cc.check_line('p.py', lines, i)]
            if f['rule'] == 'first-on-text-lookup']
    assert hits == [1, 2]


def test_the_flaky_mark_is_refused_in_any_form_and_intermittent_passes():
    """The flaky mark belongs to pytest-rerunfailures, which retries it on any
    failure, once even bare (measured 09/17/2026; 17 tests carried it). The
    label is intermittent. The strings are joined so this pin is not a hit."""
    mark = '@pytest.mark.'
    lines = ['    ' + mark + 'flaky(reruns=1)', '    ' + mark + 'flaky', '    ' + mark + 'intermittent',
             '    ' + mark + 'flakyish', 'pytestmark = pytest.mark.' + 'flaky',
             '    pytest.param(1, marks=pytest.mark.' + 'flaky(reruns=2))', '    @mark.' + 'flaky']
    rules = [[f['rule'] for f in cc.check_line('tests/ui/x/test_x.py', lines, i, mapped=set())] for i in range(7)]
    assert rules == [['flaky-marker'], ['flaky-marker'], [], [], ['flaky-marker'], ['flaky-marker'], ['flaky-marker']]



def test_swallowed_default_timeout_flags_the_action_not_the_try():
    """A click with no timeout in a try that only passes: the finding sits on the click's line."""
    lines = [
        'def navigate(self):',
        '    try:',
        '        self.close_icon.click()',
        '        self.other.click(timeout=5000)',
        '        self.page.keyboard.press("Escape")',
        '    except Exception:  # nothing to close',
        '        pass',
    ]
    findings = cc.check_swallowed_default_timeout('x.py', lines)
    assert [(f['rule'], f['line']) for f in findings] == [('swallowed-default-timeout', 3)]
    assert findings[0]['sev'] == 'MEDIUM'


def test_swallowed_default_timeout_is_clean_when_the_handler_raises_or_fails():
    """A handler that re-raises, fails or skips hides nothing, so its try is left alone."""
    for tail in ('        raise', '        pytest.' + 'fail("no close icon")'):
        lines = ['def f(self):', '    try:', '        self.icon.click()', '    except Exception:', tail]
        assert not cc.check_swallowed_default_timeout('x.py', lines), tail


def test_swallowed_default_timeout_survives_a_file_that_does_not_parse():
    """A half-written file is another rule's problem: this one returns nothing."""
    assert cc.check_swallowed_default_timeout('x.py', ['def broken(:', '    try:']) == []


def test_an_absolute_count_and_the_words_of_a_message_are_not_a_strong_oracle():
    """'count() > 0' is presence, and "not found" in the message is not a negative expectation."""
    for weak in ('    assert page.rows.count() > 0, "Create List button not found"',
                 '    assert len(versions) >= 1, "No version info in the page"',
                 '    assert icon.is_visible(), "the icon is not in the row"'):
        assert not cc.is_strong_oracle(weak), weak
    lines = ['def test_button_shows(page):', '    """Title."""',
             '    assert page.button.count() > 0, "Create List button not found"']
    assert [f['rule'] for f in cc.check_presence_only_tests('tests/ui/x/test_x.py', lines)] == ['presence-only-oracle']


def test_a_real_comparison_stays_strong():
    """A baseline, a text, a negative and a combined condition still count."""
    for strong in ('    assert after > before, "no row was added"',
                   '    assert page.rows.count() == before + 1',
                   '    assert name not in names',
                   '    assert rows.count() > 0 and rows.first.inner_text() == name',
                   '    expect(row).to_have_text(name)',
                   '    expect(toast).not_to_be_visible()'):
        assert cc.is_strong_oracle(strong), strong


def test_no_oracle_rule_reads_only_files_that_pytest_collects():
    """A scenario file (no test_ prefix) holds bodies that pass or die on purpose."""
    lines = ['def test_a1():', '    """Runs first."""', '    time.sleep(0.5)  # why: pacing']
    assert cc.check_no_oracle_tests('tests/plugins/xdist_crash_scenario.py', lines) == []
    assert [f['rule'] for f in cc.check_no_oracle_tests('tests/plugins/test_x.py', lines)] == ['no-oracle-test']


MULTI_LINE_SIGNATURE = '''
def test_download(
    page,
    tmp_path,
):
    with page.expect_download() as info:
        page.click("#csv")


def test_gives_up(
    page,
):
    if not page.url:
        return
    assert page.url
'''


def test_a_signature_over_several_lines_has_its_body_read():
    """The `):` that closes a long signature is not the end of the test: its oracle is seen, and so is its bare return."""
    lines = MULTI_LINE_SIGNATURE.splitlines()
    assert cc.check_no_oracle_tests("tests/ui/test_x.py", lines) == []
    early = cc.check_early_exit_tests("tests/ui/test_x.py", lines)
    assert [f["text"] for f in early] == ["return"]


def test_a_nested_handler_and_a_fixture_named_test_are_not_test_exits():
    """A return inside a nested def with a long signature, inside an async def, or inside a fixture named test_* is not flagged."""
    # indented, then dedented: text at column 0 would end this test's body for the checker's own block reader
    source = textwrap.dedent('''
        import pytest


        @pytest.fixture
        def test_site():
            return "Newtown"


        def test_blocks_images(page):
            def handler(
                route,
            ):
                return route.abort()

            async def later():
                return 1

            page.route("**/*.png", handler)
            assert page.url
    ''')
    lines = source.splitlines()
    assert cc.check_early_exit_tests("tests/ui/test_x.py", lines) == []
    assert cc.check_no_oracle_tests("tests/ui/test_x.py", lines) == []


@pytest.mark.parametrize("body", [
    "page.wait_for_url('**/views')",
    "with page.expect_response('**/api'):\n        page.click('#go')",
    "mock.assert_called_once_with(3)",
])
def test_a_call_that_raises_when_the_thing_does_not_happen_is_an_oracle(body):
    """wait_for_url, expect_response and a mock's assert_called raise on a miss, so the test can fail."""
    lines = f"def test_x(page, mock):\n    {body}\n".splitlines()
    assert cc.check_no_oracle_tests("tests/ui/test_x.py", lines) == []


def test_a_sleep_is_not_an_oracle():
    """wait_for_timeout never raises: a body with only that is still a test with no oracle."""
    lines = "def test_x(page):\n    page.wait_for_timeout(500)  # settle: the panel animates\n".splitlines()
    assert [f["rule"] for f in cc.check_no_oracle_tests("tests/ui/test_x.py", lines)] == ["no-oracle-test"]


@pytest.mark.parametrize("signature", [
    'def test_color(page, color="#fff"):',
    "def test_label(page, label='('):",
    'def test_both(page, a="#x", b="]"):',
])
def test_a_default_holding_a_bracket_or_a_hash_does_not_empty_the_body(signature):
    """A string default must not cut the signature short: the body was unread, so a real oracle went missing."""
    lines = [signature, "    assert page.title()"]
    assert cc.check_no_oracle_tests("tests/ui/test_x.py", lines) == []
    early = cc.check_early_exit_tests("tests/ui/test_x.py", [signature, "    return", "    assert 1"])
    assert [f["text"] for f in early] == ["return"]


def test_a_constant_that_mentions_a_fixture_does_not_exempt_a_test():
    """_is_fixture reads the decorators above a def, not any line that holds the word."""
    lines = ['USE = "pytest.fixture"', "def test_x(page):", "    print(1)"]
    assert [f["rule"] for f in cc.check_no_oracle_tests("tests/ui/test_x.py", lines)] == ["no-oracle-test"]
    fixture = ["@pytest.fixture", "def test_site():", '    return "Newtown"']
    assert cc.check_no_oracle_tests("tests/ui/test_x.py", fixture) == []
