from typing import Any

from fastmcp import FastMCP

from yougile_mcp.client import YougileClient
from yougile_mcp.resolvers import resolve_project


def register(mcp: FastMCP, client: YougileClient) -> None:

    @mcp.tool
    async def list_projects() -> list[dict[str, Any]]:
        """List all projects in the company with their boards.

        Returns a list of projects, each containing its boards with IDs and names.
        Use this to discover the workspace structure before working with tasks.
        """
        projects = await client.get_projects(None)
        result = []
        for project in projects:
            if project.get("deleted", False):
                continue
            boards = await client.get_boards(project["id"], None)
            result.append({
                "id": project["id"],
                "name": project.get("title", ""),
                "boards": [
                    {"id": b["id"], "name": b.get("title", "")}
                    for b in boards
                    if not b.get("deleted", False)
                ],
            })
        return result

    @mcp.tool
    async def get_project_overview(project: str) -> dict[str, Any]:
        """Get a detailed overview of a project: all boards, their columns, and task counts per column.

        Use this to understand the full structure and workload distribution of a project.

        Args:
            project: Project name (case-insensitive, substring match).
        """
        project_id = await resolve_project(client, project)
        project_data = await client.get_project(project_id)
        boards = await client.get_boards(project_id, None)

        board_details = []
        total_tasks = 0
        for board in boards:
            if board.get("deleted", False):
                continue
            columns = await client.get_columns(board["id"], None)
            col_details = []
            for col in columns:
                if col.get("deleted", False):
                    continue
                tasks = await client.get_tasks(col["id"], None, None, 0)
                # limit=0 trick doesn't work, use paging count
                tasks_data = await client.get("/task-list", {
                    "columnId": col["id"], "limit": 1, "offset": 0,
                })
                count = tasks_data.get("paging", {}).get("count", 0)
                total_tasks += count
                col_details.append({
                    "name": col.get("title", ""),
                    "id": col["id"],
                    "color": col.get("color", 0),
                    "task_count": count,
                })
            board_details.append({
                "name": board.get("title", ""),
                "id": board["id"],
                "columns": col_details,
            })

        return {
            "project": project_data.get("title", ""),
            "id": project_id,
            "total_tasks": total_tasks,
            "boards": board_details,
        }
