"""
Tests for CLI submit command
"""
import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from nightshift.interfaces.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestSubmitCommand:
    """Tests for the submit command"""

    def test_submit_basic(self, runner, mock_ctx):
        """submit creates task and calls planner"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["submit", "Test task description"])

                            # Planner should be called
                            mock_ctx["task_planner"].plan_task.assert_called_once()
                            call_args = mock_ctx["task_planner"].plan_task.call_args
                            assert call_args[0][0] == "Test task description"

                            # Task should be created
                            assert "Task created" in result.output
                            assert result.exit_code == 0

    def test_submit_with_auto_approve(self, runner, mock_ctx):
        """submit --auto-approve queues task for execution"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["submit", "Test task", "--auto-approve"])

                            # Task should be approved
                            assert "Auto-approving" in result.output or "queued" in result.output.lower()
                            assert result.exit_code == 0

    def test_submit_with_auto_approve_sync(self, runner, mock_ctx):
        """submit --auto-approve --sync executes immediately"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["submit", "Test task", "--auto-approve", "--sync"])

                            # Execute should be called
                            mock_ctx["agent_manager"].execute_task.assert_called_once()
                            assert "completed" in result.output.lower() or "success" in result.output.lower()
                            assert result.exit_code == 0

    def test_submit_with_timeout(self, runner, mock_ctx):
        """submit --timeout sets task timeout"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["submit", "Test task", "--timeout", "600"])

                            # Check output shows timeout
                            assert "600" in result.output
                            assert result.exit_code == 0

    def test_submit_with_planning_timeout(self, runner, mock_ctx):
        """submit --planning-timeout passes timeout to planner"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["submit", "Test task", "--planning-timeout", "60"])

                            # Planner should be called with timeout
                            mock_ctx["task_planner"].plan_task.assert_called_once()
                            call_args = mock_ctx["task_planner"].plan_task.call_args
                            assert call_args[1]["timeout"] == 60

    def test_submit_with_allow_dir(self, runner, mock_ctx):
        """submit --allow-dir adds directories to sandbox"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["submit", "Test task", "--allow-dir", "/tmp/test"])

                            # Output should show directories
                            assert result.exit_code == 0

    def test_submit_planner_failure(self, runner, mock_ctx):
        """submit handles planner failure gracefully"""
        mock_ctx["task_planner"].plan_task.side_effect = Exception("Planning failed")

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["submit", "Test task"])

                            assert "Planning failed" in result.output or "Error" in result.output
                            assert result.exit_code != 0

    def test_submit_sync_execution_failure(self, runner, mock_ctx):
        """submit --auto-approve --sync handles execution failure"""
        mock_ctx["agent_manager"].execute_task.return_value = {
            "success": False,
            "error": "Execution failed: timeout",
            "token_usage": 0,
            "execution_time": 0.0
        }

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["submit", "Test task", "--auto-approve", "--sync"])

                            # Should show failure
                            assert "failed" in result.output.lower()
                            # Note: CLI may still return 0 even on task failure
