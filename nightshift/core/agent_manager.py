"""
Agent Manager - Orchestrates Claude Code headless processes
Spawns claude CLI with specific configurations per task
"""
import subprocess
import json
import time
import os
import signal
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from .task_queue import Task, TaskQueue, TaskStatus
from .logger import NightShiftLogger
from .file_tracker import FileTracker
from .notifier import Notifier
from .sandbox import SandboxManager


class AgentManager:
    """Manages Claude Code headless execution for tasks"""

    def __init__(
        self,
        task_queue: TaskQueue,
        logger: NightShiftLogger,
        output_dir: str = "output",
        claude_bin: str = "claude",
        enable_notifications: bool = True,
        enable_sandbox: bool = True
    ):
        self.task_queue = task_queue
        self.logger = logger
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.claude_bin = claude_bin
        self.enable_notifications = enable_notifications
        self.enable_sandbox = enable_sandbox

        # Notifier uses notifications directory next to output
        notifications_dir = self.output_dir.parent / "notifications"
        self.notifier = Notifier(notification_dir=str(notifications_dir)) if enable_notifications else None

        # Sandbox manager for macOS isolation
        self.sandbox = SandboxManager() if enable_sandbox and SandboxManager.is_available() else None
        if enable_sandbox and not self.sandbox:
            self.logger.warning("Sandboxing requested but sandbox-exec not available on this system")

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

        # Start file tracking
        file_tracker = FileTracker()
        file_tracker.start_tracking()

        try:
            # Build Claude command (potentially wrapped with sandbox)
            cmd = self._build_command(task)

            # Log the exact command for debugging
            self.logger.info("=" * 80)
            self.logger.info("EXECUTING COMMAND:")
            if self.sandbox and task.allowed_directories:
                self.logger.info("🔒 SANDBOXED EXECUTION (writes restricted)")
                self.logger.info(f"   Allowed directories: {task.allowed_directories}")
            self.logger.info("")
            self.logger.info(f"Full command: {cmd}")
            self.logger.info("=" * 80)

            self.logger.log_task_started(task.task_id, cmd)

            # Set up environment variables
            env = dict(os.environ)

            # If needs_git, try to get gh token for sandbox compatibility
            if task.needs_git:
                # Try to get gh token from gh CLI
                try:
                    token_result = subprocess.run(
                        ["gh", "auth", "token"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if token_result.returncode == 0:
                        env['GH_TOKEN'] = token_result.stdout.strip()
                        self.logger.info("Loaded GH_TOKEN from gh CLI for sandbox compatibility")
                except Exception as e:
                    self.logger.warning(f"Could not load GH_TOKEN: {e}")

            # Execute with Popen to get PID immediately
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env
            )

            # Store PID in task metadata immediately
            self.task_queue.update_status(
                task.task_id,
                TaskStatus.RUNNING,
                process_id=process.pid
            )
            self.logger.info(f"Task {task.task_id} executing with PID: {process.pid}")

            # Wait for completion
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                returncode = process.returncode
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                raise

            execution_time = time.time() - start_time

            # Create a result object similar to subprocess.run
            class Result:
                def __init__(self, stdout, stderr, returncode):
                    self.stdout = stdout
                    self.stderr = stderr
                    self.returncode = returncode

            result = Result(stdout, stderr, returncode)

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

    def _build_command(self, task: Task) -> str:
        """Build Claude CLI command from task specification"""
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

        claude_cmd = " ".join(cmd_parts)

        # Wrap with sandbox if enabled
        if self.sandbox:
            try:
                # If no directories specified, run in read-only mode (no write access except /tmp)
                if not task.allowed_directories:
                    self.logger.info("Sandboxing task in READ-ONLY mode (no write directories specified)")
                    # Empty list means no write access except system temp dirs
                    validated_dirs = []
                else:
                    # Validate directories before sandboxing
                    validated_dirs = SandboxManager.validate_directories(task.allowed_directories)
                    self.logger.info(f"Sandboxing task with allowed directories: {validated_dirs}")

                if task.needs_git:
                    self.logger.info("Git operations enabled - allowing device file access")

                return self.sandbox.wrap_command(
                    claude_cmd,
                    validated_dirs,
                    profile_name=task.task_id,
                    needs_git=bool(task.needs_git)
                )
            except ValueError as e:
                self.logger.error(f"Sandbox validation failed: {e}")
                raise

        return claude_cmd

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

    def pause_task(self, task_id: str) -> Dict[str, Any]:
        """
        Pause a running task by sending SIGSTOP to its subprocess

        Returns:
            Dict with keys: success, message, error
        """
        # Get task
        task = self.task_queue.get_task(task_id)
        if not task:
            return {
                "success": False,
                "error": f"Task {task_id} not found"
            }

        # Verify task is running
        if task.status != TaskStatus.RUNNING.value:
            return {
                "success": False,
                "error": f"Task {task_id} is not running (current status: {task.status})"
            }

        # Verify we have a PID
        if not task.process_id:
            return {
                "success": False,
                "error": f"Task {task_id} has no process ID stored"
            }

        # Verify process is still alive
        try:
            os.kill(task.process_id, 0)  # Signal 0 checks if process exists
        except ProcessLookupError:
            return {
                "success": False,
                "error": f"Process {task.process_id} no longer exists"
            }
        except PermissionError:
            return {
                "success": False,
                "error": f"No permission to signal process {task.process_id}"
            }

        # Send SIGSTOP to pause the process
        try:
            os.kill(task.process_id, signal.SIGSTOP)
            self.task_queue.update_status(task_id, TaskStatus.PAUSED)
            self.logger.info(f"Paused task {task_id} (PID: {task.process_id})")
            return {
                "success": True,
                "message": f"Task {task_id} paused successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to pause task: {str(e)}"
            }

    def resume_task(self, task_id: str) -> Dict[str, Any]:
        """
        Resume a paused task by sending SIGCONT to its subprocess

        Returns:
            Dict with keys: success, message, error
        """
        # Get task
        task = self.task_queue.get_task(task_id)
        if not task:
            return {
                "success": False,
                "error": f"Task {task_id} not found"
            }

        # Verify task is paused
        if task.status != TaskStatus.PAUSED.value:
            return {
                "success": False,
                "error": f"Task {task_id} is not paused (current status: {task.status})"
            }

        # Verify we have a PID
        if not task.process_id:
            return {
                "success": False,
                "error": f"Task {task_id} has no process ID stored"
            }

        # Verify process is still alive
        try:
            os.kill(task.process_id, 0)  # Signal 0 checks if process exists
        except ProcessLookupError:
            return {
                "success": False,
                "error": f"Process {task.process_id} no longer exists"
            }
        except PermissionError:
            return {
                "success": False,
                "error": f"No permission to signal process {task.process_id}"
            }

        # Send SIGCONT to resume the process
        try:
            os.kill(task.process_id, signal.SIGCONT)
            self.task_queue.update_status(task_id, TaskStatus.RUNNING)
            self.logger.info(f"Resumed task {task_id} (PID: {task.process_id})")
            return {
                "success": True,
                "message": f"Task {task_id} resumed successfully"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to resume task: {str(e)}"
            }
