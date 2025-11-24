# NightShift Installation Guide

Complete installation guide for NightShift with Docker containerized execution support.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Installation](#detailed-installation)
  - [1. System Dependencies](#1-system-dependencies)
  - [2. Python Environment](#2-python-environment)
  - [3. NightShift Installation](#3-nightshift-installation)
  - [4. MCP Handley Lab Package](#4-mcp-handley-lab-package)
  - [5. Docker Setup (Optional)](#5-docker-setup-optional)
- [Configuration](#configuration)
- [Verification](#verification)
- [Platform-Specific Notes](#platform-specific-notes)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required

- **Python 3.10+**: For NightShift and MCP servers
- **Claude Code CLI**: The `claude` command-line tool
- **API Keys**: At minimum, `ANTHROPIC_API_KEY` for Claude

### Optional (for Docker execution)

- **Docker**: Docker Engine (Linux) or Docker Desktop (macOS/Windows)
- **Git**: For cloning repositories

## Quick Start

```bash
# 1. Clone the repository
git clone <nightshift-repo-url>
cd nightshift-handley

# 2. Install NightShift
pip install -e .

# 3. Set API key
export ANTHROPIC_API_KEY="your-key-here"

# 4. Run a simple task
nightshift submit "What is 2+2?" --auto-approve

# 5. (Optional) Enable Docker execution
export NIGHTSHIFT_USE_DOCKER=true
./scripts/build-executor.sh
nightshift submit "What is 2+2?" --auto-approve
```

## Detailed Installation

### 1. System Dependencies

#### macOS

```bash
# Install Homebrew (if not already installed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install Python 3.10+
brew install python@3.11

# Install Docker Desktop (for containerized execution)
brew install --cask docker
# Or download from: https://www.docker.com/products/docker-desktop/

# Start Docker Desktop
open -a Docker
```

#### Linux (Ubuntu/Debian)

```bash
# Update package list
sudo apt update

# Install Python 3.10+
sudo apt install python3.11 python3.11-venv python3-pip

# Install Docker Engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group (avoid needing sudo)
sudo usermod -aG docker $USER
# Log out and back in for group change to take effect

# Install Git
sudo apt install git
```

#### Windows

```bash
# Install Python 3.11+ from python.org or Microsoft Store

# Install Docker Desktop
# Download from: https://www.docker.com/products/docker-desktop/

# Install Git for Windows
# Download from: https://git-scm.com/download/win
```

### 2. Python Environment

It's recommended to use a virtual environment:

```bash
# Create a virtual environment
python3 -m venv nightshift-venv

# Activate it
# macOS/Linux:
source nightshift-venv/bin/activate
# Windows:
nightshift-venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip
```

### 3. NightShift Installation

```bash
# Clone the repository
git clone <nightshift-repo-url>
cd nightshift-handley

# Install in development mode
pip install -e .

# Verify installation
nightshift --version
```

### 4. MCP Handley Lab Package

NightShift uses the MCP Handley Lab package for MCP tool support. This is required for:
- LLM integrations (Gemini, OpenAI, Claude)
- Academic research (ArXiv)
- Productivity tools (Google Calendar)
- Code analysis (code2prompt)
- And more

#### Option A: Install from Local Directory

If you have the mcp-handley-lab package locally:

```bash
# Place mcp-handley-lab directory in the nightshift-handley root
cd nightshift-handley
# Copy or symlink mcp-handley-lab here

# Docker will automatically use it during build
./scripts/build-executor.sh
```

#### Option B: Install in Host Environment (Non-Docker)

For non-containerized execution, install MCP tools in your host environment:

```bash
# Install mcp-handley-lab package
pip install /path/to/mcp-handley-lab

# Or install from source
cd /path/to/mcp-handley-lab
pip install -e .

# Verify MCP tools are available
which mcp-gemini
which mcp-arxiv
```

#### Option C: Use Pre-built Docker Image (Future)

```bash
# Pull pre-built image (when available)
docker pull nightshift/claude-executor:latest

# No local mcp-handley-lab needed - included in image
```

### 5. Docker Setup (Optional)

Docker execution provides security isolation and reproducible environments.

#### Build the Docker Image

```bash
cd nightshift-handley

# Ensure mcp-handley-lab directory is present
ls mcp-handley-lab/  # Should show package contents

# Build the executor image
./scripts/build-executor.sh

# Verify the image
docker images | grep nightshift-claude-executor
```

**Build options:**

```bash
# Custom user/group ID
./scripts/build-executor.sh --uid 1001 --gid 1001

# Custom image name
./scripts/build-executor.sh --image my-executor:v1

# See all options
./scripts/build-executor.sh --help
```

#### Test the Docker Image

```bash
# Test basic functionality
docker run --rm nightshift-claude-executor:latest --version

# Test in interactive mode
docker run -it --rm \
  -e ANTHROPIC_API_KEY \
  --entrypoint /bin/bash \
  nightshift-claude-executor:latest

# Inside container, test MCP servers
which mcp-gemini
ls /opt/mcp-venv/bin/mcp-*
```

## Configuration

### API Keys

Set required API keys as environment variables:

```bash
# Required
export ANTHROPIC_API_KEY="sk-ant-..."

# Optional (for specific MCP tools)
export GEMINI_API_KEY="..."
export OPENAI_API_KEY="..."
export GOOGLE_API_KEY="..."

# Make permanent (add to ~/.bashrc or ~/.zshrc)
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc
```

### Claude Code Configuration

Ensure Claude Code is installed and configured:

```bash
# Install Claude Code (if not already)
npm install -g @anthropic-ai/claude-code

# Verify installation
claude --version

# Configure MCP servers (if using non-Docker execution)
claude mcp add gemini mcp-gemini
claude mcp add arxiv mcp-arxiv
claude mcp list  # Verify servers are configured
```

### Docker Execution Mode

Enable Docker execution by setting an environment variable:

```bash
# Enable Docker mode
export NIGHTSHIFT_USE_DOCKER=true

# Or set permanently
echo 'export NIGHTSHIFT_USE_DOCKER=true' >> ~/.bashrc

# Disable Docker mode
unset NIGHTSHIFT_USE_DOCKER
```

### NightShift Data Directory

By default, NightShift stores data in `~/.nightshift/`:

```
~/.nightshift/
├── database/
│   └── nightshift.db          # Task queue database
├── logs/
│   └── nightshift_YYYYMMDD.log  # Daily logs
├── output/
│   ├── task_XXX_output.json   # Task results
│   └── task_XXX_files.json    # File tracking
└── notifications/
    └── task_XXX_notification.json  # Completion summaries
```

To change the data directory:

```bash
# Set custom directory (not currently supported, coming soon)
export NIGHTSHIFT_DATA_DIR="/custom/path"
```

## Verification

### Verify Installation

```bash
# Check NightShift is installed
nightshift --version

# Check Python environment
python3 --version
which python3

# Check Claude Code
claude --version

# Check Docker (if using containerized execution)
docker --version
docker ps

# Check MCP servers (non-Docker)
which mcp-gemini
mcp-gemini --help  # May not show help but shouldn't error
```

### Run Test Tasks

```bash
# Simple test (non-Docker)
nightshift submit "What is the capital of France?" --auto-approve

# Check task status
nightshift queue

# View results
nightshift results task_XXXXXXXX --show-output

# Test with Docker
export NIGHTSHIFT_USE_DOCKER=true
nightshift submit "What is 2+2?" --auto-approve
```

### Verify MCP Tools

```bash
# Test MCP server directly (non-Docker)
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | mcp-gemini

# Should return JSON with server info
```

## Platform-Specific Notes

### macOS

**Docker Desktop:**
- Start Docker Desktop before running containerized tasks
- Grant necessary permissions when prompted
- File paths with spaces work automatically

**Homebrew:**
- MCP servers installed via Homebrew will be at `/opt/homebrew/bin/`
- Docker executor skips mounting `/opt` on macOS to preserve container's MCP venv

**Performance:**
- Docker Desktop uses a VM, adding some overhead
- Non-Docker execution is faster for simple tasks

### Linux

**Docker Permissions:**
- Add your user to the `docker` group to avoid needing `sudo`
- Log out and back in after group change

**MCP Server Mounting:**
- Docker executor mounts host MCP servers directly (better performance)
- Ensure MCP servers are installed in standard locations

**System Libraries:**
- Docker executor mounts `/lib`, `/lib64`, `/opt` from host

### Windows (Experimental)

**Docker Desktop:**
- Requires WSL2 backend
- Enable WSL2 integration in Docker Desktop settings

**Path Handling:**
- Windows paths may need translation
- Use WSL2 for best compatibility

**Status:**
- Not officially tested yet
- Should work similar to macOS

## Troubleshooting

### Common Issues

#### "docker: command not found"

**Problem:** Docker is not installed or not in PATH

**Solution:**
```bash
# Verify Docker installation
which docker

# Install Docker (see System Dependencies section)

# Start Docker Desktop (macOS/Windows)
open -a Docker  # macOS
# Or launch from Start Menu (Windows)
```

#### "Cannot connect to Docker daemon"

**Problem:** Docker daemon is not running

**Solution:**
```bash
# Start Docker Desktop (macOS/Windows)
# Or start Docker service (Linux)
sudo systemctl start docker

# Verify
docker ps
```

#### "Permission denied" when building Docker image

**Problem:** User not in docker group (Linux)

**Solution:**
```bash
# Add user to docker group
sudo usermod -aG docker $USER

# Log out and back in
exit
# Log back in

# Verify
docker ps  # Should work without sudo
```

#### "nightshift: command not found"

**Problem:** NightShift not installed or not in PATH

**Solution:**
```bash
# Ensure virtual environment is activated
source nightshift-venv/bin/activate

# Install NightShift
cd nightshift-handley
pip install -e .

# Verify
which nightshift
nightshift --version
```

#### "ANTHROPIC_API_KEY not found"

**Problem:** API key not set

**Solution:**
```bash
# Set the API key
export ANTHROPIC_API_KEY="sk-ant-..."

# Verify
echo $ANTHROPIC_API_KEY

# Make permanent
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc
source ~/.bashrc
```

#### "MCP servers not found in container"

**Problem:** `/opt` is being mounted from host, overwriting container's `/opt/mcp-venv`

**Solution:**
```bash
# Verify docker_executor.py is using correct logic
# On macOS, /opt should NOT be in mounted volumes

# Test in interactive container
docker run -it --rm \
  --entrypoint /bin/bash \
  nightshift-claude-executor:latest

# Inside container
ls /opt/mcp-venv/bin/  # Should show MCP executables
```

#### "mcp-handley-lab not found during Docker build"

**Problem:** mcp-handley-lab directory not present in nightshift-handley root

**Solution:**
```bash
# Ensure mcp-handley-lab is in the right location
cd nightshift-handley
ls mcp-handley-lab/  # Should exist

# If missing, copy or symlink it
cp -r /path/to/mcp-handley-lab .
# Or
ln -s /path/to/mcp-handley-lab .

# Rebuild
./scripts/build-executor.sh
```

### Getting Help

If you encounter issues not covered here:

1. **Check logs:**
   ```bash
   # NightShift logs
   tail -f ~/.nightshift/logs/nightshift_$(date +%Y%m%d).log

   # Docker logs (if using containers)
   docker logs <container-id>
   ```

2. **Enable debug mode:**
   ```bash
   # Set log level
   export NIGHTSHIFT_LOG_LEVEL=DEBUG

   # Run task
   nightshift submit "test task" --auto-approve
   ```

3. **Check configuration:**
   ```bash
   # Verify API keys
   env | grep API_KEY

   # Check Claude config
   cat ~/.claude.json

   # Check Docker setup
   docker info
   ```

4. **Test components individually:**
   ```bash
   # Test Claude CLI
   claude -p "test" --max-tokens 10

   # Test MCP server
   echo '{"jsonrpc":"2.0","id":1,"method":"initialize",...}' | mcp-gemini

   # Test Docker image
   docker run --rm nightshift-claude-executor:latest --version
   ```

5. **Open an issue:** If the problem persists, open an issue on GitHub with:
   - System information (`uname -a`, `docker --version`, `python --version`)
   - Error messages and logs
   - Steps to reproduce

## Next Steps

After successful installation:

1. **Read the documentation:**
   - [Docker Execution Guide](./docker-execution.md)
   - [AGENTS.md](../AGENTS.md) - Understanding the agent architecture
   - [README.md](../README.md) - Project overview

2. **Try example tasks:**
   ```bash
   # Simple query
   nightshift submit "What is the capital of France?" --auto-approve

   # Use ArXiv MCP tool
   nightshift submit "Search ArXiv for papers about transformers from 2023" --auto-approve

   # File analysis
   nightshift submit "Analyze the Python files in this directory and summarize the codebase" --auto-approve
   ```

3. **Configure MCP tools:**
   - Set up Google Calendar OAuth (if needed)
   - Add additional API keys for other services
   - Explore available MCP tools: `claude mcp list`

4. **Set up workflows:**
   - Create aliases for common tasks
   - Set up scheduled tasks
   - Integrate with CI/CD pipelines

5. **Join the community:**
   - Report bugs and request features
   - Share your use cases
   - Contribute improvements
