"""Pins for tools/qatouch_cases_from_tests.py.

The generator reads a case out of a test's docstring and never out of
its body. These pin the docstring parse, the module name, the CSV
shape (every column of tools/qa_touch_import_test.csv, Reference is the
node id), the parametrize id derivation, and the after-import matcher.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import (  # noqa: E402
    qatouch_cases_from_tests as gen,
    qatouch_csv_import as imp,
)

DOC_WITH_STEPS = '''Verify the star adds the camera to Favorites.

Some prose the reader keeps.

Steps:
1. Open Views and expand the test site.
   Expected: The camera list shows.
2. Click the star on the test camera
   and wait for the fill.
   Expected: The star fills and the camera
   appears in the Favorites panel.
3. Click the star again.
'''

SYNTHETIC_FILE = '''"""Synthetic file."""
import pytest

IDS = [f"{a}_{b}" for a, b in [("Line", "Person"), ("Bar", "Event")]]
PAIRS = [("Line", "Person"), ("Bar", "Event")]


class TestThing:
    def test_titled(self):
        """Verify the thing.

        Steps:
        1. Do the thing.
           Expected: The thing is done.
        """

    def test_no_steps(self):
        """Verify the other thing."""

    @pytest.mark.parametrize("graph,cat", PAIRS, ids=IDS)
    def test_params(self, graph, cat):
        """Verify a widget per graph and category.

        Steps:
        1. Create the widget. Repeat for each graph and category.
           Expected: The widget is listed.
        """

    @pytest.mark.parametrize("path,name", [("/search", "Search"), ("/events", "Events")])
    def test_tuple_params(self, path, name):
        """Verify logout from each page.

        Steps:
        1. Sign out.
           Expected: The login page opens.
        """

    @pytest.mark.skip(reason="held")
    def test_held(self):
        """Verify a held thing.

        Steps:
        1. Wait.
           Expected: Nothing.
        """


def test_plain():
    """Verify a plain function test.

    Steps:
    1. Look.
       Expected: See.
    """
'''


# ---------------------------------------------------------------- docstring

def test_parse_docstring_title_steps_expected():
    """Title is the first line, steps are the numbered lines, Expected and
    continuation lines attach to the step above them."""
    parsed = gen.parse_docstring(DOC_WITH_STEPS, 'tests/ui/views/test_v.py::TestV::test_star')
    assert parsed.ok
    assert parsed.title == 'Verify the star adds the camera to Favorites'
    assert [s.text for s in parsed.steps] == [
        'Open Views and expand the test site.',
        'Click the star on the test camera and wait for the fill.',
        'Click the star again.',
    ]
    assert parsed.steps[0].expected == 'The camera list shows.'
    assert parsed.steps[1].expected == 'The star fills and the camera appears in the Favorites panel.'
    assert parsed.steps[2].expected == ''


@pytest.mark.parametrize(('doc', 'problem'), [
    ('Verify a thing.\n\nJust prose.', 'no Steps: block'),
    ('Verify a thing.\n\nSteps:\nnothing numbered', 'Steps: block has no numbered line'),
    ('Verify a thing.\n\nSteps:\n1. Do it.\n2. Do it again.', 'no Expected: line'),
    ('', 'no Steps: block'),
])
def test_parse_docstring_names_the_gap(doc, problem):
    """A docstring the generator cannot use says why, and yields no steps to import."""
    parsed = gen.parse_docstring(doc, 'tests/ui/x/test_x.py::test_thing')
    assert not parsed.ok
    assert parsed.problem == problem


def test_title_falls_back_to_function_name():
    """No docstring: the title is the function name as words, like the run report."""
    parsed = gen.parse_docstring('', 'tests/ui/x/test_x.py::TestX::test_drag_camera_to_tile')
    assert parsed.title == 'Drag camera to tile'


# ---------------------------------------------------------------- module name

@pytest.mark.parametrize(('nodeid', 'classes', 'module'), [
    ('tests/ui/insights/test_insights_navigation.py::TestInsightsNavigation::test_x', 1,
     'Insights > Navigation'),
    ('tests/ui/admin/test_lpr_navigation.py::TestLprNavigation::test_x', 1,
     'Admin > LPR Navigation'),
    ('tests/ui/admin/test_lpr_operations.py::TestLprListOperations::test_x', 2,
     'Admin > LPR Operations > List Operations'),
    ('tests/ui/admin/test_lpr_grid_and_timer.py::TestLprTimer::test_x', 2,
     'Admin > LPR Grid and Timer > Timer'),
    ('tests/ui/admin/test_lpr_grid_and_timer.py::TestLprGridLayout::test_x', 2,
     'Admin > LPR Grid and Timer > Grid Layout'),
    ('tests/ui/login/test_logout.py::test_x', 1, 'Login > Logout'),
    ('tests/ui/maps/test_maps.py::TestMaps::test_x', 1, 'Maps'),
])
def test_module_name_from_folder_file_and_class(nodeid, classes, module):
    """Module path from the folder and the file stem; the class is a third
    level only when the file holds more than one Test class."""
    assert gen.module_name(nodeid, classes) == module


# ---------------------------------------------------------------- scan + rows

@pytest.fixture
def synthetic(tmp_path):
    """A tests/ui/thing/test_thing.py under a fake repo root."""
    path = tmp_path / 'tests' / 'ui' / 'thing' / 'test_thing.py'
    path.parent.mkdir(parents=True)
    path.write_text(SYNTHETIC_FILE, encoding='utf-8')
    return tmp_path, path


def test_scan_reads_skip_and_param_ids(synthetic):
    """The scan finds every test, its skip mark, and its parametrize ids."""
    root, path = synthetic
    found = gen.scan_file(path, root)
    base = 'tests/ui/thing/test_thing.py'
    assert set(found) == {
        f'{base}::TestThing::test_titled', f'{base}::TestThing::test_no_steps',
        f'{base}::TestThing::test_params', f'{base}::TestThing::test_tuple_params',
        f'{base}::TestThing::test_held', f'{base}::test_plain',
    }
    assert found[f'{base}::TestThing::test_held'].skipped
    assert not found[f'{base}::TestThing::test_titled'].skipped
    # ids= computed by a comprehension over module literals
    assert found[f'{base}::TestThing::test_params'].param_ids == ['Line_Person', 'Bar_Event']
    # no ids=: pytest joins tuple values with '-'
    assert found[f'{base}::TestThing::test_tuple_params'].param_ids == [
        '/search-Search', '/events-Events']
    assert not found[f'{base}::test_plain'].parametrized


def test_row_has_every_column_and_reference_is_nodeid(synthetic):
    """A row carries every column of the sample CSV, in order, with the
    node id in Reference."""
    root, path = synthetic
    info = gen.scan_file(path, root)['tests/ui/thing/test_thing.py::TestThing::test_params']
    row = gen.build_row(info, gen.parse_docstring(info.docstring, info.nodeid), '2026-08-25')
    assert list(row) == gen.COLUMNS

    # Cross-check against the real QA Touch import file when a working copy
    # has one. tools/*.csv is gitignored, so it is in no clean checkout and
    # this assertion cannot run in CI. Reading it unconditionally made this
    # test pass on a developer machine and raise FileNotFoundError on every
    # CI run - the shape of failure that gets a whole gate switched off.
    sample = REPO_ROOT / 'tools' / 'qa_touch_import_test.csv'
    if not sample.exists():
        pytest.skip('tools/qa_touch_import_test.csv is gitignored and absent; '
                    'gen.COLUMNS is still checked above')
    header = sample.read_text(encoding='utf-8-sig').splitlines()[0].split(',')
    assert list(row) == header
    assert row['Reference'] == 'tests/ui/thing/test_thing.py::TestThing::test_params'
    assert row['Test Case Title'] == 'Verify a widget per graph and category'
    assert row['Module_name'] == 'Thing'
    assert row['Steps'] == 'Step 1: Create the widget. Repeat for each graph and category.'
    assert row['Expected_result'] == 'The widget is listed.'
    assert row['Test Data'] == 'Line_Person, Bar_Event'
    assert row['Tags'] == 'automated;playwright;thing'
    assert row['Type'] == 'Regression'
    assert row['Priority'] == 'Medium'
    assert row['Mode'] == 'Automation'
    assert row['Description'] == (
        'Generated from tests/ui/thing/test_thing.py::TestThing::test_params on 2026-08-25')
    assert row['Precondition'].startswith('Logged in as an Admin user')


def test_row_pads_expected_and_tags_skipped(synthetic):
    """Expected_result holds one line per step, "-" where a step has none,
    and a skipped test carries the skipped-in-suite tag."""
    root, path = synthetic
    found = gen.scan_file(path, root)
    held = found['tests/ui/thing/test_thing.py::TestThing::test_held']
    row = gen.build_row(held, gen.parse_docstring(held.docstring, held.nodeid), '2026-08-25')
    assert row['Tags'] == 'automated;playwright;thing;skipped-in-suite'
    assert row['Test Data'] == 'N/A'
    parsed = gen.parse_docstring(DOC_WITH_STEPS, 'tests/ui/views/test_v.py::TestV::test_star')
    row = gen.build_row(found['tests/ui/thing/test_thing.py::test_plain'], parsed, '2026-08-25')
    # one line per step; "-" where a step has no expected result
    assert row['Expected_result'].split('\n') == [
        'The camera list shows.',
        'The star fills and the camera appears in the Favorites panel.',
        '-',
    ]
    assert row['Steps'].count('\n') == 2


def test_csv_round_trips_through_the_importer(synthetic, tmp_path):
    """The written CSV is what qatouch_csv_import.py maps to the endpoint's
    columns: title, steps and reference all land."""
    root, path = synthetic
    found = gen.scan_file(path, root)
    info = found['tests/ui/thing/test_thing.py::TestThing::test_titled']
    row = gen.build_row(info, gen.parse_docstring(info.docstring, info.nodeid), '2026-08-25')
    out = tmp_path / 'cases.csv'
    gen.write_csv([row], out)
    with open(out, encoding='utf-8', newline='') as f:
        assert csv.DictReader(f).fieldnames == gen.COLUMNS
    result = imp.preview(out)
    assert result['cases'] == 1
    assert result['warnings'] == []
    assert result['empty_titles'] == 0
    first = result['first']
    assert first['title'] == first['test_case_title'] == 'Verify the thing'
    assert first['module_name'] == 'Thing'
    assert first['reference'] == info.nodeid
    assert first['steps'] == 'Step 1: Do the thing.'
    assert first['expected_result'] == 'The thing is done.'
    assert first['tags'] == 'automated;playwright;thing'


def test_generate_lists_needs_steps_and_writes_both_files(synthetic, tmp_path, monkeypatch):
    """--unmapped writes the CSV and the preview, and lists the test with no
    Steps block under Needs steps instead of inventing one."""
    root, _path = synthetic
    monkeypatch.setattr(gen, 'ROOT', root)
    monkeypatch.setattr(gen, 'TESTS_ROOTS', [root / 'tests' / 'ui'])
    monkeypatch.setattr(gen, 'LOGS_DIR', tmp_path / 'logs')
    mapping = tmp_path / 'mapping.json'
    mapping.write_text(json.dumps({'version': 1, 'mappings': {}}), encoding='utf-8')
    monkeypatch.setattr(gen, 'collect_tests', lambda _root=None: {
        n: {'nodeid': n} for n in gen.scan_tests(root / 'tests' / 'ui', root)})
    rc = gen.main(['--unmapped', '--mapping', str(mapping)])
    assert rc == 0
    csvs = list((tmp_path / 'logs').glob('qatouch_new_cases_*.csv'))
    mds = list((tmp_path / 'logs').glob('qatouch_new_cases_*.md'))
    assert len(csvs) == 1
    assert len(mds) == 1
    with open(csvs[0], encoding='utf-8', newline='') as f:
        refs = [r['Reference'] for r in csv.DictReader(f)]
    # every titled test gets a row; the one without a Steps block does not
    assert 'tests/ui/thing/test_thing.py::TestThing::test_no_steps' not in refs
    assert len(refs) == 5
    md = mds[0].read_text(encoding='utf-8')
    assert 'Needs steps' in md
    assert 'test_no_steps: no Steps: block' in md


# ---------------------------------------------------------------- after import

def _case(key, ref, title='T', module='M'):
    return {'case_key': key, 'case_title': title, 'module_name': module, 'References': ref}


def test_match_cases_on_reference():
    """Rows match cases on Reference; missing and duplicated references are reported."""
    rows = [{'Reference': 'tests/a.py::TestA::test_one'},
            {'Reference': 'tests/a.py::TestA::test_two'},
            {'Reference': 'tests/a.py::TestA::test_dup'}]
    cases = [_case('K1', 'tests/a.py::TestA::test_one'),
             _case('K3', 'tests/a.py::TestA::test_dup'),
             _case('K4', 'tests/a.py::TestA::test_dup'),
             _case('K9', 'unrelated'),
             {'case_key': 'K0', 'case_title': 'no ref'}]
    matched, missing, ambiguous = gen.match_cases(rows, cases)
    assert matched == {'tests/a.py::TestA::test_one': cases[0]}
    assert missing == ['tests/a.py::TestA::test_two']
    assert ambiguous == {'tests/a.py::TestA::test_dup': ['K3', 'K4']}


def test_case_reference_reads_any_spelling():
    """The reference field is read under every name the API has used."""
    assert gen.case_reference({'References': ' x '}) == 'x'
    assert gen.case_reference({'reference': 'y'}) == 'y'
    assert gen.case_reference({'refLink': 'z'}) == 'z'
    assert gen.case_reference({}) == ''


def test_mapping_rows_carry_browser_and_param_ids(synthetic):
    """Mapping rows are keyed the way the file stores them: [chromium], or
    [chromium-<id>] per parameter id."""
    root, path = synthetic
    found = gen.scan_file(path, root)
    case = _case('K1', 'ref', title='Verify a widget', module='Thing')
    plain = gen.mapping_rows('tests/ui/thing/test_thing.py::TestThing::test_titled', case,
                             found['tests/ui/thing/test_thing.py::TestThing::test_titled'])
    assert list(plain) == ['tests/ui/thing/test_thing.py::TestThing::test_titled[chromium]']
    entry = plain['tests/ui/thing/test_thing.py::TestThing::test_titled[chromium]']
    assert entry == {'case_key': 'K1', 'case_title': 'Verify a widget', 'score': 1.0,
                     'module': 'Thing', 'auto_matched': False, 'reviewed': True,
                     'source': 'generated'}
    params = gen.mapping_rows('tests/ui/thing/test_thing.py::TestThing::test_params', case,
                              found['tests/ui/thing/test_thing.py::TestThing::test_params'])
    assert list(params) == [
        'tests/ui/thing/test_thing.py::TestThing::test_params[chromium-Line_Person]',
        'tests/ui/thing/test_thing.py::TestThing::test_params[chromium-Bar_Event]',
    ]
    # no test info (deleted since the CSV): the bare [chromium] row
    assert list(gen.mapping_rows('tests/x.py::test_gone', case, None)) == [
        'tests/x.py::test_gone[chromium]']


def test_after_import_writes_mapping_from_fake_case_list(synthetic, tmp_path, monkeypatch):
    """End to end with a fake case list: rows land reviewed, generated, and
    an old dead-key row of the same function is replaced."""
    root, path = synthetic
    monkeypatch.setattr(gen, 'ROOT', root)
    monkeypatch.setattr(gen, 'TESTS_ROOTS', [root / 'tests' / 'ui'])
    base = 'tests/ui/thing/test_thing.py::TestThing::test_titled'
    found = gen.scan_file(path, root)
    row = gen.build_row(found[base], gen.parse_docstring(found[base].docstring, base),
                        '2026-08-25')
    csv_path = tmp_path / 'cases.csv'
    gen.write_csv([row], csv_path)
    cases_path = tmp_path / 'cases.json'
    cases_path.write_text(json.dumps({'cases': [
        _case('NEW1', base, title='Verify the thing', module='Thing'),
    ]}), encoding='utf-8')
    mapping = tmp_path / 'mapping.json'
    mapping.write_text(json.dumps({'version': 1, 'mappings': {
        f'{base}[chromium]': {'case_key': 'DEAD', 'reviewed': True},
        'tests/ui/other.py::test_keep[chromium]': {'case_key': 'KEEP', 'reviewed': True},
    }}), encoding='utf-8')
    rc = gen.main(['--after-import', str(csv_path), '--cases', str(cases_path),
                   '--mapping', str(mapping)])
    assert rc == 0
    data = json.loads(mapping.read_text(encoding='utf-8'))
    assert data['mappings'][f'{base}[chromium]'] == {
        'case_key': 'NEW1', 'case_title': 'Verify the thing', 'score': 1.0,
        'module': 'Thing', 'auto_matched': False, 'reviewed': True, 'source': 'generated'}
    assert 'tests/ui/other.py::test_keep[chromium]' in data['mappings']
    assert data['total_mapped'] == 2


def test_after_import_dry_run_saves_nothing(synthetic, tmp_path, monkeypatch, capsys):
    """--dry-run reports the match result and leaves the mapping file as it was."""
    root, path = synthetic
    monkeypatch.setattr(gen, 'ROOT', root)
    monkeypatch.setattr(gen, 'TESTS_ROOTS', [root / 'tests' / 'ui'])
    base = 'tests/ui/thing/test_thing.py::TestThing::test_titled'
    found = gen.scan_file(path, root)
    row = gen.build_row(found[base], gen.parse_docstring(found[base].docstring, base),
                        '2026-08-25')
    csv_path = tmp_path / 'cases.csv'
    gen.write_csv([row], csv_path)
    cases_path = tmp_path / 'cases.json'
    cases_path.write_text(json.dumps({'cases': []}), encoding='utf-8')
    mapping = tmp_path / 'mapping.json'
    original = json.dumps({'version': 1, 'mappings': {}})
    mapping.write_text(original, encoding='utf-8')
    rc = gen.main(['--after-import', str(csv_path), '--cases', str(cases_path),
                   '--mapping', str(mapping), '--dry-run'])
    assert rc == 1   # the reference matched nothing
    assert mapping.read_text(encoding='utf-8') == original
    assert 'No case carries' in capsys.readouterr().out



# ------------------------------------------------------------ shared keys

def test_rank_claimants_puts_the_matching_title_first():
    """The claimant whose title reads like the case's is the proposed owner."""
    ranked = gen.rank_claimants(
        "Verify online cameras are detected on map",
        [("t::a", "Verify clicking an online camera icon plays its stream", True),
         ("t::b", "Verify there are online (green) cameras on the map", False)],
    )
    assert [r["nodeid"] for r in ranked] == ["t::b", "t::a"]
    assert ranked[0]["score"] > ranked[1]["score"]
    assert ranked[1]["has_steps"] is True


def test_rank_claimants_ties_break_on_nodeid():
    """Equal scores come back in a stable order, so runs are comparable."""
    ranked = gen.rank_claimants("x", [("t::b", "y", False), ("t::a", "y", False)])
    assert [r["nodeid"] for r in ranked] == ["t::a", "t::b"]


def test_shared_keys_worklist_reports_only_keys_with_two_claimants():
    """One test per key is fine; two or more is the worklist, ranked."""
    mapping = {
        "tests/ui/x/test_x.py::TestX::test_one[chromium]": {"case_key": "K1"},
        "tests/ui/x/test_x.py::TestX::test_two[chromium]": {"case_key": "K1"},
        "tests/ui/x/test_x.py::TestX::test_alone[chromium]": {"case_key": "K2"},
    }
    cases = {"K1": {"case_key": "K1", "case_title": "Verify two things happen",
                    "module_name": "X"}}
    tests = {}
    rows = gen.shared_keys_worklist(mapping, cases, tests)
    assert [r["key"] for r in rows] == ["K1"]
    assert {rows[0]["owner"]["nodeid"], *(o["nodeid"] for o in rows[0]["others"])} == {
        "tests/ui/x/test_x.py::TestX::test_one",
        "tests/ui/x/test_x.py::TestX::test_two",
    }
    assert rows[0]["owner_weak"] is True  # no test found, no title to match



def test_weak_mappings_lists_a_test_whose_title_is_not_its_case():
    """A single-claimant mapping whose case title shares nothing with the test
    is listed for review; the score orders the list, a person decides."""
    mapping = {
        "tests/ui/x/test_x.py::TestX::test_navigate_to_media[chromium]": {"case_key": "K1"},
        "tests/ui/x/test_x.py::TestX::test_audio_option[chromium]": {"case_key": "K2"},
    }
    cases = {
        "K1": {"case_key": "K1", "case_title": "Verify the LPR plate list exports to CSV", "module_name": "LPR"},
        "K2": {"case_key": "K2", "case_title": "Verify the Audio option is offered", "module_name": "Settings"},
    }
    tests = {
        "tests/ui/x/test_x.py::TestX::test_navigate_to_media": gen.TestInfo(
            nodeid="tests/ui/x/test_x.py::TestX::test_navigate_to_media", file="tests/ui/x/test_x.py",
            area="x", class_name="TestX", func_name="test_navigate_to_media",
            docstring="Verify navigation to the Media page via the sidebar.", skipped=False,
            param_ids=None, parametrized=False),
        "tests/ui/x/test_x.py::TestX::test_audio_option": gen.TestInfo(
            nodeid="tests/ui/x/test_x.py::TestX::test_audio_option", file="tests/ui/x/test_x.py",
            area="x", class_name="TestX", func_name="test_audio_option",
            docstring="Verify the Audio option is offered.", skipped=False,
            param_ids=None, parametrized=False),
    }
    rows = gen.weak_mappings(mapping, cases, tests)
    assert [r["nodeid"].split("::")[-1] for r in rows] == ["test_navigate_to_media"]
    assert rows[0]["key"] == "K1"


def test_c2c_stays_one_acronym_in_class_names():
    """'C2C' is one word: the camera suite's classes start with it, and the
    CamelCase split alone read TestC2CVCA as 'C2 Cvca' (09/11/2026)."""
    assert gen._words('C2CAdditionalSettings') == ['C2C', 'Additional', 'Settings']
    assert gen._words('C2CVCA') == ['C2C', 'VCA']
    assert gen._words('C2COSD') == ['C2C', 'OSD']
    nodeid = 'tests/c2c/test_c2c_camera.py::TestC2CAdditionalSettings::test_corridor_mode_options'
    assert gen.module_name(nodeid, classes_in_file=4) == 'C2C > Camera > Additional Settings'


def test_after_import_for_another_project_adds_the_key_beside_the_home_rows(synthetic, tmp_path, monkeypatch):
    """--project P0BK on a Core test with home rows: the Neurosen key lands under
    case_keys on those rows; nothing is deleted and the Core key stays."""
    root, path = synthetic
    monkeypatch.setattr(gen, 'ROOT', root)
    monkeypatch.setattr(gen, 'TESTS_ROOTS', [root / 'tests' / 'ui'])
    base = 'tests/ui/thing/test_thing.py::TestThing::test_titled'
    found = gen.scan_file(path, root)
    row = gen.build_row(found[base], gen.parse_docstring(found[base].docstring, base), '2026-09-11')
    csv_path = tmp_path / 'cases.csv'
    gen.write_csv([row], csv_path)
    cases_path = tmp_path / 'cases.json'
    cases_path.write_text(json.dumps({'cases': [_case('NEURO1', base, title='Verify the thing', module='Thing')]}),
                          encoding='utf-8')
    mapping = tmp_path / 'mapping.json'
    mapping.write_text(json.dumps({'version': 1, 'mappings': {
        f'{base}[chromium]': {'case_key': 'CORE1', 'reviewed': True},
    }}), encoding='utf-8')
    rc = gen.main(['--after-import', str(csv_path), '--cases', str(cases_path),
                   '--mapping', str(mapping), '--project', 'P0BK'])
    assert rc == 0
    rows = json.loads(mapping.read_text(encoding='utf-8'))['mappings']
    assert rows[f'{base}[chromium]'] == {'case_key': 'CORE1', 'reviewed': True, 'case_keys': {'P0BK': 'NEURO1'}}


def test_mapping_rows_for_a_foreign_project_file_the_key_under_case_keys(synthetic):
    """A foreign project's key goes under case_keys; the home project's stays plain."""
    root, path = synthetic
    base = 'tests/ui/thing/test_thing.py::TestThing::test_titled'
    info = gen.scan_file(path, root)[base]
    rows = gen.mapping_rows(base, {'case_key': 'NEURO1', 'case_title': 'T', 'module_name': 'Thing'}, info,
                            project='P0BK')
    entry = rows[f'{base}[chromium]']
    assert (entry['case_key'], entry['case_keys']) == ('', {'P0BK': 'NEURO1'})
    home = gen.mapping_rows(base, {'case_key': 'CORE1', 'case_title': 'T', 'module_name': 'Thing'}, info,
                            project='JlW1')[f'{base}[chromium]']
    assert home['case_key'] == 'CORE1'
    assert 'case_keys' not in home
