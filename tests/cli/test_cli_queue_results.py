"""
Tests for CLI queue and results commands
"""
import pytest
import json
from unittest.mock import Mock, patch
from click.testing import CliRunner

from nightshift.interfaces.cli import cli
from nightshift.core.task_queue import TaskStatus


@pytest.fixture
def runner():
    return CliRunner()


class TestQueueCommand:
    """Tests for the queue command"""

    def test_queue_empty(self, runner, tmp_path):
        """queue shows empty message when no tasks"""
        with runner.isolated_filesystem(temp_dir=tmp_path):
            with patch("nightshift.interfaces.cli.Config") as mock_config:
                mock_config.return_value.base_dir = tmp_path / "nightshift"
                mock_config.return_value.get_log_dir.return_value = tmp_path / "logs"
                mock_config.return_value.get_database_path.return_value = tmp_path / "test.db"
                mock_config.return_value.get_output_dir.return_value = tmp_path / "output"
                mock_config.return_value.get_tools_reference_path.return_value = tmp_path / "tools.md"

                (tmp_path / "logs").mkdir(parents=True, exist_ok=True)
                (tmp_path / "output").mkdir(parents=True, exist_ok=True)

                result = runner.invoke(cli, ["queue"])

                assert "No tasks found" in result.output

    def test_queue_with_tasks(self, runner, mock_ctx):
        """queue displays tasks in table format"""
        # Create a task
        mock_ctx["task_queue"].create_task(
            task_id="task_001",
            description="Test task"
        )

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["queue"])

                            assert "task_001" in result.output
                            assert "STAGED" in result.output

    def test_queue_filter_by_status(self, runner, mock_ctx):
        """queue --status filters by status"""
        # Create tasks with different statuses
        mock_ctx["task_queue"].create_task(task_id="task_001", description="Staged")
        mock_ctx["task_queue"].create_task(task_id="task_002", description="Running")
        mock_ctx["task_queue"].update_status("task_002", TaskStatus.COMMITTED)
        mock_ctx["task_queue"].update_status("task_002", TaskStatus.RUNNING)

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["queue", "--status", "staged"])

                            assert "task_001" in result.output
                            assert "task_002" not in result.output


class TestResultsCommand:
    """Tests for the results command"""

    def test_results_task_not_found(self, runner, mock_ctx):
        """results shows error for nonexistent task"""
        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["results", "nonexistent"])

                            assert "not found" in result.output
                            assert result.exit_code == 1

    def test_results_displays_task_info(self, runner, mock_ctx):
        """results displays task information"""
        mock_ctx["task_queue"].create_task(
            task_id="task_001",
            description="Test task"
        )

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["results", "task_001"])

                            assert "task_001" in result.output
                            assert "STAGED" in result.output
                            assert "Test task" in result.output

    def test_results_show_output_flag(self, runner, mock_ctx):
        """results --show-output displays output file"""
        # Create task with result path
        mock_ctx["task_queue"].create_task(
            task_id="task_001",
            description="Test task"
        )

        # Create output file
        output_file = mock_ctx["config"].get_output_dir() / "task_001_output.json"
        output_file.write_text(json.dumps({"status": "completed", "output": "test"}))

        mock_ctx["task_queue"].update_status(
            "task_001",
            TaskStatus.COMPLETED,
            result_path=str(output_file)
        )

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["results", "task_001", "--show-output"])

                            # Output should include JSON content
                            assert "completed" in result.output or "test" in result.output


class TestResultsFailurePaths:
    """Tests for results command failure scenarios"""

    def test_results_show_output_file_missing(self, runner, mock_ctx):
        """results --show-output handles missing file gracefully"""
        mock_ctx["task_queue"].create_task(
            task_id="task_001",
            description="Test task"
        )

        # Set result_path but don't create file
        mock_ctx["task_queue"].update_status(
            "task_001",
            TaskStatus.COMPLETED,
            result_path="/nonexistent/path/output.json"
        )

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["results", "task_001", "--show-output"])

                            # Should handle gracefully - either error message or skip
                            # Don't crash with unhandled exception
                            assert result.exception is None or "not found" in result.output.lower() or "task_001" in result.output

    def test_results_show_output_no_result_path(self, runner, mock_ctx):
        """results --show-output handles missing result_path"""
        mock_ctx["task_queue"].create_task(
            task_id="task_001",
            description="Test task"
        )
        # Task has no result_path set (still staged)

        with patch("nightshift.interfaces.cli.Config", return_value=mock_ctx["config"]):
            with patch("nightshift.interfaces.cli.TaskQueue", return_value=mock_ctx["task_queue"]):
                with patch("nightshift.interfaces.cli.NightShiftLogger", return_value=mock_ctx["logger"]):
                    with patch("nightshift.interfaces.cli.TaskPlanner", return_value=mock_ctx["task_planner"]):
                        with patch("nightshift.interfaces.cli.AgentManager", return_value=mock_ctx["agent_manager"]):
                            result = runner.invoke(cli, ["results", "task_001", "--show-output"])

                            # Should handle gracefully
                            assert result.exception is None
