"""Per-run archive -- pytest plugin.

Copies each run's evidence into its own folder before the next run can
destroy it: reports/report.html is overwritten every run, pytest-playwright
wipes reports/artifacts/ at session start, and reports/screenshots/ only
ever holds the latest run.

What lands in reports/runs/<start-time>__<target>/:
  - run.html: the run's own page (plugins/run_report.py) - failures first,
    each with its error, call log, screenshots, video, and trace command.
  - report.html: this run's HTML report (skipped when the run wrote none).
  - screenshots/: the labeled per-test screenshots (see report_media).
  - traces/: everything under reports/artifacts/ - failure trace zips plus
    pytest-playwright's per-test artifact dirs.
  - last_run_results.json: the per-nodeid outcomes from qatouch_reporter,
    when that reporter ran.
  - log/: one file per test with the stdout and stderr pytest captured in
    every phase (plus the traceback of a failed phase), and run.log with
    every INFO-or-higher logging record of the session. Page-object
    prints land in the per-test files, logging in run.log.
  - summary.json: timing, counts, exit status, the invocation target,
    provenance (ENV, base_url host, git commit, browser, Playwright
    versions), the advisories below, and one record per test: node id,
    module, readable title (the docstring's first line, else the function
    name as words), the QA Touch case from config/qatouch_case_mapping.json
    when the node id is mapped, outcome, per-phase timing, and its log
    file. The node id is the key; the title is display only.
  - advisories.txt: every [VIEWS] / [LPR] / [EXPORT] marker line a test
    printed, grouped by test - the drag fallbacks, content-health deltas,
    and export timings the page objects report. They come from pytest's
    captured output, so a -s run shows them live instead of filing them.
    The same lines print as a 'run advisories' section at the end of
    every run, so nobody has to grep for them.

Start at reports/runs/index.html: one row per archived run, newest first,
with links to each run's page, report, and folder, and to health.html
(tools/health_summary.py, `python run.py health`) when that page exists.
The index is rebuilt after every run from the folders' summary.json
files, so hand-deleting a folder is safe.

Runs whose every target sits under tests/plugins or tests/tools are not
archived: those are the repo's own unit tests, and they leave no UI
evidence worth a folder.

Retention: each target keeps its newest 20 runs, capped at 100 runs in
total - per-target so a morning of debug iterations on one file can only
evict its own older runs, never the last full-suite archive. Only folders
named like <YYYY-MM-DD_HH-MM-SS>__<target> are ever pruned; index.html and
anything else parked in reports/runs/ stays.

Everything is a copy. The live files are never moved or modified, so the
report generation itself stays exactly as it is today.

Kill switch: set RUN_ARCHIVE=off to disable the plugin entirely (no archive,
no index rebuild, no pruning). Default is on - nothing to set up.

Archiving is reporting, not testing: every error in this plugin is logged
and swallowed, so an archive problem can never change the run's exit code.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.metadata
import json
import logging
import os
import re
import shutil
import subprocess
import time
from collections.abc import Mapping
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import pytest

from plugins.run_report import RUN_DIR_RE, build_run_report, module_of, readable_title

log = logging.getLogger('run_archive')

RUNS_DIR = Path('reports') / 'runs'
SCREENSHOT_DIR = Path('reports') / 'screenshots'
TRACE_DIR = Path('reports') / 'artifacts'
RESULTS_JSON = Path('logs') / 'last_run_results.json'
# QA Touch case titles come from here. The file is Justin's workflow, not
# the team's, so a missing file only costs the second title line.
MAPPING_FILE = Path('config') / 'qatouch_case_mapping.json'
# run.log is written here while the session runs (the run folder does not
# exist yet) and copied into the archive at the end.
RUN_LOG = Path('logs') / 'run.log'

# 2: adds "tests" (per-test records) and "provenance".
SCHEMA_VERSION = 2

# Per-test log files use the screenshot sanitizer and cap: the archive's
# names then sort together, and the path cap already fits them.
LOG_NAME_MAX = 120

# Marker tags the page objects print for things worth a human's eye that
# never fail a test on their own. Add a tag here when a page object
# starts printing a new one.
ADVISORY_TAGS = ('VIEWS', 'LPR', 'EXPORT')
_ADVISORY_RE = re.compile(r'^\[(' + '|'.join(ADVISORY_TAGS) + r')\] \S')
TERMINAL_ADVISORY_MAX = 40

# Retention is per target: a run only competes with other runs of the same
# slug, so repair workflows that rerun one file dozens of times a morning
# can never evict the full-suite archives the plugin exists to preserve.
# The total cap stops one-off targets from accumulating folders forever.
KEEP_RUNS = 20
KEEP_RUNS_TOTAL = 100

# Folder-name slug from the invocation. Shorter than the 120/150 name caps:
# the slug is a label, not an identifier, and every file the run produced
# nests under it - a long slug would eat the path budget of every copy.
SLUG_MAX = 40

# Copies nest the already-long trace names one folder deeper than the
# originals, which can cross Windows' 260-char MAX_PATH on a deep checkout.
# Capping the absolute destination at 250 leaves margin for the drive root.
DEST_PATH_MAX = 250

# When a filename must be cut to fit the path cap, the shortened stem keeps
# this many of its trailing chars: the tail is where near-twin names differ
# (parametrized camera ids, the PASSED/FAILED label).
FIT_TAIL = 20

# Same off-values parsing as report_media so one convention covers both.
_OFF_VALUES = ('off', '0', 'false', 'no')

# The repo's own unit tests. A run aimed only at these produces no
# screenshots, traces, or advisories - nothing an archive folder could hold.
UNIT_TEST_ROOTS = ('tests/plugins', 'tests/tools')

# Run folders are named <session-start>__<slug> (RUN_DIR_RE, shared with
# run_report); only names with this shape are ever pruned, so index.html
# and hand-made folders can never be deleted.

# pytest's terminal convention: the call phase carries the test's outcome,
# a setup crash is an error (the test never ran), a setup skip is the
# test's skip. Teardown reports never represent the test itself.
_PHASE_OUTCOME_COUNTER = {
    ('call', 'passed'): 'passed',
    ('call', 'failed'): 'failed',
    ('call', 'skipped'): 'skipped',
    ('setup', 'failed'): 'errors',
    ('setup', 'skipped'): 'skipped',
}

# The same phases, in the per-test vocabulary run_report renders
# (passed / failed / skipped / error).
_PHASE_TEST_OUTCOME = {
    ('call', 'passed'): 'passed',
    ('call', 'failed'): 'failed',
    ('call', 'skipped'): 'skipped',
    ('setup', 'failed'): 'error',
    ('setup', 'skipped'): 'skipped',
}


class _RunLog:
    """The run.log handler: every INFO-or-higher record of the session.

    Attached to the root logger so the page objects' and plugins' loggers
    all reach it. The root logger's level is lowered to INFO for the
    session when it sits above (a handler cannot see what its logger
    drops) and restored on detach.
    """

    def __init__(self) -> None:
        self.handler: logging.Handler | None = None
        self.path: Path | None = None
        self._previous_level: int | None = None

    def attach(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(path, mode='w', encoding='utf-8')
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(name)s: %(message)s'))
        root = logging.getLogger()
        if root.level == logging.NOTSET or root.level > logging.INFO:
            self._previous_level = root.level
            root.setLevel(logging.INFO)
        root.addHandler(handler)
        self.handler, self.path = handler, path

    def detach(self) -> None:
        if self.handler is None:
            return
        root = logging.getLogger()
        root.removeHandler(self.handler)
        self.handler.close()
        self.handler = None
        if self._previous_level is not None:
            root.setLevel(self._previous_level)
            self._previous_level = None


class _RunState:
    """Facts collected across the session for the end-of-run archive."""

    def __init__(self) -> None:
        self.started: float | None = None
        self.ended: float | None = None
        self.exitstatus: int | None = None
        self.counts: dict[str, int] = {'passed': 0, 'failed': 0,
                                       'skipped': 0, 'errors': 0}
        self.advisories: list[dict] = []
        # One record per test, in execution order, keyed by node id.
        self.tests: dict[str, dict] = {}
        # The captured output of every phase, for the log/ files. Kept
        # apart from the records so summary.json stays small.
        self.captured: dict[str, list[dict]] = {}
        # Docstrings seen at makereport, where the item is in reach.
        self.docs: dict[str, str] = {}
        self.mapping: dict[str, dict] | None = None
        self.run_log = _RunLog()

    @property
    def tests_run(self) -> int:
        return sum(self.counts.values())

    def case_mapping(self) -> dict[str, dict]:
        """The QA Touch mapping, read once per session."""
        if self.mapping is None:
            self.mapping = load_case_mapping(MAPPING_FILE)
        return self.mapping


_state = _RunState()


def _archive_disabled(environ: Mapping[str, str]) -> bool:
    """Kill switch: RUN_ARCHIVE=off turns the whole plugin off."""
    return environ.get('RUN_ARCHIVE', '').strip().lower() in _OFF_VALUES


def _process_may_archive(config: Any, environ: Mapping[str, str]) -> bool:
    """The guards known at session start: is this a process that archives?

    - --collect-only never archives: run_suite's planning pass collects
      before the real run, and its empty "run" would bury the real one.
    - xdist workers never archive: each worker starts its own session; the
      controller sees every result and archives once.
    - Every target is a unit-test root (tests/plugins, tests/tools): those
      runs leave no UI evidence, and a folder per plugin test run would
      bury the suite runs the archive exists for.
    """
    if config.getoption('--collect-only', default=False):
        return False
    if environ.get('PYTEST_XDIST_WORKER'):
        return False
    return not _unit_tests_only(getattr(config, 'args', None) or [])


def _should_archive(config: Any, environ: Mapping[str, str], tests_run: int) -> bool:
    """Decide whether this process may archive the finished run.

    The session-start guards above, plus: zero tests ran means nothing
    was produced, so there is nothing to keep, and a folder per typo'd
    invocation would drown the real runs.
    """
    return _process_may_archive(config, environ) and tests_run > 0


def _unit_tests_only(args: list[str]) -> bool:
    """True when every invocation target sits under a unit-test root.

    A target is a path or a node id (path::Class::test); only the path
    part counts. Separators are normalized so a backslash or an absolute
    path still lands under its root. No targets means the whole suite.
    """
    targets = [str(a) for a in args if str(a).strip()]
    if not targets:
        return False
    for target in targets:
        path = target.split('::', 1)[0].replace('\\', '/').strip('/')
        if not any(f'/{root}/' in f'/{path}/' for root in UNIT_TEST_ROOTS):
            return False
    return True


def _classify(when: str, outcome: str) -> str | None:
    """Map a report phase + outcome to a summary counter, or None to ignore."""
    return _PHASE_OUTCOME_COUNTER.get((when, outcome))


def _build_slug(args: list[str], markexpr: str = '') -> str:
    """Build the folder-name slug from what the run was asked to do.

    config.args joined, plus the -m expression when one was given - same
    sanitizer as report_media._safe_name so run folders and the files inside
    them follow one naming convention. Empty invocations become 'all'.
    """
    parts = [*list(args or []), markexpr] if markexpr else list(args or [])
    raw = ' '.join(parts)
    return re.sub(r'[^\w.-]+', '-', raw).strip('-')[:SLUG_MAX] or 'all'


def _unique_dir(parent: Path, name: str) -> Path:
    """Pick a folder name that does not collide with an existing run.

    Two quick debugging runs of the same target can start in the same
    second; the second gets a -2 (then -3, ...) suffix instead of pouring
    its copies into the first run's folder.
    """
    candidate = parent / name
    suffix = 2
    while candidate.exists():
        candidate = parent / f'{name}-{suffix}'
        suffix += 1
    return candidate


def _fit_dest(dest: Path, limit: int = DEST_PATH_MAX) -> Path | None:
    """Keep the absolute destination path under the Windows path cap.

    Returns the path unchanged when it fits, or a shortened variant when
    the filename can absorb the cut. A plain cut is not enough: nodeid-
    derived names often differ only past it (parametrized camera ids in
    a suite that runs the same test per camera), and two sources fitted
    to one name would make the later copy silently overwrite the earlier.
    The shortened stem keeps its head and tail around a digest of the full
    stem, so distinct sources stay distinct. None when the directory
    leaves no room for a usable filename.
    """
    absolute = Path(os.path.abspath(dest))
    if len(str(absolute)) <= limit:
        return dest
    digest = hashlib.sha256(absolute.stem.encode('utf-8')).hexdigest()[:8]
    room = limit - len(str(absolute.parent)) - len(absolute.suffix) - 1
    keep = room - len(digest) - 2  # the two '-' joiners
    if keep < 2:
        return None
    tail = min(FIT_TAIL, keep // 2)
    fitted = absolute.parent / (f'{absolute.stem[:keep - tail]}-{digest}'
                                f'-{absolute.stem[-tail:]}{absolute.suffix}')
    log.warning(f'run_archive: shortened {dest.name} to {fitted.name} '
                f'to fit the {limit}-char path cap')
    return fitted


def _copy_report(config: Any, started: float, dest: Path) -> str | None:
    """Copy this run's HTML report; return the archived name, or None.

    The report path is configurable (--html): the team default is
    reports/report.html but debugging runs override it, so the option is
    the source of truth. A report older than the session start is a
    leftover from an earlier run (this run may have died before pytest-html
    wrote one) and must not be filed under this run - mtime is the
    freshness signal.
    """
    htmlpath = config.getoption('htmlpath', default=None)
    if not htmlpath:
        return None
    src = Path(htmlpath)
    try:
        if not src.is_file() or src.stat().st_mtime < started:
            return None
        shutil.copy2(src, dest / 'report.html')
    except OSError as e:
        log.warning(f'run_archive: could not copy the report {src}: {e}')
        return None
    return 'report.html'


def _copy_screenshots(started: float, dest: Path) -> None:
    """Copy this run's *.png files sitting directly in reports/screenshots/.

    report_media empties that folder at session start - but only when that
    plugin is on, so under REPORT_SCREENSHOTS=off an earlier run's images
    are still sitting there. As with the report copy, mtime against the
    session start is the freshness signal that keeps them out.
    """
    if not SCREENSHOT_DIR.is_dir():
        return
    target_root = dest / 'screenshots'
    for png in sorted(SCREENSHOT_DIR.glob('*.png')):
        if not png.is_file():
            continue
        try:
            if png.stat().st_mtime < started:
                continue
            target = _fit_dest(target_root / png.name)
            if target is None:
                log.warning(f'run_archive: skipped {png.name}: its destination '
                            f'directory leaves no room for a filename under '
                            f'the {DEST_PATH_MAX}-char path cap')
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(png, target)
        except OSError as e:
            log.warning(f'run_archive: could not copy {png}: {e}')


def _copy_traces(dest: Path) -> None:
    """Copy the full contents of reports/artifacts/ into traces/.

    That folder holds conftest's failure trace zips plus pytest-playwright's
    per-test artifact dirs, and is wiped at each session start - so at
    session end its contents belong to exactly this run.
    """
    if not TRACE_DIR.is_dir():
        return
    target_root = dest / 'traces'
    for src in sorted(TRACE_DIR.rglob('*')):
        if not src.is_file():
            continue
        try:
            target = _fit_dest(target_root / src.relative_to(TRACE_DIR))
            if target is None:
                log.warning(f'run_archive: skipped {src.name}: its destination '
                            f'directory leaves no room for a filename under '
                            f'the {DEST_PATH_MAX}-char path cap')
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
        except OSError as e:
            log.warning(f'run_archive: could not copy {src}: {e}')


def _copy_results_json(started: float, dest: Path) -> None:
    """Copy qatouch_reporter's per-nodeid outcomes JSON, when it is fresh.

    The reporter only writes the file when it is active, so a stale mtime
    means the file on disk belongs to an earlier run and stays out.
    """
    try:
        if not RESULTS_JSON.is_file() or RESULTS_JSON.stat().st_mtime < started:
            return
        shutil.copy2(RESULTS_JSON, dest / RESULTS_JSON.name)
    except OSError as e:
        log.warning(f'run_archive: could not copy {RESULTS_JSON}: {e}')


def scan_advisories(text: str | None) -> list[str]:
    """The advisory marker lines in a block of captured output, in order.

    Only lines opening with one of ADVISORY_TAGS count; the [AUTH] and
    DEBUG chatter every test prints is not an advisory. Duplicates within
    one block collapse - a poll that prints the same warning each tick
    is one advisory, not forty.
    """
    seen: set[str] = set()
    lines = []
    for raw in (text or '').splitlines():
        line = raw.strip()
        if _ADVISORY_RE.match(line) and line not in seen:
            seen.add(line)
            lines.append(line)
    return lines


def _format_advisories(advisories: list[dict]) -> str:
    """advisories.txt body: one block per test, its lines indented."""
    out = []
    current = None
    for item in advisories:
        if item.get('test') != current:
            current = item.get('test')
            out.append(str(current))
        out.append(f"  {item.get('line', '')}")
    return '\n'.join(out) + '\n'


# ---------------------------------------------------------------- per-test facts

def load_case_mapping(path: Path = MAPPING_FILE) -> dict[str, dict]:
    """Node id -> {'case_key', 'case_title'} from the QA Touch mapping file.

    Empty when the file is missing or not the expected shape: the case
    title is a convenience line on the page, never a reason to fail.
    """
    try:
        loaded = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}
    mappings = loaded.get('mappings') if isinstance(loaded, dict) else None
    if not isinstance(mappings, dict):
        return {}
    out: dict[str, dict] = {}
    for nodeid, row in mappings.items():
        if isinstance(row, dict) and row.get('case_key'):
            out[str(nodeid)] = {'case_key': str(row['case_key']),
                                'case_title': str(row.get('case_title') or '')}
    return out


def lookup_case(mapping: Mapping[str, dict], nodeid: str) -> dict:
    """The mapped QA Touch case for a node id, or None fields when unmapped.

    Exact id first. Then the id without its parameter part against the
    keys without theirs: a mapping keyed on the bare function still
    names the [chromium] variant pytest-playwright runs.
    """
    row = mapping.get(nodeid)
    if row is None:
        bare = re.sub(r'\[.*\]$', '', nodeid)
        for key, candidate in mapping.items():
            if re.sub(r'\[.*\]$', '', key) == bare:
                row = candidate
                break
    if row is None:
        return {'case_key': None, 'case_title': None}
    return {'case_key': row.get('case_key'), 'case_title': row.get('case_title') or None}


def log_file_name(nodeid: str) -> str:
    """The per-test log file's name: the sanitized node id plus .log."""
    return re.sub(r'[^\w.-]+', '-', nodeid).strip('-')[:LOG_NAME_MAX] + '.log'


def phase_capture(report: Any, stream: str) -> str:
    """The text pytest captured on `stream` (stdout or stderr) during this
    phase alone.

    A report's capstdout joins every section the item has collected so
    far, so the call report repeats setup's output and teardown repeats
    both (seen in the archived logs). The phase's own section, titled
    'Captured stdout call', holds only its text. Reports without sections
    (fakes, other plugins' objects) fall back to the joined attribute.
    """
    sections = getattr(report, 'sections', None)
    if isinstance(sections, list):
        wanted = f'Captured {stream} {report.when}'
        return ''.join(str(text) for title, text in sections if title == wanted)
    return getattr(report, f'cap{stream}', '') or ''


def record_phase(state: _RunState, report: Any, doc: str | None = None,
                 mapping: Mapping[str, dict] | None = None) -> None:
    """Fold one phase report into the test's record and its captured output.

    The first phase seen creates the record (title, module, case). Rerun
    outcomes (pytest-rerunfailures) are not final and are ignored; the
    attempt that ends the test overwrites the phases of the earlier ones.
    """
    nodeid = str(report.nodeid)
    rec = state.tests.get(nodeid)
    if rec is None:
        case = lookup_case(mapping or {}, nodeid)
        rec = state.tests[nodeid] = {
            'nodeid': nodeid, 'module': module_of(nodeid),
            'title': readable_title(nodeid, doc),
            'case_key': case['case_key'], 'case_title': case['case_title'],
            'outcome': None, 'duration_s': 0.0, 'phases': {}, 'log_file': None,
        }
    if report.outcome == 'rerun':
        return
    duration = float(getattr(report, 'duration', 0.0) or 0.0)
    rec['phases'][report.when] = round(duration, 3)
    rec['duration_s'] = round(sum(rec['phases'].values()), 3)
    outcome = _PHASE_TEST_OUTCOME.get((report.when, report.outcome))
    if outcome is not None:
        rec['outcome'] = outcome
    state.captured.setdefault(nodeid, []).append({
        'phase': report.when, 'outcome': report.outcome, 'duration': duration,
        'stdout': phase_capture(report, 'stdout'),
        'stderr': phase_capture(report, 'stderr'),
        'error': (getattr(report, 'longreprtext', '') or '') if report.outcome == 'failed' else '',
        # a skip's reason is the phase's whole story - keep it beside the output
        'skip': (getattr(report, 'longreprtext', '') or '') if report.outcome == 'skipped' else '',
    })


def format_test_log(rec: Mapping[str, Any], phases: list[dict]) -> str:
    """One test's log file: its names, then each phase's captured output."""
    lines = [str(rec.get('nodeid', '')), str(rec.get('title', ''))]
    if rec.get('case_key'):
        lines.append(f"QA Touch {rec['case_key']}: {rec.get('case_title') or ''}".rstrip(': '))
    for phase in phases:
        lines.append('')
        lines.append(f"=== {phase.get('phase')}: {phase.get('outcome')} "
                     f"({float(phase.get('duration') or 0.0):.2f} s) ===")
        wrote = False
        for label in ('stdout', 'stderr', 'error', 'skip'):
            text = str(phase.get(label) or '')
            if text.strip():
                lines.append(f'--- {label} ---')
                lines.append(text.rstrip())
                wrote = True
        if not wrote:
            lines.append('(no output)')
    return '\n'.join(lines) + '\n'


def _write_logs(dest: Path, state: _RunState) -> None:
    """Write log/<test>.log per test and copy the session's run.log."""
    log_dir = dest / 'log'
    for nodeid, rec in state.tests.items():
        target = _fit_dest(log_dir / log_file_name(nodeid))
        if target is None:
            log.warning(f'run_archive: skipped the log of {nodeid}: its destination '
                        f'directory leaves no room for a filename under the '
                        f'{DEST_PATH_MAX}-char path cap')
            continue
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(format_test_log(rec, state.captured.get(nodeid) or []),
                              encoding='utf-8', errors='replace')
            rec['log_file'] = (Path('log') / target.name).as_posix()
        except OSError as e:
            log.warning(f'run_archive: could not write the log of {nodeid}: {e}')
    run_log = state.run_log.path
    if run_log is not None and run_log.is_file():
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(run_log, log_dir / 'run.log')
        except OSError as e:
            log.warning(f'run_archive: could not copy {run_log}: {e}')


def _provenance(config: Any, environ: Mapping[str, str]) -> dict:
    """Where and with what the run happened. Every field tolerates absence."""
    out: dict[str, Any] = {
        'env': (environ.get('ENV') or 'qa').strip().lower(), 'base_url_host': None,
        'git_commit': None, 'playwright': None, 'pytest_playwright': None,
        'browser': None, 'browser_channel': None,
    }
    try:
        from config.base_config import config as env_config
        out['base_url_host'] = urlparse(str(env_config.get('base_url') or '')).netloc or None
    except Exception as e:  # noqa: BLE001 - the env module needs .env and network names; the host is a label
        log.debug(f'run_archive: no base_url host: {e}')
    try:
        result = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], capture_output=True,
                                text=True, timeout=10, check=False)
        if result.returncode == 0:
            out['git_commit'] = result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError) as e:
        log.debug(f'run_archive: no git commit: {e}')
    for key, dist in (('playwright', 'playwright'), ('pytest_playwright', 'pytest-playwright')):
        with contextlib.suppress(importlib.metadata.PackageNotFoundError):
            out[key] = importlib.metadata.version(dist)
    browsers = config.getoption('browser', default=None)
    if isinstance(browsers, (list, tuple)):
        browsers = ', '.join(str(b) for b in browsers)
    out['browser'] = str(browsers) if browsers else None
    channel = config.getoption('browser_channel', default=None)
    out['browser_channel'] = str(channel) if channel else None
    return out


def _build_summary(*, started: float, ended: float, exitstatus: int | None,
                   counts: Mapping[str, int], target: list[str], markexpr: str,
                   keyword: str, report_file: str | None,
                   advisories: list[dict] | None = None,
                   tests: list[dict] | None = None,
                   provenance: Mapping[str, Any] | None = None) -> dict:
    """Build the summary.json payload. Fixed shape - the index renders it."""
    return {
        'schema_version': SCHEMA_VERSION,
        'started': datetime.fromtimestamp(started).isoformat(timespec='seconds'),
        'ended': datetime.fromtimestamp(ended).isoformat(timespec='seconds'),
        'duration_s': round(ended - started, 1),
        'exitstatus': exitstatus,
        'counts': {key: int(counts.get(key, 0))
                   for key in ('passed', 'failed', 'skipped', 'errors')},
        'target': list(target),
        'markexpr': markexpr or '',
        'keyword': keyword or '',
        'report_file': report_file,
        'provenance': dict(provenance or {}),
        'advisories': [dict(a) for a in (advisories or [])],
        'tests': [dict(t, phases=dict(t.get('phases') or {})) for t in (tests or [])],
    }


def _select_prunable(names: list[str], keep: int = KEEP_RUNS,
                     total: int = KEEP_RUNS_TOTAL) -> list[str]:
    """Pick the run-folder names that retention lets go.

    A run stays while it is among the newest `keep` of its own slug AND
    the newest `total` overall. Per-slug counting is the point: a flat
    newest-N would let a morning of debug iterations on one file evict
    the full-suite archives the plugin exists to preserve.

    Only names matching RUN_DIR_RE are candidates; their timestamp prefix
    makes name order chronological order, so a plain sort finds the oldest.
    """
    runs = sorted((n for n in names if RUN_DIR_RE.match(n)), reverse=True)
    seen_per_slug: dict[str, int] = {}
    prunable = []
    for rank, name in enumerate(runs):
        slug = name.partition('__')[2]
        seen_per_slug[slug] = seen_per_slug.get(slug, 0) + 1
        if seen_per_slug[slug] > keep or rank >= total:
            prunable.append(name)
    return prunable


def _prune_runs(runs_dir: Path, keep: int = KEEP_RUNS,
                total: int = KEEP_RUNS_TOTAL) -> None:
    """Delete the run folders retention lets go, and nothing else.

    Deliberately narrow - only directories directly inside runs_dir whose
    names match the run pattern, never anything outside it - so a
    misconfigured path can never eat more than old archives.
    """
    if not runs_dir.is_dir():
        return
    names = [p.name for p in runs_dir.iterdir() if p.is_dir()]
    for name in _select_prunable(names, keep, total):
        try:
            shutil.rmtree(runs_dir / name)
            log.info(f'run_archive: pruned old run {name}')
        except OSError as e:
            log.warning(f'run_archive: could not prune {name}: {e}')


def _load_entries(runs_dir: Path) -> list[dict]:
    """Read each run folder's summary.json into an index entry.

    Scanning the folders instead of remembering state keeps the index
    correct when folders are hand-deleted or hold no readable summary
    (older layouts, an archive that died mid-write) - such folders still
    get a row built from their name alone.
    """
    entries: list[dict] = []
    if not runs_dir.is_dir():
        return entries
    for folder in sorted(runs_dir.iterdir()):
        if not folder.is_dir() or not RUN_DIR_RE.match(folder.name):
            continue
        summary: dict = {}
        try:
            loaded = json.loads((folder / 'summary.json').read_text(encoding='utf-8'))
            if isinstance(loaded, dict):
                summary = loaded
        except (OSError, ValueError):
            pass
        entries.append({'name': folder.name, 'summary': summary,
                        'has_report': (folder / 'report.html').is_file(),
                        'has_run_report': (folder / 'run.html').is_file()})
    return entries


def _render_index(entries: list[dict], has_health: bool = False) -> str:
    """Render the archive index page, newest run first.

    Plain, self-contained HTML: the page is opened from disk, so it can
    depend on nothing but the run folders sitting next to it. Every summary
    key is optional - a row shows '-' where a value is unknown. The health
    link only appears when health.html exists beside the index.
    """
    rows = []
    for entry in sorted(entries, key=lambda e: e.get('name', ''), reverse=True):
        name = entry.get('name', '')
        summary = entry.get('summary') or {}
        counts = summary.get('counts') or {}
        stamp, _, slug = name.partition('__')
        started = summary.get('started') or stamp.replace('_', ' ')
        target = ' '.join(summary.get('target') or []) or slug
        exitstatus = summary.get('exitstatus')
        advisories = summary.get('advisories')
        advisory_count = len(advisories) if isinstance(advisories, list) else '-'
        links = [f'<a href="{escape(name, quote=True)}/">folder</a>']
        if entry.get('has_report'):
            links.insert(0, f'<a href="{escape(name, quote=True)}/report.html">report</a>')
        if entry.get('has_run_report'):
            links.insert(0, f'<a href="{escape(name, quote=True)}/run.html">run report</a>')
        cells = [
            escape(str(started)),
            escape(str(target)),
            *[escape(str(counts.get(key, '-')))
              for key in ('passed', 'failed', 'skipped', 'errors')],
            '-' if exitstatus is None else escape(str(exitstatus)),
            escape(str(advisory_count)),
            ' '.join(links),
        ]
        rows.append('<tr>' + ''.join(f'<td>{cell}</td>' for cell in cells) + '</tr>')

    body = '\n'.join(rows) if rows else ('<tr><td colspan="9">No archived runs '
                                         'yet. Run the suite once.</td></tr>')
    health = ('<p><a href="health.html">Health summary</a>: pass rates, flaky '
              'candidates, and the slowest tests across recent runs.</p>' if has_health
              else '<p><code>python run.py health</code> builds health.html: pass rates, '
                   'flaky candidates, and the slowest tests across recent runs.</p>')
    return f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Test run archive</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; }}
table {{ border-collapse: collapse; }}
th, td {{ border: 1px solid #ccc; padding: 0.35rem 0.7rem; text-align: left; }}
th {{ background: #f0f0f0; }}
</style>
</head>
<body>
<h1>Test run archive</h1>
<p>One folder per test run, newest first. Open a run's <b>run report</b>
for its failures with their screenshots, video, and trace. The archive
keeps the newest {KEEP_RUNS} runs of each target ({KEEP_RUNS_TOTAL} in
total) and rebuilds this page after every run.</p>
{health}
<table>
<tr><th>Started</th><th>Target</th><th>Passed</th><th>Failed</th>
<th>Skipped</th><th>Errors</th><th>Exit</th><th>Advisories</th><th>Open</th></tr>
{body}
</table>
</body>
</html>
'''


def _write_index(runs_dir: Path) -> None:
    """Regenerate index.html from whatever run folders exist right now."""
    if not runs_dir.is_dir():
        return
    (runs_dir / 'index.html').write_text(
        _render_index(_load_entries(runs_dir), has_health=(runs_dir / 'health.html').is_file()),
        encoding='utf-8')


def _archive_run(config: Any, state: _RunState) -> None:
    """Copy the finished run's outputs into its own dated folder."""
    markexpr = config.getoption('markexpr', default='') or ''
    keyword = config.getoption('keyword', default='') or ''
    stamp = datetime.fromtimestamp(state.started).strftime('%Y-%m-%d_%H-%M-%S')
    dest = _unique_dir(RUNS_DIR, f'{stamp}__{_build_slug(config.args, markexpr)}')
    dest.mkdir(parents=True, exist_ok=True)

    report_file = _copy_report(config, state.started, dest)
    _copy_screenshots(state.started, dest)
    _copy_traces(dest)
    _copy_results_json(state.started, dest)
    # Before the summary: writing the logs fills in each record's log_file.
    _write_logs(dest, state)

    # A sessionfinish that never ran (crash before initstate 2) leaves ended
    # unset; the archive still records an honest end time.
    ended = state.ended if state.ended is not None else time.time()
    summary = _build_summary(started=state.started, ended=ended,
                             exitstatus=state.exitstatus, counts=state.counts,
                             target=config.args, markexpr=markexpr,
                             keyword=keyword, report_file=report_file,
                             advisories=state.advisories,
                             tests=list(state.tests.values()),
                             provenance=_provenance(config, os.environ))
    (dest / 'summary.json').write_text(json.dumps(summary, indent=2),
                                       encoding='utf-8')
    if state.advisories:
        (dest / 'advisories.txt').write_text(_format_advisories(state.advisories),
                                             encoding='utf-8')
    _write_run_report(dest)
    log.info(f'run_archive: archived the run to {dest}')


def _write_run_report(dest: Path) -> None:
    """Build the run's own page from the copies just filed.

    Last, so it sees summary.json and every copy. The builder reads only
    the folder, so `python -m plugins.run_report <folder>` can rebuild the
    page later. A builder error costs the page, never the archive.
    """
    try:
        (dest / 'run.html').write_text(build_run_report(dest), encoding='utf-8')
    except Exception as e:  # noqa: BLE001 - the page is a convenience; the copies already stand
        log.warning(f'run_archive: could not build run.html for {dest.name}: {e}')


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session: Any) -> None:
    """Record the session start time - it names the archive folder, and any
    report or results file older than it belongs to an earlier run - and
    start run.log in every process that will archive. First among the
    sessionstart hooks, so the other plugins' start-up lines land in it."""
    _state.started = time.time()
    if _archive_disabled(os.environ) or not _process_may_archive(session.config, os.environ):
        return
    try:
        _state.run_log.attach(RUN_LOG)
    except Exception as e:  # noqa: BLE001 - a lost run.log must never block the session
        log.warning(f'run_archive: could not start {RUN_LOG}: {e}')


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: Any, call: Any):  # noqa: ARG001 - pytest fixes the hook signature
    """Remember the test's docstring while the item is in reach.

    The phase itself is recorded in logreport below, which also fires on
    the xdist controller (the process that archives) where this hook
    does not.
    """
    yield
    if item.nodeid in _state.docs:
        return
    try:
        doc = getattr(getattr(item, 'obj', None), '__doc__', None)
        _state.docs[item.nodeid] = doc if isinstance(doc, str) else ''
    except Exception as e:  # noqa: BLE001 - a title fallback is cheaper than a broken run
        log.debug(f'run_archive: no docstring for {item.nodeid}: {e}')


def pytest_runtest_logreport(report: Any) -> None:
    """Tally outcomes for summary.json and the zero-test guard, keep the
    advisory marker lines each phase printed, and record the phase's
    facts and captured output for the test's summary record and log."""
    counter = _classify(report.when, report.outcome)
    if counter is not None:
        _state.counts[counter] += 1
    if report.when in ('setup', 'call'):
        # The phase's own capture: capstdout would repeat setup's lines
        # under the call phase and file each advisory twice.
        captured = phase_capture(report, 'stdout') + '\n' + phase_capture(report, 'stderr')
        for line in scan_advisories(captured):
            _state.advisories.append({'test': report.nodeid,
                                      'phase': report.when, 'line': line})
    try:
        record_phase(_state, report, doc=_state.docs.get(report.nodeid),
                     mapping=_state.case_mapping())
    except Exception as e:  # noqa: BLE001 - per-test facts are reporting, never a verdict
        log.debug(f'run_archive: could not record {report.nodeid}: {e}')


def pytest_sessionfinish(session: Any, exitstatus: int) -> None:  # noqa: ARG001 - pytest fixes the hook signature
    """Record when the session ended and how it exited."""
    _state.ended = time.time()
    _state.exitstatus = int(exitstatus)


def pytest_terminal_summary(terminalreporter: Any, exitstatus: int, config: Any) -> None:  # noqa: ARG001 - pytest fixes the hook signature
    """Print the run's advisory lines where the team will actually see them.

    Passing tests swallow their output, so the [VIEWS]/[LPR]/[EXPORT]
    markers would otherwise only exist inside the archive.
    """
    advisories = _state.advisories
    if not advisories:
        return
    try:
        terminalreporter.section(f'run advisories ({len(advisories)})')
        for item in advisories[:TERMINAL_ADVISORY_MAX]:
            terminalreporter.write_line(f"{item['test']}: {item['line']}")
        if len(advisories) > TERMINAL_ADVISORY_MAX:
            terminalreporter.write_line(
                f'... {len(advisories) - TERMINAL_ADVISORY_MAX} more in the '
                f"run's advisories.txt under {RUNS_DIR}/")
    except Exception as e:  # noqa: BLE001 - a summary must never fail the run
        log.debug(f'run_archive: could not print advisories: {e}')


def pytest_unconfigure(config: Any) -> None:
    """Archive the finished run, prune old runs, rebuild the index.

    This hook - not sessionfinish - because pytest fires unconfigure
    strictly after every sessionfinish (wrap_session in _pytest/main.py
    runs the sessionfinish hook, then _ensure_unconfigure). pytest-html
    writes the report file during ITS sessionfinish and conftest mails it
    during its own, so by unconfigure the report is complete and sent and
    the copies here always see the finished file.
    """
    # Closed first so the archive copies a complete, flushed run.log.
    _state.run_log.detach()
    if _archive_disabled(os.environ):
        return
    if not _should_archive(config, os.environ, _state.tests_run):
        return
    try:
        _archive_run(config, _state)
    except Exception as e:  # noqa: BLE001 - archiving must never change the run's exit code
        log.warning(f'run_archive: could not archive the run: {e}')
    try:
        _prune_runs(RUNS_DIR)
    except Exception as e:  # noqa: BLE001 - pruning is best-effort housekeeping
        log.warning(f'run_archive: could not prune old runs: {e}')
    try:
        _write_index(RUNS_DIR)
    except Exception as e:  # noqa: BLE001 - a stale index is better than a broken run
        log.warning(f'run_archive: could not rebuild the index: {e}')
