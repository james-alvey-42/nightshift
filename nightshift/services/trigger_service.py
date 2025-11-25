"""
Remote Trigger Service
Main webhook handler that processes messages from all platforms
"""
import uuid
from typing import Dict, Any, Optional
from pathlib import Path

from .auth.authenticator import Authenticator, AuthMethod
from .auth.user_mapper import UserMapper
from .platforms.base import PlatformHandler, PlatformMessage, PlatformResponse, MessageType
from .platforms.slack import SlackPlatform

from ..core.task_queue import TaskQueue, TaskStatus
from ..core.task_planner import TaskPlanner
from ..core.agent_manager import AgentManager
from ..core.logger import NightShiftLogger


class TriggerService:
    """
    Remote trigger service for NightShift

    Handles:
    - Webhook reception from messaging platforms
    - User authentication and authorization
    - Task submission and approval
    - Status updates and notifications
    """

    def __init__(
        self,
        config: Dict[str, Any],
        task_queue: TaskQueue,
        task_planner: TaskPlanner,
        agent_manager: AgentManager,
        logger: NightShiftLogger
    ):
        """
        Initialize trigger service

        Args:
            config: Remote trigger configuration
            task_queue: TaskQueue instance
            task_planner: TaskPlanner instance
            agent_manager: AgentManager instance
            logger: Logger instance
        """
        self.config = config
        self.task_queue = task_queue
        self.task_planner = task_planner
        self.agent_manager = agent_manager
        self.logger = logger

        # Initialize authentication
        auth_config = config.get('auth', {})
        self.authenticator = Authenticator(auth_config)

        # Initialize user mapper
        user_db_path = config.get('user_db_path', str(Path.home() / '.nightshift' / 'database' / 'users.db'))
        self.user_mapper = UserMapper(user_db_path)

        # Initialize platform handlers
        self.platforms: Dict[str, PlatformHandler] = {}
        self._init_platforms()

    def _init_platforms(self):
        """Initialize enabled platform handlers"""
        platforms_config = self.config.get('platforms', {})

        # Initialize Slack if enabled
        slack_config = platforms_config.get('slack', {})
        if slack_config.get('enabled', False):
            self.platforms['slack'] = SlackPlatform(slack_config, self.authenticator)
            self.logger.info("Slack platform integration enabled")

        # TODO: Initialize other platforms (WhatsApp, Telegram, Discord)

    def handle_webhook(
        self,
        platform: str,
        headers: Dict[str, str],
        body: str,
        payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle incoming webhook from a platform

        Args:
            platform: Platform name (slack, whatsapp, etc.)
            headers: HTTP headers
            body: Raw request body
            payload: Parsed JSON payload

        Returns:
            Response dictionary with status and message
        """
        # Check if platform is enabled
        if platform not in self.platforms:
            return {
                'success': False,
                'error': f'Platform not enabled: {platform}'
            }

        handler = self.platforms[platform]

        # Validate webhook signature
        if not handler.validate_webhook(headers, body):
            self.logger.warning(f"Invalid webhook signature from {platform}")
            return {
                'success': False,
                'error': 'Invalid signature'
            }

        # Handle Slack URL verification challenge
        if platform == 'slack' and payload.get('type') == 'url_verification':
            return {
                'success': True,
                'challenge': payload.get('challenge')
            }

        # Parse message
        message = handler.parse_webhook(payload)
        if not message:
            return {
                'success': True,
                'message': 'Ignored'
            }

        # Map platform user to NightShift user
        platform_user = self.user_mapper.get_nightshift_user(
            platform=message.platform,
            user_id=message.user_id
        )

        # Auto-register new users
        if not platform_user:
            nightshift_user_id = self.user_mapper.map_user(
                platform=message.platform,
                platform_user_id=message.user_id
            )
            # Set default quotas
            self.user_mapper.set_quota(nightshift_user_id)
            self.logger.info(f"Auto-registered user: {nightshift_user_id}")
        else:
            nightshift_user_id = platform_user.nightshift_user_id
            self.user_mapper.update_last_seen(message.platform, message.user_id)

        # Route message based on type
        if message.message_type == MessageType.COMMAND:
            return self._handle_command(handler, message, nightshift_user_id)
        elif message.message_type == MessageType.INTERACTIVE:
            return self._handle_interactive(handler, message, nightshift_user_id)
        elif message.message_type == MessageType.STATUS_REQUEST:
            return self._handle_status_request(handler, message, nightshift_user_id)
        elif message.message_type == MessageType.TEXT:
            return self._handle_text(handler, message, nightshift_user_id)

        return {
            'success': True,
            'message': 'Processed'
        }

    def _handle_command(
        self,
        handler: PlatformHandler,
        message: PlatformMessage,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Handle task submission command

        Example: /nightshift analyze papers on transformers
        """
        description = message.text.strip()

        if not description:
            handler.send_message(PlatformResponse(
                text="Usage: /nightshift <task description>",
                channel_id=message.channel_id,
                thread_id=message.thread_id
            ))
            return {'success': True}

        try:
            # Check user quotas
            quota = self.user_mapper.get_quota(user_id)
            if quota:
                # TODO: Implement quota checking
                pass

            # Send "planning" message
            handler.send_message(PlatformResponse(
                text="🤔 Planning your task...",
                channel_id=message.channel_id,
                thread_id=message.thread_id
            ))

            # Plan task
            plan = self.task_planner.plan_task(description)

            # Generate task ID
            task_id = f"task_{uuid.uuid4().hex[:8]}"

            # Create task in STAGED state
            task = self.task_queue.create_task(
                task_id=task_id,
                description=plan['enhanced_prompt'],
                allowed_tools=plan['allowed_tools'],
                system_prompt=plan['system_prompt'],
                estimated_tokens=plan['estimated_tokens'],
                estimated_time=plan['estimated_time']
            )

            self.logger.log_task_created(task_id, description)
            self.logger.info(f"Task {task_id} created by {user_id} via {message.platform}")

            # Send task submission with approval buttons (platform-specific)
            if isinstance(handler, SlackPlatform):
                formatted = handler.format_task_submission(
                    task_id=task_id,
                    description=plan['enhanced_prompt'],
                    estimated_tokens=plan['estimated_tokens'],
                    estimated_time=plan['estimated_time']
                )
                handler.send_message(PlatformResponse(
                    text=formatted['text'],
                    channel_id=message.channel_id,
                    thread_id=message.thread_id,
                    blocks=formatted['blocks']
                ))
            else:
                # Fallback for other platforms
                response_text = (
                    f"✨ Task created: {task_id}\n\n"
                    f"Description: {plan['enhanced_prompt']}\n"
                    f"Estimated: ~{plan['estimated_tokens']} tokens, ~{plan['estimated_time']}s\n\n"
                    f"Reply 'approve {task_id}' to execute"
                )
                handler.send_message(PlatformResponse(
                    text=response_text,
                    channel_id=message.channel_id,
                    thread_id=message.thread_id
                ))

            return {
                'success': True,
                'task_id': task_id
            }

        except Exception as e:
            self.logger.error(f"Error handling command: {str(e)}")
            handler.send_message(PlatformResponse(
                text=f"❌ Error: {str(e)}",
                channel_id=message.channel_id,
                thread_id=message.thread_id
            ))
            return {
                'success': False,
                'error': str(e)
            }

    def _handle_interactive(
        self,
        handler: PlatformHandler,
        message: PlatformMessage,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Handle interactive action (button click)

        Example: Approve button clicked
        """
        action_data = message.text.split(':', 1)
        if len(action_data) != 2:
            return {'success': False, 'error': 'Invalid action format'}

        action_id, task_id = action_data

        try:
            # Get task
            task = self.task_queue.get_task(task_id)
            if not task:
                handler.send_message(PlatformResponse(
                    text=f"❌ Task {task_id} not found",
                    channel_id=message.channel_id
                ))
                return {'success': False, 'error': 'Task not found'}

            if action_id == 'approve_task':
                # Approve and execute task
                if task.status != TaskStatus.STAGED.value:
                    handler.send_message(PlatformResponse(
                        text=f"❌ Task {task_id} is not in STAGED state (current: {task.status})",
                        channel_id=message.channel_id
                    ))
                    return {'success': False, 'error': 'Invalid task status'}

                # Update to COMMITTED
                self.task_queue.update_status(task_id, TaskStatus.COMMITTED)
                self.logger.log_task_approved(task_id)

                # Send execution message
                handler.send_message(PlatformResponse(
                    text=f"▶️ Executing task {task_id}...",
                    channel_id=message.channel_id,
                    thread_id=message.thread_id
                ))

                # Execute task (async in production)
                # TODO: Use message queue for async execution
                result = self.agent_manager.execute_task(task)

                # Send completion message
                if result['success']:
                    response_text = (
                        f"✅ Task {task_id} completed successfully!\n"
                        f"Token usage: {result.get('token_usage', 'N/A')}\n"
                        f"Execution time: {result['execution_time']:.1f}s\n"
                        f"Results: {result.get('result_path', 'N/A')}"
                    )
                else:
                    response_text = f"❌ Task {task_id} failed: {result.get('error')}"

                handler.send_message(PlatformResponse(
                    text=response_text,
                    channel_id=message.channel_id,
                    thread_id=message.thread_id
                ))

                return {
                    'success': True,
                    'action': 'approved',
                    'task_id': task_id,
                    'result': result
                }

            elif action_id == 'cancel_task':
                # Cancel task
                self.task_queue.update_status(task_id, TaskStatus.CANCELLED)
                handler.send_message(PlatformResponse(
                    text=f"✕ Task {task_id} cancelled",
                    channel_id=message.channel_id
                ))

                return {
                    'success': True,
                    'action': 'cancelled',
                    'task_id': task_id
                }

        except Exception as e:
            self.logger.error(f"Error handling interactive action: {str(e)}")
            handler.send_message(PlatformResponse(
                text=f"❌ Error: {str(e)}",
                channel_id=message.channel_id
            ))
            return {
                'success': False,
                'error': str(e)
            }

    def _handle_status_request(
        self,
        handler: PlatformHandler,
        message: PlatformMessage,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Handle status request

        Example: /nightshift status task_12345678
        """
        parts = message.text.split()
        if len(parts) < 2:
            handler.send_message(PlatformResponse(
                text="Usage: /nightshift status <task_id>",
                channel_id=message.channel_id
            ))
            return {'success': True}

        task_id = parts[1]

        try:
            task = self.task_queue.get_task(task_id)
            if not task:
                handler.send_message(PlatformResponse(
                    text=f"❌ Task {task_id} not found",
                    channel_id=message.channel_id
                ))
                return {'success': False, 'error': 'Task not found'}

            # Format status message
            status_text = (
                f"📊 Task Status: {task_id}\n\n"
                f"Status: {task.status.upper()}\n"
                f"Description: {task.description[:100]}...\n"
                f"Created: {task.created_at}\n"
            )

            if task.started_at:
                status_text += f"Started: {task.started_at}\n"
            if task.completed_at:
                status_text += f"Completed: {task.completed_at}\n"
            if task.token_usage:
                status_text += f"Token usage: {task.token_usage}\n"
            if task.execution_time:
                status_text += f"Execution time: {task.execution_time:.1f}s\n"
            if task.error_message:
                status_text += f"\n❌ Error: {task.error_message}\n"

            handler.send_message(PlatformResponse(
                text=status_text,
                channel_id=message.channel_id
            ))

            return {
                'success': True,
                'task_id': task_id,
                'status': task.status
            }

        except Exception as e:
            self.logger.error(f"Error handling status request: {str(e)}")
            handler.send_message(PlatformResponse(
                text=f"❌ Error: {str(e)}",
                channel_id=message.channel_id
            ))
            return {
                'success': False,
                'error': str(e)
            }

    def _handle_text(
        self,
        handler: PlatformHandler,
        message: PlatformMessage,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Handle plain text message (app mention, DM, etc.)

        Parse for commands like "approve task_XXX" or treat as task submission
        """
        text = message.text.strip().lower()

        # Check for approval command
        if text.startswith('approve '):
            task_id = text.split()[1] if len(text.split()) > 1 else None
            if task_id:
                # Simulate interactive approval
                message.message_type = MessageType.INTERACTIVE
                message.text = f"approve_task:{task_id}"
                return self._handle_interactive(handler, message, user_id)

        # Check for status command
        if text.startswith('status '):
            message.message_type = MessageType.STATUS_REQUEST
            return self._handle_status_request(handler, message, user_id)

        # Otherwise treat as task submission
        message.message_type = MessageType.COMMAND
        return self._handle_command(handler, message, user_id)
