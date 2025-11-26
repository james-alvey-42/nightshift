"""
TUI Widgets
prompt_toolkit UI components for NightShift
"""
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout import Window
from .models import UIState


class TaskListControl(FormattedTextControl):
    """Control for displaying the task list"""

    def __init__(self, state: UIState):
        self.state = state
        super().__init__(self.get_text)

    def get_text(self):
        """Generate formatted text for task list"""
        lines = []
        for i, row in enumerate(self.state.tasks):
            selected = (i == self.state.selected_index)
            style = f"reverse {row.status_color}" if selected else row.status_color
            desc = row.description
            if len(desc) > 50:
                desc = desc[:47] + "..."
            created = row.created_at.split("T")[0] if row.created_at else ""
            text = f" {row.status_emoji} {row.task_id} {desc} [{created}]"
            lines.append((style, text + "\n"))

        if not lines:
            lines = [("class:dim", "No tasks\n")]

        return lines


class DetailControl(FormattedTextControl):
    """Control for displaying task details"""

    def __init__(self, state: UIState):
        self.state = state
        super().__init__(self.get_text)

    def get_text(self):
        """Generate formatted text for detail panel"""
        st = self.state.selected_task
        tab = self.state.detail_tab

        if not st.details:
            return [("class:dim", "No task selected\n")]

        lines = []

        if tab == "overview":
            lines.append(("bold", f"Task: {st.task_id}\n\n"))

            # Status with emoji and color
            status = st.details.get('status', 'unknown').upper()
            status_emojis = {
                "STAGED": "📝",
                "COMMITTED": "✔️",
                "RUNNING": "⏳",
                "PAUSED": "⏸️",
                "COMPLETED": "✅",
                "FAILED": "❌",
                "CANCELLED": "🚫",
            }
            status_colors = {
                "STAGED": "yellow",
                "COMMITTED": "blue",
                "RUNNING": "cyan",
                "PAUSED": "magenta",
                "COMPLETED": "green",
                "FAILED": "red",
                "CANCELLED": "ansired",
            }
            emoji = status_emojis.get(status, "❓")
            status_color = status_colors.get(status, "white")
            lines.append(("", "Status: "))
            lines.append((status_color, f"{emoji} {status}\n\n"))

            # Timestamps
            lines.append(("", f"Created: {st.details.get('created_at', 'N/A')}\n"))
            if st.details.get('started_at'):
                lines.append(("", f"Started: {st.details['started_at']}\n"))
            if st.details.get('completed_at'):
                lines.append(("", f"Completed: {st.details['completed_at']}\n"))

            # Execution time and result path for completed tasks
            if st.details.get('execution_time'):
                lines.append(("", f"Execution Time: {st.details['execution_time']:.1f}s\n"))
            if st.details.get('result_path'):
                lines.append(("", f"Result Path: {st.details['result_path']}\n"))

            # Description
            lines.append(("", f"\nDescription:\n{st.details.get('description', 'N/A')}\n"))

            # Estimates
            if st.details.get('estimated_tokens'):
                lines.append(("", f"\nEstimated Tokens: {st.details['estimated_tokens']}\n"))
            if st.details.get('estimated_time'):
                lines.append(("", f"Estimated Time: {st.details['estimated_time']}s\n"))

            # Allowed tools
            allowed_tools = st.details.get('allowed_tools') or []
            if allowed_tools:
                lines.append(("", f"\nAllowed Tools:\n"))
                for tool in allowed_tools:
                    lines.append(("", f"  • {tool}\n"))

            # Allowed directories (sandbox)
            allowed_dirs = st.details.get('allowed_directories') or []
            needs_git = st.details.get('needs_git', False)
            if allowed_dirs or needs_git:
                lines.append(("", f"\nSandbox (write access):\n"))
                for d in allowed_dirs:
                    lines.append(("", f"  • {d}\n"))
                lines.append(("", f"(needs_git: {needs_git})\n"))

            # Error message
            if st.details.get('error_message'):
                lines.append(("", f"\nError:\n"))
                lines.append(("red", f"{st.details['error_message']}\n"))

            # System prompt snippet (first 500 chars)
            system_prompt = st.details.get('system_prompt', '')
            if system_prompt:
                snippet = system_prompt[:500]
                if len(system_prompt) > 500:
                    snippet += "..."
                lines.append(("", f"\nSystem Prompt:\n"))
                lines.append(("class:dim", f"{snippet}\n"))

        elif tab == "exec":
            lines.append(("bold", "Execution Log\n\n"))
            if st.exec_snippet:
                lines.append(("", st.exec_snippet + "\n"))
            else:
                lines.append(("class:dim", "No execution log available\n"))

        elif tab == "files":
            lines.append(("bold", "File Changes\n\n"))
            if st.files_info:
                created = st.files_info.get('created', [])
                modified = st.files_info.get('modified', [])
                deleted = st.files_info.get('deleted', [])

                if created:
                    lines.append(("green", f"Created ({len(created)}):\n"))
                    for f in created[:10]:
                        lines.append(("", f"  • {f}\n"))

                if modified:
                    lines.append(("yellow", f"Modified ({len(modified)}):\n"))
                    for f in modified[:10]:
                        lines.append(("", f"  • {f}\n"))

                if deleted:
                    lines.append(("red", f"Deleted ({len(deleted)}):\n"))
                    for f in deleted[:10]:
                        lines.append(("", f"  • {f}\n"))
            else:
                lines.append(("class:dim", "No file changes\n"))

        elif tab == "summary":
            lines.append(("bold", "Task Summary\n\n"))
            if not st.summary_info:
                lines.append(("class:dim", "No summary available\n"))
            else:
                info = st.summary_info

                # Status with emoji
                status = info.get("status", "").upper()
                status_emoji = "✅" if status == "SUCCESS" else "❌"
                status_color = "green" if status == "SUCCESS" else "red"
                lines.append((status_color, f"{status_emoji} {status}\n\n"))

                # Basic info
                lines.append(("", f"Description: {info.get('description', '')}\n"))
                lines.append(("", f"Completed: {info.get('timestamp', '')}\n"))
                lines.append(("", f"Execution Time: {info.get('execution_time', 0):.1f}s\n"))

                if info.get("token_usage") is not None:
                    lines.append(("", f"Token Usage: {info['token_usage']}\n"))

                if info.get("result_path"):
                    lines.append(("", f"Results: {info['result_path']}\n"))

                # Error message
                if info.get("error_message"):
                    lines.append(("", f"\nError:\n"))
                    lines.append(("red", f"{info['error_message']}\n"))

                # File changes
                fc = info.get("file_changes", {})
                if any(fc.get(k) for k in ("created", "modified", "deleted")):
                    lines.append(("", f"\nFile Changes:\n"))
                    for label, key, color in [
                        ("Created", "created", "green"),
                        ("Modified", "modified", "yellow"),
                        ("Deleted", "deleted", "red"),
                    ]:
                        files = fc.get(key) or []
                        if files:
                            lines.append((color, f"{label} ({len(files)}):\n"))
                            for fpath in files[:5]:
                                lines.append(("", f"  • {fpath}\n"))
                            if len(files) > 5:
                                lines.append(("class:dim", f"  ... and {len(files) - 5} more\n"))

        return lines


class StatusBarControl(FormattedTextControl):
    """Control for the status bar"""

    def __init__(self, state: UIState):
        self.state = state
        super().__init__(self.get_text)

    def get_text(self):
        """Generate formatted text for status bar"""
        mode = "COMMAND" if self.state.command_active else "NORMAL"
        filt = self.state.status_filter or "all"
        msg = self.state.busy_label or self.state.message or ""

        # Show keybinding hints
        hints = "j/k:nav g/G:first/last 1-4:tabs H/L:prev/next q:quit ^L:refresh"

        # Limit message length to make room for hints
        msg = msg[:40] if msg else ""

        if msg:
            text = f" {mode} | {hints} | {msg}"
        else:
            text = f" {mode} | {hints}"

        return [("class:status", text)]


def create_task_list_window(state: UIState) -> Window:
    """Create the task list window"""
    return Window(
        TaskListControl(state),
        wrap_lines=False,
        always_hide_cursor=True,
    )


def create_detail_window(state: UIState) -> Window:
    """Create the detail panel window"""
    return Window(
        DetailControl(state),
        wrap_lines=True,
        always_hide_cursor=True,
    )


def create_status_bar(state: UIState) -> Window:
    """Create the status bar window"""
    return Window(
        StatusBarControl(state),
        height=1,
        style="class:statusbar",
        always_hide_cursor=True,
    )
