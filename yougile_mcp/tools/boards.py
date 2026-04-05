from typing import Any

from fastmcp import FastMCP

from yougile_mcp.client import YougileClient
from yougile_mcp.resolvers import resolve_board, resolve_project


KANBAN_COLUMNS = ["Backlog", "To Do", "In Progress", "Review", "Done"]


def register(mcp: FastMCP, client: YougileClient) -> None:

    @mcp.tool
    async def create_board(
        project: str,
        board_name: str,
        columns: list[str] | None = None,
    ) -> dict[str, Any]:
        """Create a new board in a project, optionally with columns in one call.

        Examples:
          - create_board(project="Marketing", board_name="Q1 Campaign", columns=["Ideas", "In Progress", "Done"])
          - create_board(project="Dev", board_name="Bugs") — no columns

        Args:
            project: Project name.
            board_name: Name for the new board.
            columns: Optional list of column names to create in the board.
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

    @mcp.tool
    async def setup_kanban_board(
        project: str,
        board_name: str,
    ) -> dict[str, Any]:
        """Create a board with standard Kanban columns: Backlog, To Do, In Progress, Review, Done.

        Args:
            project: Project name.
            board_name: Name for the new board.
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

    @mcp.tool
    async def get_board_details(
        project: str,
        board: str,
    ) -> dict[str, Any]:
        """Get all columns and their tasks for a specific board.

        Returns the board structure with each column's tasks including title, assignees, and completion status.

        Args:
            project: Project name.
            board: Board name within the project.
        """
        project_id = await resolve_project(client, project)
        board_id = await resolve_board(client, project_id, board)
        board_data = await client.get_board(board_id)
        columns = await client.get_columns(board_id, None)

        # Build user map for name resolution
        all_users = await client.get_users(None, None)
        user_map = {u["id"]: u for u in all_users}

        col_details = []
        for col in columns:
            if col.get("deleted", False):
                continue
            tasks = await client.get_tasks(col["id"], None, None, None)
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
                    "task_code": t.get("idTaskCommon", "") or t.get("idTaskProject", ""),
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
