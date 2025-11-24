# NightShift GUI User Guide

## Overview

NightShift provides a graphical user interface (GUI) for managing research tasks. The GUI is built with tkinter and offers a user-friendly way to submit, monitor, and manage tasks without using the command line.

## Installation

The GUI is included with NightShift. After installing NightShift, you can launch the GUI:

```bash
# Install NightShift
pip install -e .

# Launch GUI
nightshift-gui
```

Alternatively, you can run the GUI directly without installation:

```bash
python test_gui.py
```

## Main Window

The GUI is organized into three main sections:

### 1. Submit New Task Section (Top)

![Task Submission](images/task-submission.png)

This section allows you to create new tasks:

- **Description Field**: Enter your task description
- **Submit Button**: Creates a task in STAGED state (waiting for approval)
- **Submit & Auto-Approve Button**: Creates and immediately executes the task

**Tips:**
- Press `Enter` in the description field to quickly submit
- Use clear, specific descriptions for better task planning
- Auto-approve is useful for quick, trusted tasks

### 2. Task Queue Section (Middle)

![Task Queue](images/task-queue.png)

This section displays all your tasks:

- **Filter Dropdown**: Filter tasks by status (all, staged, running, completed, etc.)
- **Refresh Button**: Manually refresh the task list
- **Auto-refresh Checkbox**: Enable/disable automatic updates every 10 seconds
- **Task Count**: Shows the number of visible tasks

**Task Table Columns:**
- **Task ID**: Unique identifier (e.g., task_a1b2c3d4)
- **Status**: Current task state (color-coded)
- **Description**: Task description (truncated if long)
- **Tools**: MCP tools used by the task
- **Est. Time**: Estimated execution time
- **Created**: Task creation date

**Interactions:**
- Click a task row to view details
- Double-click a task to open detailed view in a new window
- Tasks are color-coded by status for quick identification

### 3. Task Details & Actions Section (Bottom)

![Task Details](images/task-details.png)

This section shows details for the selected task and provides action buttons:

**Action Buttons:**
- **✓ Approve & Execute**: Approve a STAGED task and start execution
  - Only enabled for STAGED tasks
  - Shows confirmation dialog before execution
  - Runs in background thread (may take several minutes)

- **✗ Cancel**: Cancel a STAGED or COMMITTED task
  - Shows confirmation dialog
  - Cannot cancel running or completed tasks

- **📄 View Results**: Display task details in the details area
  - Shows task metadata, status, timing, errors

- **📋 View Full Output**: Open complete task output in new window
  - Only enabled for COMPLETED or FAILED tasks
  - Shows full JSON output from task execution

## Task Status Colors

The GUI uses color-coding to indicate task status:

| Status | Color | Meaning |
|--------|-------|---------|
| STAGED | 🟠 Orange | Awaiting user approval |
| COMMITTED | 🔵 Blue | Approved, queued for execution |
| RUNNING | 🔷 Cyan | Currently executing |
| COMPLETED | 🟢 Green | Successfully finished |
| FAILED | 🔴 Red | Execution failed |
| CANCELLED | ⚫ Gray | User cancelled |

## Workflows

### Basic Task Submission Workflow

1. Enter task description in the text field
2. Click "Submit" (or press Enter)
3. Wait for task planning (10-30 seconds)
4. Review task plan in success message
5. Task appears in queue with STAGED status
6. Select task in queue and click "✓ Approve & Execute"
7. Wait for execution (may take several minutes)
8. Task status changes to COMPLETED or FAILED
9. Click "📋 View Full Output" to see results

### Quick Auto-Approve Workflow

1. Enter task description
2. Click "Submit & Auto-Approve"
3. Wait for planning and execution
4. Review results when complete

### Monitoring Long-Running Tasks

1. Submit task with auto-approve or approve manually
2. Task status changes to RUNNING
3. Enable "Auto-refresh" to monitor status
4. GUI updates every 10 seconds
5. When complete, status changes to COMPLETED/FAILED
6. View results with "View Full Output" button

### Cancelling Unwanted Tasks

1. Select task in queue (must be STAGED or COMMITTED)
2. Click "✗ Cancel"
3. Confirm cancellation
4. Task status changes to CANCELLED

## Tips and Best Practices

### Task Management
- Use auto-refresh to monitor multiple tasks
- Filter by status to focus on specific task types
- Review task plans before approving staged tasks
- Use descriptive task names for easier tracking

### Performance
- Disable auto-refresh when not needed to reduce system load
- Long-running tasks (>5 minutes) are better monitored via CLI
- Multiple concurrent task approvals can be done from CLI

### Troubleshooting
- If task list doesn't update, click Refresh manually
- If GUI freezes, check terminal for error messages
- For detailed execution logs, use CLI: `nightshift results task_id --show-output`
- If task planning fails, check that Claude API key is configured

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| Enter (in description field) | Submit task |
| Double-click task | Open detailed view |

## Integration with CLI

The GUI is a frontend for the NightShift CLI. All operations are performed via subprocess calls to:

- `nightshift submit <description>`
- `nightshift submit <description> --auto-approve`
- `nightshift queue [--status <status>]`
- `nightshift approve <task_id>`
- `nightshift cancel <task_id>`
- `nightshift results <task_id> [--show-output]`

You can freely mix GUI and CLI usage. Changes made in one interface are immediately visible in the other.

## Limitations

Current limitations of the GUI:

1. **No real-time streaming**: Task execution output is not streamed in real-time (use CLI for that)
2. **Fixed refresh interval**: Auto-refresh is set to 10 seconds
3. **No task revision**: Cannot revise task plans (use CLI: `nightshift revise`)
4. **No custom mounts**: Cannot specify custom Docker mounts (use CLI: `nightshift submit --mount`)
5. **Output parsing**: Relies on CLI output format (may break if format changes)

## Advanced Features (CLI Only)

Some features are only available via CLI:

- **Task Revision**: `nightshift revise <task_id> "feedback"`
- **Custom Docker Mounts**: `nightshift submit --mount /path`
- **Planning Timeout**: `nightshift submit --planning-timeout 300`
- **Clear All Data**: `nightshift clear --confirm`

## System Requirements

- Python 3.8 or higher
- tkinter (included with Python on most systems)
- NightShift CLI installed and configured
- GUI works on Linux, macOS, and Windows

### Installing tkinter

If tkinter is not available:

**Ubuntu/Debian:**
```bash
sudo apt-get install python3-tk
```

**macOS:**
```bash
# tkinter is included with Python from python.org
# If using Homebrew Python:
brew install python-tk
```

**Windows:**
```bash
# tkinter is included with Python installer
```

## Troubleshooting

### GUI won't launch

```bash
# Check if tkinter is available
python3 -m tkinter

# Should open a small test window
```

### "nightshift: command not found"

```bash
# Make sure NightShift is installed
pip install -e .

# Or use absolute path to nightshift
which nightshift
```

### Task list shows empty or errors

```bash
# Verify CLI works
nightshift queue

# Check database exists
ls ~/.nightshift/database/

# Check permissions
ls -la ~/.nightshift/
```

### Tasks don't execute

```bash
# Verify Claude CLI is installed
which claude

# Check API key is configured
claude --version

# Test Claude manually
claude -p "Hello, Claude"
```

## Getting Help

For issues or questions:

1. Check the main documentation: `CLAUDE.md`
2. Run CLI commands directly to diagnose issues
3. Check logs: `~/.nightshift/logs/`
4. Review task output: `nightshift results <task_id> --show-output`

## Future Enhancements

Planned improvements for future versions:

- [ ] Real-time execution output streaming
- [ ] Task search and advanced filtering
- [ ] Task statistics dashboard
- [ ] Custom theme support (dark mode)
- [ ] Task revision UI
- [ ] Custom mount configuration UI
- [ ] Export results to file
- [ ] Task history visualization
- [ ] Multi-select operations (bulk cancel, etc.)
- [ ] Configurable auto-refresh interval
