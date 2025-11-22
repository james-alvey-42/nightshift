"""
Task Queue Management for NightShift
Handles task creation, state transitions, and persistence
"""
import sqlite3
import json
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
    system_prompt: Optional[str] = None
    estimated_tokens: Optional[int] = None
    estimated_time: Optional[int] = None  # seconds
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result_path: Optional[str] = None
    error_message: Optional[str] = None
    token_usage: Optional[int] = None
    execution_time: Optional[float] = None  # seconds
    execution_environment: Optional[Dict[str, Any]] = None  # execution environment details
    software_stack: Optional[Dict[str, Any]] = None  # software stack requirements
    containerization: Optional[Dict[str, Any]] = None  # containerization recommendations

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class TaskQueue:
    """SQLite-backed task queue with state management"""

    def __init__(self, db_path: str = "database/nightshift.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    description TEXT NOT NULL,
                    status TEXT NOT NULL,
                    skill_name TEXT,
                    allowed_tools TEXT,  -- JSON array
                    system_prompt TEXT,
                    estimated_tokens INTEGER,
                    estimated_time INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    started_at TEXT,
                    completed_at TEXT,
                    result_path TEXT,
                    error_message TEXT,
                    token_usage INTEGER,
                    execution_time REAL,
                    execution_environment TEXT,  -- JSON object
                    software_stack TEXT,  -- JSON object
                    containerization TEXT  -- JSON object
                )
            """)

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

            # Migration: Add new columns if they don't exist
            cursor = conn.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'execution_environment' not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN execution_environment TEXT")
            if 'software_stack' not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN software_stack TEXT")
            if 'containerization' not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN containerization TEXT")

            conn.commit()

    def create_task(
        self,
        task_id: str,
        description: str,
        skill_name: Optional[str] = None,
        allowed_tools: Optional[List[str]] = None,
        system_prompt: Optional[str] = None,
        estimated_tokens: Optional[int] = None,
        estimated_time: Optional[int] = None,
        execution_environment: Optional[Dict[str, Any]] = None,
        software_stack: Optional[Dict[str, Any]] = None,
        containerization: Optional[Dict[str, Any]] = None
    ) -> Task:
        """Create a new task in STAGED state"""
        now = datetime.now().isoformat()

        task = Task(
            task_id=task_id,
            description=description,
            status=TaskStatus.STAGED.value,
            skill_name=skill_name,
            allowed_tools=allowed_tools,
            system_prompt=system_prompt,
            estimated_tokens=estimated_tokens,
            estimated_time=estimated_time,
            execution_environment=execution_environment,
            software_stack=software_stack,
            containerization=containerization,
            created_at=now,
            updated_at=now
        )

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO tasks (
                    task_id, description, status, skill_name, allowed_tools,
                    system_prompt, estimated_tokens, estimated_time,
                    execution_environment, software_stack, containerization,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                task.task_id,
                task.description,
                task.status,
                task.skill_name,
                json.dumps(task.allowed_tools) if task.allowed_tools else None,
                task.system_prompt,
                task.estimated_tokens,
                task.estimated_time,
                json.dumps(task.execution_environment) if task.execution_environment else None,
                json.dumps(task.software_stack) if task.software_stack else None,
                json.dumps(task.containerization) if task.containerization else None,
                task.created_at,
                task.updated_at
            ))
            conn.commit()

        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve a task by ID"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,)
            )
            row = cursor.fetchone()

            if not row:
                return None

            # Handle new columns that may not exist in old databases
            execution_env = row["execution_environment"] if "execution_environment" in row.keys() else None
            soft_stack = row["software_stack"] if "software_stack" in row.keys() else None
            container = row["containerization"] if "containerization" in row.keys() else None

            return Task(
                task_id=row["task_id"],
                description=row["description"],
                status=row["status"],
                skill_name=row["skill_name"],
                allowed_tools=json.loads(row["allowed_tools"]) if row["allowed_tools"] else None,
                system_prompt=row["system_prompt"],
                estimated_tokens=row["estimated_tokens"],
                estimated_time=row["estimated_time"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                started_at=row["started_at"],
                completed_at=row["completed_at"],
                result_path=row["result_path"],
                error_message=row["error_message"],
                token_usage=row["token_usage"],
                execution_time=row["execution_time"],
                execution_environment=json.loads(execution_env) if execution_env else None,
                software_stack=json.loads(soft_stack) if soft_stack else None,
                containerization=json.loads(container) if container else None
            )

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """List all tasks, optionally filtered by status"""
        with sqlite3.connect(self.db_path) as conn:
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
                # Handle new columns that may not exist in old databases
                execution_env = row["execution_environment"] if "execution_environment" in row.keys() else None
                soft_stack = row["software_stack"] if "software_stack" in row.keys() else None
                container = row["containerization"] if "containerization" in row.keys() else None

                tasks.append(Task(
                    task_id=row["task_id"],
                    description=row["description"],
                    status=row["status"],
                    skill_name=row["skill_name"],
                    allowed_tools=json.loads(row["allowed_tools"]) if row["allowed_tools"] else None,
                    system_prompt=row["system_prompt"],
                    estimated_tokens=row["estimated_tokens"],
                    estimated_time=row["estimated_time"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    started_at=row["started_at"],
                    completed_at=row["completed_at"],
                    result_path=row["result_path"],
                    error_message=row["error_message"],
                    token_usage=row["token_usage"],
                    execution_time=row["execution_time"],
                    execution_environment=json.loads(execution_env) if execution_env else None,
                    software_stack=json.loads(soft_stack) if soft_stack else None,
                    containerization=json.loads(container) if container else None
                ))

            return tasks

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
            if key in ["result_path", "error_message", "token_usage", "execution_time"]:
                update_fields.append(f"{key} = ?")
                values.append(value)

        values.append(task_id)

        with sqlite3.connect(self.db_path) as conn:
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
        system_prompt: Optional[str] = None,
        estimated_tokens: Optional[int] = None,
        estimated_time: Optional[int] = None,
        execution_environment: Optional[Dict[str, Any]] = None,
        software_stack: Optional[Dict[str, Any]] = None,
        containerization: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update task plan details (for plan revision)
        Only allows updates on tasks in STAGED state
        """
        now = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """UPDATE tasks SET
                    description = ?,
                    allowed_tools = ?,
                    system_prompt = ?,
                    estimated_tokens = ?,
                    estimated_time = ?,
                    execution_environment = ?,
                    software_stack = ?,
                    containerization = ?,
                    updated_at = ?
                WHERE task_id = ? AND status = ?""",
                (
                    description,
                    json.dumps(allowed_tools) if allowed_tools else None,
                    system_prompt,
                    estimated_tokens,
                    estimated_time,
                    json.dumps(execution_environment) if execution_environment else None,
                    json.dumps(software_stack) if software_stack else None,
                    json.dumps(containerization) if containerization else None,
                    now,
                    task_id,
                    TaskStatus.STAGED.value
                )
            )
            conn.commit()
            return cursor.rowcount > 0

    def add_log(self, task_id: str, log_level: str, message: str):
        """Add a log entry for a task"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO task_logs (task_id, timestamp, log_level, message)
                VALUES (?, ?, ?, ?)
            """, (task_id, datetime.now().isoformat(), log_level, message))
            conn.commit()

    def get_logs(self, task_id: str) -> List[Dict[str, Any]]:
        """Retrieve all logs for a task"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT timestamp, log_level, message
                FROM task_logs
                WHERE task_id = ?
                ORDER BY timestamp ASC
            """, (task_id,))

            return [dict(row) for row in cursor.fetchall()]
