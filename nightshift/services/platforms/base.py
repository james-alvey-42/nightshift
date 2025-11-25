"""
Base Platform Handler
Abstract interface for messaging platform integrations
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from enum import Enum


class MessageType(Enum):
    """Types of messages from platforms"""
    COMMAND = "command"
    TEXT = "text"
    INTERACTIVE = "interactive"  # Button clicks, menu selections
    STATUS_REQUEST = "status_request"


@dataclass
class PlatformMessage:
    """Represents a message from a messaging platform"""
    platform: str
    user_id: str
    message_type: MessageType
    text: str
    channel_id: Optional[str] = None
    thread_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class PlatformResponse:
    """Response to send back to platform"""
    text: str
    channel_id: Optional[str] = None
    thread_id: Optional[str] = None
    blocks: Optional[List[Dict[str, Any]]] = None  # For rich formatting
    metadata: Optional[Dict[str, Any]] = None


class PlatformHandler(ABC):
    """
    Abstract base class for messaging platform handlers

    Each platform integration should inherit from this and implement:
    - parse_webhook: Parse incoming webhook payload
    - send_message: Send message to user/channel
    - send_interactive: Send interactive components (buttons, etc.)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize platform handler

        Args:
            config: Platform-specific configuration
        """
        self.config = config
        self.enabled = config.get('enabled', False)

    @abstractmethod
    def parse_webhook(self, payload: Dict[str, Any]) -> Optional[PlatformMessage]:
        """
        Parse incoming webhook payload into standardized message

        Args:
            payload: Raw webhook payload from platform

        Returns:
            PlatformMessage if valid, None if should be ignored
        """
        pass

    @abstractmethod
    def send_message(self, response: PlatformResponse) -> bool:
        """
        Send message back to platform

        Args:
            response: Message to send

        Returns:
            True if sent successfully
        """
        pass

    @abstractmethod
    def send_interactive(
        self,
        channel_id: str,
        text: str,
        actions: List[Dict[str, Any]],
        thread_id: Optional[str] = None
    ) -> bool:
        """
        Send interactive message with buttons/actions

        Args:
            channel_id: Channel/chat to send to
            text: Message text
            actions: List of action definitions (platform-specific)
            thread_id: Optional thread ID for threading

        Returns:
            True if sent successfully
        """
        pass

    @abstractmethod
    def validate_webhook(self, headers: Dict[str, str], body: str) -> bool:
        """
        Validate webhook signature/authenticity

        Args:
            headers: HTTP headers from webhook request
            body: Raw request body

        Returns:
            True if valid
        """
        pass
