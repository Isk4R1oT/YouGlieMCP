from typing import Any

from fastmcp import FastMCP

from yougile_mcp.client import YougileClient
from yougile_mcp.resolvers import resolve_task


def register(mcp: FastMCP, client: YougileClient) -> None:

    @mcp.tool
    async def get_task_comments(
        task: str,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Get all chat messages/comments on a task with resolved author names.

        Args:
            task: Task code (e.g. 'PRJ-123') or task UUID.
            limit: Maximum number of messages to return. Omit for all messages.
        """
        task_data = await resolve_task(client, task)
        task_id = task_data["id"]

        messages = await client.get_chat_messages(task_id, limit, None)

        # Build user map for author resolution
        all_users = await client.get_users(None, None)
        user_map = {u["id"]: u for u in all_users}

        enriched_messages = []
        for msg in messages:
            if msg.get("deleted", False):
                continue
            author_id = msg.get("fromUserId", "")
            author = user_map.get(author_id, {})
            enriched_messages.append({
                "id": msg.get("id", 0),
                "author": author.get("realName", author_id),
                "author_email": author.get("email", ""),
                "text": msg.get("text", ""),
                "timestamp": msg.get("id", 0),
                "reactions": msg.get("reactions", {}),
            })

        return {
            "task": task_data.get("title", task),
            "task_code": task_data.get("idTaskCommon", "") or task_data.get("idTaskProject", ""),
            "message_count": len(enriched_messages),
            "messages": enriched_messages,
        }

    @mcp.tool
    async def add_task_comment(
        task: str,
        text: str,
    ) -> dict[str, Any]:
        """Post a comment/message on a task's chat.

        Args:
            task: Task code (e.g. 'PRJ-123') or task UUID.
            text: Message text to post.
        """
        task_data = await resolve_task(client, task)
        task_id = task_data["id"]

        result = await client.send_chat_message(task_id, text)

        return {
            "task": task_data.get("title", task),
            "message_id": result.get("id", 0),
            "status": "sent",
        }
