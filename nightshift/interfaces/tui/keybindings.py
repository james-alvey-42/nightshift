"""
TUI Keybindings
Vi-style keymaps for NightShift
"""
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import Condition
from prompt_toolkit.application.current import get_app
from prompt_toolkit.shortcuts import input_dialog
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
        if state.tasks:
            state.selected_index = 0
            controller.load_selected_task_details()

    @kb.add('G', filter=is_normal_mode)
    def _(event):
        """Jump to last task"""
        if state.tasks:
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

    # H/L for prev/next tab
    @kb.add('H', filter=is_normal_mode)
    def _(event):
        """Previous tab"""
        tabs = ["overview", "exec", "files", "summary"]
        current_idx = tabs.index(state.detail_tab)
        state.detail_tab = tabs[(current_idx - 1) % len(tabs)]

    @kb.add('L', filter=is_normal_mode)
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

    # Refresh
    @kb.add('c-l', filter=is_normal_mode)
    def _(event):
        """Hard refresh from backend"""
        try:
            controller.refresh_tasks()
            state.message = "Refreshed"
        except Exception as e:
            state.message = f"Refresh failed: {e}"
        get_app().invalidate()

    # Phase 3: Task actions
    # Approve selected STAGED task
    @kb.add('a', filter=is_normal_mode)
    def _(event):
        """Approve selected task"""
        controller.approve_selected_task()
        get_app().invalidate()

    # Reject/cancel selected task
    @kb.add('r', filter=is_normal_mode)
    def _(event):
        """Reject/cancel selected task"""
        controller.reject_selected_task()
        get_app().invalidate()

    # Submit new task (simple prompt)
    @kb.add('s', filter=is_normal_mode)
    def _(event):
        """
        Submit new task.
        Opens a simple blocking input dialog for description,
        then calls controller.submit_task().
        """
        app = get_app()

        async def _prompt_and_submit():
            # input_dialog is async-friendly helper
            desc = await input_dialog(
                title="Submit Task",
                text="Describe the task:"
            ).run_async()
            if desc:
                controller.submit_task(desc, auto_approve=False)
                app.invalidate()

        app.create_background_task(_prompt_and_submit())

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
