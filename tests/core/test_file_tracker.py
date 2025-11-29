"""
Tests for FileTracker - file system change detection
"""
import pytest
import json
import time
from pathlib import Path

from nightshift.core.file_tracker import FileTracker, FileChange


class TestSnapshots:
    """Tests for snapshot creation and comparison"""

    def test_take_snapshot_empty_dir(self, tmp_path):
        """Snapshot of empty directory returns empty dict"""
        tracker = FileTracker(watch_dir=str(tmp_path))
        snapshot = tracker.take_snapshot()

        assert snapshot == {}

    def test_take_snapshot_with_files(self, tmp_path):
        """Snapshot captures visible files with mtimes"""
        # Create some files
        (tmp_path / "file1.txt").write_text("content1")
        (tmp_path / "file2.txt").write_text("content2")

        tracker = FileTracker(watch_dir=str(tmp_path))
        snapshot = tracker.take_snapshot()

        assert "file1.txt" in snapshot
        assert "file2.txt" in snapshot
        assert isinstance(snapshot["file1.txt"], float)

    def test_take_snapshot_ignores_hidden_files(self, tmp_path):
        """Snapshot ignores files starting with dot"""
        (tmp_path / ".hidden").write_text("hidden")
        (tmp_path / "visible.txt").write_text("visible")

        tracker = FileTracker(watch_dir=str(tmp_path))
        snapshot = tracker.take_snapshot()

        assert ".hidden" not in snapshot
        assert "visible.txt" in snapshot

    def test_take_snapshot_ignores_hidden_dirs(self, tmp_path):
        """Snapshot ignores directories starting with dot"""
        hidden_dir = tmp_path / ".git"
        hidden_dir.mkdir()
        (hidden_dir / "config").write_text("git config")

        visible_dir = tmp_path / "src"
        visible_dir.mkdir()
        (visible_dir / "main.py").write_text("code")

        tracker = FileTracker(watch_dir=str(tmp_path))
        snapshot = tracker.take_snapshot()

        assert ".git/config" not in snapshot
        assert "src/main.py" in snapshot

    def test_take_snapshot_ignores_node_modules(self, tmp_path):
        """Snapshot ignores node_modules directory"""
        node_dir = tmp_path / "node_modules"
        node_dir.mkdir()
        (node_dir / "package.json").write_text("{}")

        tracker = FileTracker(watch_dir=str(tmp_path))
        snapshot = tracker.take_snapshot()

        assert "node_modules/package.json" not in snapshot

    def test_take_snapshot_ignores_pycache(self, tmp_path):
        """Snapshot ignores __pycache__ directory"""
        cache_dir = tmp_path / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "module.pyc").write_text("bytecode")

        tracker = FileTracker(watch_dir=str(tmp_path))
        snapshot = tracker.take_snapshot()

        assert "__pycache__/module.pyc" not in snapshot

    def test_take_snapshot_handles_stat_errors(self, tmp_path):
        """Snapshot gracefully handles files that can't be stat'd"""
        # Create a valid file
        (tmp_path / "valid.txt").write_text("content")

        # Create a broken symlink (target doesn't exist)
        broken_link = tmp_path / "broken_link"
        broken_link.symlink_to(tmp_path / "nonexistent_target")

        tracker = FileTracker(watch_dir=str(tmp_path))
        snapshot = tracker.take_snapshot()

        # Should include valid file but not crash on broken symlink
        assert "valid.txt" in snapshot
        assert "broken_link" not in snapshot


class TestChangeDetection:
    """Tests for detecting file changes between snapshots"""

    def test_detect_created_file(self, tmp_path):
        """Detects newly created files"""
        tracker = FileTracker(watch_dir=str(tmp_path))

        tracker.start_tracking()

        # Create a new file
        (tmp_path / "new_file.txt").write_text("new content")

        changes = tracker.stop_tracking()

        assert len(changes) == 1
        assert changes[0].path == "new_file.txt"
        assert changes[0].change_type == "created"
        assert changes[0].size is not None

    def test_detect_modified_file(self, tmp_path):
        """Detects modified files"""
        # Create file before tracking
        test_file = tmp_path / "existing.txt"
        test_file.write_text("original")

        tracker = FileTracker(watch_dir=str(tmp_path))
        tracker.start_tracking()

        # Wait to ensure mtime changes
        time.sleep(0.01)

        # Modify the file
        test_file.write_text("modified content")

        changes = tracker.stop_tracking()

        assert len(changes) == 1
        assert changes[0].path == "existing.txt"
        assert changes[0].change_type == "modified"

    def test_detect_deleted_file(self, tmp_path):
        """Detects deleted files"""
        # Create file before tracking
        test_file = tmp_path / "to_delete.txt"
        test_file.write_text("content")

        tracker = FileTracker(watch_dir=str(tmp_path))
        tracker.start_tracking()

        # Delete the file
        test_file.unlink()

        changes = tracker.stop_tracking()

        assert len(changes) == 1
        assert changes[0].path == "to_delete.txt"
        assert changes[0].change_type == "deleted"
        assert changes[0].size is None

    def test_detect_multiple_changes(self, tmp_path):
        """Detects multiple types of changes simultaneously"""
        # Setup: create files before tracking
        (tmp_path / "to_modify.txt").write_text("original")
        (tmp_path / "to_delete.txt").write_text("delete me")

        tracker = FileTracker(watch_dir=str(tmp_path))
        tracker.start_tracking()

        time.sleep(0.01)

        # Make changes
        (tmp_path / "new_file.txt").write_text("created")
        (tmp_path / "to_modify.txt").write_text("modified")
        (tmp_path / "to_delete.txt").unlink()

        changes = tracker.stop_tracking()

        change_map = {c.path: c.change_type for c in changes}
        assert change_map.get("new_file.txt") == "created"
        assert change_map.get("to_modify.txt") == "modified"
        assert change_map.get("to_delete.txt") == "deleted"

    def test_no_changes_detected(self, tmp_path):
        """No changes detected when nothing happens"""
        (tmp_path / "unchanged.txt").write_text("content")

        tracker = FileTracker(watch_dir=str(tmp_path))
        tracker.start_tracking()
        changes = tracker.stop_tracking()

        assert len(changes) == 0

    def test_nested_directory_changes(self, tmp_path):
        """Detects changes in nested directories"""
        nested = tmp_path / "src" / "lib"
        nested.mkdir(parents=True)

        tracker = FileTracker(watch_dir=str(tmp_path))
        tracker.start_tracking()

        (nested / "module.py").write_text("code")

        changes = tracker.stop_tracking()

        assert len(changes) == 1
        assert changes[0].path == "src/lib/module.py"


class TestSaveChanges:
    """Tests for saving changes to JSON"""

    def test_save_changes_creates_file(self, tmp_path):
        """save_changes creates a JSON file"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        tracker = FileTracker(watch_dir=str(tmp_path))
        changes = [
            FileChange(path="test.txt", change_type="created", timestamp="2024-01-01", size=100)
        ]

        result_path = tracker.save_changes("task_001", changes, output_dir=str(output_dir))

        assert Path(result_path).exists()
        assert "task_001_files.json" in result_path

    def test_save_changes_content(self, tmp_path):
        """save_changes writes correct JSON structure"""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        tracker = FileTracker(watch_dir=str(tmp_path))
        changes = [
            FileChange(path="created.txt", change_type="created", timestamp="2024-01-01", size=100),
            FileChange(path="deleted.txt", change_type="deleted", timestamp="2024-01-01", size=None)
        ]

        result_path = tracker.save_changes("task_001", changes, output_dir=str(output_dir))

        with open(result_path) as f:
            data = json.load(f)

        assert data["task_id"] == "task_001"
        assert "timestamp" in data
        assert len(data["changes"]) == 2
        assert data["changes"][0]["path"] == "created.txt"
        assert data["changes"][0]["change_type"] == "created"
        assert data["changes"][1]["size"] is None


class TestFileChangeDataclass:
    """Tests for FileChange dataclass"""

    def test_filechange_basic(self):
        """FileChange stores basic attributes"""
        change = FileChange(
            path="test.txt",
            change_type="created",
            timestamp="2024-01-01T12:00:00"
        )

        assert change.path == "test.txt"
        assert change.change_type == "created"
        assert change.timestamp == "2024-01-01T12:00:00"
        assert change.size is None

    def test_filechange_with_size(self):
        """FileChange can store file size"""
        change = FileChange(
            path="test.txt",
            change_type="modified",
            timestamp="2024-01-01T12:00:00",
            size=1024
        )

        assert change.size == 1024
