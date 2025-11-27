# NightShift Authentication Setup

**Related Issue**: [#25 - Investigate Claude CLI authentication method for headless execution](https://github.com/james-alvey-42/nightshift/issues/25)

## Quick Setup

NightShift uses Claude Pro account authentication via OAuth tokens. One-time setup:

### 1. Generate OAuth Token

```bash
claude setup-token
```

This command will output a long-lived authentication token (starts with `sk-ant-oat01-`).

### 2. Add to Shell Profile

Add the token to your `~/.zshrc` or `~/.bashrc`:

```bash
# Claude Pro authentication for NightShift
export CLAUDE_CODE_OAUTH_TOKEN="sk-ant-oat01-your-token-here"
```

### 3. Reload Shell

```bash
source ~/.zshrc  # or source ~/.bashrc
```

### 4. Verify

```bash
# Check token is set
echo ${CLAUDE_CODE_OAUTH_TOKEN:0:20}

# Test Claude CLI
claude -p "test" --output-format json

# Test NightShift
nightshift submit "Say hello" --auto-approve --sync
```

## How It Works

NightShift automatically:
1. Removes `ANTHROPIC_API_KEY` from subprocess environment (if present)
2. Uses `CLAUDE_CODE_OAUTH_TOKEN` for Claude Pro authentication
3. Logs which authentication method is active

**Tasks are billed to your Claude Pro subscription, not API account.**

## Log Messages

When running tasks, you should see:

```
[INFO] Using CLAUDE_CODE_OAUTH_TOKEN for Claude Pro authentication
```

If token is missing:

```
[WARNING] CLAUDE_CODE_OAUTH_TOKEN not found in environment. Run 'claude setup-token' and add to shell profile.
```

## Troubleshooting

### Token not found after adding to shell profile

**Solution**: Restart your terminal or run `source ~/.zshrc`

### Authentication failed errors

**Solution**: Re-run `claude setup-token` to generate a new token, then update your shell profile.

### Using API key instead of OAuth token

**Solution**: NightShift explicitly removes `ANTHROPIC_API_KEY`. Even if you have it set for other tools, NightShift will use OAuth token instead.

## Background Services

For background services (systemd, launchd, docker), ensure `CLAUDE_CODE_OAUTH_TOKEN` is set in the service environment:

**macOS LaunchAgent**:
```xml
<key>EnvironmentVariables</key>
<dict>
    <key>CLAUDE_CODE_OAUTH_TOKEN</key>
    <string>your-token-here</string>
</dict>
```

**Linux systemd**:
```ini
[Service]
Environment="CLAUDE_CODE_OAUTH_TOKEN=your-token-here"
```

**Docker**:
```yaml
environment:
  - CLAUDE_CODE_OAUTH_TOKEN=${CLAUDE_CODE_OAUTH_TOKEN}
```

## Security

- Never commit OAuth tokens to git
- Use restrictive permissions on shell profiles: `chmod 600 ~/.zshrc`
- Rotate tokens periodically by re-running `claude setup-token`

## Implementation

- `nightshift/core/agent_manager.py:95-107` - Task execution authentication
- `nightshift/core/task_planner.py:149-157` - Planning authentication
- `nightshift/core/task_planner.py:310-314` - Refinement authentication

---

**Status**: ✅ Complete
**Last Updated**: 2025-11-27
