"""
User Mapper
Maps platform-specific user identities to NightShift user accounts
"""
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PlatformUser:
    """Represents a user identity from a messaging platform"""
    platform: str
    platform_user_id: str
    nightshift_user_id: str
    display_name: Optional[str] = None
    email: Optional[str] = None
    created_at: Optional[str] = None
    last_seen_at: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class UserMapper:
    """
    Maps platform user identities to NightShift users
    Supports multiple platform identities per user
    """

    def __init__(self, db_path: str):
        """
        Initialize user mapper

        Args:
            db_path: Path to SQLite database for user mappings
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema for user mappings"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS platform_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    platform TEXT NOT NULL,
                    platform_user_id TEXT NOT NULL,
                    nightshift_user_id TEXT NOT NULL,
                    display_name TEXT,
                    email TEXT,
                    created_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    metadata TEXT,
                    UNIQUE(platform, platform_user_id)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_permissions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nightshift_user_id TEXT NOT NULL,
                    permission TEXT NOT NULL,
                    granted_at TEXT NOT NULL,
                    granted_by TEXT,
                    UNIQUE(nightshift_user_id, permission)
                )
            """)

            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_quotas (
                    nightshift_user_id TEXT PRIMARY KEY,
                    max_tasks_per_day INTEGER DEFAULT 10,
                    max_tokens_per_task INTEGER DEFAULT 100000,
                    max_concurrent_tasks INTEGER DEFAULT 3,
                    updated_at TEXT NOT NULL
                )
            """)

            conn.commit()

    def map_user(
        self,
        platform: str,
        platform_user_id: str,
        nightshift_user_id: Optional[str] = None,
        display_name: Optional[str] = None,
        email: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Map a platform user to a NightShift user

        Args:
            platform: Platform name (slack, whatsapp, telegram, discord)
            platform_user_id: User ID on the platform
            nightshift_user_id: NightShift user ID (auto-generated if not provided)
            display_name: User's display name
            email: User's email address
            metadata: Additional user metadata

        Returns:
            NightShift user ID
        """
        now = datetime.now().isoformat()

        # Generate user ID if not provided
        if not nightshift_user_id:
            nightshift_user_id = f"user_{platform}_{platform_user_id}"

        with sqlite3.connect(self.db_path) as conn:
            # Try to insert, or update if already exists
            conn.execute("""
                INSERT INTO platform_users (
                    platform, platform_user_id, nightshift_user_id,
                    display_name, email, created_at, last_seen_at, metadata
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(platform, platform_user_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    email = excluded.email,
                    last_seen_at = excluded.last_seen_at,
                    metadata = excluded.metadata
            """, (
                platform,
                platform_user_id,
                nightshift_user_id,
                display_name,
                email,
                now,
                now,
                str(metadata) if metadata else None
            ))
            conn.commit()

        return nightshift_user_id

    def get_nightshift_user(
        self,
        platform: str,
        platform_user_id: str
    ) -> Optional[PlatformUser]:
        """
        Get NightShift user ID for a platform user

        Args:
            platform: Platform name
            platform_user_id: User ID on the platform

        Returns:
            PlatformUser if found, None otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM platform_users
                WHERE platform = ? AND platform_user_id = ?
            """, (platform, platform_user_id))

            row = cursor.fetchone()
            if not row:
                return None

            return PlatformUser(
                platform=row['platform'],
                platform_user_id=row['platform_user_id'],
                nightshift_user_id=row['nightshift_user_id'],
                display_name=row['display_name'],
                email=row['email'],
                created_at=row['created_at'],
                last_seen_at=row['last_seen_at'],
                metadata=eval(row['metadata']) if row['metadata'] else None
            )

    def update_last_seen(self, platform: str, platform_user_id: str):
        """Update last seen timestamp for a user"""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE platform_users
                SET last_seen_at = ?
                WHERE platform = ? AND platform_user_id = ?
            """, (now, platform, platform_user_id))
            conn.commit()

    def grant_permission(
        self,
        nightshift_user_id: str,
        permission: str,
        granted_by: Optional[str] = None
    ):
        """Grant a permission to a user"""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR IGNORE INTO user_permissions
                (nightshift_user_id, permission, granted_at, granted_by)
                VALUES (?, ?, ?, ?)
            """, (nightshift_user_id, permission, now, granted_by))
            conn.commit()

    def has_permission(self, nightshift_user_id: str, permission: str) -> bool:
        """Check if a user has a permission"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT COUNT(*) FROM user_permissions
                WHERE nightshift_user_id = ? AND permission = ?
            """, (nightshift_user_id, permission))
            count = cursor.fetchone()[0]
            return count > 0

    def set_quota(
        self,
        nightshift_user_id: str,
        max_tasks_per_day: Optional[int] = None,
        max_tokens_per_task: Optional[int] = None,
        max_concurrent_tasks: Optional[int] = None
    ):
        """Set usage quotas for a user"""
        now = datetime.now().isoformat()

        # Get current quotas
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM user_quotas WHERE nightshift_user_id = ?
            """, (nightshift_user_id,))
            current = cursor.fetchone()

            # Merge with provided values
            if current:
                if max_tasks_per_day is None:
                    max_tasks_per_day = current['max_tasks_per_day']
                if max_tokens_per_task is None:
                    max_tokens_per_task = current['max_tokens_per_task']
                if max_concurrent_tasks is None:
                    max_concurrent_tasks = current['max_concurrent_tasks']
            else:
                # Defaults
                if max_tasks_per_day is None:
                    max_tasks_per_day = 10
                if max_tokens_per_task is None:
                    max_tokens_per_task = 100000
                if max_concurrent_tasks is None:
                    max_concurrent_tasks = 3

            # Insert or update
            conn.execute("""
                INSERT INTO user_quotas (
                    nightshift_user_id, max_tasks_per_day, max_tokens_per_task,
                    max_concurrent_tasks, updated_at
                )
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(nightshift_user_id) DO UPDATE SET
                    max_tasks_per_day = excluded.max_tasks_per_day,
                    max_tokens_per_task = excluded.max_tokens_per_task,
                    max_concurrent_tasks = excluded.max_concurrent_tasks,
                    updated_at = excluded.updated_at
            """, (
                nightshift_user_id,
                max_tasks_per_day,
                max_tokens_per_task,
                max_concurrent_tasks,
                now
            ))
            conn.commit()

    def get_quota(self, nightshift_user_id: str) -> Optional[Dict[str, int]]:
        """Get usage quotas for a user"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM user_quotas WHERE nightshift_user_id = ?
            """, (nightshift_user_id,))
            row = cursor.fetchone()

            if not row:
                return None

            return {
                'max_tasks_per_day': row['max_tasks_per_day'],
                'max_tokens_per_task': row['max_tokens_per_task'],
                'max_concurrent_tasks': row['max_concurrent_tasks']
            }

    def list_platform_users(self, nightshift_user_id: str) -> List[PlatformUser]:
        """List all platform identities for a NightShift user"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM platform_users WHERE nightshift_user_id = ?
            """, (nightshift_user_id,))

            users = []
            for row in cursor.fetchall():
                users.append(PlatformUser(
                    platform=row['platform'],
                    platform_user_id=row['platform_user_id'],
                    nightshift_user_id=row['nightshift_user_id'],
                    display_name=row['display_name'],
                    email=row['email'],
                    created_at=row['created_at'],
                    last_seen_at=row['last_seen_at'],
                    metadata=eval(row['metadata']) if row['metadata'] else None
                ))

            return users
