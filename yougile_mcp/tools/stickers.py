from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from yougile_mcp.client import YougileClient
from yougile_mcp.resolvers import resolve_sticker, resolve_sticker_state, resolve_task


def register(mcp: FastMCP, client: YougileClient) -> None:

    @mcp.tool(
        annotations={"readOnlyHint": True, "idempotentHint": True},
        tags={"stickers", "read"},
    )
    async def list_stickers() -> list[dict[str, Any]]:
        """List all stickers (custom labels) with states.

        Example: Priority sticker with High, Medium, Low.
        """
        raw = await client.get_string_stickers(None, None)
        return [
            {
                "id": s.get("id", ""),
                "name": s.get("name", ""),
                "icon": s.get("icon", ""),
                "states": [
                    {
                        "id": st.get("id", ""),
                        "name": st.get("name", ""),
                        "color": st.get("color", ""),
                    }
                    for st in s.get("states", [])
                ],
            }
            for s in raw
        ]

    @mcp.tool(
        annotations={"readOnlyHint": False},
        tags={"stickers", "write"},
    )
    async def set_task_sticker(
        task: Annotated[
            str, Field(description="Task code or UUID")
        ],
        sticker: Annotated[
            str, Field(description="Sticker name (e.g. 'Priority')")
        ],
        state: Annotated[
            str | None,
            Field(description="State name (e.g. 'High', 'Bug')"),
        ] = None,
    ) -> dict[str, Any]:
        """Apply a sticker to a task with an optional state value.

        Examples:
          - set_task_sticker(task="PRJ-123",
              sticker="Priority", state="High")
          - set_task_sticker(task="PRJ-123", sticker="Type")
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
            "state": (
                state if state is not None
                else "(attached without state)"
            ),
            "status": "applied",
        }

    @mcp.tool(
        annotations={"readOnlyHint": False},
        tags={"stickers", "write"},
    )
    async def remove_task_sticker(
        task: Annotated[
            str, Field(description="Task code or UUID")
        ],
        sticker: Annotated[
            str,
            Field(description="Sticker name to remove"),
        ],
    ) -> dict[str, Any]:
        """Remove a sticker from a task."""
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
