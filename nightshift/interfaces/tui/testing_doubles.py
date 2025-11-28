"""
Test doubles (mocks/fakes) for TUI testing
Shared between unit tests and integration tests
"""
import types


class DummyQueue:
    """Mock TaskQueue for testing"""
    def __init__(self, tasks):
        self._tasks = {t.task_id: t for t in tasks}

    def list_tasks(self, status=None):
        """
        Return tasks, optionally filtered by status.

        If status is None, returns all tasks.
        If status is a TaskStatus enum, filters by matching status.value.
        """
        if status is None:
            return list(self._tasks.values())

        # Handle TaskStatus enum
        from nightshift.core.task_queue import TaskStatus
        status_value = status.value if isinstance(status, TaskStatus) else str(status).lower()

        # Filter tasks by normalized status
        filtered = []
        for task in self._tasks.values():
            task_status = task.status
            if isinstance(task_status, TaskStatus):
                task_status = task_status.value
            elif isinstance(task_status, str):
                task_status = task_status.lower()

            if task_status == status_value:
                filtered.append(task)

        return filtered

    def get_task(self, task_id):
        """Get task by ID"""
        return self._tasks.get(task_id)

    def update_status(self, task_id, status):
        """Update task status"""
        if task_id in self._tasks:
            self._tasks[task_id].status = status.value if hasattr(status, 'value') else status

    def create_task(self, description, **kwargs):
        """Create a new task"""
        task_id = f"task_{len(self._tasks)}"
        task = types.SimpleNamespace(
            task_id=task_id,
            description=description,
            status="staged",
            created_at="2025-01-01T00:00:00",
            result_path=None,
            **kwargs
        )
        task.to_dict = lambda: {
            "task_id": task.task_id,
            "status": task.status,
            "description": task.description,
            "created_at": task.created_at,
            "result_path": task.result_path,
        }
        self._tasks[task_id] = task
        return task

    def delete_task(self, task_id):
        """Delete a task"""
        if task_id in self._tasks:
            del self._tasks[task_id]
            return True
        return False


class DummyConfig:
    """Mock Config for testing"""
    def __init__(self, tmp_path=None):
        self._tmp_path = tmp_path or "/tmp"

    def get_output_dir(self):
        return str(self._tmp_path)

    def get_notifications_dir(self):
        return str(self._tmp_path)


class DummyPlanner:
    """Mock TaskPlanner for testing"""
    def plan_task(self, description):
        return {
            "enhanced_prompt": description,
            "estimated_tokens": 1000,
            "estimated_time": 10.0,
        }


class DummyAgent:
    """Mock AgentManager for testing"""
    def __init__(self):
        self.executed = []
        self.paused = []
        self.resumed = []
        self.killed = []

    def execute_task(self, task):
        self.executed.append(task.task_id)

    def pause_task(self, task_id):
        self.paused.append(task_id)

    def resume_task(self, task_id):
        self.resumed.append(task_id)

    def kill_task(self, task_id):
        self.killed.append(task_id)


class DummyLogger:
    """Mock NightShiftLogger for testing"""
    def __init__(self):
        self.info_messages = []
        self.error_messages = []

    def info(self, msg):
        self.info_messages.append(msg)

    def error(self, msg):
        self.error_messages.append(msg)
