"""
Slack Event Handler
Routes Slack events to NightShift operations
"""
import threading
import uuid
from typing import Dict, Any
from flask import jsonify

from ..core.task_queue import TaskQueue, TaskStatus
from ..core.task_planner import TaskPlanner
from ..core.agent_manager import AgentManager
from ..core.logger import NightShiftLogger
from .slack_client import SlackClient
from .slack_formatter import SlackFormatter
from .slack_metadata import SlackMetadataStore


class SlackEventHandler:
    """
    Handles Slack events and maps them to NightShift operations
    """

    def __init__(
        self,
        slack_client: SlackClient,
        task_queue: TaskQueue,
        task_planner: TaskPlanner,
        agent_manager: AgentManager,
        slack_metadata: SlackMetadataStore,
        logger: NightShiftLogger
    ):
        """
        Initialize event handler

        Args:
            slack_client: SlackClient instance for posting messages
            task_queue: TaskQueue instance for CRUD operations
            task_planner: TaskPlanner instance for creating plans
            agent_manager: AgentManager instance for executing tasks
            slack_metadata: SlackMetadataStore for tracking Slack context
            logger: Logger instance
        """
        self.slack = slack_client
        self.task_queue = task_queue
        self.task_planner = task_planner
        self.agent_manager = agent_manager
        self.slack_metadata = slack_metadata
        self.logger = logger

    def handle_submit(
        self,
        text: str,
        user_id: str,
        channel_id: str,
        response_url: str
    ) -> Dict:
        """
        Handle /nightshift submit command

        Args:
            text: Task description
            user_id: Slack user ID
            channel_id: Slack channel ID
            response_url: Slack response URL for delayed responses

        Returns:
            Immediate response dict
        """
        if not text.strip():
            return jsonify({
                "response_type": "ephemeral",
                "text": "Please provide a task description:\n`/nightshift submit \"your task description\"`"
            })

        # Immediate acknowledgment (must respond within 3 seconds)
        response = {
            "response_type": "ephemeral",
            "text": "🔄 Planning task... This may take 30-120 seconds."
        }

        # Start async planning
        threading.Thread(
            target=self._plan_and_stage_task,
            args=(text, user_id, channel_id, response_url),
            daemon=True
        ).start()

        return jsonify(response)

    def _plan_and_stage_task(
        self,
        description: str,
        user_id: str,
        channel_id: str,
        response_url: str
    ):
        """
        Async task planning and staging (runs in background thread)

        Args:
            description: Task description
            user_id: Slack user ID
            channel_id: Slack channel ID
            response_url: Slack response URL
        """
        try:
            self.logger.info(f"Planning task for Slack user {user_id}: {description[:100]}")

            # Plan task (can take 30-120s)
            plan = self.task_planner.plan_task(description)

            # Generate task ID
            task_id = f"task_{uuid.uuid4().hex[:8]}"

            # Create task in STAGED state (default timeout: 15 minutes)
            task = self.task_queue.create_task(
                task_id=task_id,
                description=plan['enhanced_prompt'],
                allowed_tools=plan['allowed_tools'],
                allowed_directories=plan.get('allowed_directories', []),
                needs_git=plan.get('needs_git', False),
                system_prompt=plan['system_prompt'],
                timeout_seconds=900  # 15 minutes default for Slack tasks
            )

            # Store Slack metadata
            self.slack_metadata.store(
                task_id=task_id,
                user_id=user_id,
                channel_id=channel_id,
                response_url=response_url
            )

            # Send approval message with buttons
            blocks = SlackFormatter.format_approval_message(task, plan)

            # For DMs, use user_id as channel; for channels, use channel_id
            target_channel = user_id if channel_id.startswith('D') else channel_id

            response = self.slack.post_message(
                channel=target_channel,
                text=f"Task {task_id} ready for approval",
                blocks=blocks
            )

            # Store thread_ts for future updates
            if response.ok and response.ts:
                self.slack_metadata.update(task_id, {"thread_ts": response.ts})

            self.logger.info(f"Task {task_id} planned and awaiting approval")

        except Exception as e:
            self.logger.error(f"Task planning failed: {e}")
            try:
                # For DMs, use user_id as channel
                target_channel = user_id if channel_id.startswith('D') else channel_id
                self.slack.post_message(
                    channel=target_channel,
                    text=f"❌ Task planning failed: {str(e)}"
                )
            except:
                pass

    def handle_approval(
        self,
        task_id: str,
        user_id: str,
        channel_id: str,
        message_ts: str,
        action: str
    ) -> Dict:
        """
        Handle approval button click

        Args:
            task_id: Task ID to approve/reject
            user_id: Slack user ID who clicked
            channel_id: Slack channel ID
            message_ts: Message timestamp to update
            action: "approve" or "reject"

        Returns:
            Response dict for Slack
        """
        try:
            # Get task
            task = self.task_queue.get_task(task_id)
            if not task:
                return jsonify({"text": f"Task {task_id} not found"})

            if action == "approve":
                # Update task status to COMMITTED (executor will pick it up)
                self.task_queue.update_status(task_id, TaskStatus.COMMITTED)

                # Update Slack message
                self.slack.update_message(
                    channel=channel_id,
                    ts=message_ts,
                    text=f"✅ Task {task_id} approved by <@{user_id}>",
                    blocks=[{
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"✅ Task {task_id} approved by <@{user_id}>\n⏳ Queued for execution (will be picked up by executor service)"
                        }
                    }]
                )

                self.logger.info(f"Task {task_id} approved via Slack and queued for execution")

                # Task will be executed by the executor service
                # Notifier will post completion notification to Slack automatically

                return jsonify({"text": "Task approved and queued for execution"})

            elif action == "reject":
                # Update task status
                self.task_queue.update_status(task_id, TaskStatus.CANCELLED)

                # Update Slack message
                self.slack.update_message(
                    channel=channel_id,
                    ts=message_ts,
                    text=f"❌ Task {task_id} rejected by <@{user_id}>"
                )

                return jsonify({"text": "Task rejected"})

        except Exception as e:
            self.logger.error(f"Error handling approval: {e}")
            return jsonify({"text": f"Error: {str(e)}"})

    def _execute_and_notify(self, task: Any, channel_id: str, thread_ts: str):
        """
        Execute task and send completion notification

        Args:
            task: Task object
            channel_id: Slack channel ID
            thread_ts: Thread timestamp
        """
        task_id = None
        try:
            # Get task_id whether task is object or string
            print(f"[DEBUG] _execute_and_notify called with task type: {type(task)}, value: {task}")
            if isinstance(task, str):
                task_id = task
                task = self.task_queue.get_task(task_id)
            else:
                task_id = task.task_id

            self.logger.info(f"Executing task {task_id} from Slack")

            # Execute task (this will take a while) - pass Task object, not task_id string
            self.agent_manager.execute_task(task)

            # Task completion notification will be sent by notifier automatically

        except Exception as e:
            import traceback
            self.logger.error(f"Task execution failed: {e}")
            self.logger.error(f"Traceback: {traceback.format_exc()}")
            try:
                # Use task_id if we have it
                msg = f"❌ Task {task_id} execution failed: {str(e)}" if task_id else f"❌ Task execution failed: {str(e)}"
                self.slack.post_message(
                    channel=channel_id,
                    text=msg,
                    thread_ts=thread_ts
                )
            except:
                pass

    def handle_details(self, task_id: str, user_id: str, channel_id: str) -> Dict:
        """
        Handle details button click

        Args:
            task_id: Task ID
            user_id: Slack user ID
            channel_id: Slack channel ID

        Returns:
            Response dict for Slack
        """
        try:
            task = self.task_queue.get_task(task_id)
            if not task:
                return jsonify({"text": f"Task {task_id} not found"})

            # Format detailed information
            tools_list = "\n".join([f"• {tool}" for tool in task.allowed_tools[:20]])
            if len(task.allowed_tools) > 20:
                tools_list += f"\n• ... and {len(task.allowed_tools) - 20} more"

            # Handle None case for allowed_directories
            if task.allowed_directories:
                dirs_list = "\n".join([f"• {d}" for d in task.allowed_directories[:10]])
                if len(task.allowed_directories) > 10:
                    dirs_list += f"\n• ... and {len(task.allowed_directories) - 10} more"
            else:
                dirs_list = ""

            details_text = f"""*Task Details: {task_id}*

*Description:*
{task.description[:1000]}

*Status:* {task.status}
*Timeout:* {task.timeout_seconds}s ({task.timeout_seconds // 60}m)
*Needs Git:* {'Yes' if task.needs_git else 'No'}

*Allowed Tools:*
{tools_list}

*Allowed Directories:*
{dirs_list if dirs_list else "None"}

*System Prompt:*
```
{task.system_prompt[:500]}
```
"""

            # Send as ephemeral message (only visible to user who clicked)
            self.slack.post_ephemeral(
                channel=channel_id,
                user=user_id,
                text=details_text
            )

            return jsonify({"text": "Details sent"})

        except Exception as e:
            self.logger.error(f"Error showing details: {e}")
            return jsonify({"text": f"Error: {str(e)}"})

    def handle_queue(self, args: str, user_id: str, channel_id: str) -> Dict:
        """
        Handle /nightshift queue command

        Args:
            args: Optional status filter
            user_id: Slack user ID
            channel_id: Slack channel ID

        Returns:
            Response dict for Slack
        """
        try:
            status_filter = args.strip().upper() if args.strip() else None

            # Get tasks
            if status_filter:
                tasks = self.task_queue.list_tasks(status=status_filter)
            else:
                tasks = self.task_queue.list_tasks()

            # Format as blocks
            blocks = SlackFormatter.format_task_list(tasks, status_filter)

            return jsonify({
                "response_type": "ephemeral",
                "blocks": blocks
            })

        except Exception as e:
            self.logger.error(f"Error listing queue: {e}")
            return jsonify({
                "response_type": "ephemeral",
                "text": f"Error: {str(e)}"
            })

    def handle_status(self, args: str, user_id: str, channel_id: str) -> Dict:
        """
        Handle /nightshift status command

        Args:
            args: Task ID
            user_id: Slack user ID
            channel_id: Slack channel ID

        Returns:
            Response dict for Slack
        """
        task_id = args.strip()
        if not task_id:
            return jsonify({
                "response_type": "ephemeral",
                "text": "Usage: `/nightshift status task_XXXXXXXX`"
            })

        try:
            task = self.task_queue.get_task(task_id)
            if not task:
                return jsonify({
                    "response_type": "ephemeral",
                    "text": f"Task {task_id} not found"
                })

            status_emoji = {
                "STAGED": "📝",
                "COMMITTED": "✔️",
                "RUNNING": "⏳",
                "PAUSED": "⏸️",
                "COMPLETED": "✅",
                "FAILED": "❌",
                "CANCELLED": "🚫"
            }.get(task.status, "❓")

            status_text = f"""{status_emoji} *Task Status: {task_id}*

*Status:* {task.status}
*Description:* {task.description[:200]}
*Created:* {task.created_at}
"""
            if task.status == "RUNNING" and task.result_path:
                status_text += f"\n*Output:* `{task.result_path}`"

            return jsonify({
                "response_type": "ephemeral",
                "text": status_text
            })

        except Exception as e:
            self.logger.error(f"Error getting status: {e}")
            return jsonify({
                "response_type": "ephemeral",
                "text": f"Error: {str(e)}"
            })

    def handle_cancel(self, args: str, user_id: str, channel_id: str) -> Dict:
        """Handle /nightshift cancel command"""
        task_id = args.strip()
        if not task_id:
            return jsonify({
                "response_type": "ephemeral",
                "text": "Usage: `/nightshift cancel task_XXXXXXXX`"
            })

        try:
            task = self.task_queue.get_task(task_id)
            if not task:
                return jsonify({
                    "response_type": "ephemeral",
                    "text": f"Task {task_id} not found"
                })

            if task.status not in ["STAGED", "COMMITTED"]:
                return jsonify({
                    "response_type": "ephemeral",
                    "text": f"Cannot cancel task in {task.status} state"
                })

            self.task_queue.update_status(task_id, TaskStatus.CANCELLED)

            return jsonify({
                "response_type": "in_channel",
                "text": f"✅ Task {task_id} cancelled by <@{user_id}>"
            })

        except Exception as e:
            self.logger.error(f"Error cancelling task: {e}")
            return jsonify({
                "response_type": "ephemeral",
                "text": f"Error: {str(e)}"
            })

    def handle_pause(self, args: str, user_id: str, channel_id: str) -> Dict:
        """Handle /nightshift pause command"""
        task_id = args.strip()
        if not task_id:
            return jsonify({
                "response_type": "ephemeral",
                "text": "Usage: `/nightshift pause task_XXXXXXXX`"
            })

        try:
            self.agent_manager.pause_task(task_id)
            return jsonify({
                "response_type": "in_channel",
                "text": f"⏸️ Task {task_id} paused by <@{user_id}>"
            })
        except Exception as e:
            return jsonify({
                "response_type": "ephemeral",
                "text": f"Error: {str(e)}"
            })

    def handle_resume(self, args: str, user_id: str, channel_id: str) -> Dict:
        """Handle /nightshift resume command"""
        task_id = args.strip()
        if not task_id:
            return jsonify({
                "response_type": "ephemeral",
                "text": "Usage: `/nightshift resume task_XXXXXXXX`"
            })

        try:
            self.agent_manager.resume_task(task_id)
            return jsonify({
                "response_type": "in_channel",
                "text": f"▶️ Task {task_id} resumed by <@{user_id}>"
            })
        except Exception as e:
            return jsonify({
                "response_type": "ephemeral",
                "text": f"Error: {str(e)}"
            })

    def handle_kill(self, args: str, user_id: str, channel_id: str) -> Dict:
        """Handle /nightshift kill command"""
        task_id = args.strip()
        if not task_id:
            return jsonify({
                "response_type": "ephemeral",
                "text": "Usage: `/nightshift kill task_XXXXXXXX`"
            })

        try:
            self.agent_manager.kill_task(task_id)
            return jsonify({
                "response_type": "in_channel",
                "text": f"🛑 Task {task_id} killed by <@{user_id}>"
            })
        except Exception as e:
            return jsonify({
                "response_type": "ephemeral",
                "text": f"Error: {str(e)}"
            })

    def handle_modal_submission(self, payload: Dict) -> Dict:
        """
        Handle modal submissions (for revision workflow, Phase 2)

        Args:
            payload: Modal submission payload

        Returns:
            Response dict for Slack
        """
        # Placeholder for Phase 2
        return jsonify({"response_action": "clear"})
