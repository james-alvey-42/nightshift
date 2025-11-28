"""
Configuration management for NightShift
Handles paths and settings
"""
from pathlib import Path
import os
import json
from typing import Optional


class Config:
    """NightShift configuration"""

    def __init__(self, base_dir: str = None):
        """
        Initialize configuration

        Args:
            base_dir: Base directory for NightShift data.
                     Defaults to ~/.nightshift
        """
        if base_dir is None:
            base_dir = Path.home() / ".nightshift"
        else:
            base_dir = Path(base_dir)

        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.database_dir = self.base_dir / "database"
        self.database_dir.mkdir(exist_ok=True)

        self.logs_dir = self.base_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)

        self.output_dir = self.base_dir / "output"
        self.output_dir.mkdir(exist_ok=True)

        self.notifications_dir = self.base_dir / "notifications"
        self.notifications_dir.mkdir(exist_ok=True)

        self.slack_metadata_dir = self.base_dir / "slack_metadata"
        self.slack_metadata_dir.mkdir(exist_ok=True)

        # Database path
        self.db_path = self.database_dir / "nightshift.db"

        # Package config directory (for tools reference, etc.)
        package_dir = Path(__file__).parent.parent
        self.config_dir = package_dir / "config"

        self.tools_reference_path = self.config_dir / "claude-code-tools-reference.md"
        self.directory_map_path = self.config_dir / "directory-map.md"
        self.slack_config_path = self.base_dir / "slack_config.json"

        # Load Slack configuration
        self._load_slack_config()

        # Load executor configuration
        self._load_executor_config()

    def get_log_dir(self) -> Path:
        """Get logs directory"""
        return self.logs_dir

    def get_database_path(self) -> Path:
        """Get database file path"""
        return self.db_path

    def get_output_dir(self) -> Path:
        """Get output directory"""
        return self.output_dir

    def get_notifications_dir(self) -> Path:
        """Get notifications directory"""
        return self.notifications_dir

    def get_tools_reference_path(self) -> Path:
        """Get tools reference file path"""
        return self.tools_reference_path

    def get_directory_map_path(self) -> Path:
        """Get directory map file path"""
        return self.directory_map_path

    def get_slack_metadata_dir(self) -> Path:
        """Get Slack metadata directory"""
        return self.slack_metadata_dir

    def _load_slack_config(self):
        """Load Slack configuration from environment variables or config file"""
        # Initialize with defaults
        self.slack_enabled = False
        self.slack_bot_token: Optional[str] = None
        self.slack_signing_secret: Optional[str] = None
        self.slack_app_token: Optional[str] = None
        self.slack_webhook_port: int = 5000
        self.slack_webhook_host: str = "0.0.0.0"
        self.slack_enable_threads: bool = True
        self.slack_default_channel: Optional[str] = None

        # Try environment variables first
        self.slack_bot_token = os.environ.get("NIGHTSHIFT_SLACK_BOT_TOKEN")
        self.slack_signing_secret = os.environ.get("NIGHTSHIFT_SLACK_SIGNING_SECRET")
        self.slack_app_token = os.environ.get("NIGHTSHIFT_SLACK_APP_TOKEN")

        # Override with config file if it exists
        if self.slack_config_path.exists():
            try:
                with open(self.slack_config_path, "r") as f:
                    config_data = json.load(f)
                    self.slack_bot_token = config_data.get("bot_token", self.slack_bot_token)
                    self.slack_signing_secret = config_data.get("signing_secret", self.slack_signing_secret)
                    self.slack_app_token = config_data.get("app_token", self.slack_app_token)
                    self.slack_webhook_port = config_data.get("webhook_port", self.slack_webhook_port)
                    self.slack_webhook_host = config_data.get("webhook_host", self.slack_webhook_host)
                    self.slack_enable_threads = config_data.get("enable_threads", self.slack_enable_threads)
                    self.slack_default_channel = config_data.get("default_channel", self.slack_default_channel)
            except (json.JSONDecodeError, IOError) as e:
                # If config file is invalid, just use environment variables
                pass

        # Enable Slack if credentials are present
        if self.slack_bot_token and self.slack_signing_secret:
            self.slack_enabled = True

    def set_slack_config(
        self,
        bot_token: str,
        signing_secret: str,
        app_token: Optional[str] = None,
        webhook_port: int = 5000,
        webhook_host: str = "0.0.0.0",
        enable_threads: bool = True,
        default_channel: Optional[str] = None
    ):
        """
        Set and persist Slack configuration

        Args:
            bot_token: Slack bot token (xoxb-...)
            signing_secret: Slack signing secret
            app_token: Slack app token (xapp-...) for Socket Mode (optional)
            webhook_port: Port for webhook server (default: 5000)
            webhook_host: Host for webhook server (default: 0.0.0.0)
            enable_threads: Use threads for conversations (default: True)
            default_channel: Fallback channel ID (optional)
        """
        config_data = {
            "bot_token": bot_token,
            "signing_secret": signing_secret,
            "app_token": app_token,
            "webhook_port": webhook_port,
            "webhook_host": webhook_host,
            "enable_threads": enable_threads,
            "default_channel": default_channel
        }

        # Save to file
        with open(self.slack_config_path, "w") as f:
            json.dump(config_data, f, indent=2)

        # Update instance variables
        self.slack_bot_token = bot_token
        self.slack_signing_secret = signing_secret
        self.slack_app_token = app_token
        self.slack_webhook_port = webhook_port
        self.slack_webhook_host = webhook_host
        self.slack_enable_threads = enable_threads
        self.slack_default_channel = default_channel
        self.slack_enabled = True

    def get_slack_config(self) -> dict:
        """Get current Slack configuration (with masked secrets)"""
        return {
            "enabled": self.slack_enabled,
            "bot_token": self._mask_token(self.slack_bot_token) if self.slack_bot_token else None,
            "signing_secret": self._mask_token(self.slack_signing_secret) if self.slack_signing_secret else None,
            "app_token": self._mask_token(self.slack_app_token) if self.slack_app_token else None,
            "webhook_port": self.slack_webhook_port,
            "webhook_host": self.slack_webhook_host,
            "enable_threads": self.slack_enable_threads,
            "default_channel": self.slack_default_channel
        }

    @staticmethod
    def _mask_token(token: str) -> str:
        """Mask token for display (show first 8 chars only)"""
        if not token or len(token) < 12:
            return "***"
        return f"{token[:8]}...{token[-4:]}"

    def _load_executor_config(self):
        """Load task executor configuration from environment variables"""
        # Max concurrent task executions (default: 3)
        self.executor_max_workers = int(os.environ.get("NIGHTSHIFT_MAX_WORKERS", "3"))

        # Polling interval in seconds (default: 1.0)
        self.executor_poll_interval = float(os.environ.get("NIGHTSHIFT_POLL_INTERVAL", "1.0"))

        # Auto-start executor with CLI/Slack server (default: true)
        auto_executor = os.environ.get("NIGHTSHIFT_AUTO_EXECUTOR", "true").lower()
        self.executor_auto_start = auto_executor in ("true", "1", "yes")

    def get_executor_config(self) -> dict:
        """Get current executor configuration"""
        return {
            "max_workers": self.executor_max_workers,
            "poll_interval": self.executor_poll_interval,
            "auto_start": self.executor_auto_start
        }
