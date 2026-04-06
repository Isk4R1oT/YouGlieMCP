import asyncio
import datetime
from typing import Annotated, Any, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from yougile_mcp.client import YougileClient
from yougile_mcp.resolvers import (
    enrich_task,
    enrich_task_summary,
    resolve_board,
    resolve_column,
    resolve_project,
    resolve_task,
    resolve_user,
    resolve_users,
)

VALID_COLORS = Literal[
    "task-primary", "task-gray", "task-red", "task-pink",
    "task-yellow", "task-green", "task-turquoise",
    "task-blue", "task-violet",
]


def register(mcp: FastMCP, client: YougileClient) -> None:

    @mcp.tool(
        annotations={"readOnlyHint": False},
        tags={"tasks", "write"},
    )
    async def create_task(
        title: Annotated[str, Field(description="Task title", min_length=1)],
        project: Annotated[str, Field(description="Project name")],
        board: Annotated[str, Field(description="Board name within the project")],
        column: Annotated[str, Field(description="Column name within the board")],
        description: Annotated[
            str | None,
            Field(description="Task description (HTML ok)"),
        ] = None,
        assigned: Annotated[
            list[str] | None,
            Field(description="User names or emails to assign"),
        ] = None,
        deadline: Annotated[
            str | None,
            Field(description="Deadline: YYYY-MM-DD or ISO"),
        ] = None,
        color: Annotated[VALID_COLORS | None, Field(description="Task color")] = None,
    ) -> dict[str, Any]:
        """Create a task in a specific column.

        Resolves project, board, column, and users by name.

        Examples:
          - create_task(title="Draft copy",
              project="Marketing", board="Q1", column="To Do")
          - create_task(title="Fix bug", project="Dev",
              board="Sprint 1", column="Backlog")
        """
        project_id = await resolve_project(client, project)
        board_id = await resolve_board(client, project_id, board)
        column_id = await resolve_column(client, board_id, column)

        body: dict[str, Any] = {
            "title": title,
            "columnId": column_id,
        }

        if description is not None:
            body["description"] = description

        if assigned is not None:
            user_ids = await resolve_users(client, assigned)
            body["assigned"] = user_ids

        if deadline is not None:
            body["deadline"] = _parse_deadline(deadline)

        if color is not None:
            body["color"] = color

        result = await client.create_task(body)

        return {
            "id": result.get("id", ""),
            "title": title,
            "project": project,
            "board": board,
            "column": column,
            "status": "created",
        }

    @mcp.tool(
        annotations={"readOnlyHint": True, "idempotentHint": True},
        tags={"tasks", "read"},
    )
    async def get_task(
        task: Annotated[
            str, Field(description="Task code or UUID")
        ],
    ) -> dict[str, Any]:
        """Get full task details with resolved names."""
        task_data = await resolve_task(client, task)
        return await enrich_task(client, task_data)

    @mcp.tool(
        annotations={"readOnlyHint": False},
        tags={"tasks", "write"},
    )
    async def update_task(
        task: Annotated[
            str, Field(description="Task code or UUID")
        ],
        title: Annotated[
            str | None, Field(description="New title")
        ] = None,
        description: Annotated[
            str | None,
            Field(description="New description (HTML ok)"),
        ] = None,
        deadline: Annotated[
            str | None,
            Field(description="YYYY-MM-DD or 'remove' to clear"),
        ] = None,
        color: Annotated[
            VALID_COLORS | None,
            Field(description="New task color"),
        ] = None,
    ) -> dict[str, Any]:
        """Update task: title, description, deadline, or color.

        Use 'move_task' to change column, 'assign_task' to change assignees,
        'complete_task'/'archive_task' for status changes.
        """
        task_data = await resolve_task(client, task)
        body: dict[str, Any] = {}

        if title is not None:
            body["title"] = title
        if description is not None:
            body["description"] = description
        if deadline is not None:
            if deadline == "remove":
                body["deadline"] = {"deleted": True}
            else:
                body["deadline"] = _parse_deadline(deadline)
        if color is not None:
            body["color"] = color

        if not body:
            raise ToolError(
                "No update fields provided. Specify at least one of: "
                "title, description, deadline, color."
            )

        await client.update_task(task_data["id"], body)

        return {
            "task": task_data.get("title", task),
            "id": task_data["id"],
            "updated_fields": list(body.keys()),
            "status": "updated",
        }

    @mcp.tool(
        annotations={"readOnlyHint": False},
        tags={"tasks", "write"},
    )
    async def move_task(
        task: Annotated[
            str, Field(description="Task code or UUID")
        ],
        column: Annotated[
            str, Field(description="Target column name")
        ],
        board: Annotated[
            str | None,
            Field(description="Target board (omit to keep current)"),
        ] = None,
        project: Annotated[
            str | None,
            Field(description="Target project (omit to keep current)"),
        ] = None,
    ) -> dict[str, Any]:
        """Move a task to a different column.

        Optionally move to a different board/project.

        Examples:
          - move_task(task="PRJ-123", column="Done")
          - move_task(task="PRJ-123", column="Backlog",
              board="Sprint 2")
        """
        task_data = await resolve_task(client, task)

        # Determine target board
        if board is not None:
            if project is not None:
                project_id = await resolve_project(client, project)
            else:
                # Get current project from task's column chain
                current_column = await client.get_column(task_data["columnId"])
                current_board = await client.get_board(current_column["boardId"])
                project_id = current_board["projectId"]
            board_id = await resolve_board(client, project_id, board)
        else:
            current_column = await client.get_column(task_data["columnId"])
            board_id = current_column["boardId"]

        column_id = await resolve_column(client, board_id, column)

        old_column = await client.get_column(task_data["columnId"])
        old_column_name = old_column.get("title", "?")

        await client.update_task(task_data["id"], {"columnId": column_id})

        return {
            "task": task_data.get("title", task),
            "from_column": old_column_name,
            "to_column": column,
            "status": "moved",
        }

    @mcp.tool(
        annotations={"readOnlyHint": False},
        tags={"tasks", "write"},
    )
    async def assign_task(
        task: Annotated[
            str, Field(description="Task code or UUID")
        ],
        assign: Annotated[
            list[str] | None,
            Field(description="Users to add as assignees"),
        ] = None,
        unassign: Annotated[
            list[str] | None,
            Field(description="Users to remove from assignees"),
        ] = None,
    ) -> dict[str, Any]:
        """Assign or unassign users on a task."""
        if assign is None and unassign is None:
            raise ToolError(
                "Provide at least one of 'assign' or 'unassign' lists."
            )

        task_data = await resolve_task(client, task)
        current_assigned = set(task_data.get("assigned", []))

        if assign is not None:
            add_ids = await resolve_users(client, assign)
            current_assigned.update(add_ids)

        if unassign is not None:
            remove_ids = await resolve_users(client, unassign)
            current_assigned -= set(remove_ids)

        await client.update_task(
            task_data["id"],
            {"assigned": list(current_assigned)},
        )

        # Resolve final names
        all_users = await client.get_users(None, None)
        user_map = {u["id"]: u for u in all_users}
        final_names = [
            user_map.get(uid, {}).get("realName", uid)
            for uid in current_assigned
        ]

        return {
            "task": task_data.get("title", task),
            "assigned_users": final_names,
            "status": "updated",
        }

    @mcp.tool(
        annotations={"readOnlyHint": False},
        tags={"tasks", "write"},
    )
    async def complete_task(
        task: Annotated[
            str, Field(description="Task code or UUID")
        ],
        completed: Annotated[
            bool,
            Field(description="True to complete, False to reopen"),
        ],
    ) -> dict[str, Any]:
        """Mark a task as completed or reopen it."""
        task_data = await resolve_task(client, task)
        await client.update_task(task_data["id"], {"completed": completed})
        action = "completed" if completed else "reopened"
        return {
            "task": task_data.get("title", task),
            "status": action,
        }

    @mcp.tool(
        annotations={"readOnlyHint": False, "destructiveHint": True},
        tags={"tasks", "write"},
    )
    async def archive_task(
        task: Annotated[
            str, Field(description="Task code or UUID")
        ],
        archived: Annotated[
            bool,
            Field(description="True to archive, False to restore"),
        ],
    ) -> dict[str, Any]:
        """Archive a task or restore it from archive."""
        task_data = await resolve_task(client, task)
        await client.update_task(task_data["id"], {"archived": archived})
        action = "archived" if archived else "restored"
        return {
            "task": task_data.get("title", task),
            "status": action,
        }

    @mcp.tool(
        annotations={"readOnlyHint": False},
        tags={"tasks", "write"},
    )
    async def manage_checklist(
        task: Annotated[
            str, Field(description="Task code or UUID")
        ],
        add_items: Annotated[
            list[str] | None,
            Field(description="Item texts to add"),
        ] = None,
        check_items: Annotated[
            list[str] | None,
            Field(description="Item texts to mark completed"),
        ] = None,
        uncheck_items: Annotated[
            list[str] | None,
            Field(description="Item texts to uncheck"),
        ] = None,
        remove_items: Annotated[
            list[str] | None,
            Field(description="Item texts to remove"),
        ] = None,
        checklist_title: Annotated[
            str | None,
            Field(description="Checklist title (default: 'Checklist')"),
        ] = None,
    ) -> dict[str, Any]:
        """Add, check, uncheck, or remove checklist items on a task.

        If no checklist exists, one will be created. Items are matched by title text.

        Examples:
          - manage_checklist(task="PRJ-123", add_items=["Write tests", "Update docs"])
          - manage_checklist(task="PRJ-123", check_items=["Write tests"])
        """
        actions = [add_items, check_items, uncheck_items, remove_items]
        if all(x is None for x in actions):
            raise ToolError(
                "Provide at least one of: add_items,"
                " check_items, uncheck_items, remove_items."
            )

        task_data = await resolve_task(client, task)
        checklists = task_data.get("checklists", [])

        effective_title = (
            checklist_title if checklist_title is not None
            else "Checklist"
        )

        # Find or create target checklist
        target = None
        for cl in checklists:
            if cl.get("title", "").lower() == effective_title.lower():
                target = cl
                break

        if target is None:
            target = {"title": effective_title, "items": []}
            checklists.append(target)

        items = target.get("items", [])

        # Remove items
        if remove_items is not None:
            remove_lower = {r.lower() for r in remove_items}
            items = [i for i in items if i.get("title", "").lower() not in remove_lower]

        # Check items
        if check_items is not None:
            check_lower = {c.lower() for c in check_items}
            for item in items:
                if item.get("title", "").lower() in check_lower:
                    item["isCompleted"] = True

        # Uncheck items
        if uncheck_items is not None:
            uncheck_lower = {u.lower() for u in uncheck_items}
            for item in items:
                if item.get("title", "").lower() in uncheck_lower:
                    item["isCompleted"] = False

        # Add items
        if add_items is not None:
            for text in add_items:
                items.append({"title": text, "isCompleted": False})

        target["items"] = items
        await client.update_task(task_data["id"], {"checklists": checklists})

        return {
            "task": task_data.get("title", task),
            "checklist": effective_title,
            "items": [
                {"title": i["title"], "completed": i.get("isCompleted", False)}
                for i in items
            ],
            "status": "updated",
        }

    @mcp.tool(
        annotations={"readOnlyHint": True, "idempotentHint": True},
        tags={"tasks", "read"},
    )
    async def search_tasks(
        title: Annotated[
            str | None,
            Field(description="Search by title substring"),
        ] = None,
        assigned_to: Annotated[
            str | None,
            Field(description="Filter by user name or email"),
        ] = None,
        project: Annotated[
            str | None,
            Field(description="Filter by project name"),
        ] = None,
        board: Annotated[
            str | None,
            Field(description="Filter by board (needs project)"),
        ] = None,
        column: Annotated[
            str | None,
            Field(description="Filter by column (needs board)"),
        ] = None,
        completed: Annotated[
            bool | None,
            Field(description="Filter by completion status"),
        ] = None,
        limit: Annotated[
            int | None,
            Field(description="Max results", ge=1, le=200),
        ] = None,
    ) -> dict[str, Any]:
        """Search tasks by title, assignee, column, board, or project.

        At least one filter required. Use 'get_user_tasks'
        for a user's full task overview grouped by column.
        """
        filters = [title, assigned_to, project, board, column]
        if all(x is None for x in filters):
            raise ToolError(
                "Provide at least one filter: title,"
                " assigned_to, project, board, or column."
            )

        effective_limit = limit if limit is not None else 50

        # Build API filters
        column_id = None
        assigned_user_id = None

        if column is not None:
            if board is None or project is None:
                raise ToolError(
                    "Column filter requires 'board' and 'project'."
                )
            project_id = await resolve_project(client, project)
            board_id = await resolve_board(client, project_id, board)
            column_id = await resolve_column(client, board_id, column)
        elif board is not None:
            if project is None:
                raise ToolError(
                    "Board filter requires 'project'."
                )
            project_id = await resolve_project(client, project)
            board_id = await resolve_board(client, project_id, board)
            columns_data = await client.get_columns(board_id, None)
            active_cols = [c for c in columns_data if not c.get("deleted", False)]
            task_lists = await asyncio.gather(*[
                client.get_tasks(col["id"], None, title, effective_limit)
                for col in active_cols
            ])
            raw_tasks: list[dict[str, Any]] = []
            for task_list in task_lists:
                raw_tasks.extend(task_list)
            column_id = None
        elif project is not None:
            project_id = await resolve_project(client, project)
            boards_data = await client.get_boards(project_id, None)
            active_boards = [b for b in boards_data if not b.get("deleted", False)]
            col_lists = await asyncio.gather(*[
                client.get_columns(b["id"], None) for b in active_boards
            ])
            all_cols = []
            for col_list in col_lists:
                all_cols.extend(c for c in col_list if not c.get("deleted", False))
            task_lists = await asyncio.gather(*[
                client.get_tasks(col["id"], None, title, effective_limit)
                for col in all_cols
            ])
            raw_tasks = []
            for task_list in task_lists:
                raw_tasks.extend(task_list)
            column_id = None

        if assigned_to is not None:
            assigned_user_id = await resolve_user(client, assigned_to)

        # If we haven't fetched tasks yet (simple column or assigned filter)
        if column_id is not None or (board is None and project is None):
            raw_tasks = await client.get_tasks(
                column_id, assigned_user_id, title, effective_limit,
            )

        # Post-filter by assigned_to if needed
        if assigned_user_id is not None and (board is not None or project is not None):
            raw_tasks = [
                t for t in raw_tasks
                if assigned_user_id in t.get("assigned", [])
            ]

        # Post-filter by completed
        if completed is not None:
            raw_tasks = [
                t for t in raw_tasks
                if t.get("completed", False) == completed
            ]

        # Limit results
        raw_tasks = raw_tasks[:effective_limit]

        # Enrich results
        all_users = await client.get_users(None, None)
        user_map = {u["id"]: u for u in all_users}
        column_cache: dict[str, str] = {}

        enriched = []
        for t in raw_tasks:
            if t.get("deleted", False):
                continue
            summary = await enrich_task_summary(client, t, column_cache, user_map)
            enriched.append(summary)

        return {
            "count": len(enriched),
            "tasks": enriched,
        }

    @mcp.tool(
        annotations={"readOnlyHint": True, "idempotentHint": True},
        tags={"tasks", "read"},
    )
    async def get_user_tasks(
        user: Annotated[
            str, Field(description="User name or email")
        ],
        limit: Annotated[
            int | None,
            Field(description="Max results", ge=1, le=200),
        ] = None,
    ) -> dict[str, Any]:
        """Get tasks assigned to a user, grouped by column.

        Use instead of 'search_tasks' for a user overview.
        """
        user_id = await resolve_user(client, user)
        effective_limit = limit if limit is not None else 100

        raw_tasks = await client.get_tasks(None, user_id, None, effective_limit)

        # Build caches
        all_users = await client.get_users(None, None)
        user_map = {u["id"]: u for u in all_users}
        column_cache: dict[str, str] = {}

        # Group by column
        grouped: dict[str, list[dict[str, Any]]] = {}
        for t in raw_tasks:
            if t.get("deleted", False):
                continue
            summary = await enrich_task_summary(client, t, column_cache, user_map)
            col_name = summary.get("column_name", "No Column")
            if col_name not in grouped:
                grouped[col_name] = []
            grouped[col_name].append(summary)

        user_data = user_map.get(user_id, {})
        user_display = user_data.get("realName", user_data.get("email", user))

        return {
            "user": user_display,
            "total_tasks": sum(len(v) for v in grouped.values()),
            "by_column": grouped,
        }


def _parse_deadline(deadline_str: str) -> dict[str, Any]:
    """Parse ISO date string to Yougile deadline object."""
    try:
        if "T" in deadline_str:
            dt = datetime.datetime.fromisoformat(deadline_str)
            with_time = True
        else:
            dt = datetime.datetime.fromisoformat(deadline_str + "T23:59:59")
            with_time = False

        timestamp = int(dt.timestamp() * 1000)

        return {
            "deadline": timestamp,
            "withTime": with_time,
        }
    except ValueError:
        raise ToolError(
            f"Invalid deadline format: '{deadline_str}'. "
            "Use ISO format: YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS"
        )
