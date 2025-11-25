# NightShift Slack Integration - Quick Start

**30-Second Setup** | **5-Minute Testing**

---

## Start Testing (Copy & Paste)

### Terminal 1 - Start Server
```bash
cd /Users/james/Dropbox/JimDex/60-69\ Library/60\ Packages/60.20\ nightshift/nightshift
nightshift slack-server
```

### Terminal 2 - Start ngrok
```bash
ngrok http 5000
```

**Copy the ngrok URL:** `https://abc-123-def.ngrok-free.app`

---

## Configure Slack App (One Time)

1. Go to https://api.slack.com/apps
2. Select your **NightShift** app

**Slash Commands:**
- Command: `/nightshift`
- URL: `https://YOUR-NGROK-URL/slack/commands` ← paste your ngrok URL

**Interactivity & Shortcuts:**
- Toggle ON
- URL: `https://YOUR-NGROK-URL/slack/interactions` ← paste your ngrok URL

---

## Test Commands (In Slack)

### Basic Test
```
/nightshift submit "write a haiku about AI"
```

✅ Approve → Task executes → Notification appears

### Real Research Task
```
/nightshift submit "download and summarize arxiv paper 2501.12345"
```

### Queue Management
```
/nightshift queue
/nightshift status task_XXXXXXXX
/nightshift cancel task_XXXXXXXX
```

---

## Verify Success

✓ Approval messages appear with buttons
✓ Buttons work (Approve/Reject/Details)
✓ Completion notifications show up
✓ Terminal shows requests (200 status)
✓ No 401 errors (signature validation)

---

## Common Issues

**Command not found:**
- Reinstall Slack app to workspace
- Verify `/nightshift` command exists in app settings

**No response:**
- Check ngrok is running
- Verify URLs in Slack match ngrok URL
- Test: `curl https://YOUR-NGROK-URL/health`

**Invalid signature (401):**
```bash
nightshift slack-setup
```
Re-enter credentials

---

## Full Testing Guide

See: `TESTING_SLACK_INTEGRATION.md` for complete details.

---

**Need Help?** Check:
- Terminal output for errors
- `nightshift slack-config` to verify setup
- Logs: `~/.nightshift/logs/`
