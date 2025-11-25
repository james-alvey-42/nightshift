# Testing NightShift Slack Integration

**Created:** November 25, 2024
**Status:** Phase 1 - Ready for Testing
**Estimated Time:** 30-45 minutes

---

## Prerequisites Checklist

Before starting, ensure you have:

- [x] Slack workspace (created)
- [x] Slack app created with bot token and signing secret (done)
- [x] NightShift installed with Slack dependencies (`pip install -e .`)
- [x] Slack credentials configured (`nightshift slack-config` shows enabled)
- [ ] ngrok installed (we'll install this now)
- [ ] Terminal window ready

---

## Part 1: Install ngrok (5 minutes)

ngrok exposes your local server to the internet so Slack can send webhooks to it.

### Option A: Install via Homebrew (recommended on macOS)

```bash
brew install ngrok
```

### Option B: Download from ngrok.com

1. Go to https://ngrok.com/download
2. Download for macOS
3. Unzip and move to `/usr/local/bin/ngrok`

### Verify Installation

```bash
ngrok version
```

Should show: `ngrok version 3.x.x`

---

## Part 2: Start the NightShift Webhook Server (2 minutes)

### Open Terminal Window #1

```bash
cd /Users/james/Dropbox/JimDex/60-69\ Library/60\ Packages/60.20\ nightshift/nightshift
nightshift slack-server
```

### Expected Output:

```
Starting Slack webhook server...

Testing Slack connection...
✓ Connected to Slack

✓ Server starting on 0.0.0.0:5000

Webhook endpoints:
  • POST http://0.0.0.0:5000/slack/commands
  • POST http://0.0.0.0:5000/slack/interactions
  • GET  http://0.0.0.0:5000/health

Press Ctrl+C to stop the server
```

### Troubleshooting:

**Error: "Slack integration not configured"**
- Run: `nightshift slack-config`
- If not enabled, run: `nightshift slack-setup` again

**Error: "Failed to connect to Slack API"**
- Check your bot token is correct
- Verify the token starts with `xoxb-`
- Reinstall the Slack app to workspace if needed

**Error: "Address already in use"**
- Port 5000 is taken. Stop other processes or use a different port:
  ```bash
  nightshift slack-server --port 5001
  ```

---

## Part 3: Expose Server with ngrok (2 minutes)

### Open Terminal Window #2

```bash
ngrok http 5000
```

If you changed the port above, use that port: `ngrok http 5001`

### Expected Output:

```
ngrok                                                   (Ctrl+C to quit)

Session Status    online
Account           your-email@example.com
Version           3.x.x
Region            United States (us)
Latency           -
Web Interface     http://127.0.0.1:4040
Forwarding        https://abc-123-def.ngrok-free.app -> http://localhost:5000

Connections       ttl     opn     rt1     rt5     p50     p90
                  0       0       0.00    0.00    0.00    0.00
```

### ⚠️ IMPORTANT: Copy Your ngrok URL

From the "Forwarding" line, copy the **HTTPS URL**:
```
https://abc-123-def.ngrok-free.app
```

**This URL changes every time you restart ngrok!** Keep this terminal window open.

### Test the Health Endpoint:

Open a browser or run:
```bash
curl https://YOUR-NGROK-URL/health
```

Should return:
```json
{"status":"healthy","service":"nightshift-slack"}
```

---

## Part 4: Configure Slack App (5 minutes)

### A. Open Your Slack App Settings

1. Go to https://api.slack.com/apps
2. Click on your **NightShift** app
3. You should see the app dashboard

### B. Configure Slash Commands

1. In the left sidebar, click **"Slash Commands"**
2. Look for existing `/nightshift` command or click **"Create New Command"**

**If creating new:**
- **Command:** `/nightshift`
- **Request URL:** `https://YOUR-NGROK-URL/slack/commands`
  - Replace `YOUR-NGROK-URL` with your actual ngrok URL
  - Example: `https://abc-123-def.ngrok-free.app/slack/commands`
- **Short Description:** `Submit and manage NightShift tasks`
- **Usage Hint:** `submit "task description"`
- **Escape channels, users, and links:** Leave unchecked
- Click **"Save"**

**If editing existing:**
- Click the pencil icon next to `/nightshift`
- Update the **Request URL** with your new ngrok URL
- Click **"Save"**

### C. Configure Interactivity (for Approve/Reject buttons)

1. In the left sidebar, click **"Interactivity & Shortcuts"**
2. Toggle **"Interactivity"** to **ON** (if not already)
3. **Request URL:** `https://YOUR-NGROK-URL/slack/interactions`
   - Example: `https://abc-123-def.ngrok-free.app/slack/interactions`
4. Click **"Save Changes"**

### D. Verify Scopes (Important!)

1. In the left sidebar, click **"OAuth & Permissions"**
2. Scroll to **"Bot Token Scopes"**
3. Ensure you have:
   - ✅ `commands`
   - ✅ `chat:write`
   - ✅ `chat:write.public`
   - ✅ `files:write`
   - ✅ `channels:read`
   - ✅ `groups:read`
   - ✅ `im:read`

**If any are missing:**
- Click **"Add an OAuth Scope"** and add them
- Click **"Reinstall to Workspace"** at the top
- Approve the new permissions

---

## Part 5: Test in Slack! (15 minutes)

Now the fun part - let's test everything!

### Test 1: Submit a Simple Task

**In Slack, type:**
```
/nightshift submit "write a haiku about AI"
```

**Expected Flow:**

1. **Immediate Response (< 3 seconds):**
   ```
   🔄 Planning task... This may take 30-120 seconds.
   ```

2. **Check Terminal Window #1 (webhook server):**
   You should see:
   ```
   127.0.0.1 - - [timestamp] "POST /slack/commands HTTP/1.1" 200 -
   ```

3. **After 30-60 seconds, approval message appears:**
   ```
   🎯 Task Plan: task_abc12345

   Description:
   Write a haiku about artificial intelligence...

   Tools: Write
   Estimated: ~500 tokens, ~30s

   [✅ Approve] [❌ Reject] [ℹ️ Details]
   ```

4. **Click "✅ Approve"**

5. **Message updates:**
   ```
   ✅ Task task_abc12345 approved by @your-name
   ⏳ Executing...
   ```

6. **After execution (30-60s), completion notification:**
   ```
   ✅ Task SUCCESS: task_abc12345

   Status: SUCCESS
   Execution Time: 45.2s

   Created: 1 files

   📄 Results: /path/to/output/task_abc12345_output.json
   ```

### Test 2: Reject a Task

**In Slack, type:**
```
/nightshift submit "calculate pi to 1 million digits"
```

**When approval message appears:**
- Click **"❌ Reject"**

**Expected:**
- Message updates to: `❌ Task task_XXXXXXXX rejected by @your-name`
- Task status changes to CANCELLED

### Test 3: View Task Details

**When an approval message appears:**
- Click **"ℹ️ Details"**

**Expected:**
- You receive an ephemeral message (only you can see it) with:
  - Full task description
  - Complete tool list
  - Allowed directories
  - System prompt

### Test 4: Queue Management

**In Slack, type:**
```
/nightshift queue
```

**Expected:**
- List of all tasks with their status
- Emoji indicators (📝 STAGED, ⏳ RUNNING, ✅ COMPLETED, etc.)

**Try with status filter:**
```
/nightshift queue staged
```

### Test 5: Check Task Status

**In Slack, type:**
```
/nightshift status task_abc12345
```

(Replace `task_abc12345` with an actual task ID from your queue)

**Expected:**
- Current status
- Task description
- Creation time
- Output path (if running/completed)

### Test 6: Real MCP Task (ArXiv Paper)

Let's test with a real research task!

**In Slack, type:**
```
/nightshift submit "download and summarize arxiv paper 2501.12345"
```

**Expected:**
1. Planning takes longer (~60-90s) because it needs to analyze tool requirements
2. Approval message shows tools: `mcp__arxiv__download`, `mcp__gemini__ask` or `mcp__claude__ask`
3. After approval, task downloads paper and generates summary
4. Completion notification shows created files

---

## Part 6: Verify Everything Works (5 minutes)

### Check Terminal Windows

**Terminal #1 (nightshift slack-server):**
- Should show all incoming requests
- No error messages
- Format: `127.0.0.1 - - [timestamp] "POST /slack/commands HTTP/1.1" 200 -`

**Terminal #2 (ngrok):**
- Shows connection count increasing
- "Connections" line shows activity

### Check Slack Messages

- [ ] Approval messages appear correctly
- [ ] Buttons work (Approve/Reject/Details)
- [ ] Completion notifications appear
- [ ] Messages update in-place (not creating new messages)

### Check File System

```bash
# Check task was created
ls ~/.nightshift/output/

# View output
cat ~/.nightshift/output/task_XXXXXXXX_output.json

# Check Slack metadata was stored
ls ~/.nightshift/slack_metadata/

# View notification
cat ~/.nightshift/notifications/task_XXXXXXXX_notification.json
```

---

## Troubleshooting Common Issues

### Issue 1: Slack Command Not Recognized

**Symptom:** `/nightshift` shows "Command not found"

**Solutions:**
1. Verify slash command is created in Slack app settings
2. Check the command is exactly `/nightshift` (lowercase, no space)
3. Try uninstalling and reinstalling the app to your workspace

### Issue 2: No Response After Typing Command

**Symptom:** Slack shows error "nightshift failed with error: dispatch_failed"

**Solutions:**
1. Check ngrok is running (`Terminal #2` should show "Session Status: online")
2. Verify Request URL in Slack app matches your ngrok URL exactly
3. Test health endpoint: `curl https://YOUR-NGROK-URL/health`
4. Check Terminal #1 for error messages

### Issue 3: "Invalid Signature" Error

**Symptom:** Terminal #1 shows 401 errors

**Solutions:**
1. Verify signing secret is correct:
   ```bash
   nightshift slack-config
   ```
2. Check signing secret matches what's in Slack App settings (Basic Information → App Credentials)
3. Reconfigure:
   ```bash
   nightshift slack-setup
   ```

### Issue 4: Planning Takes Too Long / Times Out

**Symptom:** Planning message appears but never shows approval

**Solutions:**
1. Check Terminal #1 for Python errors
2. Verify Claude CLI is installed: `claude --version`
3. Check you're logged in: `claude auth status`
4. Try a simpler task first: `/nightshift submit "write hello world"`

### Issue 5: Approval Buttons Don't Work

**Symptom:** Clicking buttons shows error or nothing happens

**Solutions:**
1. Check Interactivity Request URL is configured
2. Verify ngrok URL is correct and hasn't changed
3. Look for errors in Terminal #1 when clicking button
4. Ensure "Interactivity" is toggled ON in Slack app settings

### Issue 6: No Completion Notification

**Symptom:** Task completes but no notification in Slack

**Solutions:**
1. Check Terminal #1 for notifier errors
2. Verify task completed successfully:
   ```bash
   nightshift queue
   ```
3. Check if metadata exists:
   ```bash
   ls ~/.nightshift/slack_metadata/
   ```
4. Look at notifier output in terminal (should show "Warning: Slack notification failed" if error)

---

## Advanced Testing (Optional)

### Test Process Control (Pause/Resume/Kill)

**1. Submit a long-running task:**
```
/nightshift submit "analyze 5 arxiv papers on quantum computing"
```

**2. After approval, while it's running:**
```
/nightshift pause task_XXXXXXXX
```

**Expected:** Process pauses (you can verify in terminal or queue)

**3. Resume:**
```
/nightshift resume task_XXXXXXXX
```

**4. If needed, kill:**
```
/nightshift kill task_XXXXXXXX
```

### Test Multiple Concurrent Tasks

Submit 3 tasks quickly:
```
/nightshift submit "task 1"
/nightshift submit "task 2"
/nightshift submit "task 3"
```

Verify:
- All three show approval messages
- You can approve them in any order
- Completion notifications appear correctly

### Test Rate Limiting

Try submitting 15 tasks in quick succession. After 10, you should see:
```
429 Too Many Requests
```

Wait 60 seconds, then try again (should work).

---

## Success Criteria Checklist

Your integration is working if:

- [✓] `/nightshift submit` creates approval messages
- [✓] Approve button executes tasks
- [✓] Reject button cancels tasks
- [✓] Completion notifications appear
- [✓] All queue commands work (`queue`, `status`, `cancel`)
- [✓] No signature verification errors (401s)
- [✓] Terminal output stays clean (no exceptions)

---

## Clean Up After Testing

### Stop Services

1. **Terminal #1:** Press `Ctrl+C` to stop webhook server
2. **Terminal #2:** Press `Ctrl+C` to stop ngrok

### Optional: Clear Test Data

```bash
nightshift clear --confirm
```

This removes all test tasks and outputs.

---

## Next Steps After Successful Testing

### Phase 2 Features (Optional - Week 3)

Now that Phase 1 works, you could implement:

1. **Real-time Progress Updates**
   - Show task progress in Slack as it executes
   - Update message every 10 seconds with current tool usage

2. **Revision Workflow**
   - Add "Revise" button to approval messages
   - Open Slack modal for feedback input
   - Re-plan task with user feedback

3. **File Uploads**
   - Upload task output files directly to Slack
   - Support PDF, MD, JSON formats

4. **Multi-User Authorization**
   - Role-based access control (admin/user/viewer)
   - User-specific task lists
   - Audit logging

### Documentation (Sub-Task 1.8)

Create comprehensive docs:
- Setup guide for new users
- Troubleshooting guide
- Architecture overview
- API reference

---

## Questions or Issues?

If you encounter issues not covered here:

1. Check both terminal windows for errors
2. Look at the Slack integration plan: `docs/slack-integration-plan.md`
3. Review the code in `nightshift/integrations/`
4. Check logs: `~/.nightshift/logs/`

---

**Happy Testing! 🚀**

If everything works, you now have a fully functional Slack integration for NightShift!
