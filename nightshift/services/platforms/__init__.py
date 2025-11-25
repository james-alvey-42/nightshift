"""
Messaging Platform Integrations
Slack, WhatsApp, Telegram, Discord bot implementations
"""

from .slack import SlackPlatform
from .base import PlatformHandler, PlatformMessage

__all__ = ['SlackPlatform', 'PlatformHandler', 'PlatformMessage']
