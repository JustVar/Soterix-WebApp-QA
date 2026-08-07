import os

config = {
    "base_url": "https://app.example.invalid",
    "api_base_url": "https://app.example.invalid/v-apiserver",

    # Safety flags - production is READ-ONLY
    "allow_write": False,
    "allow_delete": False,

    # Box configurations
    "boxes": {
        "soterix": {
            "email": "test-auto-prod@soterixsystems.com",
            "password_env": "TEST_AUTO_PROD_PASSWORD",
            "default_site_id": None,  # TBD
        },
        # QA production box. Shared account; set HARDWARE_LAB_PASSWORD in .env.
        "hardware-lab": {
            "email": "hardware-lab@soterixsystems.com",
            "password_env": "HARDWARE_LAB_PASSWORD",
            "default_site_id": None,  # TBD
        },
    },

    # Default box if not specified
    "default_box": "soterix",
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

