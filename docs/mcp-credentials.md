# MCP Tool Credentials Configuration

Guide for configuring credentials for MCP tools that require authentication (Google Calendar, GitHub, etc.).

## Overview

Some MCP tools require authentication credentials (OAuth tokens, API keys, etc.). When using Docker execution, these credentials need to be mounted into the container.

NightShift automatically mounts common credential files if they exist, and you can customize the paths using environment variables.

## Automatic Credential Mounting

### Google Calendar

**Default paths:**
- Credentials: `~/.google_calendar_credentials.json` (read-only)
- Token: `~/.google_calendar_token.json` (read-write for token refresh)

**Setup:**

1. **Get OAuth credentials from Google Cloud Console:**
   ```bash
   # 1. Go to: https://console.cloud.google.com/
   # 2. Create a project (or select existing)
   # 3. Enable Google Calendar API
   # 4. Create OAuth 2.0 Client ID (Desktop app)
   # 5. Download credentials JSON
   ```

2. **Save credentials file:**
   ```bash
   # Place the downloaded file as:
   cp ~/Downloads/client_secret_*.json ~/.google_calendar_credentials.json
   ```

3. **Run initial authentication (outside Docker):**
   ```bash
   # This will open a browser for OAuth flow
   mcp-google-calendar

   # Follow the prompts to authenticate
   # This creates ~/.google_calendar_token.json
   ```

4. **Verify files exist:**
   ```bash
   ls -la ~/.google_calendar_credentials.json
   ls -la ~/.google_calendar_token.json
   ```

5. **Use with NightShift:**
   ```bash
   export NIGHTSHIFT_USE_DOCKER=true
   nightshift submit "Add an event to my calendar for tomorrow at 2pm titled 'Team meeting'" --auto-approve
   ```

**Custom paths:**

If your credentials are in different locations:

```bash
export GOOGLE_CALENDAR_CREDENTIALS_PATH="/custom/path/to/credentials.json"
export GOOGLE_CALENDAR_TOKEN_PATH="/custom/path/to/token.json"

nightshift submit "calendar task" --auto-approve
```

## Adding Support for Other MCP Tools

### Manual Mount via additional_mounts

For MCP tools that aren't automatically supported, you can mount credentials manually:

```python
from nightshift.core.docker_executor import DockerExecutor

executor = DockerExecutor()

# Mount GitHub token
additional_mounts = [
    {
        "host_path": "/Users/you/.github_token",
        "container_path": "/Users/you/.github_token",
        "mode": "ro"
    }
]

cmd = executor.build_docker_command(
    claude_args=['-p', 'your prompt'],
    additional_mounts=additional_mounts
)
```

### Adding Auto-Mount Support

To add automatic mounting for other tools, edit `docker_executor.py`:

```python
# Around line 259, after Google Calendar mounts

# Auto-mount GitHub credentials if they exist
github_token_path = os.environ.get(
    "GITHUB_TOKEN_PATH",
    str(Path.home() / ".github_token"),
)

if Path(github_token_path).exists():
    cmd.extend(["-v", f"{github_token_path}:{github_token_path}:ro"])
    logger.debug(f"Mounting GitHub token: {github_token_path}")
```

## Environment Variables Reference

### Supported Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `GOOGLE_CALENDAR_CREDENTIALS_PATH` | `~/.google_calendar_credentials.json` | OAuth client credentials |
| `GOOGLE_CALENDAR_TOKEN_PATH` | `~/.google_calendar_token.json` | OAuth access/refresh token |

### Future Support (Planned)

| Variable | Default | Purpose |
|----------|---------|---------|
| `GITHUB_TOKEN_PATH` | `~/.github_token` | GitHub personal access token |
| `AWS_CREDENTIALS_PATH` | `~/.aws/credentials` | AWS credentials |
| `GCP_CREDENTIALS_PATH` | `~/.config/gcloud/application_default_credentials.json` | GCP credentials |

## Security Considerations

### Read-Only vs Read-Write Mounts

- **Credentials files** (client secrets): Mounted **read-only** (`ro`)
  - These don't need to change
  - Read-only provides extra security

- **Token files** (OAuth tokens): Mounted **read-write** (`rw`)
  - Tokens need to be refreshed when they expire
  - MCP tools need write access to update them

### File Permissions

Ensure your credential files have restrictive permissions:

```bash
# Credentials should only be readable by you
chmod 600 ~/.google_calendar_credentials.json
chmod 600 ~/.google_calendar_token.json

# Verify permissions
ls -la ~/.google_calendar_*.json
# Should show: -rw------- (600)
```

### Credential Exposure

**What's mounted:**
- Only specific credential files you configure
- Not your entire home directory

**What's NOT mounted:**
- Other files in your home directory
- Browser passwords/cookies
- SSH keys (unless you explicitly add them)

## Troubleshooting

### "Credentials not found" error in container

**Problem:** MCP tool can't find credentials in container

**Check:**

1. **Files exist on host:**
   ```bash
   ls -la ~/.google_calendar_credentials.json
   ls -la ~/.google_calendar_token.json
   ```

2. **Files are mounted in container:**
   ```bash
   # Start interactive session
   docker run -it --rm \
     -v ~/.google_calendar_credentials.json:~/.google_calendar_credentials.json:ro \
     -v ~/.google_calendar_token.json:~/.google_calendar_token.json \
     --entrypoint /bin/bash \
     nightshift-claude-executor:latest

   # Inside container
   ls -la ~/.google_calendar_credentials.json
   ```

3. **Check environment variables:**
   ```bash
   echo $GOOGLE_CALENDAR_CREDENTIALS_PATH
   echo $GOOGLE_CALENDAR_TOKEN_PATH
   ```

### "Permission denied" when accessing credentials

**Problem:** Container can't read credential files

**Solution:**

```bash
# Make files readable by your user
chmod 600 ~/.google_calendar_credentials.json
chmod 600 ~/.google_calendar_token.json

# Verify ownership
ls -la ~/.google_calendar_*.json
# Should show your username
```

### "Token expired" error

**Problem:** OAuth token needs refresh

**Solution:**

1. **Token should auto-refresh:** The token file is mounted read-write, so MCP tools should automatically refresh expired tokens.

2. **If auto-refresh fails, re-authenticate:**
   ```bash
   # Delete old token
   rm ~/.google_calendar_token.json

   # Re-run authentication (outside Docker)
   mcp-google-calendar
   # Follow OAuth flow in browser

   # Try NightShift again
   nightshift submit "calendar task" --auto-approve
   ```

### Custom paths not working

**Problem:** Set `GOOGLE_CALENDAR_CREDENTIALS_PATH` but still not found

**Solution:**

```bash
# Export BEFORE running nightshift
export GOOGLE_CALENDAR_CREDENTIALS_PATH="/custom/path.json"
export GOOGLE_CALENDAR_TOKEN_PATH="/custom/token.json"

# Verify they're set
echo $GOOGLE_CALENDAR_CREDENTIALS_PATH

# Then run nightshift
nightshift submit "task" --auto-approve
```

## Testing Credentials

### Test Without Docker

First verify credentials work outside of Docker:

```bash
# Test MCP server directly
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | mcp-google-calendar

# Should return server info without errors
```

### Test With Docker

Test credentials work inside container:

```bash
# Start interactive session with mounts
cd ~/nightshift-handley
python3 << 'EOF'
from nightshift.core.docker_executor import DockerExecutor
executor = DockerExecutor()
cmd = executor.build_docker_command(claude_args=['--version'])
image_idx = cmd.index('nightshift-claude-executor:latest')
interactive = cmd[:2] + ['-it'] + cmd[2:image_idx] + ['--entrypoint', '/bin/bash', cmd[image_idx]]
print(' \\\n  '.join(interactive))
EOF

# Copy the output and run it
# Inside container, test:
ls -la ~/.google_calendar_credentials.json  # Should exist
cat ~/.google_calendar_credentials.json     # Should show OAuth client info
echo '{"jsonrpc":"2.0","id":1,"method":"initialize"...}' | mcp-google-calendar
```

### Test with NightShift

Run a simple calendar task:

```bash
export NIGHTSHIFT_USE_DOCKER=true
nightshift submit "List my calendar events for today" --auto-approve

# Check results
nightshift queue
nightshift results task_XXXXXXXX --show-output
```

## Best Practices

1. **Keep credentials in home directory:** Use the default paths unless you have a specific reason not to
2. **Never commit credentials:** Add `*_credentials.json` and `*_token.json` to `.gitignore`
3. **Use environment variables for paths:** Makes it easier to change locations without code changes
4. **Test outside Docker first:** Easier to debug authentication issues
5. **Restrict file permissions:** Always `chmod 600` your credential files
6. **Rotate credentials regularly:** Especially for long-lived tokens
7. **Use service accounts when possible:** For production use, prefer service accounts over user OAuth

## Adding New MCP Tools with Credentials

When adding support for a new MCP tool that requires credentials:

1. **Document the credential setup** in this file
2. **Add auto-mount support** in `docker_executor.py` if it's commonly used
3. **Use environment variables** for path customization
4. **Mount credentials read-only** unless they need to be updated
5. **Test in container** before committing

Example template for new tools:

```python
# In docker_executor.py, around line 280

# Auto-mount [TOOL_NAME] credentials if they exist
tool_creds_path = os.environ.get(
    "[TOOL_NAME]_CREDENTIALS_PATH",
    str(Path.home() / ".[tool_name]_credentials.json"),
)

if Path(tool_creds_path).exists():
    cmd.extend(["-v", f"{tool_creds_path}:{tool_creds_path}:ro"])
    logger.debug(f"Mounting [TOOL_NAME] credentials: {tool_creds_path}")
```
