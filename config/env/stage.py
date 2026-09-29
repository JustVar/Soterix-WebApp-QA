"""The staging server. Same shape as config/env/qa.py. Run with ENV=stage.

Writes are allowed. The site and the camera are None, so a run reads
them from the server (config/env/qa.py explains the keys); media_host is
None until somebody reads it from the browser's network tab there.
"""
import os

from config.secret import Secret

config = {
    "base_url": "https://staging.example.invalid",
    "media_host": None,
    "allow_write": True,
    "default_site_id": None,
    "test_site_name": None,
    "test_camera_name": None,
    "test_chat_user_search": None,
    "test_chat_user_name": None,
    "camera_capabilities": {},
    "without": {},
}


def get_credentials():
    """The account the tests sign in as, from .env, and the site its data goes to."""
    return {"email": os.environ.get("QA_USER", ""),
            "password": Secret(os.environ.get("QA_PASSWORD", "")),
            "site_id": config["default_site_id"]}
