"""
TUI Application
Main application factory and event loop management
"""
import asyncio
from prompt_toolkit.application import Application
from prompt_toolkit.styles import Style

from nightshift.core.config import Config
from nightshift.core.logger import NightShiftLogger
from nightshift.core.task_queue import TaskQueue
from nightshift.core.task_planner import TaskPlanner
from nightshift.core.agent_manager import AgentManager

from .models import UIState, task_to_row
from .layout import create_layout, create_command_line
from .keybindings import create_keybindings
from .controllers import TUIController


def create_app() -> Application:
    """Create and configure the TUI application"""

    # Initialize backends
    cfg = Config()
    logger = NightShiftLogger(log_dir=str(cfg.get_log_dir()), console_output=False)
    queue = TaskQueue(db_path=str(cfg.get_database_path()))
    planner = TaskPlanner(logger, tools_reference_path=str(cfg.get_tools_reference_path()))
    agent = AgentManager(
        queue,
        logger,
        output_dir=str(cfg.get_output_dir()),
        enable_terminal_notifications=False  # Disable terminal output in TUI mode
    )

    # Initialize UI state
    state = UIState()

    # Create controller
    controller = TUIController(state, queue, cfg, planner, agent, logger)

    # Load initial tasks via controller
    controller.refresh_tasks()
    state.message = f"Loaded {len(state.tasks)} tasks"

    # Create command line widget
    cmd_widget = create_command_line(state)

    # Create layout
    layout = create_layout(state, cmd_widget)

    # Create keybindings
    key_bindings = create_keybindings(state, controller, cmd_widget)

    # Define style - use terminal color palette
    style = Style.from_dict({
        "statusbar": "dim",
        "separator": "dim",
        "dim": "dim",
        "yellow": "fg:ansiyellow",
        "orange": "fg:ansibrightred",
        "blue": "fg:ansiblue",
        "cyan": "fg:ansicyan",
        "magenta": "fg:ansimagenta",
        "green": "fg:ansigreen",
        "red": "fg:ansired",
        "ansired": "fg:ansired",

        # Tab styles
        "tab-active": "bold",

        # New detail panel helpers
        "heading": "bold underline",
        "section-title": "bold fg:ansicyan",
        "success": "fg:ansigreen bold",
        "error": "fg:ansired bold",

        # File change styles
        "file-created-title": "bold fg:ansigreen",
        "file-modified-title": "bold fg:ansiyellow",
        "file-deleted-title": "bold fg:ansired",
        "file-created": "fg:ansigreen",
        "file-modified": "fg:ansiyellow",
        "file-deleted": "fg:ansired",

        # Error codeblock style
        "error-codeblock": "fg:ansired",

        # Execution log styles
        "arg-key": "fg:ansibrightblack italic",
    })

    # Create application
    app = Application(
        layout=layout,
        key_bindings=key_bindings,
        full_screen=True,
        style=style,
        mouse_support=False,
    )

    # Auto-refresh task list every 2 seconds
    async def auto_refresh():
        """Periodically refresh the task list"""
        while True:
            await asyncio.sleep(2)
            controller.refresh_tasks()
            app.invalidate()

    # Schedule auto-refresh
    app.pre_run_callables.append(
        lambda: app.create_background_task(auto_refresh())
    )

    return app


def create_app_for_test(tasks=None, tmp_path=None, disable_auto_refresh: bool = True):
    """
    Create an Application wired with test doubles for integration testing.

    Args:
        tasks: List of task objects to populate DummyQueue (default: [])
        tmp_path: Path for temporary files (default: None)
        disable_auto_refresh: Disable background auto-refresh (default: True)

    Returns:
        (app, state, controller, queue, agent, logger) tuple
    """
    # Import test doubles
    from .testing_doubles import DummyQueue, DummyConfig, DummyPlanner, DummyAgent, DummyLogger

    # Backends with test doubles
    config = DummyConfig(tmp_path)
    logger = DummyLogger()

    # Default empty task list
    if tasks is None:
        tasks = []

    queue = DummyQueue(tasks)
    planner = DummyPlanner()
    agent = DummyAgent()

    # UI state + controller
    state = UIState()
    controller = TUIController(state, queue, config, planner, agent, logger)

    # Initial load
    controller.refresh_tasks()
    state.message = f"Loaded {len(state.tasks)} tasks"

    # UI pieces
    cmd_widget = create_command_line(state)
    layout = create_layout(state, cmd_widget)
    key_bindings = create_keybindings(state, controller, cmd_widget)

    # Minimal style for tests
    style = Style.from_dict({
        "statusbar": "dim",
        "separator": "dim",
        "dim": "dim",
        "yellow": "fg:ansiyellow",
        "orange": "fg:ansibrightred",
        "blue": "fg:ansiblue",
        "cyan": "fg:ansicyan",
        "magenta": "fg:ansimagenta",
        "green": "fg:ansigreen",
        "red": "fg:ansired",
        "ansired": "fg:ansired",
        "tab-active": "bold",
        "heading": "bold underline",
        "section-title": "bold fg:ansicyan",
        "success": "fg:ansigreen bold",
        "error": "fg:ansired bold",
        "file-created-title": "bold fg:ansigreen",
        "file-modified-title": "bold fg:ansiyellow",
        "file-deleted-title": "bold fg:ansired",
        "file-created": "fg:ansigreen",
        "file-modified": "fg:ansiyellow",
        "file-deleted": "fg:ansired",
        "error-codeblock": "fg:ansired",
        "arg-key": "fg:ansibrightblack italic",
    })

    app = Application(
        layout=layout,
        key_bindings=key_bindings,
        full_screen=False,  # Simpler for tests
        style=style,
        mouse_support=False,
    )

    if not disable_auto_refresh:
        # Optional: enable auto-refresh for specific tests
        async def auto_refresh():
            while True:
                await asyncio.sleep(2)
                controller.refresh_tasks()
                app.invalidate()

        app.pre_run_callables.append(
            lambda: app.create_background_task(auto_refresh())
        )

    return app, state, controller, queue, agent, logger
