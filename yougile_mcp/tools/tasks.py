from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

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


def register(mcp: FastMCP, client: YougileClient) -> None:

    @mcp.tool
    async def create_task(
        title: str,
        project: str,
        board: str,
        column: str,
        description: str | None = None,
        assigned: list[str] | None = None,
        deadline: str | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        """Create a task in a specific column. Resolves project, board, column, and users by name.

        Examples:
          - create_task(title="Draft copy", project="Marketing", board="Q1", column="To Do")
          - create_task(title="Fix bug", project="Dev", board="Sprint 1", column="Backlog", assigned=["igor@example.com"])

        Args:
            title: Task title.
            project: Project name.
            board: Board name within the project.
            column: Column name within the board.
            description: Optional task description (supports HTML).
            assigned: Optional list of user names or emails to assign.
            deadline: Optional deadline in ISO format (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS).
            color: Optional task color. One of: task-primary, task-gray, task-red, task-pink, task-yellow, task-green, task-turquoise, task-blue, task-violet.
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
            valid_colors = [
                "task-primary", "task-gray", "task-red", "task-pink",
                "task-yellow", "task-green", "task-turquoise",
                "task-blue", "task-violet",
            ]
            if color not in valid_colors:
                raise ToolError(
                    f"Invalid color '{color}'. "
                    f"Valid colors: {', '.join(valid_colors)}"
                )
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

    @mcp.tool
    async def get_task(task: str) -> dict[str, Any]:
        """Get full details of a task with resolved names for column, board, project, assignees, and stickers.

        Args:
            task: Task code (e.g. 'PRJ-123') or task UUID.
        """
        task_data = await resolve_task(client, task)
        return await enrich_task(client, task_data)

    @mcp.tool
    async def update_task(
        task: str,
        title: str | None = None,
        description: str | None = None,
        deadline: str | None = None,
        color: str | None = None,
    ) -> dict[str, Any]:
        """Update task properties: title, description, deadline, or color.

        Use 'move_task' to change column, 'assign_task' to change assignees,
        'complete_task'/'archive_task' for status changes.

        Args:
            task: Task code (e.g. 'PRJ-123') or task UUID.
            title: New title.
            description: New description (supports HTML).
            deadline: New deadline in ISO format (YYYY-MM-DD). Pass 'remove' to clear deadline.
            color: New color. One of: task-primary, task-gray, task-red, task-pink, task-yellow, task-green, task-turquoise, task-blue, task-violet.
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

    @mcp.tool
    async def move_task(
        task: str,
        column: str,
        board: str | None = None,
        project: str | None = None,
    ) -> dict[str, Any]:
        """Move a task to a different column, optionally in a different board/project.

        If board/project are omitted, moves within the task's current board.

        Examples:
          - move_task(task="PRJ-123", column="Done") — move within current board
          - move_task(task="PRJ-123", column="Backlog", board="Sprint 2") — move to another board

        Args:
            task: Task code (e.g. 'PRJ-123') or task UUID.
            column: Target column name.
            board: Target board name (omit to stay in current board).
            project: Target project name (omit to stay in current project).
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

    @mcp.tool
    async def assign_task(
        task: str,
        assign: list[str] | None = None,
        unassign: list[str] | None = None,
    ) -> dict[str, Any]:
        """Assign or unassign users to/from a task. Resolves user names or emails.

        Args:
            task: Task code (e.g. 'PRJ-123') or task UUID.
            assign: List of user names or emails to add as assignees.
            unassign: List of user names or emails to remove from assignees.
        """
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

    @mcp.tool
    async def complete_task(
        task: str,
        completed: bool,
    ) -> dict[str, Any]:
        """Mark a task as completed or reopen it.

        Args:
            task: Task code (e.g. 'PRJ-123') or task UUID.
            completed: True to complete, False to reopen.
        """
        task_data = await resolve_task(client, task)
        await client.update_task(task_data["id"], {"completed": completed})
        action = "completed" if completed else "reopened"
        return {
            "task": task_data.get("title", task),
            "status": action,
        }

    @mcp.tool
    async def archive_task(
        task: str,
        archived: bool,
    ) -> dict[str, Any]:
        """Archive a task or restore it from archive.

        Args:
            task: Task code (e.g. 'PRJ-123') or task UUID.
            archived: True to archive, False to restore.
        """
        task_data = await resolve_task(client, task)
        await client.update_task(task_data["id"], {"archived": archived})
        action = "archived" if archived else "restored"
        return {
            "task": task_data.get("title", task),
            "status": action,
        }

    @mcp.tool
    async def manage_checklist(
        task: str,
        add_items: list[str] | None = None,
        check_items: list[str] | None = None,
        uncheck_items: list[str] | None = None,
        remove_items: list[str] | None = None,
        checklist_title: str | None = None,
    ) -> dict[str, Any]:
        """Add, check, uncheck, or remove checklist items on a task.

        If no checklist exists, one will be created. Items are matched by title text.

        Args:
            task: Task code (e.g. 'PRJ-123') or task UUID.
            add_items: List of item texts to add to the checklist.
            check_items: List of item texts to mark as completed.
            uncheck_items: List of item texts to mark as not completed.
            remove_items: List of item texts to remove.
            checklist_title: Title for the checklist (defaults to 'Checklist').
        """
        if all(x is None for x in [add_items, check_items, uncheck_items, remove_items]):
            raise ToolError(
                "Provide at least one of: add_items, check_items, uncheck_items, remove_items."
            )

        task_data = await resolve_task(client, task)
        checklists = task_data.get("checklists", [])

        effective_title = checklist_title if checklist_title is not None else "Checklist"

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

    @mcp.tool
    async def search_tasks(
        title: str | None = None,
        assigned_to: str | None = None,
        project: str | None = None,
        board: str | None = None,
        column: str | None = None,
        completed: bool | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Search for tasks by title, assignee, column, board, or project.

        At least one filter must be provided. Results include resolved column and assignee names.

        Args:
            title: Search by title substring.
            assigned_to: Filter by user name or email.
            project: Filter by project name.
            board: Filter by board name (requires project).
            column: Filter by column name (requires project and board).
            completed: Filter by completion status.
            limit: Maximum results (default 50).
        """
        if all(x is None for x in [title, assigned_to, project, board, column]):
            raise ToolError(
                "Provide at least one search filter: title, assigned_to, project, board, or column."
            )

        effective_limit = limit if limit is not None else 50

        # Build API filters
        column_id = None
        assigned_user_id = None

        if column is not None:
            if board is None or project is None:
                raise ToolError(
                    "When filtering by column, you must also specify 'board' and 'project'."
                )
            project_id = await resolve_project(client, project)
            board_id = await resolve_board(client, project_id, board)
            column_id = await resolve_column(client, board_id, column)
        elif board is not None:
            if project is None:
                raise ToolError(
                    "When filtering by board, you must also specify 'project'."
                )
            project_id = await resolve_project(client, project)
            board_id = await resolve_board(client, project_id, board)
            # Get all columns in this board and fetch tasks from each
            columns_data = await client.get_columns(board_id, None)
            all_tasks: list[dict[str, Any]] = []
            for col in columns_data:
                if col.get("deleted", False):
                    continue
                tasks = await client.get_tasks(
                    col["id"], None, title, effective_limit,
                )
                all_tasks.extend(tasks)
            # Filter and enrich below
            raw_tasks = all_tasks
            column_id = None  # already fetched by column
        elif project is not None:
            project_id = await resolve_project(client, project)
            boards_data = await client.get_boards(project_id, None)
            all_tasks = []
            for b in boards_data:
                if b.get("deleted", False):
                    continue
                cols = await client.get_columns(b["id"], None)
                for col in cols:
                    if col.get("deleted", False):
                        continue
                    tasks = await client.get_tasks(
                        col["id"], None, title, effective_limit,
                    )
                    all_tasks.extend(tasks)
            raw_tasks = all_tasks
            column_id = None

        if assigned_to is not None:
            assigned_user_id = await resolve_user(client, assigned_to)

        # If we haven't fetched tasks yet (simple column or assigned filter)
        if column_id is not None or (
            board is None and project is None
        ):
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

    @mcp.tool
    async def get_user_tasks(
        user: str,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """Get all tasks assigned to a specific user, grouped by board and column.

        Args:
            user: User name or email.
            limit: Maximum results (default 100).
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
    import datetime

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
