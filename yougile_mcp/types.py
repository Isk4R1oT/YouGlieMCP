from typing import TypedDict


class UserInfo(TypedDict):
    id: str
    email: str
    real_name: str
    is_admin: bool
    is_online: bool


class ColumnInfo(TypedDict):
    id: str
    title: str
    color: int
    task_count: int


class BoardInfo(TypedDict):
    id: str
    title: str
    columns: list[ColumnInfo]


class ProjectInfo(TypedDict):
    id: str
    title: str
    boards: list[BoardInfo]


class ChecklistItem(TypedDict):
    title: str
    is_completed: bool


class Checklist(TypedDict):
    title: str
    items: list[ChecklistItem]


class StickerLabel(TypedDict):
    sticker_name: str
    state_name: str


class DeadlineInfo(TypedDict):
    deadline: int
    start_date: int
    with_time: bool


class TaskDetail(TypedDict, total=False):
    id: str
    title: str
    description: str
    task_code: str
    project_name: str
    board_name: str
    column_name: str
    assigned_users: list[UserInfo]
    completed: bool
    archived: bool
    deadline: DeadlineInfo
    checklists: list[Checklist]
    sticker_labels: list[StickerLabel]
    color: str
    created_at: int


class TaskSummary(TypedDict, total=False):
    id: str
    title: str
    task_code: str
    column_name: str
    assigned_users: list[str]
    completed: bool
    archived: bool
    color: str


class ChatMessage(TypedDict, total=False):
    id: int
    author_name: str
    author_email: str
    text: str
    timestamp: int
    reactions: dict[str, list[str]]


class StickerInfo(TypedDict):
    id: str
    name: str
    icon: str
    states: list[dict[str, str]]
