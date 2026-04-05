---
name: yougile-create
description: Create a new task in Yougile with automatic project/board/column resolution. Use when the user wants to create a task.
argument-hint: "<task title> [assign to <user>]"
allowed-tools:
  - mcp__yougile__create_task
  - mcp__yougile__list_users
  - mcp__yougile__list_projects
  - mcp__yougile__get_project_overview
  - mcp__yougile__get_board_details
---

Create a new task in Yougile.

Arguments: `$ARGUMENTS` — free-form task description, optionally mentioning assignee.

Examples:
- `/yougile-create Fix avatar rendering bug`
- `/yougile-create Add webhook logging, assign to Darya`

Steps:
1. Parse the task title from arguments
2. If no title provided, ask the user
3. Ask the user which project and board to create the task in (if not obvious from context)
4. Call `list_users` to get the list of team members
5. Ask the user who to assign the task to — show the list of available people. If the user already specified an assignee in the arguments, use that. If assignment is not needed, skip.
6. Call `create_task` with:
   - `title`: the task title
   - `project`: user-specified project
   - `board`: user-specified board
   - `column`: default backlog column, unless user specifies otherwise
   - `assigned`: list of selected users (if any)
7. Confirm creation: "Created task {code}: {title}"

If the user specifies a column, deadline, or color — pass those too.
Color options: task-primary, task-gray, task-red, task-pink, task-yellow, task-green, task-turquoise, task-blue, task-violet.
