"""
TUI Controllers
Business logic layer that interfaces with NightShift core
"""
import json
from datetime import datetime
from pathlib import Path
from nightshift.core.task_queue import TaskQueue
from nightshift.core.config import Config
from .models import UIState, SelectedTaskState, task_to_row


class TUIController:
    """Controller for TUI operations"""

    def __init__(self, state: UIState, queue: TaskQueue, config: Config):
        self.state = state
        self.queue = queue
        self.config = config

    def load_selected_task_details(self):
        """Load details for the currently selected task"""
        if not self.state.tasks:
            self.state.selected_task = SelectedTaskState()
            return

        if self.state.selected_index >= len(self.state.tasks):
            return

        row = self.state.tasks[self.state.selected_index]
        st = self.state.selected_task

        # Only reload if we selected a different task
        if st.task_id != row.task_id:
            task = self.queue.get_task(row.task_id)
            if task:
                st.task_id = row.task_id
                st.details = task.to_dict()
                st.exec_snippet = self._load_exec_snippet(task)
                st.files_info = self._load_files_info(task)
                st.summary_info = self._load_summary_info(task)
                st.last_loaded = datetime.utcnow()

    def _load_exec_snippet(self, task) -> str:
        """Load execution log snippet"""
        if not task.result_path:
            return ""

        path = Path(task.result_path)
        if not path.exists():
            return ""

        try:
            with open(path) as f:
                data = json.load(f)
            stdout = data.get("stdout", "")
            if not stdout:
                return ""
            # Take last 40 lines
            lines = stdout.strip().split("\n")
            tail = lines[-40:]
            return "\n".join(tail)
        except Exception:
            return ""

    def _load_files_info(self, task) -> dict:
        """Load file changes info"""
        files_path = Path(self.config.get_output_dir()) / f"{task.task_id}_files.json"
        if not files_path.exists():
            return None

        try:
            with open(files_path) as f:
                data = json.load(f)
            created = [c["path"] for c in data.get("changes", []) if c.get("change_type") == "created"]
            modified = [c["path"] for c in data.get("changes", []) if c.get("change_type") == "modified"]
            deleted = [c["path"] for c in data.get("changes", []) if c.get("change_type") == "deleted"]
            return {
                "created": created,
                "modified": modified,
                "deleted": deleted,
            }
        except Exception:
            return None

    def _load_summary_info(self, task) -> dict:
        """Load summary notification"""
        notif_path = Path(self.config.get_notifications_dir()) / f"{task.task_id}_notification.json"
        if not notif_path.exists():
            return None

        try:
            with open(notif_path) as f:
                return json.load(f)
        except Exception:
            return None

    def refresh_tasks(self):
        """Refresh task list from queue, applying filters"""
        from nightshift.core.task_queue import TaskStatus

        if self.state.status_filter:
            tasks = self.queue.list_tasks(TaskStatus(self.state.status_filter))
        else:
            tasks = self.queue.list_tasks()

        self.state.tasks = [task_to_row(t) for t in tasks]

        # Clamp selected_index
        if self.state.selected_index >= len(self.state.tasks):
            self.state.selected_index = max(0, len(self.state.tasks) - 1)

        # Reload selected task details
        self.load_selected_task_details()

    def execute_command(self, line: str):
        """Execute a command entered in command mode"""
        import shlex

        line = line.strip()
        if not line:
            return

        try:
            parts = shlex.split(line)
        except ValueError:
            self.state.message = f"Invalid command syntax: {line}"
            return

        if not parts:
            return

        cmd = parts[0].lower()
        args = parts[1:]

        # Dispatch commands
        if cmd == "queue":
            self._cmd_queue(args)
        elif cmd == "status":
            self._cmd_status(args)
        elif cmd == "results":
            self._cmd_results(args)
        elif cmd == "help" or cmd == "h":
            self._cmd_help()
        elif cmd == "quit" or cmd == "q":
            from prompt_toolkit.application.current import get_app
            get_app().exit()
        else:
            self.state.message = f"Unknown command: {cmd}"

    def _cmd_queue(self, args):
        """Handle :queue [status] command"""
        if not args:
            # Clear filter
            self.state.status_filter = None
            self.refresh_tasks()
            self.state.message = "Showing all tasks"
        else:
            status = args[0].lower()
            valid_statuses = ["staged", "committed", "running", "paused", "completed", "failed", "cancelled"]
            if status in valid_statuses:
                self.state.status_filter = status
                self.refresh_tasks()
                self.state.message = f"Filtering by status: {status}"
            else:
                self.state.message = f"Invalid status: {status}. Valid: {', '.join(valid_statuses)}"

    def _cmd_status(self, args):
        """Handle :status [task_id] command"""
        if not args:
            self.state.message = "Usage: status <task_id>"
            return

        task_id = args[0]
        # Find task in list
        for idx, row in enumerate(self.state.tasks):
            if row.task_id == task_id:
                self.state.selected_index = idx
                self.state.detail_tab = "overview"
                self.load_selected_task_details()
                self.state.message = f"Selected task: {task_id}"
                return

        self.state.message = f"Task not found: {task_id}"

    def _cmd_results(self, args):
        """Handle :results [task_id] command"""
        if not args:
            # Show results for currently selected task
            self.state.detail_tab = "summary"
            self.state.message = "Showing summary"
        else:
            task_id = args[0]
            # Find task in list
            for idx, row in enumerate(self.state.tasks):
                if row.task_id == task_id:
                    self.state.selected_index = idx
                    self.state.detail_tab = "summary"
                    self.load_selected_task_details()
                    self.state.message = f"Showing results for: {task_id}"
                    return

            self.state.message = f"Task not found: {task_id}"

    def _cmd_help(self):
        """Handle :help command"""
        self.state.message = "Commands: :queue [status] | :status <task_id> | :results [task_id] | :help | :quit"
