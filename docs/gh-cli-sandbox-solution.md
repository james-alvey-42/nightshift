# GitHub CLI (gh) Sandbox Solution

## Problem Statement

The GitHub CLI (`gh`) was failing with authentication errors when run inside NightShift's macOS sandbox, even though authentication worked perfectly outside the sandbox.

**Error observed:**
```
github.com
  X Failed to log in to github.com account james-alvey-42 (default)
  - Active account: true
  - The token in default is invalid.
```

## Root Cause Analysis

### 1. Keychain Storage Issue
- Outside sandbox: `gh auth status` showed "Logged in (keyring)" - tokens stored in macOS Keychain
- Inside sandbox: macOS sandbox blocks access to Keychain API, even with authorization permissions
- The gh CLI could not retrieve tokens from Keychain within the sandbox

### 2. Insufficient Sandbox Permissions
Initial sandbox profile was missing critical network and system services needed for gh to:
- Perform SSL/TLS certificate validation
- Resolve DNS
- Establish HTTPS connections to GitHub API
- Communicate with system services

## Solution

### Part 1: Environment Variable Authentication

Instead of relying on Keychain access, use the `GH_TOKEN` environment variable which gh CLI checks before Keychain:

```python
# In agent_manager.py execute_task()
if task.needs_git:
    # Get token from gh CLI (runs outside sandbox)
    token_result = subprocess.run(
        ["gh", "auth", "token"],
        capture_output=True,
        text=True,
        timeout=5
    )
    if token_result.returncode == 0:
        env['GH_TOKEN'] = token_result.stdout.strip()

# Pass environment to subprocess
result = subprocess.run(cmd, shell=True, env=env, ...)
```

### Part 2: Enhanced Sandbox Profile

Updated the sandbox profile to include all necessary permissions for gh operations:

```scheme
;; Allow comprehensive process execution
(allow process*)

;; Allow network operations
(allow network*)
(allow network-outbound (remote tcp))  ;; For HTTPS/SSH
(allow system-socket)

;; Allow critical system services for gh CLI
(allow mach-lookup (global-name "com.apple.SecurityServer"))  ;; SSL/TLS validation
(allow mach-lookup (global-name "com.apple.dnssd.service"))   ;; DNS resolution
(allow mach-lookup (global-name "com.apple.trustd"))          ;; Certificate trust
(allow mach-lookup (global-name "com.apple.nsurlsessiond"))   ;; Network sessions

;; Allow IPC operations
(allow mach-lookup)
(allow sysctl*)
(allow ipc-posix-shm)
(allow mach*)
(allow ipc-posix-shm-read* (ipc-posix-name "apple.shm.notification_center"))

;; Allow device file writes
(allow file-write* (literal "/dev/null"))
(allow file-write* (literal "/dev/stdout"))
(allow file-write* (literal "/dev/stderr"))
(allow file-write* (literal "/dev/dtracehelper"))
```

## Testing & Verification

### Test Command
```bash
# Outside sandbox - get token
gh auth token

# Inside sandbox - test with GH_TOKEN
export GH_TOKEN="$(gh auth token)"
sandbox-exec -f profile.sb env GH_TOKEN="$GH_TOKEN" gh repo list --limit 5
```

### Results
```
✅ Exit code: 0
✅ Successfully lists repositories
✅ No authentication errors
✅ Full HTTPS/SSH connectivity
```

## Key Insights

1. **Environment variables bypass Keychain**: gh CLI checks `GH_TOKEN` environment variable before attempting Keychain access

2. **Network services are critical**: gh requires multiple macOS system services for:
   - SSL/TLS certificate validation (`com.apple.SecurityServer`, `com.apple.trustd`)
   - DNS resolution (`com.apple.dnssd.service`)
   - Network session management (`com.apple.nsurlsessiond`)

3. **Process permissions need to be broad**: Using `(allow process*)` instead of individual `process-exec*`, `process-fork`, etc. provides better compatibility

4. **IPC shared memory matters**: The notification center IPC (`apple.shm.notification_center`) is required for gh to function properly

## Implementation Details

### When This Runs
The GH_TOKEN loading happens automatically when:
- Task has `needs_git=True` set by the task planner
- Task planner sets this flag for any task involving:
  - Direct git operations (commit, push, pull, etc.)
  - GitHub CLI (`gh`) commands
  - GitHub API interactions

### Error Handling
- If `gh auth token` fails, logs a warning but continues execution
- Task may fail if gh commands are used, but other operations proceed
- User can re-authenticate with `gh auth login` if needed

### Security Considerations
- GH_TOKEN is only passed to sandboxed processes, never logged
- Token is fetched fresh for each task execution
- Token remains in Keychain, not written to disk
- Sandbox still restricts filesystem writes to allowed directories

## Alternative Approaches Tried (Unsuccessful)

### 1. File-based Token Storage
Attempted to store token in `~/.config/gh/token.txt` and use file-based auth.
- **Failed**: gh CLI still complained about invalid Keychain auth even when GH_TOKEN worked

### 2. Keychain Access Permissions
Added various authorization and mach-lookup permissions for Keychain:
```scheme
(allow authorization-right-obtain)
(allow mach-lookup (global-name "com.apple.SecurityServer"))
(allow mach-lookup (global-name "com.apple.security.syspolicy"))
```
- **Failed**: macOS sandbox has very limited Keychain API support

### 3. Minimal Permissions
Tried to use only essential permissions to minimize attack surface.
- **Failed**: gh requires comprehensive network stack access to function

## Maintenance Notes

### If gh Breaks Again
1. Check if `gh auth status` works outside sandbox
2. Verify `gh auth token` returns a valid token
3. Test manually with: `sandbox-exec -f profile.sb env GH_TOKEN="token" gh repo list`
4. Check logs for "Loaded GH_TOKEN from gh CLI" message
5. Verify sandbox profile includes all required mach services

### Adding Support for Other CLIs
This pattern can be extended to other CLIs that support environment variable authentication:
- `GITHUB_TOKEN` for GitHub Actions
- `GITLAB_TOKEN` for GitLab CLI
- `BITBUCKET_TOKEN` for Bitbucket CLI

## References

- GitHub CLI Environment Variables: https://cli.github.com/manual/gh_help_environment
- macOS Sandbox Profile Format: `man sandbox-exec`
- Mach Services: `/System/Library/Frameworks/Security.framework/`

## Version History

- **2025-11-25**: Initial implementation with GH_TOKEN environment variable approach
- Successfully tested with `gh repo list`, `gh issue create`, `gh pr list`
