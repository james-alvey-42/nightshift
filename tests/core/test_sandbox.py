"""
Tests for SandboxManager - macOS sandbox profile generation
"""
import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from nightshift.core.sandbox import SandboxManager


class TestProfileCreation:
    """Tests for sandbox profile generation"""

    def test_create_profile_basic(self, tmp_path):
        """create_profile generates a .sb file"""
        sandbox = SandboxManager()
        profile_path = sandbox.create_profile([str(tmp_path)])

        assert Path(profile_path).exists()
        assert profile_path.endswith(".sb")

        # Cleanup
        sandbox.cleanup()

    def test_create_profile_content(self, tmp_path):
        """Profile contains expected sandbox directives"""
        sandbox = SandboxManager()
        profile_path = sandbox.create_profile([str(tmp_path)])

        content = Path(profile_path).read_text()

        # Check structure
        assert "(version 1)" in content
        assert "(deny default)" in content
        assert "(allow process*)" in content
        assert "(allow file-read*)" in content
        assert "(allow network*)" in content

        # Check allowed directory
        assert str(tmp_path) in content

        sandbox.cleanup()

    def test_create_profile_allows_temp_dirs(self, tmp_path):
        """Profile always allows /tmp and /private/tmp"""
        sandbox = SandboxManager()
        profile_path = sandbox.create_profile([str(tmp_path)])

        content = Path(profile_path).read_text()

        assert '"/tmp"' in content
        assert '"/private/tmp"' in content

        sandbox.cleanup()

    def test_create_profile_allows_claude_config(self, tmp_path):
        """Profile allows ~/.claude for Claude CLI"""
        sandbox = SandboxManager()
        profile_path = sandbox.create_profile([str(tmp_path)])

        content = Path(profile_path).read_text()

        claude_dir = str(Path.home() / ".claude")
        assert claude_dir in content

        sandbox.cleanup()

    def test_create_profile_with_needs_git(self, tmp_path):
        """Profile includes device files when needs_git=True"""
        sandbox = SandboxManager()
        profile_path = sandbox.create_profile([str(tmp_path)], needs_git=True)

        content = Path(profile_path).read_text()

        # Should allow device files
        assert '"/dev/null"' in content
        assert '"/dev/stdout"' in content
        assert '"/dev/stderr"' in content
        # Should allow security services for HTTPS
        assert "com.apple.SecurityServer" in content

        sandbox.cleanup()

    def test_create_profile_without_needs_git(self, tmp_path):
        """Profile excludes device files when needs_git=False"""
        sandbox = SandboxManager()
        profile_path = sandbox.create_profile([str(tmp_path)], needs_git=False)

        content = Path(profile_path).read_text()

        # Should NOT have device file rules (except in comments)
        lines = [l for l in content.split("\n") if not l.strip().startswith(";")]
        dev_lines = [l for l in lines if "/dev/null" in l]
        assert len(dev_lines) == 0

        sandbox.cleanup()

    def test_create_profile_multiple_directories(self, tmp_path):
        """Profile allows all specified directories"""
        dir1 = tmp_path / "dir1"
        dir2 = tmp_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        sandbox = SandboxManager()
        profile_path = sandbox.create_profile([str(dir1), str(dir2)])

        content = Path(profile_path).read_text()

        assert str(dir1) in content
        assert str(dir2) in content

        sandbox.cleanup()

    def test_create_profile_resolves_paths(self, tmp_path):
        """Profile resolves relative paths to absolute"""
        sandbox = SandboxManager()

        # Use a relative path
        with patch.object(Path, "resolve", return_value=tmp_path):
            profile_path = sandbox.create_profile(["./relative"])

            content = Path(profile_path).read_text()
            # Should contain resolved absolute path
            assert str(tmp_path) in content

        sandbox.cleanup()

    def test_create_profile_tracks_temp_files(self, tmp_path):
        """Sandbox manager tracks created profile files"""
        sandbox = SandboxManager()

        profile1 = sandbox.create_profile([str(tmp_path)])
        profile2 = sandbox.create_profile([str(tmp_path)])

        assert len(sandbox._temp_profiles) == 2
        assert profile1 in sandbox._temp_profiles
        assert profile2 in sandbox._temp_profiles

        sandbox.cleanup()

    def test_create_profile_warns_on_nonexistent_directory(self, tmp_path, caplog):
        """Profile creation warns when allowed directory doesn't exist"""
        sandbox = SandboxManager()

        nonexistent = tmp_path / "does_not_exist"

        with caplog.at_level("WARNING"):
            profile_path = sandbox.create_profile([str(nonexistent)])

        # Warning should be logged
        assert "does not exist" in caplog.text

        # Profile should still be created (resolved path included)
        content = Path(profile_path).read_text()
        assert "does_not_exist" in content

        sandbox.cleanup()


class TestWrapCommand:
    """Tests for wrap_command method"""

    def test_wrap_command_basic(self, tmp_path):
        """wrap_command prepends sandbox-exec"""
        sandbox = SandboxManager()

        wrapped = sandbox.wrap_command("echo hello", [str(tmp_path)])

        assert wrapped.startswith("sandbox-exec -f")
        assert "echo hello" in wrapped

        sandbox.cleanup()

    def test_wrap_command_with_needs_git(self, tmp_path):
        """wrap_command passes needs_git to profile"""
        sandbox = SandboxManager()

        wrapped = sandbox.wrap_command(
            "gh pr list",
            [str(tmp_path)],
            needs_git=True
        )

        # Find the profile path in the command
        # Format: sandbox-exec -f "/path/to/profile.sb" command
        profile_path = wrapped.split('"')[1]
        content = Path(profile_path).read_text()

        assert '"/dev/null"' in content

        sandbox.cleanup()


class TestCleanup:
    """Tests for profile cleanup"""

    def test_cleanup_removes_profiles(self, tmp_path):
        """cleanup removes all created profile files"""
        sandbox = SandboxManager()

        profile1 = sandbox.create_profile([str(tmp_path)])
        profile2 = sandbox.create_profile([str(tmp_path)])

        assert Path(profile1).exists()
        assert Path(profile2).exists()

        sandbox.cleanup()

        assert not Path(profile1).exists()
        assert not Path(profile2).exists()

    def test_cleanup_clears_list(self, tmp_path):
        """cleanup clears the internal profile list"""
        sandbox = SandboxManager()

        sandbox.create_profile([str(tmp_path)])
        assert len(sandbox._temp_profiles) == 1

        sandbox.cleanup()
        assert len(sandbox._temp_profiles) == 0

    def test_cleanup_handles_missing_files(self, tmp_path):
        """cleanup handles already-deleted files gracefully"""
        sandbox = SandboxManager()

        profile = sandbox.create_profile([str(tmp_path)])
        # Manually delete the file
        Path(profile).unlink()

        # Should not raise
        sandbox.cleanup()


class TestIsAvailable:
    """Tests for sandbox availability check"""

    def test_is_available_returns_bool(self):
        """is_available returns a boolean"""
        result = SandboxManager.is_available()
        assert isinstance(result, bool)

    @patch("shutil.which")
    def test_is_available_when_present(self, mock_which):
        """is_available returns True when sandbox-exec exists"""
        mock_which.return_value = "/usr/bin/sandbox-exec"

        assert SandboxManager.is_available() is True

    @patch("shutil.which")
    def test_is_available_when_missing(self, mock_which):
        """is_available returns False when sandbox-exec missing"""
        mock_which.return_value = None

        assert SandboxManager.is_available() is False


class TestValidateDirectories:
    """Tests for directory validation"""

    def test_validate_normal_directories(self, tmp_path):
        """validate_directories accepts normal paths"""
        dir1 = tmp_path / "safe1"
        dir2 = tmp_path / "safe2"
        dir1.mkdir()
        dir2.mkdir()

        result = SandboxManager.validate_directories([str(dir1), str(dir2)])

        assert str(dir1) in result
        assert str(dir2) in result

    def test_validate_rejects_root(self):
        """validate_directories rejects root directory"""
        with pytest.raises(ValueError) as exc_info:
            SandboxManager.validate_directories(["/"])

        assert "system directory" in str(exc_info.value)

    def test_validate_rejects_etc(self):
        """validate_directories rejects /etc"""
        with pytest.raises(ValueError) as exc_info:
            SandboxManager.validate_directories(["/etc"])

        assert "system directory" in str(exc_info.value)

    def test_validate_rejects_private_etc(self):
        """validate_directories rejects /private/etc"""
        with pytest.raises(ValueError) as exc_info:
            SandboxManager.validate_directories(["/private/etc"])

        assert "system directory" in str(exc_info.value)

    def test_validate_rejects_var(self):
        """validate_directories rejects /var"""
        with pytest.raises(ValueError) as exc_info:
            SandboxManager.validate_directories(["/var"])

        assert "system directory" in str(exc_info.value)

    def test_validate_rejects_bin(self):
        """validate_directories rejects /bin"""
        with pytest.raises(ValueError) as exc_info:
            SandboxManager.validate_directories(["/bin"])

        assert "system directory" in str(exc_info.value)

    def test_validate_rejects_usr(self):
        """validate_directories rejects /usr"""
        with pytest.raises(ValueError) as exc_info:
            SandboxManager.validate_directories(["/usr"])

        assert "system directory" in str(exc_info.value)

    def test_validate_rejects_system(self):
        """validate_directories rejects /System"""
        with pytest.raises(ValueError) as exc_info:
            SandboxManager.validate_directories(["/System"])

        assert "system directory" in str(exc_info.value)

    def test_validate_rejects_library(self):
        """validate_directories rejects /Library"""
        with pytest.raises(ValueError) as exc_info:
            SandboxManager.validate_directories(["/Library"])

        assert "system directory" in str(exc_info.value)

    def test_validate_rejects_child_of_dangerous(self):
        """validate_directories rejects children of dangerous paths"""
        with pytest.raises(ValueError) as exc_info:
            SandboxManager.validate_directories(["/etc/passwd"])

        assert "system directory" in str(exc_info.value)

    def test_validate_warns_home_directory(self, tmp_path, caplog):
        """validate_directories warns about home directory"""
        import logging

        with caplog.at_level(logging.WARNING):
            home = str(Path.home())
            SandboxManager.validate_directories([home])

        assert "home directory" in caplog.text.lower()

    def test_validate_resolves_paths(self, tmp_path):
        """validate_directories resolves paths"""
        # Create a real directory we can resolve
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        result = SandboxManager.validate_directories([str(test_dir)])

        # Result should be absolute path
        assert Path(result[0]).is_absolute()
