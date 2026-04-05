---
name: yougile-move
description: Move a task to a different column in Yougile. Use when the user wants to change task status or move it between columns.
argument-hint: "<task-code> <target-column>"
allowed-tools:
  - mcp__yougile__move_task
  - mcp__yougile__get_task
  - mcp__yougile__list_projects
  - mcp__yougile__get_board_details
---

Move a task to a different column in Yougile.

Arguments: `$ARGUMENTS` — task code and target column name.

Examples:
- `/yougile-move ID-582 In Progress`
- `/yougile-move ID-1061 Testing`

Steps:
1. Parse the task code and target column from `$ARGUMENTS`
2. If arguments are missing or unclear, ask the user to specify task code and column
3. Call `move_task` with `task` and `column` parameters
4. Confirm the move: "Task {code} moved to '{column}'"
