import asyncio
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from yougile_mcp.client import YougileClient
from yougile_mcp.resolvers import resolve_project


def register(mcp: FastMCP, client: YougileClient) -> None:

    @mcp.tool(
        annotations={"readOnlyHint": True, "idempotentHint": True},
        tags={"workspace", "read"},
    )
    async def list_projects() -> list[dict[str, Any]]:
        """List all projects in the company with their boards.

        Returns a list of projects, each containing its boards with IDs and names.
        Call this first to discover the workspace structure before working with tasks.
        """
        projects = await client.get_projects(None)
        active_projects = [p for p in projects if not p.get("deleted", False)]

        board_lists = await asyncio.gather(*[
            client.get_boards(p["id"], None) for p in active_projects
        ])

        result = []
        for project, boards in zip(active_projects, board_lists):
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

    @mcp.tool(
        annotations={"readOnlyHint": True, "idempotentHint": True},
        tags={"workspace", "read"},
    )
    async def get_project_overview(
        project: Annotated[
            str,
            Field(description="Project name (case-insensitive)"),
        ],
    ) -> dict[str, Any]:
        """Get a project overview: boards, columns, task counts.

        Shows structure and workload distribution.
        """
        project_id = await resolve_project(client, project)
        project_data, boards = await asyncio.gather(
            client.get_project(project_id),
            client.get_boards(project_id, None),
        )

        active_boards = [b for b in boards if not b.get("deleted", False)]

        col_lists = await asyncio.gather(*[
            client.get_columns(b["id"], None) for b in active_boards
        ])

        # Gather task counts for all columns in parallel
        all_active_cols: list[
            tuple[dict[str, Any], dict[str, Any]]
        ] = []
        for board, cols in zip(active_boards, col_lists):
            for col in cols:
                if not col.get("deleted", False):
                    all_active_cols.append((board, col))

        count_results = await asyncio.gather(*[
            client.get(
                "/task-list",
                {"columnId": col["id"], "limit": 1, "offset": 0},
            )
            for _, col in all_active_cols
        ])

        # Build column counts map
        col_counts: dict[str, int] = {}
        for (_, col), count_data in zip(all_active_cols, count_results):
            col_counts[col["id"]] = count_data.get("paging", {}).get("count", 0)

        total_tasks = 0
        board_details = []
        for board, cols in zip(active_boards, col_lists):
            col_details = []
            for col in cols:
                if col.get("deleted", False):
                    continue
                count = col_counts.get(col["id"], 0)
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
