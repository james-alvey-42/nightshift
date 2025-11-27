"""
Tests for controller exec log loading and real-time updates
"""
import json
import time
from pathlib import Path


def write_result(path, lines):
    """
    Write a mock result file with stream-json stdout.

    Args:
        path: Path to result file
        lines: List of event dicts to write as JSON lines
    """
    stdout_lines = [json.dumps(event) for event in lines]
    data = {"stdout": "\n".join(stdout_lines)}
    Path(path).write_text(json.dumps(data))


def test_exec_log_initial_load(controller):
    """Test that exec log loads on first task selection"""
    state, ctl, tmp_path, queue, agent = controller

    # Create result file with initial content
    result_path = tmp_path / "task_1_output.json"
    write_result(result_path, [
        {"type": "text", "text": "hello world"}
    ])

    # Refresh tasks to populate task list
    ctl.refresh_tasks()
    assert len(state.tasks) == 1
    assert state.tasks[0].task_id == "task_1"

    # Load selected task details (simulates first selection)
    ctl.load_selected_task_details()

    # Exec snippet should be loaded
    st = state.selected_task
    assert st.task_id == "task_1"
    assert st.exec_snippet  # not empty
    assert "hello world" in st.exec_snippet or "hello" in st.exec_snippet
    assert st.log_mtime is not None
    assert st.log_size is not None


def test_exec_log_updates_for_running_task(controller):
    """Test that exec log updates when file changes for RUNNING task"""
    state, ctl, tmp_path, queue, agent = controller

    result_path = tmp_path / "task_1_output.json"

    # Initial log: one line
    write_result(result_path, [
        {"type": "text", "text": "hello"}
    ])

    # First load: selection changed, so _load_exec_snippet is used
    ctl.refresh_tasks()
    ctl.load_selected_task_details()

    st = state.selected_task
    assert st.task_id == "task_1"
    initial_snippet = st.exec_snippet
    assert "hello" in initial_snippet
    initial_mtime = st.log_mtime
    initial_size = st.log_size

    # Append another line and ensure mtime changes
    time.sleep(0.1)  # Increased from 0.01 for filesystem timestamp reliability
    write_result(result_path, [
        {"type": "text", "text": "hello"},
        {"type": "text", "text": "world"},
    ])

    # Simulate auto-refresh: same task selected, status RUNNING
    ctl.load_selected_task_details()

    # Metadata should have changed
    assert st.log_mtime != initial_mtime or st.log_size != initial_size
    # Snippet should now include "world"
    assert "world" in st.exec_snippet
    assert st.exec_snippet != initial_snippet


def test_exec_log_no_reload_if_file_unchanged(controller):
    """Test that exec log is not reloaded if file hasn't changed"""
    state, ctl, tmp_path, queue, agent = controller

    result_path = tmp_path / "task_1_output.json"

    # Create initial log
    write_result(result_path, [
        {"type": "text", "text": "static content"}
    ])

    # First load
    ctl.refresh_tasks()
    ctl.load_selected_task_details()

    st = state.selected_task
    initial_snippet = st.exec_snippet
    initial_mtime = st.log_mtime
    initial_size = st.log_size

    # Simulate auto-refresh without file changes
    ctl.load_selected_task_details()

    # Metadata should be unchanged
    assert st.log_mtime == initial_mtime
    assert st.log_size == initial_size
    # Snippet should be the same object (no reload occurred)
    assert st.exec_snippet == initial_snippet


def test_exec_log_handles_json_errors_gracefully(controller):
    """Test that JSON parse errors don't crash, keep previous snippet"""
    state, ctl, tmp_path, queue, agent = controller

    result_path = tmp_path / "task_1_output.json"

    # Create valid initial log
    write_result(result_path, [
        {"type": "text", "text": "valid content"}
    ])

    # First load
    ctl.refresh_tasks()
    ctl.load_selected_task_details()

    st = state.selected_task
    valid_snippet = st.exec_snippet
    assert "valid" in valid_snippet

    # Corrupt the file (simulating mid-write)
    time.sleep(0.1)  # Increased from 0.01 for filesystem timestamp reliability
    Path(result_path).write_text("{invalid json")

    # Simulate auto-refresh
    ctl.load_selected_task_details()

    # Should keep the previous valid snippet, update metadata
    assert st.exec_snippet == valid_snippet  # keeps old snippet
    # Metadata should have changed (file modified)
    assert st.log_mtime is not None
    assert st.log_size is not None


def test_exec_log_loads_once_for_completed_task(controller):
    """Test that completed tasks only load exec log once"""
    state, ctl, tmp_path, queue, agent = controller
    from nightshift.core.task_queue import TaskStatus

    # Change task to COMPLETED
    task = queue.get_task("task_1")
    task.status = TaskStatus.COMPLETED.value

    result_path = tmp_path / "task_1_output.json"
    write_result(result_path, [
        {"type": "text", "text": "completed output"}
    ])

    # First load
    ctl.refresh_tasks()
    ctl.load_selected_task_details()

    st = state.selected_task
    initial_snippet = st.exec_snippet
    assert "completed" in initial_snippet or "output" in initial_snippet

    # Modify file
    time.sleep(0.1)  # Increased from 0.01 for filesystem timestamp reliability
    write_result(result_path, [
        {"type": "text", "text": "completed output"},
        {"type": "text", "text": "new line"},
    ])

    # Simulate auto-refresh
    ctl.load_selected_task_details()

    # Snippet should NOT have changed (completed tasks don't reload)
    assert st.exec_snippet == initial_snippet
    # "new line" should NOT appear
    assert "new line" not in st.exec_snippet


def test_exec_log_missing_result_path(controller):
    """Test handling of tasks with no result_path"""
    state, ctl, tmp_path, queue, agent = controller
    import types

    # Create task with no result_path
    task = types.SimpleNamespace(
        task_id="task_no_result",
        status="running",
        description="Task without result",
        created_at="2025-01-01T00:00:00",
        result_path=None,
    )
    task.to_dict = lambda: {
        "task_id": task.task_id,
        "status": task.status,
        "description": task.description,
        "created_at": task.created_at,
        "result_path": task.result_path,
    }

    # Add to queue
    queue._tasks["task_no_result"] = task

    # Select this task
    ctl.refresh_tasks()
    state.selected_index = 1  # Assuming it's second in list
    ctl.load_selected_task_details()

    st = state.selected_task
    assert st.task_id == "task_no_result"
    assert st.exec_snippet == ""
    assert st.log_mtime is None
    assert st.log_size is None


def test_exec_log_nonexistent_file(controller):
    """Test handling of tasks with result_path pointing to nonexistent file"""
    state, ctl, tmp_path, queue, agent = controller

    # Set result_path to nonexistent file
    task = queue.get_task("task_1")
    task.result_path = str(tmp_path / "nonexistent.json")
    task.to_dict = lambda: {
        "task_id": task.task_id,
        "status": task.status,
        "description": task.description,
        "created_at": task.created_at,
        "result_path": task.result_path,
    }

    ctl.refresh_tasks()
    ctl.load_selected_task_details()

    st = state.selected_task
    assert st.exec_snippet == ""
    assert st.log_mtime is None
    assert st.log_size is None


def test_exec_log_raw_tail_fallback(controller, monkeypatch):
    """Test raw tail fallback when format_exec_log_from_result returns empty"""
    state, ctl, tmp_path, queue, agent = controller

    result_path = tmp_path / "task_1_output.json"

    # Create stdout with plain text (not JSON events)
    plain_text = "\n".join([f"Plain line {i}" for i in range(50)])
    Path(result_path).write_text(json.dumps({"stdout": plain_text}))

    # Mock format_exec_log_from_result to return empty (simulating formatting failure)
    from nightshift.interfaces.tui import controllers

    original_format = controllers.format_exec_log_from_result

    def mock_format(*args, **kwargs):
        return ""

    monkeypatch.setattr(controllers, "format_exec_log_from_result", mock_format)

    # Load task
    ctl.refresh_tasks()
    ctl.load_selected_task_details()

    st = state.selected_task

    # Should have fallen back to raw tail (last 40 lines)
    assert st.exec_snippet != ""
    # Should contain lines from the tail (last 40 lines = lines 10-49)
    assert "Plain line 49" in st.exec_snippet


def test_exec_log_file_deleted_between_calls(controller):
    """Test handling when file is deleted between initial load and refresh"""
    state, ctl, tmp_path, queue, agent = controller

    result_path = tmp_path / "task_1_output.json"

    # Initial load with file present
    write_result(result_path, [
        {"type": "text", "text": "initial content"}
    ])

    ctl.refresh_tasks()
    ctl.load_selected_task_details()

    st = state.selected_task
    initial_snippet = st.exec_snippet
    assert "initial" in initial_snippet

    # Delete the file
    Path(result_path).unlink()

    # Simulate auto-refresh (same task, file now missing)
    ctl.load_selected_task_details()

    # Should keep previous snippet when file doesn't exist
    assert st.exec_snippet == initial_snippet
    # _maybe_reload_exec_snippet returns early when file doesn't exist,
    # preserving current snippet and returning (current_snippet, None, None)
