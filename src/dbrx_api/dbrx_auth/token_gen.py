"""Module for generating Databricks authentication token."""

import base64
import json
import os
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
from typing import Tuple

import requests
from dotenv import load_dotenv

# Conditionally load from .env file if it exists (local development)
# In production (Azure Web App), environment variables are loaded from Key Vault at startup
env_file = Path(__file__).parent.parent.parent.parent / ".env"
if env_file.exists():
    load_dotenv(env_file)
    print(f"✓ Loaded environment variables from {env_file}")
else:
    print("⚠ No .env file found - using web app environment variables")

# NOTE: Don't load credentials at import time - they may not be available yet
# (Key Vault secrets are loaded in create_app() before Settings initialization)
# Instead, read from os.getenv() when needed in get_auth_token()


class CustomError(Exception):
    """Custom exception for token generation failures."""


def _update_env_file(key: str, value: str) -> None:
    """
    Update or add a key-value pair in the .env file.

    Parameters
    ----------
    key : str
        Environment variable name
    value : str
        Environment variable value

    """
    # Find the .env file (look in current directory and parent directories)
    env_path = None
    current_dir = Path(__file__).parent

    for _ in range(5):  # Search up to 5 levels up
        potential_env = current_dir / ".env"
        if potential_env.exists():
            env_path = potential_env
            break
        current_dir = current_dir.parent

    if not env_path:
        # If .env doesn't exist, create it in the project root
        env_path = Path(__file__).parent.parent.parent.parent / ".env"

    # Read existing content
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8") as f:
            content = f.read()
    else:
        content = ""

    # Parse existing lines
    lines = content.splitlines(keepends=True)
    if not lines or not content.endswith("\n"):
        # Ensure last line has newline
        if lines:
            lines[-1] = lines[-1].rstrip("\n") + "\n"

    # Update or add the key (quote values with special characters)
    key_found = False
    quoted_value = f'"{value}"' if " " in value or "\n" in value else value

    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={quoted_value}\n"
            key_found = True
            break

    if not key_found:
        lines.append(f"{key}={quoted_value}\n")

    # Write back to file
    with open(env_path, "w", encoding="utf-8") as f:
        f.writelines(lines)


def get_auth_token(exec_time_utc: datetime) -> Tuple[str, datetime]:
    """
    Generate an authentication token for Databricks API.

    Parameters
    ----------
    exec_time_utc : datetime
        Current execution time in UTC

    Returns
    -------
    Tuple[str, datetime]
        A tuple containing:
        - access_token: The OAuth access token
        - expires_at_utc: Expiration time as datetime object in UTC

    Raises
    ------
    CustomError
        If token generation fails for any reason

    """
    try:
        # Check if cached token exists and is still valid (try lowercase first, then uppercase for backward compatibility)
        cached_token = os.environ.get("databricks_token") or os.environ.get("DATABRICKS_TOKEN")
        cached_expiry = os.environ.get("token_expires_at_utc") or os.environ.get("TOKEN_EXPIRES_AT_UTC")

        if cached_token and cached_expiry:
            try:
                # Parse the cached expiry time
                expires_at_utc = datetime.fromisoformat(cached_expiry)

                # Ensure expires_at_utc has timezone info
                if expires_at_utc.tzinfo is None:
                    expires_at_utc = expires_at_utc.replace(tzinfo=timezone.utc)

                # Check if token expires in more than 5 minutes (300 seconds)
                time_until_expiry = (expires_at_utc - exec_time_utc).total_seconds()

                if time_until_expiry > 300:
                    expires_msg = f"expires in {int(time_until_expiry)} seconds"
                    print(f"\n✓ Using cached token ({expires_msg})")
                    return cached_token, expires_at_utc

                print("\n⚠ Cached token expires soon, generating new token...")
            except (ValueError, TypeError) as e:
                print(f"\n⚠ Error parsing cached token, generating new: {e}")
        # Read credentials from environment (case-insensitive - try lowercase first, then uppercase for backward compatibility)
        client_id = os.getenv("client_id") or os.getenv("CLIENT_ID")
        client_secret = os.getenv("client_secret") or os.getenv("CLIENT_SECRET")
        account_id = os.getenv("account_id") or os.getenv("ACCOUNT_ID")

        # Validate required environment variables
        if not all([client_id, client_secret, account_id]):
            raise CustomError(
                "Missing required environment variables: client_id, client_secret, or account_id. "
                "Ensure these are set in Azure App Configuration as lowercase variables."
            )

        url = f"https://accounts.azuredatabricks.net/oidc/accounts/{account_id}/v1/token"

        # Prepare request payload
        payload = {"grant_type": "client_credentials", "scope": "all-apis"}

        # Encode credentials for Basic authentication
        credentials = f"{client_id}:{client_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()

        headers = {"Authorization": f"Basic {encoded_credentials}"}

        # Get current UTC time
        created_at_utc = datetime.now(timezone.utc)

        # Send token request
        response = requests.post(url, headers=headers, data=payload, timeout=30)

        # Check response status
        if response.status_code != 200:
            raise CustomError(f"Token request failed with status {response.status_code}: " f"{response.text}")

        # Parse response
        try:
            token_data = response.json()
        except json.JSONDecodeError as e:
            raise CustomError(f"Failed to parse token response as JSON: {e}") from e

        # Extract token information
        access_token = token_data.get("access_token")
        token_expiry = token_data.get("expires_in", 3600)

        if not access_token:
            raise CustomError("Access token not found in response")

        # Calculate expiration time in UTC
        expires_at_utc = created_at_utc + timedelta(seconds=token_expiry)

        # Store token in environment variables (as string for persistence) - use lowercase
        os.environ["databricks_token"] = access_token
        os.environ["token_expires_at_utc"] = expires_at_utc.isoformat()

        # Persist to .env file for cross-process caching
        _update_env_file("databricks_token", access_token)
        _update_env_file("token_expires_at_utc", expires_at_utc.isoformat())

        return access_token, expires_at_utc

    except requests.exceptions.RequestException as e:
        raise CustomError(f"Network error during token request: {e}") from e
    except Exception as e:
        if isinstance(e, CustomError):
            raise
        raise CustomError(f"Unexpected error during token generation: {e}") from e
