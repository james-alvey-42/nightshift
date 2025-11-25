# Slack Integration - Testing Checklist

**Print this and check off as you test!**

---

## Pre-Test Setup

- [ ] Terminal 1 running: `nightshift slack-server --port 5001`
- [ ] Terminal 2 running: `ngrok http 5001`
- [ ] ngrok URL copied: `https://_____________________.ngrok-free.app`
- [ ] Slack app configured with ngrok URL (both endpoints)

---

## Test 1: Simple Task Submission ⭐ CRITICAL

**Command:**
```
/nightshift submit "write a haiku about AI"
```

**Expected Results:**

- [ ] Immediate response: "🔄 Planning task..." (< 3 seconds)
- [ ] Terminal 1 shows: `POST /slack/commands HTTP/1.1 200`
- [ ] Approval message appears in ~30-60 seconds
- [ ] Message shows: Task ID, Description, Tools, Estimate
- [ ] Three buttons visible: ✅ Approve | ❌ Reject | ℹ️ Details

**Click ✅ Approve:**

- [ ] Message updates: "✅ Task approved by @name ⏳ Executing..."
- [ ] Terminal 1 shows: `POST /slack/interactions HTTP/1.1 200`
- [ ] No 401 errors in either terminal

**Wait ~30-60 seconds:**

- [ ] Completion notification appears
- [ ] Shows: Status, Execution Time, Files Created, Results Path
- [ ] File exists: `ls ~/.nightshift/output/task_*_output.json`

**If any step fails, STOP and check terminals for errors.**

---

## Test 2: Reject Button

**Command:**
```
/nightshift submit "calculate pi to 1 million digits"
```

- [ ] Approval message appears
- [ ] Click ❌ Reject
- [ ] Message updates: "❌ Task rejected by @name"
- [ ] No execution happens

---

## Test 3: Details Button

**Using the next approval message:**

- [ ] Click ℹ️ Details
- [ ] Ephemeral message appears (only you see it)
- [ ] Shows: Full description, tools, directories, system prompt

---

## Test 4: Queue Management

**Commands:**
```
/nightshift queue
/nightshift queue staged
/nightshift status task_XXXXXXXX
```

- [ ] Queue shows all tasks
- [ ] Status filter works
- [ ] Status shows task details

---

## Test 5: Real MCP Task ⭐ IMPORTANT

**Command:**
```
/nightshift submit "download and summarize arxiv paper 2501.12345"
```

- [ ] Planning takes longer (~60-90s)
- [ ] Shows MCP tools in approval message
- [ ] Execution works after approval
- [ ] Creates summary file

---

## Terminal Verification

**Terminal 1 (slack-server):**

✅ Good output:
```
[DEBUG] Received signature: v0=abc123...
[DEBUG] Expected signature: v0=abc123...  ← MUST MATCH!
127.0.0.1 - - [timestamp] "POST /slack/commands HTTP/1.1" 200 -
```

❌ Bad output:
```
[ERROR] Signature mismatch!
127.0.0.1 - - [timestamp] "POST /slack/commands HTTP/1.1" 401 -
```

**Terminal 2 (ngrok):**

✅ Good output:
```
POST /slack/commands     200 OK
POST /slack/interactions 200 OK
```

❌ Bad output:
```
POST /slack/commands     401 Unauthorized
```

---

## File System Verification

**Run these commands:**

```bash
# Check task outputs
ls -lh ~/.nightshift/output/

# Check Slack metadata
ls -lh ~/.nightshift/slack_metadata/

# Check notifications
ls -lh ~/.nightshift/notifications/

# View a task result
cat ~/.nightshift/output/task_*_output.json | head -50
```

**Expected:**

- [ ] Output files exist for completed tasks
- [ ] Metadata JSON exists for each Slack task
- [ ] Notification JSON exists for completed tasks

---

## Success Criteria ⭐

Your integration is working if ALL of these pass:

- [ ] `/nightshift submit` creates approval messages
- [ ] ✅ Approve button executes tasks
- [ ] ❌ Reject button cancels tasks
- [ ] ℹ️ Details button shows task info
- [ ] Completion notifications appear
- [ ] NO 401 errors in terminals
- [ ] NO Python exceptions in Terminal 1
- [ ] Files created in `~/.nightshift/output/`

---

## If Tests Fail

### Check These First:

1. **ngrok URL hasn't changed?**
   - Restart ngrok changes the URL
   - Must update Slack app settings every time

2. **Signing secret correct?**
   ```bash
   nightshift slack-config
   ```

3. **Both terminals running?**
   - Terminal 1: nightshift slack-server --port 5001
   - Terminal 2: ngrok http 5001

4. **Claude CLI working?**
   ```bash
   claude --version
   claude auth status
   ```

### Common Errors:

**401 Unauthorized:**
- Check signing secret matches
- Verify ngrok URL is correct
- Look at signature debug output in Terminal 1

**No approval message:**
- Check Terminal 1 for Python errors
- Verify Claude CLI is authenticated
- Try simpler task: "write hello world"

**Buttons don't work:**
- Check Interactivity URL in Slack app
- Verify ngrok URL hasn't changed
- Look for errors when clicking button

**No completion notification:**
- Check Terminal 1 for notifier errors
- Verify Slack metadata exists
- Check bot token has `chat:write` scope

---

## After All Tests Pass

### Cleanup:

- [ ] Remove debug print statements
- [ ] Test process control (pause/resume/kill)
- [ ] Test with multiple concurrent tasks
- [ ] Document any issues found

### Optional:

- [ ] Deploy to production (replace ngrok)
- [ ] Add monitoring/alerting
- [ ] Implement Phase 2 features (progress updates, revisions)

---

**Date Tested:** _______________

**Result:** ☐ Pass  ☐ Fail

**Notes:**
```





```

---

**Ready to test!** 🚀
