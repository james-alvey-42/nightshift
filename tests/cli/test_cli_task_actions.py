"""
Tests for CLI task action commands: cancel, pause, resume, kill
"""
import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from nightshift.interfaces.cli import cli
from nightshift.core.task_queue import TaskStatus


@pytest.fixture
def runner():
    return CliRunner()


class TestCancelCommand:
    """Tests for the cancel command"""

    def test_cancel_task_not_found(self, runner, mock_ctx):
        """cancel shows error for nonexistent task"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["cancel", "nonexistent"])

                            assert "not found" in result.output
                            assert result.exit_code == 1

    def test_cancel_staged_task(self, runner, mock_ctx):
        """cancel works for staged tasks"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["cancel", "task_001"])

                            assert "cancelled" in result.output.lower()
                            task = mock_ctx["task_queue"].get_task("task_001")
                            assert task.status == TaskStatus.CANCELLED.value

    def test_cancel_committed_task(self, runner, mock_ctx):
        """cancel works for committed tasks"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")
        mock_ctx["task_queue"].update_status("task_001", TaskStatus.COMMITTED)

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["cancel", "task_001"])

                            assert "cancelled" in result.output.lower()

    def test_cancel_running_task_fails(self, runner, mock_ctx):
        """cancel fails for running tasks"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")
        mock_ctx["task_queue"].update_status("task_001", TaskStatus.COMMITTED)
        mock_ctx["task_queue"].update_status("task_001", TaskStatus.RUNNING)

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["cancel", "task_001"])

                            assert "Cannot cancel" in result.output
                            assert result.exit_code == 1


class TestPauseCommand:
    """Tests for the pause command"""

    def test_pause_success(self, runner, mock_ctx):
        """pause calls agent_manager.pause_task"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["pause", "task_001"])

                            mock_ctx["agent_manager"].pause_task.assert_called_once_with("task_001")
                            assert "paused" in result.output.lower()

    def test_pause_failure(self, runner, mock_ctx):
        """pause shows error on failure"""
        mock_ctx["agent_manager"].pause_task.return_value = {
            "success": False,
            "error": "Task not running"
        }

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["pause", "task_001"])

                            assert "Error" in result.output
                            assert result.exit_code == 1


class TestResumeCommand:
    """Tests for the resume command"""

    def test_resume_success(self, runner, mock_ctx):
        """resume calls agent_manager.resume_task"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["resume", "task_001"])

                            mock_ctx["agent_manager"].resume_task.assert_called_once_with("task_001")
                            assert "resumed" in result.output.lower()

    def test_resume_failure(self, runner, mock_ctx):
        """resume shows error on failure"""
        mock_ctx["agent_manager"].resume_task.return_value = {
            "success": False,
            "error": "Task not paused"
        }

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["resume", "task_001"])

                            assert "Error" in result.output
                            assert result.exit_code == 1


class TestKillCommand:
    """Tests for the kill command"""

    def test_kill_success(self, runner, mock_ctx):
        """kill calls agent_manager.kill_task"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["kill", "task_001"])

                            mock_ctx["agent_manager"].kill_task.assert_called_once_with("task_001")
                            assert "killed" in result.output.lower()

    def test_kill_failure(self, runner, mock_ctx):
        """kill shows error on failure"""
        mock_ctx["agent_manager"].kill_task.return_value = {
            "success": False,
            "error": "Task not running"
        }

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["kill", "task_001"])

                            assert "Error" in result.output
                            assert result.exit_code == 1
