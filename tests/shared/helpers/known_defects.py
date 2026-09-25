"""Which tests are red because of an app defect somebody already knows about.

A nightly ends with about 30 red tests on each box. Most are defects already
being worked, and nothing on the run page said so, so a reader had to remember
which was which (09/25/2026). This reads config/known_defects.yaml and answers,
for one test, "is this a known defect, and which".

The answer travels INTO the run record at archive time, through the shared
package's `configure_known_defects` hook, so a served page needs neither this
file nor this repo to render the label.
"""
from __future__ import annotations

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
        if tests:
            out.append({**entry, "tests": tests})
    return out


def matches(nodeid: str, name: str) -> bool:
    """`test_x` matches a nodeid ending in ::test_x; `path::test_x` matches that path."""
    bare = _bare(nodeid)
    if "::" in name:
        return bare == name or (bare.endswith("::" + name.split("::", 1)[1]) and bare.startswith(name.split("::", 1)[0]))
    return bare.rsplit("::", 1)[-1] == name


def known_defect_for(nodeid: str) -> dict | None:
    """What the run record carries for this test, or None: {row, since, what}."""
    for entry in load():
        if any(matches(nodeid, t) for t in entry["tests"]):
            return {"row": entry.get("row"), "since": str(entry.get("since") or ""), "what": str(entry["what"])}
    return None
