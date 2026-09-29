"""The docs point at files that exist, and no live file names what left.

A doc that links a page that is gone sends a new reader nowhere. A comment
or a message that names a host, a variable or a page that left the main
branch tells the reader to look for something that does not exist, and the
guard it explains gets deleted next. Both are silent until someone follows
the pointer. These tests follow every pointer.

The first test resolves every relative markdown link in README.md,
AGENTS.md and the live docs. The second scans the live tree for the names
of what left: the old hosts, the two-tenant account variables, the removed
config function, the failure register and the words of the old schedule.
docs/ARCHIVE.md is the one page allowed to name them, because naming what
left is its job.

The scan reports a path and the term it holds, never the line, so a
finding in a local file can never print a value.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"
# Docs that are not part of the live set: the local notes are gitignored
# and a fresh clone never has them.
DOC_SKIP = {"archive", "local"}

# Names of what left the main branch. docs/ARCHIVE.md may name them.
DEAD_TERMS = (
    "spartan1",
    "10.2.0.2",
    "spartan20",
    "qa-publish",
    "QA_INDIA_",
    "QA_US_",
    "get_active_box",
    "TEST_REPAIRS.md",
    "register row",
    "india leg",
    "per-box",
    "per box",
    "the nightly",
    "CLAUDE.md",
    "--run-destructive",
)
ALLOWED = {DOCS / "ARCHIVE.md", Path(__file__).resolve()}
SCAN_ROOTS = ("config", "plugins", "tools", "tests", "deploy", ".github")
# The tracked text files at the repo root, by name. Never the whole root:
# .env and its backups are gitignored, private, and may hold anything.
ROOT_FILES = (".env.template", ".gitattributes", ".gitignore", "conftest.py",
              "pyproject.toml", "pytest.ini", "requirements.txt", "run.py")
TEXT_SUFFIXES = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".ini", ".toml", ".cfg",
    ".csv", ".ps1", ".sh", ".template", ".html", ".js", ".css", "",
}
SKIP_DIRS = {"__pycache__", ".git", "venv", "node_modules", ".pytest_cache"}

LINK_RE = re.compile(r"(?<!\!)\[[^\]]*\]\(([^)\s]+)\)")


def live_docs() -> list[Path]:
    """README.md, AGENTS.md and every markdown page under docs/ that a
    fresh clone has, the archive excluded."""
    pages = [REPO_ROOT / "README.md", REPO_ROOT / "AGENTS.md"]
    for path in sorted(DOCS.rglob("*.md")):
        parts = path.relative_to(DOCS).parts
        if parts[0] in DOC_SKIP:
            continue
        pages.append(path)
    return [p for p in pages if p.is_file()]


def relative_links(page: Path) -> list[str]:
    """The link targets in a page that point at a file, anchors stripped."""
    text = page.read_text(encoding="utf-8", errors="replace")
    targets = []
    for target in LINK_RE.findall(text):
        if re.match(r"^[a-z][a-z0-9+.-]*:", target):
            continue    # http, https, mailto
        target = target.split("#", 1)[0]
        if not target:
            continue    # a same-page anchor
        targets.append(target)
    return targets


def test_every_relative_link_in_the_live_docs_resolves():
    """A link in README.md, AGENTS.md or docs/*.md names a file that exists."""
    dead = []
    for page in live_docs():
        for target in relative_links(page):
            if not (page.parent / target).exists():
                dead.append(f"{page.relative_to(REPO_ROOT)} -> {target}")
    assert not dead, "dead links:\n" + "\n".join(dead)


def live_files() -> list[Path]:
    """Every text file the scan covers: the two root pages, the live docs,
    the tracked root files, and the trees under config/, plugins/, tools/,
    tests/, deploy/ and .github/."""
    files = list(live_docs())
    files += [REPO_ROOT / name for name in ROOT_FILES if (REPO_ROOT / name).is_file()]
    for root in SCAN_ROOTS:
        for path in sorted((REPO_ROOT / root).rglob("*")):
            if not path.is_file():
                continue
            if SKIP_DIRS & set(path.relative_to(REPO_ROOT).parts):
                continue
            if path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            files.append(path)
    return [p for p in files if p.resolve() not in ALLOWED]


def test_no_live_file_names_what_left():
    """No live file names a dead host, a removed variable or the register."""
    found = []
    for path in live_files():
        # An unreadable file fails the test with its own traceback.
        text = path.read_text(encoding="utf-8", errors="replace")
        terms = [term for term in DEAD_TERMS if term in text]
        if terms:
            found.append(f"{path.relative_to(REPO_ROOT)}: {', '.join(terms)}")
    assert not found, (
        "these files name what left the main branch (see docs/ARCHIVE.md):\n"
        + "\n".join(found)
    )
