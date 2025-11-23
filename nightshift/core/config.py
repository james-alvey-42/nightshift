"""
Configuration management for NightShift
Handles paths and settings
"""
from pathlib import Path
import os


class Config:
    """NightShift configuration"""

    def __init__(self, base_dir: str = None):
        """
        Initialize configuration

        Args:
            base_dir: Base directory for NightShift data.
                     Defaults to ~/.nightshift
        """
        if base_dir is None:
            base_dir = Path.home() / ".nightshift"
        else:
            base_dir = Path(base_dir)

        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        self.database_dir = self.base_dir / "database"
        self.database_dir.mkdir(exist_ok=True)

        self.logs_dir = self.base_dir / "logs"
        self.logs_dir.mkdir(exist_ok=True)

        self.output_dir = self.base_dir / "output"
        self.output_dir.mkdir(exist_ok=True)

        self.notifications_dir = self.base_dir / "notifications"
        self.notifications_dir.mkdir(exist_ok=True)

        # Database path
        self.db_path = self.database_dir / "nightshift.db"

        # Package config directory (for tools reference, etc.)
        package_dir = Path(__file__).parent.parent
        self.config_dir = package_dir / "config"

        self.tools_reference_path = self.config_dir / "claude-code-tools-reference.md"

        # Docker execution settings
        self.use_docker = os.environ.get("NIGHTSHIFT_USE_DOCKER", "false").lower() == "true"
        self.docker_image = os.environ.get("NIGHTSHIFT_DOCKER_IMAGE", "nightshift-claude-executor:latest")

    def get_log_dir(self) -> Path:
        """Get logs directory"""
        return self.logs_dir

    def get_database_path(self) -> Path:
        """Get database file path"""
        return self.db_path

    def get_output_dir(self) -> Path:
        """Get output directory"""
        return self.output_dir

    def get_notifications_dir(self) -> Path:
        """Get notifications directory"""
        return self.notifications_dir

    def get_tools_reference_path(self) -> Path:
        """Get tools reference file path"""
        return self.tools_reference_path
