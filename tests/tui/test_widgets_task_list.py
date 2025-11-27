"""
Tests for TaskListControl widget rendering
"""
from nightshift.interfaces.tui.models import UIState, TaskRow
from nightshift.interfaces.tui.widgets import TaskListControl


def test_task_list_empty():
    """Test rendering of empty task list"""
    state = UIState()
    state.tasks = []

    ctrl = TaskListControl(state)
    fragments = ctrl.get_text()

    # Should show "No tasks" message
    text = "".join(t for _, t in fragments)
    assert "No tasks" in text


def test_task_list_single_task():
    """Test rendering of single task"""
    state = UIState()
    state.tasks = [
        TaskRow(
            task_id="task_1",
            status="running",
            description="Test task",
            created_at="2025-01-01T12:00:00",
            status_emoji="⏳",
            status_color="cyan"
        )
    ]
    state.selected_index = 0

    ctrl = TaskListControl(state)
    fragments = ctrl.get_text()

    # Extract text
    text = "".join(t for _, t in fragments)

    # Should contain task ID, emoji, and description
    assert "task_1" in text
    assert "⏳" in text
    assert "Test task" in text
    assert "2025-01-01" in text


def test_task_list_multiple_tasks():
    """Test rendering of multiple tasks"""
    state = UIState()
    state.tasks = [
        TaskRow(
            task_id="task_1",
            status="completed",
            description="First task",
            created_at="2025-01-01T12:00:00",
            status_emoji="✅",
            status_color="green"
        ),
        TaskRow(
            task_id="task_2",
            status="failed",
            description="Second task",
            created_at="2025-01-02T12:00:00",
            status_emoji="❌",
            status_color="red"
        ),
        TaskRow(
            task_id="task_3",
            status="staged",
            description="Third task",
            created_at="2025-01-03T12:00:00",
            status_emoji="📝",
            status_color="orange"
        )
    ]
    state.selected_index = 1

    ctrl = TaskListControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    # All tasks should be present
    assert "task_1" in text
    assert "task_2" in text
    assert "task_3" in text
    assert "✅" in text
    assert "❌" in text
    assert "📝" in text


def test_task_list_selection_styling():
    """Test that selected task has reverse styling"""
    state = UIState()
    state.tasks = [
        TaskRow(
            task_id="task_1",
            status="running",
            description="Unselected",
            created_at="2025-01-01T12:00:00",
            status_emoji="⏳",
            status_color="cyan"
        ),
        TaskRow(
            task_id="task_2",
            status="completed",
            description="Selected",
            created_at="2025-01-02T12:00:00",
            status_emoji="✅",
            status_color="green"
        )
    ]
    state.selected_index = 1

    ctrl = TaskListControl(state)
    fragments = ctrl.get_text()

    # Find selected task fragment
    selected_fragments = [
        (style, text) for style, text in fragments
        if "task_2" in text
    ]

    assert len(selected_fragments) > 0
    # Selected task should have "reverse" in its style
    assert any("reverse" in style for style, _ in selected_fragments)


def test_task_list_long_description_truncation():
    """Test that long descriptions are truncated"""
    state = UIState()
    long_desc = "A" * 100  # 100 character description
    state.tasks = [
        TaskRow(
            task_id="task_1",
            status="running",
            description=long_desc,
            created_at="2025-01-01T12:00:00",
            status_emoji="⏳",
            status_color="cyan"
        )
    ]
    state.selected_index = 0

    ctrl = TaskListControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    # Description should be truncated with "..."
    assert "..." in text
    # Full description should NOT be present
    assert long_desc not in text


def test_task_list_status_colors():
    """Test that different statuses use correct colors"""
    state = UIState()
    state.tasks = [
        TaskRow(
            task_id="task_staged",
            status="staged",
            description="Staged",
            created_at="2025-01-01T12:00:00",
            status_emoji="📝",
            status_color="orange"
        ),
        TaskRow(
            task_id="task_running",
            status="running",
            description="Running",
            created_at="2025-01-01T12:00:00",
            status_emoji="⏳",
            status_color="cyan"
        ),
        TaskRow(
            task_id="task_completed",
            status="completed",
            description="Completed",
            created_at="2025-01-01T12:00:00",
            status_emoji="✅",
            status_color="green"
        ),
        TaskRow(
            task_id="task_failed",
            status="failed",
            description="Failed",
            created_at="2025-01-01T12:00:00",
            status_emoji="❌",
            status_color="red"
        )
    ]

    ctrl = TaskListControl(state)
    fragments = ctrl.get_text()

    # Check that status colors appear in fragments
    styles = [style for style, _ in fragments]
    assert any("orange" in s for s in styles)
    assert any("cyan" in s for s in styles)
    assert any("green" in s for s in styles)
    assert any("red" in s for s in styles)


def test_task_list_missing_created_at():
    """Test handling of tasks without created_at"""
    state = UIState()
    state.tasks = [
        TaskRow(
            task_id="task_1",
            status="running",
            description="No timestamp",
            created_at=None,
            status_emoji="⏳",
            status_color="cyan"
        )
    ]
    state.selected_index = 0

    ctrl = TaskListControl(state)
    fragments = ctrl.get_text()

    text = "".join(t for _, t in fragments)

    # Should still render without crashing
    assert "task_1" in text
    assert "No timestamp" in text
