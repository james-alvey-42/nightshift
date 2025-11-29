"""
Tests for CLI executor commands
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from click.testing import CliRunner

from nightshift.interfaces.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestExecutorStatus:
    """Tests for executor status command"""

    def test_executor_status_not_running(self, runner, mock_ctx):
        """executor status shows not running"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            with patch("nightshift.interfaces.cli.ExecutorManager") as mock_exec:
                                mock_exec.get_status.return_value = {
                                    "is_running": False,
                                    "max_workers": 0,
                                    "running_tasks": 0,
                                    "available_workers": 0,
                                    "poll_interval": 0
                                }

                                result = runner.invoke(cli, ["executor", "status"])

                                assert "Stopped" in result.output

    def test_executor_status_running(self, runner, mock_ctx):
        """executor status shows running state"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            with patch("nightshift.interfaces.cli.ExecutorManager") as mock_exec:
                                mock_exec.get_status.return_value = {
                                    "is_running": True,
                                    "max_workers": 3,
                                    "running_tasks": 1,
                                    "available_workers": 2,
                                    "poll_interval": 1.0
                                }

                                result = runner.invoke(cli, ["executor", "status"])

                                assert "Running" in result.output
                                assert "3" in result.output  # max_workers


class TestExecutorStop:
    """Tests for executor stop command"""

    def test_executor_stop(self, runner, mock_ctx):
        """executor stop calls ExecutorManager.stop_executor"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            with patch("nightshift.interfaces.cli.ExecutorManager") as mock_exec:
                                result = runner.invoke(cli, ["executor", "stop"])

                                mock_exec.stop_executor.assert_called_once()
                                assert "stopped" in result.output.lower()

    def test_executor_stop_with_timeout(self, runner, mock_ctx):
        """executor stop --timeout passes timeout"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            with patch("nightshift.interfaces.cli.ExecutorManager") as mock_exec:
                                result = runner.invoke(cli, ["executor", "stop", "--timeout", "60"])

                                mock_exec.stop_executor.assert_called_once_with(timeout=60.0)


class TestClearCommand:
    """Tests for clear command"""

    def test_clear_without_confirm(self, runner, mock_ctx):
        """clear prompts for confirmation"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            # Simulate user saying 'no'
                            result = runner.invoke(cli, ["clear"], input="n\n")

                            assert "Cancelled" in result.output

    def test_clear_with_confirm(self, runner, mock_ctx):
        """clear --confirm skips prompt"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            with patch("shutil.rmtree") as mock_rmtree:
                                result = runner.invoke(cli, ["clear", "--confirm"])

                                # Should clear data
                                assert "Cleared" in result.output or "Nothing to clear" in result.output


class TestExecutorFailurePaths:
    """Tests for executor command failure scenarios"""

    def test_executor_stop_failure(self, runner, mock_ctx):
        """executor stop handles failure gracefully"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            with patch("nightshift.interfaces.cli.ExecutorManager") as mock_exec:
                                mock_exec.stop_executor.side_effect = Exception("Failed to stop: no executor running")

                                result = runner.invoke(cli, ["executor", "stop"])

                                # Should show error message
                                assert "Error" in result.output or "Failed" in result.output
                                # Click's abort returns exit code 1
                                assert result.exit_code != 0

    def test_executor_status_failure(self, runner, mock_ctx):
        """executor status handles failure gracefully"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            with patch("nightshift.interfaces.cli.ExecutorManager") as mock_exec:
                                mock_exec.get_status.side_effect = Exception("Status check failed")

                                result = runner.invoke(cli, ["executor", "status"])

                                # Should handle exception gracefully
                                # Either show error or have non-zero exit
                                assert "Status check failed" in result.output or result.exit_code != 0 or result.exception is not None
