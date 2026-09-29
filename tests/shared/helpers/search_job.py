"""Watch the search job behind a Search click, and report what the server said.

The Events page and the Search page (every category: Event, Vehicle, Line,
Zone) run a search the same way, measured on the app:

    POST .../REST/site/search        -> {"result": [{"jobId": "...", "query": {...}}]}
    POST .../REST/site/search/event  -> {"result": [{"eventList": [...],
        (polled until complete)            "totalEvent": N, "completionPercentage": P}]}

Before this helper every caller waited on the first result thumbnail with
a 60 to 120 second ceiling, so three different facts all read as
"Locator.wait_for: Timeout exceeded":

- the click sent no job: the app re-runs a search only after a filter
  changes;
- the job reached 100% with nothing in it: the tenant holds no such data
  for those parameters, and the page says "We couldn't find any data"
  (24 of 49 failures in one run were this, on a tenant with no events);
- the job never finished: the server-side search hung.

`watch_search` returns the moment the server has answered, whichever of
those it is, and `require_results` turns the answer into the house verdict
(docs/CONVENTIONS.md > Missing artifacts and skips): a finished, empty
search is a data fact and skips with the measurements; the other two are
faults and fail.

Polls that arrive before the job's own start response are ignored, so the
tail of a previous search is not read as this one; the app stops the
previous job when a new search starts, so a later stray poll is unlikely.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import pytest
from playwright.sync_api import Page

from tests.shared.helpers import search_gap

JOB_PATH = "/REST/site/search"
POLL_PATH = "/REST/site/search/event"
REQUEST_TIMEOUT_MS = 15000

OUTCOMES = ("pending", "results", "empty", "no_request", "incomplete", "fault")


@dataclass
class SearchJob:
    """What the server said about one search, response by response."""

    job_id: str | None = None
    category: str | None = None
    channels: int | None = None
    window_s: float | None = None
    polls: int = 0
    total: int | None = None
    completion: float | None = None
    delivered: int = 0
    faults: list[str] = field(default_factory=list)
    elapsed_s: float = 0.0
    outcome: str = "pending"

    # --- folding responses in ---

    def observe(self, path: str, http_status: int, body: Any) -> None:
        """Fold one POST response into the record.

        `path` is the URL without its query string; `body` the parsed JSON,
        or None when the body was not JSON (a gateway page, a timeout).
        """
        if http_status != 200:
            self.faults.append(f"{_short(path)} answered HTTP {http_status}")
            return
        if not isinstance(body, dict):
            self.faults.append(f"{_short(path)} answered with a body that is not JSON")
            return
        if body.get("code") not in (200, None):
            self.faults.append(f"{_short(path)} answered code {body.get('code')}: {body.get('message')}")
            return
        first = _first_result(body)
        if path.endswith(JOB_PATH):
            self._observe_start(first)
        elif path.endswith(POLL_PATH) and self.job_id is not None:
            self._observe_poll(first)

    def _observe_start(self, first: dict) -> None:
        self.job_id = str(first.get("jobId") or "") or None
        query_list = (first.get("query") or {}).get("queryList") or [{}]
        query = (query_list[0] or {}).get("query") or {} if isinstance(query_list, list) else {}
        self.category = query.get("category") or None
        channels = query.get("channelList")
        self.channels = len(channels) if isinstance(channels, list) else None
        start, end = query.get("startTimeStamp"), query.get("endTimeStamp")
        if isinstance(start, (int, float)) and isinstance(end, (int, float)):
            self.window_s = (end - start) / 1000

    def _observe_poll(self, first: dict) -> None:
        self.polls += 1
        events = first.get("eventList")
        if isinstance(events, list):
            self.delivered += len(events)
        total = first.get("totalEvent")
        if isinstance(total, (int, float)):
            self.total = int(total)
        completion = first.get("completionPercentage")
        if isinstance(completion, (int, float)):
            self.completion = float(completion)

    # --- reading the record ---

    def finished(self) -> bool:
        """True once the server reports the search 100% complete."""
        return self.completion is not None and self.completion >= 100

    def has_results(self) -> bool:
        """True once the server has delivered or counted at least one event."""
        return self.delivered > 0 or (self.total or 0) > 0

    def settle(self, elapsed_s: float, *, timeout_s: float, request_timeout_s: float) -> str:
        """Decide the outcome from what has arrived so far; 'pending' means keep waiting."""
        self.elapsed_s = elapsed_s
        if self.faults:
            self.outcome = "fault"
        elif self.job_id is None:
            self.outcome = "no_request" if elapsed_s >= request_timeout_s else "pending"
        elif self.has_results():
            self.outcome = "results"
        elif self.finished():
            self.outcome = "empty"
        elif elapsed_s >= timeout_s:
            self.outcome = "incomplete"
        else:
            self.outcome = "pending"
        return self.outcome

    def describe(self) -> str:
        """One sentence of measurements for a report line."""
        if self.job_id is None:
            return f"no search job was sent within {self.elapsed_s:.0f} s of the click"
        scope = ", ".join(s for s in (
            self.category,
            f"{self.channels} channels" if self.channels is not None else None,
            f"{self.window_s / 86400:.1f} days" if self.window_s else None,
        ) if s)
        progress = (f"{self.completion:.0f}% complete" if self.completion is not None
                    else "no poll answered")
        counted = (f"{self.total} events counted, {self.delivered} delivered"
                   if self.total is not None else f"{self.delivered} delivered")
        text = (f"search job {self.job_id} ({scope}): {self.polls} polls in "
                f"{self.elapsed_s:.1f} s, {progress}, {counted}")
        if self.faults:
            text += "; faults: " + "; ".join(self.faults)
        return text


def _first_result(body: dict) -> dict:
    result = body.get("result")
    if isinstance(result, list) and result and isinstance(result[0], dict):
        return result[0]
    return {}


def _short(path: str) -> str:
    return path.split("/REST/")[-1] if "/REST/" in path else path


def watch_search(page: Page, click: Callable[[], None], *, timeout_ms: int = 60000,
                 request_timeout_ms: int = REQUEST_TIMEOUT_MS) -> SearchJob:
    """Click, then follow the search job until the server has answered.

    Returns as soon as one of these is true: an event was delivered or
    counted (results), the job reached 100% with none (empty), no job was
    sent within `request_timeout_ms` (no_request), a response was not a
    clean 200 (fault), or `timeout_ms` passed first (incomplete). The
    ceiling is on the SERVER's work, so a search that answers in ten
    seconds costs ten seconds whatever the ceiling says.
    """
    job = SearchJob()

    def on_response(response) -> None:
        request = response.request
        if request.method != "POST" or JOB_PATH not in response.url:
            return
        path = response.url.split("?")[0]
        try:
            body = response.json()
        except Exception:  # why: a non-JSON body is one of the faults observe records
            body = None
        job.observe(path, response.status, body)

    # the account's one search job frees about 16 s after the previous
    # searching test's page closed: wait only the remainder, then note
    # that this test searched so its own close is stamped (search_gap)
    search_gap.wait_for_gap()
    search_gap.mark_ran()
    page.on("response", on_response)
    started = time.monotonic()
    try:
        click()
        while job.settle(time.monotonic() - started, timeout_s=timeout_ms / 1000,
                         request_timeout_s=request_timeout_ms / 1000) == "pending":
            page.wait_for_timeout(200)  # poll tick: progress arrives as responses, not in the DOM
    finally:
        page.remove_listener("response", on_response)
    return job


def require_results(job: SearchJob, *, surface: str) -> None:
    """The house verdict for a search that must return something.

    A finished, empty search skips: the surface answered, the tenant holds
    nothing for those parameters. Anything else that is not results fails,
    naming which fault it was.
    """
    if job.outcome == "results":
        return
    if job.outcome == "empty":
        pytest.skip(
            f"{surface}: {job.describe()}. The search completed and the tenant "
            f"holds nothing for these parameters, so this is data, not a broken page."
        )
    raise AssertionError(f"{surface}: {job.describe()}. {_fault_hint(job)}")


def require_finished(job: SearchJob, *, surface: str) -> bool:
    """For callers that accept an empty search: True when it returned results.

    Results and a finished empty search both count as finished. A search
    that never ran or never finished is a fault and fails.
    """
    if job.outcome in ("results", "empty"):
        return job.outcome == "results"
    raise AssertionError(f"{surface}: {job.describe()}. {_fault_hint(job)}")


def _fault_hint(job: SearchJob) -> str:
    if job.outcome == "no_request":
        return ("The click sent no search job: the app re-runs a search only after "
                "a filter changes, so re-apply the filters or start from a fresh view.")
    if job.outcome == "incomplete":
        return "The server never reported the job complete: the search hung or the polls stopped."
    if job.outcome == "fault":
        return "A search response was not a clean 200; the app, not the test, failed here."
    return f"Unexpected outcome '{job.outcome}'."
