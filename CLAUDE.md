# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NightShift is an AI-driven research automation system that uses Claude Code in headless mode to execute research tasks. It provides a staged approval workflow where a task planner agent analyzes user requests, selects appropriate MCP tools, and creates execution plans that can be reviewed before execution.

The system can be controlled via CLI or Slack, with sandboxed execution on macOS for security.

## Development Commands

### Installation
```bash
pip install -e .
```

### Core CLI Commands
```bash
# Submit task and wait for approval
nightshift submit "task description"

# Auto-approve and execute immediately
nightshift submit "task description" --auto-approve

# Submit with additional allowed directories for sandbox
nightshift submit "task description" --allow-dir /path/to/dir

# View task queue
nightshift queue
nightshift queue --status staged

# Approve and execute a task
nightshift approve task_XXXXXXXX

# Revise a staged task plan with feedback
nightshift revise task_XXXXXXXX "use Claude instead of Gemini"

# View task results (basic info)
nightshift results task_XXXXXXXX

# View task results (with full output JSON)
nightshift results task_XXXXXXXX --show-output

# View execution session (human-readable display)
nightshift display task_XXXXXXXX

# Process control
nightshift pause task_XXXXXXXX
nightshift resume task_XXXXXXXX
nightshift kill task_XXXXXXXX
nightshift cancel task_XXXXXXXX

# Clear all data (with confirmation)
nightshift clear
```

### Slack Integration Commands
```bash
# Configure Slack credentials
nightshift slack-setup

# Start the Slack webhook server
nightshift slack-server

# Then use slash commands in Slack:
# /nightshift submit "task description"
# /nightshift queue
# /nightshift status task_XXXXXXXX
```

### Testing
No formal test suite exists yet. Manual testing is done via:
1. CLI commands listed above
2. Slack commands in a test workspace
3. Checking logs in `~/.nightshift/logs/`

## Architecture

NightShift uses a two-agent architecture where both agents are Claude Code instances running in headless mode via the `claude` CLI:

### 1. Task Planner Agent (nightshift/core/task_planner.py)
Analyzes user requests to produce structured execution plans. Invoked as:
```bash
claude -p "<planning_prompt>" --output-format json --json-schema <schema>
```

**Responsibilities:**
- Analyzes task description and selects appropriate MCP tools
- Determines sandbox permissions (which directories need write access)
- Generates enhanced prompt for executor
- Estimates token usage and execution time
- Sets `needs_git` flag for tasks requiring git/gh CLI access

**Key Logic:**
- Reads available tools from `nightshift/config/claude-code-tools-reference.md`
- Uses JSON schema validation to enforce structured output
- Parses response handling both direct JSON and markdown-wrapped format (task_planner.py:137-150)
- Defaults to current working directory for sandbox permissions when uncertain

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

**SandboxManager** (nightshift/core/sandbox.py)
- macOS-only sandboxing using `sandbox-exec` with `.sb` profiles
- Generates profiles that deny all writes except to allowed_directories
- Always permits: /tmp, ~/.claude/, MCP credential files
- When `needs_git=true`: also permits /dev/null, /dev/tty, ~/.config/gh/
- Profiles enforce least-privilege: read-all, execute-all, network-all, write-restricted

**FileTracker** (nightshift/core/file_tracker.py)
- Takes SHA-256 hash snapshots before/after execution
- Detects created/modified/deleted files
- Only tracks changes within working directory (not system-wide)

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

### Data Storage

All data lives in `~/.nightshift/`:
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

### Claude CLI Execution
- **NOT using Claude Agent SDK** - All Claude interactions are via subprocess calls to `claude` CLI binary
- No timeouts by default during development (can be added via `timeout` parameter to `execute_task`)
- Environment variables: GH_TOKEN loaded from `gh auth token` when `needs_git=true` for sandbox compatibility

### Task Planner
- Uses `--json-schema` flag to enforce structured output from Claude
- Response parsing handles both direct JSON and markdown code fence wrappers (task_planner.py:137-150)
- Tool selection based on `nightshift/config/claude-code-tools-reference.md`
- Planning timeout default: 120 seconds (configurable via `--planning-timeout`)

### Executor
- Uses `--allowed-tools` to restrict MCP tool access to planner-approved list
- Stream-json output parsed line-by-line (not all lines are valid JSON - some are plain text)
- Process ID stored in task record for pause/resume/kill operations
- Stdout/stderr captured and saved to output JSON

### Sandboxing (macOS only)
- `SandboxManager.is_available()` checks for `sandbox-exec` availability
- Sandbox profiles are temporary files cleaned up after execution
- When sandboxing fails (permission issues), falls back to unsandboxed execution with warning
- Sandbox violations appear as "Operation not permitted" errors in output

### File Tracking
- Snapshots taken before/after execution using SHA-256 hashes
- Only tracks changes within current working directory (not system-wide)
- Three categories: created, modified, deleted
- Results saved to `task_XXX_files.json`

### Slack Integration
- Signature verification uses cached raw request body (before Flask parsing)
- Timestamp window: 5 minutes (prevents replay attacks)
- Planning/execution spawned in background threads to avoid 3-second timeout
- DM channels detected and handled differently (use user_id instead of channel_id)
- Metadata persistence links Slack context to task_id

### Git Operations
- Tasks with `needs_git=true` get additional sandbox permissions:
  - `/dev/null` and `/dev/tty` (required by gh CLI)
  - `~/.config/gh/` (gh CLI token cache)
  - `~/.gitconfig` (git configuration)
- GH_TOKEN environment variable loaded from `gh auth token` for API access
- Commit messages should end with: "🌙 Generated by NightShift (https://github.com/james-alvey-42/nightshift)"

## Common Pitfalls

### Task Planner Issues
- Task planner may wrap JSON in markdown code fences - parser handles this at task_planner.py:137-150
- If planning times out, increase `--planning-timeout` (default 120s)
- Planning prompt includes current working directory for absolute path resolution

### Executor Issues
- Stream-json output must be parsed line-by-line; not all lines are valid JSON
- Tool calls may fail if tool name not in `allowed_tools` list
- File tracking only detects changes in working directory (files in /tmp or other locations won't be tracked)

### State Machine
- Task status transitions must follow valid state machine:
  - STAGED → COMMITTED → RUNNING → COMPLETED/FAILED
  - RUNNING ↔ PAUSED (bidirectional)
  - Any state → CANCELLED
- Attempting invalid transition will raise error

### Sandbox Issues
- Sandbox only works on macOS with `sandbox-exec` installed
- Write operations outside `allowed_directories` will fail with "Operation not permitted"
- If task needs to write to additional directories, use `--allow-dir` flag or revise plan
- Git operations require `needs_git=true` or will fail with device access errors
- MCP credential files automatically permitted (see sandbox.py:66-70)
