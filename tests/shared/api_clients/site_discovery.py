"""Helper to auto-discover user's sites and enterprise IDs after login."""
from __future__ import annotations

from typing import Dict, List, Optional, Any
import requests


class SiteDiscovery:
    """Discovers available sites and enterprise IDs for the logged-in user."""
    
    def __init__(self, base_url: str, auth_token: str):
        self.base_url = base_url.rstrip("/")
        self.auth_token = auth_token
        self._sites_cache: Optional[List[Dict[str, Any]]] = None
    
    def get_user_sites(self, user_email: str) -> List[Dict[str, Any]]:
        """
        Get all sites available to a user.
        
        Args:
            user_email: The user's email address
            
        Returns:
            List of site objects with siteId, enterpriseId, name, etc.
        """
        if self._sites_cache is not None:
            return self._sites_cache
        
        url = f"{self.base_url}/REST/site/user/{user_email}"
        headers = {
            "Cookie": f"JSESSIONID={self.auth_token}",
            "Content-Type": "application/json",
        }
        
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        
        data = response.json()
        sites = data.get("result", [])
        
        # Cache for future calls
        self._sites_cache = sites
        
        print(f"[SITE DISCOVERY] Found {len(sites)} site(s) for user {user_email}")
        for site in sites:
            print(f"  - {site.get('name')} (Site ID: {site.get('siteId')}, Enterprise ID: {site.get('enterpriseId')})")
        
        return sites
    
    def get_default_site(self, user_email: str) -> Optional[Dict[str, Any]]:
        """Get the first/default site for a user."""
        sites = self.get_user_sites(user_email)
        return sites[0] if sites else None
    
    def get_default_site_id(self, user_email: str) -> Optional[int]:
        """Get the default site ID for a user."""
        site = self.get_default_site(user_email)
        return site.get("siteId") if site else None
    
    def get_default_enterprise_id(self, user_email: str) -> Optional[int]:
        """Get the enterprise ID from the user's default site."""
        site = self.get_default_site(user_email)
        return site.get("enterpriseId") if site else None
    
    def get_site_by_name(self, user_email: str, site_name: str) -> Optional[Dict[str, Any]]:
        """Find a specific site by name."""
        sites = self.get_user_sites(user_email)
        for site in sites:
            if site.get("name", "").lower() == site_name.lower():
                return site
        return None
    
    def clear_cache(self):
        """Clear the cached sites."""
        self._sites_cache = None
