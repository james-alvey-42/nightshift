"""
Tests for SlackMetadataStore
"""
import pytest
import json
from pathlib import Path

from nightshift.integrations.slack_metadata import SlackMetadataStore


class TestSlackMetadataStoreInit:
    """Tests for SlackMetadataStore initialization"""

    def test_creates_directory(self, tmp_path):
        """__init__ creates metadata directory if it doesn't exist"""
        metadata_dir = tmp_path / "slack_metadata"
        assert not metadata_dir.exists()

        store = SlackMetadataStore(metadata_dir)

        assert metadata_dir.exists()
        assert metadata_dir.is_dir()

    def test_uses_existing_directory(self, tmp_path):
        """__init__ uses existing directory"""
        metadata_dir = tmp_path / "slack_metadata"
        metadata_dir.mkdir()
        existing_file = metadata_dir / "existing.json"
        existing_file.write_text("{}")

        store = SlackMetadataStore(metadata_dir)

        assert existing_file.exists()


class TestSlackMetadataStoreStore:
    """Tests for store method"""

    def test_store_basic_metadata(self, tmp_path):
        """store writes metadata to JSON file"""
        store = SlackMetadataStore(tmp_path)

        store.store(
            task_id="task_001",
            user_id="U123456",
            channel_id="C789012"
        )

        metadata_file = tmp_path / "task_001.json"
        assert metadata_file.exists()

        with open(metadata_file) as f:
            data = json.load(f)

        assert data["task_id"] == "task_001"
        assert data["user_id"] == "U123456"
        assert data["channel_id"] == "C789012"

    def test_store_with_thread_ts(self, tmp_path):
        """store saves thread_ts"""
        store = SlackMetadataStore(tmp_path)

        store.store(
            task_id="task_001",
            user_id="U123456",
            channel_id="C789012",
            thread_ts="1234567890.123456"
        )

        with open(tmp_path / "task_001.json") as f:
            data = json.load(f)

        assert data["thread_ts"] == "1234567890.123456"

    def test_store_with_response_url(self, tmp_path):
        """store saves response_url"""
        store = SlackMetadataStore(tmp_path)

        store.store(
            task_id="task_001",
            user_id="U123456",
            channel_id="C789012",
            response_url="https://hooks.slack.com/response/xxx"
        )

        with open(tmp_path / "task_001.json") as f:
            data = json.load(f)

        assert data["response_url"] == "https://hooks.slack.com/response/xxx"

    def test_store_overwrites_existing(self, tmp_path):
        """store overwrites existing metadata"""
        store = SlackMetadataStore(tmp_path)

        store.store(task_id="task_001", user_id="U111", channel_id="C111")
        store.store(task_id="task_001", user_id="U222", channel_id="C222")

        with open(tmp_path / "task_001.json") as f:
            data = json.load(f)

        assert data["user_id"] == "U222"
        assert data["channel_id"] == "C222"


class TestSlackMetadataStoreGet:
    """Tests for get method"""

    def test_get_existing_metadata(self, tmp_path):
        """get returns metadata for existing task"""
        store = SlackMetadataStore(tmp_path)
        store.store(task_id="task_001", user_id="U123", channel_id="C456")

        metadata = store.get("task_001")

        assert metadata is not None
        assert metadata["task_id"] == "task_001"
        assert metadata["user_id"] == "U123"

    def test_get_nonexistent_task(self, tmp_path):
        """get returns None for nonexistent task"""
        store = SlackMetadataStore(tmp_path)

        metadata = store.get("nonexistent")

        assert metadata is None

    def test_get_handles_corrupted_json(self, tmp_path):
        """get returns None for corrupted JSON file"""
        store = SlackMetadataStore(tmp_path)

        # Create corrupted JSON file
        corrupted_file = tmp_path / "corrupted.json"
        corrupted_file.write_text("not valid json {{{")

        metadata = store.get("corrupted")

        assert metadata is None


class TestSlackMetadataStoreUpdate:
    """Tests for update method"""

    def test_update_existing_field(self, tmp_path):
        """update modifies existing field"""
        store = SlackMetadataStore(tmp_path)
        store.store(task_id="task_001", user_id="U123", channel_id="C456")

        store.update("task_001", {"thread_ts": "1234.5678"})

        metadata = store.get("task_001")
        assert metadata["thread_ts"] == "1234.5678"
        # Original fields preserved
        assert metadata["user_id"] == "U123"

    def test_update_nonexistent_task(self, tmp_path):
        """update does nothing for nonexistent task"""
        store = SlackMetadataStore(tmp_path)

        store.update("nonexistent", {"thread_ts": "1234"})

        assert store.get("nonexistent") is None


class TestSlackMetadataStoreDelete:
    """Tests for delete method"""

    def test_delete_existing_metadata(self, tmp_path):
        """delete removes metadata file"""
        store = SlackMetadataStore(tmp_path)
        store.store(task_id="task_001", user_id="U123", channel_id="C456")

        assert store.exists("task_001")

        store.delete("task_001")

        assert not store.exists("task_001")
        assert not (tmp_path / "task_001.json").exists()

    def test_delete_nonexistent_task(self, tmp_path):
        """delete does nothing for nonexistent task"""
        store = SlackMetadataStore(tmp_path)

        # Should not raise
        store.delete("nonexistent")


class TestSlackMetadataStoreExists:
    """Tests for exists method"""

    def test_exists_returns_true_for_existing(self, tmp_path):
        """exists returns True when metadata exists"""
        store = SlackMetadataStore(tmp_path)
        store.store(task_id="task_001", user_id="U123", channel_id="C456")

        assert store.exists("task_001") is True

    def test_exists_returns_false_for_nonexistent(self, tmp_path):
        """exists returns False when metadata doesn't exist"""
        store = SlackMetadataStore(tmp_path)

        assert store.exists("nonexistent") is False
