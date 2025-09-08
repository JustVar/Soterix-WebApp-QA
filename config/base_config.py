# config/base_config.py
import os
import importlib
import logging
from pathlib import Path
from dotenv import load_dotenv

# Load .env if present (lets you set AUTO_USER/AUTO_PASSWORD, etc.)
load_dotenv()

# Logging setup
LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "env_config.log"
logging.basicConfig(filename=str(LOG_FILE), level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(message)s")

# Map aliases to real environment modules
ENV_ALIAS = {
    "qa":    "config.env.qa",
    "stage": "config.env.stage",
    "staging": "config.env.stage",
    "prod":  "config.env.prod",
    "production": "config.env.prod",
    # keep room for future aliases if needed:
    "uat":   "config.env.stage",   # until a dedicated UAT file exists
    "demo":  "config.env.prod",
    "user":  "config.env.prod",
}

def load_config():
    env = (os.environ.get("ENV") or "qa").strip().lower()
    module_path = ENV_ALIAS.get(env)
    if not module_path:
        raise RuntimeError(f"Unknown ENV '{env}'. Valid: {', '.join(sorted(ENV_ALIAS))}")
    mod = importlib.import_module(module_path)
    cfg = getattr(mod, "config", None)
    if not isinstance(cfg, dict):
        raise RuntimeError(f"{module_path} must define a dict named 'config'")
    logging.info(f"[ENV RESOLVED] ENV='{env}' -> {module_path} | base_url={cfg.get('base_url')}")
    return cfg

# Exposed to the rest of the test suite:
config = load_config()
