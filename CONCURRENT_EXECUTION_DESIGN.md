# Concurrent Task Execution Design

## Overview

This document outlines the design for implementing concurrent task submission and execution in NightShift, addressing issue #20.

## Current Limitations

1. **Single-threaded execution**: Only one task can execute at a time
2. **Blocking operations**: CLI commands and Slack handlers block during task execution
3. **No concurrent database access**: SQLite operations are not optimized for concurrent writes
4. **No execution queue management**: COMMITTED tasks must be manually executed one at a time

## Design Goals

1. Support multiple concurrent task submissions (both CLI and Slack)
2. Execute multiple approved tasks in parallel with configurable concurrency limits
3. Maintain thread-safe database operations
4. Preserve existing subprocess-based architecture (no async refactoring)
5. Provide clear status updates for concurrent operations

## Architecture

### 1. Task Executor Service

Create a new `TaskExecutor` service that runs as a background worker process:

```python
class TaskExecutor:
    """
    Background service that polls for COMMITTED tasks and executes them
    using a process pool.
    """
    def __init__(
        self,
        task_queue: TaskQueue,
        agent_manager: AgentManager,
        max_workers: int = 3,
        poll_interval: float = 1.0
    ):
        self.task_queue = task_queue
        self.agent_manager = agent_manager
        self.max_workers = max_workers
        self.poll_interval = poll_interval
        self.executor = ProcessPoolExecutor(max_workers=max_workers)
        self.running_tasks = {}  # task_id -> Future
        self.shutdown_event = threading.Event()

    def start(self):
        """Start the executor service"""

    def stop(self):
        """Gracefully shutdown the executor"""

    def _poll_and_execute(self):
        """Main polling loop"""

    def _execute_task_wrapper(self, task_id: str):
        """Wrapper for executing task in subprocess"""
```

**Key features:**
- Runs in separate daemon process/thread
- Polls database for tasks in COMMITTED state
- Submits tasks to ProcessPoolExecutor
- Tracks running tasks and updates status
- Respects max_workers limit for resource management

### 2. Thread-Safe Database Operations

Modify `TaskQueue` to support concurrent access:

```python
class TaskQueue:
    def __init__(self, db_path: str):
        self.db_path = db_path
        # Enable WAL mode for better concurrent access
        self._enable_wal_mode()

    def _get_connection(self):
        """Get a database connection with proper settings"""
        conn = sqlite3.connect(
            self.db_path,
            check_same_thread=False,  # Allow multi-thread access
            timeout=30.0,  # Wait up to 30s for lock
            isolation_level='DEFERRED'  # Reduce lock contention
        )
        return conn

    def _enable_wal_mode(self):
        """Enable Write-Ahead Logging for concurrent writes"""
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.commit()

    def acquire_task_for_execution(self) -> Optional[Task]:
        """
        Atomically get next COMMITTED task and mark as RUNNING
        Thread-safe for concurrent executor workers
        """
        with self._get_connection() as conn:
            conn.execute("BEGIN IMMEDIATE")  # Exclusive lock
            cursor = conn.execute("""
                SELECT task_id FROM tasks
                WHERE status = ?
                ORDER BY created_at ASC
                LIMIT 1
            """, (TaskStatus.COMMITTED.value,))

            row = cursor.fetchone()
            if not row:
                return None

            task_id = row[0]

            # Update to RUNNING
            now = datetime.now().isoformat()
            conn.execute("""
                UPDATE tasks
                SET status = ?, updated_at = ?, started_at = ?
                WHERE task_id = ?
            """, (TaskStatus.RUNNING.value, now, now, task_id))

            conn.commit()

        return self.get_task(task_id)
```

**Changes:**
- Enable SQLite WAL mode for concurrent writes
- Add `check_same_thread=False` to allow multi-thread access
- Add `timeout` parameter to handle lock waits gracefully
- Create `acquire_task_for_execution()` with atomic BEGIN IMMEDIATE transaction
- Use connection pooling pattern with context managers

### 3. CLI Integration

Update CLI commands to work with the executor service:

**Option A: Background Executor Process**
```bash
# Start executor daemon
nightshift executor start --workers 3

# Submit tasks (no longer blocks)
nightshift submit "task description"  # Returns immediately
nightshift submit "another task" --auto-approve  # Queues for execution

# Monitor
nightshift queue --status running
nightshift watch task_12345

# Stop executor
nightshift executor stop
```

**Option B: Inline Auto-Execution**
```bash
# Submit with auto-execute (spawns background thread)
nightshift submit "task" --auto-approve  # Returns after planning, executes in background

# Check status later
nightshift queue --status running
```

**Recommended: Hybrid Approach**
- Default: Use inline auto-execution with background threads for simple use cases
- Optional: Run dedicated executor service for production/server deployments
- Both use the same `TaskExecutor` class

### 4. Slack Integration

Update Slack handler to use non-blocking execution:

```python
def handle_approval(self, task_id: str, ...):
    """Handle approval button click"""
    task = self.task_queue.get_task(task_id)

    if action == "approve":
        # Update to COMMITTED (executor will pick it up)
        self.task_queue.update_status(task_id, TaskStatus.COMMITTED)

        # Update Slack message
        self.slack.update_message(
            channel=channel_id,
            ts=message_ts,
            text=f"✅ Task {task_id} approved and queued for execution",
            blocks=SlackFormatter.format_executing_message(task)
        )

        # Executor service will handle actual execution
        # Notifier will post results to Slack when complete
```

**Changes:**
- Remove synchronous `agent_manager.execute_task()` call from approval handler
- Rely on executor service to pick up COMMITTED tasks
- Update UI to show "queued for execution" state
- Use existing Notifier to post completion messages

### 5. Configuration

Add configuration options in `Config`:

```python
class Config:
    def __init__(self):
        # Existing config...

        # Concurrent execution settings
        self.max_concurrent_tasks = int(os.getenv('NIGHTSHIFT_MAX_WORKERS', 3))
        self.executor_poll_interval = float(os.getenv('NIGHTSHIFT_POLL_INTERVAL', 1.0))
        self.enable_auto_executor = os.getenv('NIGHTSHIFT_AUTO_EXECUTOR', 'true').lower() == 'true'
```

Environment variables:
- `NIGHTSHIFT_MAX_WORKERS`: Max concurrent task executions (default: 3)
- `NIGHTSHIFT_POLL_INTERVAL`: How often to poll for new tasks in seconds (default: 1.0)
- `NIGHTSHIFT_AUTO_EXECUTOR`: Auto-start executor service with CLI/Slack server (default: true)

## Implementation Plan

### Phase 1: Database Thread-Safety
1. Add WAL mode support to TaskQueue
2. Add `acquire_task_for_execution()` method
3. Add connection pooling pattern
4. Test concurrent task creation and status updates

### Phase 2: Task Executor Service
1. Create `TaskExecutor` class with ProcessPoolExecutor
2. Implement polling loop and task acquisition
3. Add graceful shutdown handling
4. Test with multiple concurrent tasks

### Phase 3: CLI Integration
1. Add `executor` command group (start/stop/status)
2. Update `submit --auto-approve` to use executor
3. Add `watch` command improvements for concurrent tasks
4. Add `queue` filtering for running tasks

### Phase 4: Slack Integration
1. Update approval handler to use COMMITTED status
2. Remove blocking execution from Slack handlers
3. Update Notifier to post Slack completions
4. Test concurrent Slack approvals

### Phase 5: Testing & Documentation
1. Test concurrent CLI submissions
2. Test concurrent Slack submissions
3. Test mixed CLI + Slack usage
4. Add integration tests
5. Update README and CLAUDE.md

## Migration Path

**Backwards Compatibility:**
- Existing single-task workflow still works
- `nightshift approve task_id` can optionally execute inline (without executor service)
- Executor service is opt-in via `--auto-approve` or `executor start`

**Configuration:**
- Default `NIGHTSHIFT_MAX_WORKERS=3` for safety
- Can be set to 1 to disable concurrency
- Can be increased on powerful machines

## Risks & Mitigations

**Risk: Database lock contention**
- Mitigation: WAL mode, proper timeouts, atomic transactions
- Fallback: Reduce max_workers if locks occur frequently

**Risk: Resource exhaustion (too many Claude processes)**
- Mitigation: Configurable max_workers limit
- Monitoring: Track process count and memory usage

**Risk: Orphaned processes on crash**
- Mitigation: Store PID in database, cleanup on startup
- Monitoring: `nightshift executor status` shows running processes

**Risk: Race conditions in task status**
- Mitigation: Atomic BEGIN IMMEDIATE transactions
- Testing: Concurrent stress tests

## Future Enhancements

1. **Priority queue**: Add priority field to tasks for urgent execution
2. **Resource-based scheduling**: Different pools for CPU vs I/O bound tasks
3. **Task dependencies**: Support task chains (task B runs after task A)
4. **Distributed execution**: Multiple executor services on different machines
5. **Real-time progress**: WebSocket support for live task updates
6. **Execution history**: Track task execution patterns and optimize scheduling

## References

- SQLite WAL mode: https://www.sqlite.org/wal.html
- concurrent.futures: https://docs.python.org/3/library/concurrent.futures.html
- Issue #20: Support concurrent task submission and execution
