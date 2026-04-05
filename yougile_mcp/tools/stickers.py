from typing import Any

from fastmcp import FastMCP

from yougile_mcp.client import YougileClient
from yougile_mcp.resolvers import resolve_sticker, resolve_sticker_state, resolve_task


def register(mcp: FastMCP, client: YougileClient) -> None:

    @mcp.tool
    async def list_stickers() -> list[dict[str, Any]]:
        """List all available stickers (custom labels) with their states. For example: Priority sticker with states High, Medium, Low."""
        raw = await client.get_string_stickers(None, None)
        return [
            {
                "id": s.get("id", ""),
                "name": s.get("name", ""),
                "icon": s.get("icon", ""),
                "states": [
                    {"id": st.get("id", ""), "name": st.get("name", ""), "color": st.get("color", "")}
                    for st in s.get("states", [])
                ],
            }
            for s in raw
        ]

    @mcp.tool
    async def set_task_sticker(
        task: str,
        sticker: str,
        state: str | None = None,
    ) -> dict[str, Any]:
        """Apply a sticker to a task with an optional state value.

        Examples:
          - set_task_sticker(task="PRJ-123", sticker="Priority", state="High")
          - set_task_sticker(task="PRJ-123", sticker="Type") — attaches without state

        Args:
            task: Task code (e.g. 'PRJ-123') or task UUID.
            sticker: Sticker name (e.g. 'Priority', 'Type').
            state: State name within the sticker (e.g. 'High', 'Bug'). Omit to attach without a state.
        """
        task_data = await resolve_task(client, task)
        sticker_data = await resolve_sticker(client, sticker)
        sticker_id = sticker_data["id"]

        if state is not None:
            state_id = resolve_sticker_state(sticker_data, state)
            sticker_value = state_id
        else:
            sticker_value = "empty"

        current_stickers = task_data.get("stickers", {})
        current_stickers[sticker_id] = sticker_value

        await client.update_task(task_data["id"], {"stickers": current_stickers})

        return {
            "task": task_data.get("title", task),
            "sticker": sticker_data["name"],
            "state": state if state is not None else "(attached without state)",
            "status": "applied",
        }

    @mcp.tool
    async def remove_task_sticker(
        task: str,
        sticker: str,
    ) -> dict[str, Any]:
        """Remove a sticker from a task.

        Args:
            task: Task code (e.g. 'PRJ-123') or task UUID.
            sticker: Sticker name to remove (e.g. 'Priority').
        """
        task_data = await resolve_task(client, task)
        sticker_data = await resolve_sticker(client, sticker)
        sticker_id = sticker_data["id"]

        current_stickers = task_data.get("stickers", {})
        current_stickers[sticker_id] = "-"

        await client.update_task(task_data["id"], {"stickers": current_stickers})

        return {
            "task": task_data.get("title", task),
            "sticker": sticker_data["name"],
            "status": "removed",
        }
