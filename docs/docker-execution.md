# Docker Containerized Execution

This document describes NightShift's Docker containerization feature, which provides secure, isolated execution of Claude Code tasks with full MCP tool support.

## Overview

NightShift can execute Claude Code tasks in isolated Docker containers, providing:

- **Security isolation**: Tasks run in sandboxed containers with read-only filesystems
- **Reproducible environments**: Consistent execution across different machines
- **MCP tool support**: All MCP servers (Gemini, OpenAI, ArXiv, Google Calendar, etc.) work seamlessly
- **Cross-platform compatibility**: Automatic platform detection and configuration

## Architecture

### Platform-Specific Execution Strategies

NightShift automatically detects the host operating system and adapts its containerization strategy:

#### Linux Hosts
- **MCP servers**: Mounts host MCP installations (compatible Linux ELF binaries)
- **System directories**: Mounts `/lib`, `/lib64`, `/opt` from host
- **Performance**: Optimal - uses native binaries without overhead

#### macOS/Windows Hosts
- **MCP servers**: Uses container-installed MCP servers (incompatible host binaries)
- **System directories**: Only mounts `/lib`, `/lib64` (skips `/opt` to preserve container's `/opt/mcp-venv`)
- **Compatibility**: Full - container has Linux-compatible MCP installations

### Container Architecture

The `nightshift-claude-executor:latest` Docker image contains:

1. **Base**: Node 20-slim (Debian-based)
2. **Claude Code CLI**: Installed globally via npm
3. **Python 3.11**: For MCP server execution
4. **MCP Servers**: Full `mcp-handley-lab` package installed at `/opt/mcp-venv`
5. **System dependencies**: Git, curl, Playwright dependencies

### Mounted Resources

When executing tasks, the container mounts:

| Resource | Host Path | Container Path | Mode | Purpose |
|----------|-----------|----------------|------|---------|
| Working directory | `$(pwd)` | `/work` | rw | Task execution and file outputs |
| Claude config | `~/.claude` | `~/.claude` | rw | Debug logs and session data |
| Claude MCP config | `~/.claude.nightshift.*.json` | `~/.claude.json` | rw | Temporary config with container MCP paths |
| System libs (Linux) | `/lib`, `/lib64`, `/opt` | Same | ro | System dependencies |
| System libs (macOS) | `/lib`, `/lib64` | Same | ro | System dependencies (no `/opt`) |

### MCP Configuration Management

The executor creates a temporary `.claude.json` configuration file that:

1. **Reads** the host's `~/.claude.json` with MCP server definitions
2. **Resolves** commands based on platform:
   - **Linux**: Resolves to host absolute paths (e.g., `/home/user/.local/bin/mcp-gemini`)
   - **macOS/Windows**: Maps to container paths (e.g., `/opt/mcp-venv/bin/mcp-gemini`)
3. **Mounts** the temporary config as `~/.claude.json` inside the container
4. **Cleans up** the temporary config after execution

Example transformation (macOS):

**Host config:**
```json
{
  "mcpServers": {
    "gemini": {
      "command": "mcp-gemini",
      "args": []
    }
  }
}
```

**Container config:**
```json
{
  "mcpServers": {
    "gemini": {
      "command": "/opt/mcp-venv/bin/mcp-gemini",
      "args": []
    }
  }
}
```

## Technical Details

### Binary Compatibility Issues (Solved)

**Problem**: MCP servers installed on macOS have shebangs pointing to macOS Python binaries:
```python
#!/Users/username/venv/bin/python3
```

These are Mach-O format executables that cannot run in Linux containers, causing:
```
/bin/bash: line 1: /path/to/python3: cannot execute binary file: Exec format error
```

**Solution**:
1. Install MCP servers inside the Docker image during build (Linux ELF binaries)
2. Detect host OS and use appropriate MCP strategy
3. Create platform-specific config with correct paths

### Container Security

The container runs with several security constraints:

- `--read-only`: Root filesystem is read-only
- `--tmpfs /tmp`: Temporary files in memory-backed filesystem
- `-u $(id -u):$(id -g)`: Runs as host user, not root
- Minimal mounts: Only necessary directories are mounted
- No privileged mode: Standard container isolation

### Environment Variables

The following environment variables are passed through to the container:

- `ANTHROPIC_API_KEY`: For Claude API access
- `GEMINI_API_KEY`: For Google Gemini MCP tools
- `OPENAI_API_KEY`: For OpenAI MCP tools
- `GOOGLE_API_KEY`: For Google services
- `HOME`: Set to host's home directory path
- `PATH`: Configured to prioritize container MCP binaries

## Implementation Details

### Key Components

#### DockerExecutor (`nightshift/core/docker_executor.py`)

Main class responsible for Docker execution:

- `_create_container_config(source_config_path, use_container_mcps)`: Creates temporary config with platform-appropriate MCP paths
- `build_docker_command(claude_args, env_vars, additional_mounts)`: Constructs the full docker run command
- `execute(claude_args, env_vars, timeout, additional_mounts)`: Executes Claude Code in container
- Platform detection via `platform.system()`: Determines Linux vs macOS/Windows

#### MCPDiscovery (`nightshift/core/mcp_discovery.py`)

Used on Linux hosts to discover and mount host MCP installations:

- `discover_mcp_mount_paths()`: Auto-discovers MCP server paths
- Parses `claude mcp list` output
- Resolves executables and finds virtualenv roots
- Returns minimal set of paths to mount

#### Dockerfile (`docker/claude-executor/Dockerfile`)

Defines the container image:

```dockerfile
FROM node:20-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git curl ca-certificates \
    python3 python3-venv python3-pip \
    # Playwright dependencies
    libnss3 libatk1.0-0 ...

# Install Claude Code
RUN npm install -g @anthropic-ai/claude-code

# Install MCP servers in container venv
COPY mcp-handley-lab /tmp/mcp-handley-lab
RUN python3 -m venv /opt/mcp-venv && \
    /opt/mcp-venv/bin/pip install /tmp/mcp-handley-lab && \
    rm -rf /tmp/mcp-handley-lab

ENV PATH="/opt/mcp-venv/bin:${PATH}"

ENTRYPOINT ["/usr/local/bin/claude"]
```

## Limitations and Known Issues

### Current Limitations

1. **OAuth flows**: MCP tools requiring browser-based OAuth (e.g., Google Calendar on first use) need credentials set up on the host before containerized execution
2. **File permissions**: Files created in containers inherit host user's UID/GID, but this may cause issues on some systems
3. **Network access**: Container needs internet access for API calls
4. **Disk space**: Container image is ~2GB due to Playwright dependencies

### Known Issues

1. **Claude CLI crashes**: `claude mcp list` sometimes crashes with stack overflow in container (Claude CLI bug, not related to our Docker setup)
2. **Temporary config files**: Temp configs (`.claude.nightshift.*.json`) accumulate in home directory - cleanup happens on exit but not if process is killed
3. **First-time auth**: Some MCP tools (Google Calendar, GitHub) require interactive auth that must be done outside the container first

### Workarounds

**For OAuth-based MCP tools:**
```bash
# Run auth flow on host first
mcp-google-calendar  # Follow OAuth flow in browser

# Then use in container
NIGHTSHIFT_USE_DOCKER=true nightshift submit "Add calendar event..."
```

**For temp config cleanup:**
```bash
# Manual cleanup if needed
rm ~/.claude.nightshift.*.json
```

## Future Improvements

### Planned Enhancements

1. **Credential mounting**: Automatically mount OAuth tokens/credentials from host
2. **Smaller base image**: Multi-stage build to reduce image size
3. **Config cleanup**: Better temporary file lifecycle management
4. **Pre-built images**: Publish images to Docker Hub for faster setup
5. **GPU support**: NVIDIA GPU passthrough for ML workloads
6. **Network isolation**: Optional network policies for sensitive tasks

### Performance Optimizations

1. **Layer caching**: Optimize Dockerfile for better build caching
2. **Parallel builds**: Multi-stage builds with parallel pip installs
3. **Volume caching**: Persistent cache volumes for pip/npm
4. **Image variants**: CPU-only vs full Playwright variants

## Troubleshooting

### Container Build Issues

**Problem**: Docker build fails with "permission denied"
```bash
./scripts/build-executor.sh
# Error: permission denied
```

**Solution**: Ensure Docker daemon is running and you have permissions:
```bash
docker ps  # Test Docker access
sudo usermod -aG docker $USER  # Add user to docker group (Linux)
# Logout/login for group change to take effect
```

### MCP Tools Not Found

**Problem**: MCP servers fail with "command not found"
```
✗ Failed to connect: /opt/mcp-venv/bin/mcp-gemini
```

**Solution**: Check if `/opt` is being mounted from host (it shouldn't be on macOS):
```bash
# In interactive container session
ls /opt/mcp-venv/bin/  # Should show MCP executables

# If not, check docker_executor.py is not mounting /opt on macOS
```

### API Key Not Found

**Problem**: Claude reports "API key not found" in container

**Solution**: Ensure API keys are exported before running:
```bash
export ANTHROPIC_API_KEY="your-key-here"
export NIGHTSHIFT_USE_DOCKER=true
nightshift submit "your task"
```

### Interactive Testing

To debug issues, start an interactive container session:

```bash
cd /path/to/nightshift
python3 << 'EOF'
from nightshift.core.docker_executor import DockerExecutor
executor = DockerExecutor()
cmd = executor.build_docker_command(claude_args=['--version'])
# Find image index and build interactive command
image_idx = cmd.index('nightshift-claude-executor:latest')
interactive = cmd[:2] + ['-it'] + cmd[2:image_idx] + ['--entrypoint', '/bin/bash', cmd[image_idx]]
print(' \\\n  '.join(interactive))
EOF
```

Then run the printed command and test inside the container:
```bash
# Inside container
which mcp-gemini          # Should be /opt/mcp-venv/bin/mcp-gemini
claude --version          # Should show Claude Code version
cat ~/.claude.json | grep command  # Check MCP paths
claude mcp list           # Check MCP server status
```

## Security Considerations

### Container Isolation

The Docker executor implements defense-in-depth security:

1. **Read-only root**: Prevents tampering with system files
2. **User namespace**: Runs as non-root user
3. **Minimal mounts**: Only essential directories are accessible
4. **No network override**: Uses default Docker network (can be restricted)
5. **Temporary filesystem**: `/tmp` is ephemeral and memory-backed

### API Key Handling

- API keys are passed as environment variables (not written to disk in container)
- Temporary config files are created with secure permissions (0600)
- Cleanup is automatic on normal exit (manual cleanup needed on kill)

### Host Access

The container has **limited** access to the host:

✅ **Can access:**
- Working directory (read-write)
- `.claude` config directory (read-write)
- System libraries (read-only)

❌ **Cannot access:**
- Other user files
- System configuration
- Network interfaces directly
- Hardware devices

### Recommendations

1. **Don't mount sensitive directories**: Avoid adding custom mounts to `/etc`, `/root`, etc.
2. **Use API keys from environment**: Don't hardcode keys in config files
3. **Review task descriptions**: Malicious prompts could attempt to exfiltrate data
4. **Monitor resource usage**: Containers can be resource-intensive
5. **Update regularly**: Keep base image and dependencies updated

## Platform-Specific Notes

### macOS

- Docker Desktop required
- `/opt` from host is NOT mounted (preserves container's `/opt/mcp-venv`)
- File paths with spaces need proper escaping in mounts
- Performance impact from Docker Desktop VM layer

### Linux

- Native Docker engine recommended
- Host MCP servers are mounted directly (better performance)
- Seamless user ID mapping
- `/opt` from host IS mounted if it exists

### Windows (Untested)

- Should work similar to macOS (uses container MCP servers)
- Docker Desktop or WSL2 with Docker required
- Path translation may need adjustments
- Not officially tested yet

## References

- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Claude Code Documentation](https://docs.anthropic.com/claude/docs/claude-code)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Container Best Practices](https://docs.docker.com/develop/dev-best-practices/)
