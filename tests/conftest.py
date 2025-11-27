"""
Test fixtures and utilities for NightShift TUI tests
"""
import types
import pytest
from nightshift.interfaces.tui.models import UIState
from nightshift.interfaces.tui.controllers import TUIController
from nightshift.interfaces.tui.testing_doubles import (
    DummyQueue,
    DummyConfig,
    DummyPlanner,
    DummyAgent,
    DummyLogger,
)


@pytest.fixture
def controller(tmp_path):
    """
    Create a TUIController with mocked backends for testing.

    Returns:
        tuple: (state, controller, tmp_path, queue, agent)
    """
    from nightshift.core.task_queue import TaskStatus

    # Create a fake RUNNING task
    task = types.SimpleNamespace(
        task_id="task_1",
        status=TaskStatus.RUNNING.value,
        description="Test running task",
        created_at="2025-01-01T00:00:00",
        result_path=str(tmp_path / "task_1_output.json"),
    )
    task.to_dict = lambda: {
        "task_id": task.task_id,
        "status": task.status,
        "description": task.description,
        "created_at": task.created_at,
        "result_path": task.result_path,
    }

    state = UIState()
    queue = DummyQueue([task])
    config = DummyConfig(tmp_path)
    planner = DummyPlanner()
    agent = DummyAgent()
    logger = DummyLogger()

    ctl = TUIController(state, queue, config, planner, agent, logger)

    return state, ctl, tmp_path, queue, agent
