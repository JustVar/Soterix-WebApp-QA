"""Verification Runner - pytest plugin for step-by-step evidence capture.

When activated via --verify-mode, this plugin:
  1. Provides a `step_capture` fixture that captures screenshots between steps
  2. Loads step definitions from tests/steps/ JSON files
  3. Outputs evidence JSON files (one per test) to verification_output/
  4. Captures final screenshots on test pass/fail

Activation:
    pytest --verify-mode tests/ui/admin/test_admin_audit_trail.py

When --verify-mode is NOT active, `step_capture` is a no-op with zero overhead.

Evidence files are consumed by the QA Ops Hub verification page for
asynchronous review by QA testers.
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

log = logging.getLogger('verification_runner')

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / 'verification_output'
SCREENSHOTS_DIR = OUTPUT_DIR / 'screenshots'
MAPPING_PATH = ROOT / 'config' / 'qatouch_case_mapping.json'


# ---------------------------------------------------------------------------
# Plugin registration
# ---------------------------------------------------------------------------

def pytest_addoption(parser: Any) -> None:
    group = parser.getgroup('verification', 'Verification evidence capture')
    group.addoption(
        '--verify-mode',
        action='store_true',
        default=False,
        help='Enable step-by-step screenshot capture for verification.',
    )


@pytest.fixture(autouse=True)
def step_capture():
    """Fallback no-op step_capture fixture when --verify-mode is not active.

    Overridden by VerificationCollector.step_capture when --verify-mode is on.
    """
    return StepCapture(active=False)


def pytest_configure(config: Any) -> None:
    enabled = config.getoption('--verify-mode', default=False)
    if not enabled:
        return

    # Create output directories
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

    collector = VerificationCollector()
    config._verification_collector = collector
    config.pluginmanager.register(collector, 'verification_collector')


# ---------------------------------------------------------------------------
# StepCapture - fixture class
# ---------------------------------------------------------------------------

class StepCapture:
    """Per-test step capture helper.

    In verification mode: captures screenshots and timestamps at each step.
    When verification mode is OFF: all methods are no-ops (zero overhead).
    """

    def __init__(self, page=None, nodeid: str = '', active: bool = False):
        self._page = page
        self._nodeid = nodeid
        self._active = active
        self._steps: list[dict[str, Any]] = []
        self._start_time = time.time()
        self._case_key = ''

    def set_page(self, page) -> None:
        """Set the Playwright page (called by fixture setup)."""
        self._page = page

    def set_case_key(self, case_key: str) -> None:
        """Set the QA Touch case key for filename prefixes."""
        self._case_key = case_key

    def mark(self, step_num: int, description: str = '') -> None:
        """Record completion of a step with screenshot.

        Call this between test steps to capture evidence.
        No-op when --verify-mode is not active.

        Args:
            step_num: Step number (matches step definition JSON).
            description: Brief description (overrides JSON if provided).
        """
        if not self._active:
            return

        screenshot_path = self._take_screenshot(step_num)

        self._steps.append({
            'step': step_num,
            'description': description,
            'screenshot': str(screenshot_path) if screenshot_path else None,
            'timestamp': time.time(),
            'result': 'passed',  # Updated to 'failed' if test fails after this step
        })

    def _take_screenshot(self, step_num: int) -> Path | None:
        """Capture a screenshot for a step."""
        if not self._page:
            return None

        try:
            prefix = self._case_key or self._safe_filename()
            filename = f'{prefix}_step{step_num}.png'
            path = SCREENSHOTS_DIR / filename
            self._page.screenshot(path=str(path), full_page=False)
            return path.relative_to(ROOT)
        except Exception as e:
            log.warning('Screenshot failed for step %d: %s', step_num, e)
            return None

    def _safe_filename(self) -> str:
        """Generate a safe filename from the nodeid."""
        safe = self._nodeid.replace('::', '_').replace('/', '_').replace('\\', '_')
        safe = safe.replace('[', '_').replace(']', '')
        # Truncate to reasonable length
        if len(safe) > 80:
            safe = safe[:80]
        return safe

    def finalize(self, outcome: str) -> dict[str, Any]:
        """Build the evidence dict for this test.

        Args:
            outcome: 'passed', 'failed', or 'skipped'

        Returns:
            Evidence dict ready for JSON serialization.
        """
        duration = time.time() - self._start_time

        # Mark the last completed step as failed if the test failed
        if outcome == 'failed' and self._steps:
            self._steps[-1]['result'] = 'failed'

        return {
            'nodeid': self._nodeid,
            'case_key': self._case_key,
            'result': outcome,
            'duration_seconds': round(duration, 2),
            'captured_at': datetime.now(timezone.utc).isoformat(),
            'total_steps_defined': len(self._steps),
            'steps': self._steps,
        }


# ---------------------------------------------------------------------------
# VerificationCollector - hooks for evidence output
# ---------------------------------------------------------------------------

class VerificationCollector:
    """Pytest plugin that manages StepCapture instances and writes evidence."""

    def __init__(self):
        self._captures: dict[str, StepCapture] = {}  # nodeid -> StepCapture
        self._mapping: dict[str, str] = {}  # nodeid -> case_key
        self._load_mapping()
        self.stats = {
            'total': 0,
            'with_steps': 0,
            'evidence_files': 0,
        }

    def _load_mapping(self) -> None:
        """Load nodeid -> case_key mapping for evidence files."""
        if not MAPPING_PATH.exists():
            return
        try:
            with open(MAPPING_PATH) as f:
                data = json.load(f)
            mappings = data.get('mappings', {})
            self._mapping = {nid: info['case_key'] for nid, info in mappings.items()}
        except Exception as e:
            log.warning('Failed to load case mapping: %s', e)

    def _resolve_case_key(self, nodeid: str) -> str:
        """Resolve a nodeid to a QA Touch case_key."""
        # Try exact match first
        if nodeid in self._mapping:
            return self._mapping[nodeid]
        # Strip browser param
        base = nodeid.split('[')[0] if '[' in nodeid else nodeid
        return self._mapping.get(base, '')

    @pytest.fixture(autouse=True)
    def step_capture(self, request) -> StepCapture:
        """Auto-injected fixture providing step capture.

        When --verify-mode is active, creates a live StepCapture.
        Otherwise returns a no-op StepCapture (zero overhead).
        """
        nodeid = request.node.nodeid
        active = request.config.getoption('--verify-mode', default=False)

        capture = StepCapture(
            nodeid=nodeid,
            active=active,
        )

        if active:
            case_key = self._resolve_case_key(nodeid)
            capture.set_case_key(case_key)

            # Try to get the page from the test instance (set by test's setup fixture)
            # The test must call step_capture.set_page(self.page) in setup,
            # or we'll try to discover it from fixtures
            self._captures[nodeid] = capture

        yield capture

        if active:
            self._captures.pop(nodeid, None)

    @pytest.hookimpl(hookwrapper=True)
    def pytest_runtest_makereport(self, item: Any, call: Any):
        outcome = yield
        report = outcome.get_result()

        # Only process the 'call' phase (not setup/teardown)
        if report.when != 'call':
            return

        nodeid = item.nodeid
        capture = self._captures.get(nodeid)
        if not capture or not capture._active:
            return

        self.stats['total'] += 1

        # Take a final screenshot on failure
        if report.failed and capture._page:
            try:
                prefix = capture._case_key or capture._safe_filename()
                path = SCREENSHOTS_DIR / f'{prefix}_FAILED.png'
                capture._page.screenshot(path=str(path), full_page=False)
            except Exception:
                pass

        # Build evidence and write to file
        evidence = capture.finalize(report.outcome)

        if evidence['steps']:
            self.stats['with_steps'] += 1

        # Write evidence JSON
        safe_name = capture._safe_filename()
        evidence_path = OUTPUT_DIR / f'{safe_name}.json'
        try:
            with open(evidence_path, 'w', encoding='utf-8') as f:
                json.dump(evidence, f, indent=2, ensure_ascii=False)
                f.write('\n')
            self.stats['evidence_files'] += 1
        except Exception as e:
            log.error('Failed to write evidence for %s: %s', nodeid, e)

    def pytest_terminal_summary(self, terminalreporter: Any, exitstatus: int) -> None:
        """Print verification summary."""
        if not self.stats['total']:
            return

        terminalreporter.write_sep('=', 'Verification Evidence Capture')
        terminalreporter.write_line(f'  Tests captured:    {self.stats["total"]}')
        terminalreporter.write_line(f'  With step marks:   {self.stats["with_steps"]}')
        terminalreporter.write_line(f'  Evidence files:    {self.stats["evidence_files"]}')
        terminalreporter.write_line(f'  Output directory:  {OUTPUT_DIR}')
