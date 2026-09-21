"""Pins for the tenant-state grouping under xdist (audit 09/17/2026, register
row 86): pytest.ini keeps --dist loadgroup, every module that writes this
account's state declares an xdist_group, and a command-line --dist that
would undo it is refused."""
from __future__ import annotations

import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import conftest  # noqa: E402

# A module that does any of these writes the account's state; two workers
# on it race. The list is the audit's grep plus the review's additions
# (api fixtures that create, favourites, exports, widget writes, the
# notification mute); a new writer joins it by failing this pin.
# create_widget_button is a read-only visibility check, hence the lookahead.
WRITES_STATE = re.compile(
    r"\b(create_(?!widget_button)|delete_|rename_|mute_|_mute_notifications|save_view|add_bookmark|_own_a_"
    r"|toggle_user|favou?rite|api_saved_view|api_bookmark|api_camera_group|export_)")
GROUP_RE = re.compile(r'^pytestmark = pytest\.mark\.xdist_group\("(\w+)"\)', re.MULTILINE)
# State that no method name gives away: the module and the group it must be in. The LPR camera
# page keeps its layout on the server for each user, so each module that drops a camera on its
# tiles shares that layout with the test that changes it.
SHARED_STATE = {
    "tests/ui/admin/test_lpr_grid_and_timer.py": "account_lpr",
    "tests/ui/admin/test_lpr_camera_selection.py": "account_lpr",
    "tests/ui/admin/test_lpr_playback.py": "account_lpr",
}


def _config(workers, dist, loaded=True):
    def getoption(name):
        if not loaded:
            raise ValueError(name)
        return {"numprocesses": workers, "dist": dist}[name]
    return SimpleNamespace(getoption=getoption)


def test_pytest_ini_keeps_loadgroup():
    """The ini carries the dist mode the grouping depends on."""
    ini = (REPO_ROOT / "pytest.ini").read_text(encoding="utf-8")
    assert "--dist loadgroup" in ini


def test_every_module_that_writes_tenant_state_declares_a_group():
    """A module that creates, renames, deletes or mutes account state names its xdist group."""
    missing = []
    for path in sorted((REPO_ROOT / "tests" / "ui").rglob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        if WRITES_STATE.search(text) and not GROUP_RE.search(text):
            missing.append(path.relative_to(REPO_ROOT).as_posix())
    assert not missing, ("these modules write tenant state and carry no xdist_group; add "
                         "pytestmark = pytest.mark.xdist_group(\"account_<family>\") (docs/PARALLEL_EXECUTION.md): "
                         + ", ".join(missing))


def test_modules_that_share_state_with_no_telling_name_are_in_their_group():
    """Each module of SHARED_STATE carries its group, and a module that plays a camera on the LPR page is in the list."""
    for rel, group in SHARED_STATE.items():
        found = GROUP_RE.search((REPO_ROOT / rel).read_text(encoding="utf-8"))
        assert found, f"{rel} must be in the xdist group {group}"
        assert found.group(1) == group, f"{rel} must be in the xdist group {group}"
    for path in sorted((REPO_ROOT / "tests" / "ui").rglob("test_lpr_*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if ".play_camera(" in path.read_text(encoding="utf-8"):
            assert rel in SHARED_STATE, f"{rel} plays a camera on the LPR page: add it to SHARED_STATE and to account_lpr"


def test_a_command_line_dist_that_undoes_the_grouping_is_refused():
    """-n with any --dist but loadgroup is refused at configure time; -n alone and no -n pass."""
    with pytest.raises(pytest.UsageError, match="use -n alone"):
        conftest.pytest_configure(_config(4, "loadfile"))
    with pytest.raises(pytest.UsageError):
        conftest.pytest_configure(_config(2, "load"))
    conftest.pytest_configure(_config(4, "loadgroup"))   # the ini's own setting
    conftest.pytest_configure(_config(0, "loadfile"))    # -n 0: no workers, nothing to group
    conftest.pytest_configure(_config(None, "no"))
    conftest.pytest_configure(_config(4, "loadfile", loaded=False))  # -p no:xdist: nothing to guard


def test_generated_names_carry_more_than_seconds():
    """Two workers can create in the same second; a name with only %H%M%S
    collides. Page objects and api fixtures name things too, and an export
    file name is a tenant name, so tests/shared is in and nothing is carved out."""
    offenders = []
    for root in ("tests/ui", "tests/shared"):
        for path in sorted((REPO_ROOT / root).rglob("*.py")):
            for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"%H%M%S[\"')}]", line):
                    offenders.append(f"{path.relative_to(REPO_ROOT).as_posix()}:{i}")
    assert not offenders, "second-resolution names (add %f): " + ", ".join(offenders)
