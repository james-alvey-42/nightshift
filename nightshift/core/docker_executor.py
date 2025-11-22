"""
Docker Executor - Runs Claude Code in isolated containers
Wraps Claude CLI execution in Docker for security and isolation
"""
import os
import json
import shutil
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

from .mcp_discovery import discover_mcp_mount_paths


class DockerExecutor:
    """Executes Claude Code in isolated Docker containers"""

    @staticmethod
    def _ensure_absolute_mcp_paths(config_path: Path) -> None:
        """
        Rewrite MCP server commands to use absolute paths

        This ensures MCP servers can be spawned inside containers where
        PATH resolution may differ from the host environment.

        Args:
            config_path: Path to .claude.json config file
        """
        if not config_path.exists():
            return

        try:
            with open(config_path, 'r') as f:
                config = json.load(f)

            servers = config.get("mcpServers", {})
            modified = False

            for name, server_config in servers.items():
                cmd = server_config.get("command")
                if not cmd or "/" in cmd:
                    # Already absolute or empty
                    continue

                # Resolve command to absolute path
                abs_path = shutil.which(cmd)
                if abs_path:
                    server_config["command"] = abs_path
                    modified = True

            # Write back if we made changes
            if modified:
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)

        except (json.JSONDecodeError, IOError) as e:
            # Don't fail if config is malformed, just skip normalization
            import sys
            print(f"Warning: Could not normalize MCP paths in {config_path}: {e}", file=sys.stderr)

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

        # Ensure MCP commands use absolute paths for container compatibility
        claude_json = Path.home() / ".claude.json"
        self._ensure_absolute_mcp_paths(claude_json)

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
        ]

        # User mapping for file permissions
        uid = os.getuid()
        gid = os.getgid()
        cmd.extend(["-u", f"{uid}:{gid}"])

        # Volume mounts
        # Auto-discover and mount MCP server paths (read-only)
        # This mounts venvs, npm globals, etc. at the same paths to preserve shebangs
        try:
            mcp_mounts = discover_mcp_mount_paths()
            for mount_path in sorted(mcp_mounts):
                cmd.extend(["-v", f"{mount_path}:{mount_path}:ro"])
        except Exception as e:
            # If discovery fails, log but continue (MCP tools won't work but container will run)
            import sys
            print(f"Warning: MCP discovery failed: {e}", file=sys.stderr)

        # Mount Claude config as read-write (needs to write debug logs)
        # This overrides the read-only mount if .claude is inside a discovered path
        if self.claude_config_dir.exists():
            cmd.extend(["-v", f"{self.claude_config_dir}:{self.claude_config_dir}"])

        # Mount .claude.json config file (contains MCP server configurations)
        # Must be read-write so Claude can update MCP server state
        claude_json = Path.home() / ".claude.json"
        if claude_json.exists():
            cmd.extend(["-v", f"{claude_json}:{claude_json}"])

        # Mount working directory as read-write (for task outputs)
        # This is where Claude creates files that the user can retrieve
        cmd.extend(["-v", f"{self.working_dir}:/work"])

        # Set working directory
        cmd.extend(["-w", "/work"])

        # Set HOME to match where we mounted .claude config
        home_dir = str(Path.home())
        cmd.extend(["-e", f"HOME={home_dir}"])

        # Set PATH to include venv binaries for MCP servers
        venv_bin = f"{Path.home()}/.claude_venv/bin"
        cmd.extend(["-e", f"PATH={venv_bin}:/usr/local/bin:/usr/bin:/bin"])

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
