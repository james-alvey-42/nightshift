"""
Sandbox Manager - Generates macOS sandbox profiles for isolated execution
Uses sandbox-exec to enforce filesystem write restrictions
"""

import os
import tempfile
from pathlib import Path
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


class SandboxManager:
    """Manages macOS sandbox-exec profile generation and execution"""

    def __init__(self):
        self._temp_profiles = []

    def create_profile(
        self,
        allowed_directories: List[str],
        profile_name: Optional[str] = None,
        needs_git: bool = False
    ) -> str:
        """
        Generate a sandbox profile that allows writes only to specified directories

        Args:
            allowed_directories: List of directory paths where writes are allowed
            profile_name: Optional name for the profile (for logging)
            needs_git: If True, allows access to /dev/null and /dev/tty (needed for git)

        Returns:
            Path to the generated .sb profile file

        The profile:
        - Allows all operations by default (read, exec, network, IPC)
        - Denies ALL filesystem writes
        - Re-allows writes only to specified directories
        - Always allows writes to /tmp and /private/tmp for temp files
        - Optionally allows device files (/dev/null, /dev/tty) if needs_git is True
        - Optionally allows ~/.config/gh/ for gh CLI token management if needs_git is True
        - Optionally allows macOS Keychain access for gh CLI authentication if needs_git is True
        """
        # Resolve all paths to absolute
        resolved_dirs = []
        for dir_path in allowed_directories:
            path = Path(dir_path).resolve()
            if not path.exists():
                logger.warning(f"Allowed directory does not exist: {path}")
            resolved_dirs.append(str(path))

        # Always allow temp directories and Claude's config/debug directories
        temp_dirs = [
            "/tmp",
            "/private/tmp",
            "/private/var/tmp",
            str(Path(tempfile.gettempdir()).resolve()),
            str(Path.home() / ".claude")  # Claude CLI needs to write debug logs
        ]

        # Specific files that need write access (not directories)
        # These are typically credentials/config files that tools need to update
        allowed_files = [
            str(Path.home() / ".claude.json"),  # Claude CLI config file
            str(Path.home() / ".google_calendar_credentials.json"),  # Google Calendar credentials
            str(Path.home() / ".google_calendar_token.json"),  # Google Calendar OAuth token
        ]

        # Add gh and git config directories if git operations are needed
        if needs_git:
            gh_config_dir = str(Path.home() / ".config" / "gh")
            if Path(gh_config_dir).exists():
                temp_dirs.append(gh_config_dir)  # gh CLI needs to write tokens/cache

            git_config_file = str(Path.home() / ".gitconfig")
            if Path(git_config_file).exists():
                allowed_files.append(git_config_file)  # git may need to update config

        # Combine and deduplicate
        all_allowed_dirs = list(set(resolved_dirs + temp_dirs))

        # Generate profile content
        # macOS sandbox: Start with (deny default) then allow specific operations
        profile_lines = [
            "(version 1)",
            "",
            ";; Deny everything by default",
            "(deny default)",
            "",
            ";; Allow process execution and basic operations",
            "(allow process*)",
            "",
            ";; Allow reading all files",
            "(allow file-read*)",
            "",
            ";; Allow mach and sysctl operations",
            "(allow mach-lookup)",
            "(allow sysctl*)",
            "(allow system-socket)",
            "(allow ipc-posix-shm)",
            "(allow mach*)",
            "",
            ";; Allow network access",
            "(allow network*)",
            "(allow network-outbound (remote tcp))",
            "",
            ";; Allow writes to specific files",
        ]

        for file_path in sorted(allowed_files):
            profile_lines.append(f'(allow file-write* (literal "{file_path}"))')

        # Add device file access and network services if needed for git/gh
        if needs_git:
            profile_lines.append("")
            profile_lines.append(";; Allow device files needed for git/gh operations")
            profile_lines.append('(allow file-write* (literal "/dev/null"))')
            profile_lines.append('(allow file-write* (literal "/dev/stdout"))')
            profile_lines.append('(allow file-write* (literal "/dev/stderr"))')
            profile_lines.append('(allow file-write* (literal "/dev/dtracehelper"))')
            profile_lines.append("")
            profile_lines.append(";; Allow network services for gh CLI (HTTPS/SSH)")
            profile_lines.append('(allow mach-lookup (global-name "com.apple.SecurityServer"))')
            profile_lines.append('(allow mach-lookup (global-name "com.apple.dnssd.service"))')
            profile_lines.append('(allow mach-lookup (global-name "com.apple.trustd"))')
            profile_lines.append('(allow mach-lookup (global-name "com.apple.nsurlsessiond"))')
            profile_lines.append('(allow ipc-posix-shm-read* (ipc-posix-name "apple.shm.notification_center"))')

        profile_lines.append("")
        profile_lines.append(";; Allow writes to specified directories")

        for allowed_path in sorted(all_allowed_dirs):
            profile_lines.append(f'(allow file-write* (subpath "{allowed_path}"))')

        profile_content = "\n".join(profile_lines)

        # Write to temporary file
        fd, profile_path = tempfile.mkstemp(
            suffix=".sb",
            prefix="nightshift_sandbox_",
            text=True
        )

        with os.fdopen(fd, "w") as f:
            f.write(profile_content)

        self._temp_profiles.append(profile_path)

        logger.info(f"Created sandbox profile: {profile_path}")
        logger.debug(f"Allowed directories: {', '.join(resolved_dirs)}")

        return profile_path

    def wrap_command(
        self,
        command: str,
        allowed_directories: List[str],
        profile_name: Optional[str] = None,
        needs_git: bool = False
    ) -> str:
        """
        Wrap a command with sandbox-exec

        Args:
            command: The command to execute
            allowed_directories: List of directories where writes are allowed
            profile_name: Optional name for the profile
            needs_git: If True, allows access to device files needed for git

        Returns:
            The wrapped command string with sandbox-exec
        """
        profile_path = self.create_profile(allowed_directories, profile_name, needs_git)

        # Build sandbox-exec command
        wrapped = f'sandbox-exec -f "{profile_path}" {command}'

        logger.info(f"🔒 Sandbox profile: {profile_path}")
        logger.debug(f"Wrapped command: {wrapped}")

        return wrapped

    def cleanup(self):
        """Remove all temporary profile files"""
        for profile_path in self._temp_profiles:
            try:
                os.unlink(profile_path)
                logger.debug(f"Cleaned up profile: {profile_path}")
            except Exception as e:
                logger.warning(f"Failed to cleanup profile {profile_path}: {e}")

        self._temp_profiles.clear()

    def __del__(self):
        """Cleanup profiles on deletion"""
        self.cleanup()

    @staticmethod
    def is_available() -> bool:
        """Check if sandbox-exec is available on this system"""
        import shutil
        return shutil.which("sandbox-exec") is not None

    @staticmethod
    def validate_directories(directories: List[str]) -> List[str]:
        """
        Validate that directories are safe to use in sandbox

        Args:
            directories: List of directory paths

        Returns:
            List of validated directory paths

        Raises:
            ValueError: If any directory is unsafe
        """
        validated = []

        # Dangerous paths - include both direct and macOS /private/* variants
        dangerous_paths = [
            "/", "/private",
            "/etc", "/private/etc",
            "/var", "/private/var",
            "/bin", "/usr", "/sbin",
            "/System", "/Library",
            "/Applications", "/Volumes"
        ]

        for dir_path in directories:
            path = Path(dir_path).resolve()
            path_str = str(path)

            # Check for dangerous paths (exact match or child of dangerous path)
            for dangerous in dangerous_paths:
                if path_str == dangerous or path_str.startswith(dangerous + "/"):
                    raise ValueError(
                        f"Refusing to allow writes to system directory: {path_str}"
                    )

            # Warn about home directory
            if path == Path.home():
                logger.warning(
                    f"Allowing writes to entire home directory: {path_str}. "
                    "Consider using a more specific subdirectory."
                )

            validated.append(path_str)

        return validated
