from typing import Any

from fastmcp import FastMCP

from yougile_mcp.client import YougileClient


def register(mcp: FastMCP, client: YougileClient) -> None:

    @mcp.tool(
        annotations={"readOnlyHint": True, "idempotentHint": True},
        tags={"users", "read"},
    )
    async def list_users() -> list[dict[str, Any]]:
        """List all company users with name, email, and status."""
        raw_users = await client.get_users(None, None)
        return [
            {
                "id": u.get("id", ""),
                "name": u.get("realName", ""),
                "email": u.get("email", ""),
                "is_admin": u.get("isAdmin", False),
                "is_online": u.get("status", "") == "online",
            }
            for u in raw_users
        ]
