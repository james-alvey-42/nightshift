"""
Tests for SlackEventHandler
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from flask import Flask

from nightshift.integrations.slack_handler import SlackEventHandler
from nightshift.core.task_queue import TaskStatus


@pytest.fixture
def app():
    """Create a Flask app for testing"""
    app = Flask(__name__)
    app.config['TESTING'] = True
    return app


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for SlackEventHandler"""
    slack_client = Mock()
    slack_client.post_message.return_value = Mock(ok=True, ts="1234.5678")
    slack_client.update_message.return_value = Mock(ok=True)
    slack_client.post_ephemeral.return_value = Mock(ok=True)

    task_queue = Mock()

    task_planner = Mock()
    task_planner.plan_task.return_value = {
        "enhanced_prompt": "Enhanced task description",
        "allowed_tools": ["Read", "Write"],
        "allowed_directories": ["/tmp"],
        "needs_git": False,
        "system_prompt": "Test system prompt"
    }

    agent_manager = Mock()
    agent_manager.execute_task.return_value = {"success": True}

    slack_metadata = Mock()
    logger = Mock()

    return {
        "slack_client": slack_client,
        "task_queue": task_queue,
        "task_planner": task_planner,
        "agent_manager": agent_manager,
        "slack_metadata": slack_metadata,
        "logger": logger
    }


@pytest.fixture
def handler(mock_dependencies):
    """Create SlackEventHandler with mocked dependencies"""
    return SlackEventHandler(
        slack_client=mock_dependencies["slack_client"],
        task_queue=mock_dependencies["task_queue"],
        task_planner=mock_dependencies["task_planner"],
        agent_manager=mock_dependencies["agent_manager"],
        slack_metadata=mock_dependencies["slack_metadata"],
        logger=mock_dependencies["logger"]
    )


class TestHandleSubmit:
    """Tests for handle_submit method"""

    def test_empty_text_returns_error(self, handler, app):
        """handle_submit returns error for empty text"""
        with app.app_context():
            response = handler.handle_submit(
                text="",
                user_id="U123",
                channel_id="C456",
                response_url="https://hooks.slack.com/xxx"
            )

        # Response is a Flask Response object
        data = json.loads(response.get_data(as_text=True))
        assert data["response_type"] == "ephemeral"
        assert "provide a task description" in data["text"].lower()

    def test_submit_returns_acknowledgment(self, handler, app):
        """handle_submit returns immediate acknowledgment"""
        with app.app_context():
            with patch("threading.Thread"):  # Don't start actual thread
                response = handler.handle_submit(
                    text="Test task",
                    user_id="U123",
                    channel_id="C456",
                    response_url="https://hooks.slack.com/xxx"
                )

        data = json.loads(response.get_data(as_text=True))
        assert "Planning task" in data["text"]

    def test_submit_starts_background_thread(self, handler, app):
        """handle_submit starts async planning thread"""
        with app.app_context():
            with patch("threading.Thread") as mock_thread:
                handler.handle_submit(
                    text="Test task",
                    user_id="U123",
                    channel_id="C456",
                    response_url="https://hooks.slack.com/xxx"
                )

                mock_thread.assert_called_once()
                # Verify daemon=True
                assert mock_thread.call_args[1]["daemon"] is True


class TestPlanAndStageTask:
    """Tests for _plan_and_stage_task method"""

    def test_plan_and_stage_creates_task(self, handler, mock_dependencies):
        """_plan_and_stage_task creates task in queue"""
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_task.allowed_tools = ["Read"]
        mock_task.timeout_seconds = 900
        mock_dependencies["task_queue"].create_task.return_value = mock_task

        handler._plan_and_stage_task(
            description="Test description",
            user_id="U123",
            channel_id="C456",
            response_url="https://hooks.slack.com/xxx"
        )

        mock_dependencies["task_planner"].plan_task.assert_called_once_with("Test description")
        mock_dependencies["task_queue"].create_task.assert_called_once()

    def test_plan_and_stage_stores_metadata(self, handler, mock_dependencies):
        """_plan_and_stage_task stores Slack metadata"""
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_task.allowed_tools = []
        mock_task.timeout_seconds = 900
        mock_dependencies["task_queue"].create_task.return_value = mock_task

        handler._plan_and_stage_task(
            description="Test",
            user_id="U123",
            channel_id="C456",
            response_url="https://hooks.slack.com/xxx"
        )

        mock_dependencies["slack_metadata"].store.assert_called_once()
        call_kwargs = mock_dependencies["slack_metadata"].store.call_args[1]
        assert call_kwargs["user_id"] == "U123"
        assert call_kwargs["channel_id"] == "C456"

    def test_plan_and_stage_sends_approval_message(self, handler, mock_dependencies):
        """_plan_and_stage_task posts approval message to Slack"""
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_task.allowed_tools = []
        mock_task.timeout_seconds = 900
        mock_dependencies["task_queue"].create_task.return_value = mock_task

        handler._plan_and_stage_task(
            description="Test",
            user_id="U123",
            channel_id="C456",
            response_url="https://hooks.slack.com/xxx"
        )

        mock_dependencies["slack_client"].post_message.assert_called_once()

    def test_plan_and_stage_handles_dm_channel(self, handler, mock_dependencies):
        """_plan_and_stage_task uses user_id for DM channels"""
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_task.allowed_tools = []
        mock_task.timeout_seconds = 900
        mock_dependencies["task_queue"].create_task.return_value = mock_task

        handler._plan_and_stage_task(
            description="Test",
            user_id="U123",
            channel_id="D456",  # DM channel starts with D
            response_url="https://hooks.slack.com/xxx"
        )

        call_kwargs = mock_dependencies["slack_client"].post_message.call_args[1]
        assert call_kwargs["channel"] == "U123"  # Uses user_id for DMs

    def test_plan_and_stage_handles_planner_error(self, handler, mock_dependencies):
        """_plan_and_stage_task handles planner exceptions"""
        mock_dependencies["task_planner"].plan_task.side_effect = Exception("Planning failed")

        # Should not raise
        handler._plan_and_stage_task(
            description="Test",
            user_id="U123",
            channel_id="C456",
            response_url="https://hooks.slack.com/xxx"
        )

        # Should post error message
        mock_dependencies["slack_client"].post_message.assert_called()
        call_kwargs = mock_dependencies["slack_client"].post_message.call_args[1]
        assert "failed" in call_kwargs["text"].lower()


class TestHandleApproval:
    """Tests for handle_approval method"""

    def test_approve_updates_status(self, handler, mock_dependencies, app):
        """handle_approval with approve action updates task to COMMITTED"""
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_dependencies["task_queue"].get_task.return_value = mock_task

        with app.app_context():
            handler.handle_approval(
                task_id="task_001",
                user_id="U123",
                channel_id="C456",
                message_ts="1234.5678",
                action="approve"
            )

        mock_dependencies["task_queue"].update_status.assert_called_once_with(
            "task_001", TaskStatus.COMMITTED
        )

    def test_reject_cancels_task(self, handler, mock_dependencies, app):
        """handle_approval with reject action cancels task"""
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_dependencies["task_queue"].get_task.return_value = mock_task

        with app.app_context():
            handler.handle_approval(
                task_id="task_001",
                user_id="U123",
                channel_id="C456",
                message_ts="1234.5678",
                action="reject"
            )

        mock_dependencies["task_queue"].update_status.assert_called_once_with(
            "task_001", TaskStatus.CANCELLED
        )

    def test_approve_updates_slack_message(self, handler, mock_dependencies, app):
        """handle_approval updates original Slack message"""
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_dependencies["task_queue"].get_task.return_value = mock_task

        with app.app_context():
            handler.handle_approval(
                task_id="task_001",
                user_id="U123",
                channel_id="C456",
                message_ts="1234.5678",
                action="approve"
            )

        mock_dependencies["slack_client"].update_message.assert_called_once()

    def test_approve_task_not_found(self, handler, mock_dependencies, app):
        """handle_approval returns error for nonexistent task"""
        mock_dependencies["task_queue"].get_task.return_value = None

        with app.app_context():
            response = handler.handle_approval(
                task_id="nonexistent",
                user_id="U123",
                channel_id="C456",
                message_ts="1234.5678",
                action="approve"
            )

        data = json.loads(response.get_data(as_text=True))
        assert "not found" in data["text"]


class TestHandleDetails:
    """Tests for handle_details method"""

    def test_details_sends_ephemeral(self, handler, mock_dependencies, app):
        """handle_details sends ephemeral message to user"""
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_task.description = "Test description"
        mock_task.status = "STAGED"
        mock_task.allowed_tools = ["Read", "Write"]
        mock_task.allowed_directories = ["/tmp"]
        mock_task.timeout_seconds = 900
        mock_task.needs_git = False
        mock_task.system_prompt = "System prompt"
        mock_dependencies["task_queue"].get_task.return_value = mock_task

        with app.app_context():
            handler.handle_details(
                task_id="task_001",
                user_id="U123",
                channel_id="C456"
            )

        mock_dependencies["slack_client"].post_ephemeral.assert_called_once()
        call_kwargs = mock_dependencies["slack_client"].post_ephemeral.call_args[1]
        assert call_kwargs["user"] == "U123"

    def test_details_task_not_found(self, handler, mock_dependencies, app):
        """handle_details returns error for nonexistent task"""
        mock_dependencies["task_queue"].get_task.return_value = None

        with app.app_context():
            response = handler.handle_details(
                task_id="nonexistent",
                user_id="U123",
                channel_id="C456"
            )

        data = json.loads(response.get_data(as_text=True))
        assert "not found" in data["text"]


class TestHandleQueue:
    """Tests for handle_queue method"""

    def test_queue_lists_all_tasks(self, handler, mock_dependencies, app):
        """handle_queue lists all tasks"""
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_task.status = "STAGED"
        mock_task.description = "Test"
        mock_dependencies["task_queue"].list_tasks.return_value = [mock_task]

        with app.app_context():
            response = handler.handle_queue(
                args="",
                user_id="U123",
                channel_id="C456"
            )

        mock_dependencies["task_queue"].list_tasks.assert_called_once()
        data = json.loads(response.get_data(as_text=True))
        assert "blocks" in data

    def test_queue_filters_by_status(self, handler, mock_dependencies, app):
        """handle_queue filters by status argument"""
        mock_dependencies["task_queue"].list_tasks.return_value = []

        with app.app_context():
            handler.handle_queue(
                args="STAGED",
                user_id="U123",
                channel_id="C456"
            )

        mock_dependencies["task_queue"].list_tasks.assert_called_once_with(status="STAGED")


class TestHandleStatus:
    """Tests for handle_status method"""

    def test_status_missing_task_id(self, handler, mock_dependencies, app):
        """handle_status returns usage for empty args"""
        with app.app_context():
            response = handler.handle_status(
                args="",
                user_id="U123",
                channel_id="C456"
            )

        data = json.loads(response.get_data(as_text=True))
        assert "Usage" in data["text"]

    def test_status_returns_task_info(self, handler, mock_dependencies, app):
        """handle_status returns task information"""
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_task.status = "RUNNING"
        mock_task.description = "Test task"
        mock_task.created_at = "2024-01-01"
        mock_task.result_path = "/path/to/result"
        mock_dependencies["task_queue"].get_task.return_value = mock_task

        with app.app_context():
            response = handler.handle_status(
                args="task_001",
                user_id="U123",
                channel_id="C456"
            )

        data = json.loads(response.get_data(as_text=True))
        assert "task_001" in data["text"]
        assert "RUNNING" in data["text"]


class TestHandleCancel:
    """Tests for handle_cancel method"""

    def test_cancel_updates_status(self, handler, mock_dependencies, app):
        """handle_cancel updates task to CANCELLED"""
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_task.status = "STAGED"
        mock_dependencies["task_queue"].get_task.return_value = mock_task

        with app.app_context():
            handler.handle_cancel(
                args="task_001",
                user_id="U123",
                channel_id="C456"
            )

        mock_dependencies["task_queue"].update_status.assert_called_once_with(
            "task_001", TaskStatus.CANCELLED
        )

    def test_cancel_running_task_fails(self, handler, mock_dependencies, app):
        """handle_cancel fails for running tasks"""
        mock_task = Mock()
        mock_task.task_id = "task_001"
        mock_task.status = "RUNNING"
        mock_dependencies["task_queue"].get_task.return_value = mock_task

        with app.app_context():
            response = handler.handle_cancel(
                args="task_001",
                user_id="U123",
                channel_id="C456"
            )

        data = json.loads(response.get_data(as_text=True))
        assert "Cannot cancel" in data["text"]


class TestHandlePauseResumeKill:
    """Tests for pause, resume, and kill handlers"""

    def test_pause_calls_agent_manager(self, handler, mock_dependencies, app):
        """handle_pause calls agent_manager.pause_task"""
        with app.app_context():
            handler.handle_pause(
                args="task_001",
                user_id="U123",
                channel_id="C456"
            )

        mock_dependencies["agent_manager"].pause_task.assert_called_once_with("task_001")

    def test_resume_calls_agent_manager(self, handler, mock_dependencies, app):
        """handle_resume calls agent_manager.resume_task"""
        with app.app_context():
            handler.handle_resume(
                args="task_001",
                user_id="U123",
                channel_id="C456"
            )

        mock_dependencies["agent_manager"].resume_task.assert_called_once_with("task_001")

    def test_kill_calls_agent_manager(self, handler, mock_dependencies, app):
        """handle_kill calls agent_manager.kill_task"""
        with app.app_context():
            handler.handle_kill(
                args="task_001",
                user_id="U123",
                channel_id="C456"
            )

        mock_dependencies["agent_manager"].kill_task.assert_called_once_with("task_001")

    def test_pause_missing_task_id(self, handler, mock_dependencies, app):
        """handle_pause returns usage for empty args"""
        with app.app_context():
            response = handler.handle_pause(
                args="",
                user_id="U123",
                channel_id="C456"
            )

        data = json.loads(response.get_data(as_text=True))
        assert "Usage" in data["text"]
