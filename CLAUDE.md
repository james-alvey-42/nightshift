# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NightShift is an AI-driven research automation system that uses Claude Code in headless mode to execute research tasks. It provides a staged approval workflow where a task planner agent analyzes user requests, selects appropriate MCP tools, and creates execution plans that can be reviewed before execution.

## Development Commands

### Installation
```bash
pip install -e .
```

### Running NightShift
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
```

### Testing
Note: No formal test suite exists yet. Manual testing is done via the CLI commands above.

## Architecture

NightShift uses a concurrent task execution architecture with three main components:

1. **Task Planner Agent** (nightshift/core/task_planner.py): Analyzes user requests via `claude -p` with `--json-schema` to produce structured task plans including tool selection, enhanced prompts, and resource estimates.

2. **Agent Manager** (nightshift/core/agent_manager.py): Executes individual tasks via `claude -p` with `--verbose --output-format stream-json`, parsing the JSON stream to extract token usage and tool calls. Spawns Claude CLI as subprocess.

3. **Task Executor** (nightshift/core/task_executor.py): Background service that polls for COMMITTED tasks and executes them concurrently using a thread pool. Supports up to N concurrent Claude CLI subprocesses (default: 3).

### Key Components

- **TaskQueue** (nightshift/core/task_queue.py): Thread-safe SQLite-backed persistence with WAL mode enabled. Task lifecycle states: STAGED → COMMITTED → RUNNING → COMPLETED/FAILED. Supports concurrent reads/writes with `acquire_task_for_execution()` using atomic transactions.

- **TaskExecutor** (nightshift/core/task_executor.py): Manages concurrent task execution using ThreadPoolExecutor. Polls TaskQueue for COMMITTED tasks and submits them to worker threads. Each worker spawns an AgentManager subprocess.

- **ExecutorManager** (nightshift/core/task_executor.py): Singleton manager for global executor instance, ensures only one executor service runs at a time.

- **FileTracker** (nightshift/core/file_tracker.py): Takes before/after snapshots of the working directory to detect created/modified files during execution

- **AgentManager** (nightshift/core/agent_manager.py): Orchestrates Claude CLI subprocess execution, parses stream-json output, and manages file tracking

- **TaskPlanner** (nightshift/core/task_planner.py): Uses Claude with JSON schema enforcement to select MCP tools from nightshift/config/claude-code-tools-reference.md

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

### Data Storage

All data lives in `~/.nightshift/`:
- `database/nightshift.db` - SQLite task queue
- `logs/nightshift_YYYYMMDD.log` - Execution logs
- `output/task_XXX_output.json` - Task results and Claude output
- `output/task_XXX_files.json` - File change tracking
- `notifications/task_XXX_notification.json` - Completion summaries

### Claude CLI Integration

Both agents execute Claude via subprocess with specific configurations:

**Task Planner:**
```bash
claude -p "<planning_prompt>" --output-format json --json-schema <schema>
```

**Executor:**
```bash
claude -p "<task_description>" --output-format stream-json --verbose --allowed-tools <tools> --system-prompt "<prompt>"
```

The stream-json format is parsed line-by-line to extract:
- Text content blocks (type: "text")
- Token usage (key: "usage")
- Tool calls (type: "tool_use")

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

- **Concurrent execution requires executor**: By default, `--auto-approve` and `approve` now queue tasks for async execution. You must run `nightshift executor start` or use `--sync` flag for immediate execution
- **Database locks**: If you see "database is locked" errors, check that WAL mode is enabled (`PRAGMA journal_mode` should return "wal")
- **Executor not running**: If tasks stay in COMMITTED state, the executor service may not be running. Check with `nightshift executor status`
- Task planner expects structured JSON output but Claude may wrap it in markdown code fences - the parser handles this in task_planner.py:137-150
- Stream-json output must be parsed line-by-line; not all lines are valid JSON (some are plain text)
- File tracking snapshots are taken before/after execution, so files modified outside the working directory won't be detected
- Task status transitions must follow the valid state machine: STAGED → COMMITTED → RUNNING → COMPLETED/FAILED
- **Slack server auto-starts executor**: By default, `nightshift slack-server` starts the executor service automatically. Use `--no-executor` to disable.
