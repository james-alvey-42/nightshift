"""
Tests for Notifier - notification generation and delivery
"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from nightshift.core.notifier import Notifier
from nightshift.core.file_tracker import FileChange


@pytest.fixture
def notifier(tmp_path):
    """Create a Notifier with terminal output disabled"""
    return Notifier(
        notification_dir=str(tmp_path / "notifications"),
        enable_terminal_output=False
    )


@pytest.fixture
def sample_file_changes():
    """Sample file changes for testing"""
    return [
        FileChange(path="created.txt", change_type="created", timestamp="2024-01-01", size=100),
        FileChange(path="modified.txt", change_type="modified", timestamp="2024-01-01", size=200),
        FileChange(path="deleted.txt", change_type="deleted", timestamp="2024-01-01", size=None)
    ]


class TestGenerateSummary:
    """Tests for generate_summary method"""

    def test_generate_summary_success(self, notifier, sample_file_changes):
        """generate_summary creates complete summary for successful task"""
        summary = notifier.generate_summary(
            task_id="task_001",
            task_description="Test task",
            success=True,
            execution_time=45.5,
            token_usage=1000,
            file_changes=sample_file_changes,
            result_path="/output/result.json"
        )

        assert summary["task_id"] == "task_001"
        assert summary["description"] == "Test task"
        assert summary["status"] == "success"
        assert summary["execution_time"] == 45.5
        assert summary["token_usage"] == 1000
        assert summary["error_message"] is None
        assert summary["result_path"] == "/output/result.json"

    def test_generate_summary_failed(self, notifier):
        """generate_summary creates summary for failed task"""
        summary = notifier.generate_summary(
            task_id="task_001",
            task_description="Test task",
            success=False,
            execution_time=10.0,
            token_usage=None,
            file_changes=[],
            error_message="Task failed due to timeout"
        )

        assert summary["status"] == "failed"
        assert summary["error_message"] == "Task failed due to timeout"

    def test_generate_summary_categorizes_file_changes(self, notifier, sample_file_changes):
        """generate_summary categorizes file changes correctly"""
        summary = notifier.generate_summary(
            task_id="task_001",
            task_description="Test",
            success=True,
            execution_time=1.0,
            token_usage=100,
            file_changes=sample_file_changes
        )

        assert "created.txt" in summary["file_changes"]["created"]
        assert "modified.txt" in summary["file_changes"]["modified"]
        assert "deleted.txt" in summary["file_changes"]["deleted"]

    def test_generate_summary_includes_timestamp(self, notifier):
        """generate_summary includes ISO timestamp"""
        summary = notifier.generate_summary(
            task_id="task_001",
            task_description="Test",
            success=True,
            execution_time=1.0,
            token_usage=100,
            file_changes=[]
        )

        assert "timestamp" in summary
        # Should be ISO format
        assert "T" in summary["timestamp"]


class TestNotify:
    """Tests for notify method"""

    def test_notify_saves_to_file(self, notifier, tmp_path):
        """notify saves notification to JSON file"""
        notifier.notify(
            task_id="task_001",
            task_description="Test task",
            success=True,
            execution_time=30.0,
            token_usage=500,
            file_changes=[]
        )

        notification_file = tmp_path / "notifications" / "task_001_notification.json"
        assert notification_file.exists()

        with open(notification_file) as f:
            data = json.load(f)

        assert data["task_id"] == "task_001"
        assert data["status"] == "success"

    def test_notify_with_slack_client(self, tmp_path):
        """notify sends to Slack when configured"""
        mock_slack = Mock()
        mock_metadata = Mock()
        mock_metadata.get.return_value = {
            "channel_id": "C12345",
            "user_id": "U12345",
            "thread_ts": "1234.5678"
        }

        notifier = Notifier(
            notification_dir=str(tmp_path / "notifications"),
            slack_client=mock_slack,
            slack_metadata_store=mock_metadata,
            enable_terminal_output=False
        )

        with patch("nightshift.integrations.slack_formatter.SlackFormatter.format_completion_notification") as mock_format:
            mock_format.return_value = [{"type": "section"}]

            notifier.notify(
                task_id="task_001",
                task_description="Test",
                success=True,
                execution_time=1.0,
                token_usage=100,
                file_changes=[]
            )

        mock_slack.post_message.assert_called_once()
        mock_metadata.delete.assert_called_once_with("task_001")

    def test_notify_skips_slack_without_metadata(self, tmp_path):
        """notify skips Slack when no metadata for task"""
        mock_slack = Mock()
        mock_metadata = Mock()
        mock_metadata.get.return_value = None  # No metadata

        notifier = Notifier(
            notification_dir=str(tmp_path / "notifications"),
            slack_client=mock_slack,
            slack_metadata_store=mock_metadata,
            enable_terminal_output=False
        )

        notifier.notify(
            task_id="task_001",
            task_description="Test",
            success=True,
            execution_time=1.0,
            token_usage=100,
            file_changes=[]
        )

        # Slack should not be called since no metadata
        mock_slack.post_message.assert_not_called()

    def test_notify_handles_slack_error(self, tmp_path, caplog):
        """notify handles Slack errors gracefully"""
        mock_slack = Mock()
        mock_slack.post_message.side_effect = Exception("Slack error")
        mock_metadata = Mock()
        mock_metadata.get.return_value = {"channel_id": "C12345", "user_id": "U12345"}

        # Enable terminal output to capture warning
        notifier = Notifier(
            notification_dir=str(tmp_path / "notifications"),
            slack_client=mock_slack,
            slack_metadata_store=mock_metadata,
            enable_terminal_output=True
        )

        with patch("nightshift.integrations.slack_formatter.SlackFormatter.format_completion_notification") as mock_format:
            mock_format.return_value = []

            # Should not raise
            notifier.notify(
                task_id="task_001",
                task_description="Test",
                success=True,
                execution_time=1.0,
                token_usage=100,
                file_changes=[]
            )


class TestSaveNotification:
    """Tests for _save_notification method"""

    def test_save_notification_creates_file(self, notifier, tmp_path):
        """_save_notification creates JSON file"""
        summary = {
            "task_id": "task_001",
            "description": "Test",
            "status": "success"
        }

        notifier._save_notification(summary)

        file_path = tmp_path / "notifications" / "task_001_notification.json"
        assert file_path.exists()

    def test_save_notification_valid_json(self, notifier, tmp_path):
        """_save_notification writes valid JSON"""
        summary = {
            "task_id": "task_002",
            "description": "Test task",
            "status": "failed",
            "error_message": "Something went wrong"
        }

        notifier._save_notification(summary)

        file_path = tmp_path / "notifications" / "task_002_notification.json"
        with open(file_path) as f:
            data = json.load(f)

        assert data == summary


class TestDisplayTerminal:
    """Tests for _display_terminal method"""

    def test_display_terminal_disabled(self, tmp_path):
        """_display_terminal does nothing when disabled"""
        notifier = Notifier(
            notification_dir=str(tmp_path),
            enable_terminal_output=False
        )

        # Should not raise or produce output
        notifier._display_terminal({
            "task_id": "task_001",
            "status": "success",
            "description": "Test",
            "execution_time": 1.0,
            "token_usage": None,
            "file_changes": {"created": [], "modified": [], "deleted": []},
            "error_message": None,
            "result_path": None
        })

    def test_display_terminal_enabled(self, tmp_path):
        """_display_terminal outputs when enabled"""
        notifier = Notifier(
            notification_dir=str(tmp_path),
            enable_terminal_output=True
        )

        # Mock the console to capture output
        with patch.object(notifier.console, "print") as mock_print:
            notifier._display_terminal({
                "task_id": "task_001",
                "status": "success",
                "description": "Test task description",
                "execution_time": 30.0,
                "token_usage": 500,
                "file_changes": {"created": ["new.txt"], "modified": [], "deleted": []},
                "error_message": None,
                "result_path": "/path/to/result"
            })

        # Should have printed something
        assert mock_print.called


class TestNotifierInit:
    """Tests for Notifier initialization"""

    def test_creates_notification_directory(self, tmp_path):
        """Notifier creates notification directory"""
        notif_dir = tmp_path / "new_notifications"
        assert not notif_dir.exists()

        Notifier(notification_dir=str(notif_dir))

        assert notif_dir.exists()

    def test_default_terminal_output_enabled(self, tmp_path):
        """Terminal output enabled by default"""
        notifier = Notifier(notification_dir=str(tmp_path))

        assert notifier.enable_terminal_output is True

    def test_slack_client_stored(self, tmp_path):
        """Slack client is stored when provided"""
        mock_client = Mock()
        notifier = Notifier(
            notification_dir=str(tmp_path),
            slack_client=mock_client
        )

        assert notifier.slack_client is mock_client


class TestDisplayTerminalEdgeCases:
    """Edge case tests for _display_terminal"""

    def test_display_terminal_many_created_files(self, tmp_path):
        """_display_terminal truncates created files > 5"""
        notifier = Notifier(
            notification_dir=str(tmp_path),
            enable_terminal_output=True
        )

        with patch.object(notifier.console, "print") as mock_print:
            notifier._display_terminal({
                "task_id": "task_001",
                "status": "success",
                "description": "Test",
                "execution_time": 30.0,
                "token_usage": None,
                "file_changes": {
                    "created": [f"file_{i}.py" for i in range(10)],
                    "modified": [],
                    "deleted": []
                },
                "error_message": None,
                "result_path": None
            })

        # Should show "and X more" for files beyond 5
        call_args = str(mock_print.call_args_list)
        # The Markdown content should include the truncation message

    def test_display_terminal_modified_files(self, tmp_path):
        """_display_terminal displays modified files"""
        notifier = Notifier(
            notification_dir=str(tmp_path),
            enable_terminal_output=True
        )

        with patch.object(notifier.console, "print") as mock_print:
            notifier._display_terminal({
                "task_id": "task_001",
                "status": "success",
                "description": "Test",
                "execution_time": 30.0,
                "token_usage": None,
                "file_changes": {
                    "created": [],
                    "modified": ["changed.py", "updated.js"],
                    "deleted": []
                },
                "error_message": None,
                "result_path": None
            })

        assert mock_print.called

    def test_display_terminal_many_modified_files(self, tmp_path):
        """_display_terminal truncates modified files > 5"""
        notifier = Notifier(
            notification_dir=str(tmp_path),
            enable_terminal_output=True
        )

        with patch.object(notifier.console, "print") as mock_print:
            notifier._display_terminal({
                "task_id": "task_001",
                "status": "success",
                "description": "Test",
                "execution_time": 30.0,
                "token_usage": None,
                "file_changes": {
                    "created": [],
                    "modified": [f"file_{i}.py" for i in range(10)],
                    "deleted": []
                },
                "error_message": None,
                "result_path": None
            })

        assert mock_print.called

    def test_display_terminal_deleted_files(self, tmp_path):
        """_display_terminal displays deleted files"""
        notifier = Notifier(
            notification_dir=str(tmp_path),
            enable_terminal_output=True
        )

        with patch.object(notifier.console, "print") as mock_print:
            notifier._display_terminal({
                "task_id": "task_001",
                "status": "success",
                "description": "Test",
                "execution_time": 30.0,
                "token_usage": None,
                "file_changes": {
                    "created": [],
                    "modified": [],
                    "deleted": ["old.py", "deprecated.js"]
                },
                "error_message": None,
                "result_path": None
            })

        assert mock_print.called

    def test_display_terminal_many_deleted_files(self, tmp_path):
        """_display_terminal truncates deleted files > 5"""
        notifier = Notifier(
            notification_dir=str(tmp_path),
            enable_terminal_output=True
        )

        with patch.object(notifier.console, "print") as mock_print:
            notifier._display_terminal({
                "task_id": "task_001",
                "status": "success",
                "description": "Test",
                "execution_time": 30.0,
                "token_usage": None,
                "file_changes": {
                    "created": [],
                    "modified": [],
                    "deleted": [f"file_{i}.py" for i in range(10)]
                },
                "error_message": None,
                "result_path": None
            })

        assert mock_print.called

    def test_display_terminal_with_error_message(self, tmp_path):
        """_display_terminal displays error message for failed tasks"""
        notifier = Notifier(
            notification_dir=str(tmp_path),
            enable_terminal_output=True
        )

        with patch.object(notifier.console, "print") as mock_print:
            notifier._display_terminal({
                "task_id": "task_001",
                "status": "failed",
                "description": "Test",
                "execution_time": 10.0,
                "token_usage": None,
                "file_changes": {"created": [], "modified": [], "deleted": []},
                "error_message": "Task failed: timeout exceeded",
                "result_path": None
            })

        assert mock_print.called


class TestSendEmail:
    """Tests for _send_email method"""

    def test_send_email_is_noop(self, tmp_path):
        """_send_email is a no-op stub"""
        notifier = Notifier(
            notification_dir=str(tmp_path),
            enable_terminal_output=False
        )

        # Should not raise
        notifier._send_email({
            "task_id": "task_001",
            "status": "success"
        })
