import json
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger("yougile_mcp")

CONFIG_DIR = Path.home() / ".config" / "yougile-mcp"
CONFIG_FILE = CONFIG_DIR / "config.json"
BASE_URL = "https://ru.yougile.com/api-v2"


def get_api_key() -> str | None:
    """Get API key from (in priority order):
    1. YOUGILE_API_KEY env var
    2. ~/.config/yougile-mcp/config.json
    3. YOUGILE_LOGIN + YOUGILE_PASSWORD env vars (auto-creates key, saves to config)
    """
    # 1. Direct API key
    key = os.environ.get("YOUGILE_API_KEY")
    if key:
        return key

    # 2. Config file
    if CONFIG_FILE.exists():
        try:
            data = json.loads(CONFIG_FILE.read_text())
            stored_key = data.get("api_key")
            if stored_key:
                return stored_key
        except (json.JSONDecodeError, OSError):
            pass

    # 3. Login + password → auto-create key
    login = os.environ.get("YOUGILE_LOGIN")
    password = os.environ.get("YOUGILE_PASSWORD")
    if login and password:
        key = _create_key_from_credentials(login, password)
        if key:
            save_api_key(key)
            return key

    return None


def _create_key_from_credentials(login: str, password: str) -> str | None:
    """Authenticate with login/password, pick first company, create API key."""
    try:
        resp = httpx.post(
            f"{BASE_URL}/auth/companies",
            json={"login": login, "password": password},
            timeout=30.0,
        )
        if resp.status_code != 200:
            logger.error("Yougile auth failed: %d %s", resp.status_code, resp.text)
            return None

        companies = resp.json().get("content", [])
        if not companies:
            logger.error("No Yougile companies found for %s", login)
            return None

        # Use YOUGILE_COMPANY env var if set, otherwise first company
        company_name = os.environ.get("YOUGILE_COMPANY")
        if company_name:
            company = next(
                (c for c in companies if c["name"].lower() == company_name.lower()),
                None,
            )
            if not company:
                names = [c["name"] for c in companies]
                logger.error(
                    "Company '%s' not found. Available: %s",
                    company_name, ", ".join(names),
                )
                return None
        else:
            company = companies[0]

        logger.info("Using Yougile company: %s", company["name"])

        resp = httpx.post(
            f"{BASE_URL}/auth/keys",
            json={"login": login, "password": password, "companyId": company["id"]},
            timeout=30.0,
        )
        if resp.status_code not in (200, 201):
            logger.error("Failed to create API key: %d %s", resp.status_code, resp.text)
            return None

        return resp.json().get("key")

    except httpx.HTTPError as exc:
        logger.error("Network error during Yougile auth: %s", exc)
        return None


def save_api_key(api_key: str) -> Path:
    """Save API key to config file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"api_key": api_key}, indent=2))
    CONFIG_FILE.chmod(0o600)
    return CONFIG_FILE
