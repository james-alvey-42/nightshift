"""
Agent Manager - Orchestrates Claude Code headless processes
Spawns claude CLI with specific configurations per task
"""

import subprocess
import json
import time
import os
import signal
import fcntl
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime

from .task_queue import Task, TaskQueue, TaskStatus
from .logger import NightShiftLogger
from .file_tracker import FileTracker
from .notifier import Notifier
from .sandbox import SandboxManager
from .mcp_config_manager import MCPConfigManager
from .scratch_manager import ScratchManager


class AgentManager:
    """Manages Claude Code headless execution for tasks"""

    def __init__(
        self,
        task_queue: TaskQueue,
        logger: NightShiftLogger,
        output_dir: str = "output",
        claude_bin: str = "claude",
        enable_notifications: bool = True,
        enable_sandbox: bool = True,
        enable_terminal_notifications: bool = True,
        mcp_config_path: Optional[str] = None,
        cleanup_scratch: bool = False,  # Don't cleanup scratch for task resumption
    ):
        self.task_queue = task_queue
        self.logger = logger
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.claude_bin = claude_bin
        self.enable_notifications = enable_notifications
        self.enable_sandbox = enable_sandbox
        self.cleanup_scratch = cleanup_scratch

        # Notifier uses notifications directory next to output
        notifications_dir = self.output_dir.parent / "notifications"
        self.notifier = (
            Notifier(
                notification_dir=str(notifications_dir),
                enable_terminal_output=enable_terminal_notifications,
            )
            if enable_notifications
            else None
        )

        # Sandbox manager for macOS isolation
        self.sandbox = (
            SandboxManager()
            if enable_sandbox and SandboxManager.is_available()
            else None
        )
        if enable_sandbox and not self.sandbox:
            self.logger.warning(
                "Sandboxing requested but sandbox-exec not available on this system"
            )

        # MCP config manager for dynamic minimal configs
        self.mcp_manager = MCPConfigManager(
            base_config_path=mcp_config_path, logger=logger
        )

        # Scratch manager for isolated task execution
        self.scratch_manager = ScratchManager(logger=logger)

    def execute_task(self, task: Task, timeout: Optional[int] = None) -> Dict[str, Any]:
        """
        Execute a task using Claude headless mode

        Args:
            task: Task object to execute
            timeout: Optional timeout override (seconds). If not provided, uses task.timeout_seconds (default: 900)

        Returns:
            Dict with keys: success, output, token_usage, execution_time, error
        """
        # Use timeout from task if not explicitly provided
        if timeout is None:
            timeout = task.timeout_seconds or 900

        start_time = time.time()

        # Determine working directory based on task configuration
        scratch_dir = None
        working_dir = None

        if task.use_scratch:
            # Create isolated scratch directory with task resources
            self.logger.info(f"Setting up scratch directory for task {task.task_id}")
            scratch_dir = self.scratch_manager.create_scratch(
                task_id=task.task_id,
                git_repos=task.scratch_git_repos,
                copy_paths=task.scratch_copy_paths
            )
            working_dir = str(scratch_dir)
            self.logger.info(f"Scratch directory ready: {scratch_dir}")
        elif task.working_directory:
            # Use explicitly specified working directory
            working_dir = task.working_directory
            self.logger.info(f"Using specified working directory: {working_dir}")
        else:
            # Use current working directory
            working_dir = str(Path.cwd())
            self.logger.info(f"Using current working directory: {working_dir}")

        # Start file tracking in working directory
        file_tracker = FileTracker(watch_dir=working_dir)
        file_tracker.start_tracking()

        # Track MCP config and sandbox profile for cleanup/copying
        mcp_config_path = None
        sandbox_profile_path = None

        try:
            # Build Claude command (potentially wrapped with sandbox)
            # Note: working_dir is used as subprocess cwd, not as a CLI flag
            # Pass working_dir to sandbox manager for proper write permissions
            cmd, mcp_config_path, sandbox_profile_path = self._build_command(task, working_dir)

            self.logger.log_task_started(task.task_id, cmd)

            # Set up environment variables
            env = dict(os.environ)

            # If sandboxed, pass Claude Code OAuth token for authentication
            # The sandbox blocks Keychain access, so we need to pass the token explicitly
            if self.sandbox:
                # Check if CLAUDE_CODE_OAUTH_TOKEN is in the parent environment
                if "CLAUDE_CODE_OAUTH_TOKEN" not in env:
                    # Try to read it from ~/.nightshift/claude_token file
                    token_file = Path.home() / ".nightshift" / "claude_token"
                    if token_file.exists():
                        try:
                            env["CLAUDE_CODE_OAUTH_TOKEN"] = token_file.read_text().strip()
                            self.logger.info(
                                f"Loaded CLAUDE_CODE_OAUTH_TOKEN from {token_file}"
                            )
                        except Exception as e:
                            self.logger.warning(
                                f"Failed to read Claude token from {token_file}: {e}"
                            )
                    else:
                        # Log a warning - the user should set it
                        self.logger.warning(
                            "CLAUDE_CODE_OAUTH_TOKEN not found in environment. "
                            "Claude Code may fail to authenticate in sandbox. "
                            f"Either set CLAUDE_CODE_OAUTH_TOKEN environment variable "
                            f"or create {token_file} with your token."
                        )
                else:
                    self.logger.info("Using CLAUDE_CODE_OAUTH_TOKEN for sandboxed authentication")

            # If needs_git, try to get gh token for sandbox compatibility
            if task.needs_git:
                # Try to get gh token from gh CLI
                try:
                    token_result = subprocess.run(
                        ["gh", "auth", "token"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if token_result.returncode == 0:
                        env["GH_TOKEN"] = token_result.stdout.strip()
                        self.logger.info(
                            "Loaded GH_TOKEN from gh CLI for sandbox compatibility"
                        )
                except Exception as e:
                    self.logger.warning(f"Could not load GH_TOKEN: {e}")

            # Pass through MCP server API keys to sandboxed environment
            # Note: We don't pass ANTHROPIC_API_KEY as it interferes with Claude authentication
            mcp_api_keys = ["GEMINI_API_KEY", "OPENAI_API_KEY"]
            for key in mcp_api_keys:
                if key in os.environ:
                    env[key] = os.environ[key]
                    self.logger.info(f"Passing {key} to sandboxed environment")

            # Create output file path immediately
            output_file = self.output_dir / f"{task.task_id}_output.json"

            # Save resumption state if using scratch directory
            if scratch_dir:
                self._save_resumption_state(
                    scratch_dir=scratch_dir,
                    task=task,
                    command=cmd,
                    env=env,
                    working_dir=working_dir,
                    mcp_config_path=mcp_config_path,
                    sandbox_profile_path=sandbox_profile_path
                )

            # Log execution details
            self.logger.info("=" * 80)
            self.logger.info("EXECUTING COMMAND:")
            self.logger.info(f"Working directory: {working_dir}")
            if self.sandbox and task.allowed_directories:
                self.logger.info("🔒 SANDBOXED EXECUTION (writes restricted)")
                self.logger.info(f"   Allowed directories: {task.allowed_directories}")
            self.logger.info("")
            self.logger.info(f"Full command: {cmd}")
            self.logger.info("=" * 80)

            # Execute with Popen to get PID immediately
            # Set working directory via cwd parameter
            process = subprocess.Popen(
                cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                cwd=working_dir  # Change to working directory (scratch or explicit)
            )

            # Store PID, result path, and scratch directory in task metadata immediately
            update_kwargs = {
                "process_id": process.pid,
                "result_path": str(output_file),
            }
            if scratch_dir:
                update_kwargs["scratch_directory"] = str(scratch_dir)

            self.task_queue.update_status(
                task.task_id,
                TaskStatus.RUNNING,
                **update_kwargs
            )
            self.logger.info(f"Task {task.task_id} executing with PID: {process.pid}")

            # Initialize output file with metadata
            with open(output_file, "w") as f:
                json.dump(
                    {
                        "task_id": task.task_id,
                        "command": cmd,
                        "stdout": "",
                        "stderr": "",
                        "returncode": None,
                        "execution_time": None,
                        "status": "running",
                    },
                    f,
                    indent=2,
                )

            # Stream output to file in real-time
            stdout_lines = []
            stderr_lines = []

            # Set non-blocking mode on stdout and stderr
            if process.stdout:
                flags = fcntl.fcntl(process.stdout.fileno(), fcntl.F_GETFL)
                fcntl.fcntl(
                    process.stdout.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK
                )
            if process.stderr:
                flags = fcntl.fcntl(process.stderr.fileno(), fcntl.F_GETFL)
                fcntl.fcntl(
                    process.stderr.fileno(), fcntl.F_SETFL, flags | os.O_NONBLOCK
                )

            # Wait for completion while streaming output
            try:
                while True:
                    # Check if process is still running
                    returncode = process.poll()

                    # Read available stdout
                    if process.stdout:
                        try:
                            line = process.stdout.readline()
                            if line:
                                stdout_lines.append(line)
                                # Update file with partial output
                                with open(output_file, "w") as f:
                                    json.dump(
                                        {
                                            "task_id": task.task_id,
                                            "command": cmd,
                                            "stdout": "".join(stdout_lines),
                                            "stderr": "".join(stderr_lines),
                                            "returncode": returncode,
                                            "execution_time": time.time() - start_time,
                                            "status": (
                                                "running"
                                                if returncode is None
                                                else "completed"
                                            ),
                                        },
                                        f,
                                        indent=2,
                                    )
                        except:
                            pass

                    # Read available stderr
                    if process.stderr:
                        try:
                            line = process.stderr.readline()
                            if line:
                                stderr_lines.append(line)
                        except:
                            pass

                    # Exit if process completed
                    if returncode is not None:
                        # Read any remaining output
                        if process.stdout:
                            remaining = process.stdout.read()
                            if remaining:
                                stdout_lines.append(remaining)
                        if process.stderr:
                            remaining = process.stderr.read()
                            if remaining:
                                stderr_lines.append(remaining)
                        break

                    # Small sleep to avoid busy waiting
                    time.sleep(0.1)

                    # Check timeout
                    if timeout and (time.time() - start_time) > timeout:
                        process.kill()
                        raise subprocess.TimeoutExpired(cmd, timeout)

            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                stdout_lines.append(stdout)
                stderr_lines.append(stderr)
                raise

            execution_time = time.time() - start_time

            # Combine output
            stdout = "".join(stdout_lines)
            stderr = "".join(stderr_lines)

            # Create a result object similar to subprocess.run
            class Result:
                def __init__(self, stdout, stderr, returncode):
                    self.stdout = stdout
                    self.stderr = stderr
                    self.returncode = returncode

            result = Result(stdout, stderr, returncode)

            # Parse output
            output_data = self._parse_output(result.stdout, result.stderr)

            # Save final output to file
            with open(output_file, "w") as f:
                json.dump(
                    {
                        "task_id": task.task_id,
                        "command": cmd,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                        "returncode": result.returncode,
                        "execution_time": execution_time,
                        "status": "completed",
                    },
                    f,
                    indent=2,
                )

            # Log agent output
            self.logger.log_agent_output(task.task_id, result.stdout)

            if result.returncode == 0:
                # Success - get file changes
                file_changes = file_tracker.stop_tracking()
                file_tracker.save_changes(
                    task.task_id, file_changes, str(self.output_dir)
                )

                self.task_queue.update_status(
                    task.task_id,
                    TaskStatus.COMPLETED,
                    result_path=str(output_file),
                    token_usage=output_data.get("token_usage"),
                    execution_time=execution_time,
                )
                self.logger.log_task_completed(
                    task.task_id, output_data.get("token_usage"), execution_time
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
                        result_path=str(output_file),
                    )

                return {
                    "success": True,
                    "output": output_data.get("content", result.stdout),
                    "token_usage": output_data.get("token_usage"),
                    "execution_time": execution_time,
                    "result_path": str(output_file),
                    "file_changes": file_changes,
                }
            else:
                # Command failed
                file_changes = file_tracker.stop_tracking()
                error_msg = (
                    result.stderr or "Claude process returned non-zero exit code"
                )

                self.task_queue.update_status(
                    task.task_id,
                    TaskStatus.FAILED,
                    error_message=error_msg,
                    execution_time=execution_time,
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
                        error_message=error_msg,
                    )

                return {
                    "success": False,
                    "error": error_msg,
                    "execution_time": execution_time,
                    "file_changes": file_changes,
                }

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            file_changes = file_tracker.stop_tracking()
            error_msg = f"Task exceeded timeout of {timeout or task.estimated_time}s"

            self.task_queue.update_status(
                task.task_id,
                TaskStatus.FAILED,
                error_message=error_msg,
                execution_time=execution_time,
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
                    error_message=error_msg,
                )

            return {
                "success": False,
                "error": error_msg,
                "execution_time": execution_time,
                "file_changes": file_changes,
            }

        except Exception as e:
            execution_time = time.time() - start_time
            file_changes = file_tracker.stop_tracking()
            error_msg = f"Unexpected error: {str(e)}"

            self.task_queue.update_status(
                task.task_id,
                TaskStatus.FAILED,
                error_message=error_msg,
                execution_time=execution_time,
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
                    error_message=error_msg,
                )

            return {
                "success": False,
                "error": error_msg,
                "execution_time": execution_time,
                "file_changes": file_changes,
            }

        finally:
            # Cleanup temporary MCP config file
            if mcp_config_path:
                try:
                    os.remove(mcp_config_path)
                    self.logger.debug(f"Cleaned up MCP config: {mcp_config_path}")
                except Exception as e:
                    self.logger.warning(
                        f"Failed to cleanup MCP config {mcp_config_path}: {e}"
                    )

            # Cleanup scratch directory if used and cleanup is enabled
            if scratch_dir and self.cleanup_scratch:
                try:
                    self.logger.info(f"Tearing down scratch directory: {scratch_dir}")
                    result = self.scratch_manager.teardown_scratch(
                        scratch_dir=scratch_dir,
                        copy_back=True,  # Copy modified files back to original locations
                        keep_scratch=False  # Clean up scratch after copying
                    )

                    if result['copied_files']:
                        self.logger.info(f"Copied {len(result['copied_files'])} files back from scratch")
                        for file in result['copied_files'][:10]:  # Log first 10
                            self.logger.debug(f"  - {file}")

                    if result['errors']:
                        self.logger.warning(f"Scratch teardown had {len(result['errors'])} errors")
                        for error in result['errors'][:5]:  # Log first 5 errors
                            self.logger.warning(f"  - {error}")

                except Exception as e:
                    self.logger.error(f"Failed to teardown scratch directory {scratch_dir}: {e}")
            elif scratch_dir:
                self.logger.info(f"Scratch directory preserved for task resumption: {scratch_dir}")

    def _build_command(self, task: Task, working_dir: Optional[str] = None) -> tuple[str, Optional[str], Optional[str]]:
        """
        Build Claude CLI command from task specification.

        Args:
            task: Task object to build command for
            working_dir: Working directory path (needed for sandbox permissions)

        Returns:
            Tuple of (command_string, mcp_config_path, sandbox_profile_path)
            mcp_config_path and sandbox_profile_path are returned for cleanup/copying after execution

        Note:
            Working directory is set via subprocess cwd parameter, not CLI flag
        """
        cmd_parts = [self.claude_bin, "-p"]

        # Add the main prompt
        cmd_parts.append(f'"{task.description}"')

        # Output format (requires --verbose for stream-json)
        cmd_parts.append("--output-format stream-json")
        cmd_parts.append("--verbose")

        # Generate minimal MCP config based on task's allowed_tools
        # This is the KEY optimization - only load MCP servers we actually need!
        mcp_config_path = None
        if task.allowed_tools:
            mcp_config_path = self.mcp_manager.create_minimal_config(
                required_tools=task.allowed_tools, profile_name=task.task_id
            )

            # Log the optimization
            savings = self.mcp_manager.estimate_token_savings(task.allowed_tools)
            self.logger.info(
                f"📊 MCP Optimization for {task.task_id}: "
                f"Loading {savings['loaded_servers']}/{savings['total_servers']} servers "
                f"(~{savings['estimated_tokens_saved']:,} tokens saved, "
                f"{savings['reduction_percent']:.0f}% reduction)"
            )

            # Add MCP config to command
            cmd_parts.append(f"--mcp-config {mcp_config_path}")

            # Add allowed tools (still needed for extra safety)
            tools_str = " ".join(task.allowed_tools)
            cmd_parts.append(f"--allowed-tools {tools_str}")

            # DEBUG: Print MCP config contents
            self.logger.info(f"🔍 MCP Config file: {mcp_config_path}")
            try:
                with open(mcp_config_path, 'r') as f:
                    mcp_config_contents = json.load(f)
                    self.logger.info(f"🔍 MCP Config contents: {json.dumps(mcp_config_contents, indent=2)}")
            except Exception as e:
                self.logger.warning(f"Could not read MCP config: {e}")
        else:
            # No tools specified - use empty MCP config
            mcp_config_path = self.mcp_manager.get_empty_config(
                profile_name=task.task_id
            )
            cmd_parts.append(f"--mcp-config {mcp_config_path}")
            self.logger.info(
                f"🔒 No MCP tools needed for {task.task_id}, using empty config"
            )

            # DEBUG: Print MCP config contents
            self.logger.info(f"🔍 MCP Config file: {mcp_config_path}")
            try:
                with open(mcp_config_path, 'r') as f:
                    mcp_config_contents = json.load(f)
                    self.logger.info(f"🔍 MCP Config contents: {json.dumps(mcp_config_contents, indent=2)}")
            except Exception as e:
                self.logger.warning(f"Could not read MCP config: {e}")

        # Add system prompt if specified
        if task.system_prompt:
            # Escape quotes in system prompt
            escaped_prompt = task.system_prompt.replace('"', '\\"')
            cmd_parts.append(f'--system-prompt "{escaped_prompt}"')

        claude_cmd = " ".join(cmd_parts)

        # Wrap with sandbox if enabled
        sandbox_profile_path = None
        if self.sandbox:
            try:
                # Build list of allowed directories
                allowed_dirs = []

                # Include working directory if it should be writable
                # (scratch directories are always writable, explicit working_dir may or may not be)
                if task.use_scratch and working_dir:
                    # Scratch directory should always be writable
                    allowed_dirs.append(working_dir)
                    self.logger.info(f"Including scratch working directory in sandbox: {working_dir}")

                # Add task-specific allowed directories if specified
                if task.allowed_directories:
                    allowed_dirs.extend(task.allowed_directories)

                # Validate directories before sandboxing
                if allowed_dirs:
                    validated_dirs = SandboxManager.validate_directories(allowed_dirs)
                    self.logger.info(
                        f"Sandboxing task with allowed directories: {validated_dirs}"
                    )
                else:
                    # If no directories specified, run in read-only mode
                    self.logger.info(
                        "Sandboxing task in READ-ONLY mode (no write directories specified)"
                    )
                    validated_dirs = []

                if task.needs_git:
                    self.logger.info(
                        "Git operations enabled - allowing device file access"
                    )

                sandboxed_cmd, sandbox_profile_path = self.sandbox.wrap_command(
                    claude_cmd,
                    validated_dirs,
                    profile_name=task.task_id,
                    needs_git=bool(task.needs_git),
                )
                return sandboxed_cmd, mcp_config_path, sandbox_profile_path
            except ValueError as e:
                self.logger.error(f"Sandbox validation failed: {e}")
                raise

        return claude_cmd, mcp_config_path, sandbox_profile_path

    def _parse_output(self, stdout: str, stderr: str) -> Dict[str, Any]:
        """
        Parse Claude stream-json output
        Extract token usage and final content
        """
        result = {"content": "", "token_usage": None, "tool_calls": []}

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

                # Extract token usage (including cache tokens)
                if "usage" in data:
                    usage = data["usage"]
                    result["token_usage"] = (
                        usage.get("output_tokens", 0)
                        + usage.get("input_tokens", 0)
                        + usage.get("cache_creation_input_tokens", 0)
                        + usage.get("cache_read_input_tokens", 0)
                    )

                # Track tool calls
                if "type" in data and data["type"] == "tool_use":
                    result["tool_calls"].append(
                        {"tool": data.get("name"), "parameters": data.get("input", {})}
                    )

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

        return {"estimated_tokens": estimated_tokens, "estimated_time": estimated_time}

    def pause_task(self, task_id: str) -> Dict[str, Any]:
        """
        Pause a running task by sending SIGSTOP to its subprocess

        Returns:
            Dict with keys: success, message, error
        """
        # Get task
        task = self.task_queue.get_task(task_id)
        if not task:
            return {"success": False, "error": f"Task {task_id} not found"}

        # Verify task is running
        if task.status != TaskStatus.RUNNING.value:
            return {
                "success": False,
                "error": f"Task {task_id} is not running (current status: {task.status})",
            }

        # Verify we have a PID
        if not task.process_id:
            return {
                "success": False,
                "error": f"Task {task_id} has no process ID stored",
            }

        # Verify process is still alive
        try:
            os.kill(task.process_id, 0)  # Signal 0 checks if process exists
        except ProcessLookupError:
            return {
                "success": False,
                "error": f"Process {task.process_id} no longer exists",
            }
        except PermissionError:
            return {
                "success": False,
                "error": f"No permission to signal process {task.process_id}",
            }

        # Send SIGSTOP to pause the process
        try:
            os.kill(task.process_id, signal.SIGSTOP)
            self.task_queue.update_status(task_id, TaskStatus.PAUSED)
            self.logger.info(f"Paused task {task_id} (PID: {task.process_id})")
            return {"success": True, "message": f"Task {task_id} paused successfully"}
        except Exception as e:
            return {"success": False, "error": f"Failed to pause task: {str(e)}"}

    def resume_task(self, task_id: str) -> Dict[str, Any]:
        """
        Resume a paused task by sending SIGCONT to its subprocess

        Returns:
            Dict with keys: success, message, error
        """
        # Get task
        task = self.task_queue.get_task(task_id)
        if not task:
            return {"success": False, "error": f"Task {task_id} not found"}

        # Verify task is paused
        if task.status != TaskStatus.PAUSED.value:
            return {
                "success": False,
                "error": f"Task {task_id} is not paused (current status: {task.status})",
            }

        # Verify we have a PID
        if not task.process_id:
            return {
                "success": False,
                "error": f"Task {task_id} has no process ID stored",
            }

        # Verify process is still alive
        try:
            os.kill(task.process_id, 0)  # Signal 0 checks if process exists
        except ProcessLookupError:
            return {
                "success": False,
                "error": f"Process {task.process_id} no longer exists",
            }
        except PermissionError:
            return {
                "success": False,
                "error": f"No permission to signal process {task.process_id}",
            }

        # Send SIGCONT to resume the process
        try:
            os.kill(task.process_id, signal.SIGCONT)
            self.task_queue.update_status(task_id, TaskStatus.RUNNING)
            self.logger.info(f"Resumed task {task_id} (PID: {task.process_id})")
            return {"success": True, "message": f"Task {task_id} resumed successfully"}
        except Exception as e:
            return {"success": False, "error": f"Failed to resume task: {str(e)}"}

    def kill_task(self, task_id: str) -> Dict[str, Any]:
        """
        Kill a running or paused task by sending SIGKILL to its subprocess

        Returns:
            Dict with keys: success, message, error
        """
        # Get task
        task = self.task_queue.get_task(task_id)
        if not task:
            return {"success": False, "error": f"Task {task_id} not found"}

        # Verify task is running or paused
        if task.status not in [TaskStatus.RUNNING.value, TaskStatus.PAUSED.value]:
            return {
                "success": False,
                "error": f"Task {task_id} is not running or paused (current status: {task.status})",
            }

        # Verify we have a PID
        if not task.process_id:
            return {
                "success": False,
                "error": f"Task {task_id} has no process ID stored",
            }

        # Check if process still exists
        try:
            os.kill(task.process_id, 0)  # Signal 0 checks if process exists
        except ProcessLookupError:
            # Process already dead, just update status
            self.task_queue.update_status(
                task_id,
                TaskStatus.CANCELLED,
                error_message="Process already terminated",
            )
            self.logger.info(
                f"Task {task_id} process {task.process_id} already terminated"
            )
            return {
                "success": True,
                "message": f"Task {task_id} process was already terminated. Status updated to CANCELLED.",
            }
        except PermissionError:
            return {
                "success": False,
                "error": f"No permission to signal process {task.process_id}",
            }

        # Send SIGKILL to forcefully terminate the process
        try:
            os.kill(task.process_id, signal.SIGKILL)
            self.task_queue.update_status(
                task_id, TaskStatus.CANCELLED, error_message="Task killed by user"
            )
            self.logger.info(f"Killed task {task_id} (PID: {task.process_id})")
            return {
                "success": True,
                "message": f"Task {task_id} killed successfully (PID: {task.process_id})",
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to kill task: {str(e)}"}

    def _save_resumption_state(
        self,
        scratch_dir: Path,
        task: Task,
        command: str,
        env: Dict[str, str],
        working_dir: str,
        mcp_config_path: Optional[str],
        sandbox_profile_path: Optional[str]
    ):
        """
        Save complete state needed for task resumption

        Args:
            scratch_dir: Path to scratch directory
            task: Task object being executed
            command: Full command string being executed
            env: Environment variables
            working_dir: Working directory path
            mcp_config_path: Path to MCP config file (if any)
            sandbox_profile_path: Path to sandbox profile file (if any)
        """
        try:
            # Save task specification
            task_spec_path = scratch_dir / ".nightshift_task.json"
            with open(task_spec_path, 'w') as f:
                json.dump(task.to_dict(), f, indent=2)

            # Save execution state
            execution_state = {
                'task_id': task.task_id,
                'command': command,
                'working_dir': working_dir,
                'saved_at': datetime.now().isoformat(),
                'claude_bin': self.claude_bin,
                'enable_sandbox': self.enable_sandbox,
                'sandbox_enabled': bool(self.sandbox),
                'version': '1.0'
            }

            # Save environment variables (excluding sensitive ones)
            safe_env_keys = [
                'GH_TOKEN', 'GEMINI_API_KEY', 'OPENAI_API_KEY',
                'CLAUDE_CODE_OAUTH_TOKEN', 'PATH', 'HOME'
            ]
            execution_state['environment'] = {
                k: v for k, v in env.items()
                if k in safe_env_keys
            }

            execution_state_path = scratch_dir / ".nightshift_execution.json"
            with open(execution_state_path, 'w') as f:
                json.dump(execution_state, f, indent=2)

            # Copy MCP config to scratch if it exists
            if mcp_config_path and os.path.exists(mcp_config_path):
                mcp_copy_path = scratch_dir / ".nightshift_mcp_config.json"
                shutil.copy2(mcp_config_path, mcp_copy_path)
                self.logger.debug(f"Saved MCP config to scratch: {mcp_copy_path}")

            # Copy sandbox profile to scratch if sandboxing is enabled
            if sandbox_profile_path and os.path.exists(sandbox_profile_path):
                # Copy the actual .sb profile file
                sandbox_profile_copy = scratch_dir / ".nightshift_sandbox.sb"
                shutil.copy2(sandbox_profile_path, sandbox_profile_copy)
                self.logger.debug(f"Saved sandbox profile to scratch: {sandbox_profile_copy}")

                # Also save sandbox configuration metadata
                sandbox_config = {
                    'enabled': True,
                    'profile_path': str(sandbox_profile_copy),
                    'allowed_directories': task.allowed_directories or [],
                    'needs_git': task.needs_git or False,
                    'version': '1.0'
                }
                sandbox_config_path = scratch_dir / ".nightshift_sandbox.json"
                with open(sandbox_config_path, 'w') as f:
                    json.dump(sandbox_config, f, indent=2)

            self.logger.info(f"Saved resumption state to scratch directory: {scratch_dir}")

        except Exception as e:
            self.logger.error(f"Failed to save resumption state: {e}")
