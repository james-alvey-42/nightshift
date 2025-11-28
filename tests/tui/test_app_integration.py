"""
Integration tests for TUI application with prompt_toolkit
Tests keybindings, command mode, and end-to-end UI behavior
"""
import types
import asyncio
import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.application import create_app_session


def make_task(task_id, status="running"):
    """Helper to create a dummy task object"""
    t = types.SimpleNamespace(
        task_id=task_id,
        status=status,
        description=f"Task {task_id}",
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


@pytest.mark.asyncio
async def test_j_k_navigation_moves_selection():
    """Test that j/k keybindings navigate task list up and down"""
    from nightshift.interfaces.tui.app import create_app_for_test

    tasks = [make_task(f"task_{i}") for i in range(3)]

    with create_pipe_input() as pipe_input:
        with create_app_session(input=pipe_input):
            app, state, *_ = create_app_for_test(tasks=tasks)

            # Initial state: selected_index should be 0
            assert state.selected_index == 0

            async def drive_keys():
                # Simulate key presses: j, j, k
                pipe_input.send_text("j")  # Move down to index 1
                await asyncio.sleep(0.01)
                pipe_input.send_text("j")  # Move down to index 2
                await asyncio.sleep(0.01)
                pipe_input.send_text("k")  # Move up to index 1
                await asyncio.sleep(0.01)
                pipe_input.send_text("q")  # Quit

            asyncio.create_task(drive_keys())

            # Run app with timeout to prevent hangs
            await asyncio.wait_for(app.run_async(), timeout=1.0)

        # After j, j, k sequence, should be at index 1
        assert state.selected_index == 1


@pytest.mark.asyncio
async def test_tab_switching_via_number_keys():
    """Test that 1-4 keybindings switch detail tabs"""
    from nightshift.interfaces.tui.app import create_app_for_test

    tasks = [make_task("task_1")]

    with create_pipe_input() as pipe_input:
        with create_app_session(input=pipe_input):
            app, state, *_ = create_app_for_test(tasks=tasks)

            # Initial tab should be overview
            assert state.detail_tab == "overview"

            async def drive_keys():
                # Switch tabs: 2 -> exec, 3 -> files, 4 -> summary, 1 -> overview
                pipe_input.send_text("2")  # Switch to exec tab
                await asyncio.sleep(0.01)
                assert state.detail_tab == "exec"

                pipe_input.send_text("3")  # Switch to files tab
                await asyncio.sleep(0.01)
                assert state.detail_tab == "files"

                pipe_input.send_text("4")  # Switch to summary tab
                await asyncio.sleep(0.01)
                assert state.detail_tab == "summary"

                pipe_input.send_text("1")  # Switch back to overview
                await asyncio.sleep(0.01)
                assert state.detail_tab == "overview"

                pipe_input.send_text("q")  # Quit

            asyncio.create_task(drive_keys())
            await asyncio.wait_for(app.run_async(), timeout=1.0)

        # Final state should be overview
        assert state.detail_tab == "overview"


@pytest.mark.asyncio
async def test_command_mode_toggle_and_help():
    """Test that : enters command mode and :help executes"""
    from nightshift.interfaces.tui.app import create_app_for_test

    tasks = [make_task("task_1")]

    with create_pipe_input() as pipe_input:
        with create_app_session(input=pipe_input):
            app, state, *_ = create_app_for_test(tasks=tasks)

            # Initially not in command mode
            assert not state.command_active

            async def drive_keys():
                # Enter command mode
                pipe_input.send_text(":")
                await asyncio.sleep(0.01)
                assert state.command_active

                # Type "help" and press Enter
                pipe_input.send_text("h")
                pipe_input.send_text("e")
                pipe_input.send_text("l")
                pipe_input.send_text("p")
                pipe_input.send_text("\r")  # Enter key
                await asyncio.sleep(0.01)

                # Command mode should be deactivated
                assert not state.command_active

                # Help message should be in state.message
                assert "Commands:" in state.message
                assert ":queue" in state.message

                pipe_input.send_text("q")  # Quit

            asyncio.create_task(drive_keys())
            await asyncio.wait_for(app.run_async(), timeout=1.0)

        # Verify final state
        assert not state.command_active
        assert "Commands:" in state.message


@pytest.mark.asyncio
async def test_queue_filter_command():
    """Test that :queue <status> filters task list"""
    from nightshift.interfaces.tui.app import create_app_for_test

    # Create tasks with mixed statuses
    tasks = [
        make_task("task_1", status="running"),
        make_task("task_2", status="running"),
        make_task("task_3", status="staged"),
        make_task("task_4", status="failed"),
    ]

    with create_pipe_input() as pipe_input:
        with create_app_session(input=pipe_input):
            app, state, *_ = create_app_for_test(tasks=tasks)

            # Initially should show all tasks
            assert len(state.tasks) == 4
            assert state.status_filter is None

            async def drive_keys():
                # Filter to running tasks: ":queue running"
                pipe_input.send_text(":")
                pipe_input.send_text("q")
                pipe_input.send_text("u")
                pipe_input.send_text("e")
                pipe_input.send_text("u")
                pipe_input.send_text("e")
                pipe_input.send_text(" ")
                pipe_input.send_text("r")
                pipe_input.send_text("u")
                pipe_input.send_text("n")
                pipe_input.send_text("n")
                pipe_input.send_text("i")
                pipe_input.send_text("n")
                pipe_input.send_text("g")
                pipe_input.send_text("\r")  # Enter
                await asyncio.sleep(0.01)

                # Should now show only running tasks
                assert state.status_filter == "running"
                assert len(state.tasks) == 2
                assert all(row.status == "running" for row in state.tasks)

                pipe_input.send_text("q")  # Quit

            asyncio.create_task(drive_keys())
            await asyncio.wait_for(app.run_async(), timeout=1.0)

        # Verify filter is applied
        assert state.status_filter == "running"
        assert len(state.tasks) == 2
