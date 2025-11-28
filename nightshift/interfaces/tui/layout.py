"""
TUI Layout
prompt_toolkit layout configuration
"""
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, Float
from prompt_toolkit.layout.containers import FloatContainer, ConditionalContainer
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.filters import Condition
from .models import UIState
from .widgets import create_task_list_window, create_detail_window, create_status_bar


def create_command_line(state: UIState):
    """Create the command line widget"""
    return TextArea(
        height=1,
        prompt=':',
        style='class:commandline',
        multiline=False,
        wrap_lines=False,
    )


def create_root_container(state: UIState, cmd_widget):
    """Create the root container for the TUI

    Returns:
        (container, detail_window) tuple - detail_window needed for scroll keybindings
    """
    # Create detail window separately so we can return it for keybindings
    detail_window = create_detail_window(state)

    # Main body: task list | separator | detail panel
    body = VSplit([
        create_task_list_window(state),
        Window(width=1, char='│', style='class:separator'),
        detail_window,
    ])

    # Status bar at bottom
    status = create_status_bar(state)

    # Vertical split: body + status
    root = HSplit([
        body,
        status,
    ])

    # Command line (shown when command_active)
    command_line_container = ConditionalContainer(
        content=cmd_widget,
        filter=Condition(lambda: state.command_active),
    )

    # Wrap in FloatContainer for command line and future modals
    float_container = FloatContainer(
        content=root,
        floats=[
            Float(
                bottom=0,
                left=0,
                right=0,
                content=command_line_container,
            ),
        ],
    )

    return float_container, detail_window


def create_layout(state: UIState, cmd_widget):
    """Create the prompt_toolkit Layout

    Returns:
        (Layout, detail_window) tuple - detail_window needed for scroll keybindings
    """
    root, detail_window = create_root_container(state, cmd_widget)
    return Layout(root), detail_window
