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

1. **Working Directory**: Current directory → `/work` (read-write)
   - Tasks execute here and can create/modify files
   - Changes persist on the host

2. **Claude Config**: `~/.claude` → `/home/executor/.claude` (read-write)
   - Shares authentication and MCP server configurations
   - Requires write access for Claude Code debug logs

3. **User Mapping**: Container runs as your UID:GID
   - Files created in containers have correct host permissions
   - No root-owned files in your working directory

## How It Works

### Native Execution (Default)

```bash
# NightShift calls subprocess directly
claude -p "task" --output-format stream-json --allowed-tools Read Write
```

### Containerized Execution

```bash
# NightShift wraps in docker run
docker run --rm \
  -u 1000:1000 \
  -v /path/to/project:/work \
  -v ~/.claude:/home/executor/.claude \
  -w /work \
  -e ANTHROPIC_API_KEY \
  nightshift-claude-executor:latest \
  -p "task" --output-format stream-json --allowed-tools Read Write
```

The output streaming and parsing works identically in both modes.

## Security Considerations

### What's Protected

- ✅ Host filesystem (except working directory and ~/.claude)
- ✅ Other running processes
- ✅ Network namespaces (isolated by default)
- ✅ System resources (can add CPU/memory limits)

### What's Shared

- ⚠️ Working directory (read-write access required for tasks)
- ⚠️ Claude config and MCP settings (read-write for debug logs)
- ⚠️ Network access (needed for MCP tools like OpenAI, Gemini, etc.)
- ⚠️ API keys (passed as environment variables)

### Best Practices

1. **Review tasks before approval**: Even in containers, tasks can modify your working directory
2. **Use separate project directories**: Don't run tasks in sensitive directories
3. **Audit MCP configurations**: Containers use your ~/.claude/settings.json
4. **Rotate API keys regularly**: Keys are passed to containers as env vars
5. **Monitor resource usage**: Add limits if running untrusted workloads

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
