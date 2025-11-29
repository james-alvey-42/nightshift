"""
Tests for TaskPlanner - Claude-based task analysis and planning
"""
import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from nightshift.core.task_planner import TaskPlanner
from nightshift.core.logger import NightShiftLogger


@pytest.fixture
def mock_logger(tmp_path):
    """Create a mock logger"""
    return NightShiftLogger(log_dir=str(tmp_path / "logs"), console_output=False)


@pytest.fixture
def tools_reference(tmp_path):
    """Create a minimal tools reference file"""
    tools_file = tmp_path / "tools.md"
    tools_file.write_text("""# Available Tools
- Read: Read files
- Write: Write files
- Bash: Execute commands
""")
    return str(tools_file)


class TestTaskPlannerInit:
    """Tests for TaskPlanner initialization"""

    def test_init_with_tools_reference(self, mock_logger, tools_reference):
        """TaskPlanner loads tools reference from specified path"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        assert "Read" in planner.tools_reference
        assert "Write" in planner.tools_reference

    def test_init_missing_tools_reference(self, mock_logger, tmp_path):
        """TaskPlanner handles missing tools reference gracefully"""
        missing_path = tmp_path / "nonexistent.md"
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=str(missing_path))

        assert planner.tools_reference == ""

    def test_init_default_tools_reference_path(self, mock_logger):
        """TaskPlanner uses default package tools reference when path not specified"""
        planner = TaskPlanner(logger=mock_logger)

        # Should resolve to package's config directory
        expected_path = Path(__file__).parent.parent.parent / "nightshift" / "config" / "claude-code-tools-reference.md"
        # The path should be set even if file doesn't exist in test environment
        assert "config" in str(planner.tools_reference_path)
        assert "claude-code-tools-reference.md" in str(planner.tools_reference_path)

    def test_init_default_claude_bin(self, mock_logger, tools_reference):
        """TaskPlanner defaults to 'claude' binary"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        assert planner.claude_bin == "claude"

    def test_init_custom_claude_bin(self, mock_logger, tools_reference):
        """TaskPlanner accepts custom claude binary path"""
        planner = TaskPlanner(
            logger=mock_logger,
            tools_reference_path=tools_reference,
            claude_bin="/custom/path/claude"
        )

        assert planner.claude_bin == "/custom/path/claude"


class TestPlanTask:
    """Tests for plan_task method"""

    def test_plan_task_success(self, mock_logger, tools_reference):
        """plan_task returns structured plan on success"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        mock_response = {
            "structured_output": {
                "enhanced_prompt": "Enhanced task description",
                "allowed_tools": ["Read", "Write"],
                "allowed_directories": ["/tmp/work"],
                "needs_git": False,
                "system_prompt": "You are an assistant",
                "reasoning": "Selected tools for file operations"
            }
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )

            plan = planner.plan_task("Write a Python script")

            assert plan["enhanced_prompt"] == "Enhanced task description"
            assert "Read" in plan["allowed_tools"]
            assert plan["needs_git"] is False

    def test_plan_task_parses_result_wrapper(self, mock_logger, tools_reference):
        """plan_task handles result wrapper format"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        # Format where result is in 'result' key with markdown
        mock_response = {
            "result": """```json
{
    "enhanced_prompt": "Test prompt",
    "allowed_tools": ["Read"],
    "allowed_directories": ["/tmp"],
    "needs_git": false,
    "system_prompt": "System prompt"
}
```"""
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )

            plan = planner.plan_task("Test task")

            assert plan["enhanced_prompt"] == "Test prompt"
            assert plan["allowed_tools"] == ["Read"]

    def test_plan_task_command_failure(self, mock_logger, tools_reference):
        """plan_task raises exception on command failure"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="Command failed"
            )

            with pytest.raises(Exception) as exc_info:
                planner.plan_task("Test task")

            assert "Planning failed" in str(exc_info.value)

    def test_plan_task_timeout(self, mock_logger, tools_reference):
        """plan_task raises exception on timeout"""
        import subprocess
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=120)

            with pytest.raises(Exception) as exc_info:
                planner.plan_task("Test task")

            assert "took too long" in str(exc_info.value)

    def test_plan_task_invalid_json(self, mock_logger, tools_reference):
        """plan_task raises exception on invalid JSON response"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="not valid json",
                stderr=""
            )

            with pytest.raises(Exception) as exc_info:
                planner.plan_task("Test task")

            assert "not valid JSON" in str(exc_info.value)

    def test_plan_task_missing_required_field(self, mock_logger, tools_reference):
        """plan_task raises exception when required field missing"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        # Missing 'system_prompt' field
        mock_response = {
            "structured_output": {
                "enhanced_prompt": "Test",
                "allowed_tools": [],
                "allowed_directories": [],
                "needs_git": False
                # Missing system_prompt
            }
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )

            with pytest.raises(Exception) as exc_info:
                planner.plan_task("Test task")

            assert "missing field" in str(exc_info.value)

    def test_plan_task_uses_timeout_parameter(self, mock_logger, tools_reference):
        """plan_task respects timeout parameter"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        mock_response = {
            "structured_output": {
                "enhanced_prompt": "Test",
                "allowed_tools": [],
                "allowed_directories": [],
                "needs_git": False,
                "system_prompt": "Test"
            }
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )

            planner.plan_task("Test task", timeout=60)

            # Verify timeout was passed to subprocess
            call_kwargs = mock_run.call_args[1]
            assert call_kwargs["timeout"] == 60

    def test_plan_task_parses_plain_fenced_json(self, mock_logger, tools_reference):
        """plan_task handles plain ``` fences without json suffix"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        # Format with plain ``` fence (not ```json)
        mock_response = {
            "result": """```
{
    "enhanced_prompt": "Plain fenced prompt",
    "allowed_tools": ["Read"],
    "allowed_directories": ["/tmp"],
    "needs_git": false,
    "system_prompt": "System prompt"
}
```"""
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )

            plan = planner.plan_task("Test task")

            assert plan["enhanced_prompt"] == "Plain fenced prompt"
            assert plan["allowed_tools"] == ["Read"]

    def test_plan_task_parses_direct_json(self, mock_logger, tools_reference):
        """plan_task handles direct JSON without wrapper"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        # Direct JSON without structured_output or result wrapper
        mock_response = {
            "enhanced_prompt": "Direct prompt",
            "allowed_tools": ["Write"],
            "allowed_directories": ["/home"],
            "needs_git": True,
            "system_prompt": "Direct system prompt"
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )

            plan = planner.plan_task("Test task")

            assert plan["enhanced_prompt"] == "Direct prompt"
            assert plan["needs_git"] is True


class TestRefinePlan:
    """Tests for refine_plan method"""

    def test_refine_plan_success(self, mock_logger, tools_reference):
        """refine_plan returns updated plan"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        current_plan = {
            "enhanced_prompt": "Original prompt",
            "allowed_tools": ["Read"],
            "allowed_directories": ["/tmp"],
            "needs_git": False,
            "system_prompt": "Original system prompt"
        }

        mock_response = {
            "structured_output": {
                "enhanced_prompt": "Refined prompt",
                "allowed_tools": ["Read", "Write"],
                "allowed_directories": ["/tmp", "/home/user"],
                "needs_git": True,
                "system_prompt": "Refined system prompt",
                "estimated_tokens": 1500,
                "reasoning": "Added Write tool per feedback"
            }
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )

            refined = planner.refine_plan(current_plan, "Please add Write tool")

            assert refined["enhanced_prompt"] == "Refined prompt"
            assert "Write" in refined["allowed_tools"]
            assert refined["needs_git"] is True

    def test_refine_plan_timeout(self, mock_logger, tools_reference):
        """refine_plan raises exception on timeout"""
        import subprocess
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=30)

            with pytest.raises(Exception) as exc_info:
                planner.refine_plan({}, "feedback")

            assert "took too long" in str(exc_info.value)

    def test_refine_plan_command_failure(self, mock_logger, tools_reference):
        """refine_plan raises exception on command failure"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="Refinement command failed"
            )

            with pytest.raises(Exception) as exc_info:
                planner.refine_plan({}, "Add more tools")

            assert "refinement failed" in str(exc_info.value).lower()

    def test_refine_plan_invalid_json(self, mock_logger, tools_reference):
        """refine_plan raises exception on invalid JSON response"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout="not valid json at all",
                stderr=""
            )

            with pytest.raises(Exception) as exc_info:
                planner.refine_plan({}, "feedback")

            assert "not valid JSON" in str(exc_info.value)

    def test_refine_plan_parses_result_wrapper(self, mock_logger, tools_reference):
        """refine_plan handles result wrapper with code fences"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        mock_response = {
            "result": """```json
{
    "enhanced_prompt": "Refined via wrapper",
    "allowed_tools": ["Read", "Write"],
    "allowed_directories": ["/tmp"],
    "needs_git": false,
    "system_prompt": "Refined system",
    "estimated_tokens": 1200
}
```"""
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )

            refined = planner.refine_plan({}, "Add Write tool")

            assert refined["enhanced_prompt"] == "Refined via wrapper"
            assert "Write" in refined["allowed_tools"]
            assert refined["estimated_tokens"] == 1200

    def test_refine_plan_parses_plain_fenced_json(self, mock_logger, tools_reference):
        """refine_plan handles plain ``` fences without json suffix"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        mock_response = {
            "result": """```
{
    "enhanced_prompt": "Plain fence refined",
    "allowed_tools": ["Bash"],
    "allowed_directories": ["/home"],
    "needs_git": true,
    "system_prompt": "Use bash",
    "estimated_tokens": 800
}
```"""
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )

            refined = planner.refine_plan({}, "Add Bash tool")

            assert refined["enhanced_prompt"] == "Plain fence refined"
            assert refined["needs_git"] is True

    def test_refine_plan_parses_direct_json(self, mock_logger, tools_reference):
        """refine_plan handles direct JSON without wrapper"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        # Direct JSON without structured_output or result wrapper
        mock_response = {
            "enhanced_prompt": "Direct refined",
            "allowed_tools": ["Read"],
            "allowed_directories": ["/data"],
            "needs_git": False,
            "system_prompt": "Direct system",
            "estimated_tokens": 500
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )

            refined = planner.refine_plan({}, "Simplify")

            assert refined["enhanced_prompt"] == "Direct refined"
            assert refined["estimated_tokens"] == 500

    def test_refine_plan_missing_required_field(self, mock_logger, tools_reference):
        """refine_plan raises exception when required field missing"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        # Missing 'estimated_tokens' field (required for refine_plan)
        mock_response = {
            "structured_output": {
                "enhanced_prompt": "Test",
                "allowed_tools": [],
                "allowed_directories": [],
                "needs_git": False,
                "system_prompt": "Test"
                # Missing estimated_tokens
            }
        }

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout=json.dumps(mock_response),
                stderr=""
            )

            with pytest.raises(Exception) as exc_info:
                planner.refine_plan({}, "feedback")

            assert "missing field" in str(exc_info.value).lower()


class TestQuickEstimate:
    """Tests for quick_estimate fallback method"""

    def test_estimate_arxiv_task(self, mock_logger, tools_reference):
        """Arxiv tasks get higher estimates"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        estimate = planner.quick_estimate("Download arxiv paper 2301.00001")

        assert estimate["estimated_tokens"] == 2500
        assert estimate["estimated_time"] == 300

    def test_estimate_paper_task(self, mock_logger, tools_reference):
        """Paper tasks get higher estimates"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        estimate = planner.quick_estimate("Summarize the research paper")

        assert estimate["estimated_tokens"] == 2500

    def test_estimate_data_task(self, mock_logger, tools_reference):
        """Data analysis tasks get medium estimates"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        estimate = planner.quick_estimate("Analyze the CSV file and create a plot")

        assert estimate["estimated_tokens"] == 1500
        assert estimate["estimated_time"] == 300

    def test_estimate_default_task(self, mock_logger, tools_reference):
        """Default tasks get baseline estimates"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        estimate = planner.quick_estimate("Hello world")

        assert estimate["estimated_tokens"] == 500
        assert estimate["estimated_time"] == 120

    def test_estimate_case_insensitive(self, mock_logger, tools_reference):
        """Keyword matching is case insensitive"""
        planner = TaskPlanner(logger=mock_logger, tools_reference_path=tools_reference)

        estimate = planner.quick_estimate("Download ARXIV paper")

        assert estimate["estimated_tokens"] == 2500
