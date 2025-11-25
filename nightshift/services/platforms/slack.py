"""
Slack Platform Integration
Handles Slack slash commands, interactive buttons, and message delivery
"""
import json
import requests
from typing import Optional, Dict, Any, List
from ..auth.authenticator import Authenticator, AuthMethod, AuthResult
from .base import PlatformHandler, PlatformMessage, PlatformResponse, MessageType


class SlackPlatform(PlatformHandler):
    """
    Slack integration for NightShift

    Supports:
    - Slash commands (/nightshift)
    - Interactive buttons for task approval
    - Direct messages and status updates
    - Threaded conversations
    """

    def __init__(self, config: Dict[str, Any], authenticator: Authenticator):
        """
        Initialize Slack platform handler

        Args:
            config: Slack configuration including:
                - bot_token: Slack Bot User OAuth Token
                - signing_secret: Slack Signing Secret for webhook verification
                - enabled: Whether Slack integration is enabled
            authenticator: Authenticator instance for signature verification
        """
        super().__init__(config)
        self.bot_token = config.get('bot_token')
        self.signing_secret = config.get('signing_secret')
        self.authenticator = authenticator

        # Slack API endpoints
        self.api_base = "https://slack.com/api"

    def validate_webhook(self, headers: Dict[str, str], body: str) -> bool:
        """
        Validate Slack webhook signature
        https://api.slack.com/authentication/verifying-requests-from-slack
        """
        signature = headers.get('X-Slack-Signature', '')
        timestamp = headers.get('X-Slack-Request-Timestamp', '')

        if not signature or not timestamp:
            return False

        # Use authenticator to verify signature
        result = self.authenticator.authenticate(
            {
                'platform': 'slack',
                'signature': signature,
                'timestamp': timestamp,
                'body': body
            },
            method=AuthMethod.PLATFORM_SIGNATURE
        )

        return result.success

    def parse_webhook(self, payload: Dict[str, Any]) -> Optional[PlatformMessage]:
        """
        Parse Slack webhook payload

        Handles:
        - Slash commands (/nightshift)
        - Interactive component callbacks (button clicks)
        - App mentions
        """
        # Handle slash command
        if payload.get('command') == '/nightshift':
            return self._parse_slash_command(payload)

        # Handle interactive component (button click)
        if payload.get('type') == 'block_actions':
            return self._parse_interactive_action(payload)

        # Handle app mention
        if payload.get('type') == 'event_callback':
            event = payload.get('event', {})
            if event.get('type') == 'app_mention':
                return self._parse_app_mention(event)

        # Handle URL verification challenge (Slack setup)
        if payload.get('type') == 'url_verification':
            # This is handled separately in the trigger service
            return None

        return None

    def _parse_slash_command(self, payload: Dict[str, Any]) -> PlatformMessage:
        """Parse /nightshift slash command"""
        text = payload.get('text', '').strip()
        user_id = payload.get('user_id')
        channel_id = payload.get('channel_id')
        response_url = payload.get('response_url')

        # Determine message type based on command
        if text.startswith('status'):
            message_type = MessageType.STATUS_REQUEST
        else:
            message_type = MessageType.COMMAND

        return PlatformMessage(
            platform='slack',
            user_id=user_id,
            message_type=message_type,
            text=text,
            channel_id=channel_id,
            metadata={
                'response_url': response_url,
                'team_id': payload.get('team_id'),
                'trigger_id': payload.get('trigger_id')
            }
        )

    def _parse_interactive_action(self, payload: Dict[str, Any]) -> PlatformMessage:
        """Parse interactive component action (button click)"""
        user = payload.get('user', {})
        user_id = user.get('id')
        channel = payload.get('channel', {})
        channel_id = channel.get('id')

        actions = payload.get('actions', [])
        if not actions:
            return None

        action = actions[0]  # Get first action
        action_id = action.get('action_id')
        value = action.get('value')

        return PlatformMessage(
            platform='slack',
            user_id=user_id,
            message_type=MessageType.INTERACTIVE,
            text=f"{action_id}:{value}",
            channel_id=channel_id,
            metadata={
                'action_id': action_id,
                'value': value,
                'response_url': payload.get('response_url'),
                'message': payload.get('message')
            }
        )

    def _parse_app_mention(self, event: Dict[str, Any]) -> PlatformMessage:
        """Parse app mention (@nightshift)"""
        text = event.get('text', '')
        user_id = event.get('user')
        channel_id = event.get('channel')
        thread_ts = event.get('thread_ts')

        # Remove bot mention from text
        # Slack sends mentions as <@BOT_USER_ID>
        import re
        text = re.sub(r'<@[A-Z0-9]+>', '', text).strip()

        return PlatformMessage(
            platform='slack',
            user_id=user_id,
            message_type=MessageType.TEXT,
            text=text,
            channel_id=channel_id,
            thread_id=thread_ts,
            metadata={'event': event}
        )

    def send_message(self, response: PlatformResponse) -> bool:
        """
        Send message to Slack channel/DM

        Uses chat.postMessage API
        """
        if not self.bot_token:
            return False

        url = f"{self.api_base}/chat.postMessage"

        payload = {
            'channel': response.channel_id,
            'text': response.text,
        }

        # Add thread support
        if response.thread_id:
            payload['thread_ts'] = response.thread_id

        # Add rich blocks if provided
        if response.blocks:
            payload['blocks'] = response.blocks

        headers = {
            'Authorization': f'Bearer {self.bot_token}',
            'Content-Type': 'application/json'
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            result = resp.json()
            return result.get('ok', False)
        except Exception as e:
            print(f"Error sending Slack message: {e}")
            return False

    def send_interactive(
        self,
        channel_id: str,
        text: str,
        actions: List[Dict[str, Any]],
        thread_id: Optional[str] = None
    ) -> bool:
        """
        Send interactive message with buttons

        Args:
            channel_id: Slack channel ID
            text: Message text
            actions: List of button definitions (Slack action blocks)
            thread_id: Optional thread timestamp for threading

        Example actions:
        [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Approve"},
                "action_id": "approve_task",
                "value": "task_12345678",
                "style": "primary"
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Cancel"},
                "action_id": "cancel_task",
                "value": "task_12345678",
                "style": "danger"
            }
        ]
        """
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": text
                }
            },
            {
                "type": "actions",
                "elements": actions
            }
        ]

        response = PlatformResponse(
            text=text,
            channel_id=channel_id,
            thread_id=thread_id,
            blocks=blocks
        )

        return self.send_message(response)

    def send_ephemeral(
        self,
        channel_id: str,
        user_id: str,
        text: str
    ) -> bool:
        """
        Send ephemeral message (only visible to specific user)

        Useful for error messages and private feedback
        """
        if not self.bot_token:
            return False

        url = f"{self.api_base}/chat.postEphemeral"

        payload = {
            'channel': channel_id,
            'user': user_id,
            'text': text
        }

        headers = {
            'Authorization': f'Bearer {self.bot_token}',
            'Content-Type': 'application/json'
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            result = resp.json()
            return result.get('ok', False)
        except Exception as e:
            print(f"Error sending ephemeral message: {e}")
            return False

    def update_message(
        self,
        channel_id: str,
        message_ts: str,
        text: str,
        blocks: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        Update an existing message

        Useful for updating task status in place
        """
        if not self.bot_token:
            return False

        url = f"{self.api_base}/chat.update"

        payload = {
            'channel': channel_id,
            'ts': message_ts,
            'text': text
        }

        if blocks:
            payload['blocks'] = blocks

        headers = {
            'Authorization': f'Bearer {self.bot_token}',
            'Content-Type': 'application/json'
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            result = resp.json()
            return result.get('ok', False)
        except Exception as e:
            print(f"Error updating message: {e}")
            return False

    def format_task_submission(
        self,
        task_id: str,
        description: str,
        estimated_tokens: int,
        estimated_time: int
    ) -> Dict[str, Any]:
        """
        Format task submission response with approval buttons

        Returns Slack blocks for rich formatting
        """
        return {
            'text': f'Task {task_id} created',
            'blocks': [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"✨ Task Created: {task_id}"
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
                            "text": f"*Estimated Tokens:*\n~{estimated_tokens}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Estimated Time:*\n~{estimated_time}s"
                        }
                    ]
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✓ Approve & Execute"
                            },
                            "action_id": "approve_task",
                            "value": task_id,
                            "style": "primary"
                        },
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "✕ Cancel"
                            },
                            "action_id": "cancel_task",
                            "value": task_id,
                            "style": "danger"
                        }
                    ]
                }
            ]
        }
