"""
Tests for task deletion functionality
"""
import types
import pytest
from nightshift.interfaces.tui.app import create_app_for_test


def make_task(task_id, status="completed", description=None):
    """Helper to create a dummy task object"""
    t = types.SimpleNamespace(
        task_id=task_id,
        status=status,
        description=description or f"Task {task_id}",
        created_at="2025-01-01T00:00:00",
        result_path=None,
    )
    t.to_dict = lambda: {
        "task_id": t.task_id,
        "status": t.status,
        "description": t.description,
        "created_at": t.created_at,
        "result_path": t.result_path,
    }
    return t


def test_delete_task_removes_from_database(tmp_path):
    """Test that deleting a task removes it from the database"""
    task = make_task("task_abc123", status="completed", description="Test task")

    app, state, controller, queue, agent, logger = create_app_for_test([task], tmp_path)

    # Verify task exists
    assert len(queue.list_tasks()) == 1
    assert queue.get_task("task_abc123") is not None

    # Delete the task
    controller.delete_selected_task()

    # Wait for deletion to complete (runs in thread)
    import time
    time.sleep(0.1)

    # Verify task is deleted
    assert len(queue.list_tasks()) == 0
    assert queue.get_task("task_abc123") is None


def test_delete_task_updates_ui(tmp_path):
    """Test that deleting a task updates the UI state"""
    task1 = make_task("task_111", status="completed", description="Task 1")
    task2 = make_task("task_222", status="completed", description="Task 2")

    app, state, controller, queue, agent, logger = create_app_for_test([task1, task2], tmp_path)

    # Verify initial state
    assert len(state.tasks) == 2
    assert state.selected_index == 0

    # Delete first task
    controller.delete_selected_task()

    # Wait for deletion and refresh
    import time
    time.sleep(0.1)

    # Verify UI updated
    assert len(state.tasks) == 1
    assert state.tasks[0].task_id == "task_222"


def test_delete_task_with_empty_list(tmp_path):
    """Test that delete does nothing when task list is empty"""
    app, state, controller, queue, agent, logger = create_app_for_test([], tmp_path)

    # Delete with empty list should not crash
    controller.delete_selected_task()

    # Verify still empty
    assert len(state.tasks) == 0
    assert len(queue.list_tasks()) == 0


def test_delete_adjusts_selection_index(tmp_path):
    """Test that selection index adjusts when deleting last task"""
    task1 = make_task("task_111", status="completed", description="Task 1")
    task2 = make_task("task_222", status="completed", description="Task 2")

    app, state, controller, queue, agent, logger = create_app_for_test([task1, task2], tmp_path)

    # Select second task
    state.selected_index = 1
    controller.load_selected_task_details()

    # Delete second task
    controller.delete_selected_task()

    # Wait for deletion and refresh
    import time
    time.sleep(0.1)

    # Verify selection index adjusted
    assert state.selected_index == 0
    assert len(state.tasks) == 1
