"""
TUI Keybindings
Vi-style keymaps for NightShift
"""
import os
import tempfile
import subprocess
from pathlib import Path
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition
from prompt_toolkit.application.current import get_app
from prompt_toolkit.application import run_in_terminal
from .models import UIState


def create_keybindings(state: UIState, controller, cmd_widget, detail_window=None) -> KeyBindings:
    """Create keybindings for the TUI

    Args:
        state: UI state
        controller: TUI controller
        cmd_widget: Command line widget
        detail_window: Detail panel Window (for scroll render_info)
    """
    kb = KeyBindings()
    cmd_buffer = cmd_widget.buffer
    logger = controller.logger  # Get logger from controller for error logging

    # Define mode filters once
    is_command_mode = Condition(lambda: state.command_active)
    is_normal_mode = ~is_command_mode

    def get_page_size():
        """Get page size from render_info, or default"""
        if detail_window and detail_window.render_info:
            return max(10, detail_window.render_info.window_height - 2)
        return 40

    # Movement: j/k and arrow keys for up/down navigation
    @kb.add('j', filter=is_normal_mode)
    @kb.add('down', filter=is_normal_mode)
    def _(event):
        """Move selection down"""
        if state.selected_index < len(state.tasks) - 1:
            state.selected_index += 1
            controller.load_selected_task_details()

    @kb.add('k', filter=is_normal_mode)
    @kb.add('up', filter=is_normal_mode)
    def _(event):
        """Move selection up"""
        if state.selected_index > 0:
            state.selected_index -= 1
            controller.load_selected_task_details()

    # Jump to first/last
    @kb.add('g', filter=is_normal_mode)
    def _(event):
        """Jump to first task"""
        state.selected_index = 0
        controller.load_selected_task_details()

    @kb.add('G', filter=is_normal_mode)
    def _(event):
        """Jump to last task"""
        state.selected_index = len(state.tasks) - 1
        controller.load_selected_task_details()

    # Tab switching: 1-4 for direct tab access
    @kb.add('1', filter=is_normal_mode)
    def _(event):
        """Switch to overview tab"""
        state.detail_tab = "overview"
        state.detail_scroll_offset = 0

    @kb.add('2', filter=is_normal_mode)
    def _(event):
        """Switch to exec tab"""
        state.detail_tab = "exec"
        state.detail_scroll_offset = 0

    @kb.add('3', filter=is_normal_mode)
    def _(event):
        """Switch to files tab"""
        state.detail_tab = "files"
        state.detail_scroll_offset = 0

    @kb.add('4', filter=is_normal_mode)
    def _(event):
        """Switch to summary tab"""
        state.detail_tab = "summary"
        state.detail_scroll_offset = 0

    # h/l for prev/next tab
    @kb.add('h', filter=is_normal_mode)
    def _(event):
        """Previous tab"""
        tabs = ["overview", "exec", "files", "summary"]
        current_idx = tabs.index(state.detail_tab)
        state.detail_tab = tabs[(current_idx - 1) % len(tabs)]
        state.detail_scroll_offset = 0

    @kb.add('l', filter=is_normal_mode)
    def _(event):
        """Next tab"""
        tabs = ["overview", "exec", "files", "summary"]
        current_idx = tabs.index(state.detail_tab)
        state.detail_tab = tabs[(current_idx + 1) % len(tabs)]
        state.detail_scroll_offset = 0

    # Detail panel scrolling (clamping handled by DetailControl on next render)
    @kb.add('c-d', filter=is_normal_mode)
    def _(event):
        """Scroll detail panel down (half page)"""
        half_page = max(1, get_page_size() // 2)
        state.detail_scroll_offset += half_page
        get_app().invalidate()

    @kb.add('c-u', filter=is_normal_mode)
    def _(event):
        """Scroll detail panel up (half page)"""
        half_page = max(1, get_page_size() // 2)
        state.detail_scroll_offset -= half_page
        if state.detail_scroll_offset < 0:
            state.detail_scroll_offset = 0
        get_app().invalidate()

    @kb.add('c-f', filter=is_normal_mode)
    @kb.add('pagedown', filter=is_normal_mode)
    def _(event):
        """Scroll detail panel down (full page)"""
        page = max(1, get_page_size() - 2)  # leave 2 lines overlap
        state.detail_scroll_offset += page
        get_app().invalidate()

    @kb.add('c-b', filter=is_normal_mode)
    @kb.add('pageup', filter=is_normal_mode)
    def _(event):
        """Scroll detail panel up (full page)"""
        page = max(1, get_page_size() - 2)
        state.detail_scroll_offset -= page
        if state.detail_scroll_offset < 0:
            state.detail_scroll_offset = 0
        get_app().invalidate()

    @kb.add('c-g', filter=is_normal_mode)
    def _(event):
        """Scroll to top of detail panel"""
        state.detail_scroll_offset = 0
        get_app().invalidate()

    @kb.add('c-e', filter=is_normal_mode)
    def _(event):
        """Scroll to bottom of detail panel"""
        # Set to large value; DetailControl will clamp on render
        state.detail_scroll_offset = 999999
        get_app().invalidate()

    # Open current content in pager
    @kb.add('o', filter=is_normal_mode)
    def _(event):
        """Open current tab content in $PAGER"""
        controller.open_in_pager()

    # Open scratch directory in terminal/finder
    @kb.add('O', filter=is_normal_mode)
    def _(event):
        """Open scratch directory in file explorer or terminal"""
        def open_scratch():
            try:
                task = state.selected_task
                if not task.details:
                    state.message = "No task selected"
                    logger.debug("TUI: Open scratch - no task selected")
                    return

                use_scratch = task.details.get('use_scratch', True)
                if not use_scratch:
                    state.message = "Task not using scratch directory"
                    logger.debug(f"TUI: Task {task.details.get('task_id')} not using scratch")
                    return

                task_id = task.details.get('task_id')
                scratch_path = Path.home() / ".nightshift" / "worktrees" / task_id

                if not scratch_path.exists():
                    state.message = f"Scratch directory doesn't exist: {scratch_path}"
                    logger.warning(f"TUI: Scratch directory not found: {scratch_path}")
                    return

                # Try to open in file explorer or terminal
                import platform
                system = platform.system()

                if system == "Darwin":  # macOS
                    # Open in Finder
                    subprocess.run(["open", str(scratch_path)], check=False)
                    state.message = f"Opened in Finder: {scratch_path.name}"
                    logger.info(f"TUI: Opened scratch in Finder: {scratch_path}")
                elif system == "Linux":
                    # Try to open in default file manager
                    subprocess.run(["xdg-open", str(scratch_path)], check=False)
                    state.message = f"Opened: {scratch_path.name}"
                    logger.info(f"TUI: Opened scratch: {scratch_path}")
                else:
                    # Fallback: open terminal in that directory
                    state.message = f"Scratch: {scratch_path}"
                    logger.info(f"TUI: Scratch path: {scratch_path}")
            except Exception as e:
                state.message = f"Error opening scratch dir: {e}"
                logger.error(f"TUI: Failed to open scratch directory: {e}")

            get_app().invalidate()

        run_in_terminal(open_scratch)

    # Quit
    @kb.add('q', filter=is_normal_mode)
    def _(event):
        """Quit the TUI"""
        logger.info("TUI: User quit application")
        event.app.exit()

    # Refresh (R key is more reliable than c-l which terminals often intercept)
    @kb.add('R', filter=is_normal_mode)
    @kb.add('c-l', filter=is_normal_mode)
    def _(event):
        """Hard refresh from backend"""
        controller.refresh_tasks()
        state.message = "Refreshed"
        get_app().invalidate()

    # Phase 3: Task actions
    # Approve selected STAGED task
    @kb.add('a', filter=is_normal_mode)
    def _(event):
        """Approve selected task"""
        controller.approve_selected_task()
        get_app().invalidate()

    # Review/revise selected STAGED task
    @kb.add('r', filter=is_normal_mode)
    def _(event):
        """Review/revise selected task"""
        controller.review_selected_task()
        get_app().invalidate()

    # Cancel selected task
    @kb.add('c', filter=is_normal_mode)
    def _(event):
        """Cancel selected task"""
        controller.reject_selected_task()
        get_app().invalidate()

    # Pause running task
    @kb.add('p', filter=is_normal_mode)
    def _(event):
        """Pause selected running task"""
        controller.pause_selected_task()
        get_app().invalidate()

    # Resume paused task
    @kb.add('P', filter=is_normal_mode)
    def _(event):
        """Resume selected paused task"""
        controller.resume_selected_task()
        get_app().invalidate()

    # Kill running/paused task
    @kb.add('X', filter=is_normal_mode)
    def _(event):
        """Kill selected running/paused task"""
        controller.kill_selected_task()
        get_app().invalidate()

    # Delete task
    @kb.add('d', filter=is_normal_mode)
    def _(event):
        """Delete selected task"""
        controller.delete_selected_task()
        get_app().invalidate()

    # Submit new task (vim editor)
    @kb.add('s', filter=is_normal_mode)
    def _(event):
        """
        Submit new task.
        Opens vim to edit task description,
        then calls controller.submit_task().
        """
        def open_vim_and_submit():
            try:
                # Create temporary file with helpful template
                with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                    f.write("\n\n")
                    f.write("# Describe your task above (lines starting with # are ignored)\n")
                    f.write("# Save and quit (:wq) to submit, or quit without saving (:q!) to cancel\n")
                    temp_path = f.name

                # Open editor (respects $EDITOR, defaults to vim)
                editor = os.environ.get('EDITOR', 'vim')
                logger.debug(f"TUI: Opening editor {editor} for task submission")
                subprocess.run([editor, temp_path], check=False)

                # Read the content
                with open(temp_path, 'r') as f:
                    lines = f.readlines()

                # Filter out comments and empty lines
                desc_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
                desc = ''.join(desc_lines).strip()

                Path(temp_path).unlink()

                if desc:
                    logger.info(f"TUI: Submitting new task from editor: {desc[:50]}...")
                    controller.submit_task(desc, auto_approve=False)
                else:
                    state.message = "Submit cancelled: empty description"
                    logger.debug("TUI: Task submission cancelled - empty description")

            except Exception as e:
                state.message = f"Error submitting task: {e}"
                logger.error(f"TUI: Failed to submit task from editor: {e}")

            get_app().invalidate()

        run_in_terminal(open_vim_and_submit)

    # Command mode: enter with :
    @kb.add(':', filter=is_normal_mode)
    def _(event):
        """Enter command mode"""
        state.command_active = True
        cmd_buffer.text = ""
        get_app().layout.focus(cmd_widget)
        get_app().invalidate()

    # Command buffer: execute command on Enter
    @kb.add('enter', filter=is_command_mode)
    def _(event):
        """Execute command"""
        line = cmd_buffer.text
        state.command_active = False
        cmd_buffer.text = ""

        # Execute command via controller
        if line:
            controller.execute_command(line)

        # Return focus to main UI
        get_app().layout.focus_previous()

    # Command buffer: cancel on Escape
    @kb.add('escape', filter=is_command_mode)
    def _(event):
        """Cancel command mode"""
        state.command_active = False
        cmd_buffer.text = ""
        # Return focus to main UI
        get_app().layout.focus_previous()

    return kb
