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
import os
import time
import logging
from typing import Dict, Any, List, Tuple

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
CASE_MAPPING = os.path.join(ROOT, "config", "qatouch_case_mapping.json")

# QA Touch case URL - fed into Jira "remote link" so QA Touch's JIRA App 2.0
# RTM panel can resolve the linkage back to the originating test case.
QATOUCH_DOMAIN = os.environ.get("QATOUCH_DOMAIN", "soterixsystems")
QATOUCH_CASE_URL_TMPL = f"https://{QATOUCH_DOMAIN}.qatouch.com/index.php/cases/view/{{key}}"

CONFIDENCE_THRESHOLD = 0.7
MIN_CONSECUTIVE_FAILURES = 2


def _lookup_qatouch_case(nodeid: str) -> str | None:
    """Resolve a pytest nodeid to its QA Touch case_key via the mapping file.
    Returns None if the file is missing or the nodeid is unmapped."""
    if not nodeid or not os.path.exists(CASE_MAPPING):
        return None
    try:
        with open(CASE_MAPPING, "r", encoding="utf-8") as f:
            mappings = json.load(f).get("mappings", {})
    except Exception:
        return None
    entry = mappings.get(nodeid)
    if not entry and "[" in nodeid:
        entry = mappings.get(nodeid.split("[", 1)[0])
    return entry.get("case_key") if entry else None


def load_flaky_db(path: str = FLAKY_DB) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {"metadata": {}, "tests": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_flaky_db(db: Dict[str, Any], path: str = FLAKY_DB) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=2, sort_keys=True)


def get_history(nodeid: str, db: Dict[str, Any]) -> List[Dict[str, Any]]:
    entry = db.get("tests", {}).get(nodeid, {})
    return entry.get("last_runs", [])


def calc_failure_rate(history: List[Dict[str, Any]]) -> float:
    if not history:
        return 0.0
    fails = sum(1 for r in history if r.get("result") == "fail")
    return fails / len(history)


def consecutive_failures(history: List[Dict[str, Any]]) -> int:
    count = 0
    for r in reversed(history):
        if r.get("result") == "fail":
            count += 1
        else:
            break
    return count


def env_health_check(base_url: str, timeout: int = 5) -> Tuple[bool, str]:
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
        else:
            # fallback: attempt a minimal urllib request
            from urllib.request import urlopen

            with urlopen(base_url, timeout=timeout) as r:
                return True, f"status:ok"
    except Exception as e:
        return False, str(e)


def compute_confidence(history: List[Dict[str, Any]], env_ok: bool) -> float:
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
    """Placeholder Jira client. Replace create_issue() with real API integration."""

    def __init__(self, server: str = None, user: str = None, token: str = None):
        self.server = server or os.environ.get('JIRA_URL')
        self.user = user or os.environ.get('JIRA_EMAIL')
        self.token = token or os.environ.get('JIRA_API_TOKEN')

    def create_issue(self, summary: str, description: str, labels: List[str] = None, project_key: str = None, issue_type: str = 'Bug', attachments: List[str] = None, story_link: str = None, qa_touch_data: Dict[str, Any] = None, qatouch_case_key: str = None) -> Dict[str, Any]:
        """Create a Jira issue using `jira` library if available and BUG_CREATION_ENABLED true.

        Args:
            qa_touch_data: Optional dict with QA Touch test case data for auto-populating
                NC mandatory Bug fields. Keys: module, steps, expected, actual,
                environment, severity, build, title, test_case_id.
            qatouch_case_key: Optional QA Touch case key for RTM linkage. When set,
                a `qatouch-<key>` label is added and (real path only) a remote link to
                the QA Touch case is attached after creation - covers both label-scan
                and remote-link-scan strategies in QA Touch's JIRA App 2.0.

        Returns the issue dict on success.
        """
        # Build the final labels list (defensive copy + RTM linkage label)
        final_labels = list(labels) if labels else []
        if qatouch_case_key and f"qatouch-{qatouch_case_key}" not in final_labels:
            final_labels.append(f"qatouch-{qatouch_case_key}")

        enabled = os.environ.get('BUG_CREATION_ENABLED', 'false').lower() in ('1', 'true', 'yes')
        project_key = project_key or os.environ.get('JIRA_PROJECT_KEY')
        if not enabled or JIRA is None:
            LOG.info("[JIRA] Disabled or client missing; would create: %s", summary)
            fake = {
                "key": "AUTO-0001",
                "summary": summary,
                "description": description,
                "labels": final_labels + (["automation-test-DELETE-ME"] if "[TEST]" in summary else []),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            if qatouch_case_key:
                fake["qatouch_case_key"] = qatouch_case_key
                fake["qatouch_remote_link"] = QATOUCH_CASE_URL_TMPL.format(key=qatouch_case_key)
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
        if final_labels:
            fields['labels'] = final_labels

        # Auto-populate NC mandatory Bug fields from QA Touch data
        if qa_touch_data and qa_touch_mapper and issue_type == 'Bug':
            mapped = qa_touch_mapper.map_bug_fields(**qa_touch_data)
            fields.update(mapped)
            unmapped = qa_touch_mapper.get_unmapped_required_fields("Bug", mapped)
            if unmapped:
                LOG.warning("[JIRA] These required fields were not auto-populated: %s", unmapped)

        issue = jira.create_issue(fields=fields)
        issue_key = issue.key

        # RTM linkage: attach a remote link back to the QA Touch case so
        # QA Touch's JIRA App 2.0 panel can resolve the case ↔ bug relationship.
        if qatouch_case_key:
            try:
                jira.add_remote_link(issue, {
                    "url": QATOUCH_CASE_URL_TMPL.format(key=qatouch_case_key),
                    "title": f"QA Touch case {qatouch_case_key}",
                })
            except Exception as e:
                LOG.warning('Failed to add QA Touch remote link to %s: %s', issue_key, e)

        # Attach files if present
        if attachments:
            for path in attachments:
                try:
                    if os.path.exists(path):
                        jira.add_attachment(issue=issue_key, attachment=path)
                except Exception as e:
                    LOG.warning('Failed to attach %s: %s', path, e)

        # Link to story if provided (simple comment or issue link attempt)
        if story_link:
            try:
                # If story_link is an issue key, create an issue link
                if '-' in story_link and story_link.isupper() is False:
                    # best-effort: add comment with link
                    jira.add_comment(issue, f'Related story: {story_link}')
                else:
                    jira.add_comment(issue, f'Related story: {story_link}')
            except Exception:
                pass

            # If this is a test issue (summary includes [TEST]) add special label and admin comment
            try:
                if "[TEST]" in summary:
                    try:
                        jira.add_comment(issue, "Admin: Please delete this test bug")
                    except Exception:
                        LOG.warning('Failed to add admin deletion comment to %s', issue_key)
                    # ensure label exists on the issue
                    try:
                        current = list(getattr(issue.fields, 'labels', []) or [])
                        if 'automation-test-DELETE-ME' not in current:
                            current.append('automation-test-DELETE-ME')
                            issue.update(fields={'labels': current})
                    except Exception:
                        LOG.warning('Failed to add label to %s', issue_key)
            except Exception:
                LOG.debug('Post-create test issue handling failed', exc_info=True)

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
    """Best-effort module inference from pytest nodeid path components."""
    nodeid_lower = nodeid.lower()
    for keyword, module_name in _MODULE_MAP.items():
        if keyword in nodeid_lower:
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


def _load_review_queue(queue_path: str = REVIEW_QUEUE) -> Dict[str, Any]:
    """Load and return the review queue, or empty structure."""
    if not os.path.exists(queue_path):
        return {"metadata": {"next_id": 1}, "items": []}
    try:
        with open(queue_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("metadata", {"next_id": 1})
        data.setdefault("items", [])
        return data
    except Exception:
        return {"metadata": {"next_id": 1}, "items": []}


def _save_review_queue(queue: Dict[str, Any], queue_path: str = REVIEW_QUEUE) -> None:
    """Persist the review queue to disk."""
    os.makedirs(os.path.dirname(queue_path), exist_ok=True)
    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)


def _try_api_queue(payload: Dict[str, Any]) -> str | None:
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
                        bug_data: Dict[str, Any] = None, score: float = None,
                        consecutive: int = None, failure_rate: float = None) -> str:
    """Add an item to the review queue with optional enriched bug data.

    Tries the QA Ops Hub API first (if QA_OPS_API_URL and QA_OPS_API_KEY are set).
    Falls back to local JSON file if the API is unreachable.

    Returns the entry ID (e.g. 'RQ-0001').
    """
    # Build API payload
    payload: Dict[str, Any] = {"nodeid": nodeid, "reason": reason}
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
    entry_id = "RQ-%04d" % next_id
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


def list_pending_bugs(queue_path: str = REVIEW_QUEUE) -> List[Dict[str, Any]]:
    """Print and return pending review queue items."""
    queue = _load_review_queue(queue_path)
    pending = [item for item in queue.get("items", []) if item.get("status") == "pending"]

    if not pending:
        print("No pending bugs in the review queue.")
        return []

    print("")
    print("=" * 78)
    print("  PENDING BUG REVIEW QUEUE  (%d item%s)" % (len(pending), "s" if len(pending) != 1 else ""))
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

        print("  [%d] %s" % (i, entry_id))
        print("      Test:       %s" % nodeid)
        print("      Module:     %s" % module)
        print("      Severity:   %s" % severity)
        print("      Confidence: %s  |  Consecutive: %s" % (score, consec))
        print("      Queued:     %s" % ts)
        print("      Bug data:   %s" % has_data)
        print("      " + "-" * 50)

    print("")
    return pending


def review_pending_bugs(queue_path: str = REVIEW_QUEUE) -> Dict[str, Any]:
    """Interactive review of pending bugs. Returns summary dict."""
    queue = _load_review_queue(queue_path)
    pending = [item for item in queue.get("items", [])
               if item.get("status") == "pending" and item.get("bug_data")]

    if not pending:
        print("No pending bugs with full data to review.")
        smoke_only = [item for item in queue.get("items", [])
                      if item.get("status") == "pending" and not item.get("bug_data")]
        if smoke_only:
            print("(%d smoke-test entries without bug data -- see --list or email report)" % len(smoke_only))
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
        print("  REVIEW: %s  (%d of %d)" % (entry_id, idx + 1, len(pending)))
        print("=" * 78)
        print("")
        print("  Test ID:      %s" % nodeid)
        print("  Module:       %s" % bug_data.get("module", "n/a"))
        print("  Summary:      %s" % bug_data.get("summary", "n/a"))
        print("  Environment:  %s" % bug_data.get("environment", "n/a"))
        print("  Severity:     %s" % bug_data.get("severity", "n/a"))
        print("  Confidence:   %s" % item.get("confidence_score", "n/a"))
        print("  Consecutive:  %s failures" % item.get("consecutive_failures", "n/a"))
        print("  Failure Rate: %s" % item.get("failure_rate", "n/a"))
        print("")
        print("  Steps to Reproduce:")
        for line in bug_data.get("steps", "n/a").split("\n"):
            print("    %s" % line)
        print("")
        print("  Expected: %s" % bug_data.get("expected", "n/a"))
        print("  Actual:   %s" % bug_data.get("actual", "n/a"))
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
                    "nodeid: %s\n"
                    "confidence: %s\n"
                    "consecutive_failures: %s\n"
                    "failure_rate: %s\n"
                    % (nodeid, item.get("confidence_score", "n/a"),
                       item.get("consecutive_failures", "n/a"),
                       item.get("failure_rate", "n/a"))
                )
                case_key = _lookup_qatouch_case(nodeid)
                try:
                    issue = jira.create_issue(
                        summary=bug_data.get("summary", nodeid),
                        description=desc,
                        labels=bug_data.get("labels", ["automation"]),
                        qatouch_case_key=case_key,
                        qa_touch_data={
                            "module": bug_data.get("module", "Other"),
                            "steps": bug_data.get("steps", ""),
                            "expected": bug_data.get("expected", ""),
                            "actual": bug_data.get("actual", ""),
                            "environment": bug_data.get("environment", "QA"),
                            "severity": bug_data.get("severity", "Medium"),
                            "build": bug_data.get("build", ""),
                            "title": bug_data.get("summary", ""),
                            "test_case_id": case_key or "",
                        }
                    )
                    issue_key = issue.get("key", "???")
                    item["status"] = "approved"
                    item["jira_key"] = issue_key
                    item["reviewed_by"] = os.environ.get("USERNAME", os.environ.get("USER", "qa"))
                    item["reviewed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    _save_review_queue(queue, queue_path)
                    print("  APPROVED -- Jira issue: %s" % issue_key)
                    approved += 1
                except Exception as e:
                    print("  ERROR creating Jira issue: %s" % e)
                    print("  Item remains pending. Try again later.")
                break

            elif choice in ("r", "reject"):
                item["status"] = "rejected"
                item["reviewed_by"] = os.environ.get("USERNAME", os.environ.get("USER", "qa"))
                item["reviewed_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                _save_review_queue(queue, queue_path)
                print("  REJECTED -- removed from pending queue.")
                rejected += 1
                break

            elif choice in ("e", "edit"):
                print("  Current severity: %s" % bug_data.get("severity", "n/a"))
                print("  Valid options: %s" % ", ".join(VALID_SEVERITIES))
                try:
                    new_sev = input("  New severity: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\n  Edit cancelled.")
                    continue
                if new_sev in VALID_SEVERITIES:
                    bug_data["severity"] = new_sev
                    _save_review_queue(queue, queue_path)
                    print("  Severity updated to: %s" % new_sev)
                    print("  Now choose: [a]pprove  [r]eject  [s]kip")
                else:
                    print("  Invalid severity. Must be one of: %s" % ", ".join(VALID_SEVERITIES))

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
    print("  Review complete: %d approved, %d rejected, %d skipped" % (approved, rejected, skipped))
    print("=" * 78)
    return {"approved": approved, "rejected": rejected, "skipped": skipped}


def multi_gate_validation(nodeid: str, env_base_url: str = None, is_smoke: bool = False, auto_create: bool = False) -> Dict[str, Any]:
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
        details["reason"] = "Environment unhealthy: %s" % env_msg
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
        summary = "[Auto] %s failing in %s" % (nodeid.split("::")[-1], env_base_url or "env")
        bug_data = {
            "summary": summary,
            "module": module,
            "steps": "1. Run test: %s\n2. Test fails consistently" % nodeid,
            "expected": "Test should pass",
            "actual": "Test has failed %d consecutive times (confidence: %s)" % (consec, score),
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
                "nodeid: %s\nconfidence: %s\n"
                "consecutive_failures: %s\nfailure_rate: %s\n"
                "env_check: %s\n"
                % (nodeid, score, consec, fail_rate, env_msg)
            )
            case_key = _lookup_qatouch_case(nodeid)
            issue = jira.create_issue(
                summary, desc,
                labels=bug_data["labels"],
                qatouch_case_key=case_key,
                qa_touch_data={
                    "module": module,
                    "steps": bug_data["steps"],
                    "expected": bug_data["expected"],
                    "actual": bug_data["actual"],
                    "environment": environment,
                    "severity": bug_data["severity"],
                    "build": bug_data["build"],
                    "title": summary,
                    "test_case_id": case_key or "",
                }
            )
            details["issue"] = issue
            return {"action": "create_issue", "details": details}
        else:
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
