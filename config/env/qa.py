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
    "boxes": {
        "us": {
            "user_key": "TEST_AUTO_QA",
            "email": "test-auto-qa@soterixsystems.com",
            "password_env": "TEST_AUTO_QA_PASSWORD",
            "default_site_id": None,
        },
        "india": {
            "user_key": "JUSTIN",
            "email": "qa@soterixsystems.com",
            "password_env": "JUSTIN_PASSWORD",
            "default_site_id": None,
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
    box_config = get_box_config(box_name)
    password = os.environ.get(box_config["password_env"], "")
    return {
        "email": box_config["email"],
        "password": password,
        "site_id": box_config["default_site_id"],
    }
