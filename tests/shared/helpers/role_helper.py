"""Helper functions for role-based access checks."""
from typing import List, Dict, Any

# Roles that have full admin access for testing purposes
ADMIN_LEVEL_ROLES = ["Enterprise Super Admin", "Admin"]

# Role IDs that have full admin access (for API checks)
ADMIN_LEVEL_PROFILE_IDS = [102, 103]


def is_admin_role(role_name: str) -> bool:
    """Check if a role name has admin-level access."""
    return role_name in ADMIN_LEVEL_ROLES


def is_admin_profile_id(profile_id: int) -> bool:
    """Check if a profile ID has admin-level access."""
    return profile_id in ADMIN_LEVEL_PROFILE_IDS


def get_user_role_from_roles(roles: List[Dict[str, Any]], user_profile_id: int) -> str:
    """Get the role name for a given profile ID."""
    for role in roles:
        if role.get("profileId") == user_profile_id:
            return role.get("profileName", "Unknown")
    return "Unknown"


def has_admin_access(roles: List[Dict[str, Any]]) -> bool:
    """
    Check if any of the provided roles grant admin-level access.
    
    Args:
        roles: List of role dictionaries with 'profileId' and 'profileName'
        
    Returns:
        True if at least one role is admin-level
    """
    for role in roles:
        if is_admin_role(role.get("profileName", "")):
            return True
        if is_admin_profile_id(role.get("profileId", 0)):
            return True
    return False
