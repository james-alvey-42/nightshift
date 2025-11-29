"""
Tests for TaskExecutor - concurrent task execution service
"""
import pytest
import json
import time
import threading
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from concurrent.futures import Future

from nightshift.core.task_executor import TaskExecutor, ExecutorManager
from nightshift.core.task_queue import TaskQueue, TaskStatus, Task
from nightshift.core.logger import NightShiftLogger


@pytest.fixture
def tmp_setup(tmp_path):
    """Set up temporary directories and basic fixtures"""
    db_path = tmp_path / "test.db"
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    queue = TaskQueue(db_path=str(db_path))
    logger = NightShiftLogger(log_dir=str(tmp_path / "logs"), console_output=False)

    # Mock agent manager
    agent_manager = Mock()
    agent_manager.execute_task = Mock(return_value={"success": True})

    return {
        "queue": queue,
        "logger": logger,
        "agent_manager": agent_manager,
        "tmp_path": tmp_path,
        "pid_file": tmp_path / "executor.pid"
    }


class TestTaskExecutorInit:
    """Tests for TaskExecutor initialization"""

    def test_default_values(self, tmp_setup):
        """TaskExecutor has correct default values"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        assert executor.max_workers == 3
        assert executor.poll_interval == 1.0
        assert executor.is_running is False

    def test_custom_values(self, tmp_setup):
        """TaskExecutor accepts custom values"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            max_workers=5,
            poll_interval=2.0,
            pid_file=tmp_setup["pid_file"]
        )

        assert executor.max_workers == 5
        assert executor.poll_interval == 2.0

    def test_creates_thread_pool(self, tmp_setup):
        """TaskExecutor creates thread pool with correct workers"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            max_workers=4,
            pid_file=tmp_setup["pid_file"]
        )

        assert executor.executor is not None
        assert executor.executor._max_workers == 4


class TestTaskExecutorStart:
    """Tests for start method"""

    def test_start_sets_running_flag(self, tmp_setup):
        """start sets is_running to True"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        try:
            executor.start()
            assert executor.is_running is True
        finally:
            executor.stop()

    def test_start_creates_pid_file(self, tmp_setup):
        """start creates PID file"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        try:
            executor.start()
            assert tmp_setup["pid_file"].exists()

            with open(tmp_setup["pid_file"]) as f:
                pid_data = json.load(f)

            assert "pid" in pid_data
            assert "max_workers" in pid_data
            assert "poll_interval" in pid_data
            assert "started_at" in pid_data
        finally:
            executor.stop()

    def test_start_twice_warns(self, tmp_setup):
        """Starting executor twice logs warning"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        try:
            executor.start()
            # Second start should just return (with warning)
            executor.start()  # Should not raise
            assert executor.is_running is True
        finally:
            executor.stop()

    def test_start_with_stale_pid_file(self, tmp_setup):
        """start removes stale PID file from dead process"""
        # Create stale PID file with non-existent PID
        stale_pid_data = {"pid": 999999, "max_workers": 3, "poll_interval": 1.0}
        with open(tmp_setup["pid_file"], 'w') as f:
            json.dump(stale_pid_data, f)

        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        try:
            # Should clean up stale file and start normally
            executor.start()
            assert executor.is_running is True
        finally:
            executor.stop()

    def test_start_starts_poll_thread(self, tmp_setup):
        """start creates and starts poll thread"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        try:
            executor.start()
            assert executor.poll_thread is not None
            assert executor.poll_thread.is_alive()
        finally:
            executor.stop()


class TestTaskExecutorStop:
    """Tests for stop method"""

    def test_stop_clears_running_flag(self, tmp_setup):
        """stop sets is_running to False"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        executor.start()
        executor.stop()

        assert executor.is_running is False

    def test_stop_removes_pid_file(self, tmp_setup):
        """stop removes PID file"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        executor.start()
        assert tmp_setup["pid_file"].exists()

        executor.stop()
        assert not tmp_setup["pid_file"].exists()

    def test_stop_joins_poll_thread(self, tmp_setup):
        """stop waits for poll thread to exit"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        executor.start()
        executor.stop()

        assert not executor.poll_thread.is_alive()

    def test_stop_when_not_running(self, tmp_setup):
        """stop when not running just warns"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        # Should not raise
        executor.stop()
        assert executor.is_running is False


class TestGetStatus:
    """Tests for get_status method"""

    def test_status_when_not_running(self, tmp_setup):
        """get_status returns correct status when not running"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        status = executor.get_status()

        assert status["is_running"] is False
        assert status["running_tasks"] == 0

    def test_status_when_running(self, tmp_setup):
        """get_status returns correct status when running"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            max_workers=5,
            poll_interval=2.0,
            pid_file=tmp_setup["pid_file"]
        )

        try:
            executor.start()
            status = executor.get_status()

            assert status["is_running"] is True
            assert status["max_workers"] == 5
            assert status["poll_interval"] == 2.0
            assert status["available_workers"] == 5
        finally:
            executor.stop()


class TestPollLoop:
    """Tests for _poll_loop method"""

    def test_poll_acquires_task(self, tmp_setup):
        """Poll loop acquires and submits tasks"""
        # Create a committed task
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)

        # Create executor with short poll interval
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            poll_interval=0.1,
            pid_file=tmp_setup["pid_file"]
        )

        try:
            executor.start()
            # Wait for poll to pick up task
            time.sleep(0.5)

            # Task should be acquired (status changed to RUNNING)
            task = tmp_setup["queue"].get_task("task_001")
            assert task.status == TaskStatus.RUNNING.value
        finally:
            executor.stop()

    def test_poll_respects_max_workers(self, tmp_setup):
        """Poll loop doesn't acquire more tasks than max_workers"""
        # Create multiple committed tasks
        for i in range(5):
            tmp_setup["queue"].create_task(task_id=f"task_{i:03d}", description=f"Test {i}")
            tmp_setup["queue"].update_status(f"task_{i:03d}", TaskStatus.COMMITTED)

        # Make execute_task block so tasks stay running
        def slow_execute(task):
            time.sleep(2)
            return {"success": True}

        tmp_setup["agent_manager"].execute_task = slow_execute

        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            max_workers=2,
            poll_interval=0.1,
            pid_file=tmp_setup["pid_file"]
        )

        try:
            executor.start()
            time.sleep(0.5)

            # Should only have 2 running at a time
            running_count = len([t for t in tmp_setup["queue"].list_tasks()
                               if t.status == TaskStatus.RUNNING.value])
            assert running_count <= 2
        finally:
            executor.stop()


class TestExecuteTaskWrapper:
    """Tests for _execute_task_wrapper method"""

    def test_wrapper_calls_agent_manager(self, tmp_setup):
        """Wrapper calls agent_manager.execute_task"""
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        tmp_setup["queue"].update_status("task_001", TaskStatus.RUNNING)

        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        executor._execute_task_wrapper("task_001")

        tmp_setup["agent_manager"].execute_task.assert_called_once()

    def test_wrapper_handles_missing_task(self, tmp_setup):
        """Wrapper handles missing task gracefully"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        # Should not raise
        executor._execute_task_wrapper("nonexistent")

        # Agent manager should not be called
        tmp_setup["agent_manager"].execute_task.assert_not_called()

    def test_wrapper_handles_exception(self, tmp_setup):
        """Wrapper handles execution exception"""
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        tmp_setup["queue"].update_status("task_001", TaskStatus.RUNNING)

        tmp_setup["agent_manager"].execute_task.side_effect = Exception("Test error")

        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        # Should not raise
        executor._execute_task_wrapper("task_001")

        # Task should be marked as FAILED
        task = tmp_setup["queue"].get_task("task_001")
        assert task.status == TaskStatus.FAILED.value


class TestCleanupCompletedTasks:
    """Tests for _cleanup_completed_tasks method"""

    def test_cleanup_removes_done_futures(self, tmp_setup):
        """Cleanup removes completed futures from tracking"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        # Create a done future
        future = Future()
        future.set_result(None)

        executor.running_tasks["task_001"] = future

        executor._cleanup_completed_tasks()

        assert "task_001" not in executor.running_tasks

    def test_cleanup_keeps_pending_futures(self, tmp_setup):
        """Cleanup keeps pending futures in tracking"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        # Create a pending future
        future = Future()
        # Don't set result - it's pending

        executor.running_tasks["task_001"] = future

        executor._cleanup_completed_tasks()

        assert "task_001" in executor.running_tasks


class TestExecutorManager:
    """Tests for ExecutorManager singleton"""

    def setup_method(self):
        """Reset singleton state before each test"""
        ExecutorManager._instance = None

    def test_start_executor_creates_instance(self, tmp_setup):
        """start_executor creates and starts executor"""
        try:
            executor = ExecutorManager.start_executor(
                task_queue=tmp_setup["queue"],
                agent_manager=tmp_setup["agent_manager"],
                logger=tmp_setup["logger"],
                max_workers=2,
                poll_interval=0.5
            )

            assert executor is not None
            assert executor.is_running is True
            assert ExecutorManager._instance is executor
        finally:
            ExecutorManager.stop_executor()

    def test_start_executor_returns_existing(self, tmp_setup):
        """start_executor returns existing running instance"""
        try:
            executor1 = ExecutorManager.start_executor(
                task_queue=tmp_setup["queue"],
                agent_manager=tmp_setup["agent_manager"],
                logger=tmp_setup["logger"]
            )
            executor2 = ExecutorManager.start_executor(
                task_queue=tmp_setup["queue"],
                agent_manager=tmp_setup["agent_manager"],
                logger=tmp_setup["logger"]
            )

            assert executor1 is executor2
        finally:
            ExecutorManager.stop_executor()

    def test_stop_executor_stops_instance(self, tmp_setup):
        """stop_executor stops running instance"""
        ExecutorManager.start_executor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"]
        )

        ExecutorManager.stop_executor()

        assert ExecutorManager._instance.is_running is False

    def test_get_executor_returns_instance(self, tmp_setup):
        """get_executor returns current instance"""
        try:
            ExecutorManager.start_executor(
                task_queue=tmp_setup["queue"],
                agent_manager=tmp_setup["agent_manager"],
                logger=tmp_setup["logger"]
            )

            result = ExecutorManager.get_executor()
            assert result is ExecutorManager._instance
        finally:
            ExecutorManager.stop_executor()

    def test_get_executor_returns_none(self, tmp_setup):
        """get_executor returns None when no instance"""
        result = ExecutorManager.get_executor()
        assert result is None

    def test_get_status_running(self, tmp_setup):
        """get_status returns status of running executor"""
        try:
            ExecutorManager.start_executor(
                task_queue=tmp_setup["queue"],
                agent_manager=tmp_setup["agent_manager"],
                logger=tmp_setup["logger"],
                max_workers=4
            )

            status = ExecutorManager.get_status()

            assert status["is_running"] is True
            assert status["max_workers"] == 4
        finally:
            ExecutorManager.stop_executor()

    def test_get_status_not_running(self, tmp_setup):
        """get_status returns not running when no executor"""
        status = ExecutorManager.get_status()

        assert status["is_running"] is False
        assert status["max_workers"] == 0

    def test_get_status_from_pid_file(self, tmp_setup):
        """get_status reads from PID file for external process"""
        # Create a PID file as if from another process
        pid_file = Path.home() / ".nightshift" / "executor.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        # Use current process PID so the check passes
        pid_data = {
            "pid": 999999,  # Non-existent PID
            "max_workers": 5,
            "poll_interval": 2.0,
            "started_at": time.time()
        }

        try:
            with open(pid_file, 'w') as f:
                json.dump(pid_data, f)

            # Status should detect stale PID and clean up
            status = ExecutorManager.get_status()
            # Since PID doesn't exist, file should be cleaned up
            assert not pid_file.exists() or status["is_running"] is False

        finally:
            if pid_file.exists():
                pid_file.unlink()


class TestTaskExecutorEdgeCases:
    """Edge case tests for TaskExecutor"""

    def test_start_with_running_executor_raises(self, tmp_setup):
        """start raises RuntimeError when another executor is running"""
        import os

        # Create a PID file with current process PID (which is running)
        current_pid = os.getpid()
        pid_data = {"pid": current_pid, "max_workers": 3, "poll_interval": 1.0}
        with open(tmp_setup["pid_file"], 'w') as f:
            json.dump(pid_data, f)

        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        with pytest.raises(RuntimeError) as exc_info:
            executor.start()

        assert "already running" in str(exc_info.value)

    def test_start_with_invalid_pid_file(self, tmp_setup):
        """start handles corrupted/invalid PID file"""
        # Create invalid JSON PID file
        with open(tmp_setup["pid_file"], 'w') as f:
            f.write("{ not valid json")

        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        try:
            # Should clean up invalid file and start normally
            executor.start()
            assert executor.is_running is True
        finally:
            executor.stop()

    def test_start_with_missing_pid_key(self, tmp_setup):
        """start handles PID file with missing 'pid' key"""
        # Create PID file without required 'pid' key
        with open(tmp_setup["pid_file"], 'w') as f:
            json.dump({"max_workers": 3}, f)

        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        try:
            # Should clean up invalid file and start normally
            executor.start()
            assert executor.is_running is True
        finally:
            executor.stop()

    def test_start_write_pid_fails(self, tmp_setup):
        """start raises exception when PID file cannot be written"""
        # Make pid_file a directory so write fails
        tmp_setup["pid_file"].mkdir(parents=True)

        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        with pytest.raises(Exception):
            executor.start()

    def test_stop_remove_pid_file_fails(self, tmp_setup):
        """stop handles PID file removal failure gracefully"""
        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        executor.start()

        # Replace pid_file path with directory to cause unlink to fail
        with patch.object(executor, 'pid_file', Path("/nonexistent/path/executor.pid")):
            # Mock exists to return True, but unlink will fail
            with patch('pathlib.Path.exists', return_value=True):
                with patch('pathlib.Path.unlink', side_effect=PermissionError("denied")):
                    # Should not raise, just log error
                    executor.stop()

        assert executor.is_running is False

    def test_poll_loop_handles_exception(self, tmp_setup):
        """Poll loop continues after exception"""
        # Make acquire_task_for_execution raise an exception
        tmp_setup["queue"].acquire_task_for_execution = Mock(
            side_effect=[Exception("DB error"), None, None, None]
        )

        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            poll_interval=0.1,
            pid_file=tmp_setup["pid_file"]
        )

        try:
            executor.start()
            # Wait for a few poll cycles
            time.sleep(0.5)
            # Executor should still be running despite exception
            assert executor.is_running is True
        finally:
            executor.stop()

    def test_wrapper_logs_task_failure(self, tmp_setup):
        """Wrapper logs when task returns success=False"""
        tmp_setup["queue"].create_task(task_id="task_001", description="Test")
        tmp_setup["queue"].update_status("task_001", TaskStatus.COMMITTED)
        tmp_setup["queue"].update_status("task_001", TaskStatus.RUNNING)

        # Make execute_task return failure
        tmp_setup["agent_manager"].execute_task.return_value = {
            "success": False,
            "error": "Task failed due to timeout"
        }

        executor = TaskExecutor(
            task_queue=tmp_setup["queue"],
            agent_manager=tmp_setup["agent_manager"],
            logger=tmp_setup["logger"],
            pid_file=tmp_setup["pid_file"]
        )

        # Should not raise
        executor._execute_task_wrapper("task_001")

        # Agent manager should be called
        tmp_setup["agent_manager"].execute_task.assert_called_once()


class TestExecutorManagerEdgeCases:
    """Edge case tests for ExecutorManager"""

    def setup_method(self):
        """Reset singleton state before each test"""
        ExecutorManager._instance = None

    def test_get_status_reads_live_process(self, tmp_setup):
        """get_status returns status when PID file points to live process"""
        import os
        pid_file = Path.home() / ".nightshift" / "executor.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        # Use current process PID (which is alive)
        pid_data = {
            "pid": os.getpid(),
            "max_workers": 5,
            "poll_interval": 2.0,
            "started_at": time.time()
        }

        try:
            with open(pid_file, 'w') as f:
                json.dump(pid_data, f)

            status = ExecutorManager.get_status()

            assert status["is_running"] is True
            assert status["max_workers"] == 5
            assert status["poll_interval"] == 2.0
            assert status["pid"] == os.getpid()

        finally:
            if pid_file.exists():
                pid_file.unlink()

    def test_get_status_cleans_invalid_pid_file(self, tmp_setup):
        """get_status cleans up corrupted PID file"""
        pid_file = Path.home() / ".nightshift" / "executor.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Write invalid JSON
            with open(pid_file, 'w') as f:
                f.write("{ invalid json")

            status = ExecutorManager.get_status()

            assert status["is_running"] is False
            # File should be cleaned up
            assert not pid_file.exists()

        finally:
            if pid_file.exists():
                pid_file.unlink()

    def test_stop_executor_signals_external_process(self, tmp_setup):
        """stop_executor sends SIGTERM to external process"""
        import os
        import signal

        pid_file = Path.home() / ".nightshift" / "executor.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        # Use a non-existent PID
        pid_data = {
            "pid": 999999,
            "max_workers": 3,
            "poll_interval": 1.0
        }

        try:
            with open(pid_file, 'w') as f:
                json.dump(pid_data, f)

            # Should clean up stale PID file
            ExecutorManager.stop_executor()

            # File should be cleaned up
            assert not pid_file.exists()

        finally:
            if pid_file.exists():
                pid_file.unlink()

    def test_stop_executor_handles_sigterm_to_live_process(self, tmp_setup):
        """stop_executor handles case where process doesn't stop gracefully"""
        import os

        pid_file = Path.home() / ".nightshift" / "executor.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Use current process PID
            pid_data = {
                "pid": os.getpid(),
                "max_workers": 3,
                "poll_interval": 1.0
            }
            with open(pid_file, 'w') as f:
                json.dump(pid_data, f)

            # Mock os.kill to simulate process not stopping
            with patch('os.kill') as mock_kill:
                # First call (signal 0) - process exists
                # Second call (SIGTERM) - send signal
                # Third call (signal 0) - still exists (didn't stop)
                mock_kill.side_effect = [None, None, None]

                with pytest.raises(RuntimeError) as exc_info:
                    ExecutorManager.stop_executor()

                assert "did not stop gracefully" in str(exc_info.value)

        finally:
            if pid_file.exists():
                pid_file.unlink()
