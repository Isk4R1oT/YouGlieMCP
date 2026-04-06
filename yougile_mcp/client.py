import asyncio
import logging
import time
from typing import Any

import httpx

from yougile_mcp.config import get_api_key
from yougile_mcp.errors import api_error, missing_key_error

logger = logging.getLogger("yougile_mcp")

BASE_URL = "https://ru.yougile.com/api-v2"
TIMEOUT = 30.0
MAX_RETRIES = 3
RETRY_BACKOFF = 1.0
PAGE_LIMIT = 1000
CACHE_TTL = 30.0


class YougileClient:
    """HTTP client for Yougile API v2 with retry, pagination, auth, and TTL cache."""

    def __init__(self) -> None:
        self._api_key: str | None = None
        self._http: httpx.AsyncClient | None = None
        self._cache: dict[str, tuple[float, Any]] = {}

    def _cache_get(self, key: str) -> Any | None:
        """Return cached value if not expired, else None."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        ts, data = entry
        if time.monotonic() - ts > CACHE_TTL:
            del self._cache[key]
            return None
        return data

    def _cache_set(self, key: str, data: Any) -> None:
        self._cache[key] = (time.monotonic(), data)

    def _ensure_api_key(self) -> str:
        if self._api_key is None:
            api_key = get_api_key()
            if not api_key:
                raise missing_key_error()
            self._api_key = api_key
        return self._api_key

    async def _get_http(self) -> httpx.AsyncClient:
        api_key = self._ensure_api_key()
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(
                base_url=BASE_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=TIMEOUT,
            )
        return self._http

    async def _request(
        self,
        method: str,
        path: str,
        json_body: dict[str, Any] | None,
        params: dict[str, Any] | None,
    ) -> httpx.Response:
        http = await self._get_http()
        last_error: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                response = await http.request(
                    method=method,
                    url=path,
                    json=json_body,
                    params=params,
                )
                if response.status_code >= 500:
                    last_error = api_error(
                        method, path, response.status_code, response.text
                    )
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(
                            "Yougile API %s %s returned %d, retrying (%d/%d)",
                            method, path, response.status_code,
                            attempt + 1, MAX_RETRIES,
                        )
                        await asyncio.sleep(RETRY_BACKOFF * (2 ** attempt))
                        continue
                    raise last_error

                if response.status_code >= 400:
                    raise api_error(
                        method, path, response.status_code, response.text
                    )

                return response

            except httpx.HTTPError as exc:
                last_error = exc
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        "Yougile API network error on %s %s: %s, retrying (%d/%d)",
                        method, path, str(exc),
                        attempt + 1, MAX_RETRIES,
                    )
                    await asyncio.sleep(RETRY_BACKOFF * (2 ** attempt))
                    continue
                raise api_error(
                    method, path, 0, f"Network error after {MAX_RETRIES} retries: {exc}"
                ) from exc

        raise last_error  # type: ignore[misc]

    async def get(
        self,
        path: str,
        params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        response = await self._request("GET", path, None, params)
        return response.json()

    async def post(
        self,
        path: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._request("POST", path, body, None)
        return response.json()

    async def put(
        self,
        path: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        response = await self._request("PUT", path, body, None)
        return response.json()

    async def delete(self, path: str) -> dict[str, Any]:
        response = await self._request("DELETE", path, None, None)
        if response.status_code == 204 or not response.text:
            return {}
        return response.json()

    async def paginate(
        self,
        path: str,
        params: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        """Fetch all pages from a paginated endpoint."""
        all_items: list[dict[str, Any]] = []
        offset = 0
        effective_params = dict(params) if params else {}

        while True:
            effective_params["limit"] = PAGE_LIMIT
            effective_params["offset"] = offset
            data = await self.get(path, effective_params)

            content = data.get("content", [])
            all_items.extend(content)

            paging = data.get("paging", {})
            if not paging.get("next", False):
                break

            offset += len(content)

        return all_items

    # --- Convenience methods for each entity ---

    async def get_projects(
        self,
        title: str | None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if title is not None:
            params["title"] = title
        if not params:
            cached = self._cache_get("projects")
            if cached is not None:
                return cached
            result = await self.paginate("/projects", params)
            self._cache_set("projects", result)
            return result
        return await self.paginate("/projects", params)

    async def get_project(self, project_id: str) -> dict[str, Any]:
        cache_key = f"project:{project_id}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        result = await self.get(f"/projects/{project_id}", None)
        self._cache_set(cache_key, result)
        return result

    async def get_boards(
        self,
        project_id: str | None,
        title: str | None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if project_id is not None:
            params["projectId"] = project_id
        if title is not None:
            params["title"] = title
        if title is None and project_id is not None:
            cache_key = f"boards:{project_id}"
            cached = self._cache_get(cache_key)
            if cached is not None:
                return cached
            result = await self.paginate("/boards", params)
            self._cache_set(cache_key, result)
            return result
        return await self.paginate("/boards", params)

    async def get_board(self, board_id: str) -> dict[str, Any]:
        cache_key = f"board:{board_id}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        result = await self.get(f"/boards/{board_id}", None)
        self._cache_set(cache_key, result)
        return result

    async def create_board(
        self,
        title: str,
        project_id: str,
    ) -> dict[str, Any]:
        return await self.post("/boards", {"title": title, "projectId": project_id})

    async def get_columns(
        self,
        board_id: str | None,
        title: str | None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if board_id is not None:
            params["boardId"] = board_id
        if title is not None:
            params["title"] = title
        return await self.paginate("/columns", params)

    async def get_column(self, column_id: str) -> dict[str, Any]:
        cache_key = f"column:{column_id}"
        cached = self._cache_get(cache_key)
        if cached is not None:
            return cached
        result = await self.get(f"/columns/{column_id}", None)
        self._cache_set(cache_key, result)
        return result

    async def create_column(
        self,
        title: str,
        board_id: str,
        color: int | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"title": title, "boardId": board_id}
        if color is not None:
            body["color"] = color
        return await self.post("/columns", body)

    async def get_tasks(
        self,
        column_id: str | None,
        assigned_to: str | None,
        title: str | None,
        limit: int | None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if column_id is not None:
            params["columnId"] = column_id
        if assigned_to is not None:
            params["assignedTo"] = assigned_to
        if title is not None:
            params["title"] = title
        if limit is not None:
            params["limit"] = limit
            return (await self.get("/task-list", params)).get("content", [])
        return await self.paginate("/task-list", params)

    async def get_task(self, task_id: str) -> dict[str, Any]:
        return await self.get(f"/tasks/{task_id}", None)

    async def create_task(self, body: dict[str, Any]) -> dict[str, Any]:
        return await self.post("/tasks", body)

    async def update_task(
        self,
        task_id: str,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        return await self.put(f"/tasks/{task_id}", body)

    async def get_users(
        self,
        email: str | None,
        project_id: str | None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if email is not None:
            params["email"] = email
        if project_id is not None:
            params["projectId"] = project_id
        if not params:
            cached = self._cache_get("users")
            if cached is not None:
                return cached
            result = await self.paginate("/users", params)
            self._cache_set("users", result)
            return result
        return await self.paginate("/users", params)

    async def get_user(self, user_id: str) -> dict[str, Any]:
        return await self.get(f"/users/{user_id}", None)

    async def get_string_stickers(
        self,
        board_id: str | None,
        name: str | None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if board_id is not None:
            params["boardId"] = board_id
        if name is not None:
            params["name"] = name
        if not params:
            cached = self._cache_get("stickers")
            if cached is not None:
                return cached
            result = await self.paginate("/string-stickers", params)
            self._cache_set("stickers", result)
            return result
        return await self.paginate("/string-stickers", params)

    async def get_string_sticker(self, sticker_id: str) -> dict[str, Any]:
        return await self.get(f"/string-stickers/{sticker_id}", None)

    async def get_chat_messages(
        self,
        chat_id: str,
        limit: int | None,
        since: int | None,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if limit is not None:
            params["limit"] = limit
        if since is not None:
            params["since"] = since
        return await self.paginate(f"/chats/{chat_id}/messages", params)

    async def send_chat_message(
        self,
        chat_id: str,
        text: str,
    ) -> dict[str, Any]:
        return await self.post(
            f"/chats/{chat_id}/messages",
            {"text": text, "textHtml": text, "label": ""},
        )

    async def close(self) -> None:
        if self._http is not None and not self._http.is_closed:
            await self._http.aclose()
