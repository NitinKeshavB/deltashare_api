"""FastAPI dependencies for accessing app state."""

import re
import socket
from typing import (
    List,
    Tuple,
)
from urllib.parse import urlparse

import httpx
from fastapi import (
    Header,
    HTTPException,
    Request,
    status,
)
from loguru import logger

from dbrx_api.dbrx_auth.token_manager import TokenManager
from dbrx_api.settings import Settings

# Valid Databricks workspace URL patterns for different cloud providers
# Azure format: https://adb-<workspace-id>.<region-id>.azuredatabricks.net
# AWS format: https://<workspace-name>.cloud.databricks.com
# GCP format: https://<workspace-name>.gcp.databricks.com
DATABRICKS_URL_PATTERNS: List[str] = [
    r"^https://[a-zA-Z0-9][a-zA-Z0-9.-]*\.azuredatabricks\.net/?$",  # Azure Databricks
    r"^https://[a-zA-Z0-9][a-zA-Z0-9.-]*\.cloud\.databricks\.com/?$",  # AWS Databricks
    r"^https://[a-zA-Z0-9][a-zA-Z0-9.-]*\.gcp\.databricks\.com/?$",  # GCP Databricks
]

# Timeout for workspace reachability check (in seconds)
WORKSPACE_CHECK_TIMEOUT = 5.0


def get_settings(request: Request) -> Settings:
    """
    Get application settings from request state.

    Parameters
    ----------
    request : Request
        FastAPI request object

    Returns
    -------
    Settings
        Application settings instance
    """
    return request.app.state.settings


def get_token_manager(request: Request) -> TokenManager:
    """
    Get token manager from request state.

    The token manager handles cached authentication tokens for Databricks API.

    Parameters
    ----------
    request : Request
        FastAPI request object

    Returns
    -------
    TokenManager
        Token manager instance with cached tokens
    """
    return request.app.state.token_manager


def is_valid_databricks_url(url: str) -> bool:
    """
    Check if a URL matches valid Databricks workspace patterns.

    Parameters
    ----------
    url : str
        URL to validate

    Returns
    -------
    bool
        True if URL matches a valid Databricks pattern, False otherwise
    """
    return any(re.match(pattern, url) for pattern in DATABRICKS_URL_PATTERNS)


async def check_workspace_reachable(url: str) -> Tuple[bool, str]:
    """
    Check if a Databricks workspace URL is reachable.

    Makes a lightweight HEAD request with a short timeout to verify
    the workspace exists and is accessible.

    Parameters
    ----------
    url : str
        Databricks workspace URL to check

    Returns
    -------
    Tuple[bool, str]
        (is_reachable, error_message)
        - (True, "") if workspace is reachable
        - (False, error_message) if workspace is not reachable
    """
    try:
        # Extract hostname for DNS check first (faster failure)
        parsed = urlparse(url)
        hostname = parsed.netloc

        # Quick DNS resolution check
        try:
            socket.gethostbyname(hostname)
        except socket.gaierror:
            return False, f"Workspace hostname '{hostname}' could not be resolved. Please verify the URL is correct."

        # Make a lightweight request to check if workspace responds
        async with httpx.AsyncClient(timeout=WORKSPACE_CHECK_TIMEOUT) as client:
            # Try to access the workspace - even a 401/403 means it exists
            response = await client.head(url, follow_redirects=True)

            # Any response (even 401/403/404) means the server exists
            # We just want to verify it's not a completely fake URL
            logger.debug(
                "Workspace reachability check",
                url=url,
                status_code=response.status_code,
            )
            return True, ""

    except httpx.TimeoutException:
        return False, f"Connection to workspace '{url}' timed out. Please verify the URL is correct and accessible."
    except httpx.ConnectError as e:
        error_str = str(e).lower()
        if "name or service not known" in error_str or "nodename nor servname" in error_str:
            return False, f"Workspace hostname could not be resolved. Please verify the URL '{url}' is correct."
        if "connection refused" in error_str:
            return False, f"Connection to workspace '{url}' was refused. Please verify the URL is correct."
        return False, f"Could not connect to workspace '{url}': {e}"
    except httpx.RequestError as e:
        return False, f"Error connecting to workspace '{url}': {e}"
    except Exception as e:
        logger.warning("Unexpected error during workspace reachability check", url=url, error=str(e))
        # Don't fail on unexpected errors - let the SDK handle it
        return True, ""


async def get_workspace_url(
    x_workspace_url: str = Header(
        ...,
        alias="X-Workspace-URL",
        description="Databricks workspace URL (e.g., https://adb-xxx.azuredatabricks.net)",
        example="https://adb-1234567890123456.12.azuredatabricks.net",
    ),
) -> str:
    """
    Extract and validate the Databricks workspace URL from header.

    Validates that the URL:
    1. Is not empty
    2. Uses HTTPS protocol
    3. Matches a valid Databricks workspace pattern (Azure, AWS, or GCP)
    4. Is reachable (workspace exists and responds)

    Parameters
    ----------
    x_workspace_url : str
        Databricks workspace URL from X-Workspace-URL header

    Returns
    -------
    str
        Validated and normalized workspace URL (trailing slash removed)

    Raises
    ------
    HTTPException
        400 if header is missing, empty, or URL format is invalid
        502 if workspace is not reachable
    """
    if not x_workspace_url or not x_workspace_url.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Workspace-URL header is required",
        )

    # Normalize URL: strip whitespace and trailing slash
    url_normalized = x_workspace_url.strip().rstrip("/")

    # Validate URL uses HTTPS
    if not url_normalized.startswith("https://"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Workspace-URL must be a valid HTTPS URL",
        )

    # Validate URL matches Databricks patterns (Azure, AWS, or GCP)
    if not is_valid_databricks_url(url_normalized):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Invalid Databricks workspace URL format. "
                "Expected patterns: *.azuredatabricks.net (Azure), "
                "*.cloud.databricks.com (AWS), or *.gcp.databricks.com (GCP)"
            ),
        )

    # Check if workspace is reachable (fail fast for non-existent workspaces)
    is_reachable, error_message = await check_workspace_reachable(url_normalized)
    if not is_reachable:
        logger.warning(
            "Workspace reachability check failed",
            url=url_normalized,
            error=error_message,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=error_message,
        )

    return url_normalized


async def verify_subscription_key(
    ocp_apim_subscription_key: str = Header(
        ...,
        alias="Ocp-Apim-Subscription-Key",
        description="Azure API Management subscription key for API authentication",
    ),
) -> str:
    """
    Verify subscription key header is present.

    Azure API Management validates the actual key value externally.
    This dependency ensures the header is present as defense in depth.

    Parameters
    ----------
    ocp_apim_subscription_key : str
        Subscription key from Ocp-Apim-Subscription-Key header

    Returns
    -------
    str
        The subscription key value

    Raises
    ------
    HTTPException
        If header is missing or empty
    """
    if not ocp_apim_subscription_key or not ocp_apim_subscription_key.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Subscription key is required",
        )

    return ocp_apim_subscription_key.strip()
