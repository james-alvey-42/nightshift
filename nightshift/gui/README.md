# NightShift GUI

A graphical user interface for managing NightShift tasks, built with tkinter.

## Features

- **Task Submission**: Submit new tasks with description input
- **Task Queue View**: Display all tasks with filtering by status
- **Task Management**: Approve, cancel, and view results for tasks
- **Auto-refresh**: Automatically refresh the task queue every 10 seconds
- **Task Details**: View comprehensive task information and full output
- **Status Colors**: Visual status indicators for different task states

## Installation

The GUI is automatically installed with NightShift. No additional dependencies are required beyond the standard NightShift installation.

```bash
pip install -e .
```

## Usage

### Launch the GUI

```bash
nightshift-gui
```

### GUI Components

#### 1. Task Submission Section
- Enter a task description in the text field
- Click "Submit" to create a task in STAGED state
- Click "Submit & Auto-Approve" to create and immediately execute the task
- Press Enter in the text field to submit quickly

#### 2. Task Queue Section
- View all tasks in a sortable table
- Filter by status: all, staged, committed, running, completed, failed, cancelled
- Auto-refresh checkbox enables/disables automatic updates every 10 seconds
- Refresh button manually updates the task list
- Task count shows the number of displayed tasks

#### 3. Task Details & Actions Section
- Displays detailed information for the selected task
- **Approve & Execute**: Approve a STAGED task and start execution
- **Cancel**: Cancel a STAGED or COMMITTED task
- **View Results**: Show task details in the current view
- **View Full Output**: Open a new window with complete task output (available for completed/failed tasks)

### Status Colors

- 🟠 **STAGED** (Orange): Awaiting approval
- 🔵 **COMMITTED** (Blue): Approved, ready to execute
- 🔷 **RUNNING** (Cyan): Currently executing
- 🟢 **COMPLETED** (Green): Successfully finished
- 🔴 **FAILED** (Red): Execution failed
- ⚫ **CANCELLED** (Gray): User cancelled

## Architecture

The GUI is a thin wrapper around the NightShift CLI commands:

- `nightshift submit` - Create new tasks
- `nightshift queue` - List tasks
- `nightshift approve` - Execute tasks
- `nightshift cancel` - Cancel tasks
- `nightshift results` - View task details

All CLI interactions are performed via subprocess calls, ensuring the GUI stays in sync with the underlying system.

## Threading

Long-running operations (task submission, approval, execution) run in background threads to prevent the GUI from freezing. Results are safely passed back to the main GUI thread using `root.after()`.

## Design Principles

1. **Simplicity**: Focus on core task management features
2. **Reliability**: Use subprocess calls to CLI instead of importing internal modules
3. **Responsiveness**: Background threads for long operations
4. **User Feedback**: Clear error messages and confirmation dialogs
5. **Visual Clarity**: Color-coded status indicators and clean layout

## Limitations

- No real-time streaming of task execution output (use CLI for that)
- Task queue parsing relies on CLI output format
- Auto-refresh interval is fixed at 10 seconds
- No support for advanced features like task revision or custom mounts

## Future Enhancements

Possible improvements for future versions:

- Real-time execution output streaming
- Task revision support in GUI
- Custom mount configuration UI
- Search and advanced filtering
- Task statistics and analytics
- Export task results
- Dark mode theme
