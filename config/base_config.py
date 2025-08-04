import os
import importlib
import logging
from datetime import datetime

# Setup basic logging to file
LOG_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

log_file_path = os.path.join(LOG_DIR, "env_config.log")

logging.basicConfig(
    filename=log_file_path,
    filemode='a',
    format='[%(asctime)s] %(levelname)s: %(message)s',
    level=logging.INFO
)

# Read ENV from environment variable or fallback to "qa"
ENV = os.getenv("ENV", "qa").lower()

def load_config():
    try:
        alias_map = {
            "qa": "qa",
            "stage": "stage",
            "staging": "stage",
            "uat": "stage",
            "prod": "prod",
            "production": "prod",
            "demo": "prod",
            "user": "prod"
        }

        module_name = alias_map.get(ENV)
        if not module_name:
            raise ValueError(f"Unsupported ENV: '{ENV}'")

        msg = f"[ENV CONFIG] Resolved environment alias '{ENV}' -> loading config.env.{module_name}"
        print(msg)
        logging.info(msg)

        module = importlib.import_module(f"config.env.{module_name}")
        return module.config

    except Exception as e:
        error_msg = f"Failed to load config for environment '{ENV}': {e}"
        logging.error(error_msg)
        raise RuntimeError(error_msg)

# Global access
test_config = load_config()
