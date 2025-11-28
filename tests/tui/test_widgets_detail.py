"""
Tests for DetailControl widget rendering
"""
from nightshift.interfaces.tui.models import UIState, SelectedTaskState
from nightshift.interfaces.tui.widgets import DetailControl


def test_detail_no_task_selected():
    """Test rendering when no task is selected"""
    state = UIState()
    state.detail_tab = "overview"

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)
    assert "No task selected" in text


def test_detail_overview_tab_basic():
    """Test overview tab with basic task details"""
    state = UIState()
    state.detail_tab = "overview"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {
        "task_id": "task_1",
        "status": "RUNNING",
        "description": "Test task description",
        "created_at": "2025-01-01T12:00:00",
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    # Should show task ID, status, description, timestamps
    assert "task_1" in text
    assert "RUNNING" in text or "⏳" in text
    assert "Test task description" in text
    assert "Created:" in text
    assert "2025-01-01" in text


def test_detail_overview_tab_with_timestamps():
    """Test overview tab shows all timestamps for completed task"""
    state = UIState()
    state.detail_tab = "overview"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {
        "task_id": "task_1",
        "status": "COMPLETED",
        "description": "Completed task",
        "created_at": "2025-01-01T12:00:00",
        "started_at": "2025-01-01T12:05:00",
        "completed_at": "2025-01-01T12:10:00",
        "execution_time": 300.5,
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    assert "Started:" in text
    assert "Completed:" in text
    assert "Execution Time:" in text
    assert "300.5s" in text


def test_detail_overview_tab_with_error():
    """Test overview tab shows error message for failed tasks"""
    state = UIState()
    state.detail_tab = "overview"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {
        "task_id": "task_1",
        "status": "FAILED",
        "description": "Failed task",
        "created_at": "2025-01-01T12:00:00",
        "error_message": "Task execution failed due to timeout",
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    assert "Error:" in text or "error" in text.lower()
    assert "timeout" in text.lower()


def test_detail_overview_tab_with_allowed_tools():
    """Test overview tab shows allowed tools"""
    state = UIState()
    state.detail_tab = "overview"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {
        "task_id": "task_1",
        "status": "STAGED",
        "description": "Task with tools",
        "created_at": "2025-01-01T12:00:00",
        "allowed_tools": ["Read", "Write", "Bash"],
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    assert "Allowed Tools:" in text
    assert "Read" in text
    assert "Write" in text
    assert "Bash" in text


def test_detail_exec_tab_with_log():
    """Test exec tab renders execution log"""
    state = UIState()
    state.detail_tab = "exec"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "running"}
    st.exec_snippet = "🔧 Read:\n  file_path: /test.py\n\nHello from Claude"

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    assert "Execution Log" in text or "📋" in text
    assert "Read" in text
    assert "file_path" in text
    assert "Hello from Claude" in text


def test_detail_exec_tab_empty():
    """Test exec tab when no execution log available"""
    state = UIState()
    state.detail_tab = "exec"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "staged"}
    st.exec_snippet = ""

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    assert "No execution log available" in text


def test_detail_exec_tab_styling():
    """Test exec tab applies styling to different log elements"""
    state = UIState()
    state.detail_tab = "exec"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "running"}
    st.exec_snippet = "🔧 Tool call\n  arg: value\n✅ Success message"

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    # Tool calls should use dim styling
    tool_fragments = [(style, text) for style, text in fragments if "🔧" in text]
    assert any("dim" in style.lower() for style, _ in tool_fragments)

    # Success messages should use green styling
    success_fragments = [(style, text) for style, text in fragments if "✅" in text]
    assert any("green" in style.lower() for style, _ in success_fragments)


def test_detail_files_tab_with_changes():
    """Test files tab renders file changes"""
    state = UIState()
    state.detail_tab = "files"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "completed"}
    st.files_info = {
        "created": ["/path/to/new_file.py", "/path/to/another.py"],
        "modified": ["/path/to/existing.py"],
        "deleted": ["/path/to/old_file.py"]
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    assert "File Changes" in text or "📁" in text
    assert "Created" in text
    assert "new_file.py" in text
    assert "Modified" in text
    assert "existing.py" in text
    assert "Deleted" in text
    assert "old_file.py" in text


def test_detail_files_tab_empty():
    """Test files tab when no file changes"""
    state = UIState()
    state.detail_tab = "files"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "completed"}
    st.files_info = None

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    assert "no file changes" in text.lower()


def test_detail_files_tab_shows_all_files():
    """Test files tab shows all files (scrolling handles long lists)"""
    state = UIState()
    state.detail_tab = "files"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "completed"}
    # Create many files
    st.files_info = {
        "created": [f"/file_{i}.py" for i in range(30)],
        "modified": [],
        "deleted": []
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    # Should show all files (no truncation - scrolling handles it)
    assert "/file_0.py" in text
    assert "/file_29.py" in text


def test_detail_summary_tab_success():
    """Test summary tab for successful task"""
    state = UIState()
    state.detail_tab = "summary"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "completed"}
    st.summary_info = {
        "task_id": "task_1",
        "status": "success",
        "description": "Task description",
        "claude_summary": "I successfully completed the task.",
        "execution_time": 15.5,
        "token_usage": 1234,
        "timestamp": "2025-01-01T12:00:00",
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    assert "Task Summary" in text or "📊" in text
    assert "SUCCESS" in text or "✅" in text
    assert "Task description" in text
    assert "successfully completed" in text
    assert "15.5s" in text
    assert "1234" in text


def test_detail_summary_tab_failed():
    """Test summary tab for failed task with error"""
    state = UIState()
    state.detail_tab = "summary"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "failed"}
    st.summary_info = {
        "task_id": "task_1",
        "status": "failed",
        "description": "Task that failed",
        "error_message": "Connection timeout after 30 seconds",
        "execution_time": 30.0,
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    assert "FAILED" in text or "❌" in text
    assert "Error Details" in text or "error" in text.lower()
    assert "timeout" in text.lower()


def test_detail_summary_tab_with_file_changes():
    """Test summary tab shows file changes summary"""
    state = UIState()
    state.detail_tab = "summary"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "completed"}
    st.summary_info = {
        "task_id": "task_1",
        "status": "success",
        "description": "Task with files",
        "file_changes": {
            "created": ["/new1.py", "/new2.py"],
            "modified": ["/modified.py"],
            "deleted": []
        }
    }
    # Also set files_info as fallback
    st.files_info = st.summary_info["file_changes"]

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    assert "What NightShift did" in text or "did" in text.lower()
    assert "Created" in text
    assert "Modified" in text


def test_detail_summary_tab_empty():
    """Test summary tab when no summary available"""
    state = UIState()
    state.detail_tab = "summary"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "running"}
    st.summary_info = None

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    assert "No summary available" in text


def test_detail_tab_switching():
    """Test that changing tabs renders different content"""
    state = UIState()
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "running", "description": "Test"}
    st.exec_snippet = "Execution log content"

    ctrl = DetailControl(state)

    # Overview tab
    state.detail_tab = "overview"
    overview_text = "".join(t for _, t in ctrl.get_text())

    # Exec tab
    state.detail_tab = "exec"
    exec_text = "".join(t for _, t in ctrl.get_text())

    # Content should be different
    assert overview_text != exec_text
    assert "Execution log content" in exec_text
    assert "Execution log content" not in overview_text


def test_detail_overview_status_emoji_and_color():
    """Test that overview tab shows correct emoji and color for different statuses"""
    state = UIState()
    state.detail_tab = "overview"
    st = state.selected_task
    st.task_id = "task_1"

    # Test COMPLETED status
    st.details = {
        "task_id": "task_1",
        "status": "COMPLETED",
        "description": "Completed task",
        "created_at": "2025-01-01T12:00:00",
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()
    text = "".join(t for _, t in fragments)
    styles = [style for style, _ in fragments]

    # Should show checkmark emoji and green color
    assert "✅" in text
    assert any("green" in s for s in styles)

    # Test FAILED status
    st.details["status"] = "FAILED"
    fragments = ctrl.get_text()
    text = "".join(t for _, t in fragments)
    styles = [style for style, _ in fragments]

    # Should show X emoji and red color
    assert "❌" in text
    assert any("red" in s for s in styles)

    # Test RUNNING status
    st.details["status"] = "RUNNING"
    fragments = ctrl.get_text()
    text = "".join(t for _, t in fragments)
    styles = [style for style, _ in fragments]

    # Should show hourglass emoji and cyan color
    assert "⏳" in text
    assert any("cyan" in s for s in styles)


def test_detail_overview_system_prompt_truncation():
    """Test that long system prompts are truncated in overview"""
    state = UIState()
    state.detail_tab = "overview"
    st = state.selected_task
    st.task_id = "task_1"

    # Create a system prompt longer than 500 chars
    long_prompt = "A" * 600
    st.details = {
        "task_id": "task_1",
        "status": "STAGED",
        "description": "Task with long system prompt",
        "created_at": "2025-01-01T12:00:00",
        "system_prompt": long_prompt,
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()
    text = "".join(t for _, t in fragments)

    # Should show truncation
    assert "..." in text
    # Full prompt should not be present
    assert long_prompt not in text


def test_detail_overview_sandbox_section():
    """Test that sandbox section displays with allowed_directories and needs_git"""
    state = UIState()
    state.detail_tab = "overview"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {
        "task_id": "task_1",
        "status": "STAGED",
        "description": "Task with sandbox",
        "created_at": "2025-01-01T12:00:00",
        "allowed_directories": ["/path/to/dir1", "/path/to/dir2"],
        "needs_git": True,
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()
    text = "".join(t for _, t in fragments)

    # Should show sandbox section
    assert "Sandbox" in text or "write access" in text.lower()
    assert "needs_git" in text.lower() or "True" in text
    assert "/path/to/dir1" in text


def test_detail_exec_arg_key_style():
    """Test that exec tab uses class:arg-key for argument keys"""
    state = UIState()
    state.detail_tab = "exec"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "running"}
    st.exec_snippet = "🔧 Read:\n  file_path: /test.py"

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()

    # Find fragments containing "file_path"
    arg_fragments = [(style, text) for style, text in fragments if "file_path" in text]

    # Should have arg-key style
    assert any("arg-key" in style for style, _ in arg_fragments)


def test_detail_files_section_specific_styles():
    """Test that files tab uses specific style classes for created/modified/deleted"""
    state = UIState()
    state.detail_tab = "files"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "completed"}
    st.files_info = {
        "created": ["/new_file.py"],
        "modified": ["/existing.py"],
        "deleted": ["/old_file.py"]
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()
    styles = [style for style, _ in fragments]

    # Should have file-created, file-modified, file-deleted classes
    assert any("file-created" in s for s in styles)
    assert any("file-modified" in s for s in styles)
    assert any("file-deleted" in s for s in styles)


def test_detail_summary_status_variants():
    """Test summary tab renders various status variants correctly"""
    state = UIState()
    state.detail_tab = "summary"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1"}

    # Test cancelled status
    st.summary_info = {
        "task_id": "task_1",
        "status": "cancelled",
        "description": "Cancelled task",
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()
    text = "".join(t for _, t in fragments)

    # Should show cancelled emoji
    assert "🚫" in text

    # Test running status
    st.summary_info["status"] = "running"
    fragments = ctrl.get_text()
    text = "".join(t for _, t in fragments)

    # Should show running emoji
    assert "⏳" in text

    # Test unknown status
    st.summary_info["status"] = "weird_unknown_status"
    fragments = ctrl.get_text()
    text = "".join(t for _, t in fragments)

    # Should show unknown emoji
    assert "❓" in text


def test_detail_summary_error_codeblock_style():
    """Test that summary tab uses class:error-codeblock for error display"""
    state = UIState()
    state.detail_tab = "summary"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "failed"}
    st.summary_info = {
        "task_id": "task_1",
        "status": "failed",
        "description": "Failed task",
        "error_message": "Something went wrong",
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()
    styles = [style for style, text in fragments if "Something went wrong" in text or "┌─" in text or "│" in text]

    # Should have error-codeblock style
    assert any("error-codeblock" in s for s in styles)


def test_detail_summary_shows_full_content():
    """Test that summary tab shows full claude_summary (scrolling handles long content)"""
    state = UIState()
    state.detail_tab = "summary"
    st = state.selected_task
    st.task_id = "task_1"
    st.details = {"task_id": "task_1", "status": "completed"}

    # Create long summary with recognizable content
    long_summary = "START_MARKER " + "content " * 200 + "END_MARKER"

    st.summary_info = {
        "task_id": "task_1",
        "status": "success",
        "description": "Short description",
        "claude_summary": long_summary,
    }

    ctrl = DetailControl(state)
    fragments = ctrl.get_text()
    text = "".join(t for _, t in fragments)

    # Should show full summary content (scrolling handles it)
    assert "START_MARKER" in text
    assert "END_MARKER" in text
