"""
Shared fixtures for CLI tests
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from click.testing import CliRunner

from nightshift.core.task_queue import TaskQueue, Task, TaskStatus
from nightshift.core.logger import NightShiftLogger
from nightshift.core.config import Config


@pytest.fixture
def cli_runner():
    """Click test runner"""
    return CliRunner()


@pytest.fixture
def tmp_config(tmp_path):
    """Create a temporary config"""
    config = Config(base_dir=str(tmp_path / "nightshift"))
    return config


@pytest.fixture
def mock_ctx(tmp_path):
    """Create a mock Click context with all necessary objects"""
    config = Config(base_dir=str(tmp_path / "nightshift"))
    queue = TaskQueue(db_path=str(config.get_database_path()))
    logger = NightShiftLogger(log_dir=str(config.get_log_dir()), console_output=False)

    # Mock task planner to avoid Claude subprocess
    task_planner = Mock()
    task_planner.plan_task = Mock(return_value={
        "enhanced_prompt": "Enhanced test prompt",
        "allowed_tools": ["Read", "Write"],
        "allowed_directories": [str(tmp_path)],
        "needs_git": False,
        "system_prompt": "Test system prompt",
        "reasoning": "Test reasoning"
    })
    task_planner.refine_plan = Mock(return_value={
        "enhanced_prompt": "Refined prompt",
        "allowed_tools": ["Read"],
        "allowed_directories": [str(tmp_path)],
        "needs_git": False,
        "system_prompt": "Refined system prompt",
        "estimated_tokens": 1000,
        "reasoning": "Refined reasoning"
    })

    # Mock agent manager
    agent_manager = Mock()
    agent_manager.execute_task = Mock(return_value={
        "success": True,
        "output": "Test output",
        "token_usage": 500,
        "execution_time": 10.0,
        "result_path": str(config.get_output_dir() / "test_output.json")
    })
    agent_manager.pause_task = Mock(return_value={"success": True, "message": "Paused"})
    agent_manager.resume_task = Mock(return_value={"success": True, "message": "Resumed"})
    agent_manager.kill_task = Mock(return_value={"success": True, "message": "Killed"})

    return {
        "config": config,
        "task_queue": queue,
        "logger": logger,
        "task_planner": task_planner,
        "agent_manager": agent_manager,
        "tmp_path": tmp_path
    }
