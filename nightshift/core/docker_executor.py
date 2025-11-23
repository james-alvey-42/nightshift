"""
Docker Executor - Runs Claude Code in isolated containers
Wraps Claude CLI execution in Docker for security and isolation
"""
import os
import json
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional

from .mcp_discovery import discover_mcp_mount_paths

logger = logging.getLogger(__name__)


class DockerExecutor:
    """Executes Claude Code in isolated Docker containers"""

    @staticmethod
    def _create_container_config(source_config_path: Path) -> Path:
        """
        Create a temporary .claude.json with absolute MCP paths for container use

        This ensures MCP servers can be spawned inside containers where
        PATH resolution may differ from the host environment.
        Does not modify the user's original config file.

        Args:
            source_config_path: Path to user's .claude.json config file

        Returns:
            Path to temporary config file with normalized paths
        """
        if not source_config_path.exists():
            # Return path to non-existent file; Docker mount will handle gracefully
            return source_config_path

        try:
            with open(source_config_path, 'r') as f:
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

            # Only create temp file if we made changes
            if modified:
                # Create temp file in same directory as original for same filesystem
                temp_fd, temp_path = tempfile.mkstemp(
                    suffix='.json',
                    prefix='.claude.nightshift.',
                    dir=source_config_path.parent
                )

                with os.fdopen(temp_fd, 'w') as f:
                    json.dump(config, f, indent=2)

                return Path(temp_path)
            else:
                # No changes needed, use original
                return source_config_path

        except (json.JSONDecodeError, IOError) as e:
            # Don't fail if config is malformed, just use original
            logger.warning(f"Could not normalize MCP paths in {source_config_path}: {e}")
            return source_config_path

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
        self._temp_config_path = None  # Track temp config for cleanup

    @staticmethod
    def _validate_mount_path(path: Path, mode: str = "ro") -> None:
        """
        Validate that a mount path is safe to expose to the container

        Args:
            path: Path to validate
            mode: Mount mode ('ro' or 'rw')

        Raises:
            ValueError: If path is unsafe to mount
        """
        path_str = str(path.resolve())

        # Dangerous paths that should never be mounted
        dangerous_paths = [
            "/",
            "/etc",
            "/var",
            "/root",
            "/boot",
            "/dev",
            "/proc",
            "/sys",
        ]

        for dangerous in dangerous_paths:
            if path_str == dangerous or path_str.startswith(dangerous + "/"):
                raise ValueError(f"Refusing to mount dangerous path: {path_str}")

        # Warn about mounting $HOME (but allow it)
        home = str(Path.home())
        if path_str == home and mode == "rw":
            logger.warning(f"Mounting entire home directory read-write: {path_str}")

        # Path must exist
        if not path.exists():
            raise ValueError(f"Mount path does not exist: {path_str}")

    def build_docker_command(
        self,
        claude_args: List[str],
        env_vars: Optional[Dict[str, str]] = None,
        additional_mounts: Optional[List[Dict[str, str]]] = None
    ) -> List[str]:
        """
        Build docker run command for Claude Code execution

        Args:
            claude_args: Arguments to pass to Claude CLI
            env_vars: Environment variables to pass to container
            additional_mounts: Optional list of additional paths to mount
                Each dict should have:
                    - 'host_path': Path on host system
                    - 'container_path': Path in container (optional, defaults to host_path)
                    - 'mode': 'ro' or 'rw' (optional, defaults to 'ro')

        Returns:
            Complete docker run command as list
        """
        cmd = [
            "docker", "run",
            "--rm",  # Remove container after execution
            "--read-only",  # Make container root filesystem read-only
        ]

        # Temporary writable directories
        cmd.extend(["--tmpfs", "/tmp"])

        # User mapping for file permissions
        uid = os.getuid()
        gid = os.getgid()
        cmd.extend(["-u", f"{uid}:{gid}"])

        # Volume mounts
        # Mount system directories for interpreters (Python, Node, etc.)
        # MCP server venvs have symlinks pointing to system interpreters
        # Note: We don't mount /usr because Claude CLI is installed there in the container
        # and mounting host's /usr would overwrite it
        system_dirs = ["/lib", "/lib64", "/opt"]
        for sys_dir in system_dirs:
            sys_path = Path(sys_dir)
            if sys_path.exists():
                cmd.extend(["-v", f"{sys_dir}:{sys_dir}:ro"])

        # Auto-discover and mount MCP server paths (read-only)
        # This mounts venvs, npm globals, etc. at the same paths to preserve shebangs
        try:
            mcp_mounts = discover_mcp_mount_paths()
            if mcp_mounts:
                logger.debug(f"Mounting {len(mcp_mounts)} MCP server paths")
                for mount_path in sorted(mcp_mounts):
                    cmd.extend(["-v", f"{mount_path}:{mount_path}:ro"])
        except Exception as e:
            # If discovery fails, log but continue (MCP tools won't work but container will run)
            logger.error(f"MCP discovery failed: {e}", exc_info=True)

        # Mount Claude config as read-write (needs to write debug logs)
        # This overrides the read-only mount if .claude is inside a discovered path
        if self.claude_config_dir.exists():
            cmd.extend(["-v", f"{self.claude_config_dir}:{self.claude_config_dir}"])

        # Create temporary .claude.json with normalized MCP paths for container
        # This avoids mutating the user's original config file
        source_config = Path.home() / ".claude.json"
        container_config = self._create_container_config(source_config)
        self._temp_config_path = container_config if container_config != source_config else None

        # Mount the container config (may be temp or original)
        # Must be read-write so Claude can update MCP server state
        if container_config.exists():
            # Mount at the original path inside container
            cmd.extend(["-v", f"{container_config}:{source_config}"])

        # Mount working directory as read-write (for task outputs)
        # This is where Claude creates files that the user can retrieve
        cmd.extend(["-v", f"{self.working_dir}:/work"])

        # Mount additional user-specified directories
        if additional_mounts:
            for mount in additional_mounts:
                host_path = Path(mount["host_path"])
                container_path = mount.get("container_path", str(host_path))
                mode = mount.get("mode", "ro")

                # Validate mount path
                try:
                    self._validate_mount_path(host_path, mode)
                except ValueError as e:
                    logger.error(f"Skipping invalid mount: {e}")
                    continue

                # Add mount
                mount_spec = f"{host_path}:{container_path}"
                if mode:
                    mount_spec += f":{mode}"
                cmd.extend(["-v", mount_spec])
                logger.info(f"Mounting additional path: {host_path} -> {container_path} ({mode})")

        # Set working directory
        cmd.extend(["-w", "/work"])

        # Set HOME to match where we mounted .claude config
        home_dir = str(Path.home())
        cmd.extend(["-e", f"HOME={home_dir}"])

        # Set PATH to include venv binaries for MCP servers (if exists)
        venv_bin = Path.home() / ".claude_venv" / "bin"
        if venv_bin.exists():
            path_str = f"{venv_bin}:/usr/local/bin:/usr/bin:/bin"
        else:
            path_str = "/usr/local/bin:/usr/bin:/bin"
        cmd.extend(["-e", f"PATH={path_str}"])

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
        timeout: Optional[int] = None,
        additional_mounts: Optional[List[Dict[str, str]]] = None
    ) -> subprocess.CompletedProcess:
        """
        Execute Claude Code in Docker container

        Args:
            claude_args: Arguments to pass to Claude CLI
            env_vars: Environment variables to pass to container
            timeout: Optional timeout in seconds
            additional_mounts: Optional list of additional paths to mount
                Each dict should have:
                    - 'host_path': Path on host system
                    - 'container_path': Path in container (optional, defaults to host_path)
                    - 'mode': 'ro' or 'rw' (optional, defaults to 'ro')

        Returns:
            subprocess.CompletedProcess result
        """
        cmd = self.build_docker_command(claude_args, env_vars, additional_mounts)
        return self.run_prepared_command(cmd, timeout=timeout)

    def run_prepared_command(
        self,
        cmd: List[str],
        timeout: Optional[int] = None
    ) -> subprocess.CompletedProcess:
        """
        Execute a previously built docker command and handle cleanup.
        """
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result
        finally:
            # Clean up temporary config file
            self._cleanup_temp_config()

    def _cleanup_temp_config(self) -> None:
        """Remove temporary config file if one was created"""
        if self._temp_config_path and self._temp_config_path.exists():
            try:
                self._temp_config_path.unlink()
                self._temp_config_path = None
            except OSError:
                # If cleanup fails, it's not critical
                pass

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
