"""Per-run HTML report -- builder and CLI.

Turns one archived run folder (see run_archive) into run.html: a page that
puts every piece of the run's evidence one click away, failures first.

    python -m plugins.run_report latest
    python -m plugins.run_report reports/runs/<start>__<target>

What the page shows, in order:
  - Header: target, start time, duration, outcome counts, exit status,
    provenance (ENV, host, git commit, browser, Playwright versions), and
    links to the pytest-html report, the archive index, and the run that
    the change chips compare against.
  - A filter box: type part of a title, node id, case key, module, or
    outcome and only the matching tests stay visible.
  - Failures: one card per failed or errored test with the error message,
    the failing Playwright action and its call log, the actions that led
    up to it, console errors, every screenshot of the test (final plus
    mid-drag frames, click for full size), the video clip when one was
    kept, and the exact show-trace command for the trace zip.
  - Advisories: the [VIEWS] / [LPR] / [EXPORT] lines from summary.json.
  - Slowest 5: the longest tests of the run.
  - Passed and Skipped: collapsed lists grouped by module, each test with
    its thumbnails and its advisory lines.

Every test shows its readable title first (the docstring's first line, or
the function name as words), the QA Touch case title beneath it when the
test is mapped, and the node id smaller under both. The node id stays the
join key for the QA Touch mapping and the archive history, so the page
never renames a test. Each test also carries its duration, a link to its
captured output under log/, and a change chip against the previous run of
the same target: new failure, fixed, still failing, or new test.

Where the facts come from, most reliable first:
  1. summary.json "tests" - run_archive's own per-test record: title,
     module, QA Touch case, outcome, per-phase timing, log file.
  2. report.html - pytest-html embeds every test's outcome, duration, and
     captured log (the traceback) as JSON in a data-jsonblob attribute.
  3. last_run_results.json - qatouch_reporter's per-nodeid outcomes. Only
     present when that reporter ran (--qatouch-upload), so never assumed.
  4. The file names themselves - a __FAILED screenshot or a -trace.zip
     names its test even when neither file above exists.
  Files attach to tests through the same sanitizer report_media and
  conftest use to name them. Names that run_archive shortened to fit the
  path cap (<head>-<8-hex-digest>-<tail>) still match: the digest is
  recomputed from the expected name, with a longest-common-prefix
  fallback for names cut by an older layout.

Stdlib only, no browser, and read-only on the run folder except for the
run.html it writes. Every input is optional: a missing file or key
renders as '-' or an empty section, never as an error.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from html import escape
from pathlib import Path
from urllib.parse import quote

# Same sanitizer and caps as report_media._safe_name (screenshots) and
# conftest._trace_path (traces, videos): the archive names are those
# files' names, so matching must reproduce them exactly.
SAFE_NAME_MAX = 120
TRACE_NAME_MAX = 150

# Run folders are named <session-start>__<slug>. Defined here, not in
# run_archive, because that module imports this one and the previous-run
# lookup below needs the pattern too.
RUN_DIR_RE = re.compile(r'^\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}__')

# How many actions before the failing one the failure card lists.
LAST_ACTIONS = 15

# How many of the run's longest tests the "Slowest" block lists.
SLOWEST_COUNT = 5

# Change chips against the previous run of the same target.
DELTA_NEW_FAILURE = 'new failure'
DELTA_FIXED = 'fixed'
DELTA_STILL_FAILING = 'still failing'
DELTA_NEW_TEST = 'new test'

# Error lines pytest prefixes with 'E ' in a longrepr; the first block of
# them is the headline a reader wants before the full traceback.
_ERROR_LINE_RE = re.compile(r'^E {1,3}(.*)$')
_HEADLINE_MAX = 30

_SCREENSHOT_RE = re.compile(
    r'^(?P<test>.*?)__(?P<suffix>PASSED|FAILED|SETUP_FAILED|SKIPPED)'
    r'(?:__(?P<label>.+)-(?P<index>\d+))?$')
_ARTIFACT_RE = re.compile(r'^(?P<test>.*?)-(?P<kind>login-failure-trace|trace|video)$')
_DIGEST_RE = re.compile(r'-([0-9a-f]{8})-')

# report.html (pytest-html) and last_run_results.json (qatouch_reporter)
# each spell outcomes their own way; the page uses one vocabulary.
_HTML_OUTCOMES = {
    'passed': 'passed', 'failed': 'failed', 'error': 'error',
    'skipped': 'skipped', 'xfailed': 'xfailed', 'xpassed': 'xpassed',
}
_SUFFIX_OUTCOMES = {'PASSED': 'passed', 'FAILED': 'failed',
                    'SETUP_FAILED': 'error', 'SKIPPED': 'skipped'}
# Worse outcomes win when two sources disagree about one test.
_OUTCOME_RANK = {'error': 5, 'failed': 4, 'xfailed': 3, 'skipped': 2,
                 'xpassed': 1, 'passed': 0}
FAILURE_OUTCOMES = ('failed', 'error')
PASSED_OUTCOMES = ('passed', 'xpassed')
SKIPPED_OUTCOMES = ('skipped', 'xfailed')


@dataclass
class TestRecord:
    """Everything the page knows about one test."""

    nodeid: str
    outcome: str = 'unknown'
    duration: str = ''
    log: str = ''
    screenshots: list[str] = field(default_factory=list)
    frames: list[str] = field(default_factory=list)
    traces: list[str] = field(default_factory=list)
    videos: list[str] = field(default_factory=list)
    advisories: list[str] = field(default_factory=list)
    # From summary.json "tests" (run_archive); empty on older archives.
    title: str = ''
    module: str = ''
    case_key: str = ''
    case_title: str = ''
    log_file: str = ''
    seconds: float | None = None
    delta: str = ''

    @property
    def safe(self) -> str:
        return _safe_name(self.nodeid, SAFE_NAME_MAX)

    @property
    def safe_trace(self) -> str:
        return _safe_name(self.nodeid, TRACE_NAME_MAX)

    @property
    def display_title(self) -> str:
        return self.title or readable_title(self.nodeid)

    @property
    def module_name(self) -> str:
        return self.module or module_of(self.nodeid)

    @property
    def duration_text(self) -> str:
        """Seconds from the archive when known, else pytest-html's text."""
        return format_seconds(self.seconds) if self.seconds is not None else self.duration


# ---------------------------------------------------------------- names

def _safe_name(nodeid: str, cap: int) -> str:
    """The filesystem stem the plugins derive from a node id."""
    return re.sub(r'[^\w.-]+', '-', nodeid).strip('-')[:cap]


def readable_title(nodeid: str, doc: str | None = None) -> str:
    """The title a reader sees for a test.

    The first non-empty line of the docstring when there is one, else the
    function name as words: test_drag_camera_to_tile[chromium] reads
    "Drag camera to tile". Display only - the node id stays the key.
    """
    for line in (doc or '').splitlines():
        text = line.strip()
        if text:
            return text
    name = nodeid.rsplit('::', 1)[-1]
    name = re.sub(r'\[.*\]$', '', name)
    name = re.sub(r'^test_?', '', name)
    words = name.replace('_', ' ').strip()
    return (words[:1].upper() + words[1:]) if words else nodeid


def module_of(nodeid: str) -> str:
    """The test file's path under tests/ - the grouping key of the page and
    the health summary. A path outside tests/ is kept whole."""
    path = nodeid.split('::', 1)[0].replace('\\', '/')
    return path[len('tests/'):] if path.startswith('tests/') else path


def format_seconds(seconds: float) -> str:
    """12.3 s under a minute, else 1 min 41 s."""
    if seconds < 60:
        return f'{seconds:.1f} s'
    minutes, rest = divmod(seconds, 60)
    return f'{int(minutes)} min {rest:.0f} s'


def _loose(text: str) -> str:
    """Case- and punctuation-insensitive form for the last-resort match.

    pytest-playwright names its per-test folders with python-slugify
    (lowercase, underscores to hyphens), so an exact comparison with the
    repo's sanitizer never fits; this form makes both spellings equal.
    """
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def _digest(stem: str) -> str:
    """The 8-char digest run_archive._fit_dest puts into a shortened name."""
    return hashlib.sha256(stem.encode('utf-8')).hexdigest()[:8]


def parse_screenshot_name(stem: str) -> dict | None:
    """Split a screenshot stem into its test part, suffix, and frame index.

    <safe>__PASSED, <safe>__FAILED__mid-drag-2, <safe>__SKIPPED__mid-drag-1.
    None when the stem carries no label - not one of report_media's files.
    """
    m = _SCREENSHOT_RE.match(stem)
    if not m:
        return None
    return {'test': m.group('test'), 'suffix': m.group('suffix'),
            'label': m.group('label'), 'index': m.group('index')}


def parse_artifact_name(relpath: str) -> dict | None:
    """Split a path under traces/ into its test part and kind.

    Flat conftest files: <safe>-trace.zip, <safe>-video.webm,
    <safe>-login-failure-trace.zip. pytest-playwright's per-test folders
    hold trace.zip / video.webm / *.png under a folder named for the test,
    so there the folder is the test part.
    """
    path = Path(relpath)
    ext = path.suffix.lower()
    if ext not in ('.zip', '.webm', '.png'):
        return None
    if len(path.parts) > 1:
        kind = {'.zip': 'trace', '.webm': 'video', '.png': 'screenshot'}[ext]
        return {'test': path.parts[0], 'kind': kind, 'nested': True}
    m = _ARTIFACT_RE.match(path.stem)
    if not m:
        return None
    return {'test': m.group('test'), 'kind': m.group('kind'), 'nested': False}


def match_test(test_part: str, safes: dict[str, str],
               full_stem: Callable[[str], str] | None = None) -> str | None:
    """Find which test an archived file's test part names.

    `safes` maps each known test's sanitized stem to its node id.
    `full_stem` rebuilds the file's original stem from a sanitized stem
    (for a final screenshot: safe + '__FAILED'), which is what the digest
    of a shortened name was computed from.

    Tiers, first hit wins:
      1. Exact stem.
      2. Shortened name whose digest recomputes from a known test's full
         stem - the only tier that tells parametrized twins apart.
      3. Shortened name whose head and tail both sit inside exactly one
         known stem (a digest from an older layout).
      4. Longest common prefix that covers the whole test part (or its
         head), then the same on the loose forms for slugified names.
    None when nothing matches: the file is listed as unattached.
    """
    if test_part in safes:
        return safes[test_part]
    splits = [(test_part[:m.start()], m.group(1), test_part[m.end():])
              for m in _DIGEST_RE.finditer(test_part)]
    for head, digest, tail in splits:
        for safe, nodeid in safes.items():
            if not (safe.startswith(head) and safe.endswith(tail)):
                continue
            if full_stem is not None and _digest(full_stem(safe)) == digest:
                return nodeid
    for head, _, tail in splits:
        inside = [nodeid for safe, nodeid in safes.items()
                  if safe.startswith(head) and safe.endswith(tail)]
        if len(inside) == 1:
            return inside[0]
    heads = [test_part, *[head for head, _d, _t in splits]]
    best: tuple[int, str] | None = None
    for head in heads:
        for safe, nodeid in safes.items():
            n = len(os.path.commonprefix([head, safe]))
            if n and n >= min(len(head), len(safe)) and (best is None or n > best[0]):
                best = (n, nodeid)
    if best is not None:
        return best[1]
    loose_part = _loose(test_part)
    for safe, nodeid in safes.items():
        loose_safe = _loose(safe)
        related = loose_safe.startswith(loose_part) or loose_part.startswith(loose_safe)
        if loose_part and loose_safe and related and (best is None or len(loose_safe) > best[0]):
            best = (len(loose_safe), nodeid)
    return best[1] if best else None


# ---------------------------------------------------------------- sources

def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None


def load_summary(run_dir: Path) -> dict:
    """summary.json as a dict; empty when missing or unreadable."""
    loaded = _read_json(run_dir / 'summary.json')
    return loaded if isinstance(loaded, dict) else {}


def summary_tests(summary: Mapping) -> list[dict]:
    """The per-test records of a summary.json, keyed rows only.

    Archives written before the "tests" key existed have none; the page
    then falls back to report.html and the file names as before.
    """
    rows = summary.get('tests')
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict) and r.get('nodeid')]


def find_previous_run(run_dir: Path) -> Path | None:
    """The newest earlier archive of the same target, or None.

    Same target means the same folder slug: the part after '__'. Only
    folders that sort before this run count, so rebuilding an old run's
    page compares it with its own past, not with a later run.
    """
    slug = run_dir.name.partition('__')[2]
    parent = run_dir.parent
    if not slug or not parent.is_dir():
        return None
    earlier = sorted(p for p in parent.iterdir()
                     if p.is_dir() and RUN_DIR_RE.match(p.name)
                     and p.name < run_dir.name and p.name.partition('__')[2] == slug)
    return earlier[-1] if earlier else None


def load_previous_outcomes(prev_dir: Path) -> dict[str, str]:
    """Node id -> outcome for an earlier run, from its summary "tests" when
    present, else from its report and file names (older archives)."""
    rows = summary_tests(load_summary(prev_dir))
    if rows:
        return {str(r['nodeid']): str(r.get('outcome') or 'unknown') for r in rows}
    records, _unattached = collect_tests(prev_dir)
    return {nodeid: rec.outcome for nodeid, rec in records.items()}


def compute_deltas(current: Mapping[str, str],
                   previous: Mapping[str, str] | None) -> dict[str, str]:
    """The change chip of each test since the previous run of this target.

    No previous run means no chips at all - nothing to compare with.
    A test absent from the previous run is 'new test'. Failing both
    times is 'still failing'; failing now after a pass or a skip is
    'new failure'; passing now after a failure is 'fixed'. Every other
    pair (pass then pass, skip either side) gets no chip.
    """
    if previous is None:
        return {}
    chips: dict[str, str] = {}
    for nodeid, outcome in current.items():
        failing = outcome in FAILURE_OUTCOMES
        if nodeid not in previous:
            chips[nodeid] = DELTA_NEW_TEST
            continue
        was_failing = previous[nodeid] in FAILURE_OUTCOMES
        if failing and was_failing:
            chips[nodeid] = DELTA_STILL_FAILING
        elif failing:
            chips[nodeid] = DELTA_NEW_FAILURE
        elif was_failing and outcome in PASSED_OUTCOMES:
            chips[nodeid] = DELTA_FIXED
    return chips


def load_report_results(run_dir: Path) -> dict[str, dict]:
    """Per-test outcome, duration, and log from pytest-html's JSON blob.

    pytest-html 4 writes the results table's data into a data-jsonblob
    attribute (HTML-escaped JSON; the log inside is escaped once more).
    A test id maps to a list of rows; the worst row's outcome is the
    test's, and its log is kept.
    """
    try:
        text = (run_dir / 'report.html').read_text(encoding='utf-8', errors='replace')
    except OSError:
        return {}
    m = re.search(r'data-jsonblob="([^"]*)"', text)
    if not m:
        return {}
    try:
        blob = json.loads(html.unescape(m.group(1)))
    except ValueError:
        return {}
    tests = blob.get('tests') if isinstance(blob, dict) else None
    if not isinstance(tests, dict):
        return {}
    out: dict[str, dict] = {}
    for nodeid, rows in tests.items():
        for row in rows if isinstance(rows, list) else []:
            if not isinstance(row, dict):
                continue
            outcome = _HTML_OUTCOMES.get(str(row.get('result', '')).lower())
            if outcome is None:
                continue  # Rerun rows are not a final verdict
            current = out.get(nodeid)
            if current is None or _OUTCOME_RANK[outcome] >= _OUTCOME_RANK[current['outcome']]:
                out[nodeid] = {'outcome': outcome,
                               'duration': str(row.get('duration', '') or ''),
                               'log': html.unescape(str(row.get('log', '') or ''))}
    return out


def load_results_json(run_dir: Path) -> dict[str, str]:
    """Per-nodeid outcomes from qatouch_reporter's last_run_results.json.

    Accepts the reporter's {'results': [{'nodeid', 'outcome'}, ...]} shape
    and a plain {nodeid: outcome} map.
    """
    loaded = _read_json(run_dir / 'last_run_results.json')
    if not isinstance(loaded, dict):
        return {}
    rows = loaded.get('results')
    pairs = []
    if isinstance(rows, list):
        pairs = [(r.get('nodeid'), r.get('outcome')) for r in rows if isinstance(r, dict)]
    else:
        pairs = [(k, v) for k, v in loaded.items() if isinstance(v, str)]
    out = {}
    for nodeid, outcome in pairs:
        if not nodeid:
            continue
        outcome = str(outcome or '').lower()
        out[str(nodeid)] = _HTML_OUTCOMES.get(outcome, 'unknown')
    return out


# ---------------------------------------------------------------- trace digest

def _error_message(node) -> str:
    """Dig the human message out of a trace error object, whatever its nesting."""
    if isinstance(node, dict):
        if isinstance(node.get('message'), str):
            return node['message']
        for key in ('error', 'value'):
            if key in node:
                found = _error_message(node[key])
                if found:
                    return found
    if isinstance(node, str):
        return node
    return ''


def _api_name(ev: dict) -> str:
    name = ev.get('apiName')
    if name:
        return str(name)
    cls, method = ev.get('class'), ev.get('method')
    return f'{cls}.{method}' if cls or method else str(ev.get('type', '?'))


def _params_text(ev: dict) -> str:
    params = ev.get('params') or {}
    bits = []
    for key in ('selector', 'url', 'text', 'value', 'key', 'expression', 'state'):
        if key in params:
            val = str(params[key]).replace('\n', ' ')
            bits.append(f'{key}={val[:120]}')
    return ' '.join(bits)


def digest_trace(zip_path: Path, last_actions: int = LAST_ACTIONS) -> dict:
    """Pull actions, errors, console errors, and the last URL from a trace.zip.

    Reads the JSON-lines *.trace files inside the zip: 'before'/'after'
    pairs are the actions (an 'after' with an error is the failure),
    'log' events are an action's call log, 'console' events carry the
    page's console, and the newest 'frame-snapshot' names the final URL.
    Returns {'actions': [{'name', 'params', 'error', 'log'}], 'errors',
    'console', 'url', 'files'}; the actions window ends at the last
    failing action, or holds the last `last_actions` when none failed.
    """
    out: dict = {'actions': [], 'errors': [], 'console': [], 'url': None, 'files': 0}
    try:
        zf = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile) as e:
        out['errors'].append(f'could not open trace: {e}')
        return out
    with zf:
        names = zf.namelist()
        out['files'] = len(names)
        calls: dict[str, dict] = {}
        order: list[str] = []
        logs: dict[str, list[str]] = {}
        for name in (n for n in names if n.endswith('.trace')):
            for raw in zf.read(name).decode('utf-8', errors='replace').splitlines():
                try:
                    ev = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(ev, dict):
                    continue
                kind = ev.get('type')
                call_id = str(ev.get('callId', ''))
                if kind == 'before':
                    calls[call_id] = {'name': _api_name(ev), 'params': _params_text(ev),
                                      'error': '', 'log': []}
                    order.append(call_id)
                elif kind == 'after':
                    msg = _error_message(ev.get('error'))
                    if call_id in calls and msg:
                        calls[call_id]['error'] = msg
                elif kind == 'log' and call_id:
                    logs.setdefault(call_id, []).append(str(ev.get('message', ''))[:200])
                elif kind == 'console':
                    if str(ev.get('messageType', '')).lower() == 'error':
                        out['console'].append(str(ev.get('text', ''))[:200])
                elif kind == 'event' and ev.get('method') == 'console':
                    params = ev.get('params') or {}
                    if str(params.get('type', '')).lower() == 'error':
                        out['console'].append(str(params.get('text', ''))[:200])
                elif kind == 'frame-snapshot':
                    snap = ev.get('snapshot') or {}
                    if snap.get('frameUrl'):
                        out['url'] = snap['frameUrl']
    failing = [cid for cid in order if calls[cid]['error']]
    if failing:
        idx = order.index(failing[-1])
        window = order[max(0, idx - last_actions):idx + 1]
    else:
        window = order[-last_actions:]
    for cid in window:
        call = dict(calls[cid])
        call['log'] = logs.get(cid, [])[-8:] if call['error'] else []
        out['actions'].append(call)
    out['errors'] = [calls[cid]['error'].splitlines()[0][:200] for cid in failing]
    return out


# ---------------------------------------------------------------- collect

def _worse(new: str, old: str) -> bool:
    return _OUTCOME_RANK.get(new, -1) > _OUTCOME_RANK.get(old, -1)


def _list_files(root: Path, patterns: tuple[str, ...]) -> list[Path]:
    if not root.is_dir():
        return []
    found = [p for pattern in patterns for p in root.rglob(pattern) if p.is_file()]
    return sorted(set(found))


def collect_tests(run_dir: Path) -> tuple[dict[str, TestRecord], list[str]]:
    """Merge every source in the run folder into one record per test.

    Returns the records keyed by node id plus the relative paths of files
    that matched no test (shown at the end of the page rather than lost).
    """
    tests: dict[str, TestRecord] = {}
    summary = load_summary(run_dir)

    for row in summary_tests(summary):
        nodeid = str(row['nodeid'])
        rec = tests.setdefault(nodeid, TestRecord(nodeid))
        rec.title = str(row.get('title') or '')
        rec.module = str(row.get('module') or '')
        rec.case_key = str(row.get('case_key') or '')
        rec.case_title = str(row.get('case_title') or '')
        rec.log_file = str(row.get('log_file') or '')
        if isinstance(row.get('duration_s'), (int, float)):
            rec.seconds = float(row['duration_s'])
        outcome = _HTML_OUTCOMES.get(str(row.get('outcome') or '').lower())
        if outcome and _worse(outcome, rec.outcome):
            rec.outcome = outcome
    for nodeid, row in load_report_results(run_dir).items():
        rec = tests.setdefault(nodeid, TestRecord(nodeid))
        rec.duration, rec.log = row['duration'], row['log']
        if _worse(row['outcome'], rec.outcome):
            rec.outcome = row['outcome']
    for nodeid, outcome in load_results_json(run_dir).items():
        rec = tests.setdefault(nodeid, TestRecord(nodeid))
        if _worse(outcome, rec.outcome):
            rec.outcome = outcome
    for item in summary.get('advisories') or []:
        if not isinstance(item, dict):
            continue
        nodeid, line = str(item.get('test', '')), str(item.get('line', ''))
        if nodeid and line:
            tests.setdefault(nodeid, TestRecord(nodeid)).advisories.append(line)

    unattached: list[str] = []

    def rel(path: Path) -> str:
        return path.relative_to(run_dir).as_posix()

    def owner(test_part: str, cap: int, full_stem: Callable[[str], str] | None,
              fallback_outcome: str) -> TestRecord:
        safes = {_safe_name(t.nodeid, cap): t.nodeid for t in tests.values()}
        nodeid = match_test(test_part, safes, full_stem)
        if nodeid is None:
            # No listed test owns the file: the name is the only witness,
            # so it becomes the test's stand-in record.
            nodeid = test_part
            rec = tests.setdefault(nodeid, TestRecord(nodeid))
            if _worse(fallback_outcome, rec.outcome):
                rec.outcome = fallback_outcome
        return tests[nodeid]

    for png in _list_files(run_dir / 'screenshots', ('*.png',)):
        parsed = parse_screenshot_name(png.stem)
        if parsed is None:
            unattached.append(rel(png))
            continue
        suffix = parsed['suffix']
        frame = f"__{parsed['label']}-{parsed['index']}" if parsed['label'] else ''
        rec = owner(parsed['test'], SAFE_NAME_MAX,
                    lambda safe, s=suffix, f=frame: f'{safe}__{s}{f}',
                    _SUFFIX_OUTCOMES[suffix])
        (rec.frames if frame else rec.screenshots).append(rel(png))
        if _worse(_SUFFIX_OUTCOMES[suffix], rec.outcome):
            rec.outcome = _SUFFIX_OUTCOMES[suffix]

    traces_dir = run_dir / 'traces'
    for artifact in _list_files(traces_dir, ('*.zip', '*.webm', '*.png')):
        parsed = parse_artifact_name(artifact.relative_to(traces_dir).as_posix())
        if parsed is None:
            unattached.append(rel(artifact))
            continue
        kind = parsed['kind']
        full_stem = None if parsed['nested'] else (lambda safe, k=kind: f'{safe}-{k}')
        # A kept trace or video means the test failed; a login-failure
        # trace means its setup did.
        fallback = 'error' if kind == 'login-failure-trace' else 'failed'
        rec = owner(parsed['test'], TRACE_NAME_MAX, full_stem, fallback)
        if kind == 'video':
            rec.videos.append(rel(artifact))
        elif kind == 'screenshot':
            rec.screenshots.append(rel(artifact))
        else:
            rec.traces.append(rel(artifact))
        if kind != 'screenshot' and _worse(fallback, rec.outcome):
            rec.outcome = fallback

    return tests, unattached


# ---------------------------------------------------------------- render

PAGE_CSS = '''
:root { color-scheme: light dark;
  --bg: #fafafa; --fg: #1b1b1b; --muted: #5f6368; --card: #ffffff; --line: #d9d9d9;
  --fail: #b3261e; --fail-bg: #fdecea; --pass: #1e7d34; --pass-bg: #e8f5e9;
  --skip: #8a6d00; --skip-bg: #fff6d6; --code-bg: #f1f3f4; --link: #0b57d0; }
@media (prefers-color-scheme: dark) { :root {
  --bg: #121212; --fg: #e6e6e6; --muted: #a0a0a0; --card: #1e1e1e; --line: #3a3a3a;
  --fail: #ff8a80; --fail-bg: #3a1f1d; --pass: #81c995; --pass-bg: #1d2f22;
  --skip: #ffd54f; --skip-bg: #3a331a; --code-bg: #262626; --link: #8ab4f8; } }
* { box-sizing: border-box; }
body { margin: 0; padding: 1.5rem; background: var(--bg); color: var(--fg);
  font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }
a { color: var(--link); }
h1 { font-size: 1.5rem; margin: 0 0 .5rem; }
h2 { font-size: 1.2rem; margin: 2rem 0 .75rem; border-bottom: 1px solid var(--line); padding-bottom: .25rem; }
h3 { font-size: 1rem; margin: 0 0 .5rem; word-break: break-all; }
h4 { font-size: .9rem; margin: 1rem 0 .35rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }
.meta { color: var(--muted); display: flex; flex-wrap: wrap; gap: .4rem 1.25rem; margin-bottom: .75rem; }
.chips { display: flex; flex-wrap: wrap; gap: .5rem; margin: .5rem 0 1rem; }
.chip { border-radius: 999px; padding: .15rem .7rem; font-weight: 600; border: 1px solid var(--line); background: var(--card); }
.chip.failed, .chip.error { color: var(--fail); background: var(--fail-bg); border-color: var(--fail); }
.chip.passed { color: var(--pass); background: var(--pass-bg); border-color: var(--pass); }
.chip.skipped { color: var(--skip); background: var(--skip-bg); border-color: var(--skip); }
.card { background: var(--card); border: 1px solid var(--line); border-left: 5px solid var(--fail);
  border-radius: 6px; padding: 1rem 1.25rem; margin-bottom: 1.25rem; }
.card.error { border-left-color: var(--skip); }
pre { background: var(--code-bg); padding: .75rem; border-radius: 4px; overflow: auto;
  font: 13px/1.4 ui-monospace, Consolas, "Courier New", monospace; white-space: pre-wrap; word-break: break-word; margin: 0; }
pre.headline { color: var(--fail); font-weight: 600; }
.actions { list-style: none; margin: 0; padding: 0; font: 13px/1.5 ui-monospace, Consolas, monospace; }
.actions li { padding: .1rem 0 .1rem .5rem; border-left: 3px solid transparent; }
.actions li.failing { border-left-color: var(--fail); background: var(--fail-bg); }
.actions .err { color: var(--fail); display: block; }
.actions .log { color: var(--muted); display: block; padding-left: 1.5rem; }
.shots { display: flex; flex-wrap: wrap; gap: .75rem; }
.shots figure { margin: 0; max-width: 320px; }
.shots img { width: 100%; height: auto; border: 1px solid var(--line); border-radius: 4px; display: block; }
.shots figcaption { font-size: .8rem; color: var(--muted); word-break: break-all; }
video { max-width: 100%; width: 640px; border: 1px solid var(--line); border-radius: 4px; background: #000; }
details { margin: .5rem 0; }
summary { cursor: pointer; font-weight: 600; }
details.section > summary { font-size: 1.05rem; }
.row { padding: .5rem 0; border-bottom: 1px solid var(--line); }
.row .shots figure { max-width: 200px; }
.dur { color: var(--muted); font-size: .85rem; margin-left: .5rem; }
ul.plain { margin: .25rem 0; padding-left: 1.25rem; }
.empty { color: var(--muted); font-style: italic; }
.title { font-weight: 600; word-break: break-word; }
h3.title { margin: 0; }
.case { color: var(--muted); font-size: .9rem; }
.nodeid { color: var(--muted); font-size: .78rem; font-family: ui-monospace, Consolas, monospace; word-break: break-all; }
.facts { display: flex; flex-wrap: wrap; align-items: center; gap: .4rem .9rem; margin: .35rem 0; font-size: .85rem; color: var(--muted); }
.chip.delta { font-size: .78rem; padding: .05rem .55rem; }
.chip.new-failure, .chip.still-failing { color: var(--fail); background: var(--fail-bg); border-color: var(--fail); }
.chip.fixed { color: var(--pass); background: var(--pass-bg); border-color: var(--pass); }
.chip.new-test { color: var(--link); border-color: var(--link); }
h4.module { margin-top: 1.25rem; text-transform: none; letter-spacing: 0; font-family: ui-monospace, Consolas, monospace; }
input#filter { width: min(100%, 36rem); padding: .45rem .7rem; font: inherit; border: 1px solid var(--line); border-radius: 6px; background: var(--card); color: var(--fg); }
#filter-count { color: var(--muted); margin-left: .75rem; font-size: .9rem; }
table.facts-table { border-collapse: collapse; width: 100%; max-width: 60rem; }
table.facts-table th, table.facts-table td { text-align: left; padding: .35rem .6rem; border-bottom: 1px solid var(--line); vertical-align: top; }
table.facts-table th { color: var(--muted); font-weight: 600; font-size: .85rem; }
table.facts-table td.num { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }
'''

_FILTER_JS = '''
(function () {
  var box = document.getElementById('filter');
  var count = document.getElementById('filter-count');
  if (!box) { return; }
  var items = document.querySelectorAll('[data-test]');
  var sections = document.querySelectorAll('details.section');
  box.addEventListener('input', function () {
    var q = box.value.trim().toLowerCase();
    var shown = 0;
    for (var i = 0; i < items.length; i++) {
      var hit = !q || items[i].getAttribute('data-test').indexOf(q) !== -1;
      items[i].style.display = hit ? '' : 'none';
      if (hit) { shown++; }
    }
    // A match hidden inside a collapsed list is no match at all.
    for (var j = 0; j < sections.length && q; j++) { sections[j].open = true; }
    count.textContent = q ? shown + ' of ' + items.length + ' tests match' : '';
  });
})();
'''


def _href(rel: str) -> str:
    return quote(rel, safe='/')


def _headline(log: str) -> str:
    """The first block of pytest's 'E ' lines - the error before the traceback."""
    lines = []
    for raw in log.splitlines():
        m = _ERROR_LINE_RE.match(raw)
        if m:
            lines.append(m.group(1))
            if len(lines) >= _HEADLINE_MAX:
                break
        elif lines:
            break
    return '\n'.join(lines).strip()


def _render_shots(rec: TestRecord) -> str:
    items = [(rel, 'final') for rel in rec.screenshots] + [(rel, 'mid-drag') for rel in rec.frames]
    if not items:
        return ''
    figures = []
    for rel, kind in sorted(items, key=lambda i: (i[1] == 'final', i[0])):
        name = Path(rel).name
        figures.append(
            f'<figure><a href="{_href(rel)}" target="_blank">'
            f'<img src="{_href(rel)}" alt="{escape(name)}" loading="lazy"></a>'
            f'<figcaption>{escape(kind)}: {escape(name)}</figcaption></figure>')
    return '<div class="shots">' + ''.join(figures) + '</div>'


def _render_actions(digest: dict) -> str:
    items = []
    for action in digest.get('actions') or []:
        line = escape(f"{action.get('name', '')} {action.get('params', '')}".strip())
        cls = ' class="failing"' if action.get('error') else ''
        extra = ''
        if action.get('error'):
            extra += f'<span class="err">ERROR: {escape(str(action["error"]).splitlines()[0])}</span>'
            for log_line in action.get('log') or []:
                extra += f'<span class="log">{escape(log_line)}</span>'
        items.append(f'<li{cls}>{line}{extra}</li>')
    return '<ul class="actions">' + ''.join(items) + '</ul>' if items else ''


def _filter_key(rec: TestRecord) -> str:
    """What the filter box matches against: every name the test goes by."""
    words = (rec.display_title, rec.nodeid, rec.case_key, rec.case_title,
             rec.module_name, rec.outcome, rec.delta)
    return escape(' '.join(w for w in words if w).lower(), quote=True)


def _delta_chip(rec: TestRecord) -> str:
    if not rec.delta:
        return ''
    return (f'<span class="chip delta {escape(rec.delta.replace(" ", "-"))}">'
            f'{escape(rec.delta)}</span>')


def _render_identity(rec: TestRecord, heading: str) -> str:
    """Title first, QA Touch case second, node id smaller beneath."""
    parts = [f'<{heading} class="title">{escape(rec.display_title)}</{heading}>']
    if rec.case_key or rec.case_title:
        case = f'QA Touch {rec.case_key}'.rstrip() + (f': {rec.case_title}' if rec.case_title else '')
        parts.append(f'<div class="case">{escape(case)}</div>')
    parts.append(f'<div class="nodeid">{escape(rec.nodeid)}</div>')
    return ''.join(parts)


def _render_facts(rec: TestRecord, with_outcome: bool = False) -> str:
    facts = []
    if with_outcome:
        facts.append(f'<span class="chip {escape(rec.outcome)}">{escape(rec.outcome)}</span>')
    if rec.duration_text:
        facts.append(f'<span>{escape(rec.duration_text)}</span>')
    facts.append(_delta_chip(rec))
    facts.append(f'<span>{escape(rec.module_name)}</span>')
    if rec.log_file:
        facts.append(f'<a href="{_href(rec.log_file)}">captured output</a>')
    return '<div class="facts">' + ''.join(f for f in facts if f) + '</div>'


def _render_failure(rec: TestRecord, run_dir: Path) -> str:
    parts = [f'<div class="card {escape(rec.outcome)}" id="{escape(rec.safe, quote=True)}" '
             f'data-test="{_filter_key(rec)}">',
             _render_identity(rec, 'h3'), _render_facts(rec, with_outcome=True)]
    digest = None
    trace_zips = [rel for rel in rec.traces if rel.lower().endswith('.zip')]
    if trace_zips:
        digest = digest_trace(run_dir / trace_zips[0])

    headline = _headline(rec.log)
    if not headline and digest and digest.get('errors'):
        headline = '\n'.join(digest['errors'])
    parts.append('<h4>Error</h4>')
    if headline:
        parts.append(f'<pre class="headline">{escape(headline)}</pre>')
    else:
        parts.append('<p class="empty">No error message recorded.</p>')
    if rec.log:
        parts.append(f'<details><summary>Full traceback and captured output</summary>'
                     f'<pre>{escape(rec.log)}</pre></details>')

    if digest is not None:
        parts.append(f'<h4>Playwright actions (last {LAST_ACTIONS}, failing one last)</h4>')
        if digest.get('url'):
            parts.append(f'<p>Final URL: <code>{escape(str(digest["url"]))}</code></p>')
        parts.append(_render_actions(digest) or '<p class="empty">No actions in the trace.</p>')
        console = digest.get('console') or []
        parts.append(f'<h4>Console errors ({len(console)})</h4>')
        if console:
            parts.append('<ul class="plain">' + ''.join(
                f'<li><code>{escape(c)}</code></li>' for c in console[:20]) + '</ul>')
        else:
            parts.append('<p class="empty">None.</p>')

    if rec.advisories:
        parts.append('<h4>Advisories</h4><ul class="plain">' + ''.join(
            f'<li>{escape(a)}</li>' for a in rec.advisories) + '</ul>')

    parts.append('<h4>Screenshots</h4>')
    parts.append(_render_shots(rec) or '<p class="empty">No screenshot for this test.</p>')

    parts.append('<h4>Video</h4>')
    if rec.videos:
        for rel in rec.videos:
            parts.append(f'<video controls preload="metadata" src="{_href(rel)}"></video>'
                         f'<div><a href="{_href(rel)}">{escape(Path(rel).name)}</a></div>')
    else:
        parts.append('<p class="empty">No video kept for this test.</p>')

    parts.append('<h4>Trace</h4>')
    if rec.traces:
        for rel in rec.traces:
            absolute = os.path.abspath(run_dir / rel)
            parts.append(f'<div><a href="{_href(rel)}">{escape(Path(rel).name)}</a></div>')
            if rel.lower().endswith('.zip'):
                parts.append(f'<pre>python -m playwright show-trace "{escape(absolute)}"</pre>')
    else:
        parts.append('<p class="empty">No trace kept for this test.</p>')
    parts.append('</div>')
    return '\n'.join(parts)


def _render_row(rec: TestRecord) -> str:
    extras = ''
    if rec.advisories:
        extras += '<ul class="plain">' + ''.join(
            f'<li>{escape(a)}</li>' for a in rec.advisories) + '</ul>'
    return (f'<div class="row" data-test="{_filter_key(rec)}">'
            f'{_render_identity(rec, "div")}{_render_facts(rec)}'
            f'{extras}{_render_shots(rec)}</div>')


def _render_collapsed(title: str, records: list[TestRecord]) -> str:
    """A collapsed list, its tests grouped under their module."""
    if records:
        groups: dict[str, list[TestRecord]] = {}
        for rec in records:
            groups.setdefault(rec.module_name, []).append(rec)
        body = ''.join(
            f'<h4 class="module">{escape(module)} ({len(group)})</h4>'
            + ''.join(_render_row(r) for r in group)
            for module, group in sorted(groups.items()))
    else:
        body = '<p class="empty">None.</p>'
    return (f'<details class="section"><summary>{escape(title)} ({len(records)})</summary>'
            f'{body}</details>')


def _render_slowest(records: list[TestRecord], count: int = SLOWEST_COUNT) -> str:
    timed = sorted((r for r in records if r.seconds is not None),
                   key=lambda r: r.seconds or 0.0, reverse=True)[:count]
    if not timed:
        return '<p class="empty">No per-test timing in this run.</p>'
    rows = ''.join(
        f'<tr><td class="num">{escape(format_seconds(r.seconds or 0.0))}</td>'
        f'<td>{escape(r.display_title)}<div class="nodeid">{escape(r.nodeid)}</div></td>'
        f'<td>{escape(r.outcome)}</td></tr>' for r in timed)
    return ('<table class="facts-table"><tr><th>Duration</th><th>Test</th><th>Outcome</th></tr>'
            + rows + '</table>')


def _render_provenance(summary: dict) -> str:
    prov = summary.get('provenance') if isinstance(summary.get('provenance'), dict) else {}
    browser = ' / '.join(str(v) for v in (prov.get('browser'), prov.get('browser_channel')) if v)
    versions = ', '.join(
        f'{label} {prov[key]}' for label, key in
        (('playwright', 'playwright'), ('pytest-playwright', 'pytest_playwright')) if prov.get(key))
    facts = (('ENV', prov.get('env')), ('Host', prov.get('base_url_host')),
             ('Commit', prov.get('git_commit')), ('Browser', browser), ('Versions', versions))
    spans = [f'<span>{label}: <code>{escape(str(value))}</code></span>'
             for label, value in facts if value]
    return '<div class="meta">' + ''.join(spans) + '</div>' if spans else ''


def render_run_report(run_dir: Path, summary: dict, tests: dict[str, TestRecord],
                      unattached: list[str], previous: str | None = None) -> str:
    """Render the page from already-collected facts. Pure - no disk reads
    beyond the trace digest in the failure cards. `previous` names the
    run folder the change chips were computed against, when there is one."""
    counts = summary.get('counts') if isinstance(summary.get('counts'), dict) else {}
    target = ' '.join(str(t) for t in (summary.get('target') or [])) or run_dir.name.partition('__')[2]
    started = summary.get('started') or run_dir.name.partition('__')[0].replace('_', ' ')
    duration = summary.get('duration_s')
    exitstatus = summary.get('exitstatus')

    def by_outcome(names: tuple[str, ...]) -> list[TestRecord]:
        return sorted((t for t in tests.values() if t.outcome in names),
                      key=lambda t: (t.module_name, t.nodeid))

    failures = by_outcome(FAILURE_OUTCOMES)
    passed = by_outcome(PASSED_OUTCOMES)
    skipped = by_outcome(SKIPPED_OUTCOMES)
    unknown = by_outcome(('unknown',))

    chips = ''.join(
        f'<span class="chip {key}">{escape(key)}: {escape(str(counts.get(key, "-")))}</span>'
        for key in ('passed', 'failed', 'skipped', 'errors'))
    links = ['<a href="../index.html">all runs</a>']
    if (run_dir / 'report.html').is_file():
        links.insert(0, '<a href="report.html">pytest-html report</a>')
    if (run_dir / 'advisories.txt').is_file():
        links.append('<a href="advisories.txt">advisories.txt</a>')
    if (run_dir / 'log' / 'run.log').is_file():
        links.append('<a href="log/run.log">run.log</a>')
    if previous:
        links.append(f'<a href="../{_href(previous)}/run.html">previous run of this target</a>')
    links.append('<a href="./">folder</a>')
    compared = (f'<p class="case">Change chips compare against <code>{escape(previous)}</code>.</p>'
                if previous else '<p class="case">No earlier run of this target to compare with.</p>')

    advisories = [a for a in (summary.get('advisories') or []) if isinstance(a, dict)]
    if advisories:
        adv_body = '<ul class="plain">' + ''.join(
            f"<li><code>{escape(str(a.get('test', '')))}</code>: {escape(str(a.get('line', '')))}</li>"
            for a in advisories) + '</ul>'
    else:
        adv_body = '<p class="empty">None.</p>'

    failure_body = ('\n'.join(_render_failure(r, run_dir) for r in failures)
                    if failures else '<p class="empty">No failures in this run.</p>')

    extra_sections = ''
    if unknown:
        extra_sections += _render_collapsed('Outcome unknown', unknown)
    if unattached:
        extra_sections += ('<details class="section"><summary>Files not matched to a test '
                           f'({len(unattached)})</summary><ul class="plain">'
                           + ''.join(f'<li><a href="{_href(u)}">{escape(u)}</a></li>'
                                     for u in unattached) + '</ul></details>')

    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Run {escape(run_dir.name)}</title>
<style>{PAGE_CSS}</style>
</head>
<body>
<h1>Test run {escape(str(started))}</h1>
<div class="meta">
<span>Target: <code>{escape(target)}</code></span>
<span>Duration: {escape(str(duration)) if duration is not None else '-'} s</span>
<span>Exit status: {escape(str(exitstatus)) if exitstatus is not None else '-'}</span>
<span>Folder: <code>{escape(run_dir.name)}</code></span>
</div>
{_render_provenance(summary)}
<div class="chips">{chips}</div>
<div class="meta">{' | '.join(links)}</div>
{compared}
<p><input id="filter" type="search" placeholder="Filter tests: title, node id, case key, module, outcome"
 aria-label="Filter tests"><span id="filter-count"></span></p>

<h2 id="failures">Failures ({len(failures)})</h2>
{failure_body}

<h2 id="advisories">Advisories ({len(advisories)})</h2>
{adv_body}

<h2 id="slowest">Slowest {SLOWEST_COUNT}</h2>
{_render_slowest(list(tests.values()))}

<h2 id="passed">Passed</h2>
{_render_collapsed('Passed', passed)}

<h2 id="skipped">Skipped</h2>
{_render_collapsed('Skipped', skipped)}
{extra_sections}
<script>{_FILTER_JS}</script>
</body>
</html>
'''


def build_run_report(run_dir: Path) -> str:
    """Build the run.html for one archived run folder and return it."""
    run_dir = Path(run_dir)
    tests, unattached = collect_tests(run_dir)
    previous = find_previous_run(run_dir)
    chips = compute_deltas({nodeid: rec.outcome for nodeid, rec in tests.items()},
                           load_previous_outcomes(previous) if previous else None)
    for nodeid, chip in chips.items():
        tests[nodeid].delta = chip
    return render_run_report(run_dir, load_summary(run_dir), tests, unattached,
                             previous=previous.name if previous else None)


# ---------------------------------------------------------------- CLI

def _resolve_run_dir(arg: str) -> Path | None:
    """'latest' is the newest run folder under reports/runs; else the path."""
    if arg != 'latest':
        path = Path(arg)
        return path if path.is_dir() else None
    from plugins.run_archive import RUNS_DIR
    if not RUNS_DIR.is_dir():
        return None
    runs = sorted(p for p in RUNS_DIR.iterdir() if p.is_dir() and RUN_DIR_RE.match(p.name))
    return runs[-1] if runs else None


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1 or argv[0] in ('-h', '--help'):
        sys.stderr.write('usage: python -m plugins.run_report <run-dir|latest>\n')
        return 2
    run_dir = _resolve_run_dir(argv[0])
    if run_dir is None:
        sys.stderr.write(f'No run folder at {argv[0]}. Archived runs live under reports/runs/.\n')
        return 1
    out = run_dir / 'run.html'
    out.write_text(build_run_report(run_dir), encoding='utf-8')
    sys.stdout.write(f'{out}\n')
    return 0


if __name__ == '__main__':
    sys.exit(main())
