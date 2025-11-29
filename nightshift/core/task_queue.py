"""
Task Queue Management for NightShift
Handles task creation, state transitions, and persistence
"""
import sqlite3
import json
from contextlib import contextmanager
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict


class TaskStatus(Enum):
    """Task lifecycle states"""
    STAGED = "staged"           # Created, awaiting approval
    COMMITTED = "committed"     # Approved, ready to execute
    RUNNING = "running"         # Currently executing
    PAUSED = "paused"           # Execution paused
    COMPLETED = "completed"     # Successfully finished
    FAILED = "failed"           # Execution failed
    CANCELLED = "cancelled"     # User cancelled


@dataclass
class Task:
    """Represents a research task"""
    task_id: str
    description: str
    status: str
    skill_name: Optional[str] = None
    allowed_tools: Optional[List[str]] = None
    allowed_directories: Optional[List[str]] = None  # Sandbox-allowed write directories
    needs_git: Optional[bool] = None  # Enable device file access for git operations
    system_prompt: Optional[str] = None
    timeout_seconds: Optional[int] = None  # Execution timeout (default: 900 = 15 mins)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result_path: Optional[str] = None
    error_message: Optional[str] = None
    token_usage: Optional[int] = None
    execution_time: Optional[float] = None  # seconds
    process_id: Optional[int] = None  # PID of Claude subprocess

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class TaskQueue:
    """SQLite-backed task queue with state management (thread-safe)"""

    def __init__(self, db_path: str = "database/nightshift.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
        self._enable_wal_mode()

    def _open_connection(self):
        """
        Open a raw database connection (caller must close)

        Returns:
            sqlite3.Connection with thread-safe settings
        """
        return sqlite3.connect(
            str(self.db_path),
            check_same_thread=False,  # Allow multi-thread access
            timeout=30.0,  # Wait up to 30s for database locks
            isolation_level='DEFERRED'  # Reduce lock contention
        )

    @contextmanager
    def _get_connection(self):
        """
        Context manager for database connections (auto-closes)

        Yields:
            sqlite3.Connection with thread-safe settings
        """
        conn = self._open_connection()
        try:
            yield conn
        finally:
            conn.close()

    def _enable_wal_mode(self):
        """
        Enable Write-Ahead Logging (WAL) mode for better concurrent access

        WAL mode allows multiple readers and one writer to access the database
        concurrently without blocking each other.
        """
        with self._get_connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.commit()

    def _init_db(self):
        """Initialize database schema"""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    skill_name TEXT,
                    allowed_tools TEXT,  -- JSON array
                    allowed_directories TEXT,  -- JSON array for sandbox
                    needs_git INTEGER,  -- Boolean: enable device files for git
                    system_prompt TEXT,
                    timeout_seconds INTEGER DEFAULT 900,  -- Execution timeout (default: 15 mins)
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    result_path TEXT,
                    error_message TEXT,
                    token_usage INTEGER,
                    execution_time REAL,
                    process_id INTEGER  -- PID of Claude subprocess
                )
            """)

            # Migrations
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'needs_git' not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN needs_git INTEGER")
                conn.commit()

            if 'process_id' not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN process_id INTEGER")
                conn.commit()

            # Migration: Add timeout_seconds column and remove estimated_time
            if 'timeout_seconds' not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN timeout_seconds INTEGER DEFAULT 900")
                conn.commit()

            # Note: SQLite doesn't support DROP COLUMN easily, so we leave estimated_time if it exists
            # New code will use timeout_seconds instead

            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    log_level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            """)

            conn.commit()

    def create_task(
        self,
        task_id: str,
        description: str,
        skill_name: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None,
        allowed_directories: Optional[List[str]] = None,
        needs_git: Optional[bool] = None,
        system_prompt: Optional[str] = None,
        timeout_seconds: Optional[int] = 900  # Default 15 minutes
    ) -> Task:
        """Create a new task in STAGED state"""
        now = datetime.now().isoformat()

        task = Task(
            task_id=task_id,
            description=description,
            status=TaskStatus.STAGED.value,
            skill_name=skill_name,
            allowed_tools=allowed_tools,
            allowed_directories=allowed_directories,
            needs_git=needs_git,
            system_prompt=system_prompt,
            timeout_seconds=timeout_seconds,
            created_at=now,
            updated_at=now
        )

        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO tasks (
                    task_id, description, status, skill_name, allowed_tools,
                    allowed_directories, needs_git, system_prompt, timeout_seconds,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id,
                task.description,
                task.status,
                task.skill_name,
                json.dumps(task.allowed_tools) if task.allowed_tools else None,
                json.dumps(task.allowed_directories) if task.allowed_directories else None,
                1 if task.needs_git else 0,
                task.system_prompt,
                task.timeout_seconds,
                task.created_at,
                task.updated_at
            ))
            conn.commit()

        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task by ID"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            # Handle timeout_seconds with fallback to estimated_time for backwards compat
            timeout_val = row["timeout_seconds"] if "timeout_seconds" in row.keys() else None
            if timeout_val is None and "estimated_time" in row.keys():
                timeout_val = row["estimated_time"]  # Fallback for old tasks
            if timeout_val is None:
                timeout_val = 900  # Default 15 minutes

            return Task(
                task_id=row["task_id"],
                description=row["description"],
                status=row["status"],
                skill_name=row["skill_name"],
                allowed_tools=json.loads(row["allowed_tools"]) if row["allowed_tools"] else None,
                allowed_directories=json.loads(row["allowed_directories"]) if row["allowed_directories"] else None,
                needs_git=bool(row["needs_git"]) if row["needs_git"] is not None else None,
                system_prompt=row["system_prompt"],
                timeout_seconds=timeout_val,
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                result_path=row["result_path"],
                error_message=row["error_message"],
                token_usage=row["token_usage"],
                execution_time=row["execution_time"],
                process_id=row["process_id"]
            )

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """List all tasks, optionally filtered by status"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row

            if status:
                cursor = conn.execute(
                    "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                    (status.value,)
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM tasks ORDER BY created_at DESC"
                )

            tasks = []
            for row in cursor.fetchall():
                # Handle timeout_seconds with fallback to estimated_time for backwards compat
                timeout_val = row["timeout_seconds"] if "timeout_seconds" in row.keys() else None
                if timeout_val is None and "estimated_time" in row.keys():
                    timeout_val = row["estimated_time"]  # Fallback for old tasks
                if timeout_val is None:
                    timeout_val = 900  # Default 15 minutes

                tasks.append(Task(
                    task_id=row["task_id"],
                    description=row["description"],
                    status=row["status"],
                    skill_name=row["skill_name"],
                    allowed_tools=json.loads(row["allowed_tools"]) if row["allowed_tools"] else None,
                    allowed_directories=json.loads(row["allowed_directories"]) if row["allowed_directories"] else None,
                    needs_git=bool(row["needs_git"]) if row["needs_git"] is not None else None,
                    system_prompt=row["system_prompt"],
                    timeout_seconds=timeout_val,
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    result_path=row["result_path"],
                    error_message=row["error_message"],
                    token_usage=row["token_usage"],
                    execution_time=row["execution_time"],
                    process_id=row["process_id"]
                ))

            return tasks

    def delete_task(self, task_id: str) -> bool:
        """Delete a task and its logs"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM task_logs WHERE task_id = ?", (task_id,))
            cursor = conn.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            conn.commit()
            return cursor.rowcount > 0

    def update_status(
        self,
        task_id: str,
        new_status: TaskStatus,
        **kwargs
    ) -> bool:
        """Update task status and optional fields"""
        now = datetime.now().isoformat()

        # Build update query dynamically
        update_fields = ["status = ?", "updated_at = ?"]
        values = [new_status.value, now]

        # Add timestamp fields based on status
        if new_status == TaskStatus.RUNNING:
            update_fields.append("started_at = ?")
            values.append(now)
        elif new_status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
            update_fields.append("completed_at = ?")
            values.append(now)

        # Add any additional fields from kwargs
        for key, value in kwargs.items():
            if key in ["result_path", "error_message", "token_usage", "execution_time", "process_id"]:
                update_fields.append(f"{key} = ?")
                values.append(value)

        values.append(task_id)

        with self._get_connection() as conn:
            cursor = conn.execute(
                f"UPDATE tasks SET {', '.join(update_fields)} WHERE task_id = ?",
                values
            )
            conn.commit()
            return cursor.rowcount > 0

    def update_plan(
        self,
        task_id: str,
        description: str,
        allowed_tools: Optional[List[str]] = None,
        allowed_directories: Optional[List[str]] = None,
        needs_git: Optional[bool] = None,
        system_prompt: Optional[str] = None,
        timeout_seconds: Optional[int] = None
    ) -> bool:
        """
        Update task plan details (for plan revision)
        Only allows updates on tasks in STAGED state
        """
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            cursor = conn.execute(
                """UPDATE tasks SET
                    description = ?,
                    allowed_tools = ?,
                    allowed_directories = ?,
                    needs_git = ?,
                    system_prompt = ?,
                    timeout_seconds = ?,
                    updated_at = ?
                WHERE task_id = ? AND status = ?""",
                (
                    description,
                    json.dumps(allowed_tools) if allowed_tools else None,
                    json.dumps(allowed_directories) if allowed_directories else None,
                    1 if needs_git else 0,
                    system_prompt,
                    timeout_seconds,
                    now,
                    task_id,
                    TaskStatus.STAGED.value
                )
            )
            conn.commit()
            return cursor.rowcount > 0

    def add_log(self, task_id: str, log_level: str, message: str):
        """Add a log entry for a task"""
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO task_logs (task_id, timestamp, log_level, message)
                VALUES (?, ?, ?, ?)
            """, (task_id, datetime.now().isoformat(), log_level, message))
            conn.commit()

    def get_logs(self, task_id: str) -> List[Dict[str, Any]]:
        """Retrieve all logs for a task"""
        with self._get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT timestamp, log_level, message
                FROM task_logs
                WHERE task_id = ?
                ORDER BY timestamp ASC
            """, (task_id,))

            return [dict(row) for row in cursor.fetchall()]

    def acquire_task_for_execution(self) -> Optional[Task]:
        """
        Atomically get next COMMITTED task and mark as RUNNING

        This method is thread-safe and designed for concurrent executor workers.
        It uses BEGIN IMMEDIATE to acquire an exclusive lock before checking
        and updating the task status.

        Returns:
            Task object if one was acquired, None if no COMMITTED tasks available
        """
        conn = self._open_connection()
        try:
            # BEGIN IMMEDIATE acquires a write lock immediately
            conn.execute("BEGIN IMMEDIATE")

            # Find the oldest COMMITTED task
            cursor = conn.execute("""
                SELECT task_id FROM tasks
                WHERE status = ?
                ORDER BY created_at ASC
                LIMIT 1
            """, (TaskStatus.COMMITTED.value,))

            row = cursor.fetchone()
            if not row:
                conn.rollback()
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

            # Return the task (using a fresh read)
            return self.get_task(task_id)

        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()

    def count_running_tasks(self) -> int:
        """
        Count how many tasks are currently in RUNNING state

        Returns:
            Number of running tasks
        """
        with self._get_connection() as conn:
            cursor = conn.execute(
                "SELECT COUNT(*) FROM tasks WHERE status = ?",
                (TaskStatus.RUNNING.value,)
            )
            return cursor.fetchone()[0]
