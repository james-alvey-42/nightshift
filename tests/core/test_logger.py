"""
Tests for NightShiftLogger - logging system
"""
import pytest
import logging
import json
from pathlib import Path
from datetime import datetime

from nightshift.core.logger import NightShiftLogger


class TestLoggerSetup:
    """Tests for logger initialization"""

    def test_creates_log_directory(self, tmp_path):
        """Logger creates log directory if it doesn't exist"""
        log_dir = tmp_path / "logs"
        assert not log_dir.exists()

        NightShiftLogger(log_dir=str(log_dir))

        assert log_dir.exists()

    def test_creates_daily_log_file(self, tmp_path):
        """Logger creates dated log file"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)
        logger.info("test message")

        # Find log file with today's date
        today = datetime.now().strftime("%Y%m%d")
        log_files = list(tmp_path.glob(f"nightshift_{today}.log"))

        assert len(log_files) == 1

    def test_console_output_disabled(self, tmp_path):
        """Logger can be created without console handler"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        # Check only file handler exists
        handlers = logger.logger.handlers
        console_handlers = [h for h in handlers if isinstance(h, logging.StreamHandler)
                          and not isinstance(h, logging.FileHandler)]

        assert len(console_handlers) == 0

    def test_console_output_enabled(self, tmp_path):
        """Logger includes console handler when enabled"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=True)

        handlers = logger.logger.handlers
        console_handlers = [h for h in handlers if isinstance(h, logging.StreamHandler)
                          and not isinstance(h, logging.FileHandler)]

        assert len(console_handlers) == 1


class TestTaskLogging:
    """Tests for task-specific log methods"""

    def test_log_task_created(self, tmp_path, caplog):
        """log_task_created logs at INFO level"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        with caplog.at_level(logging.DEBUG, logger="nightshift"):
            logger.log_task_created("task_001", "Test description")

        assert "Task created: task_001" in caplog.text
        assert "Test description" in caplog.text

    def test_log_task_approved(self, tmp_path, caplog):
        """log_task_approved logs at INFO level"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        with caplog.at_level(logging.INFO, logger="nightshift"):
            logger.log_task_approved("task_001")

        assert "Task approved: task_001" in caplog.text

    def test_log_task_started(self, tmp_path, caplog):
        """log_task_started logs task and command"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        with caplog.at_level(logging.DEBUG, logger="nightshift"):
            logger.log_task_started("task_001", "claude -p 'test'")

        assert "Task started: task_001" in caplog.text
        assert "claude -p 'test'" in caplog.text

    def test_log_tool_call(self, tmp_path, caplog):
        """log_tool_call logs tool name and parameters"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        with caplog.at_level(logging.DEBUG, logger="nightshift"):
            logger.log_tool_call("task_001", "Read", {"file_path": "/tmp/test.txt"})

        assert "[task_001] Tool call: Read" in caplog.text
        assert "file_path" in caplog.text

    def test_log_task_completed(self, tmp_path, caplog):
        """log_task_completed logs completion with metrics"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        with caplog.at_level(logging.INFO, logger="nightshift"):
            logger.log_task_completed("task_001", token_usage=1500, execution_time=45.5)

        assert "Task completed: task_001" in caplog.text
        assert "1500" in caplog.text
        assert "45.5" in caplog.text

    def test_log_task_completed_no_metrics(self, tmp_path, caplog):
        """log_task_completed works without metrics"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        with caplog.at_level(logging.INFO, logger="nightshift"):
            logger.log_task_completed("task_001")

        assert "Task completed: task_001" in caplog.text

    def test_log_task_failed(self, tmp_path, caplog):
        """log_task_failed logs at ERROR level"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        with caplog.at_level(logging.ERROR, logger="nightshift"):
            logger.log_task_failed("task_001", "Connection timeout")

        assert "Task failed: task_001" in caplog.text
        assert "Connection timeout" in caplog.text


class TestAgentOutputLogging:
    """Tests for raw agent output logging"""

    def test_log_agent_output_creates_file(self, tmp_path):
        """log_agent_output creates task-specific log file"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        logger.log_agent_output("task_001", "Sample output content")

        output_file = tmp_path / "task_task_001_output.log"
        assert output_file.exists()

    def test_log_agent_output_content(self, tmp_path):
        """log_agent_output writes output with timestamp"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        logger.log_agent_output("task_001", "Test output line 1\nTest output line 2")

        output_file = tmp_path / "task_task_001_output.log"
        content = output_file.read_text()

        assert "Test output line 1" in content
        assert "Test output line 2" in content
        # Should have ISO timestamp
        assert "T" in content  # ISO format separator

    def test_log_agent_output_appends(self, tmp_path):
        """log_agent_output appends to existing file"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        logger.log_agent_output("task_001", "First output")
        logger.log_agent_output("task_001", "Second output")

        output_file = tmp_path / "task_task_001_output.log"
        content = output_file.read_text()

        assert "First output" in content
        assert "Second output" in content


class TestGenericLogging:
    """Tests for generic log methods"""

    def test_info(self, tmp_path, caplog):
        """info() logs at INFO level"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        with caplog.at_level(logging.INFO, logger="nightshift"):
            logger.info("Info message")

        assert "Info message" in caplog.text

    def test_debug(self, tmp_path, caplog):
        """debug() logs at DEBUG level"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        with caplog.at_level(logging.DEBUG, logger="nightshift"):
            logger.debug("Debug message")

        assert "Debug message" in caplog.text

    def test_error(self, tmp_path, caplog):
        """error() logs at ERROR level"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        with caplog.at_level(logging.ERROR, logger="nightshift"):
            logger.error("Error message")

        assert "Error message" in caplog.text

    def test_warning(self, tmp_path, caplog):
        """warning() logs at WARNING level"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        with caplog.at_level(logging.WARNING, logger="nightshift"):
            logger.warning("Warning message")

        assert "Warning message" in caplog.text


class TestLogFileContent:
    """Tests verifying actual log file content"""

    def test_file_contains_formatted_logs(self, tmp_path):
        """Log file contains properly formatted messages"""
        logger = NightShiftLogger(log_dir=str(tmp_path), console_output=False)

        logger.info("Test info message")
        logger.error("Test error message")

        # Find today's log file
        today = datetime.now().strftime("%Y%m%d")
        log_file = tmp_path / f"nightshift_{today}.log"

        content = log_file.read_text()

        # Check format: timestamp - logger - level - message
        assert "nightshift" in content
        assert "INFO" in content
        assert "ERROR" in content
        assert "Test info message" in content
        assert "Test error message" in content
