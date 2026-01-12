"""Unit tests for dbrx_auth/token_manager.py."""

from datetime import (
    datetime,
    timedelta,
    timezone,
)
from unittest.mock import patch

import pytest

from dbrx_api.dbrx_auth.token_manager import TokenManager


class TestTokenManagerInit:
    """Tests for TokenManager initialization."""

    def test_init_without_cache(self):
        """Test initialization without cached token."""
        manager = TokenManager(
            client_id="test_client",
            client_secret="test_secret",
            account_id="test_account",
        )

        assert manager.client_id == "test_client"
        assert manager.cached_token is None
        assert manager.cached_expiry is None

    def test_init_with_valid_cache(self):
        """Test initialization with valid cached token."""
        expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

        manager = TokenManager(
            client_id="test_client",
            client_secret="test_secret",
            account_id="test_account",
            cached_token="cached_token",
            cached_expiry=expiry,
        )

        assert manager.cached_token == "cached_token"
        assert manager.cached_expiry is not None

    def test_init_with_invalid_cache_expiry(self):
        """Test initialization with invalid expiry format."""
        manager = TokenManager(
            client_id="test_client",
            client_secret="test_secret",
            account_id="test_account",
            cached_token="cached_token",
            cached_expiry="invalid_date",
        )

        # Invalid expiry should clear both token and expiry
        assert manager.cached_token is None
        assert manager.cached_expiry is None

    def test_init_with_naive_datetime(self):
        """Test initialization with naive datetime (no timezone)."""
        expiry = datetime.now().isoformat()  # naive datetime

        manager = TokenManager(
            client_id="test_client",
            client_secret="test_secret",
            account_id="test_account",
            cached_token="cached_token",
            cached_expiry=expiry,
        )

        # Should add UTC timezone
        assert manager.cached_expiry is not None
        assert manager.cached_expiry.tzinfo == timezone.utc


class TestTokenManagerGetToken:
    """Tests for TokenManager.get_token method."""

    @patch("dbrx_api.dbrx_auth.token_manager.get_auth_token")
    def test_get_token_no_cache(self, mock_get_auth):
        """Test getting token when no cache exists."""
        mock_get_auth.return_value = (
            "new_token",
            datetime.now(timezone.utc) + timedelta(hours=1),
        )

        manager = TokenManager(
            client_id="test_client",
            client_secret="test_secret",
            account_id="test_account",
        )

        token, expiry = manager.get_token()

        assert token == "new_token"
        mock_get_auth.assert_called_once()

    def test_get_token_valid_cache(self):
        """Test getting token when valid cache exists."""
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        manager = TokenManager(
            client_id="test_client",
            client_secret="test_secret",
            account_id="test_account",
            cached_token="cached_token",
            cached_expiry=expiry.isoformat(),
        )

        with patch("dbrx_api.dbrx_auth.token_manager.get_auth_token") as mock_get_auth:
            token, _ = manager.get_token()

            assert token == "cached_token"
            mock_get_auth.assert_not_called()

    @patch("dbrx_api.dbrx_auth.token_manager.get_auth_token")
    def test_get_token_expiring_soon(self, mock_get_auth):
        """Test getting token when cached token expires soon."""
        expiry = datetime.now(timezone.utc) + timedelta(minutes=2)  # Less than 5 min

        mock_get_auth.return_value = (
            "new_token",
            datetime.now(timezone.utc) + timedelta(hours=1),
        )

        manager = TokenManager(
            client_id="test_client",
            client_secret="test_secret",
            account_id="test_account",
            cached_token="old_token",
            cached_expiry=expiry.isoformat(),
        )

        token, _ = manager.get_token()

        assert token == "new_token"
        mock_get_auth.assert_called_once()


class TestTokenManagerProperties:
    """Tests for TokenManager properties."""

    def test_cached_token_property(self):
        """Test cached_token property."""
        manager = TokenManager(
            client_id="test_client",
            client_secret="test_secret",
            account_id="test_account",
            cached_token="my_token",
            cached_expiry=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        )

        assert manager.cached_token == "my_token"

    def test_cached_expiry_property(self):
        """Test cached_expiry property."""
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        manager = TokenManager(
            client_id="test_client",
            client_secret="test_secret",
            account_id="test_account",
            cached_token="my_token",
            cached_expiry=expiry.isoformat(),
        )

        assert manager.cached_expiry is not None


class TestTokenManagerIsTokenValid:
    """Tests for TokenManager.is_token_valid method."""

    @pytest.mark.parametrize(
        "token,expiry_delta,expected",
        [
            (None, None, False),  # No token
            ("old_token", timedelta(minutes=-1), False),  # Expired
            ("expiring_token", timedelta(minutes=2), False),  # Expires soon (<5 min)
            ("valid_token", timedelta(hours=1), True),  # Valid
            ("valid_token", timedelta(minutes=10), True),  # Valid (>5 min)
        ],
        ids=["no_token", "expired", "expiring_soon", "valid_1h", "valid_10min"],
    )
    def test_is_token_valid(self, token, expiry_delta, expected: bool):
        """Test token validity for various scenarios."""
        expiry = None
        if expiry_delta is not None:
            expiry = (datetime.now(timezone.utc) + expiry_delta).isoformat()

        manager = TokenManager(
            client_id="test_client",
            client_secret="test_secret",
            account_id="test_account",
            cached_token=token,
            cached_expiry=expiry,
        )

        assert manager.is_token_valid() is expected


class TestTokenManagerInvalidate:
    """Tests for TokenManager.invalidate_token method."""

    def test_invalidate_token(self):
        """Test invalidating cached token."""
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        manager = TokenManager(
            client_id="test_client",
            client_secret="test_secret",
            account_id="test_account",
            cached_token="my_token",
            cached_expiry=expiry.isoformat(),
        )

        assert manager.cached_token is not None

        manager.invalidate_token()

        assert manager.cached_token is None
        assert manager.cached_expiry is None
