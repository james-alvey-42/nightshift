"""
Docker Executor - Runs Claude Code in isolated containers
Wraps Claude CLI execution in Docker for security and isolation
"""
import os
import subprocess
from pathlib import Path
from typing import List, Dict, Optional


class DockerExecutor:
    """Executes Claude Code in isolated Docker containers"""

    def __init__(
        self,
        image_name: str = "nightshift-claude-executor:latest",
        working_dir: Optional[str] = None,
        claude_config_dir: Optional[str] = None
    ):
        """
        Initialize Docker executor

        Args:
            image_name: Docker image to use for execution
            working_dir: Working directory to mount (defaults to cwd)
            claude_config_dir: Claude config directory (defaults to ~/.claude)
        """
        self.image_name = image_name
        self.working_dir = Path(working_dir) if working_dir else Path.cwd()
        self.claude_config_dir = Path(claude_config_dir) if claude_config_dir else Path.home() / ".claude"

    def build_docker_command(
        self,
        claude_args: List[str],
        env_vars: Optional[Dict[str, str]] = None
    ) -> List[str]:
        """
        Build docker run command for Claude Code execution

        Args:
            claude_args: Arguments to pass to Claude CLI
            env_vars: Environment variables to pass to container

        Returns:
            Complete docker run command as list
        """
        cmd = [
            "docker", "run",
            "--rm",  # Remove container after execution
            "-i",    # Interactive (for stdin if needed)
        ]

        # User mapping for file permissions
        uid = os.getuid()
        gid = os.getgid()
        cmd.extend(["-u", f"{uid}:{gid}"])

        # Volume mounts
        # Working directory (read-write)
        cmd.extend(["-v", f"{self.working_dir}:/work"])

        # Claude config (read-only for security)
        if self.claude_config_dir.exists():
            cmd.extend(["-v", f"{self.claude_config_dir}:/home/executor/.claude:ro"])

        # Set working directory
        cmd.extend(["-w", "/work"])

        # Environment variables for API keys
        if env_vars:
            for key, value in env_vars.items():
                if value:  # Only pass non-empty values
                    cmd.extend(["-e", f"{key}={value}"])
        else:
            # Pass through common API key env vars if they exist
            api_keys = [
                "ANTHROPIC_API_KEY",
                "OPENAI_API_KEY",
                "GEMINI_API_KEY",
                "GOOGLE_API_KEY",
            ]
            for key in api_keys:
                if key in os.environ:
                    cmd.extend(["-e", key])

        # Docker image
        cmd.append(self.image_name)

        # Claude arguments
        cmd.extend(claude_args)

        return cmd

    def execute(
        self,
        claude_args: List[str],
        env_vars: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess:
        """
        Execute Claude Code in Docker container

        Args:
            claude_args: Arguments to pass to Claude CLI
            env_vars: Environment variables to pass to container
            timeout: Optional timeout in seconds

        Returns:
            subprocess.CompletedProcess result
        """
        cmd = self.build_docker_command(claude_args, env_vars)

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        return result

    def check_image_exists(self) -> bool:
        """
        Check if the Docker image exists locally

        Returns:
            True if image exists, False otherwise
        """
        result = subprocess.run(
            ["docker", "image", "inspect", self.image_name],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
