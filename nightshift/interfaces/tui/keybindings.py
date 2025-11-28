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


def create_keybindings(state: UIState, controller, cmd_widget) -> KeyBindings:
    """Create keybindings for the TUI"""
    kb = KeyBindings()
    cmd_buffer = cmd_widget.buffer

    # Define mode filters once
    is_command_mode = Condition(lambda: state.command_active)
    is_normal_mode = ~is_command_mode

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

    @kb.add('2', filter=is_normal_mode)
    def _(event):
        """Switch to exec tab"""
        state.detail_tab = "exec"

    @kb.add('3', filter=is_normal_mode)
    def _(event):
        """Switch to files tab"""
        state.detail_tab = "files"

    @kb.add('4', filter=is_normal_mode)
    def _(event):
        """Switch to summary tab"""
        state.detail_tab = "summary"

    # h/l for prev/next tab
    @kb.add('h', filter=is_normal_mode)
    def _(event):
        """Previous tab"""
        tabs = ["overview", "exec", "files", "summary"]
        current_idx = tabs.index(state.detail_tab)
        state.detail_tab = tabs[(current_idx - 1) % len(tabs)]

    @kb.add('l', filter=is_normal_mode)
    def _(event):
        """Next tab"""
        tabs = ["overview", "exec", "files", "summary"]
        current_idx = tabs.index(state.detail_tab)
        state.detail_tab = tabs[(current_idx + 1) % len(tabs)]

    # Quit
    @kb.add('q', filter=is_normal_mode)
    def _(event):
        """Quit the TUI"""
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
            # Create temporary file with helpful template
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
                f.write("\n\n")
                f.write("# Describe your task above (lines starting with # are ignored)\n")
                f.write("# Save and quit (:wq) to submit, or quit without saving (:q!) to cancel\n")
                temp_path = f.name

            # Open editor (respects $EDITOR, defaults to vim)
            editor = os.environ.get('EDITOR', 'vim')
            subprocess.run([editor, temp_path], check=False)

            # Read the content
            with open(temp_path, 'r') as f:
                lines = f.readlines()

            # Filter out comments and empty lines
            desc_lines = [line for line in lines if line.strip() and not line.strip().startswith('#')]
            desc = ''.join(desc_lines).strip()

            Path(temp_path).unlink()

            if desc:
                controller.submit_task(desc, auto_approve=False)
            else:
                state.message = "Submit cancelled: empty description"

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
