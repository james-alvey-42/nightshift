"""
Comprehensive logging system for NightShift
Tracks all agent decisions, tool calls, and outputs
"""
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any


class NightShiftLogger:
    """Structured logger for agent activities"""

    def __init__(self, log_dir: str = "logs", console_output: bool = True):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Set up Python logging
        self.logger = logging.getLogger("nightshift")
        self.logger.setLevel(logging.DEBUG)

        # Clear any existing handlers to prevent duplicates
        self.logger.handlers.clear()

        # Console handler (optional, disabled for TUI to prevent interference)
        if console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            console_formatter = logging.Formatter(
                "[%(levelname)s] %(message)s"
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)

        # File handler (all logs)
        file_handler = logging.FileHandler(
            self.log_dir / f"nightshift_{datetime.now():%Y%m%d}.log"
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_formatter)

        self.logger.addHandler(file_handler)

    def log_task_created(self, task_id: str, description: str):
        """Log task creation"""
        self.logger.info(f"Task created: {task_id}")
        self.logger.debug(f"  Description: {description}")

    def log_task_approved(self, task_id: str):
        """Log task approval"""
        self.logger.info(f"Task approved: {task_id}")

    def log_task_started(self, task_id: str, command: str):
        """Log task execution start"""
        self.logger.info(f"Task started: {task_id}")
        self.logger.debug(f"  Command: {command}")

    def log_tool_call(self, task_id: str, tool_name: str, params: Dict[str, Any]):
        """Log individual tool calls from Claude"""
        self.logger.debug(f"[{task_id}] Tool call: {tool_name}")
        self.logger.debug(f"  Parameters: {json.dumps(params, indent=2)}")

    def log_task_completed(
        self,
        task_id: str,
        token_usage: Optional[int] = None,
        execution_time: Optional[float] = None
    ):
        """Log task completion"""
        msg = f"Task completed: {task_id}"
        if token_usage:
            msg += f" (tokens: {token_usage}"
        if execution_time:
            msg += f", time: {execution_time:.1f}s"
        if token_usage or execution_time:
            msg += ")"
        self.logger.info(msg)

    def log_task_failed(self, task_id: str, error: str):
        """Log task failure"""
        self.logger.error(f"Task failed: {task_id}")
        self.logger.error(f"  Error: {error}")

    def log_agent_output(self, task_id: str, output: str):
        """Log raw agent output for debugging"""
        log_file = self.log_dir / f"task_{task_id}_output.log"
        with open(log_file, "a") as f:
            f.write(f"[{datetime.now().isoformat()}]\n")
            f.write(output)
            f.write("\n---\n")

    def info(self, message: str):
        """Generic info log"""
        self.logger.info(message)

    def debug(self, message: str):
        """Generic debug log"""
        self.logger.debug(message)

    def error(self, message: str):
        """Generic error log"""
        self.logger.error(message)

    def warning(self, message: str):
        """Generic warning log"""
        self.logger.warning(message)
