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
            "user_key": "JUSTIN_PROD",
            "email": "qa@soterixsystems.com",
            "password_env": "JUSTIN_PROD_PASSWORD",
            "default_site_id": None,  # TBD
        },
    },
    
    # Default box if not specified
    "default_box": "soterix",
}

# Helper to get active box config
def get_box_config(box_name=None):
    box = box_name or os.environ.get("BOX", config["default_box"])
    return config["boxes"].get(box, config["boxes"][config["default_box"]])

# Helper to get credentials for active box
def get_credentials(box_name=None):
    box_config = get_box_config(box_name)
    password = os.environ.get(box_config["password_env"], "")
    return {
        "email": box_config["email"],
        "password": password,
        "site_id": box_config["default_site_id"],
    }

