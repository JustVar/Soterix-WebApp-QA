"""Which tests are red because of an app defect somebody already knows about.

A full run ends with red tests that are defects already being worked, and
nothing on the run page says so, so a reader has to remember which is
which. This reads config/known_defects.yaml and answers, for one test, "is
this a known defect, and which". The list ships empty: a team adds one
entry per app defect it knows about.

The answer travels INTO the run record at archive time, through the shared
package's `configure_known_defects` hook, so a served page needs neither this
file nor this repo to render the label.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

DEFECTS_FILE = Path(__file__).resolve().parents[3] / "config" / "known_defects.yaml"


def _bare(nodeid: str) -> str:
    """The nodeid without its parameter suffix and xdist group tag."""
    return nodeid.split("[", 1)[0].split("@", 1)[0]


@lru_cache(maxsize=1)
def load(path: Path | None = None) -> list[dict]:
    """The entries, each with its tests as a list. [] when there is no file.

    Cached: this is asked once per test at archive time and the file does not
    change inside a run.
    """
    import yaml
    p = path or DEFECTS_FILE
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or []
    except (OSError, yaml.YAMLError):  # why: a missing or broken file must leave the archive as it was, unlabelled, not stop the run
        return []
    out = []
    for entry in data if isinstance(data, list) else []:
        if not isinstance(entry, dict) or not entry.get("what"):
            continue
        tests = [str(t).strip() for t in (entry.get("tests") or []) if str(t).strip()]
        signature = str(entry.get("signature") or "").strip()
        if signature:
            try:
                re.compile(signature)
            except re.error:  # why: a bad pattern must not stop the archive; the entry is dropped and the pin names it
                continue
        if tests or signature:
            out.append({**entry, "tests": tests, "signature": signature})
    return out


def matches(nodeid: str, name: str) -> bool:
    """`test_x` matches a nodeid ending in ::test_x; `path::test_x` matches that path."""
    bare = _bare(nodeid)
    if "::" in name:
        return bare == name or (bare.endswith("::" + name.split("::", 1)[1]) and bare.startswith(name.split("::", 1)[0]))
    return bare.rsplit("::", 1)[-1] == name


def _record(entry: dict) -> dict:
    return {"since": str(entry.get("since") or ""), "what": str(entry["what"])}


def known_defect_for(nodeid: str, error: str | None = None) -> dict | None:
    """What the run record carries for this test, or None: {since, what}.

    By test name first. Then, when the failure's error line is known, by
    signature: a defect that hits whichever test touched it (the tenant's
    search API answering something other than 200) is one entry, not a list
    of tests that changes every night.
    """
    for entry in load():
        if any(matches(nodeid, t) for t in entry["tests"]):
            return _record(entry)
    if error:
        for entry in load():
            if entry["signature"] and re.search(entry["signature"], error, re.I):
                return _record(entry)
    return None
