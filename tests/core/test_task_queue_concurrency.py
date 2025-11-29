"""
Tests for TaskQueue concurrency and thread safety
"""
import pytest
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from nightshift.core.task_queue import TaskQueue, TaskStatus


class TestAcquireTaskForExecution:
    """Tests for the atomic acquire_task_for_execution method"""

    def test_acquire_returns_committed_task(self, tmp_path):
        """acquire_task_for_execution returns a COMMITTED task"""
        db_path = tmp_path / "test.db"
        queue = TaskQueue(db_path=str(db_path))

        # Create and commit a task
        queue.create_task(task_id="task_001", description="Test")
        queue.update_status("task_001", TaskStatus.COMMITTED)

        # Acquire it
        task = queue.acquire_task_for_execution()

        assert task is not None
        assert task.task_id == "task_001"
        assert task.status == TaskStatus.RUNNING.value

    def test_acquire_returns_none_when_no_committed(self, tmp_path):
        """acquire_task_for_execution returns None if no COMMITTED tasks"""
        db_path = tmp_path / "test.db"
        queue = TaskQueue(db_path=str(db_path))

        # Create only a STAGED task
        queue.create_task(task_id="task_001", description="Test")

        task = queue.acquire_task_for_execution()
        assert task is None

    def test_acquire_returns_oldest_committed_first(self, tmp_path):
        """acquire_task_for_execution returns oldest COMMITTED task (FIFO)"""
        db_path = tmp_path / "test.db"
        queue = TaskQueue(db_path=str(db_path))

        # Create multiple tasks
        queue.create_task(task_id="task_001", description="First")
        queue.create_task(task_id="task_002", description="Second")
        queue.create_task(task_id="task_003", description="Third")

        # Commit them in order
        queue.update_status("task_001", TaskStatus.COMMITTED)
        queue.update_status("task_002", TaskStatus.COMMITTED)
        queue.update_status("task_003", TaskStatus.COMMITTED)

        # First acquire should get oldest
        task = queue.acquire_task_for_execution()
        assert task.task_id == "task_001"

        # Second should get next
        task = queue.acquire_task_for_execution()
        assert task.task_id == "task_002"

        # Third should get last
        task = queue.acquire_task_for_execution()
        assert task.task_id == "task_003"

        # Fourth should be None
        task = queue.acquire_task_for_execution()
        assert task is None

    def test_acquire_marks_task_running(self, tmp_path):
        """acquire_task_for_execution sets task status to RUNNING"""
        db_path = tmp_path / "test.db"
        queue = TaskQueue(db_path=str(db_path))

        queue.create_task(task_id="task_001", description="Test")
        queue.update_status("task_001", TaskStatus.COMMITTED)

        queue.acquire_task_for_execution()

        task = queue.get_task("task_001")
        assert task.status == TaskStatus.RUNNING.value
        assert task.started_at is not None


class TestConcurrentAcquire:
    """Tests for concurrent access to acquire_task_for_execution"""

    def test_no_duplicate_acquisition(self, tmp_path):
        """Multiple threads cannot acquire the same task"""
        db_path = tmp_path / "test.db"
        queue = TaskQueue(db_path=str(db_path))

        # Create single committed task
        queue.create_task(task_id="task_001", description="Test")
        queue.update_status("task_001", TaskStatus.COMMITTED)

        acquired_tasks = []
        lock = threading.Lock()

        def worker():
            task = queue.acquire_task_for_execution()
            with lock:
                if task:
                    acquired_tasks.append(task.task_id)

        # Run 10 threads simultaneously
        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only one thread should have acquired the task
        assert len(acquired_tasks) == 1
        assert acquired_tasks[0] == "task_001"

    def test_concurrent_acquire_multiple_tasks(self, tmp_path):
        """Multiple threads correctly distribute multiple tasks"""
        db_path = tmp_path / "test.db"
        queue = TaskQueue(db_path=str(db_path))

        num_tasks = 20

        # Create multiple committed tasks
        for i in range(num_tasks):
            queue.create_task(task_id=f"task_{i:03d}", description=f"Task {i}")
            queue.update_status(f"task_{i:03d}", TaskStatus.COMMITTED)

        acquired_tasks = []
        lock = threading.Lock()

        def worker():
            while True:
                task = queue.acquire_task_for_execution()
                if task is None:
                    break
                with lock:
                    acquired_tasks.append(task.task_id)
                # Small delay to allow interleaving
                time.sleep(0.001)

        # Run 5 workers competing for tasks
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(worker) for _ in range(5)]
            for future in as_completed(futures):
                future.result()

        # All tasks should be acquired exactly once
        assert len(acquired_tasks) == num_tasks
        assert len(set(acquired_tasks)) == num_tasks  # No duplicates


class TestConcurrentCreateAndUpdate:
    """Tests for concurrent task creation and updates"""

    def test_concurrent_task_creation(self, tmp_path):
        """Multiple threads can create tasks without conflicts"""
        db_path = tmp_path / "test.db"
        queue = TaskQueue(db_path=str(db_path))

        num_tasks = 50
        created_ids = []
        lock = threading.Lock()

        def create_task(i):
            task = queue.create_task(task_id=f"task_{i:03d}", description=f"Task {i}")
            with lock:
                created_ids.append(task.task_id)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(create_task, i) for i in range(num_tasks)]
            for future in as_completed(futures):
                future.result()

        # All tasks should be created
        assert len(created_ids) == num_tasks
        assert len(set(created_ids)) == num_tasks

        # Verify in database
        tasks = queue.list_tasks()
        assert len(tasks) == num_tasks

    def test_concurrent_status_updates(self, tmp_path):
        """Multiple threads can update different task statuses"""
        db_path = tmp_path / "test.db"
        queue = TaskQueue(db_path=str(db_path))

        num_tasks = 20

        # Create tasks
        for i in range(num_tasks):
            queue.create_task(task_id=f"task_{i:03d}", description=f"Task {i}")

        def update_task(i):
            task_id = f"task_{i:03d}"
            queue.update_status(task_id, TaskStatus.COMMITTED)
            queue.update_status(task_id, TaskStatus.RUNNING)
            queue.update_status(task_id, TaskStatus.COMPLETED)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(update_task, i) for i in range(num_tasks)]
            for future in as_completed(futures):
                future.result()

        # All tasks should be completed
        for i in range(num_tasks):
            task = queue.get_task(f"task_{i:03d}")
            assert task.status == TaskStatus.COMPLETED.value


class TestConnectionBehavior:
    """Tests for connection handling"""

    def test_multiple_connections_work_concurrently(self, tmp_path):
        """Multiple connections can work with the same database"""
        db_path = tmp_path / "test.db"
        queue = TaskQueue(db_path=str(db_path))

        # Create a task with one connection
        queue.create_task(task_id="task_001", description="Test")

        # Get multiple raw connections (use _open_connection for raw access)
        conns = [queue._open_connection() for _ in range(5)]

        # All connections should be able to read the task
        for conn in conns:
            cursor = conn.execute("SELECT task_id FROM tasks WHERE task_id = ?", ("task_001",))
            result = cursor.fetchone()
            assert result is not None
            assert result[0] == "task_001"
            conn.close()

    def test_new_connection_each_call(self, tmp_path):
        """_open_connection creates a new connection each time"""
        db_path = tmp_path / "test.db"
        queue = TaskQueue(db_path=str(db_path))

        conn1 = queue._open_connection()
        conn2 = queue._open_connection()

        # Each call creates a new connection object
        assert id(conn1) != id(conn2)
        conn1.close()
        conn2.close()
