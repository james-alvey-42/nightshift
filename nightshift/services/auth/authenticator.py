"""
Authentication Handler
Validates API keys, OAuth tokens, and JWT tokens for remote access
"""
import hashlib
import hmac
import time
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum


class AuthMethod(Enum):
    """Supported authentication methods"""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    JWT = "jwt"
    PLATFORM_SIGNATURE = "platform_signature"  # For webhook signature verification


@dataclass
class AuthResult:
    """Result of authentication attempt"""
    success: bool
    user_id: Optional[str] = None
    platform: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class Authenticator:
    """
    Handles authentication and authorization for remote triggers

    Supports:
    - API key validation
    - OAuth 2.0 token verification
    - JWT token validation
    - Webhook signature verification (Slack, WhatsApp, etc.)
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize authenticator with configuration

        Args:
            config: Authentication configuration including:
                - method: AuthMethod to use
                - api_keys: Dict of valid API keys to user IDs
                - oauth_config: OAuth 2.0 configuration
                - jwt_config: JWT configuration
                - platform_secrets: Dict of platform signing secrets
        """
        self.config = config
        self.method = AuthMethod(config.get('method', 'api_key'))
        self.api_keys = config.get('api_keys', {})
        self.platform_secrets = config.get('platform_secrets', {})

    def authenticate(
        self,
        credentials: Dict[str, Any],
        method: Optional[AuthMethod] = None
    ) -> AuthResult:
        """
        Authenticate a request

        Args:
            credentials: Authentication credentials (API key, token, etc.)
            method: Override default authentication method

        Returns:
            AuthResult with success status and user information
        """
        auth_method = method or self.method

        if auth_method == AuthMethod.API_KEY:
            return self._authenticate_api_key(credentials)
        elif auth_method == AuthMethod.PLATFORM_SIGNATURE:
            return self._verify_platform_signature(credentials)
        elif auth_method == AuthMethod.OAUTH2:
            return self._authenticate_oauth2(credentials)
        elif auth_method == AuthMethod.JWT:
            return self._authenticate_jwt(credentials)
        else:
            return AuthResult(
                success=False,
                error_message=f"Unsupported authentication method: {auth_method}"
            )

    def _authenticate_api_key(self, credentials: Dict[str, Any]) -> AuthResult:
        """Validate API key"""
        api_key = credentials.get('api_key')

        if not api_key:
            return AuthResult(
                success=False,
                error_message="Missing API key"
            )

        # Look up user ID for this API key
        user_id = self.api_keys.get(api_key)

        if user_id:
            return AuthResult(
                success=True,
                user_id=user_id,
                metadata={'auth_method': 'api_key'}
            )
        else:
            return AuthResult(
                success=False,
                error_message="Invalid API key"
            )

    def _verify_platform_signature(self, credentials: Dict[str, Any]) -> AuthResult:
        """
        Verify webhook signature from messaging platforms

        Supports Slack, WhatsApp, Telegram, Discord signature formats
        """
        platform = credentials.get('platform')
        signature = credentials.get('signature')
        timestamp = credentials.get('timestamp')
        body = credentials.get('body', '')

        if not all([platform, signature, timestamp]):
            return AuthResult(
                success=False,
                error_message="Missing signature verification parameters"
            )

        # Get platform secret
        secret = self.platform_secrets.get(platform)
        if not secret:
            return AuthResult(
                success=False,
                error_message=f"No secret configured for platform: {platform}"
            )

        # Verify signature based on platform
        if platform == 'slack':
            return self._verify_slack_signature(signature, timestamp, body, secret)
        elif platform == 'whatsapp':
            return self._verify_whatsapp_signature(signature, body, secret)
        elif platform == 'telegram':
            return self._verify_telegram_signature(signature, body, secret)
        elif platform == 'discord':
            return self._verify_discord_signature(signature, timestamp, body, secret)
        else:
            return AuthResult(
                success=False,
                error_message=f"Unsupported platform: {platform}"
            )

    def _verify_slack_signature(
        self,
        signature: str,
        timestamp: str,
        body: str,
        secret: str
    ) -> AuthResult:
        """
        Verify Slack request signature
        https://api.slack.com/authentication/verifying-requests-from-slack
        """
        # Check timestamp is recent (within 5 minutes)
        try:
            ts = int(timestamp)
            if abs(time.time() - ts) > 60 * 5:
                return AuthResult(
                    success=False,
                    error_message="Request timestamp too old"
                )
        except ValueError:
            return AuthResult(
                success=False,
                error_message="Invalid timestamp format"
            )

        # Compute signature
        sig_basestring = f"v0:{timestamp}:{body}"
        computed_signature = 'v0=' + hmac.new(
            secret.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()

        # Compare signatures (constant-time comparison)
        if hmac.compare_digest(computed_signature, signature):
            return AuthResult(
                success=True,
                platform='slack',
                metadata={'timestamp': timestamp}
            )
        else:
            return AuthResult(
                success=False,
                error_message="Invalid signature"
            )

    def _verify_whatsapp_signature(
        self,
        signature: str,
        body: str,
        secret: str
    ) -> AuthResult:
        """
        Verify WhatsApp webhook signature
        https://developers.facebook.com/docs/graph-api/webhooks/getting-started
        """
        computed_signature = hmac.new(
            secret.encode(),
            body.encode(),
            hashlib.sha256
        ).hexdigest()

        # WhatsApp sends signature with 'sha256=' prefix
        expected_signature = f"sha256={computed_signature}"

        if hmac.compare_digest(expected_signature, signature):
            return AuthResult(
                success=True,
                platform='whatsapp'
            )
        else:
            return AuthResult(
                success=False,
                error_message="Invalid signature"
            )

    def _verify_telegram_signature(
        self,
        signature: str,
        body: str,
        bot_token: str
    ) -> AuthResult:
        """
        Verify Telegram update signature
        Telegram doesn't use webhook signatures, but validates via secret token
        """
        # Telegram uses a secret token in the webhook URL for validation
        # The signature parameter here would be the token from the URL
        if hmac.compare_digest(signature, bot_token):
            return AuthResult(
                success=True,
                platform='telegram'
            )
        else:
            return AuthResult(
                success=False,
                error_message="Invalid token"
            )

    def _verify_discord_signature(
        self,
        signature: str,
        timestamp: str,
        body: str,
        public_key: str
    ) -> AuthResult:
        """
        Verify Discord interaction signature
        https://discord.com/developers/docs/interactions/receiving-and-responding

        Note: Discord uses Ed25519 signatures, which requires the nacl library
        This is a placeholder that would need the actual implementation
        """
        # TODO: Implement Ed25519 verification with nacl library
        # from nacl.signing import VerifyKey
        # from nacl.exceptions import BadSignatureError

        return AuthResult(
            success=False,
            error_message="Discord signature verification not yet implemented"
        )

    def _authenticate_oauth2(self, credentials: Dict[str, Any]) -> AuthResult:
        """
        Validate OAuth 2.0 token

        Note: This is a placeholder for OAuth2 token validation
        Real implementation would verify with the OAuth provider
        """
        token = credentials.get('access_token')

        if not token:
            return AuthResult(
                success=False,
                error_message="Missing access token"
            )

        # TODO: Implement OAuth2 token verification
        # This would typically involve:
        # 1. Introspecting the token with the OAuth provider
        # 2. Validating scopes and expiration
        # 3. Extracting user information

        return AuthResult(
            success=False,
            error_message="OAuth2 authentication not yet fully implemented"
        )

    def _authenticate_jwt(self, credentials: Dict[str, Any]) -> AuthResult:
        """
        Validate JWT token

        Note: This is a placeholder for JWT validation
        Real implementation would decode and verify the JWT
        """
        token = credentials.get('jwt_token')

        if not token:
            return AuthResult(
                success=False,
                error_message="Missing JWT token"
            )

        # TODO: Implement JWT verification
        # This would typically involve:
        # 1. Decoding the JWT
        # 2. Verifying signature with public key
        # 3. Checking expiration and claims
        # 4. Extracting user information

        return AuthResult(
            success=False,
            error_message="JWT authentication not yet fully implemented"
        )
