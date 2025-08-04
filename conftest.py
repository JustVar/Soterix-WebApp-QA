# conftest.py
import os
import importlib
import logging
import pytest
from config.base_config import config

# Setup logging
LOG_FILE = os.path.join("logs", "env_config.log")
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def resolve_tenant_data(tenant_name):
    """Dynamically import tenant login data"""
    try:
        module = importlib.import_module(f"data.{tenant_name}_login_data")
        return module.login_data
    except ModuleNotFoundError:
        raise Exception(f"Tenant login data file not found: data/{tenant_name}_login_data.py")

@pytest.fixture(scope="session")
def env_config():
    """Fixture that returns resolved environment config based on ENV"""
    logging.info(f"[ENV CONFIG] Loaded config for: {os.environ.get('ENV')}")
    return config

@pytest.fixture(scope="session")
def login_data():
    """Fixture to provide tenant login credentials"""
    tenant = os.environ.get("TENANT", "acme")
    logging.info(f"[TENANT CONFIG] Loaded tenant login data for: {tenant}")
    return resolve_tenant_data(tenant)

@pytest.fixture
def login(page, env_config, login_data):
    """Reusable login fixture to authenticate before test"""
    page.goto(env_config["base_url"])
    page.fill("input[type='email']", login_data["username"])
    page.fill("input[type='password']", login_data["password"])
    page.click("button[type='submit']")
    page.wait_for_url(f"**{login_data['expected_landing']}**")
    return page
