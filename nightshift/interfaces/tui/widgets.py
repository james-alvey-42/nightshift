"""
TUI Widgets
prompt_toolkit UI components for NightShift
"""
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout import Window
from .models import UIState


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len characters, adding '...' if truncated"""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


class TaskListControl(FormattedTextControl):
    """Control for displaying the task list"""

    def __init__(self, state: UIState):
        self.state = state
        super().__init__(self.get_text)

    def get_text(self):
        """Generate formatted text for task list"""
        if not self.state.tasks:
            return [("class:dim", "No tasks\n")]

        lines = []
        for i, row in enumerate(self.state.tasks):
            selected = (i == self.state.selected_index)
            style = f"reverse {row.status_color}" if selected else row.status_color
            desc = row.description if len(row.description) <= 50 else row.description[:47] + "..."
            created = row.created_at.split("T")[0] if row.created_at else ""
            text = f" {row.status_emoji} {row.task_id} {desc} {created}"
            lines.append((style, text + "\n"))

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

        # Tab bar
        tab_names = [
            ("1", "Overview"),
            ("2", "Exec"),
            ("3", "Files"),
            ("4", "Summary")
        ]
        tab_values = ["overview", "exec", "files", "summary"]

        for i, (key, name) in enumerate(tab_names):
            is_active = tab_values[i] == tab
            if is_active:
                lines.append(("class:tab-active", f" {key}:{name} "))
            else:
                lines.append(("class:dim", f" {key}:{name} "))
        lines.append(("", "\n\n"))

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
                "STAGED": "orange",
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
            if st.details.get('allowed_tools'):
                lines.append(("", f"\nAllowed Tools:\n"))
                for tool in st.details['allowed_tools']:
                    lines.append(("", f"  • {tool}\n"))

            # Allowed directories (sandbox)
            allowed_dirs = st.details.get('allowed_directories', [])
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

            # System prompt snippet
            if st.details.get('system_prompt'):
                snippet = _truncate(st.details['system_prompt'], 500)
                lines.append(("", f"\nSystem Prompt:\n"))
                lines.append(("class:dim", f"{snippet}\n"))

        elif tab == "exec":
            lines.append(("class:heading", "📋 Execution Log\n\n"))
            if st.exec_snippet:
                # Parse and colorize execution log
                for line in st.exec_snippet.split("\n"):
                    if line.startswith("🔧"):
                        # Tool calls - dim
                        lines.append(("class:dim", line + "\n"))
                    elif line.startswith("✅"):
                        # Success messages - green
                        lines.append(("green", line + "\n"))
                    elif line.startswith("  ") and ":" in line and not line.startswith("    "):
                        # Argument keys (2-space indent with colon) - use dim italic
                        lines.append(("class:arg-key", line + "\n"))
                    elif line.strip():
                        # Claude's text and content - default color
                        lines.append(("", line + "\n"))
                    else:
                        lines.append(("", line + "\n"))
            else:
                lines.append(("class:dim", "No execution log available\n"))

        elif tab == "files":
            lines.append(("class:heading", "📁 File Changes\n\n"))
            fi = st.files_info

            if not fi:
                lines.append(("class:dim", "No file changes recorded for this task.\n"))
            else:
                created = fi.get('created', [])
                modified = fi.get('modified', [])
                deleted = fi.get('deleted', [])

                max_per_section = 20  # show more here than summary tab

                # Created
                if created:
                    total = len(created)
                    lines.append(("class:file-created-title", f"✨ Created ({total})\n"))
                    for path in created[:max_per_section]:
                        lines.append(("class:file-created", f"  • {path}\n"))
                    if total > max_per_section:
                        remaining = total - max_per_section
                        lines.append(("class:dim", f"  ... {remaining} more created files not shown\n"))
                    lines.append(("", "\n"))

                # Modified
                if modified:
                    total = len(modified)
                    lines.append(("class:file-modified-title", f"✏️ Modified ({total})\n"))
                    for path in modified[:max_per_section]:
                        lines.append(("class:file-modified", f"  • {path}\n"))
                    if total > max_per_section:
                        remaining = total - max_per_section
                        lines.append(("class:dim", f"  ... {remaining} more modified files not shown\n"))
                    lines.append(("", "\n"))

                # Deleted
                if deleted:
                    total = len(deleted)
                    lines.append(("class:file-deleted-title", f"🗑️ Deleted ({total})\n"))
                    for path in deleted[:max_per_section]:
                        lines.append(("class:file-deleted", f"  • {path}\n"))
                    if total > max_per_section:
                        remaining = total - max_per_section
                        lines.append(("class:dim", f"  ... {remaining} more deleted files not shown\n"))
                    lines.append(("", "\n"))

        elif tab == "summary":
            info = st.summary_info
            if not info:
                lines.append(("bold", "Task Summary\n\n"))
                lines.append(("class:dim", "No summary available\n"))
            else:
                lines.append(("class:heading", "📊 Task Summary\n\n"))

                # --- Status header (SUCCESS/FAILED/CANCELLED/etc) ---
                raw_status = (info.get("status") or "").lower()
                if raw_status == "success":
                    status_text, status_emoji, status_color = "SUCCESS", "✅", "class:success"
                elif raw_status in ("failed", "error"):
                    status_text, status_emoji, status_color = "FAILED", "❌", "class:error"
                elif raw_status == "cancelled":
                    status_text, status_emoji, status_color = "CANCELLED", "🚫", "class:error"
                elif raw_status == "running":
                    status_text, status_emoji, status_color = "RUNNING", "⏳", "cyan"
                else:
                    status_text, status_emoji, status_color = raw_status.upper() or "UNKNOWN", "❓", ""

                task_id = info.get('task_id', st.task_id)
                header = f"{status_emoji} Task {status_text}: {task_id}\n\n"
                lines.append((status_color, header))

                # --- What you asked for ---
                lines.append(("class:section-title", "🎯 What you asked for\n"))
                lines.append(("", "-" * 40 + "\n"))
                lines.append(("", _truncate(info.get("description", "No description"), 500) + "\n\n"))

                # --- What NightShift found/created ---
                if info.get("claude_summary"):
                    lines.append(("class:section-title", "🤖 What NightShift found/created\n"))
                    lines.append(("", "-" * 40 + "\n"))
                    lines.append(("", _truncate(info["claude_summary"], 1200) + "\n\n"))

                # --- Execution metrics ---
                lines.append(("class:section-title", "📈 Execution metrics\n"))
                lines.append(("", "-" * 40 + "\n"))
                lines.append(("", "  • Status: "))
                lines.append((status_color, status_text))
                lines.append(("", "\n"))
                lines.append(("", f"  • Execution Time: {info.get('execution_time', 0.0):.1f}s\n"))
                if info.get("token_usage"):
                    lines.append(("", f"  • Tokens Used: {info['token_usage']}\n"))
                if info.get("timestamp"):
                    lines.append(("", f"  • Completed At: {info['timestamp']}\n"))
                lines.append(("", "\n"))

                # --- What NightShift did (file changes) ---
                fc = info.get("file_changes") or st.files_info or {}
                created = fc.get("created", [])
                modified = fc.get("modified", [])
                deleted = fc.get("deleted", [])

                if any((created, modified, deleted)):
                    lines.append(("class:section-title", "🛠️ What NightShift did\n"))
                    lines.append(("", "-" * 40 + "\n"))

                    # Created
                    if created:
                        total = len(created)
                        lines.append(("class:file-created", f"✨ Created {total} file(s):\n"))
                        for path in created[:5]:
                            lines.append(("", f"   • {path}\n"))
                        if total > 5:
                            remaining = total - 5
                            lines.append(("class:dim", f"   ... and {remaining} more\n"))

                    # Modified
                    if modified:
                        total = len(modified)
                        lines.append(("class:file-modified", f"\n✏️ Modified {total} file(s):\n"))
                        for path in modified[:5]:
                            lines.append(("", f"   • {path}\n"))
                        if total > 5:
                            remaining = total - 5
                            lines.append(("class:dim", f"   ... and {remaining} more\n"))

                    # Deleted
                    if deleted:
                        total = len(deleted)
                        lines.append(("class:file-deleted", f"\n🗑️ Deleted {total} file(s):\n"))
                        for path in deleted[:5]:
                            lines.append(("", f"   • {path}\n"))
                        if total > 5:
                            remaining = total - 5
                            lines.append(("class:dim", f"   ... and {remaining} more\n"))

                    lines.append(("", "\n"))

                # --- Error block ---
                if raw_status != "success" and info.get("error_message"):
                    lines.append(("class:section-title", "❌ Error Details\n"))
                    lines.append(("", "-" * 40 + "\n"))
                    lines.append(("class:error-codeblock", "┌─ error ───────────────────────────────\n"))
                    for line in _truncate(info["error_message"], 300).splitlines():
                        lines.append(("class:error-codeblock", f"│ {line}\n"))
                    lines.append(("class:error-codeblock", "└───────────────────────────────────────\n\n"))

                # --- Result path ---
                if info.get("result_path"):
                    lines.append(("class:dim", f"📄 Full results: {info['result_path']}\n"))

        return lines


class StatusBarControl(FormattedTextControl):
    """Control for the status bar"""

    def __init__(self, state: UIState):
        self.state = state
        super().__init__(self.get_text)

    def get_text(self):
        """Generate formatted text for status bar"""
        mode = "COMMAND" if self.state.command_active else "NORMAL"
        msg = self.state.busy_label or self.state.message or ""
        hints = "j/k:nav h/l:tabs 1-4:tab a:approve r:review c:cancel p:pause P:resume X:kill d:delete s:submit q:quit R:refresh :help"

        if msg and ("failed" in msg.lower() or "error" in msg.lower()):
            text = f" {mode} | {msg[:120]}"
        elif msg:
            text = f" {mode} | {hints} | {msg[:40]}"
        else:
            text = f" {mode} | {hints}"

        return [("class:statusbar", text)]


def create_task_list_window(state: UIState) -> Window:
    """Create the task list window (fixed width)"""
    from prompt_toolkit.layout.dimension import Dimension
    return Window(
        TaskListControl(state),
        width=Dimension.exact(79),
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
