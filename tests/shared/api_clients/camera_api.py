"""Camera-related API client."""
from __future__ import annotations

from typing import Any, Dict

from .base_api_client import BaseAPIClient


class CameraAPI(BaseAPIClient):
    def get_camera_tree(self, site_id: int) -> Dict[str, Any]:
        path = f"/REST/site/{site_id}/channel"
        r = self.get(path)
        r.raise_for_status()
        return r.json()

    def get_camera_snapshot(self, site_id: int, channel_id: int) -> bytes:
        path = f"/REST/site/{site_id}/channel/{channel_id}/camera/snap"
        r = self.get(path)
        r.raise_for_status()
        return r.content

    def validate_camera_tree(self, data: Dict[str, Any]) -> bool:
        return isinstance(data, (dict, list))

    def validate_snapshot_is_jpeg(self, data: bytes) -> bool:
        # crude check for JPEG magic bytes
        return data[:3] == b"\xff\xd8\xff"
