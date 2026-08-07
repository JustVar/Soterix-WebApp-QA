import os

config = {
    "base_url": "https://qa.example.invalid",
    "api_base_url": "https://qa.example.invalid/v-apiserver",

    # Safety flags
    "allow_write": True,
    "allow_delete": True,

    # Test Data Configuration
    "test_site_name": "Newtown ActionArea",
    "test_camera_name": "main gate",

    # Box configurations
    # Box configurations. Each box names the environment variables that hold
    # the account to use, so every tester signs in as themselves.
    "boxes": {
        "india": {
            "email_env": "QA_INDIA_USER",
            "password_env": "QA_INDIA_PASSWORD",
            "default_site_id": None,
        },
        "us": {
            "email_env": "QA_US_USER",
            "password_env": "QA_US_PASSWORD",
            "default_site_id": None,
        },
    },

    # Default box if not specified
    "default_box": "india",
}

# Helper to get active box config
def get_box_config(box_name=None):
    box = box_name or os.environ.get("BOX", config["default_box"])
    if box not in config["boxes"]:
        raise KeyError(
            f"Unknown box '{box}' for this environment. "
            f"Valid boxes: {sorted(config['boxes'])}")
    return config["boxes"][box]

# Helper to get credentials for active box
def get_credentials(box_name=None):
    """Credentials for a box.

    A box gives either a literal `email` (shared accounts) or an `email_env`
    naming the variable that holds it (per-tester accounts).
    """
    box_config = get_box_config(box_name)
    email = box_config.get("email") or os.environ.get(
        box_config.get("email_env", ""), "")
    password = os.environ.get(box_config["password_env"], "")
    return {
        "email": email,
        "password": password,
        "site_id": box_config["default_site_id"],
    }
