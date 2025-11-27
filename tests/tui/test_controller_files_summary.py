"""
Tests for controller file tracking and summary info loading
"""
import json
from pathlib import Path


def test_load_files_info(controller):
    """Test loading file changes info from _files.json"""
    state, ctl, tmp_path, queue, agent = controller

    # Create _files.json with expected format
    files_path = tmp_path / "task_1_files.json"
    files_data = {
        "changes": [
            {"path": "/path/to/new_file.py", "change_type": "created"},
            {"path": "/path/to/another.py", "change_type": "created"},
            {"path": "/path/to/existing.py", "change_type": "modified"},
            {"path": "/path/to/old_file.py", "change_type": "deleted"}
        ]
    }
    files_path.write_text(json.dumps(files_data))

    # Load task details
    ctl.refresh_tasks()
    ctl.load_selected_task_details()

    st = state.selected_task
    assert st.files_info is not None
    assert "/path/to/new_file.py" in st.files_info["created"]
    assert "/path/to/another.py" in st.files_info["created"]
    assert "/path/to/existing.py" in st.files_info["modified"]
    assert "/path/to/old_file.py" in st.files_info["deleted"]


def test_load_files_info_missing_file(controller):
    """Test handling when _files.json doesn't exist"""
    state, ctl, tmp_path, queue, agent = controller

    # Don't create _files.json

    ctl.refresh_tasks()
    ctl.load_selected_task_details()

    st = state.selected_task
    # Should be None when file doesn't exist
    assert st.files_info is None


def test_load_files_info_empty_sections(controller):
    """Test loading files info with empty sections"""
    state, ctl, tmp_path, queue, agent = controller

    # Create _files.json with expected format, only modified files
    files_path = tmp_path / "task_1_files.json"
    files_data = {
        "changes": [
            {"path": "/path/to/file.py", "change_type": "modified"}
        ]
    }
    files_path.write_text(json.dumps(files_data))

    ctl.refresh_tasks()
    ctl.load_selected_task_details()

    st = state.selected_task
    assert st.files_info is not None
    assert st.files_info["created"] == []
    assert "/path/to/file.py" in st.files_info["modified"]
    assert st.files_info["deleted"] == []


def test_load_summary_info(controller):
    """Test loading summary info from _notification.json"""
    state, ctl, tmp_path, queue, agent = controller

    # Create _notification.json
    notification_path = tmp_path / "task_1_notification.json"
    summary_data = {
        "task_id": "task_1",
        "status": "success",
        "description": "Test task",
        "claude_summary": "I completed the task successfully.",
        "execution_time": 15.5,
        "token_usage": 1234,
        "timestamp": "2025-01-01T12:00:00",
        "result_path": str(tmp_path / "task_1_output.json"),
        "error_message": None,
        "file_changes": {
            "created": ["/test.py"],
            "modified": [],
            "deleted": []
        }
    }
    notification_path.write_text(json.dumps(summary_data))

    # Load task details
    ctl.refresh_tasks()
    ctl.load_selected_task_details()

    st = state.selected_task
    assert st.summary_info is not None
    assert st.summary_info["status"] == "success"
    assert st.summary_info["claude_summary"] == "I completed the task successfully."
    assert st.summary_info["execution_time"] == 15.5
    assert st.summary_info["token_usage"] == 1234


def test_load_summary_info_missing_file(controller):
    """Test handling when _notification.json doesn't exist"""
    state, ctl, tmp_path, queue, agent = controller

    # Don't create _notification.json

    ctl.refresh_tasks()
    ctl.load_selected_task_details()

    st = state.selected_task
    # Should be None when file doesn't exist
    assert st.summary_info is None


def test_load_summary_info_with_claude_text_extraction(controller):
    """Test that claude_summary is populated from result_path if not in notification"""
    state, ctl, tmp_path, queue, agent = controller

    # Create result file with content_block_delta events
    result_path = tmp_path / "task_1_output.json"
    events = [
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Summary "}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "from result"}},
    ]
    stdout = "\n".join(json.dumps(e) for e in events)
    result_data = {"stdout": stdout}
    result_path.write_text(json.dumps(result_data))

    # Create notification without claude_summary
    notification_path = tmp_path / "task_1_notification.json"
    summary_data = {
        "task_id": "task_1",
        "status": "success",
        "result_path": str(result_path)
    }
    notification_path.write_text(json.dumps(summary_data))

    # Load task details
    ctl.refresh_tasks()
    ctl.load_selected_task_details()

    st = state.selected_task
    assert st.summary_info is not None
    # claude_summary should be populated from extract_claude_text_from_result
    assert st.summary_info.get("claude_summary") == "Summary from result"
