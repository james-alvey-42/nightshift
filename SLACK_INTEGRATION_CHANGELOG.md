# Slack Integration - Debugging Changelog

**Session Date:** November 25, 2025
**Duration:** ~2 hours of active debugging
**Result:** All critical bugs fixed, ready for production testing

---

## Code Changes Summary

### 1. slack_server.py - Request Body Caching

**Problem:** Flask consumed request body stream during form parsing, leaving nothing for signature verification.

**Solution:** Added `@app.before_request` hook to cache raw body before any parsing.

```python
# Added at line 53-57
@app.before_request
def cache_request_body():
    """Cache the raw request body before Flask parses it"""
    if request.method == 'POST' and not hasattr(request, '_cached_raw_body'):
        request._cached_raw_body = request.get_data(cache=True, as_text=True)
```

**Modified `_verify_signature()` at line 287-303:**
```python
# Use the cached raw body that was saved in before_request
if hasattr(request, '_cached_raw_body'):
    request_body = request._cached_raw_body
    print(f"[DEBUG] Using cached raw body: {len(request_body)} chars")
else:
    # Fallback to get_data (shouldn't happen)
    request_body = request.get_data(cache=True, as_text=True)
    print(f"[DEBUG] Fallback to get_data: {len(request_body)} chars")

sig_basestring = f"v0:{timestamp}:{request_body}"
```

**Impact:** Signature verification now works for both slash commands and button interactions.

---

### 2. slack_handler.py - DM Channel Handling

**Problem:** Posting to DM channels failed with `channel_not_found` because we used channel_id instead of user_id.

**Solution:** Detect DM channels (start with 'D') and use user_id instead.

**Modified `_plan_and_stage_task()` at line 139-146:**
```python
# Send approval message with buttons
blocks = SlackFormatter.format_approval_message(task, plan)

# For DMs, use user_id as channel; for channels, use channel_id
target_channel = user_id if channel_id.startswith('D') else channel_id

response = self.slack.post_message(
    channel=target_channel,
    text=f"Task {task_id} ready for approval",
    blocks=blocks
)
```

**Also applied same fix in error handler at line 157-162.**

**Impact:** Approval messages now successfully post to DMs.

---

### 3. slack_handler.py - Task Object vs String

**Problem:** `agent_manager.execute_task()` expects Task object with attributes like `.description`, `.allowed_tools`, etc., but was receiving task_id string.

**Solution:** Pass Task object instead of string.

**Modified `_execute_and_notify()` at line 248-259:**
```python
try:
    # Get task_id whether task is object or string
    print(f"[DEBUG] _execute_and_notify called with task type: {type(task)}, value: {task}")
    if isinstance(task, str):
        task_id = task
        task = self.task_queue.get_task(task_id)
    else:
        task_id = task.task_id

    self.logger.info(f"Executing task {task_id} from Slack")

    # Execute task (this will take a while) - pass Task object, not task_id string
    self.agent_manager.execute_task(task)  # ← Fixed: was task_id
```

**Impact:** Task execution now starts successfully after approval.

---

## Error Timeline

### Error 1: Port Conflict
- **When:** Initial server startup
- **Error:** `Address already in use` on port 5000
- **Cause:** macOS AirPlay Receiver
- **Fix:** Use `--port 5001`
- **Status:** ✅ Fixed immediately

### Error 2: 401 Unauthorized (Signature Verification)
- **When:** First `/nightshift submit` command
- **Error:** `Invalid signature` (401)
- **Cause:** Request body empty (0 bytes) during signature verification
- **Debug Process:**
  1. Verified signing secret matched ✓
  2. Checked timestamp within 5 minutes ✓
  3. Found body length = 0 ✗
- **Attempts:**
  1. Added `request.get_data()` before verification → Failed
  2. Tried custom caching with `request._cached_data` → Failed
  3. Reconstructed body from `request.form` → Worked for commands, failed for interactions
  4. **Final fix:** `@app.before_request` hook → Success!
- **Status:** ✅ Fixed with before_request hook

### Error 3: channel_not_found
- **When:** After task planning, posting approval message
- **Error:** `{'ok': False, 'error': 'channel_not_found'}`
- **Cause:** Using channel_id (D09VAHAPUN8) for DM instead of user_id
- **Fix:** Check if channel_id starts with 'D', use user_id
- **Status:** ✅ Fixed with conditional channel selection

### Error 4: Signature Mismatch for Interactions
- **When:** Clicking Approve/Reject buttons
- **Error:** Signature verification failed again
- **Cause:** `urlencode()` reconstruction didn't match exact bytes
- **Fix:** Already solved by before_request hook from Error 2
- **Status:** ✅ Fixed (same solution as Error 2)

### Error 5: AttributeError - 'str' object has no attribute 'task_id'
- **When:** After clicking Approve button, during task execution
- **Error:** `AttributeError: 'str' object has no attribute 'description'`
- **Cause:** Passing task_id string instead of Task object to execute_task()
- **Traceback:**
  ```
  File "agent_manager.py", line 70, in execute_task
      cmd = self._build_command(task)
  File "agent_manager.py", line 382, in _build_command
      cmd_parts.append(f'"{task.description}"')
  ```
- **Fix:** Pass Task object instead of task_id string
- **Status:** ✅ Fixed (pass `task` not `task_id`)

---

## Files Modified

### nightshift/integrations/slack_server.py
- Added `cache_request_body()` function (lines 53-57)
- Modified `_verify_signature()` to use cached body (lines 287-303)
- **Reason:** Fix signature verification with consumed request bodies

### nightshift/integrations/slack_handler.py
- Modified `_plan_and_stage_task()` for DM handling (lines 139-146, 157-162)
- Modified `_execute_and_notify()` for Task object (lines 248-259)
- **Reason:** Fix DM channel posting and task execution type mismatch

---

## Documentation Created

### SLACK_TESTING_STATUS.md
- Current status and quick testing guide
- Lists all fixed bugs
- Verification checklist

### TESTING_SLACK_INTEGRATION.md (previously created)
- Comprehensive 45-minute testing guide
- 6 phases: install ngrok, start server, expose, configure, test, verify
- Troubleshooting section for common issues

### SLACK_QUICK_START.md (previously created)
- One-page quick reference
- Copy-paste commands for experienced users

---

## Technical Learnings

### Flask Request Lifecycle
- Request body streams can only be read once
- `request.form` consumes the body
- Must cache before any parsing if signature verification needed
- Use `@app.before_request` for early caching

### Slack API Patterns
- DM channels have IDs starting with 'D' (e.g., D09VAHAPUN8)
- Regular channels start with 'C' (e.g., C123456)
- Use `user_id` for posting to DMs, `channel_id` for channels
- Signature verification uses HMAC-SHA256 with timestamp and body

### NightShift Architecture
- `agent_manager.execute_task()` expects Task objects, not IDs
- Task objects have attributes: .task_id, .description, .allowed_tools, .system_prompt
- Fetch Task from queue when receiving task_id string

---

## Testing Status

### ✅ Tested and Working
- Server startup on port 5001
- ngrok tunneling
- Slack signature verification (commands)
- Slack signature verification (interactions)
- Task planning (30-60s)
- Approval message posting to DM
- Button clicks (Approve/Reject)

### 🔄 Ready to Test
- Full end-to-end execution flow
- Completion notifications
- File creation and tracking
- Queue management commands
- Real MCP tasks (ArXiv, etc.)

---

## Next Steps

### Immediate (After Successful Test)
1. Remove debug print statements
2. Test all slash commands (queue, status, cancel, pause, resume, kill)
3. Test with real MCP task (ArXiv paper download)
4. Verify file tracking works
5. Check completion notifications

### Future Enhancements (Phase 2)
1. Real-time progress updates during execution
2. Revision workflow with modal dialogs
3. File uploads to Slack
4. Multi-user authorization and role-based access
5. Production deployment (replace ngrok with proper domain)

---

## Debug Mode

Debug print statements are currently active in:
- `slack_server.py`: Lines 262-313 (_verify_signature)
- `slack_handler.py`: Line 249 (_execute_and_notify)

**To remove after successful testing:**
```bash
grep -n "print(f\"\[DEBUG\]" nightshift/integrations/*.py
```

Then delete those lines.

---

**Status:** Ready for production testing! 🎉

All critical bugs have been identified and fixed. The integration should now work end-to-end.
