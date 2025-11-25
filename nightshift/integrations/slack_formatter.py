"""
Slack Formatter
Block Kit message formatting for rich Slack messages
"""
from typing import Dict, List, Any


class SlackFormatter:
    """Utility class for formatting Slack messages using Block Kit"""

    @staticmethod
    def format_approval_message(task: Any, plan: Dict) -> List[Dict]:
        """
        Format task plan as interactive Slack message with approval buttons

        Args:
            task: Task object with task details
            plan: Task plan dictionary with tools, estimates, etc.

        Returns:
            List of Block Kit blocks
        """
        # Truncate description if too long
        description = task.description
        if len(description) > 500:
            description = description[:497] + "..."

        # Format tool list
        tools = task.allowed_tools if hasattr(task, 'allowed_tools') else []
        tools_display = ', '.join(tools[:5])
        if len(tools) > 5:
            tools_display += f' (+{len(tools) - 5} more)'

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🎯 Task Plan: {task.task_id}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Description:*\n{description}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Tools:*\n{tools_display}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Estimated:*\n~{task.estimated_tokens} tokens, ~{task.estimated_time}s"
                    }
                ]
            },
            {
                "type": "divider"
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "✅ Approve"
                        },
                        "style": "primary",
                        "action_id": f"approve_{task.task_id}",
                        "value": task.task_id
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "❌ Reject"
                        },
                        "style": "danger",
                        "action_id": f"reject_{task.task_id}",
                        "value": task.task_id
                    },
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "ℹ️ Details"
                        },
                        "action_id": f"details_{task.task_id}",
                        "value": task.task_id
                    }
                ]
            }
        ]

        return blocks

    @staticmethod
    def format_completion_notification(summary: Dict) -> List[Dict]:
        """
        Format task completion as Slack blocks with detailed information

        Args:
            summary: Task summary dictionary with status, timing, changes

        Returns:
            List of Block Kit blocks
        """
        import json
        from pathlib import Path

        status_emoji = "✅" if summary['status'] == "success" else "❌"
        status_text = "SUCCESS" if summary['status'] == "success" else "FAILED"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{status_emoji} Task {status_text}: {summary['task_id']}"
                }
            }
        ]

        # Show original task description
        description = summary.get('description', 'No description')
        if len(description) > 500:
            description = description[:497] + "..."

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*What you asked for:*\n{description}"
            }
        })

        blocks.append({"type": "divider"})

        # Extract and show Claude's response summary
        result_path = summary.get('result_path')
        if result_path and Path(result_path).exists():
            try:
                with open(result_path, 'r') as f:
                    output_data = json.load(f)
                    stdout = output_data.get('stdout', '')

                    # Parse stream-json output to extract text content
                    text_blocks = []
                    for line in stdout.split('\n'):
                        if line.strip():
                            try:
                                event = json.loads(line)
                                if event.get('type') == 'content_block_delta':
                                    delta = event.get('delta', {})
                                    if delta.get('type') == 'text_delta':
                                        text_blocks.append(delta.get('text', ''))
                            except json.JSONDecodeError:
                                continue

                    if text_blocks:
                        response_text = ''.join(text_blocks).strip()
                        if response_text:
                            # Truncate if too long
                            max_length = 1000
                            if len(response_text) > max_length:
                                response_text = response_text[:max_length] + "...\n\n_[Response truncated - see full results file]_"

                            blocks.append({
                                "type": "section",
                                "text": {
                                    "type": "mrkdwn",
                                    "text": f"*What NightShift found/created:*\n{response_text}"
                                }
                            })
                            blocks.append({"type": "divider"})
            except Exception:
                # If parsing fails, just skip the response summary
                pass

        # Execution metrics
        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Status:*\n{status_text}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Execution Time:*\n{summary.get('execution_time', 0):.1f}s"
                }
            ]
        })

        # Add token usage if available
        if summary.get('token_usage'):
            blocks[-1]['fields'].append({
                "type": "mrkdwn",
                "text": f"*Tokens Used:*\n{summary['token_usage']}"
            })

        # Detailed file changes
        file_changes = summary.get('file_changes', {})
        if isinstance(file_changes, dict) and any(file_changes.values()):
            blocks.append({"type": "divider"})

            changes_text = "*What NightShift did:*\n"

            # Created files
            if file_changes.get('created'):
                created = file_changes['created']
                changes_text += f"\n✨ *Created {len(created)} file(s):*\n"
                for f in created[:5]:  # Show first 5
                    changes_text += f"• `{f}`\n"
                if len(created) > 5:
                    changes_text += f"• _...and {len(created) - 5} more_\n"

            # Modified files
            if file_changes.get('modified'):
                modified = file_changes['modified']
                changes_text += f"\n✏️ *Modified {len(modified)} file(s):*\n"
                for f in modified[:5]:
                    changes_text += f"• `{f}`\n"
                if len(modified) > 5:
                    changes_text += f"• _...and {len(modified) - 5} more_\n"

            # Deleted files
            if file_changes.get('deleted'):
                deleted = file_changes['deleted']
                changes_text += f"\n🗑️ *Deleted {len(deleted)} file(s):*\n"
                for f in deleted[:5]:
                    changes_text += f"• `{f}`\n"
                if len(deleted) > 5:
                    changes_text += f"• _...and {len(deleted) - 5} more_\n"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": changes_text.strip()
                }
            })

        # Add error message if failed
        if summary['status'] != "success" and summary.get('error_message'):
            blocks.append({"type": "divider"})
            error_msg = summary['error_message']
            if len(error_msg) > 300:
                error_msg = error_msg[:297] + "..."

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Error Details:*\n```{error_msg}```"
                }
            })

        # Add result path
        if summary.get('result_path'):
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"📄 Full results: `{summary['result_path']}`"
                    }
                ]
            })

        return blocks

    @staticmethod
    def format_task_list(tasks: List[Any], status_filter: str = None) -> List[Dict]:
        """
        Format list of tasks as Slack blocks

        Args:
            tasks: List of task objects
            status_filter: Optional status filter to display

        Returns:
            List of Block Kit blocks
        """
        if not tasks:
            return [{
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "No tasks found."
                }
            }]

        header_text = "📋 Task Queue"
        if status_filter:
            header_text += f" ({status_filter.upper()})"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": header_text
                }
            }
        ]

        for task in tasks[:10]:  # Limit to 10 tasks to avoid message size limits
            status_emoji = {
                "STAGED": "📝",
                "COMMITTED": "✔️",
                "RUNNING": "⏳",
                "PAUSED": "⏸️",
                "COMPLETED": "✅",
                "FAILED": "❌",
                "CANCELLED": "🚫"
            }.get(task.status, "❓")

            task_desc = task.description
            if len(task_desc) > 100:
                task_desc = task_desc[:97] + "..."

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{status_emoji} *{task.task_id}*\n{task_desc}"
                }
            })

        if len(tasks) > 10:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_Showing 10 of {len(tasks)} tasks_"
                    }
                ]
            })

        return blocks

    @staticmethod
    def format_error_message(error: str) -> List[Dict]:
        """
        Format error message as Slack blocks

        Args:
            error: Error message

        Returns:
            List of Block Kit blocks
        """
        if len(error) > 500:
            error = error[:497] + "..."

        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"❌ *Error*\n```{error}```"
                }
            }
        ]
