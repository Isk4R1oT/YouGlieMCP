import sys

from fastmcp import FastMCP

from yougile_mcp.client import YougileClient
from yougile_mcp.tools import boards, chat, stickers, tasks, users, workspace

SERVER_INSTRUCTIONS = """Yougile project management MCP server.

IMPORTANT: All tools accept human-readable names (project names, board names, column names, user names/emails), NOT UUIDs.
The server resolves names to IDs automatically.

Tasks can be referenced by task code (e.g. 'PRJ-123') or UUID.

Workflow:
1. Use 'list_projects' to discover the workspace structure
2. Use 'get_project_overview' or 'get_board_details' to see columns and tasks
3. Use task tools (create_task, move_task, assign_task, etc.) for task management
4. Use 'add_task_comment' and 'get_task_comments' for task communication
5. Use sticker tools to label tasks with custom categories

If a name is not found, the error will list all available options so you can retry with the correct name.
"""

mcp = FastMCP(
    name="Yougile",
    instructions=SERVER_INSTRUCTIONS,
    version="0.1.0",
)

_client = YougileClient()

workspace.register(mcp, _client)
boards.register(mcp, _client)
tasks.register(mcp, _client)
chat.register(mcp, _client)
users.register(mcp, _client)
stickers.register(mcp, _client)


def setup() -> None:
    """Interactive setup: get API key and save to config."""
    import getpass

    import httpx

    from yougile_mcp.config import save_api_key

    print("=== Yougile MCP Server Setup ===\n")

    email = input("Yougile email: ")
    password = getpass.getpass("Yougile password: ")

    base = "https://ru.yougile.com/api-v2"

    resp = httpx.post(f"{base}/auth/companies", json={"login": email, "password": password})
    if resp.status_code != 200:
        print(f"Authentication failed: {resp.status_code} {resp.text}")
        sys.exit(1)

    companies = resp.json().get("content", [])
    if not companies:
        print("No companies found for this account.")
        sys.exit(1)

    if len(companies) == 1:
        company = companies[0]
    else:
        print("\nCompanies:")
        for i, c in enumerate(companies):
            print(f"  {i + 1}. {c['name']}")
        choice = int(input("Choose number: ")) - 1
        company = companies[choice]

    print(f"Using company: {company['name']}")

    resp = httpx.post(f"{base}/auth/keys", json={
        "login": email,
        "password": password,
        "companyId": company["id"],
    })
    if resp.status_code not in (200, 201):
        print(f"Failed to create API key: {resp.status_code} {resp.text}")
        sys.exit(1)

    api_key = resp.json().get("key", "")
    config_path = save_api_key(api_key)
    print(f"\nAPI key saved to {config_path}")
    print("MCP server is ready to use!")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "setup":
        setup()
    else:
        mcp.run()


if __name__ == "__main__":
    main()
