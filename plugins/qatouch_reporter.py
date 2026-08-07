"""QA Touch Result Reporter -- pytest plugin.

Uploads test results to QA Touch after a test session completes.
Requires a test run to exist in QA Touch (create one first).

Activation:
  pytest --qatouch-upload --qatouch-run <RUN_KEY>

Or via env vars:
  QATOUCH_UPLOAD=1  QATOUCH_RUN_KEY=<key>  pytest ...

The plugin:
  1. Loads config/qatouch_case_mapping.json for nodeid -> case_key mapping
  2. Collects pass/fail/skip results per test via pytest hooks
  3. At session end, batch-uploads results to QA Touch with retry

Resilience:
  - Upload retries 3 times with exponential backoff (2s, 4s, 8s)
  - On final failure, writes results to logs/upload_failures.json for later retry
  - Never crashes the test process - upload errors are logged, not raised

Status codes: passed=1, blocked/skipped=3, failed=5
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

log = logging.getLogger('qatouch_reporter')

ROOT = Path(__file__).resolve().parent.parent
MAPPING_PATH = ROOT / 'config' / 'qatouch_case_mapping.json'
FAILURE_LOG_DIR = ROOT / 'logs'
FAILURE_LOG_PATH = FAILURE_LOG_DIR / 'upload_failures.json'
# Per-nodeid run results dumped at session-finish; consumed by the downstream
# Jira bug filer (tools/run_suite.py and friends). Lives under logs/ alongside
# the upload-failure log so both are gitignored together.
RUN_RESULTS_PATH = FAILURE_LOG_DIR / 'last_run_results.json'

# Retry configuration
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2  # seconds, doubles each attempt

# QA Touch status codes
STATUS_PASSED = 1
STATUS_BLOCKED = 3
STATUS_FAILED = 5

PYTEST_TO_QT = {
    'passed': STATUS_PASSED,
    'failed': STATUS_FAILED,
    'skipped': STATUS_BLOCKED,
}


def pytest_addoption(parser: Any) -> None:
    group = parser.getgroup('qatouch', 'QA Touch result reporting')
    group.addoption(
        '--qatouch-upload',
        action='store_true',
        default=False,
        help='Upload test results to QA Touch after the session.',
    )
    group.addoption(
        '--qatouch-run',
        default=None,
        help='QA Touch test run key (e.g. "d6pw"). Also: QATOUCH_RUN_KEY env var.',
    )


def pytest_configure(config: Any) -> None:
    upload = config.getoption('--qatouch-upload', default=False) or os.environ.get('QATOUCH_UPLOAD', '').lower() in ('1', 'true', 'yes')
    if not upload:
        return

    run_key = config.getoption('--qatouch-run', default=None) or os.environ.get('QATOUCH_RUN_KEY')
    if not run_key:
        log.warning('QA Touch upload enabled but no test run key provided. '
                     'Use --qatouch-run <key> or QATOUCH_RUN_KEY env var.')
        return

    config._qatouch_reporter = QATouchReporter(run_key)
    config.pluginmanager.register(config._qatouch_reporter, 'qatouch_reporter')


def _format_duration(seconds: float) -> str:
    """Format pytest duration for QA Touch's `execution_time` field.

    Matches the format the vendor playwright-qatouch-reporter emits (e.g. "1.2s",
    "450ms") so values are comparable in the QA Touch UI.
    """
    if seconds is None or seconds < 0:
        return ''
    if seconds < 1.0:
        return f'{int(round(seconds * 1000))}ms'
    return f'{seconds:.1f}s'


_OUTCOME_RANK = {'passed': 0, 'skipped': 1, 'failed': 2}


def _worse_outcome(new: str, existing: str | None) -> bool:
    """Return True if `new` outcome should overwrite `existing` (worse wins)."""
    return _OUTCOME_RANK.get(new, -1) > _OUTCOME_RANK.get(existing or '', -1)


DEFAULT_PROJECT_KEY = 'JlW1'


class QATouchReporter:
    def __init__(self, run_key: str):
        self.run_key = run_key
        self.project_key = os.environ.get('QATOUCH_PROJECT_ID', DEFAULT_PROJECT_KEY)
        self.results: dict[str, int] = {}  # case_key -> status code
        # case_key -> project_key resolved at record time (per-test marker override)
        self.case_projects: dict[str, str] = {}
        self.durations: dict[str, float] = {}  # case_key -> duration in seconds
        self.screenshots: dict[str, bytes] = {}  # case_key -> PNG bytes (failures only)
        self.nodeid_outcomes: dict[str, dict] = {}  # nodeid -> {outcome, duration, case_key}
        self.mapping = self._load_mapping()
        self.case_to_run_key: dict[str, str] = {}  # case_key -> run_key (for API-created runs)
        self.use_playwright_endpoint = os.environ.get(
            'QATOUCH_USE_PLAYWRIGHT_ENDPOINT', '').lower() in ('1', 'true', 'yes')
        # Failure-screenshot capture is enabled by default for the playwright
        # endpoint, since legacy uploads ignore attachments anyway.
        self.capture_screenshots = self.use_playwright_endpoint and (
            os.environ.get('QATOUCH_CAPTURE_SCREENSHOTS', '1').lower()
            not in ('0', 'false', 'no'))
        self.stats = {'mapped': 0, 'unmapped': 0, 'uploaded': 0, 'errors': 0,
                      'retries': 0, 'saved_for_retry': 0, 'screenshots': 0}
        # Set by pytest_sessionfinish once an upload is attempted.
        self._upload_path_used: str = '(none)'

    def _load_mapping(self) -> dict[str, str]:
        """Load nodeid -> case_key mapping from JSON file."""
        if not MAPPING_PATH.exists():
            log.warning(f'Mapping file not found: {MAPPING_PATH}')
            log.warning('Run: python tools/qatouch_mapper.py build')
            return {}

        with open(MAPPING_PATH) as f:
            data = json.load(f)

        # Build nodeid -> case_key lookup
        mappings = data.get('mappings', {})
        return {nodeid: info['case_key'] for nodeid, info in mappings.items()}

    def _build_run_key_mapping(self, client) -> None:
        """Build case_key -> run_key mapping for API-created runs.

        API-created runs require run_key (per-result key) instead of case_key
        for result uploads. This fetches the run results and builds the lookup.
        """
        try:
            all_results = client.get_all_test_run_results(
                self.project_key, self.run_key)
            for r in all_results:
                case_id = r.get('case_id', '')
                run_key = r.get('run_key', '')
                if case_id and run_key:
                    self.case_to_run_key[case_id] = run_key
            if self.case_to_run_key:
                log.info(f'QA Touch: Built run_key mapping for {len(self.case_to_run_key)} cases')
        except Exception as e:
            log.debug(f'QA Touch: Could not build run_key mapping: {e}')

    def _nodeid_variants(self, nodeid: str) -> list[str]:
        """Generate nodeid variants for flexible matching.

        Playwright tests have [chromium] suffix, parametrized tests have [param].
        Try exact match first, then without parameters.
        """
        variants = [nodeid]
        # Strip browser parameter: tests/ui/views/test_views_basic.py::TestClass::test_func[chromium]
        if '[' in nodeid:
            base = nodeid.split('[')[0]
            variants.append(base)
        return variants

    @staticmethod
    def _get_marker_case_key(item: Any) -> str | None:
        """Read case_key from @pytest.mark.qatouch("KEY") marker on the test item."""
        marker = item.get_closest_marker('qatouch')
        if marker and marker.args:
            return marker.args[0]
        return None

    @staticmethod
    def _get_marker_project_key(item: Any) -> str | None:
        """Read project_key from @pytest.mark.qatouch_project("PKEY") on the test item.

        Per-test marker is authoritative; falls back to the reporter's default
        (env QATOUCH_PROJECT_ID or DEFAULT_PROJECT_KEY) when absent.
        """
        if item is None:
            return None
        marker = item.get_closest_marker('qatouch_project')
        if marker and marker.args:
            return marker.args[0]
        return None

    def _resolve_project_key(self, item: Any) -> str:
        """Resolve project key for a given test item.

        Order: per-test marker > env QATOUCH_PROJECT_ID > DEFAULT_PROJECT_KEY.
        self.project_key already encodes env-vs-default, so we only check marker
        and fall back to self.project_key.
        """
        marker_project = self._get_marker_project_key(item)
        return marker_project or self.project_key

    @staticmethod
    def _resolve_page(item: Any):
        """Find the Playwright Page object on a test item.

        Tries (1) class-based tests' self.page, (2) fixture funcargs `page` and
        `authenticated_page`. Returns None if no live page is available - the
        screenshot step is best-effort and never raises.
        """
        instance = getattr(item, 'instance', None)
        if instance is not None:
            page = getattr(instance, 'page', None)
            if page is not None:
                return page
        funcargs = getattr(item, 'funcargs', {}) or {}
        return funcargs.get('page') or funcargs.get('authenticated_page')

    def _maybe_capture_screenshot(self, item: Any, report: Any) -> None:
        """Capture a PNG screenshot on test failure for QA Touch upload.

        Runs inside the makereport hookwrapper while fixtures are still alive.
        Stores raw bytes on the item; _record_result moves it to self.screenshots
        once the case_key is resolved.
        """
        if not self.capture_screenshots:
            return
        if report.outcome != 'failed':
            return
        page = self._resolve_page(item)
        if page is None:
            return
        try:
            # Viewport-only (not full_page) keeps payload size reasonable.
            png = page.screenshot()
            item._qatouch_screenshot = png
        except Exception as e:
            log.debug(f'QA Touch: failed to capture screenshot for {item.nodeid}: {e}')

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: Any, call: Any):
        outcome = yield
        report = outcome.get_result()

        # Only care about the 'call' phase (not setup/teardown)
        if report.when != 'call':
            # Handle skips in setup phase
            if report.when == 'setup' and report.skipped:
                self._record_result(item, item.nodeid, 'skipped',
                                    duration=getattr(report, 'duration', None))
            return

        self._maybe_capture_screenshot(item, report)
        self._record_result(item, item.nodeid, report.outcome,
                            duration=getattr(report, 'duration', None))

    def _record_result(self, item: Any, nodeid: str, outcome: str,
                       duration: float | None = None) -> None:
        """Map a pytest outcome to a QA Touch result.

        Resolution order:
          1. @pytest.mark.qatouch("KEY") marker on the test (authoritative)
          2. JSON mapping file fallback (legacy, for unmarked tests)
        """
        # Primary: read from marker
        case_key = self._get_marker_case_key(item) if item else None

        # Fallback: JSON mapping
        if not case_key:
            for variant in self._nodeid_variants(nodeid):
                if variant in self.mapping:
                    case_key = self.mapping[variant]
                    break

        # Always record the per-nodeid outcome - the post-run bug filer keys off
        # nodeid (not case_key), and unmapped failures still deserve a bug.
        existing_nodeid = self.nodeid_outcomes.get(nodeid)
        if existing_nodeid is None or _worse_outcome(outcome, existing_nodeid.get('outcome')):
            self.nodeid_outcomes[nodeid] = {
                'outcome': outcome,
                'duration': float(duration) if duration is not None else None,
                'case_key': case_key,
            }

        if not case_key:
            self.stats['unmapped'] += 1
            return

        status = PYTEST_TO_QT.get(outcome)
        if status is None:
            return

        # If already recorded (e.g., reruns), keep the worst result
        existing = self.results.get(case_key)
        if existing is not None:
            # Failed > Blocked > Passed (higher number = worse)
            status = max(existing, status)

        self.results[case_key] = status
        # Record per-test project resolution. If the same case_key is recorded
        # under two different projects (rerun with a different marker), keep the
        # last one - markers should be stable per case_key in practice.
        self.case_projects[case_key] = self._resolve_project_key(item)
        if duration is not None:
            # Keep the latest duration (most recent run wins on reruns)
            self.durations[case_key] = float(duration)
        screenshot = getattr(item, '_qatouch_screenshot', None) if item else None
        if screenshot:
            self.screenshots[case_key] = screenshot
            self.stats['screenshots'] += 1
        self.stats['mapped'] += 1

    def _upload_with_retry(self, upload_fn) -> bool:
        """Run an upload callable with retry logic. Returns True on success."""
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                upload_fn()
                if attempt > 1:
                    log.info(f'QA Touch: Upload succeeded on attempt {attempt}')
                    self.stats['retries'] += attempt - 1
                return True
            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                    log.warning(f'QA Touch: Upload attempt {attempt}/{MAX_RETRIES} failed: {e}. '
                                f'Retrying in {delay}s...')
                    self.stats['retries'] += 1
                    time.sleep(delay)
                else:
                    log.error(f'QA Touch: Upload failed after {MAX_RETRIES} attempts: {last_error}')
        return False

    def _save_failed_results(self, results_payload: list, comment: str, error: str) -> None:
        """Save failed upload results to JSON for later retry."""
        try:
            FAILURE_LOG_DIR.mkdir(parents=True, exist_ok=True)

            # Load existing failures (append, don't overwrite)
            existing = []
            if FAILURE_LOG_PATH.exists():
                try:
                    with open(FAILURE_LOG_PATH) as f:
                        existing = json.load(f)
                except (json.JSONDecodeError, ValueError):
                    existing = []

            failure_entry = {
                'timestamp': datetime.now(UTC).isoformat(),
                'project_key': self.project_key,
                'run_key': self.run_key,
                'result_count': len(results_payload),
                'results': results_payload,
                'comment': comment,
                'error': str(error),
            }
            existing.append(failure_entry)

            with open(FAILURE_LOG_PATH, 'w') as f:
                json.dump(existing, f, indent=2)

            self.stats['saved_for_retry'] = len(results_payload)
            log.info(f'QA Touch: Saved {len(results_payload)} results to '
                     f'{FAILURE_LOG_PATH} for later retry')
        except Exception as save_err:
            log.error(f'QA Touch: Failed to save results for retry: {save_err}')

    def _write_run_results(self) -> None:
        """Dump per-nodeid outcomes to last_run_results.json for run_suite.py.

        Written at session-finish regardless of upload success so the post-run
        bug filer can run even when QA Touch upload had errors. Includes both
        mapped and unmapped tests (unmapped tests will have case_key=None).
        """
        try:
            FAILURE_LOG_DIR.mkdir(parents=True, exist_ok=True)
            records = [
                {
                    'nodeid': nodeid,
                    'outcome': rec.get('outcome'),
                    'duration': rec.get('duration'),
                    'case_key': rec.get('case_key'),
                }
                for nodeid, rec in self.nodeid_outcomes.items()
            ]
            payload = {
                'timestamp': datetime.now(UTC).isoformat(),
                'run_key': self.run_key,
                'project_key': self.project_key,
                'env': os.environ.get('ENV', 'unknown'),
                'results': records,
            }
            with open(RUN_RESULTS_PATH, 'w') as f:
                json.dump(payload, f, indent=2)
            log.info(f'QA Touch: Wrote {len(records)} per-nodeid records to '
                     f'{RUN_RESULTS_PATH}')
        except Exception as e:
            log.warning(f'QA Touch: Failed to write run results JSON: {e}')

    def _group_results_by_project(self) -> dict[str, list[str]]:
        """Group recorded case_keys by their resolved project_key.

        Cases with no recorded project (legacy path / no marker) fall under
        self.project_key. Returns {project_key: [case_key, ...]}.
        """
        groups: dict[str, list[str]] = {}
        for case_key in self.results:
            pk = self.case_projects.get(case_key, self.project_key)
            groups.setdefault(pk, []).append(case_key)
        return groups

    def _build_payload(self, case_keys: list[str]) -> list[dict]:
        """Build the results payload for a subset of case_keys."""
        results_payload = []
        translated = 0
        for case_key in case_keys:
            status = self.results[case_key]
            upload_key = case_key
            if self.case_to_run_key:
                mapped_run_key = self.case_to_run_key.get(case_key)
                if mapped_run_key:
                    upload_key = mapped_run_key
                    translated += 1
            entry = {'case': upload_key, 'status': status}
            if self.use_playwright_endpoint:
                duration = self.durations.get(case_key)
                entry['execution_time'] = _format_duration(duration) if duration is not None else ''
                entry['comments'] = ''
                entry['description'] = ''
                attachments = []
                png = self.screenshots.get(case_key)
                if png:
                    attachments.append({
                        'name': f'{case_key}-failure.png',
                        'contentType': 'image/png',
                        'content': base64.b64encode(png).decode('ascii'),
                    })
                entry['attachments'] = attachments
            results_payload.append(entry)

        if translated > 0:
            log.info(
                f'QA Touch: Translated {translated} case_keys to run_keys '
                '(API-created run)')
        return results_payload

    def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
        """Upload collected results to QA Touch."""
        # Write per-nodeid results JSON for the post-run bug filer first - this
        # path must run even if there are no mapped uploads.
        self._write_run_results()

        if not self.results:
            log.info('QA Touch: No mapped results to upload.')
            return

        # Group cases by their resolved project key. Any project_key != the
        # reporter's default needs its own run_key - we don't have one, so we
        # log clearly and skip those uploads.
        project_groups = self._group_results_by_project()
        cross_project = [pk for pk in project_groups if pk != self.project_key]
        if cross_project:
            log.error(
                f'QA Touch: Cases target non-default projects {cross_project} '
                f'but no per-project run key is configured. Default project: '
                f'{self.project_key}, run: {self.run_key}. Skipping those cases.')
            for pk in cross_project:
                self.stats['errors'] += 1
                skipped = project_groups.pop(pk)
                log.error(
                    f'QA Touch: Skipped {len(skipped)} case(s) for project '
                    f'{pk}: {skipped}')

        # Now only self.project_key remains in groups (or empty).
        case_keys = project_groups.get(self.project_key, [])
        if not case_keys:
            log.info('QA Touch: No uploadable mapped results after project filtering.')
            return

        timestamp = datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')
        comment = f'Automated upload from Playwright run at {timestamp}'

        # Upload via the QA Touch client.
        try:
            from tools.qatouch_client import QATouchClient
            client = QATouchClient()
        except Exception as e:
            log.error(f'QA Touch: Failed to initialize client: {e}')
            self.stats['errors'] += 1
            return

        # Build run_key mapping for API-created runs
        try:
            self._build_run_key_mapping(client)
        except Exception as e:
            log.warning(f'QA Touch: run_key mapping failed (non-fatal): {e}')

        results_payload = self._build_payload(case_keys)

        endpoint_label = 'playwright' if self.use_playwright_endpoint else 'legacy'
        log.info(f'QA Touch: Uploading {len(results_payload)} results to run '
                 f'{self.run_key} via {endpoint_label} endpoint...')
        self._upload_path_used = endpoint_label

        # Pick the right uploader based on the opt-in env var
        if self.use_playwright_endpoint:
            def _do_upload():
                client.update_playwright_results(
                    project_key=self.project_key,
                    test_run_key=self.run_key,
                    results=results_payload,
                )
        else:
            def _do_upload():
                client.update_test_run_results(
                    project_key=self.project_key,
                    test_run_key=self.run_key,
                    results=results_payload,
                    comment=comment,
                )

        success = self._upload_with_retry(_do_upload)

        if success:
            self.stats['uploaded'] = len(results_payload)
            log.info(f'QA Touch: Successfully uploaded {len(results_payload)} results.')
        else:
            self.stats['errors'] += 1
            # Save to failure log for later retry
            self._save_failed_results(
                results_payload, comment,
                f'Failed after {MAX_RETRIES} attempts')

    def pytest_terminal_summary(self, terminalreporter: Any, exitstatus: int) -> None:
        """Print QA Touch upload summary in the terminal."""
        terminalreporter.write_sep('=', 'QA Touch Result Upload')
        terminalreporter.write_line(f'  Run key:    {self.run_key}')
        terminalreporter.write_line(f'  Project:    {self.project_key}')
        path_used = getattr(self, '_upload_path_used', '(none)')
        terminalreporter.write_line(f'  Upload path: {path_used}')
        terminalreporter.write_line(
            f'  Endpoint:   {"playwright (rich)" if self.use_playwright_endpoint else "legacy (status-only)"}')
        terminalreporter.write_line(f'  Mapped:     {self.stats["mapped"]} results')
        terminalreporter.write_line(f'  Unmapped:   {self.stats["unmapped"]} tests (no case mapping)')
        terminalreporter.write_line(f'  Uploaded:   {self.stats["uploaded"]} results')
        if self.stats.get('screenshots'):
            terminalreporter.write_line(
                f'  Screenshots: {self.stats["screenshots"]} captured on failure')
        if self.stats['retries']:
            terminalreporter.write_line(f'  Retries:    {self.stats["retries"]}')
        if self.stats['errors']:
            terminalreporter.write_line(f'  Errors:     {self.stats["errors"]}')
        if self.stats['saved_for_retry']:
            terminalreporter.write_line(
                f'  Saved:      {self.stats["saved_for_retry"]} results in '
                f'{FAILURE_LOG_PATH} (retry later)')

        # Breakdown by status
        passed = sum(1 for s in self.results.values() if s == STATUS_PASSED)
        failed = sum(1 for s in self.results.values() if s == STATUS_FAILED)
        blocked = sum(1 for s in self.results.values() if s == STATUS_BLOCKED)
        terminalreporter.write_line(f'  Passed:     {passed}')
        terminalreporter.write_line(f'  Failed:     {failed}')
        terminalreporter.write_line(f'  Blocked:    {blocked}')
