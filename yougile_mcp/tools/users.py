from typing import Any

from fastmcp import FastMCP

from yougile_mcp.client import YougileClient


def register(mcp: FastMCP, client: YougileClient) -> None:

    @mcp.tool
    async def list_users() -> list[dict[str, Any]]:
        """List all users in the company with their name, email, admin status, and online status."""
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
