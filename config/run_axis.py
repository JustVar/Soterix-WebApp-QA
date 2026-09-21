"""Names for the map of a run page: which camera a test parameter is.

The Camera 2 Cloud suite runs each test on each lab camera, so its run page has a map
of tests by cameras (soterix_qa_shared.reporting.run_page). The package knows a
parameter only as text, `dc-5v-1-q300c5b44`. The registry, tests/data/c2c_cameras.yaml,
knows the model and the address. People name a lab camera by the end of its address
(`.129`), and the error texts use the same address, so that is the column label.

plugins/run_archive.py and plugins/run_report.py register `camera_columns`. A run with
no camera parameter gets None, and the page shows no camera names.
"""
from __future__ import annotations

from pathlib import Path

CAMERAS_YAML = Path(__file__).resolve().parent.parent / "tests" / "data" / "c2c_cameras.yaml"


def camera_columns(params: set[str], registry: Path | None = None) -> dict | None:
    """{'noun': 'camera', 'columns': {param: {'group', 'label', 'title'}}} for the parameters
    that are camera ids in the registry, or None when none is."""
    import yaml
    path = registry or CAMERAS_YAML
    if not path.is_file():
        return None
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    cameras = doc.get("cameras") if isinstance(doc, dict) else doc
    columns = {}
    for cam in cameras or []:
        if not isinstance(cam, dict) or cam.get("id") not in params:
            continue
        ip = str(cam.get("ip") or "")
        title = ", ".join(part for part in (str(cam["id"]), ip, f"firmware {cam['firmware']}" if cam.get("firmware") else "") if part)
        columns[str(cam["id"])] = {
            "group": str(cam.get("model") or ""),
            "label": "." + ip.rsplit(".", 1)[-1] if ip else "",
            "title": title,
        }
    return {"noun": "camera", "columns": columns} if columns else None
