"""
Scratch Manager - Manages isolated scratch directories for task execution

Provides proper isolation by:
1. Creating temporary working directories for each task
2. Copying/cloning required files and git repositories into scratch
3. Executing tasks in isolation
4. Copying modified files back to original locations
5. Cleaning up scratch directories after completion
"""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
from datetime import datetime

from .logger import NightShiftLogger


class ScratchManager:
    """
    Manages scratch directory lifecycle for task isolation

    Workflow:
    1. create_scratch() - Create isolated directory with required resources
    2. Task executes in scratch directory
    3. teardown_scratch() - Copy results back and cleanup
    """

    def __init__(
        self,
        logger: NightShiftLogger,
        scratch_base: Optional[Path] = None
    ):
        """
        Initialize scratch manager

        Args:
            logger: Logger instance
            scratch_base: Base directory for scratch workspaces (default: ~/.nightshift/worktrees)
        """
        self.logger = logger
        self.scratch_base = scratch_base or (Path.home() / ".nightshift" / "worktrees")
        self.scratch_base.mkdir(parents=True, exist_ok=True)

    def create_scratch(
        self,
        task_id: str,
        git_repos: Optional[List[Dict[str, str]]] = None,
        copy_paths: Optional[List[Dict[str, str]]] = None,
        link_paths: Optional[List[Dict[str, str]]] = None
    ) -> Path:
        """
        Create and populate a scratch directory for task execution

        Args:
            task_id: Unique task identifier
            git_repos: List of git repos to clone, each dict with:
                - 'source': Path to source git repo
                - 'dest': Relative path in scratch (optional, defaults to repo name)
            copy_paths: List of paths to copy, each dict with:
                - 'source': Source path (file or directory)
                - 'dest': Relative path in scratch (optional, preserves structure)
            link_paths: List of paths to symlink (for read-only access), each dict with:
                - 'source': Source path
                - 'dest': Relative path in scratch

        Returns:
            Path to the created scratch directory
        """
        scratch_dir = self.scratch_base / task_id

        # Clean up any existing scratch directory from previous attempts
        if scratch_dir.exists():
            self.logger.warning(f"Scratch directory already exists, cleaning up: {scratch_dir}")
            shutil.rmtree(scratch_dir)

        scratch_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Created scratch directory: {scratch_dir}")

        # Clone git repositories
        if git_repos:
            for repo_spec in git_repos:
                source = Path(repo_spec['source']).resolve()
                dest_name = repo_spec.get('dest', source.name)
                dest = scratch_dir / dest_name

                if not source.exists():
                    self.logger.warning(f"Git repo source does not exist: {source}")
                    continue

                if not (source / ".git").exists():
                    self.logger.warning(f"Not a git repository: {source}")
                    continue

                try:
                    # Use git clone with local path for efficiency
                    # --shared saves disk space by using git alternates
                    self.logger.info(f"Cloning git repo {source} -> {dest}")
                    result = subprocess.run(
                        ["git", "clone", "--shared", str(source), str(dest)],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )

                    if result.returncode == 0:
                        self.logger.info(f"Successfully cloned: {dest_name}")
                    else:
                        self.logger.error(f"Failed to clone {source}: {result.stderr}")

                except subprocess.TimeoutExpired:
                    self.logger.error(f"Timeout cloning {source}")
                except Exception as e:
                    self.logger.error(f"Error cloning {source}: {e}")

        # Copy files and directories
        if copy_paths:
            for path_spec in copy_paths:
                source = Path(path_spec['source']).resolve()

                # Determine destination
                if 'dest' in path_spec:
                    dest = scratch_dir / path_spec['dest']
                else:
                    # Preserve relative structure from CWD
                    try:
                        rel_path = source.relative_to(Path.cwd())
                        dest = scratch_dir / rel_path
                    except ValueError:
                        # Source is outside CWD, use just the name
                        dest = scratch_dir / source.name

                if not source.exists():
                    self.logger.warning(f"Copy source does not exist: {source}")
                    continue

                try:
                    # Ensure parent directory exists
                    dest.parent.mkdir(parents=True, exist_ok=True)

                    if source.is_file():
                        self.logger.info(f"Copying file {source} -> {dest}")
                        shutil.copy2(source, dest)
                    elif source.is_dir():
                        self.logger.info(f"Copying directory {source} -> {dest}")
                        shutil.copytree(source, dest, symlinks=True, dirs_exist_ok=True)

                except Exception as e:
                    self.logger.error(f"Error copying {source}: {e}")

        # Create symlinks (for read-only access to large resources)
        if link_paths:
            for link_spec in link_paths:
                source = Path(link_spec['source']).resolve()
                dest_name = link_spec.get('dest', source.name)
                dest = scratch_dir / dest_name

                if not source.exists():
                    self.logger.warning(f"Link source does not exist: {source}")
                    continue

                try:
                    dest.symlink_to(source)
                    self.logger.info(f"Created symlink {dest} -> {source}")
                except Exception as e:
                    self.logger.error(f"Error creating symlink {source}: {e}")

        # Save scratch manifest for teardown and resumption
        manifest = {
            'task_id': task_id,
            'scratch_dir': str(scratch_dir),
            'created_at': datetime.now().isoformat(),
            'git_repos': git_repos or [],
            'copy_paths': copy_paths or [],
            'link_paths': link_paths or [],
            'version': '1.0'  # Manifest version for future compatibility
        }

        manifest_path = scratch_dir / ".nightshift_manifest.json"
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)

        self.logger.info(f"Scratch directory ready: {scratch_dir}")
        return scratch_dir

    def teardown_scratch(
        self,
        scratch_dir: Path,
        copy_back: bool = True,
        keep_scratch: bool = False
    ) -> Dict[str, Any]:
        """
        Teardown scratch directory and optionally copy results back

        Args:
            scratch_dir: Path to scratch directory
            copy_back: Whether to copy modified files back to original locations
            keep_scratch: Whether to keep scratch directory (for debugging)

        Returns:
            Dict with:
                - 'copied_files': List of files copied back
                - 'errors': List of errors encountered
        """
        result = {
            'copied_files': [],
            'errors': []
        }

        if not scratch_dir.exists():
            result['errors'].append(f"Scratch directory does not exist: {scratch_dir}")
            return result

        # Load manifest
        manifest_path = scratch_dir / ".nightshift_manifest.json"
        if not manifest_path.exists():
            self.logger.warning(f"No manifest found in scratch directory: {scratch_dir}")
            manifest = {'git_repos': [], 'copy_paths': []}
        else:
            with open(manifest_path) as f:
                manifest = json.load(f)

        if copy_back:
            # Copy back modified files from git repos
            for repo_spec in manifest.get('git_repos', []):
                source_repo = Path(repo_spec['source']).resolve()
                dest_name = repo_spec.get('dest', source_repo.name)
                scratch_repo = scratch_dir / dest_name

                if not scratch_repo.exists():
                    continue

                try:
                    # Check if there are any changes in the scratch repo
                    status_result = subprocess.run(
                        ["git", "-C", str(scratch_repo), "status", "--porcelain"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    if status_result.stdout.strip():
                        # There are uncommitted changes
                        self.logger.info(f"Found uncommitted changes in {scratch_repo}")

                        # Get list of modified/new files
                        files_result = subprocess.run(
                            ["git", "-C", str(scratch_repo), "diff", "--name-only", "HEAD"],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )

                        modified_files = files_result.stdout.strip().split('\n')

                        # Copy modified files back to source repo
                        for rel_file in modified_files:
                            if not rel_file:
                                continue
                            src_file = scratch_repo / rel_file
                            dest_file = source_repo / rel_file

                            if src_file.exists():
                                try:
                                    dest_file.parent.mkdir(parents=True, exist_ok=True)
                                    shutil.copy2(src_file, dest_file)
                                    result['copied_files'].append(str(dest_file))
                                    self.logger.info(f"Copied back: {dest_file}")
                                except Exception as e:
                                    error_msg = f"Failed to copy {src_file} -> {dest_file}: {e}"
                                    result['errors'].append(error_msg)
                                    self.logger.error(error_msg)

                    # Check for new commits that need to be pushed back
                    # Count commits ahead of origin
                    ahead_result = subprocess.run(
                        ["git", "-C", str(scratch_repo), "rev-list", "--count", "HEAD", "^origin/HEAD"],
                        capture_output=True,
                        text=True,
                        timeout=10
                    )

                    if ahead_result.returncode == 0:
                        ahead_count = int(ahead_result.stdout.strip() or 0)
                        if ahead_count > 0:
                            self.logger.info(f"Found {ahead_count} new commits in {scratch_repo}")

                            # Get commit info
                            log_result = subprocess.run(
                                ["git", "-C", str(scratch_repo), "log", f"origin/HEAD..HEAD", "--oneline"],
                                capture_output=True,
                                text=True,
                                timeout=10
                            )

                            commits = log_result.stdout.strip()
                            self.logger.info(f"New commits:\n{commits}")

                            # Copy the .git directory to preserve commits
                            # This is safer than trying to push from scratch
                            try:
                                self.logger.info(f"Syncing git state from {scratch_repo} to {source_repo}")

                                # Use git fetch to pull commits from scratch to source
                                fetch_result = subprocess.run(
                                    ["git", "-C", str(source_repo), "fetch", str(scratch_repo), "HEAD:refs/heads/nightshift-scratch"],
                                    capture_output=True,
                                    text=True,
                                    timeout=30
                                )

                                if fetch_result.returncode == 0:
                                    self.logger.info("Successfully fetched commits to source repo (branch: nightshift-scratch)")
                                    self.logger.info("You can merge with: git merge nightshift-scratch")
                                else:
                                    error_msg = f"Failed to fetch commits: {fetch_result.stderr}"
                                    result['errors'].append(error_msg)
                                    self.logger.error(error_msg)

                            except Exception as e:
                                error_msg = f"Failed to sync git state: {e}"
                                result['errors'].append(error_msg)
                                self.logger.error(error_msg)

                except subprocess.TimeoutExpired:
                    error_msg = f"Timeout checking git status for {scratch_repo}"
                    result['errors'].append(error_msg)
                    self.logger.error(error_msg)
                except Exception as e:
                    error_msg = f"Error processing git repo {scratch_repo}: {e}"
                    result['errors'].append(error_msg)
                    self.logger.error(error_msg)

            # Copy back modified files from copy_paths
            for path_spec in manifest.get('copy_paths', []):
                source = Path(path_spec['source']).resolve()

                # Determine where file is in scratch
                if 'dest' in path_spec:
                    scratch_path = scratch_dir / path_spec['dest']
                else:
                    try:
                        rel_path = source.relative_to(Path.cwd())
                        scratch_path = scratch_dir / rel_path
                    except ValueError:
                        scratch_path = scratch_dir / source.name

                if not scratch_path.exists():
                    continue

                try:
                    if scratch_path.is_file():
                        # Check if file was modified (compare mtime or content)
                        if not source.exists() or scratch_path.stat().st_mtime > source.stat().st_mtime:
                            source.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(scratch_path, source)
                            result['copied_files'].append(str(source))
                            self.logger.info(f"Copied back modified file: {source}")
                    elif scratch_path.is_dir():
                        # For directories, sync only modified files
                        for scratch_file in scratch_path.rglob('*'):
                            if not scratch_file.is_file():
                                continue

                            rel_to_scratch = scratch_file.relative_to(scratch_path)
                            dest_file = source / rel_to_scratch

                            # Copy if new or modified
                            if not dest_file.exists() or scratch_file.stat().st_mtime > dest_file.stat().st_mtime:
                                dest_file.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy2(scratch_file, dest_file)
                                result['copied_files'].append(str(dest_file))
                                self.logger.debug(f"Copied back: {dest_file}")

                except Exception as e:
                    error_msg = f"Error copying back {scratch_path}: {e}"
                    result['errors'].append(error_msg)
                    self.logger.error(error_msg)

        # Cleanup scratch directory
        if not keep_scratch:
            try:
                shutil.rmtree(scratch_dir)
                self.logger.info(f"Cleaned up scratch directory: {scratch_dir}")
            except Exception as e:
                error_msg = f"Failed to cleanup scratch directory {scratch_dir}: {e}"
                result['errors'].append(error_msg)
                self.logger.error(error_msg)
        else:
            self.logger.info(f"Keeping scratch directory for debugging: {scratch_dir}")

        return result

    def get_scratch_path(self, task_id: str) -> Path:
        """Get the path to a task's scratch directory"""
        return self.scratch_base / task_id

    def cleanup_all_scratch(self, older_than_days: Optional[int] = None):
        """
        Cleanup all scratch directories

        Args:
            older_than_days: Only cleanup directories older than this many days
        """
        import time

        if not self.scratch_base.exists():
            return

        cleaned_count = 0
        for scratch_dir in self.scratch_base.iterdir():
            if not scratch_dir.is_dir():
                continue

            # Check age if specified
            if older_than_days is not None:
                age_days = (time.time() - scratch_dir.stat().st_mtime) / 86400
                if age_days < older_than_days:
                    continue

            try:
                shutil.rmtree(scratch_dir)
                cleaned_count += 1
                self.logger.debug(f"Cleaned up scratch directory: {scratch_dir}")
            except Exception as e:
                self.logger.error(f"Failed to cleanup {scratch_dir}: {e}")

        self.logger.info(f"Cleaned up {cleaned_count} scratch directories")
