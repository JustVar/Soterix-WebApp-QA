"""Pins for config/run_axis.py: the names that the map of a run page gives the lab cameras."""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import run_axis  # noqa: E402

REGISTRY = """cameras:
- id: dc-5v-1-q300c5b44
  ip: 10.2.0.129
  model: DC-5V-1
  firmware: 2025.06.09_A20.3.3
- id: bc-5v-1-pc00c5554
  ip: 10.2.0.171
  model: BC-5V-1
- id: no-address-cam
  model: FC-12F-1
"""


def _registry(tmp_path: Path) -> Path:
    path = tmp_path / "c2c_cameras.yaml"
    path.write_text(REGISTRY, encoding="utf-8")
    return path


def test_a_camera_is_named_by_its_model_and_the_end_of_its_address(tmp_path):
    """The group is the model, the label is the last part of the address, and the title holds the id, the address and the firmware."""
    axis = run_axis.camera_columns({"dc-5v-1-q300c5b44", "bc-5v-1-pc00c5554"}, _registry(tmp_path))
    assert axis["noun"] == "camera"
    assert axis["columns"]["dc-5v-1-q300c5b44"] == {
        "group": "DC-5V-1", "label": ".129", "title": "dc-5v-1-q300c5b44, 10.2.0.129, firmware 2025.06.09_A20.3.3"}
    assert axis["columns"]["bc-5v-1-pc00c5554"]["label"] == ".171"
    assert axis["columns"]["bc-5v-1-pc00c5554"]["title"] == "bc-5v-1-pc00c5554, 10.2.0.171"


def test_a_run_with_no_camera_parameter_gets_no_names(tmp_path):
    """Parameters that are not camera ids, and a registry that is not there, both answer None: the page keeps the parameter text."""
    assert run_axis.camera_columns({"person", "vehicle"}, _registry(tmp_path)) is None
    assert run_axis.camera_columns({"dc-5v-1-q300c5b44"}, tmp_path / "gone.yaml") is None


def test_a_camera_with_no_address_gets_an_empty_label(tmp_path):
    """The package fills an empty label from the parameter text, so the column still has a name."""
    axis = run_axis.camera_columns({"no-address-cam"}, _registry(tmp_path))
    assert axis["columns"]["no-address-cam"]["label"] == ""
    assert axis["columns"]["no-address-cam"]["group"] == "FC-12F-1"


def test_the_real_registry_names_each_enabled_camera():
    """The registry in the repo parses, and each enabled camera gets a model and a label that starts with a dot."""
    import yaml
    cameras = yaml.safe_load(run_axis.CAMERAS_YAML.read_text(encoding="utf-8"))["cameras"]
    enabled = {str(c["id"]) for c in cameras if c.get("enabled")}
    assert enabled, "the registry lists no enabled camera"
    axis = run_axis.camera_columns(enabled)
    assert set(axis["columns"]) == enabled
    for column in axis["columns"].values():
        assert column["group"]
        assert column["label"].startswith(".")


def test_both_shims_register_the_names_with_the_package():
    """The archive plugin and the run page CLI give the package this repo's provider."""
    from soterix_qa_shared.reporting import run_page

    import plugins.run_archive
    assert run_page._axis_provider is run_axis.camera_columns
    for shim in ("plugins/run_archive.py", "plugins/run_report.py"):
        assert "configure_axis(camera_columns)" in (REPO_ROOT / shim).read_text(encoding="utf-8")
