"""
Tests for Config - configuration management
"""
import pytest
import json
import os
from pathlib import Path
from unittest.mock import patch

from nightshift.core.config import Config


class TestDirectoryCreation:
    """Tests for automatic directory creation"""

    def test_default_base_dir_is_home_nightshift(self, tmp_path, monkeypatch):
        """Config uses ~/.nightshift as default when no base_dir provided"""
        # Monkeypatch Path.home() to use tmp_path
        monkeypatch.setattr(Path, "home", lambda: tmp_path)

        config = Config()

        assert config.base_dir == tmp_path / ".nightshift"
        assert config.base_dir.exists()

    def test_creates_base_dir(self, tmp_path):
        """Config creates base directory if it doesn't exist"""
        base_dir = tmp_path / "nightshift"
        assert not base_dir.exists()

        Config(base_dir=str(base_dir))

        assert base_dir.exists()

    def test_creates_subdirectories(self, tmp_path):
        """Config creates all required subdirectories"""
        base_dir = tmp_path / "nightshift"
        config = Config(base_dir=str(base_dir))

        assert config.database_dir.exists()
        assert config.logs_dir.exists()
        assert config.output_dir.exists()
        assert config.notifications_dir.exists()
        assert config.slack_metadata_dir.exists()

    def test_existing_dirs_not_recreated(self, tmp_path):
        """Config doesn't fail on existing directories"""
        base_dir = tmp_path / "nightshift"
        base_dir.mkdir()
        (base_dir / "database").mkdir()

        # Should not raise
        config = Config(base_dir=str(base_dir))
        assert config.database_dir.exists()


class TestPathGetters:
    """Tests for path getter methods"""

    def test_get_log_dir(self, tmp_path):
        """get_log_dir returns logs directory"""
        config = Config(base_dir=str(tmp_path))

        log_dir = config.get_log_dir()

        assert log_dir == config.logs_dir
        assert "logs" in str(log_dir)

    def test_get_database_path(self, tmp_path):
        """get_database_path returns db file path"""
        config = Config(base_dir=str(tmp_path))

        db_path = config.get_database_path()

        assert "nightshift.db" in str(db_path)
        assert "database" in str(db_path)

    def test_get_output_dir(self, tmp_path):
        """get_output_dir returns output directory"""
        config = Config(base_dir=str(tmp_path))

        output_dir = config.get_output_dir()

        assert output_dir == config.output_dir
        assert "output" in str(output_dir)

    def test_get_notifications_dir(self, tmp_path):
        """get_notifications_dir returns notifications directory"""
        config = Config(base_dir=str(tmp_path))

        notifications_dir = config.get_notifications_dir()

        assert "notifications" in str(notifications_dir)

    def test_get_slack_metadata_dir(self, tmp_path):
        """get_slack_metadata_dir returns slack_metadata directory"""
        config = Config(base_dir=str(tmp_path))

        slack_dir = config.get_slack_metadata_dir()

        assert "slack_metadata" in str(slack_dir)


class TestSlackConfig:
    """Tests for Slack configuration loading and persistence"""

    def test_slack_disabled_by_default(self, tmp_path):
        """Slack is disabled when no credentials provided"""
        config = Config(base_dir=str(tmp_path))

        assert config.slack_enabled is False
        assert config.slack_bot_token is None

    def test_slack_enabled_from_env(self, tmp_path):
        """Slack enabled when environment variables set"""
        with patch.dict(os.environ, {
            "NIGHTSHIFT_SLACK_BOT_TOKEN": "xoxb-test-token",
            "NIGHTSHIFT_SLACK_SIGNING_SECRET": "secret123"
        }):
            config = Config(base_dir=str(tmp_path))

            assert config.slack_enabled is True
            assert config.slack_bot_token == "xoxb-test-token"
            assert config.slack_signing_secret == "secret123"

    def test_slack_config_from_file(self, tmp_path):
        """Slack config loaded from JSON file"""
        base_dir = tmp_path / "nightshift"
        base_dir.mkdir()

        # Create config file before Config init
        config_file = base_dir / "slack_config.json"
        config_file.write_text(json.dumps({
            "bot_token": "xoxb-file-token",
            "signing_secret": "file-secret",
            "webhook_port": 8080
        }))

        config = Config(base_dir=str(base_dir))

        assert config.slack_enabled is True
        assert config.slack_bot_token == "xoxb-file-token"
        assert config.slack_webhook_port == 8080

    def test_slack_config_file_overrides_env(self, tmp_path):
        """Config file values override environment variables"""
        base_dir = tmp_path / "nightshift"
        base_dir.mkdir()

        config_file = base_dir / "slack_config.json"
        config_file.write_text(json.dumps({
            "bot_token": "xoxb-file-token",
            "signing_secret": "file-secret"
        }))

        with patch.dict(os.environ, {
            "NIGHTSHIFT_SLACK_BOT_TOKEN": "xoxb-env-token",
            "NIGHTSHIFT_SLACK_SIGNING_SECRET": "env-secret"
        }):
            config = Config(base_dir=str(base_dir))

            # File should override env
            assert config.slack_bot_token == "xoxb-file-token"

    def test_set_slack_config_persists(self, tmp_path):
        """set_slack_config writes to file and updates instance"""
        config = Config(base_dir=str(tmp_path))

        config.set_slack_config(
            bot_token="xoxb-new-token",
            signing_secret="new-secret",
            webhook_port=9000
        )

        # Check instance updated
        assert config.slack_enabled is True
        assert config.slack_bot_token == "xoxb-new-token"
        assert config.slack_webhook_port == 9000

        # Check file written
        assert config.slack_config_path.exists()
        with open(config.slack_config_path) as f:
            data = json.load(f)
        assert data["bot_token"] == "xoxb-new-token"

    def test_get_slack_config_masks_tokens(self, tmp_path):
        """get_slack_config returns masked token values"""
        config = Config(base_dir=str(tmp_path))
        config.set_slack_config(
            bot_token="xoxb-1234567890-abcdefghij",
            signing_secret="secret-key-12345678"
        )

        result = config.get_slack_config()

        assert result["enabled"] is True
        # Tokens should be masked (first 8 + ... + last 4)
        assert "..." in result["bot_token"]
        assert "xoxb-123" in result["bot_token"]
        assert len(result["bot_token"]) < len("xoxb-1234567890-abcdefghij")

    def test_slack_defaults(self, tmp_path):
        """Slack config has correct defaults"""
        config = Config(base_dir=str(tmp_path))

        assert config.slack_webhook_port == 5000
        assert config.slack_webhook_host == "0.0.0.0"
        assert config.slack_enable_threads is True
        assert config.slack_default_channel is None

    def test_invalid_json_config_file_is_ignored(self, tmp_path):
        """Invalid JSON config file is gracefully ignored"""
        base_dir = tmp_path / "nightshift"
        base_dir.mkdir()

        # Create invalid JSON config file
        config_file = base_dir / "slack_config.json"
        config_file.write_text("{invalid json content")

        # Should not raise, should fall back to defaults
        config = Config(base_dir=str(base_dir))

        # Slack should be disabled (defaults used)
        assert config.slack_enabled is False
        assert config.slack_webhook_port == 5000


class TestExecutorConfig:
    """Tests for executor configuration"""

    def test_executor_defaults(self, tmp_path):
        """Executor config has correct defaults"""
        config = Config(base_dir=str(tmp_path))

        assert config.executor_max_workers == 3
        assert config.executor_poll_interval == 1.0
        assert config.executor_auto_start is True

    def test_executor_from_env(self, tmp_path):
        """Executor config loaded from environment"""
        with patch.dict(os.environ, {
            "NIGHTSHIFT_MAX_WORKERS": "5",
            "NIGHTSHIFT_POLL_INTERVAL": "2.5",
            "NIGHTSHIFT_AUTO_EXECUTOR": "false"
        }):
            config = Config(base_dir=str(tmp_path))

            assert config.executor_max_workers == 5
            assert config.executor_poll_interval == 2.5
            assert config.executor_auto_start is False

    def test_get_executor_config(self, tmp_path):
        """get_executor_config returns dict with all settings"""
        config = Config(base_dir=str(tmp_path))

        result = config.get_executor_config()

        assert "max_workers" in result
        assert "poll_interval" in result
        assert "auto_start" in result


class TestMaskToken:
    """Tests for token masking helper"""

    def test_mask_normal_token(self):
        """Masks normal length token"""
        result = Config._mask_token("xoxb-1234567890-abcdefghij")
        assert result == "xoxb-123...ghij"

    def test_mask_short_token(self):
        """Short tokens become ***"""
        result = Config._mask_token("short")
        assert result == "***"

    def test_mask_none_token(self):
        """None/empty tokens become ***"""
        result = Config._mask_token("")
        assert result == "***"

        result = Config._mask_token(None)
        assert result == "***"
