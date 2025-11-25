"""
Example Webhook Server for NightShift Remote Triggers

This is a sample Flask application that handles webhooks from messaging platforms.

Usage:
    python webhook_server.py

Then expose with ngrok for testing:
    ngrok http 8080

Update your Slack/WhatsApp/etc. webhook URLs to point to the ngrok URL.
"""
from flask import Flask, request, jsonify
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from nightshift.core import Config, TaskQueue, TaskPlanner, AgentManager, NightShiftLogger
from nightshift.services import TriggerService

app = Flask(__name__)

# Initialize NightShift components
print("Initializing NightShift components...")
config = Config()
logger = NightShiftLogger(log_dir=str(config.get_log_dir()))
task_queue = TaskQueue(db_path=str(config.get_database_path()))
task_planner = TaskPlanner(logger, tools_reference_path=str(config.get_tools_reference_path()))
agent_manager = AgentManager(task_queue, logger, output_dir=str(config.get_output_dir()))

# Check if remote is enabled
if not config.is_remote_enabled():
    print("WARNING: Remote triggers are not enabled in config!")
    print("Set 'remote.enabled: true' in ~/.nightshift/config.yaml")

# Create trigger service
remote_config = config.get_remote_config()
trigger_service = TriggerService(
    config=remote_config,
    task_queue=task_queue,
    task_planner=task_planner,
    agent_manager=agent_manager,
    logger=logger
)

print("Trigger service initialized successfully!")
print(f"Enabled platforms: {[p for p in trigger_service.platforms.keys()]}")


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'service': 'nightshift-webhook',
        'remote_enabled': config.is_remote_enabled(),
        'platforms': list(trigger_service.platforms.keys())
    })


@app.route('/webhook/slack', methods=['POST'])
def slack_webhook():
    """
    Slack webhook handler

    Receives:
    - Slash commands (/nightshift)
    - Interactive components (button clicks)
    - App mentions
    - URL verification challenges
    """
    try:
        # Get headers and body
        headers = dict(request.headers)
        body = request.get_data(as_text=True)

        # Parse JSON payload
        # Slack sometimes sends form-encoded data for slash commands
        if request.content_type == 'application/x-www-form-urlencoded':
            payload = request.form.to_dict()
        else:
            payload = request.json or {}

        # Handle URL verification challenge
        if payload.get('type') == 'url_verification':
            return jsonify({'challenge': payload.get('challenge')})

        # Handle webhook
        result = trigger_service.handle_webhook(
            platform='slack',
            headers=headers,
            body=body,
            payload=payload
        )

        # Return appropriate response
        if result.get('challenge'):
            return jsonify({'challenge': result['challenge']})

        if result.get('success'):
            return jsonify({'status': 'ok', 'message': 'Processed'})
        else:
            return jsonify({'status': 'error', 'error': result.get('error', 'Unknown error')}), 400

    except Exception as e:
        logger.error(f"Error handling Slack webhook: {str(e)}")
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/webhook/whatsapp', methods=['POST'])
def whatsapp_webhook():
    """WhatsApp webhook handler (placeholder)"""
    return jsonify({
        'status': 'error',
        'error': 'WhatsApp integration not yet implemented'
    }), 501


@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    """Telegram webhook handler (placeholder)"""
    return jsonify({
        'status': 'error',
        'error': 'Telegram integration not yet implemented'
    }), 501


@app.route('/webhook/discord', methods=['POST'])
def discord_webhook():
    """Discord webhook handler (placeholder)"""
    return jsonify({
        'status': 'error',
        'error': 'Discord integration not yet implemented'
    }), 501


@app.route('/api/submit', methods=['POST'])
def api_submit():
    """
    Direct API submission endpoint

    Requires API key authentication

    Example:
        curl -X POST http://localhost:8080/api/submit \
             -H "X-API-Key: sk_test_12345" \
             -H "Content-Type: application/json" \
             -d '{"description": "analyze papers on transformers"}'
    """
    try:
        # Get API key from header
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'error': 'Missing API key'}), 401

        # TODO: Validate API key with authenticator

        data = request.json
        description = data.get('description')

        if not description:
            return jsonify({'error': 'Missing description'}), 400

        # Plan task
        plan = task_planner.plan_task(description)

        # Create task
        import uuid
        task_id = f"task_{uuid.uuid4().hex[:8]}"

        task = task_queue.create_task(
            task_id=task_id,
            description=plan['enhanced_prompt'],
            allowed_tools=plan['allowed_tools'],
            system_prompt=plan['system_prompt'],
            estimated_tokens=plan['estimated_tokens'],
            estimated_time=plan['estimated_time']
        )

        logger.log_task_created(task_id, description)

        return jsonify({
            'success': True,
            'task_id': task_id,
            'status': 'staged',
            'plan': plan
        })

    except Exception as e:
        logger.error(f"Error in API submit: {str(e)}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    print("\n" + "="*60)
    print("NightShift Webhook Server")
    print("="*60)
    print("\nEndpoints:")
    print("  GET  /health             - Health check")
    print("  POST /webhook/slack      - Slack webhooks")
    print("  POST /webhook/whatsapp   - WhatsApp webhooks (not implemented)")
    print("  POST /webhook/telegram   - Telegram webhooks (not implemented)")
    print("  POST /webhook/discord    - Discord webhooks (not implemented)")
    print("  POST /api/submit         - Direct API submission")
    print("\nStarting server on http://0.0.0.0:8080")
    print("="*60 + "\n")

    app.run(host='0.0.0.0', port=8080, debug=True)
