import asyncio
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from yougile_mcp.client import YougileClient
from yougile_mcp.resolvers import resolve_board, resolve_project


KANBAN_COLUMNS = ["Backlog", "To Do", "In Progress", "Review", "Done"]


def register(mcp: FastMCP, client: YougileClient) -> None:

    @mcp.tool(
        annotations={"readOnlyHint": False},
        tags={"boards", "write"},
    )
    async def create_board(
        project: Annotated[str, Field(description="Project name")],
        board_name: Annotated[
            str, Field(description="New board name", min_length=1)
        ],
        columns: Annotated[
            list[str] | None,
            Field(description="Column names to create"),
        ] = None,
    ) -> dict[str, Any]:
        """Create a board in a project, optionally with columns.

        Examples:
          - create_board(project="Marketing",
              board_name="Q1", columns=["Ideas", "Done"])
          - create_board(project="Dev", board_name="Bugs")
        """
        project_id = await resolve_project(client, project)
        board_result = await client.create_board(board_name, project_id)
        board_id = board_result["id"]

        created_columns = []
        if columns is not None:
            for col_name in columns:
                col_result = await client.create_column(col_name, board_id, None)
                created_columns.append({"name": col_name, "id": col_result["id"]})

        return {
            "board": board_name,
            "board_id": board_id,
            "project": project,
            "columns": created_columns,
        }

    @mcp.tool(
        annotations={"readOnlyHint": False},
        tags={"boards", "write"},
    )
    async def setup_kanban_board(
        project: Annotated[str, Field(description="Project name")],
        board_name: Annotated[
            str, Field(description="New board name", min_length=1)
        ],
    ) -> dict[str, Any]:
        """Create a board with standard Kanban columns.

        Columns: Backlog, To Do, In Progress, Review, Done.
        """
        project_id = await resolve_project(client, project)
        board_result = await client.create_board(board_name, project_id)
        board_id = board_result["id"]

        created_columns = []
        for col_name in KANBAN_COLUMNS:
            col_result = await client.create_column(col_name, board_id, None)
            created_columns.append({"name": col_name, "id": col_result["id"]})

        return {
            "board": board_name,
            "board_id": board_id,
            "project": project,
            "columns": created_columns,
        }

    @mcp.tool(
        annotations={"readOnlyHint": True, "idempotentHint": True},
        tags={"boards", "read"},
    )
    async def get_board_details(
        project: Annotated[str, Field(description="Project name")],
        board: Annotated[str, Field(description="Board name within the project")],
    ) -> dict[str, Any]:
        """Get all columns and their tasks for a board.

        Returns columns with tasks including title,
        assignees, and completion status.
        Call 'list_projects' first to discover names.
        """
        project_id = await resolve_project(client, project)
        board_id = await resolve_board(client, project_id, board)

        board_data, columns, all_users = await asyncio.gather(
            client.get_board(board_id),
            client.get_columns(board_id, None),
            client.get_users(None, None),
        )

        user_map = {u["id"]: u for u in all_users}
        active_columns = [c for c in columns if not c.get("deleted", False)]

        task_lists = await asyncio.gather(*[
            client.get_tasks(col["id"], None, None, None)
            for col in active_columns
        ])

        col_details = []
        for col, tasks in zip(active_columns, task_lists):
            task_summaries = []
            for t in tasks:
                if t.get("deleted", False):
                    continue
                assigned_names = [
                    user_map.get(uid, {}).get("realName", uid)
                    for uid in t.get("assigned", [])
                ]
                task_summaries.append({
                    "id": t.get("id", ""),
                    "title": t.get("title", ""),
                    "task_code": (
                        t.get("idTaskCommon", "")
                        or t.get("idTaskProject", "")
                    ),
                    "assigned": assigned_names,
                    "completed": t.get("completed", False),
                    "color": t.get("color", ""),
                })
            col_details.append({
                "name": col.get("title", ""),
                "id": col["id"],
                "color": col.get("color", 0),
                "tasks": task_summaries,
            })

        return {
            "board": board_data.get("title", ""),
            "board_id": board_id,
            "project": project,
            "columns": col_details,
        }
