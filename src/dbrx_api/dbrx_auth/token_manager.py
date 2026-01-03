"""Centralized token management with caching for Databricks authentication."""

import threading
from datetime import (
    datetime,
    timezone,
)
from typing import (
    Optional,
    Tuple,
)

from loguru import logger

from dbrx_api.dbrx_auth.token_gen import get_auth_token


class TokenManager:
    """
    Thread-safe token manager that caches Databricks OAuth tokens.

    This manager ensures that tokens are reused across all API calls until they expire,
    preventing unnecessary token generation requests.
    """

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        account_id: str,
        cached_token: Optional[str] = None,
        cached_expiry: Optional[str] = None,
    ):
        """
        Initialize the token manager.

        Parameters
        ----------
        client_id : str
            Azure Service Principal Client ID
        client_secret : str
            Azure Service Principal Client Secret
        account_id : str
            Databricks Account ID
        cached_token : Optional[str]
            Previously cached token (from settings/env)
        cached_expiry : Optional[str]
            Expiry time for cached token in ISO format
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id
        self._token: Optional[str] = cached_token
        self._expires_at: Optional[datetime] = None
        self._lock = threading.Lock()

        # Parse cached expiry if provided
        if cached_token and cached_expiry:
            try:
                self._expires_at = datetime.fromisoformat(cached_expiry)
                if self._expires_at.tzinfo is None:
                    self._expires_at = self._expires_at.replace(tzinfo=timezone.utc)
                logger.info(
                    "Token manager initialized with cached token",
                    expires_at=self._expires_at.isoformat(),
                )
            except (ValueError, TypeError) as e:
                logger.warning(f"Failed to parse cached token expiry: {e}")
                self._token = None
                self._expires_at = None

    def get_token(self) -> Tuple[str, datetime]:
        """
        Get a valid authentication token.

        Returns a cached token if it's still valid (expires in more than 5 minutes),
        otherwise generates a new token.

        Returns
        -------
        Tuple[str, datetime]
            A tuple containing:
            - access_token: The OAuth access token
            - expires_at_utc: Expiration time as datetime object in UTC

        Thread-safe: Multiple concurrent requests will share the same token.
        """
        with self._lock:
            now_utc = datetime.now(timezone.utc)

            # Check if cached token is still valid
            if self._token and self._expires_at:
                time_until_expiry = (self._expires_at - now_utc).total_seconds()

                # Reuse token if it expires in more than 5 minutes (300 seconds)
                if time_until_expiry > 300:
                    logger.debug(
                        "Reusing cached token",
                        expires_in_seconds=int(time_until_expiry),
                    )
                    return self._token, self._expires_at

                logger.info(
                    "Cached token expires soon, generating new token",
                    expires_in_seconds=int(time_until_expiry),
                )

            # Generate new token
            logger.info("Generating new authentication token")
            token, expires_at = get_auth_token(now_utc)

            # Cache the new token
            self._token = token
            self._expires_at = expires_at

            logger.info(
                "New token cached successfully",
                expires_at=expires_at.isoformat(),
            )

            return token, expires_at

    @property
    def cached_token(self) -> Optional[str]:
        """Get the currently cached token (if any)."""
        return self._token

    @property
    def cached_expiry(self) -> Optional[datetime]:
        """Get the expiry time of the cached token (if any)."""
        return self._expires_at

    def is_token_valid(self) -> bool:
        """
        Check if the cached token is valid.

        Returns
        -------
        bool
            True if token exists and expires in more than 5 minutes, False otherwise.
        """
        if not self._token or not self._expires_at:
            return False

        now_utc = datetime.now(timezone.utc)
        time_until_expiry = (self._expires_at - now_utc).total_seconds()
        return time_until_expiry > 300

    def invalidate_token(self) -> None:
        """
        Invalidate the cached token.

        This forces a new token to be generated on the next get_token() call.
        Useful for error recovery or manual token refresh.
        """
        with self._lock:
            logger.info("Token invalidated manually")
            self._token = None
            self._expires_at = None
