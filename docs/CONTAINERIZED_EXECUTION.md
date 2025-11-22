# Containerized Execution

NightShift supports running Claude Code tasks in isolated Docker containers for enhanced security and reproducibility.

## Overview

When containerized execution is enabled, NightShift continues to run natively on your host machine, but each Claude Code task execution happens in a fresh, isolated Docker container. This provides:

- **Isolation**: Task execution is sandboxed from your host system
- **Security**: Reduced attack surface for potentially malicious tasks
- **Resource Limits**: Ability to constrain CPU/memory usage per task
- **Reproducibility**: Consistent environment for every execution
- **Easy Rollback**: Can disable containerization at any time

## Architecture

```
Host (Native):
  ├── NightShift CLI
  ├── SQLite Database (~/.nightshift/)
  ├── Task Queue Management
  └── Docker Client

Container (Per Task):
  ├── Claude CLI
  ├── MCP Servers
  ├── Task Working Directory (mounted)
  └── Claude Config (mounted read-write)
```

## Setup

### 1. Build the Executor Image

```bash
# Build with your current user ID (recommended)
./scripts/build-executor.sh

# Or build with custom UID/GID
./scripts/build-executor.sh --uid 1000 --gid 1000

# Or build with custom image name
./scripts/build-executor.sh --image my-claude-executor:v1
```

The build script:
- Installs Node.js and Claude CLI
- Installs system dependencies for MCP tools (including Playwright)
- Creates a non-root user with matching UID for file permissions
- Tags the image as `nightshift-claude-executor:latest`

### 2. Verify the Build

```bash
# Check that the image exists
docker images | grep nightshift-claude-executor

# Test Claude CLI is installed
docker run --rm nightshift-claude-executor:latest --version
```

### 3. Enable Containerized Execution

```bash
# Enable for current session
export NIGHTSHIFT_USE_DOCKER=true

# Or add to your shell profile (~/.bashrc, ~/.zshrc)
echo 'export NIGHTSHIFT_USE_DOCKER=true' >> ~/.bashrc

# Optional: Specify custom image
export NIGHTSHIFT_DOCKER_IMAGE=my-claude-executor:v1
```

## Platform Compatibility

**Containerized execution is currently Linux-only.**

The implementation relies on Linux-specific features:

- **Filesystem layout**: Assumes `/usr`, `/lib`, `/lib64` structure (Debian/Ubuntu/Arch)
- **User mapping**: Uses `os.getuid()` and `os.getgid()` for UID/GID mapping
- **MCP discovery**: Expects Linux/Unix file paths and symlink behavior

**macOS limitations**:
- `/usr`, `/lib` paths are different and more restricted
- Docker Desktop runs in a VM with different mount semantics
- User ID mapping works differently

**Windows limitations**:
- Path separators and drive letters incompatible with mount logic
- UID/GID concepts don't apply to Windows users
- WSL2 may work but is untested

If you need containerized execution on macOS or Windows, consider:
1. Using WSL2 on Windows (may work with modifications)
2. Using Docker Desktop but expect MCP tool issues
3. Contributing cross-platform support (PRs welcome!)

For now, **use native execution mode on non-Linux platforms**.

## Usage

Once enabled, NightShift automatically runs all task executions in containers:

```bash
# This will now run in a container
nightshift submit "Download arxiv paper and analyze" --auto-approve

# Docker mode is transparent - all commands work the same
nightshift queue
nightshift approve task_abc123
nightshift results task_abc123
```

### Checking Docker Status

NightShift will log when Docker mode is active:

```
[INFO] Docker mode enabled: nightshift-claude-executor:latest
[INFO] Executing in container...
```

If the image is missing, you'll see a warning:

```
[WARNING] Docker image 'nightshift-claude-executor:latest' not found.
Please build it with: ./scripts/build-executor.sh
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NIGHTSHIFT_USE_DOCKER` | `false` | Enable containerized execution |
| `NIGHTSHIFT_DOCKER_IMAGE` | `nightshift-claude-executor:latest` | Docker image to use |
| `ANTHROPIC_API_KEY` | - | Anthropic API key (passed to container) |
| `OPENAI_API_KEY` | - | OpenAI API key (passed to container) |
| `GEMINI_API_KEY` | - | Google Gemini API key (passed to container) |

### Volume Mounts

The Docker executor automatically mounts:

1. **System Directories** (read-only):
   - `/usr`, `/lib`, `/lib64` → Provides system interpreters (Python, Node.js) for MCP servers
   - Mounted read-only for security

2. **MCP Server Paths** (read-only, auto-discovered):
   - Python virtual environments (e.g., `~/.claude_venv`)
   - npm global directories
   - Discovered by parsing `claude mcp list` output
   - Mounted at the same paths to preserve shebang compatibility

3. **Working Directory** (read-write):
   - Current directory → `/work`
   - Tasks execute here and can create/modify files
   - Changes persist on the host

4. **Claude Config** (read-write):
   - `~/.claude` → MCP server state and debug logs
   - `~/.claude.json` → Temporary copy with normalized MCP paths
     - Original config is **not modified** (temporary file created per-execution)
     - MCP server commands resolved to absolute paths for container compatibility
     - Temp file cleaned up after execution

5. **Container Hardening**:
   - Root filesystem mounted read-only (`--read-only`)
   - Temporary files in `/tmp` via tmpfs mount
   - Container runs as your UID:GID (not root)
   - Files created have correct host permissions

## How It Works

### Native Execution (Default)

```bash
# NightShift calls subprocess directly
claude -p "task" --output-format stream-json --allowed-tools Read Write
```

### Containerized Execution

```bash
# NightShift wraps in docker run with security hardening
docker run --rm --read-only \
  --tmpfs /tmp \
  -u 1000:1000 \
  -v /usr:/usr:ro \
  -v /lib:/lib:ro \
  -v /lib64:/lib64:ro \
  -v ~/.claude_venv:~/.claude_venv:ro \
  -v ~/.claude:~/.claude \
  -v ~/.claude.nightshift.XXXXX.json:~/.claude.json \
  -v /path/to/project:/work \
  -w /work \
  -e HOME=/home/user \
  -e PATH=~/.claude_venv/bin:/usr/local/bin:/usr/bin:/bin \
  -e ANTHROPIC_API_KEY \
  nightshift-claude-executor:latest \
  -p "task" --output-format stream-json --allowed-tools Read Write
```

Key differences from native execution:

- **Isolation**: System dirs and MCP paths mounted read-only
- **Hardening**: Container root filesystem read-only, `/tmp` on tmpfs
- **MCP compatibility**: Absolute paths used, venvs mounted at same locations
- **Config safety**: Temporary `.claude.json` created, original untouched

The output streaming and parsing works identically in both modes.

## Security Considerations

### Threat Model

NightShift's containerized execution is designed to protect against:

- **Accidental file access**: Prevent Claude from reading/writing user files outside the working directory
- **Filesystem damage**: Isolate tasks from modifying system or personal files
- **Resource exhaustion**: Container can be limited to prevent DoS on host

It is **NOT** designed to protect against:

- **Malicious code execution**: Tasks can still execute arbitrary code within the container
- **Data exfiltration**: Containers have full network access (required for MCP tools)
- **API key theft**: Any MCP server or task can read API keys from environment variables

### What's Protected

- ✅ **User home directory**: Not mounted (except `~/.claude` config)
- ✅ **Other projects**: Only current working directory is accessible
- ✅ **Container root filesystem**: Mounted read-only to prevent tampering
- ✅ **System files**: `/usr`, `/lib`, `/lib64` mounted read-only
- ✅ **MCP server code**: Virtual environments mounted read-only

### What's Shared

- ⚠️ **Working directory**: Mounted read-write (tasks need to create output files)
- ⚠️ **Claude config** (`~/.claude`): Mounted read-write (Claude needs to write debug logs)
- ⚠️ **MCP configuration** (`~/.claude.json`): Mounted read-write (Claude updates MCP server state)
- ⚠️ **System directories**: `/usr`, `/lib`, `/lib64` mounted read-only for interpreter compatibility
- ⚠️ **MCP server paths**: Auto-discovered virtual environments mounted read-only
- ⚠️ **Network access**: Full outbound connectivity (required for MCP APIs)
- ⚠️ **API keys**: Passed as environment variables (visible to any code running in container)

### MCP Server Trust Model

**Important**: Any MCP server configured in `~/.claude.json` is effectively trusted with:

1. **API keys**: All keys passed to container are readable by MCP servers
2. **Working directory data**: MCP servers can read any files Claude accesses
3. **Network access**: MCP servers can make arbitrary network requests

**Recommendation**: Only configure MCP servers from trusted sources. Treat MCP servers as part of your "tooling infrastructure" with the same trust level as your Python packages or npm modules.

### System Directory Mounts

The container mounts `/usr`, `/lib`, and `/lib64` from the host as **read-only** to support MCP servers that depend on system interpreters (Python, Node.js). This is safe because:

- These directories contain system software, not user data
- They are mounted read-only (cannot be modified)
- Sensitive data should be in `$HOME`, not system directories

If you have sensitive data in `/usr/local` or `/opt`, be aware these may be mounted if MCP servers are installed there.

### API Key Security

API keys are passed to containers via environment variables and are:

- **Visible to all processes** in the container
- **Readable by any MCP server** you have configured
- **Not encrypted** or otherwise protected within the container

**Best practices**:

1. Use dedicated API keys for NightShift (not shared with other applications)
2. Rotate keys regularly
3. Review MCP server code before adding new servers
4. Monitor API usage for unexpected activity

### Network Access

Containers have **full outbound network access** because MCP tools need to call external APIs (OpenAI, Gemini, email, etc.). This means:

- Tasks can exfiltrate any data they access
- Tasks can make arbitrary HTTP requests
- Tasks can download and execute code from the internet

For additional security, you can add network restrictions by modifying `docker_executor.py`:

```python
# Disable network entirely (breaks most MCP tools)
cmd.extend(["--network", "none"])

# Or use a custom network with firewall rules
cmd.extend(["--network", "nightshift-restricted"])
```

### Best Practices

1. **Review tasks before approval**: Understand what a task will do before executing it
2. **Use separate project directories**: Don't run tasks in directories with sensitive data
3. **Audit MCP configurations**: Review what servers are installed and what they do
4. **Rotate API keys regularly**: Treat keys as compromised if exposed to untrusted tasks
5. **Monitor resource usage**: Add CPU/memory limits for production deployments
6. **Keep working directories clean**: Don't leave sensitive files in task working directories

## Adding Resource Limits

You can modify `docker_executor.py` to add resource constraints:

```python
# In DockerExecutor.build_docker_command():
cmd.extend(["--cpus", "2.0"])  # Limit to 2 CPUs
cmd.extend(["--memory", "4g"])  # Limit to 4GB RAM
cmd.extend(["--pids-limit", "1000"])  # Limit processes
```

## Troubleshooting

### Issue: "Docker image not found"

**Solution**: Build the image first

```bash
./scripts/build-executor.sh
```

### Issue: Permission denied on created files

**Solution**: Rebuild image with matching UID

```bash
./scripts/build-executor.sh --uid $(id -u) --gid $(id -g)
```

### Issue: MCP tools not working in container

**Possible causes**:
1. **Network access**: Ensure container has outbound network access
2. **API keys**: Check that env vars are exported and passed to container
3. **Claude config**: Verify `~/.claude/settings.json` exists and is mounted

**Debug steps**:

```bash
# Test network access
docker run --rm nightshift-claude-executor:latest /bin/bash -c "curl -I https://api.anthropic.com"

# Check mounted config
docker run --rm -v ~/.claude:/home/executor/.claude:ro nightshift-claude-executor:latest \
  ls -la /home/executor/.claude

# Verify env vars are passed
docker run --rm -e ANTHROPIC_API_KEY nightshift-claude-executor:latest env | grep ANTHROPIC
```

### Issue: Playwright tools failing

**Solution**: Playwright requires additional system dependencies. These are included in the Dockerfile, but if you customize the image, ensure these packages are installed:

```
libnss3, libatk1.0-0, libatk-bridge2.0-0, libcups2, libdrm2,
libxkbcommon0, libxcomposite1, libxdamage1, libxfixes3, libxrandr2,
libgbm1, libpango-1.0-0, libcairo2, libasound2, fonts-liberation
```

### Issue: Slow container startup

**Causes**: Docker image pull/load time

**Solutions**:
- Keep image minimal (avoid unnecessary dependencies)
- Use multi-stage builds to reduce final image size
- Consider image caching strategies for frequent use

## Disabling Containerized Execution

To return to native execution:

```bash
# Disable for current session
export NIGHTSHIFT_USE_DOCKER=false

# Or unset the variable
unset NIGHTSHIFT_USE_DOCKER

# Remove from shell profile if added
# Edit ~/.bashrc or ~/.zshrc and remove the export line
```

## Advanced: Custom Docker Images

You can create custom executor images for specific needs:

```dockerfile
# my-custom-executor/Dockerfile
FROM nightshift-claude-executor:latest

# Install additional tools
RUN apt-get update && apt-get install -y \
    python3-pip \
    && pip3 install numpy pandas

# Custom MCP server setup
# ...
```

Build and use:

```bash
docker build -t my-custom-executor:latest -f my-custom-executor/Dockerfile .
export NIGHTSHIFT_DOCKER_IMAGE=my-custom-executor:latest
```

## Future Enhancements

Potential improvements for containerized execution:

- [ ] Container reuse (persistent containers for multiple tasks)
- [ ] GPU passthrough for ML tasks
- [ ] Network isolation modes (no internet, allowlist, etc.)
- [ ] Automatic resource limit detection
- [ ] Container health checks
- [ ] Multi-architecture support (ARM, AMD64)
- [ ] Kubernetes executor (for cluster deployments)
