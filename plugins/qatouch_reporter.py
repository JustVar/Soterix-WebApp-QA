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

import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

log = logging.getLogger('qatouch_reporter')

ROOT = Path(__file__).resolve().parent.parent
MAPPING_PATH = ROOT / 'config' / 'qatouch_case_mapping.json'
FAILURE_LOG_DIR = ROOT / 'logs'
FAILURE_LOG_PATH = FAILURE_LOG_DIR / 'upload_failures.json'

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


class QATouchReporter:
    def __init__(self, run_key: str):
        self.run_key = run_key
        self.project_key = os.environ.get('QATOUCH_PROJECT_ID', 'JlW1')
        self.results: dict[str, int] = {}  # case_key -> status code
        self.mapping = self._load_mapping()
        self.case_to_run_key: dict[str, str] = {}  # case_key -> run_key (for API-created runs)
        self.stats = {'mapped': 0, 'unmapped': 0, 'uploaded': 0, 'errors': 0,
                      'retries': 0, 'saved_for_retry': 0}

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

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: Any, call: Any):
        outcome = yield
        report = outcome.get_result()

        # Only care about the 'call' phase (not setup/teardown)
        if report.when != 'call':
            # Handle skips in setup phase
            if report.when == 'setup' and report.skipped:
                self._record_result(item, item.nodeid, 'skipped')
            return

        self._record_result(item, item.nodeid, report.outcome)

    def _record_result(self, item: Any, nodeid: str, outcome: str) -> None:
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
        self.stats['mapped'] += 1

    def _upload_with_retry(self, client, results_payload: list, comment: str) -> bool:
        """Upload results with retry logic. Returns True on success."""
        last_error = None
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                client.update_test_run_results(
                    project_key=self.project_key,
                    test_run_key=self.run_key,
                    results=results_payload,
                    comment=comment,
                )
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
                'timestamp': datetime.now(timezone.utc).isoformat(),
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

    def pytest_sessionfinish(self, session: Any, exitstatus: int) -> None:
        """Upload collected results to QA Touch."""
        if not self.results:
            log.info('QA Touch: No mapped results to upload.')
            return

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

        # Build the results payload
        results_payload = []
        translated = 0
        for case_key, status in self.results.items():
            upload_key = case_key
            if self.case_to_run_key:
                mapped_run_key = self.case_to_run_key.get(case_key)
                if mapped_run_key:
                    upload_key = mapped_run_key
                    translated += 1
            results_payload.append({'case': upload_key, 'status': status})

        if translated > 0:
            log.info(f'QA Touch: Translated {translated} case_keys to run_keys (API-created run)')

        timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
        comment = f'Automated upload from Playwright run at {timestamp}'

        log.info(f'QA Touch: Uploading {len(results_payload)} results to run {self.run_key}...')

        # Upload with retry
        success = self._upload_with_retry(client, results_payload, comment)

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
        terminalreporter.write_line(f'  Mapped:     {self.stats["mapped"]} results')
        terminalreporter.write_line(f'  Unmapped:   {self.stats["unmapped"]} tests (no case mapping)')
        terminalreporter.write_line(f'  Uploaded:   {self.stats["uploaded"]} results')
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
