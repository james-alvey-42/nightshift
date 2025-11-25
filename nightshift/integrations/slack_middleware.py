"""
Slack Middleware
Signature verification and rate limiting for webhook requests
"""
import hmac
import hashlib
import time
from flask import request
from functools import wraps
from typing import Callable


def verify_slack_signature(signing_secret: str) -> Callable:
    """
    Decorator to verify Slack request signatures

    Args:
        signing_secret: Slack signing secret from app settings

    Returns:
        Decorator function

    Usage:
        @app.route('/slack/commands', methods=['POST'])
        @verify_slack_signature(config.slack_signing_secret)
        def handle_commands():
            ...
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapper(*args, **kwargs):
            # Get signature components from headers
            timestamp = request.headers.get('X-Slack-Request-Timestamp')
            signature = request.headers.get('X-Slack-Signature')

            if not timestamp or not signature:
                return {"error": "Missing signature headers"}, 401

            # Prevent replay attacks (reject requests older than 5 minutes)
            current_time = int(time.time())
            if abs(current_time - int(timestamp)) > 60 * 5:
                return {"error": "Request timestamp too old"}, 401

            # Compute expected signature
            sig_basestring = f"v0:{timestamp}:{request.get_data().decode('utf-8')}"
            expected_signature = 'v0=' + hmac.new(
                signing_secret.encode(),
                sig_basestring.encode(),
                hashlib.sha256
            ).hexdigest()

            # Compare signatures (constant-time comparison)
            if not hmac.compare_digest(expected_signature, signature):
                return {"error": "Invalid signature"}, 401

            # Signature valid, proceed with request
            return f(*args, **kwargs)

        return wrapper
    return decorator


def extract_user_id() -> str:
    """
    Extract user ID from Slack request for rate limiting

    Returns:
        User ID from form data or IP address as fallback
    """
    # Try to get user_id from form (slash commands)
    if request.form:
        user_id = request.form.get('user_id')
        if user_id:
            return user_id

    # Try to get from JSON payload (interactions)
    if request.is_json:
        data = request.get_json(silent=True) or {}
        user_data = data.get('user', {})
        if user_data and 'id' in user_data:
            return user_data['id']

    # Fallback to IP address
    return request.remote_addr or 'unknown'
