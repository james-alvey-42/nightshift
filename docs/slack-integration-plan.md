# Slack API Integration Plan for NightShift
## Issue #11 Analysis & Implementation Roadmap

**Created:** November 25, 2024
**Branch:** `feature/issue-11-slack-api-integration`
**Status:** Planning Phase

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Existing Architecture Analysis](#existing-architecture-analysis)
3. [Issue #11 Requirements](#issue-11-requirements)
4. [Integration Design](#integration-design)
5. [Sub-Task Breakdown](#sub-task-breakdown)
6. [Implementation Roadmap](#implementation-roadmap)
7. [Security Considerations](#security-considerations)
8. [Testing Strategy](#testing-strategy)
9. [Scalability Considerations](#scalability-considerations)

---

## Executive Summary

This document provides a comprehensive analysis and implementation plan for adding Slack API integration to NightShift, enabling users to submit tasks, approve workflows, and receive notifications directly from Slack.

**Key Objectives:**
- Enable task submission via Slack slash commands
- Implement interactive approval workflows
- Provide real-time status updates and notifications
- Maintain security and authorization controls
- Build a scalable, maintainable integration

**Timeline Estimate:** 3-4 weeks (Phase 1)
**Complexity:** Medium-High
**Dependencies:** Slack SDK, webhook infrastructure, existing CLI commands

---

## Existing Architecture Analysis

### 1. Command Structure (CLI Interface)

**Location:** `nightshift/interfaces/cli.py`

**Current Commands:**
- `submit` - Create and optionally execute tasks
- `queue` - View task list with filtering
- `approve` - Approve and execute staged tasks
- `results` - View task results
- `display` - Show execution output
- `revise` - Request plan revisions
- `cancel` - Cancel staged tasks
- `pause` - Pause running tasks (SIGSTOP)
- `resume` - Resume paused tasks (SIGCONT)
- `kill` - Kill running/paused tasks (SIGKILL)
- `watch` - Monitor task execution
- `clear` - Clear all NightShift data

**Key Patterns Observed:**
1. All commands follow a consistent pattern:
   - Accept `@click.pass_context` to access shared components
   - Use `ctx.obj` dictionary for dependency injection
   - Leverage `Rich` library for formatted console output
   - Return user-friendly messages with color coding

2. Dependency Injection via Context:
   ```python
   ctx.obj['config'] = Config()
   ctx.obj['logger'] = NightShiftLogger(...)
   ctx.obj['task_queue'] = TaskQueue(...)
   ctx.obj['task_planner'] = TaskPlanner(...)
   ctx.obj['agent_manager'] = AgentManager(...)
   ```

3. Error Handling:
   - Validate task existence before operations
   - Check task status before state transitions
   - Raise `click.Abort()` for user-facing errors
   - Console output for success/error feedback

### 2. Task Queue & Lifecycle

**Location:** `nightshift/core/task_queue.py`

**Task Status States:**
```python
STAGED → COMMITTED → RUNNING → COMPLETED
                    ↓          ↓
                  PAUSED    FAILED
                    ↓          ↓
                RUNNING    CANCELLED
```

**Key Methods:**
- `create_task()` - Creates task in STAGED state
- `get_task()` - Retrieves task by ID
- `list_tasks()` - Lists all/filtered tasks
- `update_status()` - Manages state transitions
- `update_plan()` - Modifies staged task plans
- `add_log()` / `get_logs()` - Task-level logging

**Task Data Structure:**
```python
@dataclass
class Task:
    task_id: str
    description: str
    status: str
    allowed_tools: List[str]
    allowed_directories: List[str]
    needs_git: bool
    system_prompt: str
    estimated_tokens: int
    estimated_time: int
    process_id: int  # PID for pause/resume/kill
    # ... timestamps, results, etc.
```

**Storage:** SQLite database at `~/.nightshift/database/nightshift.db`

### 3. Agent Manager & Execution

**Location:** `nightshift/core/agent_manager.py`

**Core Responsibilities:**
1. **Task Execution:** Spawns Claude CLI subprocesses with specific configurations
2. **Process Management:** Tracks PIDs for pause/resume/kill operations
3. **Output Streaming:** Real-time output capture and file updates
4. **File Tracking:** Before/after snapshots of filesystem changes
5. **Notification Dispatch:** Calls Notifier on task completion

**Key Methods:**
- `execute_task()` - Main execution orchestrator
- `pause_task()` - Sends SIGSTOP to process
- `resume_task()` - Sends SIGCONT to process
- `kill_task()` - Sends SIGKILL to process
- `_build_command()` - Constructs Claude CLI command
- `_parse_output()` - Parses stream-json format

**Execution Flow:**
1. Build Claude command with allowed tools and system prompt
2. Wrap with sandbox-exec if enabled (macOS isolation)
3. Launch subprocess with `Popen` to capture PID
4. Update task status to RUNNING with PID and result path
5. Stream stdout/stderr to file in real-time (non-blocking I/O)
6. Parse stream-json output for tokens and tool calls
7. Track file changes during execution
8. Update final task status (COMPLETED/FAILED)
9. Trigger notification

**Command Example:**
```bash
claude -p "task description" \
  --output-format stream-json \
  --verbose \
  --allowed-tools Read Write mcp__arxiv__download \
  --system-prompt "..."
```

### 4. Notification System

**Location:** `nightshift/core/notifier.py`

**Current Implementation:**
- Generates JSON summaries of task completion
- Saves to `~/.nightshift/notifications/task_XXX_notification.json`
- Displays formatted terminal output using Rich
- **Contains placeholder methods for Slack/email** (lines 153-161)

**Notification Data:**
```python
{
    "task_id": str,
    "description": str,
    "timestamp": str,
    "status": "success" | "failed",
    "execution_time": float,
    "token_usage": int,
    "file_changes": {
        "created": List[str],
        "modified": List[str],
        "deleted": List[str]
    },
    "error_message": str,
    "result_path": str
}
```

**Integration Points:**
- Called by `AgentManager.execute_task()` on completion
- Currently only implements terminal display
- **Ready for Slack integration** via `_send_slack()` method

### 5. Task Planner

**Location:** `nightshift/core/task_planner.py`

**Responsibilities:**
1. Analyzes user requests using Claude
2. Selects appropriate MCP tools
3. Generates enhanced prompts and system prompts
4. Estimates resource usage (tokens, time)
5. Determines sandbox permissions (allowed directories)

**Key Insights for Slack Integration:**
- Planning is CPU-intensive (uses Claude CLI with JSON schema)
- Can take 30-120 seconds depending on complexity
- Produces structured JSON output
- **Async execution could improve Slack UX** (submit → plan in background → notify)

---

## Issue #11 Requirements

### Core Features (from GitHub Issue)

#### 1. Task Submission via Slack Commands
```
/nightshift submit "task description"
```
- User submits task via slash command
- Bot responds with task ID and confirmation
- Task enters STAGED state (same as CLI)

#### 2. Approval Workflow in Slack
- Interactive message with task details:
  - Task description
  - Resource estimates (tokens, time)
  - Selected MCP tools
  - Sandbox permissions
- **Approve** and **Reject** buttons
- Option to view complete plan details
- Follow-up messages for status updates

#### 3. Direct Task Execution
```
/nightshift execute "task description"
```
- Equivalent to CLI's `--auto-approve` flag
- Immediately plans and executes
- Sends completion notification

#### 4. Status Updates and Notifications
- Real-time progress updates in channels/threads
- Completion notifications with results summary
- Links to output files (local storage)
- Error notifications with diagnostic info

### Technical Requirements

#### Bot Token Scopes
- `commands` - Slash command registration
- `chat:write` - Post messages to channels
- `interactions:write` - Interactive buttons/components
- `files:write` - Upload result files (future)

#### Architecture Components
1. **Webhook Server** - Handles Slack events and requests
2. **Slack Client Wrapper** - Encapsulates Slack SDK operations
3. **Event Handlers** - Maps Slack interactions to NightShift commands
4. **Configuration** - Manages tokens, secrets, workspace settings

#### Security Requirements
- Slack request signature verification
- Rate limiting on webhook endpoints
- User authentication/authorization mapping
- Sensitive output protection in public channels

### Implementation Phases

**Phase 1:** Basic slash command functionality with CLI-based approval
**Phase 2:** Interactive approval buttons and thread-based updates
**Phase 3:** File uploads, real-time progress, Block Kit formatting, multi-channel support

---

## Integration Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        Slack Workspace                      │
│  ┌──────────────┐     ┌──────────────┐    ┌─────────────┐ │
│  │ /nightshift  │────▶│ Interactive  │───▶│ Completion  │ │
│  │   submit     │     │  Approval    │    │Notification │ │
│  └──────────────┘     └──────────────┘    └─────────────┘ │
└──────────────┬──────────────┬──────────────────┬───────────┘
               │              │                  │
               ▼              ▼                  ▼
┌─────────────────────────────────────────────────────────────┐
│                    Slack Integration Layer                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │            SlackWebhookServer (Flask/FastAPI)        │  │
│  │  - Request signature verification                    │  │
│  │  - Rate limiting                                     │  │
│  │  - Event routing                                     │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                   │
│  ┌──────────────────────▼───────────────────────────────┐  │
│  │              SlackEventHandler                       │  │
│  │  - Parse slash commands                             │  │
│  │  - Handle button interactions                       │  │
│  │  - Format responses                                 │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                   │
│  ┌──────────────────────▼───────────────────────────────┐  │
│  │              SlackClient (SDK Wrapper)               │  │
│  │  - Post messages                                     │  │
│  │  - Update messages                                   │  │
│  │  - Send ephemeral messages                          │  │
│  │  - Thread management                                │  │
│  └──────────────────────┬───────────────────────────────┘  │
└──────────────────────────┼───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  Existing NightShift Core                    │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐  │
│  │ TaskQueue  │  │TaskPlanner │  │   AgentManager       │  │
│  │            │  │            │  │                      │  │
│  │ - CRUD ops │  │ - Plan     │  │ - Execute            │  │
│  │ - Status   │  │ - Estimate │  │ - Pause/Resume/Kill  │  │
│  │ - Logging  │  │ - Revise   │  │ - Stream output      │  │
│  └────────────┘  └────────────┘  └──────────────────────┘  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │              Notifier (Extended)                     │  │
│  │  - Terminal display (existing)                       │  │
│  │  - Slack notifications (NEW)                         │  │
│  │  - Format for Block Kit                             │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow Examples

#### Flow 1: Task Submission
```
User types: /nightshift submit "analyze arxiv paper 2501.12345"
    ↓
Slack → POST /slack/commands (webhook)
    ↓
SlackWebhookServer validates signature
    ↓
SlackEventHandler.handle_submit()
    ↓
TaskPlanner.plan_task() [30-120s async]
    ↓
TaskQueue.create_task() → STAGED
    ↓
SlackClient.post_message() with approval buttons
    ↓
User sees interactive message in Slack
```

#### Flow 2: Approval Workflow
```
User clicks "Approve" button
    ↓
Slack → POST /slack/interactions (webhook)
    ↓
SlackEventHandler.handle_approval()
    ↓
TaskQueue.update_status() → COMMITTED
    ↓
AgentManager.execute_task() [async]
    ↓
[Task executes, streams output to file]
    ↓
Notifier.notify() [on completion]
    ↓
SlackClient.post_message() with results
    ↓
User sees completion notification in thread
```

#### Flow 3: Status Monitoring
```
During execution:
    AgentManager updates task.result_path in real-time
    ↓
Periodic status checker (optional):
    TaskQueue.get_task()
    ↓
    If status changed → SlackClient.update_message()
```

---

## Sub-Task Breakdown

### Phase 1: Foundation (Week 1-2)

#### Sub-Task 1.1: Configuration & Secrets Management
**Complexity:** Low
**Duration:** 2-3 hours
**Dependencies:** None

**Objectives:**
- Add Slack configuration to `nightshift/core/config.py`
- Support environment variables and config file
- Secure storage for bot tokens and signing secrets

**Files to Create/Modify:**
- `nightshift/core/config.py` (modify)
- `.env.example` (create)
- `nightshift/config/slack_config.example.json` (create)

**Configuration Schema:**
```python
class SlackConfig:
    bot_token: str          # xoxb-...
    signing_secret: str     # From Slack App settings
    app_token: str          # For Socket Mode (optional)
    webhook_port: int       # Default: 5000
    webhook_host: str       # Default: 0.0.0.0
    enable_threads: bool    # Use threads for conversations
    default_channel: str    # Fallback channel ID
```

**Testing:**
- Validate token format
- Test config loading from env/file
- Verify secret masking in logs

---

#### Sub-Task 1.2: Slack Client Wrapper
**Complexity:** Low-Medium
**Duration:** 4-6 hours
**Dependencies:** 1.1

**Objectives:**
- Create abstraction layer over Slack SDK
- Implement core messaging operations
- Error handling and retry logic

**Files to Create:**
- `nightshift/integrations/__init__.py`
- `nightshift/integrations/slack_client.py`

**Core Methods:**
```python
class SlackClient:
    def __init__(self, bot_token: str):
        self.client = WebClient(token=bot_token)

    def post_message(
        self,
        channel: str,
        text: str,
        blocks: List[Dict] = None,
        thread_ts: str = None
    ) -> SlackResponse

    def update_message(
        self,
        channel: str,
        ts: str,
        text: str,
        blocks: List[Dict] = None
    ) -> SlackResponse

    def post_ephemeral(
        self,
        channel: str,
        user: str,
        text: str
    ) -> SlackResponse

    def upload_file(
        self,
        channel: str,
        file_path: str,
        title: str = None,
        thread_ts: str = None
    ) -> SlackResponse
```

**Error Handling:**
- Rate limit detection and backoff
- Token expiration handling
- Network failure retries (exponential backoff)
- Graceful degradation (log errors, don't crash)

**Testing:**
- Mock Slack API responses
- Test retry logic
- Validate error handling

---

#### Sub-Task 1.3: Webhook Server Infrastructure
**Complexity:** Medium
**Duration:** 6-8 hours
**Dependencies:** 1.1, 1.2

**Objectives:**
- Set up Flask/FastAPI webhook server
- Implement Slack signature verification
- Route incoming events to handlers
- Add rate limiting

**Files to Create:**
- `nightshift/integrations/slack_server.py`
- `nightshift/integrations/slack_middleware.py`

**Server Structure:**
```python
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/slack/commands', methods=['POST'])
def handle_commands():
    # Verify signature
    if not verify_slack_signature(request):
        return jsonify({"error": "Invalid signature"}), 401

    # Parse command
    command = request.form.get('command')
    text = request.form.get('text')
    user_id = request.form.get('user_id')
    channel_id = request.form.get('channel_id')

    # Route to handler
    if command == '/nightshift':
        return handle_nightshift_command(text, user_id, channel_id)

    return jsonify({"error": "Unknown command"}), 400

@app.route('/slack/interactions', methods=['POST'])
def handle_interactions():
    # Verify signature
    if not verify_slack_signature(request):
        return jsonify({"error": "Invalid signature"}), 401

    # Parse interaction payload
    payload = json.loads(request.form.get('payload'))

    # Route based on action
    return handle_button_click(payload)
```

**Signature Verification:**
```python
def verify_slack_signature(request) -> bool:
    timestamp = request.headers.get('X-Slack-Request-Timestamp')
    signature = request.headers.get('X-Slack-Signature')

    # Prevent replay attacks (timestamp > 5 min old)
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    # Verify HMAC signature
    sig_basestring = f"v0:{timestamp}:{request.get_data().decode()}"
    expected_sig = 'v0=' + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_sig, signature)
```

**Rate Limiting:**
- Use Flask-Limiter or custom middleware
- Per-user limits (e.g., 10 requests/minute)
- Per-endpoint limits
- Return 429 with Retry-After header

**Testing:**
- Test signature verification with valid/invalid signatures
- Test rate limiting behavior
- Mock Slack payload formats

---

#### Sub-Task 1.4: Event Handler Core
**Complexity:** Medium
**Duration:** 8-10 hours
**Dependencies:** 1.1, 1.2, 1.3

**Objectives:**
- Create event routing and handling logic
- Map Slack commands to NightShift operations
- Format responses for Slack (text + blocks)

**Files to Create:**
- `nightshift/integrations/slack_handler.py`
- `nightshift/integrations/slack_formatter.py`

**Handler Structure:**
```python
class SlackEventHandler:
    def __init__(
        self,
        slack_client: SlackClient,
        task_queue: TaskQueue,
        task_planner: TaskPlanner,
        agent_manager: AgentManager,
        logger: NightShiftLogger
    ):
        self.slack = slack_client
        self.task_queue = task_queue
        self.task_planner = task_planner
        self.agent_manager = agent_manager
        self.logger = logger

    def handle_submit(
        self,
        text: str,
        user_id: str,
        channel_id: str
    ) -> Dict:
        """Handle /nightshift submit command"""
        # Acknowledge immediately (Slack 3s timeout)
        response = {"response_type": "ephemeral", "text": "Planning task..."}

        # Start async planning
        threading.Thread(
            target=self._plan_and_stage_task,
            args=(text, user_id, channel_id)
        ).start()

        return response

    def _plan_and_stage_task(
        self,
        description: str,
        user_id: str,
        channel_id: str
    ):
        """Async task planning and staging"""
        try:
            # Plan task (can take 30-120s)
            plan = self.task_planner.plan_task(description)

            # Create task in STAGED state
            task_id = f"task_{uuid.uuid4().hex[:8]}"
            task = self.task_queue.create_task(
                task_id=task_id,
                description=plan['enhanced_prompt'],
                allowed_tools=plan['allowed_tools'],
                allowed_directories=plan['allowed_directories'],
                needs_git=plan.get('needs_git', False),
                system_prompt=plan['system_prompt'],
                estimated_tokens=plan['estimated_tokens'],
                estimated_time=plan['estimated_time']
            )

            # Store Slack metadata
            self._store_slack_metadata(task_id, user_id, channel_id)

            # Send approval message with buttons
            blocks = self._format_approval_message(task, plan)
            self.slack.post_message(
                channel=channel_id,
                text=f"Task {task_id} ready for approval",
                blocks=blocks
            )

        except Exception as e:
            self.logger.error(f"Task planning failed: {e}")
            self.slack.post_message(
                channel=channel_id,
                text=f"❌ Task planning failed: {str(e)}"
            )

    def handle_approval(
        self,
        task_id: str,
        user_id: str,
        channel_id: str,
        message_ts: str,
        action: str  # "approve" or "reject"
    ):
        """Handle approval button click"""
        if action == "approve":
            # Update task status
            self.task_queue.update_status(task_id, TaskStatus.COMMITTED)

            # Update Slack message to show "Executing..."
            self.slack.update_message(
                channel=channel_id,
                ts=message_ts,
                text=f"✅ Task {task_id} approved by <@{user_id}>",
                blocks=[{"type": "section", "text": {"type": "mrkdwn", "text": f"⏳ Executing task {task_id}..."}}]
            )

            # Start execution async
            task = self.task_queue.get_task(task_id)
            threading.Thread(
                target=self._execute_and_notify,
                args=(task, channel_id, message_ts)
            ).start()

        elif action == "reject":
            self.task_queue.update_status(task_id, TaskStatus.CANCELLED)
            self.slack.update_message(
                channel=channel_id,
                ts=message_ts,
                text=f"❌ Task {task_id} rejected by <@{user_id}>"
            )
```

**Formatter for Block Kit:**
```python
class SlackFormatter:
    @staticmethod
    def format_approval_message(task: Task, plan: Dict) -> List[Dict]:
        """Format task plan as interactive Slack message"""
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"🎯 Task Plan: {task.task_id}"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Description:*\n{task.description[:500]}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Tools:*\n{', '.join(task.allowed_tools[:5])}"},
                    {"type": "mrkdwn", "text": f"*Estimated:*\n~{task.estimated_tokens} tokens, ~{task.estimated_time}s"}
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ Approve"},
                        "style": "primary",
                        "action_id": f"approve_{task.task_id}",
                        "value": task.task_id
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Reject"},
                        "style": "danger",
                        "action_id": f"reject_{task.task_id}",
                        "value": task.task_id
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "ℹ️ Details"},
                        "action_id": f"details_{task.task_id}",
                        "value": task.task_id
                    }
                ]
            }
        ]
        return blocks

    @staticmethod
    def format_completion_notification(summary: Dict) -> List[Dict]:
        """Format task completion as Slack blocks"""
        status_emoji = "✅" if summary['status'] == "success" else "❌"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{status_emoji} Task Completed: {summary['task_id']}"
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Status:*\n{summary['status'].upper()}"},
                    {"type": "mrkdwn", "text": f"*Execution Time:*\n{summary['execution_time']:.1f}s"}
                ]
            }
        ]

        # Add file changes if any
        file_changes = summary['file_changes']
        if any(file_changes.values()):
            changes_text = ""
            if file_changes['created']:
                changes_text += f"*Created:* {len(file_changes['created'])} files\n"
            if file_changes['modified']:
                changes_text += f"*Modified:* {len(file_changes['modified'])} files\n"

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": changes_text}
            })

        return blocks
```

**Testing:**
- Unit tests for each handler method
- Mock Slack client responses
- Test async execution paths
- Validate Block Kit formatting

---

### Phase 1: Implementation (Week 2)

#### Sub-Task 1.5: Notifier Extension for Slack
**Complexity:** Low-Medium
**Duration:** 4-6 hours
**Dependencies:** 1.1, 1.2, 1.4

**Objectives:**
- Extend `Notifier` class to send Slack messages
- Integrate with existing notification flow
- Support both terminal and Slack outputs

**Files to Modify:**
- `nightshift/core/notifier.py`

**Changes:**
```python
class Notifier:
    def __init__(
        self,
        notification_dir: str = "notifications",
        slack_client: Optional[SlackClient] = None,
        slack_metadata_store: Optional[SlackMetadataStore] = None
    ):
        self.notification_dir = Path(notification_dir)
        self.notification_dir.mkdir(parents=True, exist_ok=True)
        self.console = Console()
        self.slack_client = slack_client
        self.slack_metadata = slack_metadata_store

    def notify(
        self,
        task_id: str,
        task_description: str,
        success: bool,
        execution_time: float,
        token_usage: Optional[int],
        file_changes: List[FileChange],
        error_message: Optional[str] = None,
        result_path: Optional[str] = None
    ):
        """Send notification about task completion"""
        summary = self.generate_summary(...)

        # Save to file (existing)
        self._save_notification(summary)

        # Display in terminal (existing)
        self._display_terminal(summary)

        # Send to Slack if configured
        if self.slack_client and self.slack_metadata:
            try:
                self._send_slack(summary)
            except Exception as e:
                self.console.print(f"[yellow]Warning: Slack notification failed: {e}[/yellow]")

    def _send_slack(self, summary: Dict[str, Any]):
        """Send notification to Slack"""
        # Get Slack metadata for this task
        metadata = self.slack_metadata.get(summary['task_id'])
        if not metadata:
            return

        # Format as Block Kit
        blocks = SlackFormatter.format_completion_notification(summary)

        # Send to original channel/thread
        self.slack_client.post_message(
            channel=metadata['channel_id'],
            text=f"Task {summary['task_id']} completed",
            blocks=blocks,
            thread_ts=metadata.get('thread_ts')
        )
```

**Metadata Storage:**
- Store Slack context for each task (channel, thread, user)
- Simple JSON file or SQLite table extension
- Clean up after completion notification sent

**Testing:**
- Test with and without Slack configured
- Verify fallback to terminal-only
- Test thread vs. channel posting

---

#### Sub-Task 1.6: Slash Command Registration
**Complexity:** Low
**Duration:** 2-3 hours
**Dependencies:** 1.3, 1.4

**Objectives:**
- Register slash commands in Slack App settings
- Configure webhook URLs
- Test end-to-end command flow

**Slash Commands to Register:**
1. `/nightshift submit [description]`
   - Command: `/nightshift`
   - Request URL: `https://your-domain.com/slack/commands`
   - Short Description: "Submit a NightShift task"
   - Usage Hint: `submit "task description"`

2. Future commands (Phase 2+):
   - `/nightshift queue`
   - `/nightshift status [task_id]`
   - `/nightshift cancel [task_id]`

**Webhook Configuration:**
- Interactivity & Shortcuts → Request URL: `https://your-domain.com/slack/interactions`
- Enable "Interactivity" for buttons

**Testing:**
- Test command in Slack workspace
- Verify payload format matches expectations
- Test with various input formats

---

#### Sub-Task 1.7: CLI Command for Server Management
**Complexity:** Low
**Duration:** 2-3 hours
**Dependencies:** 1.3

**Objectives:**
- Add CLI command to start/stop Slack server
- Support daemon mode for production
- Integrate with existing CLI structure

**Files to Modify:**
- `nightshift/interfaces/cli.py`

**New Commands:**
```python
@cli.command()
@click.option('--port', default=5000, help='Port to run server on')
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--daemon', is_flag=True, help='Run in background')
@click.pass_context
def slack_server(ctx, port, host, daemon):
    """Start Slack webhook server"""
    config = ctx.obj['config']

    if not config.slack_enabled:
        console.print("[red]Slack integration not configured[/red]")
        console.print("Run 'nightshift slack-setup' to configure")
        raise click.Abort()

    from ..integrations.slack_server import app

    if daemon:
        # Run in background using subprocess
        console.print(f"Starting Slack server on {host}:{port} (daemon mode)")
        # Implementation...
    else:
        console.print(f"Starting Slack server on {host}:{port}")
        console.print("Press Ctrl+C to stop")
        app.run(host=host, port=port)

@cli.command()
@click.pass_context
def slack_setup(ctx):
    """Interactive Slack integration setup"""
    console.print("[bold]NightShift Slack Integration Setup[/bold]\n")

    # Prompt for bot token
    bot_token = click.prompt("Enter Slack Bot Token (xoxb-...)")
    signing_secret = click.prompt("Enter Slack Signing Secret")

    # Save to config
    config = ctx.obj['config']
    config.set_slack_config(
        bot_token=bot_token,
        signing_secret=signing_secret
    )

    console.print("\n[green]✓ Slack configuration saved![/green]")
    console.print("\nNext steps:")
    console.print("1. Run 'nightshift slack-server' to start webhook server")
    console.print("2. Configure Slack App slash commands to point to your webhook URL")
    console.print("3. Test with /nightshift submit in Slack")
```

**Testing:**
- Test server start/stop
- Test daemon mode
- Test interactive setup

---

#### Sub-Task 1.8: Documentation & Examples
**Complexity:** Low
**Duration:** 3-4 hours
**Dependencies:** All Phase 1 tasks

**Objectives:**
- Document Slack setup process
- Provide configuration examples
- Create troubleshooting guide

**Files to Create:**
- `docs/slack-integration-setup.md`
- `docs/slack-troubleshooting.md`
- Update `README.md` with Slack section

**Documentation Sections:**
1. Prerequisites (Slack workspace admin access)
2. Slack App creation and configuration
3. Bot token and signing secret setup
4. Webhook URL configuration (ngrok for development)
5. Testing slash commands
6. Common issues and solutions

---

### Phase 2: Interactive Features (Week 3)

#### Sub-Task 2.1: Additional Slash Commands
**Complexity:** Medium
**Duration:** 6-8 hours
**Dependencies:** Phase 1 complete

**Commands to Implement:**
- `/nightshift queue [status]` - View task queue
- `/nightshift status [task_id]` - Check task status
- `/nightshift cancel [task_id]` - Cancel a task
- `/nightshift pause [task_id]` - Pause running task
- `/nightshift resume [task_id]` - Resume paused task
- `/nightshift kill [task_id]` - Kill running task

**Implementation Pattern:**
- Each command follows same structure as `handle_submit`
- Map directly to existing `AgentManager` methods
- Format responses using Block Kit
- Handle errors gracefully

---

#### Sub-Task 2.2: Thread-Based Conversations
**Complexity:** Medium
**Duration:** 4-6 hours
**Dependencies:** Phase 1 complete

**Objectives:**
- Post approval messages as thread parents
- Send status updates in threads
- Post completion notifications in threads
- Keep channel clean (less noise)

**Changes:**
- Store `message_ts` from initial post
- Use `thread_ts` parameter in follow-up messages
- Update SlackMetadataStore to track threads

---

#### Sub-Task 2.3: Real-Time Progress Updates
**Complexity:** High
**Duration:** 10-12 hours
**Dependencies:** 2.2

**Objectives:**
- Stream execution progress to Slack
- Update message with current status
- Show tool calls and intermediate results

**Design:**
- Modify `AgentManager` to publish progress events
- Create progress monitor that polls task output file
- Update Slack message periodically (avoid rate limits)
- Use progress bar emoji or percentage

**Example Progress Message:**
```
⏳ Task task_abc123 executing...
━━━━━━━━━━━━━━━━━━━━━━ 60% (3/5 tools)

Recent activity:
✓ Downloaded ArXiv paper
✓ Extracted text content
⏳ Summarizing with Gemini...
```

---

#### Sub-Task 2.4: Revision Workflow
**Complexity:** Medium
**Duration:** 6-8 hours
**Dependencies:** Phase 1 complete

**Objectives:**
- Add "Revise" button to approval message
- Open modal for feedback input
- Re-plan task with feedback
- Show updated plan for approval

**Implementation:**
- Use Slack modals (Block Kit)
- Handle modal submission
- Call `TaskPlanner.refine_plan()`
- Update original message with revised plan

---

### Phase 3: Advanced Features (Week 4+)

#### Sub-Task 3.1: File Upload Support
**Complexity:** Medium-High
**Duration:** 8-10 hours
**Dependencies:** Phase 2 complete

**Objectives:**
- Upload task output files to Slack
- Support PDF, MD, JSON, CSV formats
- Add download links to notifications

**Considerations:**
- File size limits (Slack free: 5GB total, individual limits vary)
- Privacy concerns (who can access?)
- Storage costs
- Alternative: Provide local file paths only

---

#### Sub-Task 3.2: Multi-User & Authorization
**Complexity:** High
**Duration:** 12-15 hours
**Dependencies:** Phase 1 complete

**Objectives:**
- Map Slack user IDs to NightShift users
- Implement permission levels (admin, user, viewer)
- Restrict sensitive operations
- Audit log for user actions

**Design:**
- User mapping table in database
- Role-based access control (RBAC)
- Per-task ownership
- Admin-only commands (kill, clear)

---

#### Sub-Task 3.3: Multi-Channel Support
**Complexity:** Medium
**Duration:** 6-8 hours
**Dependencies:** Phase 1 complete

**Objectives:**
- Support task submission from any channel
- Route notifications to original channel
- Support DMs (direct messages)
- Channel-specific settings

---

#### Sub-Task 3.4: Rich Formatting & Visualizations
**Complexity:** Medium
**Duration:** 8-10 hours
**Dependencies:** Phase 2 complete

**Objectives:**
- Enhanced Block Kit layouts
- Emoji-rich status indicators
- Inline code blocks for errors
- Chart images for token usage trends

---

## Implementation Roadmap

### Week 1: Foundation Setup

**Days 1-2:**
- ✅ Create feature branch
- ✅ Analyze existing architecture (this document)
- [ ] Sub-Task 1.1: Configuration & Secrets Management
- [ ] Sub-Task 1.2: Slack Client Wrapper

**Days 3-4:**
- [ ] Sub-Task 1.3: Webhook Server Infrastructure
- [ ] Begin Sub-Task 1.4: Event Handler Core

**Day 5:**
- [ ] Complete Sub-Task 1.4: Event Handler Core
- [ ] Code review and refactoring

### Week 2: Core Integration

**Days 1-2:**
- [ ] Sub-Task 1.5: Notifier Extension for Slack
- [ ] Sub-Task 1.6: Slash Command Registration
- [ ] End-to-end testing

**Days 3-4:**
- [ ] Sub-Task 1.7: CLI Command for Server Management
- [ ] Sub-Task 1.8: Documentation & Examples
- [ ] Integration testing

**Day 5:**
- [ ] Bug fixes and polish
- [ ] Prepare for Phase 1 demo
- [ ] User acceptance testing

### Week 3: Interactive Features (Phase 2)

**Days 1-2:**
- [ ] Sub-Task 2.1: Additional Slash Commands
- [ ] Sub-Task 2.2: Thread-Based Conversations

**Days 3-5:**
- [ ] Sub-Task 2.3: Real-Time Progress Updates
- [ ] Sub-Task 2.4: Revision Workflow
- [ ] Testing and refinement

### Week 4+: Advanced Features (Phase 3)

**Flexible timeline based on priority:**
- [ ] Sub-Task 3.1: File Upload Support
- [ ] Sub-Task 3.2: Multi-User & Authorization
- [ ] Sub-Task 3.3: Multi-Channel Support
- [ ] Sub-Task 3.4: Rich Formatting & Visualizations

---

## Security Considerations

### 1. Request Signature Verification

**Critical:** Always verify Slack request signatures to prevent spoofing.

```python
def verify_slack_signature(request, signing_secret: str) -> bool:
    """Verify that request came from Slack"""
    timestamp = request.headers.get('X-Slack-Request-Timestamp')
    signature = request.headers.get('X-Slack-Signature')

    if not timestamp or not signature:
        return False

    # Prevent replay attacks
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{request.get_data().decode()}"
    expected_sig = 'v0=' + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_sig, signature)
```

### 2. Token Storage

**Best Practices:**
- Store bot tokens in environment variables
- Never commit tokens to version control
- Use `.env` file for local development
- Rotate tokens periodically
- Restrict token scopes to minimum required

**Example `.env`:**
```bash
NIGHTSHIFT_SLACK_BOT_TOKEN=xoxb-your-token-here
NIGHTSHIFT_SLACK_SIGNING_SECRET=your-signing-secret
NIGHTSHIFT_SLACK_APP_TOKEN=xapp-your-app-token  # Optional, for Socket Mode
```

### 3. Rate Limiting

**Implement multi-level rate limiting:**

1. **Per-User Limits:**
   - 10 task submissions per minute
   - 20 status checks per minute
   - 5 task approvals per minute

2. **Per-Endpoint Limits:**
   - `/slack/commands`: 100 requests/minute
   - `/slack/interactions`: 200 requests/minute

3. **Slack API Limits:**
   - Respect Slack's Tier 1/2/3/4 rate limits
   - Implement exponential backoff for 429 responses
   - Queue messages if approaching limits

**Implementation:**
```python
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    app,
    key_func=lambda: request.form.get('user_id', get_remote_address()),
    default_limits=["100 per minute"]
)

@app.route('/slack/commands', methods=['POST'])
@limiter.limit("10 per minute")
def handle_commands():
    ...
```

### 4. Authorization & User Mapping

**Phase 1:** Simple user ID tracking
- Store Slack user ID with each task
- Display user who submitted/approved task
- No permission checks yet

**Phase 2+:** Role-based access control
- Admin: All operations (kill, clear, configure)
- User: Submit, approve own tasks, cancel own tasks
- Viewer: Read-only (queue, status, results)

**User Mapping Table:**
```sql
CREATE TABLE slack_users (
    slack_user_id TEXT PRIMARY KEY,
    slack_username TEXT,
    role TEXT DEFAULT 'user',  -- 'admin', 'user', 'viewer'
    created_at TEXT NOT NULL
);
```

### 5. Sensitive Output Protection

**Risks:**
- Task outputs may contain API keys, secrets, credentials
- Public channels expose data to all members
- Logs may leak sensitive information

**Mitigations:**
1. **Redaction:**
   - Scan outputs for common secret patterns
   - Redact before posting to Slack
   - Regex patterns: API keys, tokens, passwords

2. **Channel Restrictions:**
   - Recommend private channels for sensitive tasks
   - Ephemeral messages for intermediate results
   - DM-only mode for high-security environments

3. **Output Truncation:**
   - Limit Slack message length (3000 chars)
   - Provide "View Full Output" link to local file
   - Never post full error stack traces

**Redaction Example:**
```python
import re

REDACTION_PATTERNS = [
    (r'sk-[a-zA-Z0-9]{48}', '***REDACTED_OPENAI_KEY***'),
    (r'xox[baprs]-[a-zA-Z0-9-]+', '***REDACTED_SLACK_TOKEN***'),
    (r'ghp_[a-zA-Z0-9]{36}', '***REDACTED_GITHUB_TOKEN***'),
    (r'[A-Za-z0-9+/]{40}', '***REDACTED_SECRET***'),  # Base64 secrets
]

def redact_sensitive_data(text: str) -> str:
    for pattern, replacement in REDACTION_PATTERNS:
        text = re.sub(pattern, replacement, text)
    return text
```

### 6. Audit Logging

**Log all security-relevant events:**
- User authentication attempts
- Command executions with parameters
- Approval/rejection actions
- Permission denied events
- Configuration changes

**Log Format:**
```python
{
    "timestamp": "2024-11-25T10:30:00Z",
    "event_type": "task_submission",
    "user_id": "U123456",
    "channel_id": "C789012",
    "task_id": "task_abc123",
    "action": "submit",
    "ip_address": "192.168.1.1",
    "user_agent": "Slackbot"
}
```

---

## Testing Strategy

### Unit Tests

**Test Coverage Goals:**
- 80%+ code coverage for new modules
- 100% coverage for security-critical functions

**Key Test Suites:**

1. **Slack Client Tests** (`tests/test_slack_client.py`)
   - Mock Slack API responses
   - Test error handling and retries
   - Validate request formatting

2. **Event Handler Tests** (`tests/test_slack_handler.py`)
   - Mock task queue, planner, agent manager
   - Test command parsing
   - Validate response formatting

3. **Webhook Server Tests** (`tests/test_slack_server.py`)
   - Test signature verification with valid/invalid signatures
   - Test rate limiting behavior
   - Test request routing

4. **Formatter Tests** (`tests/test_slack_formatter.py`)
   - Validate Block Kit JSON structure
   - Test edge cases (long text, special characters)
   - Test all message types

**Example Test:**
```python
import pytest
from unittest.mock import Mock, patch
from nightshift.integrations.slack_handler import SlackEventHandler

def test_handle_submit_success(mock_slack_client, mock_task_planner):
    handler = SlackEventHandler(
        slack_client=mock_slack_client,
        task_queue=Mock(),
        task_planner=mock_task_planner,
        agent_manager=Mock(),
        logger=Mock()
    )

    response = handler.handle_submit(
        text="analyze arxiv paper 2501.12345",
        user_id="U123",
        channel_id="C456"
    )

    assert response["response_type"] == "ephemeral"
    assert "Planning task" in response["text"]
```

### Integration Tests

**Test Scenarios:**

1. **End-to-End Task Submission:**
   ```
   User → /nightshift submit → Webhook → Handler → TaskPlanner
   → TaskQueue → Slack Approval Message
   ```

2. **Approval Workflow:**
   ```
   User → Click Approve → Webhook → Handler → AgentManager
   → Task Execution → Notifier → Slack Completion Message
   ```

3. **Error Handling:**
   - Planning timeout → Error message to user
   - Execution failure → Error notification
   - Network error → Retry logic

**Integration Test Environment:**
- Use Slack test workspace
- Mock external MCP servers (ArXiv, Gemini, etc.)
- Isolated test database

### Manual Testing Checklist

**Phase 1 Acceptance Criteria:**

- [ ] Slack app installed in test workspace
- [ ] Slash command `/nightshift submit` works
- [ ] Task planning completes (30-120s)
- [ ] Approval message appears with buttons
- [ ] "Approve" button triggers execution
- [ ] "Reject" button cancels task
- [ ] Completion notification appears in Slack
- [ ] Terminal output still works (backward compatibility)
- [ ] Server starts via `nightshift slack-server`
- [ ] Rate limiting prevents abuse
- [ ] Signature verification blocks invalid requests

**Phase 2 Acceptance Criteria:**

- [ ] Additional slash commands work (queue, status, cancel)
- [ ] Thread-based conversations keep channels clean
- [ ] Real-time progress updates appear
- [ ] Revision workflow allows feedback and re-planning

### Performance Testing

**Load Tests:**
- Simulate 10 concurrent task submissions
- Measure planning time under load
- Test rate limiting effectiveness

**Stress Tests:**
- Submit 100 tasks in quick succession
- Verify queue doesn't corrupt
- Check for memory leaks in long-running server

---

## Scalability Considerations

### 1. Async Task Processing

**Current Limitation:**
- Task planning blocks for 30-120 seconds
- Slack expects response within 3 seconds

**Solution:**
- Immediate acknowledgment response
- Background thread for planning/execution
- Callback-based updates to Slack

**Implementation:**
```python
def handle_submit(self, text, user_id, channel_id):
    # Immediate response (< 3s)
    response = {"response_type": "ephemeral", "text": "🔄 Planning task..."}

    # Background processing
    threading.Thread(
        target=self._plan_and_stage_task,
        args=(text, user_id, channel_id),
        daemon=True
    ).start()

    return response
```

**Future Enhancement:** Task queue with worker pool
- Use Celery or RQ for distributed task processing
- Multiple workers handle planning/execution
- Redis for job queue

### 2. Multi-Instance Support

**Challenge:** Multiple Slack server instances need shared state

**Requirements:**
- Shared task queue (already SQLite-based, can migrate to PostgreSQL)
- Shared Slack metadata store
- Coordinated webhook routing

**Solutions:**

**Option A: Single instance with load balancer**
- Run one `nightshift slack-server` instance
- Use nginx/HAProxy for SSL termination and load balancing
- Simple but single point of failure

**Option B: Multi-instance with shared database**
- Migrate from SQLite to PostgreSQL
- Multiple server instances read/write same database
- Use advisory locks for critical sections
- Requires distributed locking for process management (pause/resume/kill)

**Option C: Hybrid with leader election**
- Multiple instances, one leader handles execution
- Leader election via Redis or etcd
- Followers handle webhooks, leader executes tasks

### 3. Database Optimization

**Current:** SQLite at `~/.nightshift/database/nightshift.db`

**Scaling Path:**
1. **Phase 1:** SQLite (sufficient for single user, < 1000 tasks)
2. **Phase 2:** PostgreSQL (multi-user, > 1000 tasks)
3. **Phase 3:** Distributed database (e.g., CockroachDB for geo-distribution)

**Indexes to Add:**
```sql
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at DESC);
CREATE INDEX idx_tasks_user_id ON tasks(user_id);  -- Phase 2+
CREATE INDEX idx_task_logs_task_id ON task_logs(task_id);
```

### 4. Notification Queue

**Current:** Synchronous notification sending in `AgentManager.execute_task()`

**Problem:** Slow Slack API calls block task completion

**Solution:** Message queue for notifications
```python
class NotificationQueue:
    def __init__(self):
        self.queue = queue.Queue()
        self.worker = threading.Thread(target=self._process_queue, daemon=True)
        self.worker.start()

    def enqueue(self, notification: Dict):
        self.queue.put(notification)

    def _process_queue(self):
        while True:
            notification = self.queue.get()
            try:
                self.slack_client.post_message(...)
            except Exception as e:
                self.logger.error(f"Notification failed: {e}")
            finally:
                self.queue.task_done()
```

### 5. Caching

**Opportunities:**
- Cache Slack user info (username, real_name)
- Cache channel metadata (name, topic)
- Cache plan templates for common task types

**Implementation:**
```python
from functools import lru_cache
import time

@lru_cache(maxsize=1000)
def get_slack_user_info(user_id: str) -> Dict:
    # Cache for 1 hour
    response = slack_client.users_info(user=user_id)
    return response['user']
```

### 6. Monitoring & Observability

**Metrics to Track:**
- Task submission rate (tasks/minute)
- Task completion rate
- Average planning time
- Average execution time
- Error rate by type
- Slack API latency
- Webhook response time

**Tools:**
- Prometheus for metrics collection
- Grafana for visualization
- Sentry for error tracking
- Structured logging (JSON format)

**Example Metrics:**
```python
from prometheus_client import Counter, Histogram

task_submissions = Counter('nightshift_task_submissions_total', 'Total task submissions')
task_completions = Counter('nightshift_task_completions_total', 'Total task completions', ['status'])
planning_duration = Histogram('nightshift_planning_duration_seconds', 'Task planning duration')
```

### 7. Rate Limit Optimization

**Slack Rate Limits:**
- Tier 1: 1 request/second (Workspace-level)
- Tier 2: 20 requests/minute (Channel-level)
- Tier 3: 50 requests/minute (User-level)
- Tier 4: No limit (Batch methods)

**Strategies:**
1. **Message Batching:**
   - Combine multiple updates into single message
   - Update message in-place instead of new messages

2. **Smart Update Frequency:**
   - Throttle progress updates (max 1 per 5 seconds)
   - Skip updates if no meaningful change

3. **Retry with Exponential Backoff:**
   ```python
   def post_with_retry(self, channel, text, max_retries=3):
       for attempt in range(max_retries):
           try:
               return self.client.chat_postMessage(channel=channel, text=text)
           except SlackApiError as e:
               if e.response['error'] == 'rate_limited':
                   delay = e.response.headers.get('Retry-After', 2 ** attempt)
                   time.sleep(int(delay))
               else:
                   raise
   ```

---

## Appendix: Key Files Summary

### New Files to Create

| File Path | Purpose | Complexity |
|-----------|---------|------------|
| `nightshift/integrations/__init__.py` | Package init | Trivial |
| `nightshift/integrations/slack_client.py` | Slack SDK wrapper | Medium |
| `nightshift/integrations/slack_server.py` | Flask webhook server | Medium |
| `nightshift/integrations/slack_handler.py` | Event handling logic | High |
| `nightshift/integrations/slack_formatter.py` | Block Kit formatting | Low |
| `nightshift/integrations/slack_middleware.py` | Auth, rate limiting | Medium |
| `nightshift/integrations/slack_metadata.py` | Task-Slack mapping store | Low |
| `tests/test_slack_client.py` | Unit tests | Medium |
| `tests/test_slack_handler.py` | Unit tests | Medium |
| `tests/test_slack_server.py` | Unit tests | Medium |
| `tests/test_slack_formatter.py` | Unit tests | Low |
| `docs/slack-integration-setup.md` | Setup guide | Low |
| `docs/slack-troubleshooting.md` | Troubleshooting | Low |
| `.env.example` | Config template | Trivial |

### Files to Modify

| File Path | Changes | Complexity |
|-----------|---------|------------|
| `nightshift/core/config.py` | Add Slack configuration | Low |
| `nightshift/core/notifier.py` | Add `_send_slack()` implementation | Medium |
| `nightshift/interfaces/cli.py` | Add `slack-server`, `slack-setup` commands | Low |
| `README.md` | Add Slack section | Low |
| `setup.py` | Add Slack dependencies | Trivial |

### Dependencies to Add

**Add to `setup.py`:**
```python
install_requires=[
    # ... existing dependencies ...
    'slack-sdk>=3.23.0',
    'flask>=3.0.0',
    'flask-limiter>=3.5.0',
    'python-dotenv>=1.0.0',  # For .env file support
]
```

---

## Conclusion

This plan provides a comprehensive, phased approach to integrating Slack API into NightShift. The implementation leverages existing architecture patterns (dependency injection, subprocess management, file tracking) and adds new components in a modular, testable way.

**Phase 1 (Weeks 1-2)** delivers the MVP: basic task submission and approval via Slack with completion notifications.

**Phase 2 (Week 3)** adds interactive features: additional commands, threads, real-time progress, and revision workflow.

**Phase 3 (Week 4+)** provides advanced capabilities: file uploads, multi-user support, rich formatting, and multi-channel support.

The design prioritizes:
- **Security:** Signature verification, rate limiting, authorization
- **Scalability:** Async processing, caching, monitoring
- **Maintainability:** Modular design, comprehensive testing, documentation
- **User Experience:** Fast responses, clear feedback, beautiful formatting

---

**Next Steps:**
1. Review and approve this plan
2. Set up development environment (Slack test workspace, ngrok)
3. Begin implementation with Sub-Task 1.1 (Configuration)
4. Iterate based on feedback and testing

**Questions for Discussion:**
- Preferred webhook server framework (Flask vs. FastAPI)?
- Hosting plan for production webhook server?
- Multi-user support priority (Phase 2 vs. Phase 3)?
- File upload requirements (size limits, storage location)?
