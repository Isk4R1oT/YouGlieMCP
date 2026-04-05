#!/usr/bin/env python3
"""One-command installer for Yougile MCP Server.

Usage:
    uv run install.py

Handles API key setup + Claude Code MCP registration in one step.
"""
import getpass
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "yougile-mcp"
CONFIG_FILE = CONFIG_DIR / "config.json"
BASE_URL = "https://ru.yougile.com/api-v2"


def print_header() -> None:
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║     Yougile MCP Server Installer     ║")
    print("  ╚══════════════════════════════════════╝")
    print()


def get_api_key_interactive() -> str:
    print("  How do you want to authenticate?\n")
    print("  1. I have an API key")
    print("  2. Login with email & password (key will be created automatically)")
    print()

    choice = input("  Choose [1/2]: ").strip()

    if choice == "1":
        api_key = input("\n  API key: ").strip()
        if not api_key:
            print("  Error: API key cannot be empty.")
            sys.exit(1)
        return api_key

    if choice == "2":
        return login_flow()

    print("  Invalid choice.")
    sys.exit(1)


def login_flow() -> str:
    try:
        import httpx
    except ImportError:
        print("  Installing httpx...")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "httpx", "-q"],
        )
        import httpx

    print()
    email = input("  Yougile email: ").strip()
    password = getpass.getpass("  Yougile password: ")

    print("\n  Authenticating...", end=" ", flush=True)
    resp = httpx.post(
        f"{BASE_URL}/auth/companies",
        json={"login": email, "password": password},
    )
    if resp.status_code != 200:
        print(f"FAILED\n  Error: {resp.text}")
        sys.exit(1)
    print("OK")

    companies = resp.json().get("content", [])
    if not companies:
        print("  No companies found for this account.")
        sys.exit(1)

    if len(companies) == 1:
        company = companies[0]
    else:
        print(f"\n  Found {len(companies)} companies:\n")
        for i, c in enumerate(companies):
            admin_tag = " (admin)" if c.get("isAdmin") else ""
            print(f"    {i + 1}. {c['name']}{admin_tag}")
        idx = int(input("\n  Choose number: ").strip()) - 1
        company = companies[idx]

    print(f"  Company: {company['name']}")

    print("  Creating API key...", end=" ", flush=True)
    resp = httpx.post(
        f"{BASE_URL}/auth/keys",
        json={"login": email, "password": password, "companyId": company["id"]},
    )
    if resp.status_code not in (200, 201):
        print(f"FAILED\n  Error: {resp.text}")
        sys.exit(1)
    print("OK")

    return resp.json().get("key", "")


def save_key(api_key: str) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps({"api_key": api_key}, indent=2))
    CONFIG_FILE.chmod(0o600)
    print(f"  Key saved to {CONFIG_FILE}")


def register_claude_mcp() -> None:
    claude_bin = shutil.which("claude")
    if not claude_bin:
        print("\n  Claude CLI not found. Add manually:")
        print_manual_instructions()
        return

    project_dir = Path(__file__).resolve().parent

    print("\n  Registering with Claude Code...", end=" ", flush=True)
    result = subprocess.run(
        [
            claude_bin, "mcp", "add",
            "yougile",
            "--",
            "uv", "--directory", str(project_dir), "run", "yougile-mcp",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        print("OK")
    else:
        print(f"FAILED\n  {result.stderr.strip()}")
        print("\n  Add manually:")
        print_manual_instructions()


def print_manual_instructions() -> None:
    project_dir = Path(__file__).resolve().parent
    print(f"\n  claude mcp add yougile -- uv --directory {project_dir} run yougile-mcp")


def main() -> None:
    print_header()

    existing_key = None
    if CONFIG_FILE.exists():
        try:
            existing_key = json.loads(CONFIG_FILE.read_text()).get("api_key")
        except (json.JSONDecodeError, OSError):
            pass

    if existing_key:
        print(f"  Existing API key found in {CONFIG_FILE}")
        reuse = input("  Use existing key? [Y/n]: ").strip().lower()
        if reuse not in ("n", "no"):
            register_claude_mcp()
            print("\n  Done! Restart Claude Code to use Yougile tools.\n")
            return

    api_key = get_api_key_interactive()
    save_key(api_key)
    register_claude_mcp()
    print("\n  Done! Restart Claude Code to use Yougile tools.\n")


if __name__ == "__main__":
    main()
