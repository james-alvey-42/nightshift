"""
Tests for SlackClient
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from slack_sdk.errors import SlackApiError

from nightshift.integrations.slack_client import SlackClient, SlackResponse


class TestSlackResponse:
    """Tests for SlackResponse wrapper"""

    def test_response_ok_true(self):
        """SlackResponse extracts ok field"""
        response = SlackResponse({"ok": True, "ts": "1234.5678"})

        assert response.ok is True
        assert response.ts == "1234.5678"

    def test_response_ok_false(self):
        """SlackResponse extracts error"""
        response = SlackResponse({"ok": False, "error": "channel_not_found"})

        assert response.ok is False
        assert response.error == "channel_not_found"

    def test_response_with_channel(self):
        """SlackResponse extracts channel"""
        response = SlackResponse({"ok": True, "channel": "C123456"})

        assert response.channel == "C123456"

    def test_response_with_message(self):
        """SlackResponse extracts message"""
        response = SlackResponse({"ok": True, "message": {"text": "hello"}})

        assert response.message == {"text": "hello"}


class TestSlackClientInit:
    """Tests for SlackClient initialization"""

    def test_init_creates_webclient(self):
        """__init__ creates WebClient with token"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_client:
            client = SlackClient("xoxb-test-token")

            mock_client.assert_called_once_with(token="xoxb-test-token")

    def test_init_default_max_retries(self):
        """__init__ uses default max_retries of 3"""
        client = SlackClient("xoxb-test-token")

        assert client.max_retries == 3

    def test_init_custom_max_retries(self):
        """__init__ accepts custom max_retries"""
        client = SlackClient("xoxb-test-token", max_retries=5)

        assert client.max_retries == 5


class TestSlackClientPostMessage:
    """Tests for post_message method"""

    def test_post_message_success(self):
        """post_message calls chat_postMessage"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = MagicMock(
                data={"ok": True, "ts": "1234.5678"}
            )
            mock_cls.return_value = mock_client

            client = SlackClient("xoxb-test")
            response = client.post_message(
                channel="C123",
                text="Hello world"
            )

            mock_client.chat_postMessage.assert_called_once()
            assert response.ok is True
            assert response.ts == "1234.5678"

    def test_post_message_with_blocks(self):
        """post_message passes blocks"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = MagicMock(
                data={"ok": True}
            )
            mock_cls.return_value = mock_client

            client = SlackClient("xoxb-test")
            blocks = [{"type": "section", "text": {"type": "mrkdwn", "text": "Hi"}}]

            client.post_message(channel="C123", text="fallback", blocks=blocks)

            call_kwargs = mock_client.chat_postMessage.call_args[1]
            assert call_kwargs["blocks"] == blocks

    def test_post_message_with_thread(self):
        """post_message passes thread_ts"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat_postMessage.return_value = MagicMock(data={"ok": True})
            mock_cls.return_value = mock_client

            client = SlackClient("xoxb-test")
            client.post_message(
                channel="C123",
                text="Reply",
                thread_ts="1234.5678"
            )

            call_kwargs = mock_client.chat_postMessage.call_args[1]
            assert call_kwargs["thread_ts"] == "1234.5678"


class TestSlackClientUpdateMessage:
    """Tests for update_message method"""

    def test_update_message_success(self):
        """update_message calls chat_update"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat_update.return_value = MagicMock(data={"ok": True})
            mock_cls.return_value = mock_client

            client = SlackClient("xoxb-test")
            response = client.update_message(
                channel="C123",
                ts="1234.5678",
                text="Updated text"
            )

            mock_client.chat_update.assert_called_once()
            assert response.ok is True


class TestSlackClientPostEphemeral:
    """Tests for post_ephemeral method"""

    def test_post_ephemeral_success(self):
        """post_ephemeral calls chat_postEphemeral"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.chat_postEphemeral.return_value = MagicMock(data={"ok": True})
            mock_cls.return_value = mock_client

            client = SlackClient("xoxb-test")
            response = client.post_ephemeral(
                channel="C123",
                user="U456",
                text="Only you can see this"
            )

            mock_client.chat_postEphemeral.assert_called_once()
            call_kwargs = mock_client.chat_postEphemeral.call_args[1]
            assert call_kwargs["user"] == "U456"


class TestSlackClientUploadFile:
    """Tests for upload_file method"""

    def test_upload_file_success(self):
        """upload_file calls files_upload_v2"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.files_upload_v2.return_value = MagicMock(data={"ok": True})
            mock_cls.return_value = mock_client

            client = SlackClient("xoxb-test")
            response = client.upload_file(
                channels="C123",
                file_path="/tmp/test.txt",
                title="Test File"
            )

            mock_client.files_upload_v2.assert_called_once()


class TestSlackClientGetUserInfo:
    """Tests for get_user_info method"""

    def test_get_user_info_success(self):
        """get_user_info returns user dict"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.users_info.return_value = MagicMock(
                data={"ok": True, "user": {"id": "U123", "name": "testuser"}}
            )
            mock_cls.return_value = mock_client

            client = SlackClient("xoxb-test")
            user = client.get_user_info("U123")

            assert user["id"] == "U123"
            assert user["name"] == "testuser"


class TestSlackClientRetryLogic:
    """Tests for retry logic"""

    def test_retry_on_rate_limit(self):
        """_retry_request retries on rate_limited error"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()

            # First call raises rate_limited, second succeeds
            error_response = MagicMock()
            error_response.get.return_value = "rate_limited"
            error_response.headers = {"Retry-After": "1"}

            mock_client.chat_postMessage.side_effect = [
                SlackApiError("rate_limited", error_response),
                MagicMock(data={"ok": True})
            ]
            mock_cls.return_value = mock_client

            with patch("time.sleep"):  # Don't actually sleep
                client = SlackClient("xoxb-test", max_retries=3)
                response = client.post_message(channel="C123", text="test")

            assert response.ok is True
            assert mock_client.chat_postMessage.call_count == 2

    def test_no_retry_on_other_errors(self):
        """_retry_request doesn't retry on non-rate-limit errors"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()

            error_response = MagicMock()
            error_response.get.return_value = "channel_not_found"

            mock_client.chat_postMessage.side_effect = SlackApiError(
                "channel_not_found", error_response
            )
            mock_cls.return_value = mock_client

            client = SlackClient("xoxb-test")

            with pytest.raises(SlackApiError):
                client.post_message(channel="invalid", text="test")

            # Should only try once
            assert mock_client.chat_postMessage.call_count == 1


class TestSlackClientGetChannelInfo:
    """Tests for get_channel_info method"""

    def test_get_channel_info_success(self):
        """get_channel_info returns channel dict"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.conversations_info.return_value = MagicMock(
                data={"ok": True, "channel": {"id": "C123", "name": "general"}}
            )
            mock_cls.return_value = mock_client

            client = SlackClient("xoxb-test")
            channel = client.get_channel_info("C123")

            assert channel["id"] == "C123"
            assert channel["name"] == "general"


class TestSlackClientTestConnection:
    """Tests for test_connection method"""

    def test_connection_success(self):
        """test_connection returns True on success"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.auth_test.return_value = {"ok": True}
            mock_cls.return_value = mock_client

            client = SlackClient("xoxb-test")
            assert client.test_connection() is True

    def test_connection_failure(self):
        """test_connection returns False on failure"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()
            mock_client.auth_test.side_effect = SlackApiError("invalid_auth", MagicMock())
            mock_cls.return_value = mock_client

            client = SlackClient("xoxb-test")
            assert client.test_connection() is False


class TestSlackClientRetryExhaustion:
    """Tests for retry exhaustion scenarios"""

    def test_retry_exhaustion_raises_last_error(self):
        """_retry_request raises last error when all retries exhausted"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()

            # All calls raise rate_limited
            error_response = MagicMock()
            error_response.get.return_value = "rate_limited"
            error_response.headers = {"Retry-After": "1"}

            mock_client.chat_postMessage.side_effect = SlackApiError(
                "rate_limited", error_response
            )
            mock_cls.return_value = mock_client

            with patch("time.sleep"):  # Don't actually sleep
                client = SlackClient("xoxb-test", max_retries=3)

                with pytest.raises(SlackApiError) as exc_info:
                    client.post_message(channel="C123", text="test")

                assert "rate_limited" in str(exc_info.value)

            # Should have tried max_retries times
            assert mock_client.chat_postMessage.call_count == 3

    def test_retry_uses_exponential_backoff_without_retry_after(self):
        """_retry_request uses exponential backoff when no Retry-After header"""
        with patch("nightshift.integrations.slack_client.WebClient") as mock_cls:
            mock_client = MagicMock()

            # First two calls rate limited (no Retry-After), third succeeds
            error_response = MagicMock()
            error_response.get.return_value = "rate_limited"
            error_response.headers = {}  # No Retry-After header

            mock_client.chat_postMessage.side_effect = [
                SlackApiError("rate_limited", error_response),
                SlackApiError("rate_limited", error_response),
                MagicMock(data={"ok": True})
            ]
            mock_cls.return_value = mock_client

            with patch("time.sleep") as mock_sleep:
                client = SlackClient("xoxb-test", max_retries=3)
                response = client.post_message(channel="C123", text="test")

                assert response.ok is True
                # Exponential backoff: 2^0=1s, 2^1=2s
                assert mock_sleep.call_count == 2
                mock_sleep.assert_any_call(1)  # 2^0
                mock_sleep.assert_any_call(2)  # 2^1
