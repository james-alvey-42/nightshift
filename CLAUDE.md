# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NightShift is an AI-driven research automation system that uses Claude Code in headless mode to execute research tasks. It provides a staged approval workflow where a task planner agent analyzes user requests, selects appropriate MCP tools, and creates execution plans that can be reviewed before execution.

The system can be controlled via CLI or Slack, with sandboxed execution on macOS for security.

## Development Commands

### Installation
```bash
pip install -e .
pip install -e ".[dev]"  # With dev dependencies (pytest, coverage)
```

### Core CLI Commands
```bash
# Submit task and wait for approval
nightshift submit "task description"

# Auto-approve and queue for execution (async, new default)
nightshift submit "task description" --auto-approve

# Auto-approve and execute synchronously (wait for completion)
nightshift submit "task description" --auto-approve --sync

# View task queue
nightshift queue
nightshift queue --status staged
nightshift queue --status running

# Approve and queue a task for execution
nightshift approve task_XXXXXXXX

# Approve and execute synchronously
nightshift approve task_XXXXXXXX --sync

# View task results
nightshift results task_XXXXXXXX --show-output

# View execution session in human-readable format
nightshift display task_XXXXXXXX
# Watch task execution in real-time
nightshift watch task_XXXXXXXX

# Cancel a task
nightshift cancel task_XXXXXXXX

# Task executor management
nightshift executor start              # Start background executor service
nightshift executor status             # View executor status
nightshift executor stop               # Stop executor service

# Clear all data (with confirmation)
nightshift clear

# Launch interactive TUI
nightshift tui
```

### Testing

```bash
# Run all tests
pytest

# Run only TUI tests
pytest tests/tui/

# Run specific test file
pytest tests/tui/test_controller_exec_log.py

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=nightshift --cov-report=term-missing

# Run with coverage and generate HTML report
pytest --cov=nightshift --cov-report=html

# Open HTML coverage report (generated in htmlcov/)
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

**Test Suite Structure:**
```
tests/
├── conftest.py                        # Shared fixtures for all tests
└── tui/                              # TUI-specific tests
    ├── test_app_integration.py       # Integration tests
    ├── test_controller_exec_log.py   # Controller exec log tests
    ├── test_controller_files_summary.py  # File tracking tests
    ├── test_exec_log_formatting.py   # Formatting helpers
    ├── test_widgets_detail.py        # DetailControl tests
    ├── test_widgets_task_list.py     # TaskListControl tests
    └── test_task_deletion.py         # Task deletion tests
```

**Testing Strategy (3-Layer Approach):**
1. **Controller Unit Tests**: Controller logic with mocked backends
2. **Widget Rendering Tests**: Widget output verification
3. **Integration Tests**: Keybindings and UI wiring via prompt_toolkit

**Test Doubles:**
- Located in `nightshift/interfaces/tui/testing_doubles.py`
- Shared mocks: DummyQueue, DummyConfig, DummyPlanner, DummyAgent, DummyLogger
- Use `create_app_for_test()` in `app.py` to create test applications

**CI/CD:**
- GitHub Actions workflow in `.github/workflows/test.yml`
- Tests run on Python 3.10, 3.11, 3.12, 3.13
- Coverage reports uploaded to Codecov
- Triggered on push to main and feature/* branches, and on pull requests

# Start the Slack webhook server
nightshift slack-server

NightShift uses a concurrent task execution architecture with three main components:

### Testing
No formal test suite exists yet. Manual testing is done via:
1. CLI commands listed above
2. Slack commands in a test workspace
3. Checking logs in `~/.nightshift/logs/`

2. **Agent Manager** (nightshift/core/agent_manager.py): Executes individual tasks via `claude -p` with `--verbose --output-format stream-json`, parsing the JSON stream to extract token usage and tool calls. Spawns Claude CLI as subprocess.

3. **Task Executor** (nightshift/core/task_executor.py): Background service that polls for COMMITTED tasks and executes them concurrently using a thread pool. Supports up to N concurrent Claude CLI subprocesses (default: 3).

NightShift uses a two-agent architecture where both agents are Claude Code instances running in headless mode via the `claude` CLI:

- **TaskQueue** (nightshift/core/task_queue.py): Thread-safe SQLite-backed persistence with WAL mode enabled. Task lifecycle states: STAGED → COMMITTED → RUNNING → COMPLETED/FAILED. Supports concurrent reads/writes with `acquire_task_for_execution()` using atomic transactions.

- **TaskExecutor** (nightshift/core/task_executor.py): Manages concurrent task execution using ThreadPoolExecutor. Polls TaskQueue for COMMITTED tasks and submits them to worker threads. Each worker spawns an AgentManager subprocess.

- **ExecutorManager** (nightshift/core/task_executor.py): Singleton manager for global executor instance, ensures only one executor service runs at a time.

**Responsibilities:**
- Analyzes task description and selects appropriate MCP tools
- Determines sandbox permissions (which directories need write access)
- Determines scratch directory requirements (git repos and files to include)
- Generates enhanced prompt for executor
- Estimates token usage and execution time
- Sets `needs_git` flag for tasks requiring git/gh CLI access
- Sets `use_scratch` flag and populates `scratch_git_repos`/`scratch_copy_paths` for resource provisioning

**Key Logic:**
- Reads available tools from `nightshift/config/claude-code-tools-reference.md`
- Uses JSON schema validation to enforce structured output
- Parses response handling both direct JSON and markdown-wrapped format
- Intelligently determines what resources (git repos, files) task needs access to
- Defaults to using scratch directory with current repo for git-related tasks
- Can opt-out of scratch via `use_scratch: false` for simple tasks

### 2. Executor Agent (nightshift/core/agent_manager.py)
Executes approved tasks with restricted tool access and optional sandboxing. Invoked as:
```bash
# On macOS with sandbox enabled:
sandbox-exec -f <profile.sb> claude -p "<task>" --output-format stream-json --verbose --allowed-tools <tools> --system-prompt "<prompt>"

# On Linux or sandbox disabled:
claude -p "<task>" --output-format stream-json --verbose --allowed-tools <tools> --system-prompt "<prompt>"
```

**Responsibilities:**
- Executes task using only allowed MCP tools
- Runs inside sandbox (macOS) with restricted filesystem writes
- Parses stream-json output line-by-line
- Tracks file changes via before/after snapshots
- Reports progress and results back to task queue

**Stream-JSON Parsing:**
- Lines with `"type": "text"` → Claude's response content
- Lines with `"usage"` key → Token usage statistics
- Lines with `"type": "tool_use"` → MCP tool invocations
- Not all lines are valid JSON (some are plain text)

### Core Components

**TaskQueue** (nightshift/core/task_queue.py)
- SQLite-backed persistence with task lifecycle state machine
- Valid transitions: STAGED → COMMITTED → RUNNING → COMPLETED/FAILED
- Also supports: PAUSED, CANCELLED states
- Stores task metadata: description, allowed_tools, allowed_directories, needs_git, process_id
- Database schema includes migrations for new columns

**ScratchManager** (nightshift/core/scratch_manager.py)
- Manages isolated scratch directories for task execution
- **Setup Phase**: Clones git repos (using `git clone --shared`), copies files/directories, creates symlinks
- **Teardown Phase**: Detects modified files, copies them back to original locations, fetches new commits to source repo
- Git commits created in scratch are fetched to source repo on `nightshift-scratch` branch (not auto-merged)
- Each task gets its own workspace in `~/.nightshift/worktrees/task_ID/`
- Enables concurrent tasks on the same repository without conflicts
- Configurable via `use_scratch`, `working_directory`, `scratch_git_repos`, and `scratch_copy_paths` task fields

**SandboxManager** (nightshift/core/sandbox.py)
- macOS-only sandboxing using `sandbox-exec` with `.sb` profiles
- Generates profiles that deny all writes except to allowed_directories
- Always permits: /tmp, ~/.claude/, MCP credential files
- When `needs_git=true`: also permits /dev/null, /dev/tty, ~/.config/gh/
- Profiles enforce least-privilege: read-all, execute-all, network-all, write-restricted
- Works seamlessly with scratch directories (scratch dir automatically added to allowed writes)

**FileTracker** (nightshift/core/file_tracker.py)
- Takes SHA-256 hash snapshots before/after execution
- Detects created/modified/deleted files
- Tracks changes within working directory (scratch or explicit working dir)

**Notifier** (nightshift/core/notifier.py)
- Generates completion notifications with task summary
- Supports terminal output and Slack notifications
- Saves notification JSON to `~/.nightshift/notifications/`

**SlackEventHandler** (nightshift/integrations/slack_handler.py)
- Routes Slack slash commands to NightShift operations
- Handles button interactions (Approve/Reject/Details)
- Spawns planning/execution in background threads
- Uses `SlackMetadataStore` to track Slack context per task

**SlackClient** (nightshift/integrations/slack_client.py)
- Wrapper around Slack SDK with DM detection
- Formats messages using Block Kit via `SlackFormatter`
- Handles threaded replies for async operations

**SlackServer** (nightshift/integrations/slack_server.py)
- Flask app with `/slack/commands` and `/slack/interactions` endpoints
- HMAC-SHA256 signature verification via `slack_middleware.py`
- Rate limiting: 100/min global, with per-user extraction
- Caches raw request body for signature verification

### Terminal UI (TUI)

The TUI (nightshift/interfaces/tui/) uses prompt_toolkit and follows a clear separation of concerns:

- **app.py**: Application factory, creates and wires components
- **models.py**: Data structures (UIState, TaskRow, SelectedTaskState)
- **controllers.py**: Business logic layer (`TUIController` class)
- **widgets.py**: Custom prompt_toolkit controls (TaskListControl, DetailControl)
- **keybindings.py**: Keyboard shortcut definitions
- **layout.py**: UI layout composition

**TUI Keybindings:**
- `j/k` or arrows: Navigate task list
- `Enter` or `a`: Approve selected task
- `r`: Reject/cancel task
- `e`: Review/edit task plan (opens $EDITOR)
- `d`: Delete task
- `Tab`: Cycle detail tabs (overview/execution/files/summary)
- `:`: Enter command mode
- `q`: Quit
### Concurrent Execution

**Default Behavior (Async):**
- `nightshift submit --auto-approve` → Task moves to COMMITTED state → Executor picks it up asynchronously
- `nightshift approve task_id` → Task moves to COMMITTED state → Executor picks it up asynchronously
- Multiple tasks can be submitted and queued simultaneously
- Executor polls every 1s (configurable) for new COMMITTED tasks
- Up to 3 tasks (configurable) execute concurrently

**Synchronous Mode (Legacy):**
- `nightshift submit --auto-approve --sync` → Blocks until task completes
- `nightshift approve task_id --sync` → Blocks until task completes
- Useful for scripts that need to wait for results

**Configuration:**
- `NIGHTSHIFT_MAX_WORKERS`: Max concurrent tasks (default: 3)
- `NIGHTSHIFT_POLL_INTERVAL`: Polling interval in seconds (default: 1.0)
- `NIGHTSHIFT_AUTO_EXECUTOR`: Auto-start executor with Slack server (default: true)

### Scratch Directory Workflow

**Default Behavior (Scratch Isolation Enabled):**

1. **Planning Phase**: Task planner analyzes the task and determines:
   - Which git repositories need to be cloned
   - Which files/directories need to be copied
   - Whether scratch isolation is needed (`use_scratch: true` by default)

2. **Setup Phase**: ScratchManager creates isolated workspace:
   - Creates `~/.nightshift/worktrees/task_XXX/`
   - Clones git repos using `git clone --shared` (efficient, reuses objects)
   - Copies specified files/directories
   - Creates symlinks for read-only resources

3. **Execution Phase**: Task runs in scratch directory:
   - Claude CLI invoked with `--working-directory /path/to/scratch`
   - All file modifications happen in isolation
   - Original repos/files remain untouched
   - Multiple concurrent tasks can work on same repo safely

4. **Teardown Phase**: ScratchManager copies results back:
   - Detects modified files in scratch
   - Copies them back to original locations
   - For git repos: fetches new commits to source repo on `nightshift-scratch` branch
   - User can review and merge manually: `git merge nightshift-scratch`
   - Cleans up scratch directory

**Alternative: Explicit Working Directory:**

Task planner can set `use_scratch: false` and specify `working_directory` for tasks that:
- Don't need isolation (e.g., read-only analysis)
- Work with external directories
- Have simple, non-conflicting operations

### Data Storage

All data lives in `~/.nightshift/`:
- `database/nightshift.db` - SQLite task queue
- `logs/nightshift_YYYYMMDD.log` - Execution logs
- `output/task_XXX_output.json` - Task results and Claude output
- `output/task_XXX_files.json` - File change tracking
- `notifications/task_XXX_notification.json` - Completion summaries
- `config/slack_config.json` - Slack credentials (for Slack integration)
- `slack_metadata/task_XXX_slack.json` - Slack context (channel, user, thread)
- `worktrees/task_XXX/` - Scratch directories (temporary, cleaned after task)

### Claude CLI Integration

Both agents execute Claude via subprocess with specific configurations:

**Task Planner:**
```bash
claude -p "<planning_prompt>" --output-format json --json-schema <schema>
```
~/.nightshift/
├── config/
│   └── slack_config.json          # Slack credentials (encrypted/secure)
├── database/
│   └── nightshift.db              # SQLite task queue
├── logs/
│   └── nightshift_YYYYMMDD.log    # Daily execution logs
├── output/
│   ├── task_XXX_output.json       # Full stream-json output
│   └── task_XXX_files.json        # File change tracking
├── notifications/
│   └── task_XXX_notification.json # Completion summaries
└── slack_metadata/
    └── task_XXX_slack.json        # Slack context (channel, user, thread)
```

## Important Implementation Details

- **Thread-safety**: TaskQueue uses SQLite WAL mode and atomic transactions for concurrent access
- **Concurrent execution**: TaskExecutor uses ThreadPoolExecutor (not ProcessPoolExecutor) because AgentManager already spawns Claude CLI as separate processes
- **Task acquisition**: `acquire_task_for_execution()` uses `BEGIN IMMEDIATE` to atomically claim COMMITTED tasks
- No timeouts are used during development (can be added via `timeout` parameter in `execute_task`)
- Task planner response parsing handles both direct JSON and wrapper format with markdown code fences
- File tracking uses hash-based comparison (SHA-256) to detect modifications
- All Claude interactions are subprocess executions, not SDK calls
- The system does NOT use the Claude Agent SDK - it shells out to the `claude` CLI binary
- Tool selection relies on the MCP tools reference document in nightshift/config/claude-code-tools-reference.md

## Common Pitfalls

- Task planner expects structured JSON output but Claude may wrap it in markdown code fences - the parser handles this in task_planner.py
- Stream-json output must be parsed line-by-line; not all lines are valid JSON (some are plain text)
- File tracking snapshots are taken before/after execution, so files modified outside the working directory won't be detected
- Task status transitions must follow the valid state machine: STAGED → COMMITTED → RUNNING → COMPLETED/FAILED/CANCELLED
- TUI auto-refreshes every 2 seconds - disable with `create_app_for_test(disable_auto_refresh=True)` when testing
- The `format_exec_log_from_result()` function in controllers.py parses stream-json events; understand its structure before modifying
- **Concurrent execution requires executor**: By default, `--auto-approve` and `approve` now queue tasks for async execution. You must run `nightshift executor start` or use `--sync` flag for immediate execution
- **Database locks**: If you see "database is locked" errors, check that WAL mode is enabled (`PRAGMA journal_mode` should return "wal")
- **Executor not running**: If tasks stay in COMMITTED state, the executor service may not be running. Check with `nightshift executor status`
- Task planner expects structured JSON output but Claude may wrap it in markdown code fences - the parser handles this in task_planner.py:137-150
- Stream-json output must be parsed line-by-line; not all lines are valid JSON (some are plain text)
- File tracking snapshots are taken before/after execution, so files modified outside the working directory won't be detected
- Task status transitions must follow the valid state machine: STAGED → COMMITTED → RUNNING → COMPLETED/FAILED
- **Slack server auto-starts executor**: By default, `nightshift slack-server` starts the executor service automatically. Use `--no-executor` to disable.
