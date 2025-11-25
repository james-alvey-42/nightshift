"""
Slack Metadata Store
Tracks Slack context (user, channel, thread) for each task
"""
import json
from pathlib import Path
from typing import Dict, Optional


class SlackMetadataStore:
    """
    Store and retrieve Slack metadata for tasks
    Maps task_id -> {user_id, channel_id, thread_ts, response_url}
    """

    def __init__(self, metadata_dir: Path):
        """
        Initialize metadata store

        Args:
            metadata_dir: Directory to store metadata JSON files
        """
        self.metadata_dir = Path(metadata_dir)
        self.metadata_dir.mkdir(parents=True, exist_ok=True)

    def store(
        self,
        task_id: str,
        user_id: str,
        channel_id: str,
        thread_ts: Optional[str] = None,
        response_url: Optional[str] = None
    ):
        """
        Store Slack metadata for a task

        Args:
            task_id: NightShift task ID
            user_id: Slack user ID who submitted the task
            channel_id: Slack channel ID where task was submitted
            thread_ts: Thread timestamp (if threaded conversation)
            response_url: Slack response URL for delayed responses
        """
        metadata = {
            "task_id": task_id,
            "user_id": user_id,
            "channel_id": channel_id,
            "thread_ts": thread_ts,
            "response_url": response_url
        }

        metadata_path = self.metadata_dir / f"{task_id}.json"
        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

    def get(self, task_id: str) -> Optional[Dict]:
        """
        Retrieve Slack metadata for a task

        Args:
            task_id: NightShift task ID

        Returns:
            Metadata dictionary or None if not found
        """
        metadata_path = self.metadata_dir / f"{task_id}.json"
        if not metadata_path.exists():
            return None

        try:
            with open(metadata_path, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def update(self, task_id: str, updates: Dict):
        """
        Update specific fields in metadata

        Args:
            task_id: NightShift task ID
            updates: Dictionary of fields to update
        """
        metadata = self.get(task_id)
        if not metadata:
            return

        metadata.update(updates)
        self.store(
            task_id=task_id,
            user_id=metadata['user_id'],
            channel_id=metadata['channel_id'],
            thread_ts=metadata.get('thread_ts'),
            response_url=metadata.get('response_url')
        )

    def delete(self, task_id: str):
        """
        Delete metadata for a task

        Args:
            task_id: NightShift task ID
        """
        metadata_path = self.metadata_dir / f"{task_id}.json"
        if metadata_path.exists():
            metadata_path.unlink()

    def exists(self, task_id: str) -> bool:
        """
        Check if metadata exists for a task

        Args:
            task_id: NightShift task ID

        Returns:
            True if metadata exists
        """
        return (self.metadata_dir / f"{task_id}.json").exists()
