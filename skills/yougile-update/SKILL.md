---
name: yougile-update
description: Update a Yougile task — title, description, deadline, color, completion status, or assignment. Use when the user wants to modify a task.
argument-hint: "<task-code> <what to update>"
allowed-tools:
  - mcp__yougile__update_task
  - mcp__yougile__complete_task
  - mcp__yougile__assign_task
  - mcp__yougile__get_task
  - mcp__yougile__list_users
---

Update a task in Yougile.

Arguments: `$ARGUMENTS` — task code and what to update.

Examples:
- `/yougile-update ID-582 title: New task title`
- `/yougile-update ID-582 deadline: 2026-03-25`
- `/yougile-update ID-582 done`
- `/yougile-update ID-582 color: task-red`
- `/yougile-update ID-582 description: Need to implement X`

Steps:
1. Parse the task code and update fields from arguments
2. If arguments are missing, ask the user what to update
3. Determine what needs to change:
   - Title change -> call `update_task` with `title`
   - Description change -> call `update_task` with `description`
   - Deadline change -> call `update_task` with `deadline` (ISO format)
   - Color change -> call `update_task` with `color`
   - Mark complete ("done", "complete") -> call `complete_task` with `completed: true`
   - Reopen ("reopen") -> call `complete_task` with `completed: false`
   - Assign someone -> call `assign_task` with `assign`
   - Unassign -> call `assign_task` with `unassign`
4. Confirm: "Task {code} updated: {what changed}"
