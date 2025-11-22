"""
Agent Manager - Orchestrates Claude Code headless processes
Spawns claude CLI with specific configurations per task
"""
import subprocess
import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from .task_queue import Task, TaskQueue, TaskStatus
from .logger import NightShiftLogger
from .file_tracker import FileTracker
from .notifier import Notifier
from .docker_executor import DockerExecutor


class AgentManager:
    """Manages Claude Code headless execution for tasks"""

    def __init__(
        self,
        task_queue: TaskQueue,
        logger: NightShiftLogger,
        output_dir: str = "output",
        claude_bin: str = "claude",
        enable_notifications: bool = True,
        use_docker: bool = False,
        docker_image: str = "nightshift-claude-executor:latest"
    ):
        self.task_queue = task_queue
        self.logger = logger
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.claude_bin = claude_bin
        self.enable_notifications = enable_notifications
        self.use_docker = use_docker
        self.docker_image = docker_image

        # Initialize Docker executor if enabled
        self.docker_executor = None
        if self.use_docker:
            self.docker_executor = DockerExecutor(image_name=docker_image)
            # Check if Docker image exists
            if not self.docker_executor.check_image_exists():
                self.logger.warning(
                    f"Docker image '{docker_image}' not found. "
                    "Please build it with: ./scripts/build-executor.sh"
                )

        # Notifier uses notifications directory next to output
        notifications_dir = self.output_dir.parent / "notifications"
        self.notifier = Notifier(notification_dir=str(notifications_dir)) if enable_notifications else None

    def execute_task(
        self,
        task: Task,
        timeout: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Execute a task using Claude headless mode

        Returns:
            Dict with keys: success, output, token_usage, execution_time, error
        """
        start_time = time.time()

        # Update task status to RUNNING
        self.task_queue.update_status(task.task_id, TaskStatus.RUNNING)

        # Start file tracking
        file_tracker = FileTracker()
        file_tracker.start_tracking()

        try:
            # Build Claude command
            if self.use_docker:
                # Use Docker executor
                claude_args = self._build_claude_args(task)
                cmd = self.docker_executor.build_docker_command(
                    claude_args,
                    additional_mounts=task.additional_mounts
                )
                cmd_str = " ".join(cmd)  # For logging
            else:
                # Use native execution
                cmd_str = self._build_command(task)
                cmd = cmd_str  # For shell=True execution

            # Log the exact command for debugging
            self.logger.info("=" * 60)
            self.logger.info("EXECUTING CLAUDE COMMAND:")
            self.logger.info(cmd_str if isinstance(cmd_str, str) else " ".join(cmd))
            self.logger.info("=" * 60)

            self.logger.log_task_started(task.task_id, cmd_str if isinstance(cmd_str, str) else " ".join(cmd))

            # Execute with timeout
            if self.use_docker:
                # Docker execution using executor's execute method
                result = self.docker_executor.execute(
                    claude_args,
                    timeout=timeout,
                    additional_mounts=task.additional_mounts
                )
            else:
                # Native execution (string, with shell)
                result = subprocess.run(
                    cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )

            execution_time = time.time() - start_time

            # Parse output
            output_data = self._parse_output(result.stdout, result.stderr)

            # Save full output to file
            output_file = self.output_dir / f"{task.task_id}_output.json"
            with open(output_file, "w") as f:
                json.dump({
                    "task_id": task.task_id,
                    "command": cmd,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode,
                    "execution_time": execution_time
                }, f, indent=2)

            # Log agent output
            self.logger.log_agent_output(task.task_id, result.stdout)

            if result.returncode == 0:
                # Success - get file changes
                file_changes = file_tracker.stop_tracking()
                file_tracker.save_changes(task.task_id, file_changes, str(self.output_dir))

                self.task_queue.update_status(
                    task.task_id,
                    TaskStatus.COMPLETED,
                    result_path=str(output_file),
                    token_usage=output_data.get("token_usage"),
                    execution_time=execution_time
                )
                self.logger.log_task_completed(
                    task.task_id,
                    output_data.get("token_usage"),
                    execution_time
                )

                # Send notification
                if self.notifier:
                    self.notifier.notify(
                        task_id=task.task_id,
                        task_description=task.description,
                        success=True,
                        execution_time=execution_time,
                        token_usage=output_data.get("token_usage"),
                        file_changes=file_changes,
                        result_path=str(output_file)
                    )

                return {
                    "success": True,
                    "output": output_data.get("content", result.stdout),
                    "token_usage": output_data.get("token_usage"),
                    "execution_time": execution_time,
                    "result_path": str(output_file),
                    "file_changes": file_changes
                }
            else:
                # Command failed
                file_changes = file_tracker.stop_tracking()
                error_msg = result.stderr or "Claude process returned non-zero exit code"

                self.task_queue.update_status(
                    task.task_id,
                    TaskStatus.FAILED,
                    error_message=error_msg,
                    execution_time=execution_time
                )
                self.logger.log_task_failed(task.task_id, error_msg)

                # Send notification
                if self.notifier:
                    self.notifier.notify(
                        task_id=task.task_id,
                        task_description=task.description,
                        success=False,
                        execution_time=execution_time,
                        token_usage=None,
                        file_changes=file_changes,
                        error_message=error_msg
                    )

                return {
                    "success": False,
                    "error": error_msg,
                    "execution_time": execution_time,
                    "file_changes": file_changes
                }

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            file_changes = file_tracker.stop_tracking()
            error_msg = f"Task exceeded timeout of {timeout or task.estimated_time}s"

            self.task_queue.update_status(
                task.task_id,
                TaskStatus.FAILED,
                error_message=error_msg,
                execution_time=execution_time
            )
            self.logger.log_task_failed(task.task_id, error_msg)

            if self.notifier:
                self.notifier.notify(
                    task_id=task.task_id,
                    task_description=task.description,
                    success=False,
                    execution_time=execution_time,
                    token_usage=None,
                    file_changes=file_changes,
                    error_message=error_msg
                )

            return {
                "success": False,
                "error": error_msg,
                "execution_time": execution_time,
                "file_changes": file_changes
            }

        except Exception as e:
            execution_time = time.time() - start_time
            file_changes = file_tracker.stop_tracking()
            error_msg = f"Unexpected error: {str(e)}"

            self.task_queue.update_status(
                task.task_id,
                TaskStatus.FAILED,
                error_message=error_msg,
                execution_time=execution_time
            )
            self.logger.log_task_failed(task.task_id, error_msg)

            if self.notifier:
                self.notifier.notify(
                    task_id=task.task_id,
                    task_description=task.description,
                    success=False,
                    execution_time=execution_time,
                    token_usage=None,
                    file_changes=file_changes,
                    error_message=error_msg
                )

            return {
                "success": False,
                "error": error_msg,
                "execution_time": execution_time,
                "file_changes": file_changes
            }

    def _build_claude_args(self, task: Task) -> List[str]:
        """Build Claude CLI arguments as list (for Docker execution)"""
        args = ["-p", task.description]

        # Output format (requires --verbose for stream-json)
        args.extend(["--output-format", "stream-json"])
        args.append("--verbose")

        # Add allowed tools if specified
        if task.allowed_tools:
            args.append("--allowed-tools")
            args.extend(task.allowed_tools)

        # Add system prompt if specified
        if task.system_prompt:
            args.extend(["--system-prompt", task.system_prompt])

        return args

    def _build_command(self, task: Task) -> str:
        """Build Claude CLI command from task specification (for native execution)"""
        cmd_parts = [self.claude_bin, "-p"]

        # Add the main prompt
        cmd_parts.append(f'"{task.description}"')

        # Output format (requires --verbose for stream-json)
        cmd_parts.append("--output-format stream-json")
        cmd_parts.append("--verbose")

        # Add allowed tools if specified
        if task.allowed_tools:
            tools_str = " ".join(task.allowed_tools)
            cmd_parts.append(f"--allowed-tools {tools_str}")

        # Add system prompt if specified
        if task.system_prompt:
            # Escape quotes in system prompt
            escaped_prompt = task.system_prompt.replace('"', '\\"')
            cmd_parts.append(f'--system-prompt "{escaped_prompt}"')

        return " ".join(cmd_parts)

    def _parse_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """
        Parse Claude stream-json output
        Extract token usage and final content
        """
        result = {
            "content": "",
            "token_usage": None,
            "tool_calls": []
        }

        if not stdout:
            return result

        # Parse stream-json output
        for line in stdout.strip().split("\n"):
            if not line:
                continue

            try:
                data = json.loads(line)

                # Extract text content
                if "type" in data and data["type"] == "text":
                    result["content"] += data.get("text", "")

                # Extract token usage
                if "usage" in data:
                    result["token_usage"] = data["usage"].get("output_tokens", 0) + \
                                          data["usage"].get("input_tokens", 0)

                # Track tool calls
                if "type" in data and data["type"] == "tool_use":
                    result["tool_calls"].append({
                        "tool": data.get("name"),
                        "parameters": data.get("input", {})
                    })

            except json.JSONDecodeError:
                # Not JSON, probably plain text output
                result["content"] += line + "\n"

        return result

    def estimate_resources(self, description: str) -> Dict[str, int]:
        """
        Estimate tokens and time for a task
        (Simple heuristic for MVP, can be improved)
        """
        # Rough heuristics
        words = len(description.split())
        estimated_tokens = words * 2  # Very rough estimate

        # Base time estimates per task type
        if "arxiv" in description.lower() or "paper" in description.lower():
            estimated_time = 60  # 1 minute for paper tasks
            estimated_tokens += 2000  # Paper download + summarization
        elif "csv" in description.lower() or "data" in description.lower():
            estimated_time = 120  # 2 minutes for data analysis
            estimated_tokens += 1000
        else:
            estimated_time = 30  # 30 seconds default
            estimated_tokens += 500

        return {
            "estimated_tokens": estimated_tokens,
            "estimated_time": estimated_time
        }
