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
    """
    try:
        with Path(result_path).open("r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return ""

    stdout = data.get("stdout", "")
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

    return "".join(text_blocks)


def format_exec_log_from_result(result_path: str) -> str:
    """
    Parse stream-json 'stdout' and render a human-readable execution log.

    Matches NightShift's actual event structure:
      - type == 'assistant' with message.content blocks
      - type == 'text'
      - type == 'tool_use'
      - type == 'result'
    """
    try:
        with Path(result_path).open("r") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return ""

    stdout = data.get("stdout", "")
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

                    if not args:
                        lines_out.append(f"🔧 {name}")
                    else:
                        # Show tool name
                        lines_out.append(f"🔧 {name}:")
                        # Show each argument nicely formatted
                        for key, value in args.items():
                            if isinstance(value, str) and len(value) > 100:
                                # Multi-line string values (like file content)
                                lines_out.append(f"  {key}:")
                                for line in value.split('\n'):
                                    lines_out.append(f"    {line}")
                            else:
                                # Short values on one line
                                lines_out.append(f"  {key}: {value}")
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

            if not args:
                lines_out.append(f"🔧 {name}")
            else:
                # Show tool name
                lines_out.append(f"🔧 {name}:")
                # Show each argument nicely formatted
                for key, value in args.items():
                    if isinstance(value, str) and len(value) > 100:
                        # Multi-line string values (like file content)
                        lines_out.append(f"  {key}:")
                        for line in value.split('\n'):
                            lines_out.append(f"    {line}")
                    else:
                        # Short values on one line
                        lines_out.append(f"  {key}: {value}")
            continue

        # Final result event
        if etype == "result":
            subtype = event.get("subtype")
            if subtype == "success":
                lines_out.append("✅ Execution completed successfully.")
            elif subtype:
                lines_out.append(f"Result: {subtype}")
            continue

    return "\n".join(lines_out)


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
        """Request a UI redraw."""
        get_app().invalidate()

    def _run_in_thread(self, label: str, target, *args, **kwargs):
        """Run blocking work in a background thread with busy state."""
        self.state.busy = True
        self.state.busy_label = label
        self._invalidate()

        def worker():
            target(*args, **kwargs)
            self.state.busy = False
            self.state.busy_label = ""
            self._invalidate()

        threading.Thread(target=worker, daemon=True).start()

    def load_selected_task_details(self):
        """Load details for the currently selected task"""
        if not self.state.tasks:
            self.state.selected_task = SelectedTaskState()
            return

        row = self.state.tasks[self.state.selected_index]
        st = self.state.selected_task

        # If we've selected a different task, reload everything
        if st.task_id != row.task_id:
            task = self.queue.get_task(row.task_id)
            st.task_id = row.task_id
            st.details = task.to_dict()
            st.exec_snippet, st.log_mtime, st.log_size = self._load_exec_snippet(task)
            st.files_info = self._load_files_info(task)
            st.summary_info = self._load_summary_info(task)
            st.last_loaded = datetime.utcnow()
            # Reset scroll position for new task
            self.state.detail_scroll_offset = 0
            return

        # Same task still selected: maybe update details and exec log
        task = self.queue.get_task(row.task_id)

        # Always update details so status and timestamps stay current
        st.details = task.to_dict()

        # Normalize status to lower-case string for comparisons
        raw_status = getattr(task, "status", None)
        if isinstance(raw_status, TaskStatus):
            status = raw_status.value  # e.g. "running"
        elif isinstance(raw_status, str):
            status = raw_status.lower()
        else:
            status = str(raw_status or "").lower()

        if status == TaskStatus.RUNNING.value:
            # For RUNNING tasks, reload exec snippet when the file changes
            st.exec_snippet, st.log_mtime, st.log_size = self._maybe_reload_exec_snippet(
                task,
                prev_mtime=st.log_mtime,
                prev_size=st.log_size,
                current_snippet=st.exec_snippet,
            )
            st.last_loaded = datetime.utcnow()
        else:
            # For non-running tasks, load exec snippet only once
            if not st.exec_snippet:
                st.exec_snippet, st.log_mtime, st.log_size = self._load_exec_snippet(task)
                st.last_loaded = datetime.utcnow()

    def _load_exec_snippet(self, task):
        """
        Load formatted execution log snippet for the task.

        Returns:
            (snippet: str, mtime: float|None, size: int|None)
        """
        result_path = task.result_path
        if not result_path:
            return "", None, None

        path = Path(result_path)
        if not path.exists():
            return "", None, None

        try:
            stat = path.stat()
            with path.open("r") as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return "", None, None

        mtime = stat.st_mtime
        size = stat.st_size
        stdout = data.get("stdout", "")

        formatted = format_exec_log_from_result(result_path)
        if formatted:
            return formatted, mtime, size

        # Fallback: raw tail
        lines = stdout.splitlines()
        return "\n".join(lines[-40:]), mtime, size

    def _maybe_reload_exec_snippet(
        self,
        task,
        prev_mtime: float,
        prev_size: int,
        current_snippet: str,
    ):
        """Only reload exec snippet if the log file has changed."""
        result_path = task.result_path
        if not result_path:
            return current_snippet, None, None

        path = Path(result_path)
        if not path.exists():
            return current_snippet, None, None

        stat = path.stat()
        mtime = stat.st_mtime
        size = stat.st_size

        # If nothing changed, keep current snippet
        if prev_mtime and prev_size and mtime == prev_mtime and size == prev_size:
            return current_snippet, prev_mtime, prev_size

        # Reload
        new_snippet, new_mtime, new_size = self._load_exec_snippet(task)
        return (new_snippet or current_snippet, new_mtime or mtime, new_size or size)

    def _load_files_info(self, task) -> dict:
        """Load file changes info"""
        files_path = Path(self.config.get_output_dir()) / f"{task.task_id}_files.json"
        if not files_path.exists():
            return None

        try:
            with open(files_path) as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

        created = [c["path"] for c in data.get("changes", []) if c.get("change_type") == "created"]
        modified = [c["path"] for c in data.get("changes", []) if c.get("change_type") == "modified"]
        deleted = [c["path"] for c in data.get("changes", []) if c.get("change_type") == "deleted"]

        return {"created": created, "modified": modified, "deleted": deleted}

    def _load_summary_info(self, task) -> dict:
        """Load summary notification"""
        notif_path = Path(self.config.get_notifications_dir()) / f"{task.task_id}_notification.json"
        if not notif_path.exists():
            return None

        try:
            with open(notif_path) as f:
                info = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return None

        # Attach Claude's response text
        result_path = info.get("result_path") or task.result_path
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

        if self.state.selected_index >= len(self.state.tasks):
            self.state.selected_index = max(0, len(self.state.tasks) - 1)

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
        task_id = args[0]
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
        """Plan and create a new task, optionally auto-approve & execute."""
        description = description.strip()
        if not description:
            self.state.message = "Submit: description is required"
            return

        def work():
            plan = self.planner.plan_task(description)
            task_id = f"task_{uuid.uuid4().hex[:8]}"

            task = self.queue.create_task(
                task_id=task_id,
                description=plan.get("enhanced_prompt", description),
                allowed_tools=plan.get("allowed_tools", []),
                allowed_directories=plan.get("allowed_directories", []),
                needs_git=plan.get("needs_git", False),
                system_prompt=plan.get("system_prompt", ""),
                estimated_tokens=plan.get("estimated_tokens"),
                estimated_time=plan.get("estimated_time"),
            )

            self.logger.info(f"TUI: created task {task_id}")
            self.state.message = f"Created task {task_id}"

            if auto_approve:
                self.queue.update_status(task_id, TaskStatus.COMMITTED)
                self.logger.info(f"TUI: auto-approved {task_id}")
                self.state.message = f"Executing {task_id}..."
                self.agent.execute_task(task)

        label = "Planning task..." if not auto_approve else "Planning & executing..."
        self._run_in_thread(label, work)

    def approve_selected_task(self):
        """Approve currently selected STAGED task and start execution."""
        if not self.state.tasks:
            return

        row = self.state.tasks[self.state.selected_index]
        task = self.queue.get_task(row.task_id)

        if task.status != TaskStatus.STAGED.value:
            self.state.message = "Approve: only STAGED tasks can be approved"
            return

        def work():
            self.queue.update_status(task.task_id, TaskStatus.COMMITTED)
            self.logger.info(f"TUI: approved {task.task_id}")
            self.state.message = f"Executing {task.task_id}..."
            self.agent.execute_task(task)

        self._run_in_thread(f"Executing {task.task_id}...", work)

    def reject_selected_task(self):
        """Cancel the selected task (STAGED or COMMITTED)."""
        if not self.state.tasks:
            return

        row = self.state.tasks[self.state.selected_index]
        task = self.queue.get_task(row.task_id)

        if task.status not in (TaskStatus.STAGED.value, TaskStatus.COMMITTED.value):
            self.state.message = "Cancel: only STAGED/COMMITTED tasks can be cancelled"
            return

        self.queue.update_status(task.task_id, TaskStatus.CANCELLED)
        self.logger.info(f"TUI: cancelled {task.task_id}")
        self.state.message = f"Cancelled {task.task_id}"
        self.refresh_tasks()

    def pause_selected_task(self):
        """Pause the currently selected RUNNING task."""
        if not self.state.tasks:
            return

        row = self.state.tasks[self.state.selected_index]
        task = self.queue.get_task(row.task_id)

        if task.status != TaskStatus.RUNNING.value:
            self.state.message = "Pause: only RUNNING tasks can be paused"
            return

        self.agent.pause_task(task.task_id)
        self.logger.info(f"TUI: paused {task.task_id}")
        self.state.message = f"Paused {task.task_id}"
        self.refresh_tasks()

    def resume_selected_task(self):
        """Resume the currently selected PAUSED task."""
        if not self.state.tasks:
            return

        row = self.state.tasks[self.state.selected_index]
        task = self.queue.get_task(row.task_id)

        if task.status != TaskStatus.PAUSED.value:
            self.state.message = "Resume: only PAUSED tasks can be resumed"
            return

        self.agent.resume_task(task.task_id)
        self.logger.info(f"TUI: resumed {task.task_id}")
        self.state.message = f"Resumed {task.task_id}"
        self.refresh_tasks()

    def kill_selected_task(self):
        """Kill the currently selected RUNNING or PAUSED task."""
        if not self.state.tasks:
            return

        row = self.state.tasks[self.state.selected_index]
        task = self.queue.get_task(row.task_id)

        if task.status not in (TaskStatus.RUNNING.value, TaskStatus.PAUSED.value):
            self.state.message = "Kill: only RUNNING/PAUSED tasks can be killed"
            return

        self.agent.kill_task(task.task_id)
        self.logger.info(f"TUI: killed {task.task_id}")
        self.state.message = f"Killed {task.task_id}"
        self.refresh_tasks()

    def delete_selected_task(self):
        """Delete the currently selected task."""
        if not self.state.tasks:
            return

        row = self.state.tasks[self.state.selected_index]
        self._run_in_thread(
            f"Deleting {row.task_id}",
            self._delete_task,
            row.task_id
        )

    def _delete_task(self, task_id: str):
        """Delete task from database (internal)"""
        self.queue.delete_task(task_id)
        self.logger.info(f"TUI: deleted {task_id}")
        self.state.message = f"Deleted {task_id}"
        self.refresh_tasks()

    def review_selected_task(self):
        """Review/edit selected STAGED task"""
        if not self.state.tasks:
            return

        row = self.state.tasks[self.state.selected_index]
        task = self.queue.get_task(row.task_id)

        if task.status != TaskStatus.STAGED.value:
            self.state.message = "Review: only STAGED tasks can be reviewed"
            return

        def open_editor_and_refine():
            import os
            import tempfile
            import subprocess
            from pathlib import Path

            # Create temp file with current task details as comments
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                # Blank area for user feedback at top
                f.write("\n\n\n")

                # Instruction line
                f.write("# Write your feedback/changes above\n")
                f.write("#\n")
                f.write("# ---------- ORIGINAL PLAN ----------\n")
                f.write("#\n")
                f.write("# Description:\n")
                for line in task.description.splitlines():
                    f.write(f"#   {line}\n")
                f.write("#\n")
                f.write(f"# Task ID: {task.task_id}\n")
                f.write(f"# Status: {task.status}\n")
                if task.allowed_tools:
                    f.write(f"# Allowed Tools: {', '.join(task.allowed_tools)}\n")
                if task.allowed_directories:
                    f.write(f"# Allowed Directories: {', '.join(task.allowed_directories)}\n")
                if task.system_prompt:
                    f.write(f"# System Prompt: {task.system_prompt[:200]}...\n")
                f.write(f"# Estimated Tokens: {task.estimated_tokens}\n")
                f.write(f"# Estimated Time: {task.estimated_time}s\n")
                f.write("#\n")
                f.write("# Save and quit to submit changes, or quit without saving to cancel\n")
                temp_path = f.name

            # Open editor
            editor = os.environ.get('EDITOR', 'vim')
            subprocess.run([editor, temp_path], check=False)

            # Read edited content
            with open(temp_path, 'r') as f:
                lines = f.readlines()

            # Filter out comments and empty lines to get feedback
            feedback_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
            feedback = ''.join(feedback_lines).strip()

            Path(temp_path).unlink()

            # If no feedback provided, cancel
            if not feedback:
                self.state.message = "Review cancelled: no feedback provided"
                return

            # Show message immediately and kick off background refinement
            self.state.message = f"Refining plan for {task.task_id}..."
            get_app().invalidate()

            # Build current plan dict
            current_plan = {
                "enhanced_prompt": task.description,
                "allowed_tools": task.allowed_tools or [],
                "allowed_directories": task.allowed_directories or [],
                "needs_git": task.needs_git or False,
                "system_prompt": task.system_prompt or "",
                "estimated_tokens": task.estimated_tokens or 0,
                "estimated_time": task.estimated_time or 0,
            }

            # Run planner in background thread to avoid blocking TUI
            def refine_in_background():
                try:
                    # Refine plan based on user feedback
                    refined_plan = self.planner.refine_plan(current_plan, feedback)

                    # Update the task
                    success = self.queue.update_plan(
                        task.task_id,
                        description=refined_plan.get("enhanced_prompt", task.description),
                        allowed_tools=refined_plan.get("allowed_tools", []),
                        allowed_directories=refined_plan.get("allowed_directories", []),
                        needs_git=refined_plan.get("needs_git", False),
                        system_prompt=refined_plan.get("system_prompt", ""),
                        estimated_tokens=refined_plan.get("estimated_tokens"),
                        estimated_time=refined_plan.get("estimated_time"),
                    )

                    if success:
                        self.logger.info(f"TUI: refined plan for {task.task_id}")
                        self.state.message = f"Updated {task.task_id}"
                    else:
                        self.state.message = f"Failed to update {task.task_id}"

                    self.refresh_tasks()
                    get_app().invalidate()

                except Exception as e:
                    self.logger.error(f"TUI: plan refinement failed: {e}")
                    self.state.message = f"Refinement failed: {str(e)}"
                    get_app().invalidate()

            import threading
            thread = threading.Thread(target=refine_in_background, daemon=True)
            thread.start()

        from prompt_toolkit.application import run_in_terminal
        run_in_terminal(open_editor_and_refine)

    def open_in_pager(self):
        """Open current detail tab content in $PAGER for full viewing"""
        import os
        import tempfile
        import subprocess

        st = self.state.selected_task
        tab = self.state.detail_tab

        if not st.details:
            self.state.message = "No task selected"
            return

        # Build content based on current tab
        content_lines = []

        if tab == "overview":
            content_lines.append(f"Task: {st.task_id}")
            content_lines.append(f"Status: {st.details.get('status', 'unknown').upper()}")
            content_lines.append(f"Created: {st.details.get('created_at', 'N/A')}")
            if st.details.get('started_at'):
                content_lines.append(f"Started: {st.details['started_at']}")
            if st.details.get('completed_at'):
                content_lines.append(f"Completed: {st.details['completed_at']}")
            if st.details.get('execution_time'):
                content_lines.append(f"Execution Time: {st.details['execution_time']:.1f}s")
            content_lines.append("")
            content_lines.append("Description:")
            content_lines.append(st.details.get('description', 'N/A'))
            content_lines.append("")
            if st.details.get('allowed_tools'):
                content_lines.append("Allowed Tools:")
                for tool in st.details['allowed_tools']:
                    content_lines.append(f"  • {tool}")
            if st.details.get('system_prompt'):
                content_lines.append("")
                content_lines.append("System Prompt:")
                content_lines.append(st.details['system_prompt'])
            if st.details.get('error_message'):
                content_lines.append("")
                content_lines.append("Error:")
                content_lines.append(st.details['error_message'])

        elif tab == "exec":
            content_lines.append("═" * 60)
            content_lines.append("EXECUTION LOG")
            content_lines.append("═" * 60)
            content_lines.append("")
            if st.exec_snippet:
                content_lines.append(st.exec_snippet)
            else:
                # Try to load full execution log
                task = self.queue.get_task(st.task_id)
                if task and task.result_path:
                    full_log = format_exec_log_from_result(task.result_path)
                    content_lines.append(full_log if full_log else "No execution log available")
                else:
                    content_lines.append("No execution log available")

        elif tab == "files":
            content_lines.append("═" * 60)
            content_lines.append("FILE CHANGES")
            content_lines.append("═" * 60)
            content_lines.append("")
            fi = st.files_info
            if not fi:
                content_lines.append("No file changes recorded for this task.")
            else:
                for change_type, label in [('created', 'Created'), ('modified', 'Modified'), ('deleted', 'Deleted')]:
                    files = fi.get(change_type, [])
                    if files:
                        content_lines.append(f"{label} ({len(files)}):")
                        for path in files:
                            content_lines.append(f"  • {path}")
                        content_lines.append("")

        elif tab == "summary":
            content_lines.append("═" * 60)
            content_lines.append("TASK SUMMARY")
            content_lines.append("═" * 60)
            content_lines.append("")
            info = st.summary_info
            if not info:
                content_lines.append("No summary available")
            else:
                content_lines.append(f"Task: {info.get('task_id', st.task_id)}")
                content_lines.append(f"Status: {info.get('status', 'unknown').upper()}")
                content_lines.append(f"Execution Time: {info.get('execution_time', 0.0):.1f}s")
                if info.get('token_usage'):
                    content_lines.append(f"Tokens Used: {info['token_usage']}")
                content_lines.append("")
                content_lines.append("Description:")
                content_lines.append(info.get('description', 'No description'))
                content_lines.append("")
                if info.get('claude_summary'):
                    content_lines.append("Claude's Response:")
                    content_lines.append("-" * 40)
                    content_lines.append(info['claude_summary'])
                    content_lines.append("")
                if info.get('error_message'):
                    content_lines.append("Error:")
                    content_lines.append(info['error_message'])

        content = "\n".join(content_lines)

        def open_pager():
            # Write to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write(content)
                temp_path = f.name

            # Open in pager
            pager = os.environ.get('PAGER', 'less')
            try:
                subprocess.run([pager, temp_path], check=False)
            finally:
                Path(temp_path).unlink()

        from prompt_toolkit.application import run_in_terminal
        run_in_terminal(open_pager)
