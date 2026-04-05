from fastmcp.exceptions import ToolError


def not_found_error(entity_type: str, name: str, available: list[str]) -> ToolError:
    available_str = ", ".join(available[:20])
    if len(available) > 20:
        available_str += f" ... and {len(available) - 20} more"
    return ToolError(
        f"{entity_type} '{name}' not found. "
        f"Available: [{available_str}]"
    )


def ambiguous_error(entity_type: str, name: str, matches: list[str]) -> ToolError:
    matches_str = ", ".join(matches[:10])
    return ToolError(
        f"Multiple {entity_type}s match '{name}': {matches_str}. "
        f"Please specify the exact name."
    )


def empty_collection_error(
    entity_type: str,
    parent_type: str,
    parent_name: str,
    suggestion: str,
) -> ToolError:
    return ToolError(
        f"No {entity_type}s found in {parent_type} '{parent_name}'. "
        f"{suggestion}"
    )


def api_error(method: str, path: str, status: int, body: str) -> ToolError:
    if status == 401:
        return ToolError(
            "Yougile authentication failed. "
            "Check that YOUGILE_API_KEY is valid and not expired."
        )
    if status == 403:
        return ToolError(
            f"Access denied: {method} {path}. "
            "Your API key may not have permission for this operation."
        )
    if status == 404:
        return ToolError(
            f"Yougile resource not found: {method} {path}. "
            "The resource may have been deleted."
        )
    if status == 429:
        return ToolError(
            "Yougile rate limit reached. Please wait before retrying."
        )
    return ToolError(
        f"Yougile API error: {method} {path} returned {status}. "
        f"Response: {body[:500]}"
    )


def missing_key_error() -> ToolError:
    return ToolError(
        "Yougile API key not found. Set it up with: "
        "uv run --directory /path/to/YouGlieMCP yougile-mcp setup  "
        "Or set YOUGILE_API_KEY environment variable."
    )


def validation_error(field: str, value: str, expected: str) -> ToolError:
    return ToolError(
        f"Invalid value for '{field}': '{value}'. Expected: {expected}"
    )
