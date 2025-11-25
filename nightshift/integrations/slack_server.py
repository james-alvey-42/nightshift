"""
Slack Webhook Server
Flask server to handle Slack slash commands and interactions
"""
import json
import hmac
import hashlib
import time
from flask import Flask, request, jsonify
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from typing import Optional

from .slack_middleware import verify_slack_signature, extract_user_id


# Global app instance (will be configured by CLI)
app = Flask(__name__)
app.config['JSON_SORT_KEYS'] = False

# Rate limiter (will be configured with proper storage in production)
limiter = Limiter(
    app=app,
    key_func=extract_user_id,
    default_limits=["100 per minute"],
    storage_uri="memory://"  # Use memory storage for now, Redis in production
)

# Global handler (will be set by setup_server)
_event_handler: Optional[object] = None
_signing_secret: Optional[str] = None


def setup_server(event_handler: object, signing_secret: str):
    """
    Configure the Flask server with handler and credentials

    Args:
        event_handler: SlackEventHandler instance
        signing_secret: Slack signing secret for verification
    """
    global _event_handler, _signing_secret
    _event_handler = event_handler
    _signing_secret = signing_secret


@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "nightshift-slack"}), 200


@app.before_request
def cache_request_body():
    """Cache the raw request body before Flask parses it"""
    if request.method == 'POST' and not hasattr(request, '_cached_raw_body'):
        request._cached_raw_body = request.get_data(cache=True, as_text=True)


@app.route('/slack/commands', methods=['POST'])
@limiter.limit("10 per minute")
def handle_commands():
    """
    Handle Slack slash commands

    Expected payload:
        command: /nightshift
        text: submit "task description"
        user_id: U123456
        channel_id: C789012
        response_url: https://hooks.slack.com/...
    """
    if not _signing_secret:
        return jsonify({"error": "Server not configured"}), 500

    # Verify signature (handles body caching internally)
    if not _verify_signature():
        return jsonify({"error": "Invalid signature"}), 401

    if not _event_handler:
        return jsonify({"error": "Event handler not initialized"}), 500

    # Parse command
    command = request.form.get('command', '')
    text = request.form.get('text', '').strip()
    user_id = request.form.get('user_id', '')
    channel_id = request.form.get('channel_id', '')
    response_url = request.form.get('response_url', '')

    # Validate command
    if command != '/nightshift':
        return jsonify({
            "response_type": "ephemeral",
            "text": f"Unknown command: {command}"
        }), 400

    # Parse subcommand
    if not text:
        return jsonify({
            "response_type": "ephemeral",
            "text": "Usage: `/nightshift submit \"task description\"`"
        }), 200

    parts = text.split(None, 1)
    subcommand = parts[0].lower() if parts else ''
    args = parts[1] if len(parts) > 1 else ''

    # Route to appropriate handler
    try:
        if subcommand == 'submit':
            return _event_handler.handle_submit(args, user_id, channel_id, response_url)
        elif subcommand == 'queue':
            return _event_handler.handle_queue(args, user_id, channel_id)
        elif subcommand == 'status':
            return _event_handler.handle_status(args, user_id, channel_id)
        elif subcommand == 'cancel':
            return _event_handler.handle_cancel(args, user_id, channel_id)
        elif subcommand == 'pause':
            return _event_handler.handle_pause(args, user_id, channel_id)
        elif subcommand == 'resume':
            return _event_handler.handle_resume(args, user_id, channel_id)
        elif subcommand == 'kill':
            return _event_handler.handle_kill(args, user_id, channel_id)
        else:
            return jsonify({
                "response_type": "ephemeral",
                "text": f"Unknown subcommand: {subcommand}\n\nAvailable commands: submit, queue, status, cancel, pause, resume, kill"
            }), 200

    except Exception as e:
        return jsonify({
            "response_type": "ephemeral",
            "text": f"Error processing command: {str(e)}"
        }), 500


@app.route('/slack/interactions', methods=['POST'])
@limiter.limit("20 per minute")
def handle_interactions():
    """
    Handle Slack interactive components (buttons, modals, etc.)

    Expected payload (JSON in form data):
        type: block_actions
        user: {id, name}
        actions: [{action_id, value}]
        message: {ts}
        channel: {id}
    """
    if not _signing_secret:
        return jsonify({"error": "Server not configured"}), 500

    # Verify signature (handles body caching internally)
    if not _verify_signature():
        return jsonify({"error": "Invalid signature"}), 401

    if not _event_handler:
        return jsonify({"error": "Event handler not initialized"}), 500

    # Parse payload (Slack sends it as form-encoded JSON)
    payload_str = request.form.get('payload', '')
    if not payload_str:
        return jsonify({"error": "Missing payload"}), 400

    try:
        payload = json.loads(payload_str)
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON payload"}), 400

    # Extract components
    interaction_type = payload.get('type', '')
    user = payload.get('user', {})
    user_id = user.get('id', '')
    channel = payload.get('channel', {})
    channel_id = channel.get('id', '')
    message = payload.get('message', {})
    message_ts = message.get('ts', '')

    # Handle different interaction types
    try:
        if interaction_type == 'block_actions':
            actions = payload.get('actions', [])
            if not actions:
                return jsonify({"error": "No actions in payload"}), 400

            action = actions[0]  # Handle first action
            action_id = action.get('action_id', '')
            action_value = action.get('value', '')

            # Route based on action ID
            if action_id.startswith('approve_'):
                return _event_handler.handle_approval(
                    action_value, user_id, channel_id, message_ts, 'approve'
                )
            elif action_id.startswith('reject_'):
                return _event_handler.handle_approval(
                    action_value, user_id, channel_id, message_ts, 'reject'
                )
            elif action_id.startswith('details_'):
                return _event_handler.handle_details(
                    action_value, user_id, channel_id
                )
            else:
                return jsonify({"text": f"Unknown action: {action_id}"}), 200

        elif interaction_type == 'view_submission':
            # Handle modal submissions (for revision workflow, etc.)
            return _event_handler.handle_modal_submission(payload)

        else:
            return jsonify({"error": f"Unsupported interaction type: {interaction_type}"}), 400

    except Exception as e:
        return jsonify({"text": f"Error processing interaction: {str(e)}"}), 500


@app.route('/slack/events', methods=['POST'])
@limiter.limit("50 per minute")
def handle_events():
    """
    Handle Slack Events API (for future use)

    Expected payload:
        type: url_verification (for initial setup)
        challenge: ... (must echo back)

        OR

        type: event_callback
        event: {type, ...}
    """
    if not _signing_secret:
        return jsonify({"error": "Server not configured"}), 500

    # Verify signature
    if not _verify_signature():
        return jsonify({"error": "Invalid signature"}), 401

    # Parse JSON payload
    if not request.is_json:
        return jsonify({"error": "Expected JSON payload"}), 400

    data = request.get_json()
    event_type = data.get('type', '')

    # Handle URL verification (first-time setup)
    if event_type == 'url_verification':
        challenge = data.get('challenge', '')
        return jsonify({"challenge": challenge}), 200

    # Handle other events (not implemented yet)
    return jsonify({"status": "ok"}), 200


def _verify_signature() -> bool:
    """
    Verify Slack request signature

    Returns:
        True if signature is valid, False otherwise
    """
    # Debug ALL request info
    print(f"[DEBUG] Request method: {request.method}")
    print(f"[DEBUG] Request path: {request.path}")
    print(f"[DEBUG] Request content-type: {request.content_type}")
    print(f"[DEBUG] Request content-length: {request.content_length}")

    timestamp = request.headers.get('X-Slack-Request-Timestamp')
    signature = request.headers.get('X-Slack-Signature')

    if not timestamp or not signature:
        print(f"[ERROR] Missing signature headers - timestamp: {timestamp}, signature: {signature}")
        return False

    # Prevent replay attacks
    try:
        current_time = int(time.time())
        request_time = int(timestamp)
        time_diff = abs(current_time - request_time)
        if time_diff > 60 * 5:
            print(f"[ERROR] Request too old - diff: {time_diff}s (max 300s)")
            return False
    except ValueError as e:
        print(f"[ERROR] Invalid timestamp: {e}")
        return False

    # Compute expected signature
    try:
        # Use the cached raw body that was saved in before_request
        if hasattr(request, '_cached_raw_body'):
            request_body = request._cached_raw_body
            print(f"[DEBUG] Using cached raw body: {len(request_body)} chars")
        else:
            # Fallback to get_data (shouldn't happen)
            request_body = request.get_data(cache=True, as_text=True)
            print(f"[DEBUG] Fallback to get_data: {len(request_body)} chars")

        sig_basestring = f"v0:{timestamp}:{request_body}"

        # Debug: show what we're signing
        print(f"[DEBUG] Body length: {len(request_body)}")
        print(f"[DEBUG] Body (first 200 chars): {request_body[:200]}")
        print(f"[DEBUG] Signing secret: {_signing_secret}")

        expected_signature = 'v0=' + hmac.new(
            _signing_secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()

        # Debug output
        print(f"[DEBUG] Received signature: {signature}")
        print(f"[DEBUG] Expected signature: {expected_signature}")

        # Constant-time comparison
        is_valid = hmac.compare_digest(expected_signature, signature)
        if not is_valid:
            print(f"[ERROR] Signature mismatch!")
        return is_valid
    except Exception as e:
        print(f"[ERROR] Signature verification exception: {e}")
        return False
