"""
MCP Server Discovery - Auto-detect MCP server locations for Docker mounting
Resolves MCP executables and infers minimal mount paths needed to run them
"""
import json
import logging
import re
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

logger = logging.getLogger(__name__)


def discover_mcp_mount_paths() -> Set[Path]:
    """
    Auto-discover paths needed to mount for MCP servers to work

    Returns:
        Set of paths to mount read-only in Docker container
    """
    mounts = set()

    # Get MCP servers from Claude
    servers = _load_mcp_servers()
    if not servers:
        logger.warning("No MCP servers found via 'claude mcp list'. MCP tools will not be available in container.")
        return mounts

    logger.debug(f"Discovered {len(servers)} MCP servers: {', '.join(servers.keys())}")

    # Add npm global paths if any Node-based MCPs exist
    npm_mounts = _get_npm_global_paths()
    mounts.update(npm_mounts)

    # Process each MCP server
    for name, (cmd, args) in servers.items():
        if cmd == "npx":
            # npx-based MCPs are handled by npm global mounts
            continue

        exe_path = _resolve_executable(cmd)
        if not exe_path:
            logger.warning(f"Could not resolve MCP server '{name}' command: {cmd}")
            continue

        # Classify and extract mount paths
        kind, metadata = _classify_executable(exe_path)

        if kind == "script":
            # Script with shebang - check for Python venv
            interp_path = metadata.get("interpreter")
            venv_found = False
            if interp_path and "python" in str(interp_path):
                venv_root = _find_python_venv_root(Path(interp_path))
                if venv_root and _is_user_path(venv_root):
                    mounts.add(venv_root)
                    venv_found = True

            # Mount the script's directory only if:
            # - It's a user path
            # - We didn't already mount a venv that contains it
            # System scripts should be provided in the Docker image
            if not venv_found and _is_user_path(exe_path):
                mounts.add(exe_path.parent)

        elif kind == "elf" or kind == "unknown":
            # Binary or unknown - mount its parent directory if under user paths
            # System binaries should be provided in Docker image, not mounted
            if _is_user_path(exe_path):
                mounts.add(exe_path.parent)

    return mounts


def _load_mcp_servers() -> Dict[str, Tuple[str, List[str]]]:
    """Load MCP servers by parsing `claude mcp list` output"""
    try:
        result = subprocess.run(
            ["claude", "mcp", "list"],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            logger.warning(f"'claude mcp list' failed with exit code {result.returncode}")
            if result.stderr:
                logger.debug(f"Error output: {result.stderr}")
            return {}

        servers = {}
        # Pattern: "name: command args - status"
        # Matches everything between ":" and "-" as the command
        pattern = r"^([^:]+):\s+(.+?)\s+-"

        for line in result.stdout.splitlines():
            # Strip ANSI color codes if present
            clean_line = re.sub(r'\x1b\[[0-9;]*m', '', line)

            match = re.match(pattern, clean_line)
            if not match:
                continue

            name = match.group(1).strip()
            cmd_part = match.group(2).strip()

            # Split command into executable and args
            cmd_tokens = cmd_part.split()
            if not cmd_tokens:
                continue

            cmd = cmd_tokens[0]
            args = cmd_tokens[1:] if len(cmd_tokens) > 1 else []
            servers[name] = (cmd, args)

        return servers

    except subprocess.TimeoutExpired:
        logger.warning("'claude mcp list' timed out after 10 seconds")
        return {}
    except FileNotFoundError:
        logger.warning("'claude' command not found. Is Claude Code installed?")
        return {}
    except OSError as e:
        logger.warning(f"Failed to execute 'claude mcp list': {e}")
        return {}


def _resolve_executable(cmd: str) -> Optional[Path]:
    """Resolve command to absolute path"""
    # Check if already a path
    p = Path(cmd)
    if p.is_absolute() and p.exists():
        return p

    # Search PATH
    exe = shutil.which(cmd)
    return Path(exe) if exe else None


def _classify_executable(path: Path) -> Tuple[str, Dict]:
    """
    Classify executable type

    Returns:
        (type, metadata) where type is "script", "elf", or "unknown"
        metadata includes "interpreter" for scripts
    """
    try:
        st = path.stat()
        if not (st.st_mode & stat.S_IXUSR):
            return "non-executable", {}
    except OSError:
        return "unknown", {}

    # Check for shebang
    shebang_info = _read_shebang(path)
    if shebang_info:
        interpreter, args = shebang_info
        return "script", {"interpreter": interpreter, "interp_args": args}

    # Check for ELF magic
    try:
        with path.open("rb") as f:
            magic = f.read(4)
            if magic == b"\x7fELF":
                return "elf", {}
    except OSError:
        pass

    return "unknown", {}


def _read_shebang(path: Path) -> Optional[Tuple[str, List[str]]]:
    """Read shebang from file, return (interpreter, args)"""
    try:
        with path.open("rb") as f:
            first_line = f.readline().decode("utf-8", "replace").strip()
    except OSError:
        return None

    if not first_line.startswith("#!"):
        return None

    # Parse shebang
    shebang = first_line[2:].strip()
    parts = shebang.split()
    if not parts:
        return None

    interpreter = parts[0]
    args = parts[1:] if len(parts) > 1 else []

    # Resolve /usr/bin/env indirection
    if interpreter.endswith("/env") and args:
        env_cmd = args[0]
        resolved = shutil.which(env_cmd)
        if resolved:
            return resolved, args[1:]

    return interpreter, args


def _find_python_venv_root(python_path: Path) -> Optional[Path]:
    """Find Python virtualenv root directory"""
    # Don't resolve symlinks - we want the venv path, not the system python
    # Typical venv structure: venv/bin/python -> /usr/bin/python3.x (symlink)
    p = python_path

    # Check parent's parent for venv markers
    # For /path/to/venv/bin/python, parent.parent is /path/to/venv
    candidates = [p.parent.parent, p.parent.parent.parent]

    for root in candidates:
        try:
            if not root.exists():
                continue
        except OSError:
            continue

        # Check for venv markers
        if (root / "pyvenv.cfg").exists():
            return root
        if (root / "bin" / "activate").exists():
            return root

    return None


def _get_npm_global_paths() -> Set[Path]:
    """Get npm global prefix and root paths (only user paths)"""
    paths = set()

    try:
        # Get npm prefix (where global binaries are installed)
        result = subprocess.run(
            ["npm", "config", "get", "prefix"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            prefix = Path(result.stdout.strip())
            if prefix.exists() and _is_user_path(prefix):
                paths.add(prefix)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    try:
        # Get npm root (node_modules location)
        result = subprocess.run(
            ["npm", "root", "-g"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            root = Path(result.stdout.strip())
            if root.exists() and _is_user_path(root):
                paths.add(root)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass

    return paths


def _is_user_path(path: Path) -> bool:
    """Check if path is under user-controlled directories (not system)"""
    path_str = str(path)

    # User paths
    if path_str.startswith(str(Path.home())):
        return True
    if path_str.startswith("/opt/"):
        return True

    # System paths (don't mount these, provide in image instead)
    system_prefixes = ["/usr/", "/bin/", "/sbin/", "/lib/", "/lib64/"]
    if any(path_str.startswith(prefix) for prefix in system_prefixes):
        return False

    return True
