"""
Discovery helper for dynamic camera/site information.
Use when sites and cameras can change at any time.
"""

class DiscoveryHelper:
    def __init__(self, base_api_client):
        self.client = base_api_client

    def get_user_sites(self):
        """Get all sites accessible to current user"""
        endpoints = [
            "/REST/central/user/session",
            "/REST/site",
        ]
        sites = []
        for ep in endpoints:
            try:
                resp = self.client.get(ep)
            except Exception:
                continue
            if resp is None:
                continue
            if resp.status_code != 200:
                continue
            try:
                data = resp.json()
            except Exception:
                continue
            # Common shapes: {"result": [...]}, or list directly
            result = data.get("result") if isinstance(data, dict) else data
            if isinstance(result, list) and result:
                # collect ids from first item shape
                for item in result:
                    if not isinstance(item, dict):
                        continue
                    for k in ("siteId", "site_id", "id"):
                        v = item.get(k)
                        if v:
                            sites.append(v)
                if sites:
                    return sites
        return sites

    def get_site_channels(self, site_id):
        """Get all channels for a site"""
        resp = self.client.get(f"/REST/site/{site_id}/channel")
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("result", [])
            return [ch.get("id") for ch in result if ch.get("id")]
        return []

    def get_snapshot_capable_channels(self, site_id):
        """Get channels that support snapshots"""
        resp = self.client.get(f"/REST/site/{site_id}/channel")
        if resp.status_code == 200:
            data = resp.json()
            result = data.get("result", [])
            return [
                ch.get("id")
                for ch in result
                if ch.get("id") and ch.get("snapUrl")
            ]
        return []

    def discover_all(self, site_id):
        """Get full discovery info for a site"""
        channels = []
        resp = self.client.get(f"/REST/site/{site_id}/channel")
        if resp.status_code == 200:
            data = resp.json()
            for ch in data.get("result", []):
                channels.append({
                    "id": ch.get("id"),
                    "name": ch.get("name"),
                    "model": ch.get("model"),
                    "has_snapshot": bool(ch.get("snapUrl")),
                })
        return {
            "site_id": site_id,
            "total_channels": len(channels),
            "channels": channels,
        }
