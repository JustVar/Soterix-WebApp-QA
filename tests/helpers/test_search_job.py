"""Pins for tests/shared/helpers/search_job.py.

The bodies here are the ones the QA server answered on 09/08/2026, trimmed to
the fields the helper reads. A fake page delivers them in the order the
browser would, so the decision logic is exercised without a browser.
"""
from __future__ import annotations

import pytest

from tests.shared.helpers import search_gap, search_job as sj


@pytest.fixture(autouse=True)
def no_search_gap(monkeypatch):
    """These pins drive watch_search with a fake page: no real job runs,
    so the account's free window does not apply. Without this, each pin's
    fake search stamped the stop and the next waited the full 17 s."""
    monkeypatch.setattr(search_gap, "wait_for_gap", lambda: 0.0)
    monkeypatch.setattr(search_gap, "mark_ran", lambda: None)

JOB_URL = "https://vsaas-qa.example/v-apiserver/REST/site/search"
POLL_URL = "https://vsaas-qa.example/v-apiserver/REST/site/search/event"


def start_body(job_id="1788887721449", channels=22, days=7.0, category="EVENT"):
    end = 1_788_887_723_051
    return {"status": 2007, "code": 200, "message": "Successfully Applied!",
            "result": [{"jobId": job_id, "query": {"queryList": [{"query": {
                "siteId": 156, "channelList": list(range(1, channels + 1)),
                "startTimeStamp": end - int(days * 86400 * 1000), "endTimeStamp": end,
                "category": category}}]}}]}


def poll_body(events=0, total=0, completion=3.0):
    return {"status": 2000, "code": 200, "message": "Successfully Retrieved!",
            "result": [{"eventList": [{"eventId": i} for i in range(events)],
                        "totalEvent": total, "completionPercentage": completion}]}


class FakeResponse:
    def __init__(self, url, body, status=200, method="POST"):
        self.url, self._body, self.status = url, body, status
        self.request = type("Req", (), {"method": method})()

    def json(self):
        if self._body is None:
            raise ValueError("not json")
        return self._body


class FakePage:
    """Delivers one queued response per wait tick, like a browser would."""

    def __init__(self, queue, clock_step=0.5):
        self.queue = list(queue)
        self.handlers = []
        self.ticks = 0
        self.clock_step = clock_step

    def on(self, event, handler):
        assert event == "response"
        self.handlers.append(handler)

    def remove_listener(self, event, handler):
        self.handlers.remove(handler)

    def wait_for_timeout(self, ms):  # fake page: a tick hands over one queued response, nothing sleeps
        self.ticks += 1
        if self.queue:
            response = self.queue.pop(0)
            for handler in list(self.handlers):
                handler(response)


def run(queue, **kw):
    page = FakePage(queue)
    clicks = []
    # the fake clock advances half a second per tick, so the timeouts below are in ticks
    times = iter(i * 0.5 for i in range(100000))
    sj.time = type("T", (), {"monotonic": staticmethod(lambda: next(times))})()
    try:
        job = sj.watch_search(page, lambda: clicks.append(1), **kw)
    finally:
        import time as real_time
        sj.time = real_time
    assert clicks == [1]
    assert page.handlers == [], "the response listener must be removed"
    return job, page


# --- observe: folding responses in -------------------------------------------

def test_start_body_yields_the_job_and_its_scope():
    """Start body yields the job and its scope."""
    job = sj.SearchJob()
    job.observe(JOB_URL, 200, start_body(channels=22, days=7.0))
    assert job.job_id == "1788887721449"
    assert (job.category, job.channels) == ("EVENT", 22)
    assert job.window_s == pytest.approx(7 * 86400)
    assert not job.finished()
    assert not job.has_results()


def test_polls_before_the_start_are_ignored():
    """The tail of a previous search must not be read as this one."""
    job = sj.SearchJob()
    job.observe(POLL_URL, 200, poll_body(events=5, total=5, completion=100))
    assert (job.polls, job.delivered, job.total) == (0, 0, None)


def test_polls_accumulate_deliveries_and_track_progress():
    """Polls accumulate deliveries and track progress."""
    job = sj.SearchJob()
    job.observe(JOB_URL, 200, start_body())
    job.observe(POLL_URL, 200, poll_body(events=9, total=9, completion=6.0))
    job.observe(POLL_URL, 200, poll_body(events=0, total=9, completion=50.0))
    assert (job.polls, job.delivered, job.total, job.completion) == (2, 9, 9, 50.0)
    assert job.has_results()
    assert not job.finished()


@pytest.mark.parametrize(("status", "body", "words"), [
    (502, None, "HTTP 502"),
    (200, None, "not JSON"),
    (200, {"code": 500, "message": "boom", "result": []}, "code 500: boom"),
])
def test_unclean_answers_are_recorded_as_faults(status, body, words):
    """Unclean answers are recorded as faults."""
    job = sj.SearchJob()
    job.observe(POLL_URL, status, body)
    assert len(job.faults) == 1
    assert words in job.faults[0]


# --- watch_search: the outcomes -----------------------------------------------

def test_results_return_on_the_first_delivery_not_at_completion():
    """Results return on the first delivery not at completion."""
    job, page = run([
        FakeResponse(JOB_URL, start_body()),
        FakeResponse(POLL_URL, poll_body(events=9, total=9, completion=6.0)),
        FakeResponse(POLL_URL, poll_body(events=0, total=9, completion=50.0)),
    ])
    assert job.outcome == "results"
    assert page.queue, "the watch stopped before the remaining polls; it did not wait for 100%"
    assert "9 events counted, 9 delivered" in job.describe()


def test_a_finished_empty_job_is_empty_not_a_timeout():
    """A finished empty job is empty not a timeout."""
    job, _ = run([
        FakeResponse(JOB_URL, start_body(channels=22, days=30.0, category="EVENT")),
        FakeResponse(POLL_URL, poll_body(completion=25.0)),
        FakeResponse(POLL_URL, poll_body(completion=100.0)),
    ], timeout_ms=60000)
    assert job.outcome == "empty"
    text = job.describe()
    assert "EVENT, 22 channels, 30.0 days" in text
    for words in ("2 polls", "100% complete", "0 events counted"):
        assert words in text


def test_no_job_within_the_request_window_is_no_request():
    """No job within the request window is no request."""
    job, page = run([], timeout_ms=60000, request_timeout_ms=3000)
    assert job.outcome == "no_request"
    assert "no search job was sent within 3 s" in job.describe()
    assert page.ticks == 5  # pending at 0.5 s .. 2.5 s, decided at 3.0 s; not the 60 s ceiling


def test_a_job_that_never_completes_is_incomplete_at_the_ceiling():
    """A job that never completes is incomplete at the ceiling."""
    job, _ = run([
        FakeResponse(JOB_URL, start_body()),
        FakeResponse(POLL_URL, poll_body(completion=12.0)),
    ], timeout_ms=5000)
    assert job.outcome == "incomplete"
    assert "12% complete" in job.describe()


def test_a_bad_response_is_a_fault_at_once():
    """A bad response is a fault at once."""
    job, page = run([
        FakeResponse(JOB_URL, start_body()),
        FakeResponse(POLL_URL, None, status=502),
        FakeResponse(POLL_URL, poll_body(completion=100.0)),
    ])
    assert job.outcome == "fault"
    assert page.queue, "the watch stopped at the fault"


def test_get_and_unrelated_responses_are_not_read():
    """Get and unrelated responses are not read."""
    job, _ = run([
        FakeResponse(JOB_URL + "/stop/123", {"code": 200, "result": [True]}, method="GET"),
        FakeResponse("https://vsaas-qa.example/v-apiserver/REST/central/user/session", {"code": 200}),
        FakeResponse(JOB_URL, start_body()),
        FakeResponse(POLL_URL, poll_body(events=1, total=1, completion=100)),
    ])
    assert job.outcome == "results"
    assert job.polls == 1


# --- the verdicts --------------------------------------------------------------

def finished(outcome, **fields):
    job = sj.SearchJob(job_id="1", category="EVENT", channels=22, polls=3, elapsed_s=4.0, **fields)
    job.outcome = outcome
    return job


def test_require_results_passes_results_and_skips_a_proven_empty_search():
    """Require results passes results and skips a proven empty search."""
    sj.require_results(finished("results", total=9, delivered=9, completion=6.0), surface="Events search")
    with pytest.raises(pytest.skip.Exception) as info:
        sj.require_results(finished("empty", total=0, completion=100.0), surface="Events search")
    reason = str(info.value)
    assert reason.startswith("Events search: search job 1 (EVENT, 22 channels): 3 polls in 4.0 s, 100% complete")
    assert "this is data, not a broken page" in reason


@pytest.mark.parametrize(("outcome", "hint"), [
    ("no_request", "re-runs a search only after a filter changes"),
    ("incomplete", "never reported the job complete"),
    ("fault", "not a clean 200"),
])
def test_require_results_fails_every_fault_with_its_hint(outcome, hint):
    """Require results fails every fault with its hint."""
    with pytest.raises(AssertionError, match=hint):
        sj.require_results(finished(outcome), surface="Search")


def test_require_finished_accepts_empty_and_reports_results_as_a_bool():
    """Require finished accepts empty and reports results as a bool."""
    assert sj.require_finished(finished("results", total=2, delivered=2), surface="S") is True
    assert sj.require_finished(finished("empty", total=0, completion=100.0), surface="S") is False
    with pytest.raises(AssertionError, match="never reported"):
        sj.require_finished(finished("incomplete"), surface="S")
