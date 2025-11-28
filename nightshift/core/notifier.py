"""
Notification System - Sends notifications about task completion
Supports multiple backends (terminal, file, Slack, email - to be added)
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown

from .file_tracker import FileChange


class Notifier:
    """Handles notifications for task completion"""

    def __init__(
        self,
        notification_dir: str = "notifications",
        slack_client: Optional[Any] = None,
        slack_metadata_store: Optional[Any] = None,
        enable_terminal_output: bool = True
    ):
        self.notification_dir = Path(notification_dir)
        self.notification_dir.mkdir(parents=True, exist_ok=True)
        self.console = Console()
        self.slack_client = slack_client
        self.slack_metadata = slack_metadata_store
        self.enable_terminal_output = enable_terminal_output

    def generate_summary(
        self,
        task_id: str,
        task_description: str,
        success: bool,
        execution_time: float,
        token_usage: Optional[int],
        file_changes: List[FileChange],
        error_message: Optional[str] = None,
        result_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a comprehensive task completion summary"""

        summary = {
            "task_id": task_id,
            "description": task_description,
            "timestamp": datetime.now().isoformat(),
            "status": "success" if success else "failed",
            "execution_time": execution_time,
            "token_usage": token_usage,
            "file_changes": {
                "created": [f.path for f in file_changes if f.change_type == 'created'],
                "modified": [f.path for f in file_changes if f.change_type == 'modified'],
                "deleted": [f.path for f in file_changes if f.change_type == 'deleted']
            },
            "error_message": error_message,
            "result_path": result_path
        }

        return summary

    def notify(
        self,
        task_id: str,
        task_description: str,
        success: bool,
        execution_time: float,
        token_usage: Optional[int],
        file_changes: List[FileChange],
        error_message: Optional[str] = None,
        result_path: Optional[str] = None
    ):
        """Send notification about task completion"""

        summary = self.generate_summary(
            task_id=task_id,
            task_description=task_description,
            success=success,
            execution_time=execution_time,
            token_usage=token_usage,
            file_changes=file_changes,
            error_message=error_message,
            result_path=result_path
        )

        # Save to file
        self._save_notification(summary)

        # Display in terminal
        self._display_terminal(summary)

        # Send to Slack if configured
        if self.slack_client and self.slack_metadata:
            try:
                self._send_slack(summary)
            except Exception as e:
                # Only print warning if terminal output is enabled
                if self.enable_terminal_output:
                    self.console.print(f"[yellow]Warning: Slack notification failed: {e}[/yellow]")

    def _save_notification(self, summary: Dict[str, Any]):
        """Save notification to file"""
        notification_file = self.notification_dir / f"{summary['task_id']}_notification.json"

        with open(notification_file, "w") as f:
            json.dump(summary, f, indent=2)

    def _display_terminal(self, summary: Dict[str, Any]):
        """Display notification in terminal"""
        # Skip terminal output if disabled (e.g., when running in TUI mode)
        if not self.enable_terminal_output:
            return

        status_emoji = "✅" if summary["status"] == "success" else "❌"
        status_color = "green" if summary["status"] == "success" else "red"

        # Build notification text
        notification_text = f"## {status_emoji} Task Completed: {summary['task_id']}\n\n"
        notification_text += f"**Description:** {summary['description'][:100]}...\n\n"
        notification_text += f"**Status:** [{status_color}]{summary['status'].upper()}[/{status_color}]\n\n"
        notification_text += f"**Execution Time:** {summary['execution_time']:.1f}s\n\n"

        if summary['token_usage']:
            notification_text += f"**Token Usage:** {summary['token_usage']}\n\n"

        # File changes
        file_changes = summary['file_changes']
        if any(file_changes.values()):
            notification_text += "### File Changes\n\n"

            if file_changes['created']:
                notification_text += f"**Created ({len(file_changes['created'])}):**\n"
                for f in file_changes['created'][:5]:
                    notification_text += f"- ✨ {f}\n"
                if len(file_changes['created']) > 5:
                    notification_text += f"- ... and {len(file_changes['created']) - 5} more\n"
                notification_text += "\n"

            if file_changes['modified']:
                notification_text += f"**Modified ({len(file_changes['modified'])}):**\n"
                for f in file_changes['modified'][:5]:
                    notification_text += f"- ✏️  {f}\n"
                if len(file_changes['modified']) > 5:
                    notification_text += f"- ... and {len(file_changes['modified']) - 5} more\n"
                notification_text += "\n"

            if file_changes['deleted']:
                notification_text += f"**Deleted ({len(file_changes['deleted'])}):**\n"
                for f in file_changes['deleted'][:5]:
                    notification_text += f"- 🗑️  {f}\n"
                if len(file_changes['deleted']) > 5:
                    notification_text += f"- ... and {len(file_changes['deleted']) - 5} more\n"
                notification_text += "\n"

        if summary['error_message']:
            notification_text += f"\n**Error:** {summary['error_message']}\n"

        if summary['result_path']:
            notification_text += f"\n**Results:** {summary['result_path']}\n"

        # Display as panel
        self.console.print("\n")
        self.console.print("=" * 80)
        self.console.print(Markdown(notification_text))
        self.console.print("=" * 80)
        self.console.print("\n")

    def _send_slack(self, summary: Dict[str, Any]):
        """Send notification to Slack"""
        # Get Slack metadata for this task
        metadata = self.slack_metadata.get(summary['task_id'])
        if not metadata:
            # Task wasn't submitted via Slack, skip notification
            return

        # Import formatter (lazy import to avoid circular dependency)
        from ..integrations.slack_formatter import SlackFormatter

        # Format as Block Kit
        blocks = SlackFormatter.format_completion_notification(summary)

        # For DMs, use user_id as channel; for channels, use channel_id
        channel_id = metadata['channel_id']
        target_channel = metadata['user_id'] if channel_id.startswith('D') else channel_id

        # Send to original channel/thread
        self.slack_client.post_message(
            channel=target_channel,
            text=f"Task {summary['task_id']} completed",
            blocks=blocks,
            thread_ts=metadata.get('thread_ts')
        )

        # Clean up metadata after notification sent
        self.slack_metadata.delete(summary['task_id'])

    def _send_email(self, summary: Dict[str, Any]):
        """Send notification via email (to be implemented)"""
        # TODO: Implement email notification
        pass
