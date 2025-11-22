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
Note: No formal test suite exists yet. Manual testing is done via the CLI commands above.

## Architecture

NightShift uses a two-agent architecture:

1. **Task Planner Agent** (nightshift/core/task_planner.py): Analyzes user requests via `claude -p` with `--json-schema` to produce structured task plans including:
   - Tool selection from available MCP servers
   - Enhanced prompts and system prompts
   - Resource estimates (tokens, time)
   - **Execution environment recommendation** (local, docker, or cloud)
   - **Software stack requirements** (Python packages, system packages, resource needs)
   - **Containerization suggestions** (base images, Dockerfile hints)

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

## Environment and Stack Planning

The task planner now includes intelligent environment and software stack detection to prepare for future containerization and cloud deployment capabilities. When you submit a task, the planner analyzes it to determine:

### Execution Environment
- **local**: For most tasks using available MCP tools (default)
- **docker**: For tasks requiring specific system packages or isolation
- **cloud**: For compute-intensive tasks (>8GB RAM, GPU, long-running)

### Software Stack
The planner infers required dependencies by analyzing:
- Task description (e.g., "analyze CSV" → pandas, matplotlib)
- Selected MCP tools (e.g., arxiv tools → PDF processing libraries)
- System requirements (compilers, image processing binaries)

### Example Planning Output
```bash
$ nightshift submit "Analyze sales data from data.csv and create visualizations"

✓ Task created: task_abc12345

╭─ Task Plan: task_abc12345 ─────────────────────────────────╮
│ Original: Analyze sales data from data.csv and create...   │
│                                                             │
│ Enhanced prompt: Read data.csv, perform statistical...     │
│                                                             │
│ Tools needed: Read, Write, Bash                            │
│                                                             │
│ Estimated: ~1500 tokens, ~120s                             │
│                                                             │
│ Reasoning: File operations needed for CSV reading and...   │
│                                                             │
│ Execution Environment: local                               │
│ Tasks using standard MCP tools can run locally without...  │
│                                                             │
│ Software Stack:                                            │
│   • Python packages: pandas, matplotlib, seaborn           │
│   • System packages: none                                  │
│   • Python: 3.11, RAM: 2GB, Disk: 1GB                     │
│                                                             │
│ Containerization: Recommended                              │
│   • Base image: python:3.11-slim                          │
╰─────────────────────────────────────────────────────────────╯
```

This planning data is stored in the database and can be used in future features for:
- Automatic Docker container preparation
- Cloud deployment and resource provisioning
- Dependency validation before execution
- Reproducible research environments
