"""Helper to dynamically fetch enterpriseId from Site Status API."""
from __future__ import annotations

from typing import Optional
import requests


class EnterpriseHelper:
    """Fetches enterpriseId dynamically from Site Status API."""
    
    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self._enterprise_id_cache: Optional[int] = None
    
    def get_enterprise_id(self, site_id: int) -> int:
        """
        Get enterpriseId by calling Site Status API.
        
        Args:
            site_id: The site ID to query
            
        Returns:
            The enterpriseId for the site
            
        Raises:
            ValueError: If enterpriseId not found in response
        """
        # Return cached value if available
        if self._enterprise_id_cache is not None:
            return self._enterprise_id_cache
        
        url = f"{self.base_url}/REST/dashboard/site/{site_id}/status"
        headers = {
            "Cookie": f"JSESSIONID={self.auth_token}",
            "Content-Type": "application/json",
        }
        
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        
        data = response.json()
        result = data.get("result", {})
        
        enterprise_id = result.get("enterpriseid")
        if enterprise_id is None:
            raise ValueError(f"enterpriseid not found in Site Status response for site {site_id}")
        
        # Cache for future calls
        self._enterprise_id_cache = enterprise_id
        print(f"[ENTERPRISE] Discovered enterpriseId: {enterprise_id} for site: {site_id}")
        
        return enterprise_id
    
    def clear_cache(self):
        """Clear the cached enterpriseId."""
        self._enterprise_id_cache = None
