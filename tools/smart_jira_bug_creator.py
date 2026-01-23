"""
Smart Jira Bug Creator

Implements multi-gate validation to avoid filing bugs for flaky tests.

Features:
- Confidence scoring based on failure history and consecutive failures
- Environment health checks (basic base_url probe)
- Manual-review queue hooks for smoke tests
- Stubs for Jira issue creation (replace with real API integration)

Configuration constants:
- CONFIDENCE_THRESHOLD: float (0-1)
- MIN_CONSECUTIVE_FAILURES: int

Usage (simple):
  python -m tools.smart_jira_bug_creator --test <nodeid> --env qa

This module is intentionally conservative and contains no live Jira calls by default.
Plug in Jira credentials and API calls in `JiraClient.create_issue()`.
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

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FLAKY_DB = os.path.join(ROOT, "flaky_tests.json")
REVIEW_QUEUE = os.path.join(ROOT, "tools", "review_queue.json")

CONFIDENCE_THRESHOLD = 0.7
MIN_CONSECUTIVE_FAILURES = 2


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

    def create_issue(self, summary: str, description: str, labels: List[str] = None, project_key: str = None, issue_type: str = 'Bug', attachments: List[str] = None, story_link: str = None) -> Dict[str, Any]:
        """Create a Jira issue using `jira` library if available and BUG_CREATION_ENABLED true.

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
        if labels:
            fields['labels'] = labels

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


def add_to_review_queue(nodeid: str, reason: str, queue_path: str = REVIEW_QUEUE) -> None:
    os.makedirs(os.path.dirname(queue_path), exist_ok=True)
    queue = {"items": []}
    if os.path.exists(queue_path):
        try:
            with open(queue_path, "r", encoding="utf-8") as f:
                queue = json.load(f)
        except Exception:
            queue = {"items": []}
    queue.setdefault("items", [])
    queue["items"].append({"nodeid": nodeid, "reason": reason, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    with open(queue_path, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2)
    LOG.info("Added %s to manual review queue (%s)", nodeid, queue_path)


def multi_gate_validation(nodeid: str, env_base_url: str = None, is_smoke: bool = False) -> Dict[str, Any]:
    """Run gates and decide whether to open a Jira bug or queue for review.

    Returns dict with keys: action: one of [no_action, queued, create_issue], details: {...}
    """
    db = load_flaky_db()
    history = get_history(nodeid, db)

    env_ok, env_msg = env_health_check(env_base_url) if env_base_url else (True, "no-check")
    score = compute_confidence(history, env_ok)
    consecutive = consecutive_failures(history)
    failure_rate = calc_failure_rate(history)

    details = {
        "nodeid": nodeid,
        "env_ok": env_ok,
        "env_msg": env_msg,
        "score": score,
        "consecutive_failures": consecutive,
        "failure_rate": failure_rate,
        "history_len": len(history),
    }

    # Gate 1: environment health
    if not env_ok:
        details["reason"] = f"Environment unhealthy: {env_msg}"
        return {"action": "no_action", "details": details}

    # Gate 2: smoke tests require manual review on first failure
    if is_smoke:
        # If there were no prior failures, add to review queue instead of auto-bug.
        prior_fails = sum(1 for r in history if r.get("result") == "fail")
        if prior_fails == 0:
            add_to_review_queue(nodeid, "First smoke test failure - manual review required")
            details["reason"] = "first_smoke_failure"
            return {"action": "queued", "details": details}

    # Gate 3: consecutive failures + confidence threshold
    if consecutive >= MIN_CONSECUTIVE_FAILURES and score >= CONFIDENCE_THRESHOLD:
        # Create issue (stub)
        jira = JiraClient()
        summary = f"[Auto] Flaky detection: {nodeid} failing in {env_base_url or 'env'}"
        desc = (
            f"Automated detection:\nnodeid: {nodeid}\nconfidence: {score}\nconsecutive_failures: {consecutive}\n"
            f"failure_rate: {failure_rate}\nenv_check: {env_msg}\n"
        )
        issue = jira.create_issue(summary, desc, labels=["automation", "auto-detected"])
        details["issue"] = issue
        return {"action": "create_issue", "details": details}

    # Default: do not file
    details["reason"] = "Insufficient evidence (confidence/consecutive)"
    return {"action": "no_action", "details": details}


def main_cli():
    import argparse

    parser = argparse.ArgumentParser(description="Smart Jira Bug Creator")
    parser.add_argument("--test", required=True, help="pytest nodeid of the failed test")
    parser.add_argument("--env-base-url", required=False, help="Base URL of the environment to check")
    parser.add_argument("--smoke", action="store_true", help="Mark this as a smoke test (requires manual review on first fail)")
    args = parser.parse_args()

    result = multi_gate_validation(args.test, env_base_url=args.env_base_url, is_smoke=args.smoke)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main_cli()
