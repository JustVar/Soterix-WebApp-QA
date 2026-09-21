"""Pin for the LPR events feed wait: the full wait one time, then a short one while the empty reading is fresh."""
from __future__ import annotations

from tests.ui.admin import test_lpr_events as mod


def test_an_empty_feed_is_proved_once_then_rechecked_quickly(monkeypatch):
    """No reading: 30 s. A reading 10 s old: 5 s. A reading 6 minutes old: 30 s again."""
    monkeypatch.setitem(mod._FEED_EMPTY, "at", None)
    assert mod._feed_wait_ms(now=1000.0) == mod.FEED_WAIT_MS
    monkeypatch.setitem(mod._FEED_EMPTY, "at", 990.0)
    assert mod._feed_wait_ms(now=1000.0) == mod.FEED_RECHECK_MS
    monkeypatch.setitem(mod._FEED_EMPTY, "at", 1000.0 - 360)
    assert mod._feed_wait_ms(now=1000.0) == mod.FEED_WAIT_MS
