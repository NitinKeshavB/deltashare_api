"""Unit tests for dbrx_auth/token_gen.py."""

import json
import os
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from unittest.mock import (
    MagicMock,
    patch,
)

import pytest
import requests

from dbrx_api.dbrx_auth.token_gen import (
    CustomError,
    get_auth_token,
)


class TestGetAuthToken:
    """Tests for get_auth_token function."""

    @patch.dict(
        os.environ,
        {
            "DATABRICKS_TOKEN": "cached_token",
            "TOKEN_EXPIRES_AT_UTC": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        },
    )
    def test_get_auth_token_cached_valid(self):
        """Test returns cached token when still valid."""
        exec_time = datetime.now(timezone.utc)

        token, expires_at = get_auth_token(exec_time)

        assert token == "cached_token"
        assert expires_at > exec_time

    @patch.dict(
        os.environ,
        {
            "DATABRICKS_TOKEN": "cached_token",
            "TOKEN_EXPIRES_AT_UTC": (datetime.now(timezone.utc) + timedelta(minutes=2)).isoformat(),
        },
    )
    @patch("dbrx_api.dbrx_auth.token_gen.requests.post")
    @patch("dbrx_api.dbrx_auth.token_gen._update_env_file")
    def test_get_auth_token_cached_expiring_soon(self, mock_update_env, mock_post):
        """Test refreshes token when cached token expires soon."""
        exec_time = datetime.now(timezone.utc)

        # Set up environment for token refresh
        with patch.dict(
            os.environ,
            {
                "CLIENT_ID": "test_client",
                "CLIENT_SECRET": "test_secret",
                "ACCOUNT_ID": "test_account",
            },
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "new_token",
                "expires_in": 3600,
            }
            mock_post.return_value = mock_response

            token, _ = get_auth_token(exec_time)

            assert token == "new_token"
            mock_post.assert_called_once()

    @patch("dbrx_api.dbrx_auth.token_gen.requests.post")
    @patch("dbrx_api.dbrx_auth.token_gen._update_env_file")
    def test_get_auth_token_no_cache(self, mock_update_env, mock_post):
        """Test generates new token when no cache exists."""
        exec_time = datetime.now(timezone.utc)

        with patch.dict(
            os.environ,
            {
                "CLIENT_ID": "test_client",
                "CLIENT_SECRET": "test_secret",
                "ACCOUNT_ID": "test_account",
                "DATABRICKS_TOKEN": "",
                "TOKEN_EXPIRES_AT_UTC": "",
            },
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "new_token",
                "expires_in": 3600,
            }
            mock_post.return_value = mock_response

            token, expires_at = get_auth_token(exec_time)

            assert token == "new_token"
            assert expires_at > exec_time

    @patch("dbrx_api.dbrx_auth.token_gen.requests.post")
    def test_get_auth_token_missing_credentials(self, mock_post):
        """Test raises error when credentials missing."""
        exec_time = datetime.now(timezone.utc)

        with patch.dict(
            os.environ,
            {
                "CLIENT_ID": "",
                "CLIENT_SECRET": "",
                "ACCOUNT_ID": "",
                "DATABRICKS_TOKEN": "",
                "TOKEN_EXPIRES_AT_UTC": "",
            },
        ):
            with pytest.raises(CustomError) as exc_info:
                get_auth_token(exec_time)

            assert "Missing required environment variables" in str(exc_info.value)

    @patch("dbrx_api.dbrx_auth.token_gen.requests.post")
    def test_get_auth_token_request_fails(self, mock_post):
        """Test raises error when token request fails."""
        exec_time = datetime.now(timezone.utc)

        with patch.dict(
            os.environ,
            {
                "CLIENT_ID": "test_client",
                "CLIENT_SECRET": "test_secret",
                "ACCOUNT_ID": "test_account",
                "DATABRICKS_TOKEN": "",
                "TOKEN_EXPIRES_AT_UTC": "",
            },
        ):
            mock_response = MagicMock()
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_post.return_value = mock_response

            with pytest.raises(CustomError) as exc_info:
                get_auth_token(exec_time)

            assert "Token request failed" in str(exc_info.value)

    @patch("dbrx_api.dbrx_auth.token_gen.requests.post")
    def test_get_auth_token_invalid_json(self, mock_post):
        """Test raises error when response is not valid JSON."""
        exec_time = datetime.now(timezone.utc)

        with patch.dict(
            os.environ,
            {
                "CLIENT_ID": "test_client",
                "CLIENT_SECRET": "test_secret",
                "ACCOUNT_ID": "test_account",
                "DATABRICKS_TOKEN": "",
                "TOKEN_EXPIRES_AT_UTC": "",
            },
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", doc="", pos=0)
            mock_post.return_value = mock_response

            with pytest.raises(CustomError) as exc_info:
                get_auth_token(exec_time)

            assert "Failed to parse" in str(exc_info.value)

    @patch("dbrx_api.dbrx_auth.token_gen.requests.post")
    def test_get_auth_token_no_access_token_in_response(self, mock_post):
        """Test raises error when access_token not in response."""
        exec_time = datetime.now(timezone.utc)

        with patch.dict(
            os.environ,
            {
                "CLIENT_ID": "test_client",
                "CLIENT_SECRET": "test_secret",
                "ACCOUNT_ID": "test_account",
                "DATABRICKS_TOKEN": "",
                "TOKEN_EXPIRES_AT_UTC": "",
            },
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"expires_in": 3600}
            mock_post.return_value = mock_response

            with pytest.raises(CustomError) as exc_info:
                get_auth_token(exec_time)

            assert "Access token not found" in str(exc_info.value)

    @patch("dbrx_api.dbrx_auth.token_gen.requests.post")
    def test_get_auth_token_network_error(self, mock_post):
        """Test raises error on network failure."""
        exec_time = datetime.now(timezone.utc)

        with patch.dict(
            os.environ,
            {
                "CLIENT_ID": "test_client",
                "CLIENT_SECRET": "test_secret",
                "ACCOUNT_ID": "test_account",
                "DATABRICKS_TOKEN": "",
                "TOKEN_EXPIRES_AT_UTC": "",
            },
        ):
            mock_post.side_effect = requests.exceptions.ConnectionError("Network error")

            with pytest.raises(CustomError) as exc_info:
                get_auth_token(exec_time)

            assert "Network error" in str(exc_info.value)

    @patch.dict(
        os.environ,
        {
            "DATABRICKS_TOKEN": "cached_token",
            "TOKEN_EXPIRES_AT_UTC": "invalid_date",
        },
    )
    @patch("dbrx_api.dbrx_auth.token_gen.requests.post")
    @patch("dbrx_api.dbrx_auth.token_gen._update_env_file")
    def test_get_auth_token_invalid_cached_expiry(self, mock_update_env, mock_post):
        """Test refreshes token when cached expiry is invalid."""
        exec_time = datetime.now(timezone.utc)

        with patch.dict(
            os.environ,
            {
                "CLIENT_ID": "test_client",
                "CLIENT_SECRET": "test_secret",
                "ACCOUNT_ID": "test_account",
            },
        ):
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "new_token",
                "expires_in": 3600,
            }
            mock_post.return_value = mock_response

            token, _ = get_auth_token(exec_time)

            assert token == "new_token"


class TestCustomError:
    """Tests for CustomError exception."""

    def test_custom_error_message(self):
        """Test CustomError stores message correctly."""
        error = CustomError("Test error message")
        assert str(error) == "Test error message"

    def test_custom_error_inheritance(self):
        """Test CustomError inherits from Exception."""
        error = CustomError("Test")
        assert isinstance(error, Exception)
