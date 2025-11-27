"""
TUI Controllers
Business logic layer that interfaces with NightShift core
"""
import json
import threading
import uuid
from datetime import datetime
from pathlib import Path

from prompt_toolkit.application.current import get_app

from nightshift.core.config import Config
from nightshift.core.logger import NightShiftLogger
from nightshift.core.task_queue import TaskQueue, TaskStatus
from nightshift.core.task_planner import TaskPlanner
from nightshift.core.agent_manager import AgentManager

from .models import UIState, SelectedTaskState, task_to_row


def extract_claude_text_from_result(result_path: str) -> str:
    """
    Parse stream-json 'stdout' from result_path and extract Claude's text
    (content_block_delta events of type 'text_delta') into a single string.
    This mirrors SlackFormatter.format_completion_notification behavior.
    """
    if not result_path:
        return ""

    p = Path(result_path)
    if not p.exists():
        return ""

    try:
        with p.open("r") as f:
            data = json.load(f)
    except Exception:
        return ""

    stdout = data.get("stdout", "")
    if not stdout:
        return ""

    text_blocks = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue

        if event.get("type") == "content_block_delta":
            delta = event.get("delta", {})
            if delta.get("type") == "text_delta":
                text_blocks.append(delta.get("text", ""))

    return "".join(text_blocks).strip()


def format_exec_log_from_result(result_path: str, max_lines: int = 200) -> str:
    """
    Parse stream-json 'stdout' and render a human-readable execution log.

    Matches NightShift's actual event structure (same as CLI watch and Slack):
      - type == 'assistant' with message.content blocks
      - type == 'text'
      - type == 'tool_use'
      - type == 'result'
    """
    if not result_path:
        return ""

    p = Path(result_path)
    if not p.exists():
        return ""

    try:
        with p.open("r") as f:
            data = json.load(f)
    except Exception:
        return ""

    stdout = data.get("stdout", "")
    if not stdout:
        return ""

    lines_out = []

    for raw_line in stdout.splitlines():
        raw_line = raw_line.strip()
        if not raw_line:
            continue

        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            # Plain text fallback
            lines_out.append(raw_line)
            continue

        etype = event.get("type")

        # Assistant message with content blocks
        if etype == "assistant" and "message" in event:
            msg = event["message"]
            content_blocks = msg.get("content") or []
            for block in content_blocks:
                btype = block.get("type")
                if btype == "text":
                    text = block.get("text") or ""
                    if text:
                        for ln in text.splitlines():
                            lines_out.append(ln)
                elif btype == "tool_use":
                    name = block.get("name") or "<tool>"
                    args = block.get("input") or {}
                    # For Bash, show the command; for other tools, show full args
                    if name == "Bash" and "command" in args:
                        cmd = args["command"]
                        lines_out.append(f"🔧 {name}: {cmd}")
                    else:
                        args_preview = repr(args)
                        if args:
                            lines_out.append(f"🔧 {name}: {args_preview}")
                        else:
                            lines_out.append(f"🔧 {name}")
            continue

        # Direct text events
        if etype == "text":
            text = event.get("text", "")
            if text:
                for ln in text.splitlines():
                    lines_out.append(ln)
            continue

        # Tool use events
        if etype == "tool_use":
            name = event.get("name") or "<tool>"
            args = event.get("input") or {}
            # For Bash, show the command; for other tools, show full args
            if name == "Bash" and "command" in args:
                cmd = args["command"]
                lines_out.append(f"🔧 {name}: {cmd}")
            else:
                args_preview = repr(args)
                if args:
                    lines_out.append(f"🔧 {name}: {args_preview}")
                else:
                    lines_out.append(f"🔧 {name}")
            continue

        # Final result event
        if etype == "result":
            subtype = event.get("subtype")
            if subtype == "success":
                lines_out.append("✅ Execution completed successfully.")
            elif subtype:
                lines_out.append(f"Result: {subtype}")
            continue

    if not lines_out:
        return ""

    # Clip to max_lines for safety
    if len(lines_out) > max_lines:
        remainder = len(lines_out) - max_lines
        lines_out = lines_out[:max_lines]
        lines_out.append(f"... ({remainder} more lines not shown)")

    return "\n".join(lines_out).strip()


class TUIController:
    """Controller for TUI operations"""

    def __init__(
        self,
        state: UIState,
        queue: TaskQueue,
        config: Config,
        planner: TaskPlanner,
        agent: AgentManager,
        logger: NightShiftLogger,
    ):
        self.state = state
        self.queue = queue
        self.config = config
        self.planner = planner
        self.agent = agent
        self.logger = logger

    # ----- internal helpers -----

    def _invalidate(self):
        """Request a UI redraw (safe to call from any thread)."""
        try:
            get_app().invalidate()
        except Exception:
            pass

    def _run_in_thread(self, label: str, target, *args, **kwargs):
        """Run blocking work in a background thread with busy state."""
        self.state.busy = True
        self.state.busy_label = label
        self._invalidate()

        def worker():
            try:
                target(*args, **kwargs)
            finally:
                # Clear busy state, but keep any message set by worker
                self.state.busy = False
                self.state.busy_label = ""
                # Don't call refresh_tasks() from worker thread - causes race conditions
                # The auto-refresh loop will pick up changes within 2 seconds
                self._invalidate()

        threading.Thread(target=worker, daemon=True).start()

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
        """Load formatted execution log snippet for the task."""
        if not getattr(task, "result_path", None):
            return ""

        path = Path(task.result_path)
        if not path.exists():
            return ""

        try:
            with path.open("r") as f:
                data = json.load(f)
        except Exception:
            return ""

        stdout = data.get("stdout", "")
        if not stdout:
            return ""

        # First try formatted view
        try:
            formatted = format_exec_log_from_result(task.result_path, max_lines=200)
        except Exception:
            formatted = ""

        if formatted:
            return formatted

        # Fallback: raw tail (old behavior)
        lines = stdout.strip().splitlines()
        tail = lines[-40:]
        return "\n".join(tail)

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
                info = json.load(f)
        except Exception:
            return None

        # Attach Claude's response text (for "What NightShift found/created")
        result_path = info.get("result_path") or getattr(task, "result_path", None)
        if result_path:
            claude = extract_claude_text_from_result(result_path)
            if claude:
                info["claude_summary"] = claude

        return info

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
        elif cmd in ("submit", "submit!"):
            auto = cmd.endswith("!")
            desc = " ".join(args)
            self.submit_task(desc, auto_approve=auto)
        elif cmd in ("refresh", "r"):
            self.refresh_tasks()
            self.state.message = "Refreshed"
        elif cmd == "pause":
            self._cmd_pause(args)
        elif cmd == "resume":
            self._cmd_resume(args)
        elif cmd == "kill":
            self._cmd_kill(args)
        elif cmd == "cancel":
            self._cmd_cancel(args)
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
        self.state.message = "Commands: :queue [status] | :status <task_id> | :results [task_id] | :submit <desc> | :pause/:resume/:kill/:cancel [task_id] | :refresh | :help | :quit"

    def _cmd_pause(self, args):
        """Handle :pause [task_id] command"""
        if args:
            task_id = args[0]
            # Find task in list and select it
            for idx, row in enumerate(self.state.tasks):
                if row.task_id == task_id:
                    self.state.selected_index = idx
                    self.load_selected_task_details()
                    self.pause_selected_task()
                    return
            self.state.message = f"Task not found: {task_id}"
        else:
            self.pause_selected_task()

    def _cmd_resume(self, args):
        """Handle :resume [task_id] command"""
        if args:
            task_id = args[0]
            # Find task in list and select it
            for idx, row in enumerate(self.state.tasks):
                if row.task_id == task_id:
                    self.state.selected_index = idx
                    self.load_selected_task_details()
                    self.resume_selected_task()
                    return
            self.state.message = f"Task not found: {task_id}"
        else:
            self.resume_selected_task()

    def _cmd_kill(self, args):
        """Handle :kill [task_id] command"""
        if args:
            task_id = args[0]
            # Find task in list and select it
            for idx, row in enumerate(self.state.tasks):
                if row.task_id == task_id:
                    self.state.selected_index = idx
                    self.load_selected_task_details()
                    self.kill_selected_task()
                    return
            self.state.message = f"Task not found: {task_id}"
        else:
            self.kill_selected_task()

    def _cmd_cancel(self, args):
        """Handle :cancel [task_id] command"""
        if args:
            task_id = args[0]
            # Find task in list and select it
            for idx, row in enumerate(self.state.tasks):
                if row.task_id == task_id:
                    self.state.selected_index = idx
                    self.load_selected_task_details()
                    self.reject_selected_task()
                    return
            self.state.message = f"Task not found: {task_id}"
        else:
            self.reject_selected_task()

    # ----- Phase 3 actions: submit/approve/reject -----

    def submit_task(self, description: str, auto_approve: bool = False):
        """
        Plan and create a new task using TaskPlanner + TaskQueue.
        Optionally auto-approve & execute.
        """
        description = (description or "").strip()
        if not description:
            self.state.message = "Submit: description is required"
            return

        def work():
            try:
                # Plan task
                plan = self.planner.plan_task(description)

                # Generate unique task ID
                task_id = f"task_{uuid.uuid4().hex[:8]}"

                # Create task in queue
                task = self.queue.create_task(
                    task_id=task_id,
                    description=plan.get("enhanced_prompt", description),
                    allowed_tools=plan.get("allowed_tools") or [],
                    allowed_directories=plan.get("allowed_directories") or [],
                    needs_git=plan.get("needs_git", False),
                    system_prompt=plan.get("system_prompt", ""),
                    estimated_tokens=plan.get("estimated_tokens"),
                    estimated_time=plan.get("estimated_time"),
                )

                self.logger.info(f"TUI: created task {task_id}")
                self.state.message = f"Created task {task_id}"

                if auto_approve:
                    # Approve & execute
                    self.queue.update_status(task_id, TaskStatus.COMMITTED)
                    self.logger.info(f"TUI: auto-approved {task_id}")
                    self.state.message = f"Executing {task_id}..."
                    # Execute in this same worker thread (already background)
                    self.agent.execute_task(task)

            except Exception as e:
                self.logger.error(f"TUI: submit task failed: {e}")
                self.state.message = f"Submit failed: {e}"

        label = "Planning task..." if not auto_approve else "Planning & executing..."
        self._run_in_thread(label, work)

    def approve_selected_task(self):
        """Approve currently selected STAGED task and start execution."""
        if not self.state.tasks:
            self.state.message = "No task selected"
            return

        row = self.state.tasks[self.state.selected_index]
        task = self.queue.get_task(row.task_id)
        if not task:
            self.state.message = f"Task not found: {row.task_id}"
            return

        if task.status != TaskStatus.STAGED.value:
            self.state.message = "Approve: task is not STAGED"
            return

        def work():
            try:
                # Mark committed and execute
                self.queue.update_status(task.task_id, TaskStatus.COMMITTED)
                self.logger.info(f"TUI: approved {task.task_id}")
                self.state.message = f"Executing {task.task_id}..."
                # Re-fetch to ensure latest state, if needed
                t = self.queue.get_task(task.task_id) or task
                self.agent.execute_task(t)
                self.state.message = f"Task {task.task_id} completed (or running)"
            except Exception as e:
                self.state.message = f"Approve failed: {e}"

        self._run_in_thread(f"Executing {task.task_id}...", work)

    def reject_selected_task(self):
        """Reject/cancel the selected task (STAGED or COMMITTED)."""
        if not self.state.tasks:
            self.state.message = "No task selected"
            return

        row = self.state.tasks[self.state.selected_index]
        task = self.queue.get_task(row.task_id)
        if not task:
            self.state.message = f"Task not found: {row.task_id}"
            return

        if task.status not in (TaskStatus.STAGED.value, TaskStatus.COMMITTED.value):
            self.state.message = "Reject: only STAGED/COMMITTED can be cancelled"
            return

        try:
            self.queue.update_status(task.task_id, TaskStatus.CANCELLED)
            self.logger.info(f"TUI: cancelled {task.task_id}")
            self.state.message = f"Cancelled {task.task_id}"
            # Refresh immediately
            self.refresh_tasks()
        except Exception as e:
            self.logger.error(f"TUI: cancel {task.task_id} failed: {e}")
            self.state.message = f"Reject failed: {e}"

    def pause_selected_task(self):
        """Pause the currently selected RUNNING task."""
        if not self.state.tasks:
            self.state.message = "No task selected"
            return

        row = self.state.tasks[self.state.selected_index]
        task = self.queue.get_task(row.task_id)
        if not task:
            self.state.message = f"Task not found: {row.task_id}"
            return

        if task.status != TaskStatus.RUNNING.value:
            self.state.message = "Pause: only RUNNING tasks can be paused"
            return

        try:
            self.agent.pause_task(task.task_id)
            self.logger.info(f"TUI: paused {task.task_id}")
            self.state.message = f"Paused {task.task_id}"
            self.refresh_tasks()
        except Exception as e:
            self.logger.error(f"TUI: pause {task.task_id} failed: {e}")
            self.state.message = f"Pause failed: {e}"

    def resume_selected_task(self):
        """Resume the currently selected PAUSED task."""
        if not self.state.tasks:
            self.state.message = "No task selected"
            return

        row = self.state.tasks[self.state.selected_index]
        task = self.queue.get_task(row.task_id)
        if not task:
            self.state.message = f"Task not found: {row.task_id}"
            return

        if task.status != TaskStatus.PAUSED.value:
            self.state.message = "Resume: only PAUSED tasks can be resumed"
            return

        try:
            self.agent.resume_task(task.task_id)
            self.logger.info(f"TUI: resumed {task.task_id}")
            self.state.message = f"Resumed {task.task_id}"
            self.refresh_tasks()
        except Exception as e:
            self.logger.error(f"TUI: resume {task.task_id} failed: {e}")
            self.state.message = f"Resume failed: {e}"

    def kill_selected_task(self):
        """Kill the currently selected RUNNING or PAUSED task."""
        if not self.state.tasks:
            self.state.message = "No task selected"
            return

        row = self.state.tasks[self.state.selected_index]
        task = self.queue.get_task(row.task_id)
        if not task:
            self.state.message = f"Task not found: {row.task_id}"
            return

        if task.status not in (TaskStatus.RUNNING.value, TaskStatus.PAUSED.value):
            self.state.message = "Kill: only RUNNING/PAUSED tasks can be killed"
            return

        try:
            self.agent.kill_task(task.task_id)
            self.logger.info(f"TUI: killed {task.task_id}")
            self.state.message = f"Killed {task.task_id}"
            self.refresh_tasks()
        except Exception as e:
            self.logger.error(f"TUI: kill {task.task_id} failed: {e}")
            self.state.message = f"Kill failed: {e}"
