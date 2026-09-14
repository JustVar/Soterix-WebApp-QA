"""
Smart Jira Bug Creator

Implements multi-gate validation to avoid filing bugs for flaky tests.
By default, bugs that pass the confidence threshold are queued for manual
QA review before being filed in Jira.

Features:
- Confidence scoring based on failure history and consecutive failures
- Environment health checks (basic base_url probe)
- Manual QA approval gate (review queue with interactive CLI)
- All 8 NC mandatory Bug fields auto-populated via config/jira_field_mapping.py

Configuration constants:
- CONFIDENCE_THRESHOLD: float (0-1)
- MIN_CONSECUTIVE_FAILURES: int

Usage:
  python -m tools.smart_jira_bug_creator --test <nodeid>               # Queue for review
  python -m tools.smart_jira_bug_creator --test <nodeid> --auto-create # Bypass review (CI)
  python -m tools.smart_jira_bug_creator --list                        # View pending bugs
  python -m tools.smart_jira_bug_creator --review                      # Approve/reject bugs

This module is intentionally conservative and contains no live Jira calls by default.
Set BUG_CREATION_ENABLED=true in .env to enable live Jira issue creation.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

try:
    import requests
except Exception:
    requests = None
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    load_dotenv = None
try:
    from jira import JIRA
except Exception:
    JIRA = None

try:
    from config.jira_field_mapping import mapper as qa_touch_mapper
except Exception:
    qa_touch_mapper = None

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FLAKY_DB = os.path.join(ROOT, "flaky_tests.json")
REVIEW_QUEUE = os.path.join(ROOT, "tools", "review_queue.json")

CONFIDENCE_THRESHOLD = 0.7
MIN_CONSECUTIVE_FAILURES = 2


def load_flaky_db(path: str = FLAKY_DB) -> dict[str, Any]:
    if not os.path.exists(path):
        return {"metadata": {}, "tests": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_flaky_db(db: dict[str, Any], path: str = FLAKY_DB) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, sort_keys=True)


def get_history(nodeid: str, db: dict[str, Any]) -> list[dict[str, Any]]:
    entry = db.get("tests", {}).get(nodeid, {})
    return entry.get("last_runs", [])


def calc_failure_rate(history: list[dict[str, Any]]) -> float:
    if not history:
        return 0.0
    fails = sum(1 for r in history if r.get("result") == "fail")
    return fails / len(history)


def consecutive_failures(history: list[dict[str, Any]]) -> int:
    count = 0
    for r in reversed(history):
        if r.get("result") == "fail":
            count += 1
        else:
            break
    return count


def env_health_check(base_url: str, timeout: int = 5) -> tuple[bool, str]:
    """Simple environment health check: probe base_url root.

    Returns (healthy: bool, message: str)
    """
    if not base_url:
        return False, "no base_url provided"
    try:
        if requests:
            resp = requests.get(base_url, timeout=timeout)
            if resp.status_code >= 200 and resp.status_code < 500:
                return True, f"status:{resp.status_code}"
            return False, f"status:{resp.status_code}"
        # fallback: attempt a minimal urllib request
        from urllib.request import urlopen

        with urlopen(base_url, timeout=timeout):
            return True, "status:ok"
    except Exception as e:
        return False, str(e)


def compute_confidence(history: list[dict[str, Any]], env_ok: bool) -> float:
    """Heuristic score between 0..1 indicating likelihood of real bug.

    Combines failure rate and consecutive failures. If environment is unhealthy,
    reduce score.
    """
    if not history:
        return 0.0
    failure_rate = calc_failure_rate(history)
    consecutive = consecutive_failures(history)
    # base is failure_rate
    score = failure_rate
    # boost for consecutive failures (diminishing returns)
    score += 0.2 * (consecutive / (consecutive + 2))
    # cap
    if score > 1.0:
        score = 1.0
    # if env unhealthy, downweight confidence
    if not env_ok:
        score *= 0.5
    return round(score, 3)


class JiraClient:
    """Creates a Jira issue, or describes the one it would create.

    Duplicated in soterix-qa-shared (soterix_qa_shared/jira/client.py). At
    migration step 6 this class becomes an import from there and the
    duplication ends. Until then: change both, or neither.

    The package version is the same behaviour with the same two fixes,
    factored into helpers and covered by 29 tests.
    """

    def __init__(self, server: str | None = None, user: str | None = None, token: str | None = None):
        self.server = server or os.environ.get('JIRA_URL')
        self.user = user or os.environ.get('JIRA_EMAIL')
        self.token = token or os.environ.get('JIRA_API_TOKEN')

    def create_issue(self, summary: str, description: str, labels: list[str] | None = None, project_key: str | None = None, issue_type: str = 'Bug', attachments: list[str] | None = None, story_link: str | None = None, qa_touch_data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Create a Jira issue using `jira` library if available and BUG_CREATION_ENABLED true.

        Args:
            qa_touch_data: Optional dict with QA Touch test case data for auto-populating
                NC mandatory Bug fields. Keys: module, steps, expected, actual,
                environment, severity, build, title, test_case_id.

        Returns the issue dict on success.
        """
        enabled = os.environ.get('BUG_CREATION_ENABLED', 'false').lower() in ('1', 'true', 'yes')
        project_key = project_key or os.environ.get('JIRA_PROJECT_KEY')
        if not enabled or JIRA is None:
            LOG.info("[JIRA] Disabled or client missing; would create: %s", summary)
            fake = {
                "key": "AUTO-0001",
                "summary": summary,
                "description": description,
                "labels": (labels or []) + (["automation-test-DELETE-ME"] if "[TEST]" in summary else []),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            if qa_touch_data and qa_touch_mapper:
                fake["mapped_fields"] = qa_touch_mapper.map_bug_fields(**qa_touch_data)
                unmapped = qa_touch_mapper.get_unmapped_required_fields("Bug", fake["mapped_fields"])
                if unmapped:
                    LOG.info("[JIRA] Unmapped required fields: %s", unmapped)
                    fake["unmapped_required_fields"] = unmapped
            return fake

        # create real issue
        options = {'server': self.server}
        jira = JIRA(options, basic_auth=(self.user, self.token))
        fields = {
            'project': {'key': project_key},
            'summary': summary,
            'description': description,
            'issuetype': {'name': issue_type},
        }
        # The delete-me marker rides on the CREATE, not only on the update
        # below. The update is inside a try/except that logs and continues,
        # so when it fails a test bug lands in NC's backlog with nothing
        # saying it is disposable. Same shape as the package's client.
        issue_labels = list(labels or [])
        if "[TEST]" in summary and 'automation-test-DELETE-ME' not in issue_labels:
            issue_labels.append('automation-test-DELETE-ME')
        if issue_labels:
            fields['labels'] = issue_labels

        # Auto-populate NC mandatory Bug fields from QA Touch data
        if qa_touch_data and qa_touch_mapper and issue_type == 'Bug':
            mapped = qa_touch_mapper.map_bug_fields(**qa_touch_data)
            fields.update(mapped)
            unmapped = qa_touch_mapper.get_unmapped_required_fields("Bug", mapped)
            if unmapped:
                LOG.warning("[JIRA] These required fields were not auto-populated: %s", unmapped)

        issue = jira.create_issue(fields=fields)
        issue_key = issue.key

        # Attach files if present
        if attachments:
            for path in attachments:
                try:
                    if os.path.exists(path):
                        jira.add_attachment(issue=issue_key, attachment=path)
                except Exception as e:
                    LOG.warning('Failed to attach %s: %s', path, e)

        # Link to story if provided (best effort: a comment naming it).
        if story_link:
            try:
                jira.add_comment(issue, f'Related story: {story_link}')
            except Exception:
                LOG.warning('Failed to link story %s to %s', story_link, issue_key)

        # A test issue gets a delete-me label and an admin comment, so
        # it is not mistaken for a real bug in somebody's backlog. Keep
        # this OUTSIDE `if story_link:` - inside it, a no-story create
        # returned None while the issue existed, and re-approval filed
        # a duplicate.
        if "[TEST]" in summary:
            try:
                jira.add_comment(issue, "Admin: Please delete this test bug")
            except Exception:
                LOG.warning('Failed to add admin deletion comment to %s', issue_key)
            try:
                current = list(getattr(issue.fields, 'labels', []) or [])
                if 'automation-test-DELETE-ME' not in current:
                    current.append('automation-test-DELETE-ME')
                    issue.update(fields={'labels': current})
            except Exception:
                LOG.warning('Failed to add label to %s', issue_key)

        return {'key': issue_key, 'self': getattr(issue, 'self', None)}


VALID_SEVERITIES = ["Critical", "High", "Medium", "Low"]

# Map test directory keywords to Jira Module values
_MODULE_MAP = {
    "views": "Views",
    "events": "Events",
    "maps": "Maps",
    "insights": "Insights",
    "media": "Media",
    "search": "Search",
    "lpr": "LPR",
    "admin": "Admin",
    "partner_admin": "Partner Admin Tool",
    "event_wall": "Event Wall",
    "login": "Other",
    "api": "Other",
}


def _infer_module_from_nodeid(nodeid: str) -> str:
    """The NC Module a test belongs to, from its file path.

    The path first, and only then the rest of the node id. Matching the
    WHOLE node id let a test's own name outrank the file it lives in:
    measured across 819 collected UI tests, 29 were filed under the wrong
    module, including test_admin_users.py::test_search_user going to Search
    rather than Admin. Module is a required NC field, so a wrong value is
    not a blank to be filled in later - it routes the bug to another team.

    The function name is still a fallback. When the path carries no keyword
    at all, "the test searches something" beats "Other".
    """
    path = nodeid.split("::", 1)[0].lower()
    for keyword, module_name in _MODULE_MAP.items():
        if keyword in path:
            return module_name
    rest = nodeid.lower()
    for keyword, module_name in _MODULE_MAP.items():
        if keyword in rest:
            return module_name
    return "Other"


def _infer_environment(base_url: str) -> str:
    """Infer Jira Environment Found value from base URL."""
    if not base_url:
        return "QA"
    url_lower = base_url.lower()
    if "staging" in url_lower or "stage" in url_lower:
        return "Staging"
    if "prod" in url_lower:
        return "Production"
    if "dev" in url_lower:
        return "Dev"
    return "QA"


def _load_review_queue(queue_path: str = REVIEW_QUEUE) -> dict[str, Any]:
    """Load and return the review queue, or empty structure."""
    if not os.path.exists(queue_path):
        return {"metadata": {"next_id": 1}, "items": []}
    try:
        with open(queue_path, encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("metadata", {"next_id": 1})
        data.setdefault("items", [])
        return data
    except Exception:
        return {"metadata": {"next_id": 1}, "items": []}


def _save_review_queue(queue: dict[str, Any], queue_path: str = REVIEW_QUEUE) -> None:
    """Persist the review queue to disk."""
    os.makedirs(os.path.dirname(queue_path), exist_ok=True)
    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)


def _try_api_queue(payload: dict[str, Any]) -> str | None:
    """Try to submit an item via the QA Ops Hub API. Returns entry_id or None."""
    api_url = os.environ.get("QA_OPS_API_URL", "").rstrip("/")
    api_key = os.environ.get("QA_OPS_API_KEY", "")
    if not api_url or not api_key or not requests:
        return None
    try:
        resp = requests.post(
            f"{api_url}/api/queue",
            json=payload,
            headers={"X-API-Key": api_key},
            timeout=5,
        )
        if resp.status_code == 201:
            entry_id = resp.json().get("entry_id")
            LOG.info("Queued via API: %s", entry_id)
            return entry_id
        LOG.warning("API queue returned %d: %s", resp.status_code, resp.text[:200])
    except Exception as exc:
        LOG.warning("API queue unavailable, falling back to JSON: %s", exc)
    return None


def add_to_review_queue(nodeid: str, reason: str, queue_path: str = REVIEW_QUEUE,
                        bug_data: dict[str, Any] | None = None, score: float | None = None,
                        consecutive: int | None = None, failure_rate: float | None = None) -> str:
    """Add an item to the review queue with optional enriched bug data.

    Tries the QA Ops Hub API first (if QA_OPS_API_URL and QA_OPS_API_KEY are set).
    Falls back to local JSON file if the API is unreachable.

    Returns the entry ID (e.g. 'RQ-0001').
    """
    # Build API payload
    payload: dict[str, Any] = {"nodeid": nodeid, "reason": reason}
    if score is not None:
        payload["confidence_score"] = score
    if consecutive is not None:
        payload["consecutive_failures"] = consecutive
    if failure_rate is not None:
        payload["failure_rate"] = failure_rate
    if bug_data:
        payload["bug_data"] = bug_data

    # Try API first
    api_entry_id = _try_api_queue(payload)
    if api_entry_id:
        return api_entry_id

    # Fallback: write to local JSON
    queue = _load_review_queue(queue_path)

    next_id = queue["metadata"].get("next_id", 1)
    entry_id = f"RQ-{next_id:04d}"
    queue["metadata"]["next_id"] = next_id + 1

    entry = {
        "id": entry_id,
        "nodeid": nodeid,
        "reason": reason,
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "status": "pending",
    }
    if score is not None:
        entry["confidence_score"] = score
    if consecutive is not None:
        entry["consecutive_failures"] = consecutive
    if failure_rate is not None:
        entry["failure_rate"] = failure_rate
    if bug_data:
        entry["bug_data"] = bug_data
    entry["reviewed_by"] = None
    entry["reviewed_at"] = None
    entry["jira_key"] = None

    queue["items"].append(entry)
    _save_review_queue(queue, queue_path)
    LOG.info("Added %s (%s) to review queue (JSON fallback: %s)", entry_id, nodeid, queue_path)
    return entry_id


def list_pending_bugs(queue_path: str = REVIEW_QUEUE) -> list[dict[str, Any]]:
    """Print and return pending review queue items."""
    queue = _load_review_queue(queue_path)
    pending = [item for item in queue.get("items", []) if item.get("status") == "pending"]

    if not pending:
        print("No pending bugs in the review queue.")
        return []

    print("")
    print("=" * 78)
    plural = "s" if len(pending) != 1 else ""
    print(f"  PENDING BUG REVIEW QUEUE  ({len(pending)} item{plural})")
    print("=" * 78)
    print("")
    for i, item in enumerate(pending, 1):
        entry_id = item.get("id", "?")
        nodeid = item.get("nodeid", "?")
        ts = item.get("ts", "?")
        score = item.get("confidence_score", "n/a")
        consec = item.get("consecutive_failures", "n/a")
        bug_data = item.get("bug_data") or {}
        severity = bug_data.get("severity", "n/a")
        module = bug_data.get("module", "n/a")
        has_data = "Yes" if bug_data else "No"

        print(f"  [{i}] {entry_id}")
        print(f"      Test:       {nodeid}")
        print(f"      Module:     {module}")
        print(f"      Severity:   {severity}")
        print(f"      Confidence: {score}  |  Consecutive: {consec}")
        print(f"      Queued:     {ts}")
        print(f"      Bug data:   {has_data}")
        print("      " + "-" * 50)

    print("")
    return pending


def review_pending_bugs(queue_path: str = REVIEW_QUEUE) -> dict[str, Any]:
    """Interactive review of pending bugs. Returns summary dict."""
    queue = _load_review_queue(queue_path)
    pending = [item for item in queue.get("items", [])
               if item.get("status") == "pending" and item.get("bug_data")]

    if not pending:
        print("No pending bugs with full data to review.")
        smoke_only = [item for item in queue.get("items", [])
                      if item.get("status") == "pending" and not item.get("bug_data")]
        if smoke_only:
            print(f"({len(smoke_only)} smoke-test entries without bug data -- see --list or email report)")
        return {"approved": 0, "rejected": 0, "skipped": 0}

    approved = 0
    rejected = 0
    skipped = 0
    jira = JiraClient()

    for idx, item in enumerate(pending):
        entry_id = item.get("id", "?")
        nodeid = item.get("nodeid", "?")
        bug_data = item.get("bug_data", {})

        print("")
        print("=" * 78)
        print(f"  REVIEW: {entry_id}  ({idx + 1} of {len(pending)})")
        print("=" * 78)
        print("")
        print(f"  Test ID:      {nodeid}")
        print("  Module:       {}".format(bug_data.get("module", "n/a")))
        print("  Summary:      {}".format(bug_data.get("summary", "n/a")))
        print("  Environment:  {}".format(bug_data.get("environment", "n/a")))
        print("  Severity:     {}".format(bug_data.get("severity", "n/a")))
        print("  Confidence:   {}".format(item.get("confidence_score", "n/a")))
        print("  Consecutive:  {} failures".format(item.get("consecutive_failures", "n/a")))
        print("  Failure Rate: {}".format(item.get("failure_rate", "n/a")))
        print("")
        print("  Steps to Reproduce:")
        for line in bug_data.get("steps", "n/a").split("\n"):
            print(f"    {line}")
        print("")
        print("  Expected: {}".format(bug_data.get("expected", "n/a")))
        print("  Actual:   {}".format(bug_data.get("actual", "n/a")))
        print("")

        print("  Actions: [a]pprove  [r]eject  [e]dit severity  [s]kip  [q]uit")
        print("")

        while True:
            try:
                choice = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\n  Review session ended.")
                _save_review_queue(queue, queue_path)
                return {"approved": approved, "rejected": rejected, "skipped": skipped}

            if choice in ("a", "approve"):
                print("  Creating Jira bug...")
                desc = (
                    "Automated detection:\n"
                    "nodeid: {}\n"
                    "confidence: {}\n"
                    "consecutive_failures: {}\n"
                    "failure_rate: {}\n".format(nodeid, item.get("confidence_score", "n/a"),
                       item.get("consecutive_failures", "n/a"),
                       item.get("failure_rate", "n/a"))
                )
                try:
                    issue = jira.create_issue(
                        summary=bug_data.get("summary", nodeid),
                        description=desc,
                        labels=bug_data.get("labels", ["automation"]),
                        qa_touch_data={
                            "module": bug_data.get("module", "Other"),
                            "steps": bug_data.get("steps", ""),
                            "expected": bug_data.get("expected", ""),
                            "actual": bug_data.get("actual", ""),
                            "environment": bug_data.get("environment", "QA"),
                            "severity": bug_data.get("severity", "Medium"),
                            "build": bug_data.get("build", ""),
                            "title": bug_data.get("summary", ""),
                        }
                    )
                    issue_key = issue.get("key", "???")
                    item["status"] = "approved"
                    item["jira_key"] = issue_key
                    item["reviewed_by"] = os.environ.get("USERNAME", os.environ.get("USER", "qa"))
                    item["reviewed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    _save_review_queue(queue, queue_path)
                    print(f"  APPROVED -- Jira issue: {issue_key}")
                    approved += 1
                except Exception as e:
                    print(f"  ERROR creating Jira issue: {e}")
                    print("  Item remains pending. Try again later.")
                break

            if choice in ("r", "reject"):
                item["status"] = "rejected"
                item["reviewed_by"] = os.environ.get("USERNAME", os.environ.get("USER", "qa"))
                item["reviewed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                _save_review_queue(queue, queue_path)
                print("  REJECTED -- removed from pending queue.")
                rejected += 1
                break

            if choice in ("e", "edit"):
                print("  Current severity: {}".format(bug_data.get("severity", "n/a")))
                print("  Valid options: {}".format(", ".join(VALID_SEVERITIES)))
                try:
                    new_sev = input("  New severity: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n  Edit cancelled.")
                    continue
                if new_sev in VALID_SEVERITIES:
                    bug_data["severity"] = new_sev
                    _save_review_queue(queue, queue_path)
                    print(f"  Severity updated to: {new_sev}")
                    print("  Now choose: [a]pprove  [r]eject  [s]kip")
                else:
                    print("  Invalid severity. Must be one of: {}".format(", ".join(VALID_SEVERITIES)))

            elif choice in ("s", "skip"):
                print("  SKIPPED -- remains pending.")
                skipped += 1
                break

            elif choice in ("q", "quit"):
                print("  Review session ended.")
                _save_review_queue(queue, queue_path)
                return {"approved": approved, "rejected": rejected, "skipped": skipped}

            else:
                print("  Unknown choice. Use: a, r, e, s, or q")

    _save_review_queue(queue, queue_path)
    print("")
    print("=" * 78)
    print(f"  Review complete: {approved} approved, {rejected} rejected, {skipped} skipped")
    print("=" * 78)
    return {"approved": approved, "rejected": rejected, "skipped": skipped}


def multi_gate_validation(nodeid: str, env_base_url: str | None = None, is_smoke: bool = False, auto_create: bool = False) -> dict[str, Any]:
    """Run gates and decide whether to queue a bug for review or create it directly.

    By default (auto_create=False), bugs that pass the confidence threshold are
    queued for manual QA review. Pass auto_create=True to bypass the queue
    (for CI pipelines).

    Returns dict with keys: action: one of [no_action, queued, create_issue], details: {...}
    """
    db = load_flaky_db()
    history = get_history(nodeid, db)

    env_ok, env_msg = env_health_check(env_base_url) if env_base_url else (True, "no-check")
    score = compute_confidence(history, env_ok)
    consec = consecutive_failures(history)
    fail_rate = calc_failure_rate(history)

    details = {
        "nodeid": nodeid,
        "env_ok": env_ok,
        "env_msg": env_msg,
        "score": score,
        "consecutive_failures": consec,
        "failure_rate": fail_rate,
        "history_len": len(history),
    }

    # Gate 1: environment health
    if not env_ok:
        details["reason"] = f"Environment unhealthy: {env_msg}"
        return {"action": "no_action", "details": details}

    # Gate 2: smoke tests require manual review on first failure
    if is_smoke:
        prior_fails = sum(1 for r in history if r.get("result") == "fail")
        if prior_fails == 0:
            add_to_review_queue(nodeid, "First smoke test failure -- manual review required")
            details["reason"] = "first_smoke_failure"
            return {"action": "queued", "details": details}

    # Gate 3: consecutive failures + confidence threshold
    if consec >= MIN_CONSECUTIVE_FAILURES and score >= CONFIDENCE_THRESHOLD:
        module = _infer_module_from_nodeid(nodeid)
        environment = _infer_environment(env_base_url)
        summary = "[Auto] {} failing in {}".format(nodeid.split("::")[-1], env_base_url or "env")
        bug_data = {
            "summary": summary,
            "module": module,
            "steps": f"1. Run test: {nodeid}\n2. Test fails consistently",
            "expected": "Test should pass",
            "actual": f"Test has failed {consec} consecutive times (confidence: {score})",
            "environment": environment,
            "severity": "Medium",
            "build": "",
            "labels": ["automation", "auto-detected"],
            "env_base_url": env_base_url or "",
        }

        if auto_create:
            # CI mode: create immediately, no review
            jira = JiraClient()
            desc = (
                "Automated detection:\n"
                f"nodeid: {nodeid}\nconfidence: {score}\n"
                f"consecutive_failures: {consec}\nfailure_rate: {fail_rate}\n"
                f"env_check: {env_msg}\n"
            )
            issue = jira.create_issue(
                summary, desc,
                labels=bug_data["labels"],
                qa_touch_data={
                    "module": module,
                    "steps": bug_data["steps"],
                    "expected": bug_data["expected"],
                    "actual": bug_data["actual"],
                    "environment": environment,
                    "severity": bug_data["severity"],
                    "build": bug_data["build"],
                    "title": summary,
                }
            )
            details["issue"] = issue
            return {"action": "create_issue", "details": details}
        # Default: queue for manual QA review
        entry_id = add_to_review_queue(
            nodeid, "Meets confidence threshold for bug creation",
            bug_data=bug_data, score=score,
            consecutive=consec, failure_rate=fail_rate,
        )
        details["reason"] = "queued_for_review"
        details["entry_id"] = entry_id
        return {"action": "queued", "details": details}

    # Default: do not file
    details["reason"] = "Insufficient evidence (confidence/consecutive)"
    return {"action": "no_action", "details": details}


def main_cli():
    import argparse

    parser = argparse.ArgumentParser(description="Smart Jira Bug Creator")

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--test", help="pytest nodeid of the failed test")
    group.add_argument("--review", action="store_true",
                       help="Interactively review and approve/reject pending bugs")
    group.add_argument("--list", action="store_true",
                       help="List all pending bugs in the review queue")

    parser.add_argument("--env-base-url", required=False,
                        help="Base URL of the environment to check (used with --test)")
    parser.add_argument("--smoke", action="store_true",
                        help="Mark as smoke test (requires manual review on first fail)")
    parser.add_argument("--auto-create", action="store_true",
                        help="Bypass review queue and create bugs immediately (CI mode)")

    args = parser.parse_args()

    if args.list:
        list_pending_bugs()
    elif args.review:
        summary = review_pending_bugs()
        print(json.dumps(summary, indent=2))
    else:
        result = multi_gate_validation(
            args.test, env_base_url=args.env_base_url,
            is_smoke=args.smoke, auto_create=args.auto_create,
        )
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main_cli()
