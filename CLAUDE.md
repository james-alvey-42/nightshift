# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NightShift is an AI-driven research automation system that uses Claude Code in headless mode to execute research tasks. It provides a staged approval workflow where a task planner agent analyzes user requests, selects appropriate MCP tools, and creates execution plans that can be reviewed before execution.

## Development Commands

### Installation
```bash
pip install -e .
```

### Containerized Execution Setup (Optional)
```bash
# Build Docker executor image
./scripts/build-executor.sh

# Enable containerized execution
export NIGHTSHIFT_USE_DOCKER=true

# Disable containerized execution
unset NIGHTSHIFT_USE_DOCKER
```

### Running NightShift

#### CLI Interface
```bash
# Submit task and wait for approval
nightshift submit "task description"

# Auto-approve and execute immediately
nightshift submit "task description" --auto-approve

# Run with Docker execution (alternative to env var)
NIGHTSHIFT_USE_DOCKER=true nightshift submit "task description" --auto-approve

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

#### GUI Interface
```bash
# Launch the graphical interface
nightshift-gui

# Or run directly without installation
python test_gui.py
```

The GUI provides a user-friendly interface for:
- Submitting new tasks with instant or staged approval
- Viewing and filtering the task queue
- Approving, cancelling, and monitoring tasks
- Viewing task results and full output

See `docs/GUI_GUIDE.md` for detailed GUI documentation.

### Testing
Note: No formal test suite exists yet. Manual testing is done via the CLI commands above.

## Architecture

NightShift uses a two-agent architecture:

1. **Task Planner Agent** (nightshift/core/task_planner.py): Analyzes user requests via `claude -p` with `--json-schema` to produce structured task plans including tool selection, enhanced prompts, and resource estimates.

2. **Executor Agent** (nightshift/core/agent_manager.py): Executes approved tasks via `claude -p` with `--verbose --output-format stream-json`, parsing the JSON stream to extract token usage and tool calls.

### Key Components

#### Core Components

- **TaskQueue** (nightshift/core/task_queue.py): SQLite-backed persistence with task lifecycle states (STAGED → COMMITTED → RUNNING → COMPLETED/FAILED). Tasks can include `additional_mounts` field for Docker execution.

- **FileTracker** (nightshift/core/file_tracker.py): Takes before/after snapshots of the working directory to detect created/modified files during execution

- **AgentManager** (nightshift/core/agent_manager.py): Orchestrates Claude CLI subprocess execution, parses stream-json output, and manages file tracking. Supports both native and Docker execution modes.

- **TaskPlanner** (nightshift/core/task_planner.py): Uses Claude with JSON schema enforcement to select MCP tools from nightshift/config/claude-code-tools-reference.md

- **DockerExecutor** (nightshift/core/docker_executor.py): Wraps Claude CLI execution in isolated Docker containers with automatic MCP server path discovery and mounting

- **MCPDiscovery** (nightshift/core/mcp_discovery.py): Auto-discovers MCP server installation paths by parsing `claude mcp list` output and resolving executables to determine what needs to be mounted in containers

#### Interface Components

- **CLI Interface** (nightshift/interfaces/cli.py): Command-line interface using Click and Rich for terminal-based task management

- **GUI Interface** (nightshift/gui/task_manager_gui.py): Tkinter-based graphical interface for visual task management. Provides:
  - Task submission with instant or staged approval
  - Real-time task queue visualization with status filtering
  - Task approval, cancellation, and result viewing
  - Auto-refresh capabilities for monitoring
  - Subprocess-based integration with CLI commands for reliability

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

## Containerized Execution

NightShift can run Claude Code tasks in isolated Docker containers when `NIGHTSHIFT_USE_DOCKER=true` is set. This provides security isolation and sandboxing.

### How It Works

- AgentManager detects the environment variable and initializes DockerExecutor
- DockerExecutor builds a `docker run` command that:
  - Runs the container as read-only (`--read-only`) with tmpfs for `/tmp`
  - Mounts system directories (`/usr`, `/lib`, `/lib64`, `/opt`) read-only for interpreters
  - Auto-discovers and mounts MCP server paths (venvs, npm globals) via MCPDiscovery
  - Mounts working directory as read-write at `/work`
  - Mounts `.claude` config directory as read-write
  - Creates temporary `.claude.json` with absolute MCP command paths (doesn't mutate user's config)
  - Passes through API key environment variables

### MCP Server Discovery

MCPDiscovery (nightshift/core/mcp_discovery.py) automatically finds MCP server installation paths:
1. Runs `claude mcp list` to get configured servers
2. Resolves each command to absolute path via `which`
3. Classifies executables (script with shebang, ELF binary, etc.)
4. For Python scripts, walks up to find virtualenv root (`pyvenv.cfg`)
5. For npm-based servers, discovers npm global prefix and root
6. Only mounts user-controlled paths (not system directories)
7. Returns minimal set of paths to mount for MCP servers to work in containers

This ensures MCP tools work inside containers without manual mount configuration.

### Building the Container

Use `./scripts/build-executor.sh` to build the `nightshift-claude-executor:latest` image.

## Important Implementation Details

- No timeouts are used during development (can be added via `timeout` parameter in `execute_task`)
- Task planner response parsing handles both direct JSON and wrapper format with markdown code fences
- File tracking uses hash-based comparison (SHA-256) to detect modifications
- All Claude interactions are subprocess executions, not SDK calls
- The system does NOT use the Claude Agent SDK - it shells out to the `claude` CLI binary
- Tool selection relies on the MCP tools reference document in nightshift/config/claude-code-tools-reference.md
- AgentManager supports both native execution (shell=True) and Docker execution (DockerExecutor.execute)
- Docker executor creates temporary config files to normalize MCP paths without mutating user's `.claude.json`

## Common Pitfalls

- Task planner expects structured JSON output but Claude may wrap it in markdown code fences - the parser handles this in task_planner.py:137-150
- Stream-json output must be parsed line-by-line; not all lines are valid JSON (some are plain text)
- File tracking snapshots are taken before/after execution, so files modified outside the working directory won't be detected
- Task status transitions must follow the valid state machine: STAGED → COMMITTED → RUNNING → COMPLETED/FAILED
- When using Docker execution, if MCP tools don't work, check that:
  - The Docker image exists (`docker image inspect nightshift-claude-executor:latest`)
  - `claude mcp list` shows the expected servers
  - MCP server paths are user-controlled (not system paths like `/usr/bin`)
- Docker executor uses user ID mapping (`-u uid:gid`) so files created in containers have correct ownership
