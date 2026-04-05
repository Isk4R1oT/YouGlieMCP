# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

MCP (Model Context Protocol) server for [Yougile](https://yougile.com) project management. Built with FastMCP v2+ and httpx. Exposes Yougile's API v2 as MCP tools that accept human-readable names (project/board/column/user names) instead of UUIDs — the server resolves names to IDs automatically.

## Commands

```bash
# Run the MCP server
uv run yougile-mcp

# Interactive setup (API key creation)
uv run yougile-mcp setup

# One-command install (API key + Claude Code MCP registration)
uv run install.py
```

No tests or linter configured yet.

## Architecture

```
yougile_mcp/
  server.py      — FastMCP app entry point, registers all tool modules
  client.py      — YougileClient: async HTTP client with retry, pagination, auth
  config.py      — API key resolution: env var → config file → login/password auto-create
  resolvers.py   — Name-to-ID resolution + task enrichment (column→board→project chain)
  errors.py      — Structured ToolError factories (not_found lists available options)
  types.py       — TypedDict definitions for API responses
  tools/         — One module per domain, each exports register(mcp, client)
    workspace.py — list_projects, get_project_overview
    boards.py    — create_board, setup_kanban_board, get_board_details
    tasks.py     — CRUD, move, assign, complete, archive, checklist, search
    chat.py      — get_task_comments, add_task_comment
    users.py     — list_users
    stickers.py  — list/set/remove stickers (custom labels with states)
```

**Tool registration pattern**: Each `tools/*.py` module defines `register(mcp: FastMCP, client: YougileClient)` which decorates async functions with `@mcp.tool`. All tools receive the shared `YougileClient` instance via closure.

**Name resolution flow**: Tools accept human-readable names → `resolvers.py` fetches all entities, does case-insensitive substring match (exact match takes priority) → raises `ToolError` with available options on not-found or ambiguity.

**Task enrichment**: `enrich_task()` walks the column→board→project chain via individual API calls to resolve IDs back to names. `enrich_task_summary()` is a lightweight version with caching for list views.

## Auth

API key resolved in priority order:
1. `YOUGILE_API_KEY` env var
2. `~/.config/yougile-mcp/config.json`
3. `YOUGILE_LOGIN` + `YOUGILE_PASSWORD` env vars (auto-creates key, saves to config)

## API

All calls go to `https://ru.yougile.com/api-v2`. Client retries up to 3 times with exponential backoff on 5xx/network errors. Pagination uses offset-based `limit`/`offset` params with `paging.next` flag.
