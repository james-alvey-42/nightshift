"""
TUI Widgets
prompt_toolkit UI components for NightShift
"""
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout import Window
from .models import UIState


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len characters, adding '...' if truncated"""
    if text is None:
        return ""
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
            lines.append(("class:heading", "📁 File Changes\n\n"))
            fi = st.files_info

            if not fi or not any(fi.get(k) for k in ("created", "modified", "deleted")):
                lines.append(("class:dim", "No file changes recorded for this task.\n"))
            else:
                created = fi.get('created') or []
                modified = fi.get('modified') or []
                deleted = fi.get('deleted') or []

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

                header = f"{status_emoji} Task {status_text}: {info.get('task_id', st.task_id or '')}\n\n"
                lines.append((status_color, header))

                # --- What you asked for ---
                desc = info.get("description", "No description")
                desc = _truncate(desc, 500)
                lines.append(("class:section-title", "🎯 What you asked for\n"))
                lines.append(("", "-" * 40 + "\n"))
                lines.append(("", desc + "\n\n"))

                # --- What NightShift found/created ---
                claude_text = info.get("claude_summary") or ""
                if claude_text:
                    claude_text = _truncate(claude_text.strip(), 1200)
                    lines.append(("class:section-title", "🤖 What NightShift found/created\n"))
                    lines.append(("", "-" * 40 + "\n"))
                    lines.append(("", claude_text + "\n\n"))

                # --- Execution metrics ---
                exec_time = info.get("execution_time", 0.0) or 0.0
                token_usage = info.get("token_usage")
                lines.append(("class:section-title", "📈 Execution metrics\n"))
                lines.append(("", "-" * 40 + "\n"))
                lines.append(("", "  • Status: "))
                lines.append((status_color, status_text))
                lines.append(("", "\n"))
                lines.append(("", f"  • Execution Time: {exec_time:.1f}s\n"))
                if token_usage is not None:
                    lines.append(("", f"  • Tokens Used: {token_usage}\n"))
                ts = info.get("timestamp")
                if ts:
                    lines.append(("", f"  • Completed At: {ts}\n"))
                lines.append(("", "\n"))

                # --- What NightShift did (file changes) ---
                fc = info.get("file_changes")
                if not fc and st.files_info:
                    fc = st.files_info
                fc = fc or {}
                created = fc.get("created") or []
                modified = fc.get("modified") or []
                deleted = fc.get("deleted") or []

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

                # --- Error block (code-block style) ---
                if raw_status != "success" and info.get("error_message"):
                    err = info["error_message"]
                    err = _truncate(err, 300)
                    lines.append(("class:section-title", "❌ Error Details\n"))
                    lines.append(("", "-" * 40 + "\n"))
                    # fake "code block"
                    lines.append(("class:error-codeblock", "┌─ error ───────────────────────────────\n"))
                    for line in err.splitlines() or ["(no details)"]:
                        lines.append(("class:error-codeblock", f"│ {line}\n"))
                    lines.append(("class:error-codeblock", "└───────────────────────────────────────\n\n"))

                # --- Result path / full results hint ---
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
        filt = self.state.status_filter or "all"
        msg = self.state.busy_label or self.state.message or ""

        # Show keybinding hints
        hints = "j/k:nav 1-4:tabs a/r/p/P/X/s:task q:quit R:refresh :help"

        if msg:
            # If message is an error (contains "failed" or "error"), prioritize it
            if "failed" in msg.lower() or "error" in msg.lower():
                # Show full error message, truncate if necessary but allow more space
                msg_truncated = msg[:120] if len(msg) > 120 else msg
                text = f" {mode} | {msg_truncated}"
            else:
                # Normal message - limit to make room for hints
                msg_truncated = msg[:40] if len(msg) > 40 else msg
                text = f" {mode} | {hints} | {msg_truncated}"
        else:
            text = f" {mode} | {hints}"

        return [("class:statusbar", text)]


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
