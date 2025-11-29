"""
Unit tests for AgentManager - subprocess and signal handling
Tests focus on unit behavior with mocked dependencies
"""
import pytest
import json
import signal
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

from nightshift.core.agent_manager import AgentManager
from nightshift.core.task_queue import TaskQueue, TaskStatus, Task
from nightshift.core.logger import NightShiftLogger


@pytest.fixture
def tmp_setup(tmp_path):
    """Set up temporary directories and basic fixtures"""
    db_path = tmp_path / "test.db"
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    queue = TaskQueue(db_path=str(db_path))
    logger = NightShiftLogger(log_dir=str(tmp_path / "logs"), console_output=False)

    return {
        "queue": queue,
        "logger": logger,
        "output_dir": str(output_dir),
        "tmp_path": tmp_path
    }


@pytest.fixture
def agent_manager(tmp_setup):
    """Create an AgentManager with notifications and sandbox disabled"""
    return AgentManager(
        task_queue=tmp_setup["queue"],
        logger=tmp_setup["logger"],
        output_dir=tmp_setup["output_dir"],
        enable_notifications=False,
        enable_sandbox=False
    )


class TestAgentManagerInit:
    """Tests for AgentManager initialization"""

    def test_creates_output_directory(self, tmp_path):
        """AgentManager creates output directory if missing"""
        output_dir = tmp_path / "new_output"
        assert not output_dir.exists()

        queue = TaskQueue(db_path=str(tmp_path / "test.db"))
        logger = NightShiftLogger(log_dir=str(tmp_path / "logs"), console_output=False)

        AgentManager(
            task_queue=queue,
            logger=logger,
            output_dir=str(output_dir),
            enable_notifications=False,
            enable_sandbox=False
        )

        assert output_dir.exists()

    def test_default_claude_bin(self, tmp_setup):
        """AgentManager defaults to 'claude' binary"""
        manager = AgentManager(
            task_queue=tmp_setup["queue"],
            logger=tmp_setup["logger"],
            output_dir=tmp_setup["output_dir"],
            enable_notifications=False
        )

        assert manager.claude_bin == "claude"

    def test_custom_claude_bin(self, tmp_setup):
        """AgentManager accepts custom claude binary"""
        manager = AgentManager(
            task_queue=tmp_setup["queue"],
            logger=tmp_setup["logger"],
            output_dir=tmp_setup["output_dir"],
            claude_bin="/custom/claude",
            enable_notifications=False
        )

        assert manager.claude_bin == "/custom/claude"

    def test_sandbox_disabled_when_unavailable(self, tmp_setup):
        """AgentManager disables sandbox when sandbox-exec unavailable"""
        with patch("nightshift.core.sandbox.SandboxManager.is_available", return_value=False):
            manager = AgentManager(
                task_queue=tmp_setup["queue"],
                logger=tmp_setup["logger"],
                output_dir=tmp_setup["output_dir"],
                enable_sandbox=True,
                enable_notifications=False
            )

            assert manager.sandbox is None


class TestBuildCommand:
    """Tests for _build_command method"""

    def test_basic_command_structure(self, agent_manager):
        """_build_command creates correct base command"""
        task = Task(
            task_id="test_001",
            description="Test task",
            status="running"
        )

        cmd = agent_manager._build_command(task)

        assert "claude -p" in cmd
        assert '"Test task"' in cmd
        assert "--output-format stream-json" in cmd
        assert "--verbose" in cmd

    def test_command_with_allowed_tools(self, agent_manager):
        """_build_command includes allowed tools"""
        task = Task(
            task_id="test_001",
            description="Test task",
            status="running",
            allowed_tools=["Read", "Write", "Bash"]
        )

        cmd = agent_manager._build_command(task)

        assert "--allowed-tools Read Write Bash" in cmd

    def test_command_with_system_prompt(self, agent_manager):
        """_build_command includes system prompt"""
        task = Task(
            task_id="test_001",
            description="Test task",
            status="running",
            system_prompt="You are a helpful assistant"
        )

        cmd = agent_manager._build_command(task)

        assert '--system-prompt "You are a helpful assistant"' in cmd

    def test_command_escapes_quotes(self, agent_manager):
        """_build_command escapes quotes in system prompt"""
        task = Task(
            task_id="test_001",
            description="Test task",
            status="running",
            system_prompt='Say "hello"'
        )

        cmd = agent_manager._build_command(task)

        assert r'\"hello\"' in cmd


class TestParseOutput:
    """Tests for _parse_output method"""

    def test_parse_text_content(self, agent_manager):
        """_parse_output extracts text content"""
        stdout = '{"type": "text", "text": "Hello world"}\n'

        result = agent_manager._parse_output(stdout, "")

        assert result["content"] == "Hello world"

    def test_parse_token_usage(self, agent_manager):
        """_parse_output extracts token usage"""
        stdout = '{"usage": {"input_tokens": 100, "output_tokens": 50}}\n'

        result = agent_manager._parse_output(stdout, "")

        assert result["token_usage"] == 150

    def test_parse_tool_calls(self, agent_manager):
        """_parse_output tracks tool calls"""
        stdout = '{"type": "tool_use", "name": "Read", "input": {"file": "test.txt"}}\n'

        result = agent_manager._parse_output(stdout, "")

        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["tool"] == "Read"

    def test_parse_mixed_output(self, agent_manager):
        """_parse_output handles mixed content"""
        stdout = """{"type": "text", "text": "Starting..."}
{"type": "tool_use", "name": "Read", "input": {}}
{"type": "text", "text": "Done!"}
{"usage": {"input_tokens": 50, "output_tokens": 100}}
"""

        result = agent_manager._parse_output(stdout, "")

        assert "Starting..." in result["content"]
        assert "Done!" in result["content"]
        assert result["token_usage"] == 150
        assert len(result["tool_calls"]) == 1

    def test_parse_non_json_lines(self, agent_manager):
        """_parse_output handles plain text lines"""
        stdout = "Plain text output\nMore text\n"

        result = agent_manager._parse_output(stdout, "")

        assert "Plain text output" in result["content"]
        assert "More text" in result["content"]

    def test_parse_empty_output(self, agent_manager):
        """_parse_output handles empty output"""
        result = agent_manager._parse_output("", "")

        assert result["content"] == ""
        assert result["token_usage"] is None
        assert result["tool_calls"] == []


class TestEstimateResources:
    """Tests for estimate_resources method"""

    def test_estimate_arxiv_task(self, agent_manager):
        """Arxiv tasks get higher estimates"""
        estimate = agent_manager.estimate_resources("Download arxiv paper")

        assert estimate["estimated_time"] == 60
        assert estimate["estimated_tokens"] > 2000

    def test_estimate_data_task(self, agent_manager):
        """Data tasks get medium estimates"""
        estimate = agent_manager.estimate_resources("Analyze CSV data")

        assert estimate["estimated_time"] == 120
        assert estimate["estimated_tokens"] > 1000

    def test_estimate_default_task(self, agent_manager):
        """Default tasks get baseline estimates"""
        estimate = agent_manager.estimate_resources("Simple task")

        assert estimate["estimated_time"] == 30
        assert estimate["estimated_tokens"] >= 500


class TestPauseTask:
    """Tests for pause_task method"""

    def test_pause_nonexistent_task(self, agent_manager, tmp_setup):
        """pause_task fails for nonexistent task"""
        result = agent_manager.pause_task("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_pause_non_running_task(self, agent_manager, tmp_setup):
        """pause_task fails for non-running task"""
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")

        result = agent_manager.pause_task("task_001")

        assert result["success"] is False
        assert "not running" in result["error"]

    def test_pause_task_no_pid(self, agent_manager, tmp_setup):
        """pause_task fails if task has no PID"""
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        tmp_setup["queue"].update_status("task_001", TaskStatus.RUNNING)

        result = agent_manager.pause_task("task_001")

        assert result["success"] is False
        assert "no process ID" in result["error"]

    def test_pause_dead_process(self, agent_manager, tmp_setup):
        """pause_task fails if process no longer exists"""
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        tmp_setup["queue"].update_status("task_001", TaskStatus.RUNNING, process_id=99999)

        with patch("os.kill", side_effect=ProcessLookupError):
            result = agent_manager.pause_task("task_001")

        assert result["success"] is False
        assert "no longer exists" in result["error"]

    def test_pause_success(self, agent_manager, tmp_setup):
        """pause_task sends SIGSTOP on success"""
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        tmp_setup["queue"].update_status("task_001", TaskStatus.RUNNING, process_id=12345)

        with patch("os.kill") as mock_kill:
            result = agent_manager.pause_task("task_001")

        assert result["success"] is True
        # Should have called kill twice: once with 0 to check, once with SIGSTOP
        calls = mock_kill.call_args_list
        assert any(call[0] == (12345, signal.SIGSTOP) for call in calls)


class TestResumeTask:
    """Tests for resume_task method"""

    def test_resume_nonexistent_task(self, agent_manager, tmp_setup):
        """resume_task fails for nonexistent task"""
        result = agent_manager.resume_task("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_resume_non_paused_task(self, agent_manager, tmp_setup):
        """resume_task fails for non-paused task"""
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        tmp_setup["queue"].update_status("task_001", TaskStatus.RUNNING, process_id=12345)

        result = agent_manager.resume_task("task_001")

        assert result["success"] is False
        assert "not paused" in result["error"]

    def test_resume_success(self, agent_manager, tmp_setup):
        """resume_task sends SIGCONT on success"""
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        tmp_setup["queue"].update_status("task_001", TaskStatus.RUNNING, process_id=12345)
        tmp_setup["queue"].update_status("task_001", TaskStatus.PAUSED)

        with patch("os.kill") as mock_kill:
            result = agent_manager.resume_task("task_001")

        assert result["success"] is True
        calls = mock_kill.call_args_list
        assert any(call[0] == (12345, signal.SIGCONT) for call in calls)


class TestKillTask:
    """Tests for kill_task method"""

    def test_kill_nonexistent_task(self, agent_manager, tmp_setup):
        """kill_task fails for nonexistent task"""
        result = agent_manager.kill_task("nonexistent")

        assert result["success"] is False
        assert "not found" in result["error"]

    def test_kill_completed_task(self, agent_manager, tmp_setup):
        """kill_task fails for completed task"""
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMPLETED)

        result = agent_manager.kill_task("task_001")

        assert result["success"] is False
        assert "not running or paused" in result["error"]

    def test_kill_already_dead_process(self, agent_manager, tmp_setup):
        """kill_task handles already-dead process gracefully"""
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        tmp_setup["queue"].update_status("task_001", TaskStatus.RUNNING, process_id=12345)

        with patch("os.kill", side_effect=ProcessLookupError):
            result = agent_manager.kill_task("task_001")

        # Should still succeed since process is gone
        assert result["success"] is True
        assert "already terminated" in result["message"]

    def test_kill_success(self, agent_manager, tmp_setup):
        """kill_task sends SIGKILL on success"""
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        tmp_setup["queue"].update_status("task_001", TaskStatus.RUNNING, process_id=12345)

        with patch("os.kill") as mock_kill:
            result = agent_manager.kill_task("task_001")

        assert result["success"] is True
        calls = mock_kill.call_args_list
        assert any(call[0] == (12345, signal.SIGKILL) for call in calls)

    def test_kill_paused_task(self, agent_manager, tmp_setup):
        """kill_task can kill paused tasks"""
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        tmp_setup["queue"].update_status("task_001", TaskStatus.RUNNING, process_id=12345)
        tmp_setup["queue"].update_status("task_001", TaskStatus.PAUSED)

        with patch("os.kill") as mock_kill:
            result = agent_manager.kill_task("task_001")

        assert result["success"] is True


class TestExecuteTask:
    """Tests for execute_task method"""

    @pytest.fixture
    def mock_process(self):
        """Create a mock process object"""
        process = MagicMock()
        process.pid = 12345
        process.returncode = None
        # Simulate process completing after first poll
        process.poll.side_effect = [None, 0]
        process.stdout = MagicMock()
        process.stderr = MagicMock()
        process.stdout.fileno.return_value = 1
        process.stderr.fileno.return_value = 2
        process.stdout.readline.side_effect = ['{"type": "text", "text": "Hello"}\n', '']
        process.stderr.readline.side_effect = ['', '']
        process.stdout.read.return_value = ''
        process.stderr.read.return_value = ''
        return process

    def test_execute_task_success(self, tmp_setup, mock_process):
        """execute_task returns success for successful command"""
        manager = AgentManager(
            task_queue=tmp_setup["queue"],
            logger=tmp_setup["logger"],
            output_dir=tmp_setup["output_dir"],
            enable_notifications=False,
            enable_sandbox=False
        )

        # Create and commit task
        tmp_setup["queue"].create_task(task_id="task_001", description="Test task")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        task = tmp_setup["queue"].get_task("task_001")

        with patch("subprocess.Popen", return_value=mock_process):
            with patch("fcntl.fcntl"):
                with patch("time.sleep"):
                    result = manager.execute_task(task)

        assert result["success"] is True
        assert "execution_time" in result

        # Task should be marked completed
        updated_task = tmp_setup["queue"].get_task("task_001")
        assert updated_task.status == TaskStatus.COMPLETED.value

    def test_execute_task_failure(self, tmp_setup):
        """execute_task returns failure for non-zero exit code"""
        manager = AgentManager(
            task_queue=tmp_setup["queue"],
            logger=tmp_setup["logger"],
            output_dir=tmp_setup["output_dir"],
            enable_notifications=False,
            enable_sandbox=False
        )

        # Create mock process that fails
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.side_effect = [None, 1]  # Non-zero exit
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()
        mock_process.stdout.fileno.return_value = 1
        mock_process.stderr.fileno.return_value = 2
        mock_process.stdout.readline.side_effect = ['', '']
        mock_process.stderr.readline.side_effect = ['Error: command failed\n', '']
        mock_process.stdout.read.return_value = ''
        mock_process.stderr.read.return_value = ''

        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        task = tmp_setup["queue"].get_task("task_001")

        with patch("subprocess.Popen", return_value=mock_process):
            with patch("fcntl.fcntl"):
                with patch("time.sleep"):
                    result = manager.execute_task(task)

        assert result["success"] is False
        assert "error" in result

        # Task should be marked failed
        updated_task = tmp_setup["queue"].get_task("task_001")
        assert updated_task.status == TaskStatus.FAILED.value

    def test_execute_task_timeout(self, tmp_setup):
        """execute_task handles timeout"""
        manager = AgentManager(
            task_queue=tmp_setup["queue"],
            logger=tmp_setup["logger"],
            output_dir=tmp_setup["output_dir"],
            enable_notifications=False,
            enable_sandbox=False
        )

        # Create mock process that never completes
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_process.poll.return_value = None  # Never completes
        mock_process.stdout = MagicMock()
        mock_process.stderr = MagicMock()
        mock_process.stdout.fileno.return_value = 1
        mock_process.stderr.fileno.return_value = 2
        mock_process.stdout.readline.return_value = ''
        mock_process.stderr.readline.return_value = ''
        mock_process.communicate.return_value = ('', '')

        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        task = tmp_setup["queue"].get_task("task_001")

        # Mock time.time - need many calls for the loop + exception handling
        start_time = 1000.0
        time_values = [start_time] * 10 + [start_time + 1000] * 10  # Eventually timeout
        with patch("subprocess.Popen", return_value=mock_process):
            with patch("fcntl.fcntl"):
                with patch("time.sleep"):
                    with patch("nightshift.core.agent_manager.time.time", side_effect=time_values):
                        result = manager.execute_task(task, timeout=1)

        assert result["success"] is False
        assert "timeout" in result["error"].lower()

    def test_execute_task_exception(self, tmp_setup):
        """execute_task handles unexpected exceptions"""
        manager = AgentManager(
            task_queue=tmp_setup["queue"],
            logger=tmp_setup["logger"],
            output_dir=tmp_setup["output_dir"],
            enable_notifications=False,
            enable_sandbox=False
        )

        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        task = tmp_setup["queue"].get_task("task_001")

        with patch("subprocess.Popen", side_effect=OSError("Failed to start process")):
            result = manager.execute_task(task)

        assert result["success"] is False
        assert "error" in result

        # Task should be marked failed
        updated_task = tmp_setup["queue"].get_task("task_001")
        assert updated_task.status == TaskStatus.FAILED.value

    def test_execute_task_with_notifications(self, tmp_setup, mock_process):
        """execute_task sends notifications when enabled"""
        manager = AgentManager(
            task_queue=tmp_setup["queue"],
            logger=tmp_setup["logger"],
            output_dir=tmp_setup["output_dir"],
            enable_notifications=True,
            enable_sandbox=False,
            enable_terminal_notifications=False
        )

        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        task = tmp_setup["queue"].get_task("task_001")

        with patch("subprocess.Popen", return_value=mock_process):
            with patch("fcntl.fcntl"):
                with patch("time.sleep"):
                    with patch.object(manager.notifier, "notify") as mock_notify:
                        result = manager.execute_task(task)

        assert result["success"] is True
        mock_notify.assert_called_once()
        # Check notification was called with success=True
        call_kwargs = mock_notify.call_args[1]
        assert call_kwargs["success"] is True

    def test_execute_task_with_needs_git(self, tmp_setup, mock_process):
        """execute_task loads GH_TOKEN when needs_git is True"""
        manager = AgentManager(
            task_queue=tmp_setup["queue"],
            logger=tmp_setup["logger"],
            output_dir=tmp_setup["output_dir"],
            enable_notifications=False,
            enable_sandbox=False
        )

        tmp_setup["queue"].create_task(
            task_id="task_001",
            description="Test",
            needs_git=True
        )
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        task = tmp_setup["queue"].get_task("task_001")

        # Mock gh auth token
        mock_gh_result = MagicMock()
        mock_gh_result.returncode = 0
        mock_gh_result.stdout = "ghp_testtoken123\n"

        with patch("subprocess.Popen", return_value=mock_process):
            with patch("subprocess.run", return_value=mock_gh_result) as mock_run:
                with patch("fcntl.fcntl"):
                    with patch("time.sleep"):
                        result = manager.execute_task(task)

        assert result["success"] is True
        # gh auth token should have been called
        mock_run.assert_called()

    def test_execute_task_gh_token_failure(self, tmp_setup, mock_process):
        """execute_task continues when GH_TOKEN loading fails"""
        manager = AgentManager(
            task_queue=tmp_setup["queue"],
            logger=tmp_setup["logger"],
            output_dir=tmp_setup["output_dir"],
            enable_notifications=False,
            enable_sandbox=False
        )

        tmp_setup["queue"].create_task(
            task_id="task_001",
            description="Test",
            needs_git=True
        )
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        task = tmp_setup["queue"].get_task("task_001")

        with patch("subprocess.Popen", return_value=mock_process):
            with patch("subprocess.run", side_effect=Exception("gh not found")):
                with patch("fcntl.fcntl"):
                    with patch("time.sleep"):
                        result = manager.execute_task(task)

        # Should still succeed even if gh fails
        assert result["success"] is True


class TestBuildCommandWithSandbox:
    """Tests for _build_command with sandbox enabled"""

    def test_build_command_with_sandbox(self, tmp_setup):
        """_build_command wraps with sandbox when enabled"""
        with patch("nightshift.core.sandbox.SandboxManager.is_available", return_value=True):
            manager = AgentManager(
                task_queue=tmp_setup["queue"],
                logger=tmp_setup["logger"],
                output_dir=tmp_setup["output_dir"],
                enable_sandbox=True,
                enable_notifications=False
            )

        task = Task(
            task_id="test_001",
            description="Test task",
            status="running",
            allowed_directories=["/tmp/test"]
        )

        cmd = manager._build_command(task)

        # Should be wrapped with sandbox-exec
        assert "sandbox-exec" in cmd

    def test_build_command_read_only_sandbox(self, tmp_setup):
        """_build_command uses read-only sandbox when no directories"""
        with patch("nightshift.core.sandbox.SandboxManager.is_available", return_value=True):
            manager = AgentManager(
                task_queue=tmp_setup["queue"],
                logger=tmp_setup["logger"],
                output_dir=tmp_setup["output_dir"],
                enable_sandbox=True,
                enable_notifications=False
            )

        task = Task(
            task_id="test_001",
            description="Test task",
            status="running",
            allowed_directories=[]  # Empty
        )

        cmd = manager._build_command(task)

        assert "sandbox-exec" in cmd

    def test_build_command_sandbox_validation_error(self, tmp_setup):
        """_build_command raises on sandbox validation failure"""
        with patch("nightshift.core.sandbox.SandboxManager.is_available", return_value=True):
            with patch("nightshift.core.sandbox.SandboxManager.validate_directories", side_effect=ValueError("Invalid path")):
                manager = AgentManager(
                    task_queue=tmp_setup["queue"],
                    logger=tmp_setup["logger"],
                    output_dir=tmp_setup["output_dir"],
                    enable_sandbox=True,
                    enable_notifications=False
                )

                task = Task(
                    task_id="test_001",
                    description="Test",
                    status="running",
                    allowed_directories=["/invalid/../path"]
                )

                with pytest.raises(ValueError):
                    manager._build_command(task)
