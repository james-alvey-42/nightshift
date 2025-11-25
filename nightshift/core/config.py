"""
Configuration management for NightShift
Handles paths and settings
"""
from pathlib import Path
import os
import yaml
from typing import Dict, Any, Optional


class Config:
    """NightShift configuration"""

    def __init__(self, base_dir: str = None, config_file: str = None):
        """
        Initialize configuration

        Args:
            base_dir: Base directory for NightShift data.
                     Defaults to ~/.nightshift
            config_file: Path to YAML configuration file.
                        Defaults to ~/.nightshift/config.yaml
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

        # User database path (for remote features)
        self.user_db_path = self.database_dir / "users.db"

        # Package config directory (for tools reference, etc.)
        package_dir = Path(__file__).parent.parent
        self.config_dir = package_dir / "config"

        self.tools_reference_path = self.config_dir / "claude-code-tools-reference.md"

        # Load YAML configuration if exists
        if config_file is None:
            config_file = self.base_dir / "config.yaml"
        else:
            config_file = Path(config_file)

        self.config_file = config_file
        self.remote_config = self._load_remote_config()

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

    def get_user_db_path(self) -> Path:
        """Get user database path"""
        return self.user_db_path

    def _load_remote_config(self) -> Dict[str, Any]:
        """
        Load remote configuration from YAML file

        Returns default configuration if file doesn't exist
        """
        if not self.config_file.exists():
            return self._get_default_remote_config()

        try:
            with open(self.config_file, 'r') as f:
                config = yaml.safe_load(f) or {}
                return config.get('remote', self._get_default_remote_config())
        except Exception as e:
            print(f"Warning: Failed to load config file: {e}")
            return self._get_default_remote_config()

    def _get_default_remote_config(self) -> Dict[str, Any]:
        """Get default remote configuration"""
        return {
            'enabled': False,
            'trigger_service': {
                'platforms': {
                    'slack': {
                        'enabled': False,
                        'bot_token': os.environ.get('SLACK_BOT_TOKEN', ''),
                        'signing_secret': os.environ.get('SLACK_SIGNING_SECRET', '')
                    },
                    'whatsapp': {
                        'enabled': False
                    },
                    'telegram': {
                        'enabled': False
                    },
                    'discord': {
                        'enabled': False
                    }
                },
                'webhook_url': os.environ.get('NIGHTSHIFT_WEBHOOK_URL', '')
            },
            'execution': {
                'mode': 'local',  # local, docker, cloud
                'cloud_provider': 'gcp',  # gcp, aws, azure
                'gcp': {
                    'project': os.environ.get('GCP_PROJECT', ''),
                    'region': os.environ.get('GCP_REGION', 'us-central1'),
                    'service_account': os.environ.get('GCP_SERVICE_ACCOUNT', ''),
                    'image': os.environ.get('GCP_NIGHTSHIFT_IMAGE', ''),
                    'storage_bucket': os.environ.get('GCP_STORAGE_BUCKET', '')
                },
                'aws': {
                    'function_name': os.environ.get('AWS_LAMBDA_FUNCTION', ''),
                    'region': os.environ.get('AWS_REGION', 'us-east-1'),
                    'storage_bucket': os.environ.get('AWS_S3_BUCKET', '')
                },
                'azure': {
                    'function_app': os.environ.get('AZURE_FUNCTION_APP', ''),
                    'region': os.environ.get('AZURE_REGION', 'eastus'),
                    'storage_account': os.environ.get('AZURE_STORAGE_ACCOUNT', '')
                }
            },
            'storage': {
                'database': 'sqlite',  # sqlite, cloud_sql, rds, azure_db
                'results_bucket': os.environ.get('RESULTS_BUCKET', '')
            },
            'auth': {
                'method': 'api_key',  # api_key, oauth2, jwt
                'api_keys': {},  # API key -> user ID mapping
                'platform_secrets': {
                    'slack': os.environ.get('SLACK_SIGNING_SECRET', ''),
                    'whatsapp': os.environ.get('WHATSAPP_SECRET', ''),
                    'telegram': os.environ.get('TELEGRAM_BOT_TOKEN', ''),
                    'discord': os.environ.get('DISCORD_PUBLIC_KEY', '')
                },
                'allowed_users': []
            }
        }

    def get_remote_config(self) -> Dict[str, Any]:
        """Get remote configuration"""
        return self.remote_config

    def is_remote_enabled(self) -> bool:
        """Check if remote trigger service is enabled"""
        return self.remote_config.get('enabled', False)

    def save_config(self, config: Dict[str, Any]):
        """
        Save configuration to YAML file

        Args:
            config: Full configuration dictionary
        """
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
