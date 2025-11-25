# Remote Trigger and Cloud Execution Guide

This guide covers the new remote trigger and cloud execution features added to NightShift in response to issue #9.

## Overview

NightShift now supports:

1. **Remote Triggers**: Submit and manage tasks from messaging platforms (Slack, WhatsApp, Telegram, Discord)
2. **Cloud Execution**: Execute tasks on cloud providers (GCP, AWS, Azure)
3. **Authentication**: Secure access control for remote submissions
4. **User Management**: User mapping and quota management

## Architecture

### Components

```
nightshift/
├── services/               # Remote trigger services
│   ├── trigger_service.py  # Main webhook handler
│   ├── auth/               # Authentication framework
│   │   ├── authenticator.py
│   │   └── user_mapper.py
│   └── platforms/          # Platform integrations
│       ├── base.py
│       └── slack.py
├── cloud/                  # Cloud execution
│   ├── executor_factory.py
│   ├── gcp/
│   ├── aws/
│   └── azure/
```

### Data Flow

```
User (Slack/WhatsApp/etc.)
    ↓
Webhook → TriggerService
    ↓
Authenticator → Verify signature
    ↓
UserMapper → Map platform user to NightShift user
    ↓
TaskPlanner → Create task plan
    ↓
TaskQueue → Stage task for approval
    ↓
User Approval (button click)
    ↓
AgentManager/CloudExecutor → Execute task
    ↓
Platform → Send status updates
```

## Configuration

### Configuration File

Create `~/.nightshift/config.yaml`:

```yaml
remote:
  enabled: true

  trigger_service:
    platforms:
      slack:
        enabled: true
        bot_token: ${SLACK_BOT_TOKEN}
        signing_secret: ${SLACK_SIGNING_SECRET}

      whatsapp:
        enabled: false
        # WhatsApp Business API configuration

      telegram:
        enabled: false
        # Telegram Bot API configuration

      discord:
        enabled: false
        # Discord Bot configuration

    webhook_url: https://your-server.com/webhook

  execution:
    mode: local  # local, docker, cloud
    cloud_provider: gcp  # gcp, aws, azure

    gcp:
      project: my-research-project
      region: us-central1
      service_account: nightshift-executor@project.iam.gserviceaccount.com
      image: gcr.io/my-project/nightshift:latest
      storage_bucket: gs://nightshift-results

    aws:
      function_name: nightshift-executor
      region: us-east-1
      storage_bucket: s3://nightshift-results

    azure:
      function_app: nightshift-executor
      region: eastus
      storage_account: nightshiftresults

  storage:
    database: sqlite  # sqlite, cloud_sql, rds, azure_db
    results_bucket: gs://nightshift-results

  auth:
    method: api_key  # api_key, oauth2, jwt, platform_signature
    api_keys:
      sk_test_12345: user_alice
      sk_test_67890: user_bob

    platform_secrets:
      slack: ${SLACK_SIGNING_SECRET}
      whatsapp: ${WHATSAPP_SECRET}
      telegram: ${TELEGRAM_BOT_TOKEN}
      discord: ${DISCORD_PUBLIC_KEY}

    allowed_users:
      - slack:U12345678
      - whatsapp:+1234567890
```

### Environment Variables

Set these environment variables for sensitive credentials:

```bash
# Slack
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_SIGNING_SECRET="your-signing-secret"

# GCP
export GCP_PROJECT="my-project"
export GCP_SERVICE_ACCOUNT="nightshift@project.iam.gserviceaccount.com"
export GCP_NIGHTSHIFT_IMAGE="gcr.io/my-project/nightshift:latest"
export GCP_STORAGE_BUCKET="nightshift-results"

# AWS
export AWS_LAMBDA_FUNCTION="nightshift-executor"
export AWS_REGION="us-east-1"
export AWS_S3_BUCKET="nightshift-results"
```

## Setting Up Slack Integration

### 1. Create Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App" → "From scratch"
3. Name: "NightShift"
4. Select your workspace

### 2. Configure Bot Permissions

In your app settings:

1. **OAuth & Permissions** → Add these scopes:
   - `chat:write` - Send messages
   - `commands` - Create slash commands
   - `im:write` - Send DMs
   - `im:history` - Read DM history
   - `channels:history` - Read channel messages
   - `app_mentions:read` - Receive mentions

2. Install app to workspace
3. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 3. Configure Slash Command

1. **Slash Commands** → Create New Command
   - Command: `/nightshift`
   - Request URL: `https://your-server.com/webhook/slack`
   - Short Description: "Submit NightShift research tasks"
   - Usage Hint: `[task description]`

2. Save

### 4. Enable Event Subscriptions

1. **Event Subscriptions** → Enable Events
2. Request URL: `https://your-server.com/webhook/slack`
3. Subscribe to bot events:
   - `app_mention` - When bot is mentioned
   - `message.im` - DMs to bot

### 5. Enable Interactivity

1. **Interactivity & Shortcuts** → Enable
2. Request URL: `https://your-server.com/webhook/slack`

### 6. Get Signing Secret

1. **Basic Information** → App Credentials
2. Copy **Signing Secret**

### 7. Configure NightShift

```bash
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_SIGNING_SECRET="your-signing-secret"
```

Or add to `~/.nightshift/config.yaml`

## Usage Examples

### Slack

```bash
# Submit task via slash command
/nightshift analyze recent papers on transformer architectures

# Check task status
/nightshift status task_12345678

# Mention bot in channel
@NightShift summarize this week's arXiv papers on ML
```

Bot will respond with:

```
✨ Task Created: task_12345678

Description:
Analyze recent papers on transformer architectures published in the last 6 months

Estimated Tokens: ~50000
Estimated Time: ~180s

[✓ Approve & Execute] [✕ Cancel]
```

Click **Approve** to execute the task.

### API (Direct Webhook)

```bash
curl -X POST https://your-server.com/webhook/slack \
  -H "Content-Type: application/json" \
  -H "X-API-Key: sk_test_12345" \
  -d '{
    "description": "Analyze transformer papers",
    "auto_approve": false
  }'
```

## Cloud Execution (GCP Example)

### Prerequisites

1. GCP project with billing enabled
2. Cloud Run API enabled
3. Service account with permissions:
   - Cloud Run Admin
   - Storage Object Admin
   - Secret Manager Secret Accessor

### Build Container Image

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

# Install Claude CLI
RUN pip install claude-cli

# Install NightShift
COPY . /app
WORKDIR /app
RUN pip install -e .

# Entrypoint
CMD ["python", "-m", "nightshift.cloud.gcp.runner"]
```

Build and push:

```bash
docker build -t gcr.io/my-project/nightshift:latest .
docker push gcr.io/my-project/nightshift:latest
```

### Configure NightShift for Cloud

```yaml
remote:
  execution:
    mode: cloud
    cloud_provider: gcp
    gcp:
      project: my-project
      region: us-central1
      service_account: nightshift@project.iam.gserviceaccount.com
      image: gcr.io/my-project/nightshift:latest
      storage_bucket: gs://nightshift-results
```

### Deploy

Tasks will now execute on Cloud Run instead of locally.

## Authentication

### API Keys

For direct API access:

```yaml
auth:
  method: api_key
  api_keys:
    sk_test_alice_12345: user_alice
    sk_test_bob_67890: user_bob
```

Usage:

```bash
curl -H "X-API-Key: sk_test_alice_12345" \
  https://your-server.com/api/submit \
  -d '{"description": "task description"}'
```

### Platform Signature Verification

Automatically verifies webhooks from platforms:

- **Slack**: HMAC-SHA256 signature verification
- **WhatsApp**: SHA256 signature with app secret
- **Telegram**: Secret token validation
- **Discord**: Ed25519 signature (requires nacl library)

## User Management

### User Mapping

Platform users are automatically mapped to NightShift users:

```python
from nightshift.services.auth import UserMapper

mapper = UserMapper('~/.nightshift/database/users.db')

# Map Slack user
mapper.map_user(
    platform='slack',
    platform_user_id='U12345678',
    nightshift_user_id='user_alice',
    display_name='Alice Smith',
    email='alice@example.com'
)

# Get user
user = mapper.get_nightshift_user('slack', 'U12345678')
print(user.nightshift_user_id)  # user_alice
```

### Quotas

Set usage limits per user:

```python
mapper.set_quota(
    nightshift_user_id='user_alice',
    max_tasks_per_day=20,
    max_tokens_per_task=200000,
    max_concurrent_tasks=5
)
```

### Permissions

Grant specific permissions:

```python
mapper.grant_permission('user_alice', 'admin')
mapper.grant_permission('user_bob', 'submit_tasks')

if mapper.has_permission('user_alice', 'admin'):
    # Allow admin actions
    pass
```

## Running the Trigger Service

### Local Development

```python
from nightshift.core import Config, TaskQueue, TaskPlanner, AgentManager, NightShiftLogger
from nightshift.services import TriggerService

# Initialize
config = Config()
logger = NightShiftLogger(log_dir=str(config.get_log_dir()))
task_queue = TaskQueue(db_path=str(config.get_database_path()))
task_planner = TaskPlanner(logger, tools_reference_path=str(config.get_tools_reference_path()))
agent_manager = AgentManager(task_queue, logger, output_dir=str(config.get_output_dir()))

# Create trigger service
remote_config = config.get_remote_config()
trigger_service = TriggerService(
    config=remote_config,
    task_queue=task_queue,
    task_planner=task_planner,
    agent_manager=agent_manager,
    logger=logger
)

# Handle webhook (example with Flask)
from flask import Flask, request

app = Flask(__name__)

@app.route('/webhook/slack', methods=['POST'])
def slack_webhook():
    result = trigger_service.handle_webhook(
        platform='slack',
        headers=dict(request.headers),
        body=request.get_data(as_text=True),
        payload=request.json
    )
    return result

app.run(port=8080)
```

### Production Deployment

Use a production WSGI server:

```bash
pip install gunicorn

gunicorn -w 4 -b 0.0.0.0:8080 nightshift.services.webhook_server:app
```

## Security Considerations

1. **Always use HTTPS** for webhook endpoints
2. **Verify webhook signatures** - implemented automatically
3. **Store secrets in environment variables** or secret managers
4. **Implement rate limiting** - use API gateway or middleware
5. **Audit logging** - all remote submissions are logged
6. **User quotas** - prevent abuse with usage limits
7. **Network security** - use private VPCs for cloud execution

## Limitations and Future Work

### Current Limitations

1. **Cloud execution not fully implemented** - GCP/AWS/Azure executors are placeholders
2. **No message queue** - task execution is synchronous (should use Pub/Sub, SQS, etc.)
3. **Discord signature verification** - requires nacl library
4. **OAuth2/JWT authentication** - placeholders only
5. **No cost tracking** - need to implement per-user cost attribution

### Roadmap

- [ ] Complete GCP Cloud Run executor
- [ ] Add message queue for async execution
- [ ] Implement cost tracking and budget alerts
- [ ] Add WhatsApp, Telegram, Discord integrations
- [ ] Real-time progress streaming via WebSockets
- [ ] Multi-region deployment
- [ ] Scheduled and recurring tasks
- [ ] Team workspaces with shared quotas

## Troubleshooting

### Slack webhook not responding

1. Check Slack signing secret matches config
2. Verify webhook URL is accessible (use ngrok for local testing)
3. Check logs: `tail -f ~/.nightshift/logs/nightshift_*.log`

### Task execution failing in cloud

1. Verify cloud credentials are valid
2. Check container image has NightShift installed
3. Ensure service account has required permissions
4. Review cloud provider logs (Cloud Run logs, Lambda logs, etc.)

### User not authorized

1. Check user is mapped: `mapper.get_nightshift_user(platform, user_id)`
2. Verify user has permissions
3. Check quota limits haven't been exceeded

## Example: Complete Slack Setup

```bash
# 1. Install dependencies
pip install -e .
pip install flask gunicorn pyyaml requests

# 2. Set environment variables
export SLACK_BOT_TOKEN="xoxb-your-token"
export SLACK_SIGNING_SECRET="your-secret"

# 3. Create config file
cat > ~/.nightshift/config.yaml <<EOF
remote:
  enabled: true
  trigger_service:
    platforms:
      slack:
        enabled: true
        bot_token: \${SLACK_BOT_TOKEN}
        signing_secret: \${SLACK_SIGNING_SECRET}
  execution:
    mode: local
  auth:
    method: platform_signature
    platform_secrets:
      slack: \${SLACK_SIGNING_SECRET}
EOF

# 4. Create webhook server (save as webhook_server.py)
python webhook_server.py

# 5. Expose with ngrok (for testing)
ngrok http 8080

# 6. Update Slack app webhook URLs with ngrok URL

# 7. Test in Slack
# /nightshift analyze recent ML papers
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/james-alvey-42/nightshift/issues
- Documentation: See issue #9 for detailed requirements
