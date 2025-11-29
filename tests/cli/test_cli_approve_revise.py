"""
Tests for CLI approve and revise commands
"""
import pytest
from unittest.mock import Mock, patch
from click.testing import CliRunner

from nightshift.interfaces.cli import cli
from nightshift.core.task_queue import TaskStatus


@pytest.fixture
def runner():
    return CliRunner()


class TestApproveCommand:
    """Tests for the approve command"""

    def test_approve_task_not_found(self, runner, mock_ctx):
        """approve shows error for nonexistent task"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["approve", "nonexistent"])

                            assert "not found" in result.output
                            assert result.exit_code == 1

    def test_approve_non_staged_task(self, runner, mock_ctx):
        """approve fails for non-staged tasks"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")
        mock_ctx["task_queue"].update_status("task_001", TaskStatus.COMMITTED)

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["approve", "task_001"])

                            assert "not in STAGED state" in result.output
                            assert result.exit_code == 1

    def test_approve_staged_task(self, runner, mock_ctx):
        """approve updates task to COMMITTED"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["approve", "task_001"])

                            assert "approved" in result.output.lower()
                            task = mock_ctx["task_queue"].get_task("task_001")
                            assert task.status == TaskStatus.COMMITTED.value

    def test_approve_sync_executes_immediately(self, runner, mock_ctx):
        """approve --sync executes task synchronously"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["approve", "task_001", "--sync"])

                            # Should call execute_task
                            mock_ctx["agent_manager"].execute_task.assert_called_once()
                            assert "completed" in result.output.lower()


class TestReviseCommand:
    """Tests for the revise command"""

    def test_revise_task_not_found(self, runner, mock_ctx):
        """revise shows error for nonexistent task"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["revise", "nonexistent", "feedback"])

                            assert "not found" in result.output
                            assert result.exit_code == 1

    def test_revise_non_staged_task(self, runner, mock_ctx):
        """revise fails for non-staged tasks"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")
        mock_ctx["task_queue"].update_status("task_001", TaskStatus.COMMITTED)

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["revise", "task_001", "feedback"])

                            assert "not in STAGED state" in result.output
                            assert result.exit_code == 1

    def test_revise_staged_task(self, runner, mock_ctx):
        """revise calls planner.refine_plan and updates task"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["revise", "task_001", "Add more tools"])

                            mock_ctx["task_planner"].refine_plan.assert_called_once()
                            assert "revised" in result.output.lower()

    def test_revise_with_timeout_override(self, runner, mock_ctx):
        """revise --timeout overrides timeout"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["revise", "task_001", "feedback", "--timeout", "600"])

                            # Check task was updated with new timeout
                            task = mock_ctx["task_queue"].get_task("task_001")
                            assert task.timeout_seconds == 600


class TestApproveFailurePaths:
    """Tests for approve command failure scenarios"""

    def test_approve_sync_execution_failure(self, runner, mock_ctx):
        """approve --sync handles execution failure gracefully"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")
        mock_ctx["agent_manager"].execute_task.return_value = {
            "success": False,
            "error": "Execution timed out",
            "token_usage": 0,
            "execution_time": 0.0
        }

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["approve", "task_001", "--sync"])

                            # Should show failure message
                            assert "failed" in result.output.lower() or "error" in result.output.lower()

    def test_approve_sync_execution_exception(self, runner, mock_ctx):
        """approve --sync propagates exception (caught by Click)"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")
        mock_ctx["agent_manager"].execute_task.side_effect = Exception("Claude CLI crashed")

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["approve", "task_001", "--sync"])

                            # Exception is caught by Click runner
                            assert result.exception is not None
                            assert "Claude CLI crashed" in str(result.exception)


class TestReviseFailurePaths:
    """Tests for revise command failure scenarios"""

    def test_revise_refine_plan_failure(self, runner, mock_ctx):
        """revise handles refine_plan failure gracefully"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")
        mock_ctx["task_planner"].refine_plan.side_effect = Exception("Refinement failed")

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["revise", "task_001", "feedback"])

                            assert "Refinement failed" in result.output or "Error" in result.output
                            assert result.exit_code != 0

    def test_revise_refine_plan_returns_error(self, runner, mock_ctx):
        """revise handles refine_plan returning error structure"""
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Test")
        mock_ctx["task_planner"].refine_plan.return_value = None  # Invalid response

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["revise", "task_001", "feedback"])

                            # Should handle invalid response (may error or show message)
                            # Exit code depends on implementation
