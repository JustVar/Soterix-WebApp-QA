"""Survive a worker that dies mid-run under --dist loadgroup.

pytest-xdist 3.8.0's LoadScopeScheduling (the loadgroup scheduler) does
two things wrong when a worker dies, both measured on a real run:

1. remove_node re-queues the dead worker's units with the item it died on
   still pending, so every replacement worker replays that item and dies
   again, until --max-worker-restart (four times the worker count) ends
   the session. A run once replayed two hung LPR screenshots this way.
2. schedule() reschedules every node, including a replacement that has
   registered no collection yet, and _assign_work_unit raises
   KeyError(<WorkerController gwN>): an INTERNALERROR that ended a run
   part way through its queue. --max-worker-restart 0 is no answer: the
   first crash then shuts the session down with the queue unrun (measured).

This plugin patches both at configure time: the crash item is marked
complete before the units go back (the controller already reports it
failed once), and a node with no collection yet is skipped until it has
one. The patch is idempotent, and tests/plugins/test_xdist_crash_recovery.py
runs the crash scenario for real to pin the outcome: a dead worker costs
one failure and nothing else.
"""
from __future__ import annotations

import logging

log = logging.getLogger("xdist_recovery")


def harden_loadscope() -> bool:
    """Patch xdist's loadscope scheduler once; True when it is patched."""
    try:
        from xdist.scheduler import loadscope
    except ImportError:  # why: xdist not installed, nothing to harden
        return False
    cls = loadscope.LoadScopeScheduling
    if getattr(cls, "_qa_hardened", False):
        return True
    orig_reschedule = cls._reschedule

    def remove_node(self, node):
        workload = self.assigned_work.pop(node)
        crashitem = None
        for unit in workload.values():
            for nodeid, done in unit.items():
                if not done:
                    crashitem = nodeid
                    # The controller reports this item failed once (worker
                    # crashed while running it); marking it done keeps a
                    # replacement worker from replaying the crash.
                    unit[nodeid] = True
                    break
            if crashitem:
                break
        if crashitem is None:
            return None
        self.workqueue.update({scope: unit for scope, unit in workload.items()
                               if not all(unit.values())})
        for other in list(self.assigned_work):
            self._reschedule(other)
        return crashitem

    def _reschedule(self, node):
        if node not in self.registered_collections:
            # A replacement worker that is ready but has not collected yet;
            # schedule() comes back to it when its collection lands.
            return None
        return orig_reschedule(self, node)

    cls.remove_node = remove_node
    cls._reschedule = _reschedule
    cls._qa_hardened = True
    log.debug("xdist_recovery: loadscope scheduler hardened against worker crashes")
    return True


def pytest_configure(config):
    harden_loadscope()
