"""
UI State Models
Dataclasses for TUI state management
"""
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime


@dataclass
class TaskRow:
    """Represents a task in the task list"""
    task_id: str
    status: str        # lowercase: 'staged', 'running', ...
    description: str
    created_at: Optional[str]
    # Derived fields (not persisted)
    status_emoji: str = ''
    status_color: str = ''


@dataclass
class SelectedTaskState:
    """State for the currently selected task"""
    task_id: Optional[str] = None
    # Cached details to avoid re-query on every render
    details: Optional[dict] = None       # from TaskQueue.get_task().to_dict()
    exec_snippet: str = ''
    files_info: Optional[dict] = None    # parsed _files.json
    summary_info: Optional[dict] = None  # parsed _notification.json
    last_loaded: Optional[datetime] = None

    # Cached log file metadata to detect changes efficiently
    log_mtime: Optional[float] = None
    log_size: Optional[int] = None


@dataclass
class UIState:
    """Global UI state for the TUI"""
    tasks: List[TaskRow] = field(default_factory=list)
    selected_index: int = 0
    scroll_offset: int = 0
    status_filter: Optional[str] = None   # 'staged', 'running', etc.
    focus_panel: str = "list"             # 'list'|'detail'
    detail_tab: str = "overview"          # 'overview'|'exec'|'files'|'summary'

    # Modes
    command_active: bool = False
    command_buffer: str = ""

    # Meta
    message: Optional[str] = None         # transient status bar text
    busy: bool = False                    # global busy indicator
    busy_label: str = ""

    selected_task: SelectedTaskState = field(default_factory=SelectedTaskState)


def task_to_row(task) -> TaskRow:
    """Convert a Task object to a TaskRow for display"""
    from nightshift.core.task_queue import TaskStatus

    # Normalize status once
    raw_status = getattr(task, "status", None)
    if isinstance(raw_status, TaskStatus):
        status = raw_status.value  # "staged", "running", ...
    elif isinstance(raw_status, str):
        status = raw_status.lower()
    else:
        status = str(raw_status or "").lower()

    status_upper = status.upper()
    emoji_map = {
        "STAGED": "📝",
        "COMMITTED": "✔️",
        "RUNNING": "⏳",
        "PAUSED": "⏸️",
        "COMPLETED": "✅",
        "FAILED": "❌",
        "CANCELLED": "🚫",
    }
    color_map = {
        "staged": "orange",
        "committed": "blue",
        "running": "cyan",
        "paused": "magenta",
        "completed": "green",
        "failed": "red",
        "cancelled": "ansired",
    }
    return TaskRow(
        task_id=task.task_id,
        status=status,
        description=task.description,
        created_at=task.created_at,
        status_emoji=emoji_map.get(status_upper, "❓"),
        status_color=color_map.get(status, "white"),
    )
