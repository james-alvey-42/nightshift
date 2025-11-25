# Slack Integration Summary - Issue #11

**Branch:** `feature/issue-11-slack-api-integration`
**Status:** Planning Complete ✅
**Full Plan:** [docs/slack-integration-plan.md](docs/slack-integration-plan.md)

---

## Quick Overview

This document summarizes the comprehensive Slack API integration plan for NightShift. The full 1,700+ line plan is available in `docs/slack-integration-plan.md`.

---

## What We're Building

Enable NightShift task management directly from Slack:
- **Submit tasks** via `/nightshift submit "description"`
- **Approve/reject** tasks with interactive buttons
- **Monitor progress** with real-time updates in threads
- **Receive notifications** when tasks complete
- **Manage tasks** with additional commands (pause, resume, kill, queue, status)

---

## Architecture Insights

### Existing System (Well-Suited for Integration)

**Strong Foundations:**
1. ✅ **Modular Command Structure** - CLI commands are well-separated, easy to map to Slack
2. ✅ **Task Lifecycle Management** - Clear state machine (STAGED → COMMITTED → RUNNING → COMPLETED/FAILED)
3. ✅ **Process Control** - pause/resume/kill commands already track PIDs and manage subprocesses
4. ✅ **Notification System** - `Notifier` class has placeholder `_send_slack()` method ready to implement
5. ✅ **Dependency Injection** - Context-based component sharing makes testing easy
6. ✅ **Real-time Output Streaming** - AgentManager already streams stdout/stderr to files, can be tapped for progress

**Key Integration Points:**
- **TaskQueue** - Add Slack metadata (user_id, channel_id, thread_ts) per task
- **Notifier** - Implement `_send_slack()` to send Block Kit messages
- **CLI** - Add `slack-server` and `slack-setup` commands
- **AgentManager** - Optionally add progress event hooks for real-time updates

---

## Implementation Plan

### Phase 1: Foundation (Weeks 1-2) - MVP ✨

**Goal:** Basic task submission and approval via Slack

**Sub-Tasks (8 total):**
1. Configuration & secrets management (2-3h)
2. Slack client wrapper (4-6h)
3. Webhook server infrastructure (6-8h)
4. Event handler core (8-10h)
5. Notifier extension (4-6h)
6. Slash command registration (2-3h)
7. CLI server management (2-3h)
8. Documentation & examples (3-4h)

**Deliverables:**
- `/nightshift submit` command works in Slack
- Interactive approval message with Approve/Reject buttons
- Completion notifications posted to Slack
- Webhook server runs via `nightshift slack-server`
- Setup documentation

**Time Estimate:** ~40-50 hours (~2 weeks)

---

### Phase 2: Interactive Features (Week 3) 🚀

**Goal:** Enhanced UX with threads, progress, and more commands

**Sub-Tasks (4 total):**
1. Additional slash commands (queue, status, cancel, pause, resume, kill) - 6-8h
2. Thread-based conversations - 4-6h
3. Real-time progress updates - 10-12h
4. Revision workflow with modal input - 6-8h

**Deliverables:**
- Full command parity with CLI
- Thread-based conversations (less channel noise)
- Live progress updates during execution
- Revision workflow via Slack modals

**Time Estimate:** ~26-34 hours (~1 week)

---

### Phase 3: Advanced Features (Week 4+) 🎯

**Goal:** Production-ready with multi-user, files, and rich formatting

**Sub-Tasks (4 total):**
1. File upload support - 8-10h
2. Multi-user & authorization (RBAC) - 12-15h
3. Multi-channel support - 6-8h
4. Rich formatting & visualizations - 8-10h

**Deliverables:**
- Upload task outputs to Slack
- Role-based access control (admin/user/viewer)
- Support for any channel or DM
- Beautiful Block Kit layouts

**Time Estimate:** ~34-43 hours (~1.5 weeks)

---

## Technical Stack

### New Dependencies
```python
# Add to setup.py
'slack-sdk>=3.23.0',       # Official Slack SDK
'flask>=3.0.0',            # Webhook server
'flask-limiter>=3.5.0',    # Rate limiting
'python-dotenv>=1.0.0',    # Environment config
```

### New Modules
```
nightshift/integrations/
├── __init__.py
├── slack_client.py         # Slack SDK wrapper
├── slack_server.py         # Flask webhook server
├── slack_handler.py        # Event routing & business logic
├── slack_formatter.py      # Block Kit message formatting
├── slack_middleware.py     # Auth, rate limiting
└── slack_metadata.py       # Task-Slack mapping store
```

---

## Key Design Decisions

### 1. Async Task Processing
**Problem:** Task planning takes 30-120s, Slack expects response in 3s
**Solution:** Immediate acknowledgment + background thread for planning

```python
def handle_submit(text, user_id, channel_id):
    # Return immediately (< 3s)
    response = {"text": "🔄 Planning task..."}

    # Plan in background
    threading.Thread(
        target=plan_and_notify,
        args=(text, user_id, channel_id),
        daemon=True
    ).start()

    return response
```

### 2. Interactive Approval Workflow
**Pattern:** Block Kit buttons + action handlers

```python
# Approval message
blocks = [
    {"type": "section", "text": {"type": "mrkdwn", "text": "Task ready!"}},
    {"type": "actions", "elements": [
        {"type": "button", "text": "✅ Approve", "action_id": "approve_123"},
        {"type": "button", "text": "❌ Reject", "action_id": "reject_123"}
    ]}
]
```

### 3. Security: Signature Verification
**Critical:** Always verify Slack request signatures

```python
def verify_slack_signature(request, signing_secret):
    timestamp = request.headers.get('X-Slack-Request-Timestamp')
    signature = request.headers.get('X-Slack-Signature')

    # Prevent replay attacks
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    # Verify HMAC
    sig_basestring = f"v0:{timestamp}:{request.get_data().decode()}"
    expected = 'v0=' + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
```

### 4. Notification Integration
**Extend existing Notifier:**

```python
class Notifier:
    def __init__(self, slack_client=None, slack_metadata=None):
        self.slack_client = slack_client
        self.slack_metadata = slack_metadata

    def notify(self, task_id, ...):
        # Existing: terminal display
        self._display_terminal(summary)

        # New: Slack notification
        if self.slack_client:
            self._send_slack(summary)
```

---

## Security Checklist

- [x] Request signature verification (HMAC-SHA256)
- [x] Rate limiting (per-user, per-endpoint)
- [x] Token storage in environment variables
- [x] Sensitive output redaction (API keys, secrets)
- [ ] User authorization & role-based access (Phase 2+)
- [ ] Audit logging for security events
- [ ] Channel restrictions for sensitive data

---

## Testing Strategy

### Unit Tests (80%+ coverage)
- Mock Slack API responses
- Test all handler methods
- Validate Block Kit formatting
- Test signature verification
- Test rate limiting logic

### Integration Tests
- End-to-end task submission flow
- Approval workflow with button clicks
- Error handling and retries
- Thread-based conversations

### Manual Testing
- Slack test workspace setup
- ngrok for local webhook testing
- Test all slash commands
- Test with various task types
- Performance testing (10+ concurrent tasks)

---

## Scalability Considerations

### Short-term (Phase 1)
- ✅ Single webhook server instance
- ✅ SQLite database (< 1000 tasks)
- ✅ Background threads for async processing

### Medium-term (Phase 2-3)
- 🔄 Task queue with Celery/RQ
- 🔄 PostgreSQL migration for multi-user
- 🔄 Redis caching for user/channel info
- 🔄 Prometheus metrics + Grafana dashboards

### Long-term (Future)
- 🎯 Multi-instance with load balancer
- 🎯 Distributed database (CockroachDB)
- 🎯 Message queue for notifications
- 🎯 Horizontal scaling with Kubernetes

---

## Development Timeline

| Week | Phase | Focus | Deliverables |
|------|-------|-------|--------------|
| 1 | Phase 1 Setup | Config, client, webhook server | Server running, signature verification |
| 2 | Phase 1 Core | Event handlers, notifier, docs | `/nightshift submit` working end-to-end |
| 3 | Phase 2 | Interactive features | Threads, progress, additional commands |
| 4+ | Phase 3 | Advanced features | Files, multi-user, RBAC, rich formatting |

---

## Getting Started (For Developers)

### 1. Read Full Plan
```bash
# Open comprehensive plan
open docs/slack-integration-plan.md
```

### 2. Review Existing Code
**Key files to understand:**
- `nightshift/interfaces/cli.py` - Command patterns
- `nightshift/core/agent_manager.py` - Process management, pause/resume/kill
- `nightshift/core/task_queue.py` - Task lifecycle
- `nightshift/core/notifier.py` - Notification system

### 3. Set Up Slack App (Before Coding)
1. Create Slack workspace for testing
2. Create new Slack App at api.slack.com/apps
3. Add bot token scopes: `commands`, `chat:write`, `interactions:write`, `files:write`
4. Install app to workspace
5. Copy bot token (xoxb-...) and signing secret

### 4. Start with Sub-Task 1.1
- Implement `SlackConfig` class
- Add environment variable support
- Create `.env.example` file

---

## Questions & Decisions Needed

1. **Webhook Framework:** Flask (simple) vs. FastAPI (async, modern)?
   - Recommendation: Flask for MVP, FastAPI for Phase 3+

2. **Hosting:** Where to run webhook server?
   - Development: ngrok tunnel
   - Production: Cloud VM, Heroku, AWS Lambda?

3. **Multi-User Priority:** Phase 2 or Phase 3?
   - Recommendation: Phase 3 unless multiple users immediately needed

4. **File Uploads:** Store in Slack or just link to local files?
   - Recommendation: Local links initially, Slack upload in Phase 3

5. **Database Migration:** When to move from SQLite to PostgreSQL?
   - Recommendation: When multi-user support needed (Phase 3)

---

## Success Metrics

### Phase 1 (MVP)
- [ ] Task submission latency < 3s (acknowledgment)
- [ ] Planning completes within 120s
- [ ] 95% uptime for webhook server
- [ ] Zero signature verification failures
- [ ] Terminal notifications still work (backward compatible)

### Phase 2 (Interactive)
- [ ] All CLI commands available in Slack
- [ ] Progress updates appear < 10s after change
- [ ] Thread-based conversations reduce channel noise by 80%

### Phase 3 (Production)
- [ ] Support 10+ concurrent users
- [ ] Multi-channel support
- [ ] RBAC prevents unauthorized access
- [ ] File uploads work for common formats

---

## Resources

- **Full Plan:** [docs/slack-integration-plan.md](docs/slack-integration-plan.md)
- **Slack API Docs:** https://api.slack.com/
- **Block Kit Builder:** https://app.slack.com/block-kit-builder
- **Slack SDK (Python):** https://slack.dev/python-slack-sdk/
- **Flask Documentation:** https://flask.palletsprojects.com/

---

## Next Steps

1. ✅ Review and approve this plan
2. ⏳ Set up Slack test workspace and app
3. ⏳ Install ngrok for local development
4. ⏳ Begin Sub-Task 1.1: Configuration & Secrets Management
5. ⏳ Iterate through Phase 1 sub-tasks

---

**Last Updated:** November 25, 2024
**Status:** Planning complete, ready for implementation
**Estimated Total Effort:** 100-130 hours (~3-4 weeks full-time)

🌙 **Built for NightShift** - Automating research, one task at a time.
