---
name: yougile-task
description: Show detailed info about a Yougile task including comments. Use when the user wants to see task details.
argument-hint: "<task-code>"
allowed-tools:
  - mcp__yougile__get_task
  - mcp__yougile__get_task_comments
---

Show detailed info about a Yougile task.

Arguments: `$ARGUMENTS` — task code (e.g. ID-582).

Examples:
- `/yougile-task ID-582`
- `/yougile-task ID-1061`

Steps:
1. Parse the task code from `$ARGUMENTS`
2. If no task code provided, ask the user
3. Call both in parallel:
   - `get_task` with the task code
   - `get_task_comments` with the task code
4. Display task details:
   - **Code**: task code
   - **Title**: title
   - **Status**: column name
   - **Project**: project name
   - **Board**: board name
   - **Assigned**: assigned users
   - **Color**: color (if set)
   - **Deadline**: deadline (if set)
   - **Completed**: yes/no
   - **Description**: description (if any)
5. If there are comments, show them in chronological order:
   - Author — date
   - Message text
6. If no comments, say "No comments"
