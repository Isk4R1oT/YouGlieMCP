# Yougile MCP Server

MCP (Model Context Protocol) server for [Yougile](https://yougile.com) project management. Lets AI assistants manage projects, boards, tasks, and team collaboration through natural language.

All tools accept **human-readable names** (project names, board names, user emails) instead of UUIDs — the server resolves them automatically.

## Features

- **Workspace** — list projects, get project overview with task counts
- **Boards** — create boards with custom or Kanban columns, view board details
- **Tasks** — create, update, move, assign, complete, archive, search tasks
- **Checklists** — add, check, uncheck, remove checklist items on tasks
- **Comments** — read and post comments on task chats
- **Users** — list company users with online status
- **Stickers** — manage custom labels (e.g. Priority: High, Type: Bug)

## Install in Claude Code

One line — no cloning needed:

**With API key:**
```bash
claude mcp add yougile -e YOUGILE_API_KEY=your-key -- uvx --from git+https://github.com/igorpronin/YouGlieMCP yougile-mcp
```

**With login/password** (API key will be created automatically):
```bash
claude mcp add yougile -e YOUGILE_LOGIN=email -e YOUGILE_PASSWORD=pass -- uvx --from git+https://github.com/igorpronin/YouGlieMCP yougile-mcp
```

Restart Claude Code and the Yougile tools are ready.

> Set `-e YOUGILE_COMPANY=name` if your account has multiple companies.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager

## Available Tools

| Tool | Description |
|------|-------------|
| `list_projects` | List all projects with their boards |
| `get_project_overview` | Project structure with task counts per column |
| `create_board` | Create a board with optional columns |
| `setup_kanban_board` | Create a board with standard Kanban columns |
| `get_board_details` | All columns and tasks for a board |
| `create_task` | Create a task in a specific column |
| `get_task` | Full task details with resolved names |
| `update_task` | Update title, description, deadline, or color |
| `move_task` | Move task to a different column/board |
| `assign_task` | Assign or unassign users |
| `complete_task` | Mark task as completed or reopen |
| `archive_task` | Archive or restore a task |
| `manage_checklist` | Add, check, uncheck, remove checklist items |
| `search_tasks` | Search by title, assignee, project, board, column |
| `get_user_tasks` | All tasks assigned to a user, grouped by column |
| `get_task_comments` | Read comments on a task |
| `add_task_comment` | Post a comment on a task |
| `list_users` | List all company users |
| `list_stickers` | List available stickers and their states |
| `set_task_sticker` | Apply a sticker to a task |
| `remove_task_sticker` | Remove a sticker from a task |

## License

MIT
