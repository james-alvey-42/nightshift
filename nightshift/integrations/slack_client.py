"""
Slack Client Wrapper
Provides abstraction over Slack SDK with error handling and retry logic
"""
import time
from typing import Dict, List, Optional, Any
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError


class SlackResponse:
    """Wrapper for Slack API response"""

    def __init__(self, data: Dict[str, Any]):
        self.data = data
        self.ok = data.get("ok", False)
        self.error = data.get("error")
        self.ts = data.get("ts")
        self.channel = data.get("channel")
        self.message = data.get("message", {})


class SlackClient:
    """
    Slack SDK wrapper with error handling, retries, and convenience methods
    """

    def __init__(self, bot_token: str, max_retries: int = 3):
        """
        Initialize Slack client

        Args:
            bot_token: Slack bot token (xoxb-...)
            max_retries: Maximum number of retries for failed requests
        """
        self.client = WebClient(token=bot_token)
        self.max_retries = max_retries

    def post_message(
        self,
        channel: str,
        text: str,
        blocks: Optional[List[Dict]] = None,
        thread_ts: Optional[str] = None,
        unfurl_links: bool = False,
        unfurl_media: bool = False
    ) -> SlackResponse:
        """
        Post a message to a Slack channel

        Args:
            channel: Channel ID (e.g., C123456) or name (e.g., #general)
            text: Plain text message (fallback for notifications)
            blocks: Block Kit blocks for rich formatting
            thread_ts: Parent message timestamp (for threading)
            unfurl_links: Automatically unfurl links
            unfurl_media: Automatically unfurl media

        Returns:
            SlackResponse object with response data

        Raises:
            SlackApiError: If all retries fail
        """
        return self._retry_request(
            self.client.chat_postMessage,
            channel=channel,
            text=text,
            blocks=blocks,
            thread_ts=thread_ts,
            unfurl_links=unfurl_links,
            unfurl_media=unfurl_media
        )

    def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: Optional[List[Dict]] = None
    ) -> SlackResponse:
        """
        Update an existing message

        Args:
            channel: Channel ID where the message was posted
            ts: Message timestamp to update
            text: New plain text content
            blocks: New Block Kit blocks

        Returns:
            SlackResponse object with response data

        Raises:
            SlackApiError: If all retries fail
        """
        return self._retry_request(
            self.client.chat_update,
            channel=channel,
            ts=ts,
            text=text,
            blocks=blocks
        )

    def post_ephemeral(
        self,
        channel: str,
        user: str,
        text: str,
        blocks: Optional[List[Dict]] = None,
        thread_ts: Optional[str] = None
    ) -> SlackResponse:
        """
        Post an ephemeral message (only visible to one user)

        Args:
            channel: Channel ID where to post
            user: User ID who will see the message
            text: Plain text message
            blocks: Block Kit blocks
            thread_ts: Parent message timestamp

        Returns:
            SlackResponse object with response data

        Raises:
            SlackApiError: If all retries fail
        """
        return self._retry_request(
            self.client.chat_postEphemeral,
            channel=channel,
            user=user,
            text=text,
            blocks=blocks,
            thread_ts=thread_ts
        )

    def upload_file(
        self,
        channels: str,
        file_path: str,
        title: Optional[str] = None,
        initial_comment: Optional[str] = None,
        thread_ts: Optional[str] = None
    ) -> SlackResponse:
        """
        Upload a file to Slack

        Args:
            channels: Comma-separated channel IDs
            file_path: Path to file to upload
            title: File title
            initial_comment: Comment to post with file
            thread_ts: Parent message timestamp

        Returns:
            SlackResponse object with response data

        Raises:
            SlackApiError: If all retries fail
        """
        return self._retry_request(
            self.client.files_upload_v2,
            channel=channels,
            file=file_path,
            title=title,
            initial_comment=initial_comment,
            thread_ts=thread_ts
        )

    def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """
        Get user information

        Args:
            user_id: Slack user ID

        Returns:
            User info dictionary

        Raises:
            SlackApiError: If request fails
        """
        response = self._retry_request(
            self.client.users_info,
            user=user_id
        )
        return response.data.get("user", {})

    def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """
        Get channel information

        Args:
            channel_id: Slack channel ID

        Returns:
            Channel info dictionary

        Raises:
            SlackApiError: If request fails
        """
        response = self._retry_request(
            self.client.conversations_info,
            channel=channel_id
        )
        return response.data.get("channel", {})

    def _retry_request(self, method, **kwargs) -> SlackResponse:
        """
        Execute Slack API request with retry logic

        Args:
            method: Slack SDK method to call
            **kwargs: Arguments to pass to method

        Returns:
            SlackResponse object

        Raises:
            SlackApiError: If all retries fail
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = method(**kwargs)
                return SlackResponse(response.data)

            except SlackApiError as e:
                last_error = e

                # Check if rate limited
                if e.response.get("error") == "rate_limited":
                    # Get retry-after header or use exponential backoff
                    retry_after = e.response.headers.get("Retry-After")
                    if retry_after:
                        delay = int(retry_after)
                    else:
                        delay = 2 ** attempt  # Exponential backoff: 1s, 2s, 4s

                    if attempt < self.max_retries - 1:
                        time.sleep(delay)
                        continue

                # For other errors, don't retry
                raise

        # If we exhausted all retries, raise the last error
        raise last_error

    def test_connection(self) -> bool:
        """
        Test if the Slack connection is working

        Returns:
            True if connection works, False otherwise
        """
        try:
            response = self.client.auth_test()
            return response.get("ok", False)
        except SlackApiError:
            return False
