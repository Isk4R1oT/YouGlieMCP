from typing import Any

from yougile_mcp.client import YougileClient
from yougile_mcp.errors import ambiguous_error, empty_collection_error, not_found_error


def _match(items: list[dict[str, Any]], key: str, query: str) -> list[dict[str, Any]]:
    """Case-insensitive substring match. Exact match takes priority."""
    query_lower = query.lower().strip()

    exact = [i for i in items if i.get(key, "").lower().strip() == query_lower]
    if exact:
        return exact

    partial = [i for i in items if query_lower in i.get(key, "").lower()]
    return partial


async def resolve_project(
    client: YougileClient,
    project_name: str,
) -> str:
    """Resolve project name to ID. Raises ToolError on not found or ambiguity."""
    projects = await client.get_projects(None)
    if not projects:
        raise empty_collection_error(
            "project", "company", "your workspace",
            "Create a project first in Yougile."
        )

    matches = _match(projects, "title", project_name)

    if len(matches) == 0:
        available = [p["title"] for p in projects]
        raise not_found_error("Project", project_name, available)

    if len(matches) > 1:
        names = [m["title"] for m in matches]
        raise ambiguous_error("project", project_name, names)

    return matches[0]["id"]


async def resolve_board(
    client: YougileClient,
    project_id: str,
    board_name: str,
) -> str:
    """Resolve board name to ID within a project."""
    boards = await client.get_boards(project_id, None)
    if not boards:
        raise empty_collection_error(
            "board", "project", project_id,
            "Create a board first using the 'create_board' tool."
        )

    matches = _match(boards, "title", board_name)

    if len(matches) == 0:
        available = [b["title"] for b in boards]
        raise not_found_error("Board", board_name, available)

    if len(matches) > 1:
        names = [m["title"] for m in matches]
        raise ambiguous_error("board", board_name, names)

    return matches[0]["id"]


async def resolve_column(
    client: YougileClient,
    board_id: str,
    column_name: str,
) -> str:
    """Resolve column name to ID within a board."""
    columns = await client.get_columns(board_id, None)
    if not columns:
        raise empty_collection_error(
            "column", "board", board_id,
            "Create columns first using the 'create_board' tool."
        )

    matches = _match(columns, "title", column_name)

    if len(matches) == 0:
        available = [c["title"] for c in columns]
        raise not_found_error("Column", column_name, available)

    if len(matches) > 1:
        names = [m["title"] for m in matches]
        raise ambiguous_error("column", column_name, names)

    return matches[0]["id"]


async def resolve_user(
    client: YougileClient,
    user_identifier: str,
) -> str:
    """Resolve user by name or email to ID."""
    users = await client.get_users(None, None)
    if not users:
        raise empty_collection_error(
            "user", "company", "your workspace",
            "No users found in the company."
        )

    # Try email match first
    email_matches = _match(users, "email", user_identifier)
    if len(email_matches) == 1:
        return email_matches[0]["id"]

    # Try realName match
    name_matches = _match(users, "realName", user_identifier)
    if len(name_matches) == 1:
        return name_matches[0]["id"]

    # Combine all matches
    all_matches_ids = set()
    all_matches = []
    for m in email_matches + name_matches:
        if m["id"] not in all_matches_ids:
            all_matches_ids.add(m["id"])
            all_matches.append(m)

    if len(all_matches) == 0:
        available = [
            f"{u.get('realName', '?')} ({u.get('email', '?')})" for u in users
        ]
        raise not_found_error("User", user_identifier, available)

    if len(all_matches) > 1:
        names = [
            f"{m.get('realName', '?')} ({m.get('email', '?')})" for m in all_matches
        ]
        raise ambiguous_error("user", user_identifier, names)

    return all_matches[0]["id"]


async def resolve_users(
    client: YougileClient,
    user_identifiers: list[str],
) -> list[str]:
    """Resolve multiple users by name or email to IDs."""
    result = []
    for identifier in user_identifiers:
        user_id = await resolve_user(client, identifier)
        result.append(user_id)
    return result


async def resolve_task(
    client: YougileClient,
    task_identifier: str,
) -> dict[str, Any]:
    """Resolve task by UUID or task code (e.g., 'PRJ-123'). Returns full task data."""
    return await client.get_task(task_identifier)


async def resolve_sticker(
    client: YougileClient,
    sticker_name: str,
) -> dict[str, Any]:
    """Resolve sticker by name. Returns full sticker data including states."""
    stickers = await client.get_string_stickers(None, None)
    if not stickers:
        raise empty_collection_error(
            "sticker", "company", "your workspace",
            "No stickers found. Create stickers in Yougile board settings."
        )

    matches = _match(stickers, "name", sticker_name)

    if len(matches) == 0:
        available = [s["name"] for s in stickers]
        raise not_found_error("Sticker", sticker_name, available)

    if len(matches) > 1:
        names = [m["name"] for m in matches]
        raise ambiguous_error("sticker", sticker_name, names)

    return matches[0]


def resolve_sticker_state(
    sticker: dict[str, Any],
    state_name: str,
) -> str:
    """Resolve sticker state by name. Returns state ID."""
    states = sticker.get("states", [])
    if not states:
        raise empty_collection_error(
            "state", "sticker", sticker.get("name", "?"),
            "This sticker has no states defined."
        )

    matches = _match(states, "name", state_name)

    if len(matches) == 0:
        available = [s["name"] for s in states]
        raise not_found_error("Sticker state", state_name, available)

    if len(matches) > 1:
        names = [m["name"] for m in matches]
        raise ambiguous_error("sticker state", state_name, names)

    return matches[0]["id"]


async def enrich_task(
    client: YougileClient,
    task: dict[str, Any],
) -> dict[str, Any]:
    """Enrich a raw task dict with resolved names for column, board, project, users."""
    enriched: dict[str, Any] = {
        "id": task.get("id", ""),
        "title": task.get("title", ""),
        "description": task.get("description", ""),
        "task_code": task.get("idTaskCommon", "") or task.get("idTaskProject", ""),
        "completed": task.get("completed", False),
        "archived": task.get("archived", False),
        "color": task.get("color", ""),
        "created_at": task.get("timestamp", 0),
    }

    # Resolve column -> board -> project chain
    column_id = task.get("columnId", "")
    if column_id and column_id != "-":
        try:
            column = await client.get_column(column_id)
            enriched["column_name"] = column.get("title", "")
            board_id = column.get("boardId", "")
            if board_id:
                board = await client.get_board(board_id)
                enriched["board_name"] = board.get("title", "")
                project_id = board.get("projectId", "")
                if project_id:
                    project = await client.get_project(project_id)
                    enriched["project_name"] = project.get("title", "")
        except Exception:
            pass

    # Resolve assigned users
    assigned_ids = task.get("assigned", [])
    if assigned_ids:
        users = []
        all_users = await client.get_users(None, None)
        user_map = {u["id"]: u for u in all_users}
        for uid in assigned_ids:
            user = user_map.get(uid)
            if user:
                users.append({
                    "name": user.get("realName", ""),
                    "email": user.get("email", ""),
                })
            else:
                users.append({"name": uid, "email": ""})
        enriched["assigned_users"] = users

    # Resolve stickers
    task_stickers = task.get("stickers", {})
    if task_stickers:
        all_stickers = await client.get_string_stickers(None, None)
        sticker_map = {s["id"]: s for s in all_stickers}
        labels = []
        for sticker_id, state_value in task_stickers.items():
            sticker = sticker_map.get(sticker_id)
            if not sticker:
                continue
            sticker_name = sticker.get("name", sticker_id)
            state_name = str(state_value)
            if state_value and state_value not in ("-", "empty"):
                states = sticker.get("states", [])
                for s in states:
                    if s.get("id") == state_value:
                        state_name = s.get("name", state_value)
                        break
            labels.append({"sticker_name": sticker_name, "state_name": state_name})
        enriched["sticker_labels"] = labels

    # Checklists
    checklists = task.get("checklists", [])
    if checklists:
        enriched["checklists"] = [
            {
                "title": cl.get("title", ""),
                "items": [
                    {
                        "title": item.get("title", ""),
                        "is_completed": item.get("isCompleted", False),
                    }
                    for item in cl.get("items", [])
                ],
            }
            for cl in checklists
        ]

    # Deadline
    deadline = task.get("deadline")
    if deadline and isinstance(deadline, dict):
        enriched["deadline"] = {
            "deadline": deadline.get("deadline", 0),
            "start_date": deadline.get("startDate", 0),
            "with_time": deadline.get("withTime", False),
        }

    return enriched


async def enrich_task_summary(
    client: YougileClient,
    task: dict[str, Any],
    column_name_cache: dict[str, str],
    user_map: dict[str, dict[str, Any]] | None,
) -> dict[str, Any]:
    """Lightweight enrichment for task lists."""
    summary: dict[str, Any] = {
        "id": task.get("id", ""),
        "title": task.get("title", ""),
        "task_code": task.get("idTaskCommon", "") or task.get("idTaskProject", ""),
        "completed": task.get("completed", False),
        "archived": task.get("archived", False),
        "color": task.get("color", ""),
    }

    column_id = task.get("columnId", "")
    if column_id and column_id != "-":
        if column_id not in column_name_cache:
            try:
                column = await client.get_column(column_id)
                column_name_cache[column_id] = column.get("title", "")
            except Exception:
                column_name_cache[column_id] = column_id
        summary["column_name"] = column_name_cache[column_id]

    assigned_ids = task.get("assigned", [])
    if assigned_ids and user_map:
        names = []
        for uid in assigned_ids:
            user = user_map.get(uid)
            if user:
                names.append(user.get("realName", user.get("email", uid)))
            else:
                names.append(uid)
        summary["assigned_users"] = names

    return summary
