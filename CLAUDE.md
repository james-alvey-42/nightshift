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

# Auto-approve and execute immediately
nightshift submit "task description" --auto-approve

# View task queue
nightshift queue
nightshift queue --status staged

# Approve and execute a task
nightshift approve task_XXXXXXXX

# View task results
nightshift results task_XXXXXXXX --show-output

# Cancel a task
nightshift cancel task_XXXXXXXX

# Clear all data (with confirmation)
nightshift clear
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

# Run with coverage (if installed)
pytest --cov=nightshift
```

**Test Suite Structure:**
```
tests/
├── conftest.py                        # Shared fixtures for all tests
└── tui/                              # TUI-specific tests (63 tests)
    ├── test_app_integration.py       # Integration tests (4 tests)
    ├── test_controller_exec_log.py   # Controller exec log tests (9 tests)
    ├── test_controller_files_summary.py  # File tracking tests (6 tests)
    ├── test_exec_log_formatting.py   # Formatting helpers (13 tests)
    ├── test_widgets_detail.py        # DetailControl tests (24 tests)
    └── test_widgets_task_list.py     # TaskListControl tests (7 tests)
```

**Testing Strategy (3-Layer Approach):**
1. ✅ **Step 1 - Controller Unit Tests** (28 tests): Controller logic with mocked backends
2. ✅ **Step 2 - Widget Rendering Tests** (31 tests): Widget output verification
3. ✅ **Step 3 - Integration Tests** (4 tests): Keybindings and UI wiring via prompt_toolkit

**Test Doubles:**
- Located in `nightshift/interfaces/tui/testing_doubles.py`
- Shared mocks: DummyQueue, DummyConfig, DummyPlanner, DummyAgent, DummyLogger

**CI/CD:**
- GitHub Actions workflow in `.github/workflows/test.yml`
- Tests run on Python 3.10, 3.11, 3.12, 3.13
- Triggered on push to main and feature/* branches, and on pull requests

## Architecture

NightShift uses a two-agent architecture:

1. **Task Planner Agent** (nightshift/core/task_planner.py): Analyzes user requests via `claude -p` with `--json-schema` to produce structured task plans including tool selection, enhanced prompts, and resource estimates.

2. **Executor Agent** (nightshift/core/agent_manager.py): Executes approved tasks via `claude -p` with `--verbose --output-format stream-json`, parsing the JSON stream to extract token usage and tool calls.

### Key Components

- **TaskQueue** (nightshift/core/task_queue.py): SQLite-backed persistence with task lifecycle states (STAGED → COMMITTED → RUNNING → COMPLETED/FAILED)

- **FileTracker** (nightshift/core/file_tracker.py): Takes before/after snapshots of the working directory to detect created/modified files during execution

- **AgentManager** (nightshift/core/agent_manager.py): Orchestrates Claude CLI subprocess execution, parses stream-json output, and manages file tracking

- **TaskPlanner** (nightshift/core/task_planner.py): Uses Claude with JSON schema enforcement to select MCP tools from nightshift/config/claude-code-tools-reference.md

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

- No timeouts are used during development (can be added via `timeout` parameter in `execute_task`)
- Task planner response parsing handles both direct JSON and wrapper format with markdown code fences
- File tracking uses hash-based comparison (SHA-256) to detect modifications
- All Claude interactions are subprocess executions, not SDK calls
- The system does NOT use the Claude Agent SDK - it shells out to the `claude` CLI binary
- Tool selection relies on the MCP tools reference document in nightshift/config/claude-code-tools-reference.md

## Common Pitfalls

- Task planner expects structured JSON output but Claude may wrap it in markdown code fences - the parser handles this in task_planner.py:137-150
- Stream-json output must be parsed line-by-line; not all lines are valid JSON (some are plain text)
- File tracking snapshots are taken before/after execution, so files modified outside the working directory won't be detected
- Task status transitions must follow the valid state machine: STAGED → COMMITTED → RUNNING → COMPLETED/FAILED
