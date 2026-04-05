---
name: yougile-my-tasks
description: Show my tasks in Yougile grouped by status column. Use when the user wants to see their assigned tasks.
argument-hint: "[done]"
allowed-tools:
  - mcp__yougile__get_user_tasks
  - mcp__yougile__list_users
---

Show tasks assigned to the current user in Yougile.

Arguments: `$ARGUMENTS` — optional, pass "done" or "all" to include completed tasks.

Steps:
1. Call `list_users` to find all team members
2. Ask the user which name is theirs (if not previously known from context)
3. Call `get_user_tasks` with the user's name

Display results grouped by column, showing active columns first (in progress, backlog, testing, rework).

For each group, show a markdown table with columns: Code | Title | Assigned

Skip the "Done"/"Completed" column unless the user explicitly asks to see completed tasks or passed "done"/"all" as argument.

At the end, show a summary line: "Total active tasks: N"
