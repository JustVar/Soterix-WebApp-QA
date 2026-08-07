import os

config = {
    "base_url": "https://staging.example.invalid",
    "api_base_url": "https://staging.example.invalid/v-apiserver",

    # Safety flags - staging allows writes but not deletes
    "allow_write": True,
    "allow_delete": False,

    # Box configurations
    "boxes": {
        "us": {
            "email_env": "STAGE_USER",
            "password_env": "STAGE_PASSWORD",
            "default_site_id": None,  # TBD - update when known
        },
    },

    # Default box if not specified
    "default_box": "us",
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

