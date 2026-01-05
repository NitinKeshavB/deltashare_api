"""Azure Key Vault client for loading secrets at application startup.

This module provides functionality to load all secrets from Azure Key Vault
and set them as environment variables. This allows the application to use
the same Settings class regardless of whether secrets come from .env files
(local development) or Key Vault (Azure deployment).

Usage:
    - Local development: Set secrets in .env file, no AZURE_KEYVAULT_URL needed
    - Azure deployment: Set AZURE_KEYVAULT_URL app setting, secrets loaded from Key Vault

Note:
    DLTSHR_WORKSPACE_URL is NOT loaded from Key Vault because it comes from
    the X-Workspace-URL request header per API call.
"""

import os
from typing import (
    Optional,
    Set,
)

from loguru import logger

# Secrets to EXCLUDE from Key Vault loading
# These are either passed per-request (headers) or not sensitive
EXCLUDED_SECRETS: Set[str] = {
    "dltshr-workspace-url",  # Comes from X-Workspace-URL header per request
}


def load_secrets_from_keyvault(vault_url: Optional[str] = None) -> bool:
    """Load all secrets from Azure Key Vault and set as environment variables.

    This function should be called BEFORE initializing the Settings class.
    It loads all secrets from the specified Key Vault and sets them as
    environment variables, converting secret names from hyphen-case to
    UPPER_SNAKE_CASE (e.g., 'client-id' -> 'CLIENT_ID').

    Args:
        vault_url: Azure Key Vault URL. If not provided, reads from
                   AZURE_KEYVAULT_URL environment variable.

    Returns:
        True if secrets were loaded from Key Vault, False if skipped
        (no vault URL configured, using .env file instead).

    Raises:
        Exception: If Key Vault access fails (credentials, permissions, etc.)
    """
    kv_url = vault_url or os.getenv("AZURE_KEYVAULT_URL")

    if not kv_url:
        # Quietly skip Key Vault in local development
        logger.debug("AZURE_KEYVAULT_URL not set, using local environment configuration")
        return False

    try:
        # Import Azure SDK only when needed (not installed in local dev)
        import logging

        from azure.identity import (
            DefaultAzureCredential,
            ManagedIdentityCredential,
        )
        from azure.keyvault.secrets import SecretClient

        # Suppress verbose Azure SDK logging in production
        logging.getLogger("azure.identity").setLevel(logging.ERROR)
        logging.getLogger("azure.core.pipeline.policies").setLevel(logging.ERROR)

        logger.info(f"Loading secrets from Azure Key Vault: {kv_url}")

        # Use ManagedIdentityCredential in Azure Web App (faster, no credential chain noise)
        # Fall back to DefaultAzureCredential for local development
        if os.getenv("WEBSITE_INSTANCE_ID"):
            # Running in Azure App Service - use Managed Identity directly
            credential = ManagedIdentityCredential()
            logger.debug("Using ManagedIdentityCredential for Azure App Service")
        else:
            # Local development - use DefaultAzureCredential (supports az login, etc.)
            credential = DefaultAzureCredential(exclude_visual_studio_code_credential=True)
            logger.debug("Using DefaultAzureCredential for local development")

        client = SecretClient(vault_url=kv_url, credential=credential)

        secrets_loaded = 0

        # List and load secrets from Key Vault (excluding header-based configs)
        for secret_properties in client.list_properties_of_secrets():
            secret_name = secret_properties.name.lower()

            # Skip excluded secrets (e.g., workspace URL comes from header)
            if secret_name in EXCLUDED_SECRETS:
                logger.debug(f"Skipping excluded secret: {secret_properties.name} (loaded from request header)")
                continue

            if not secret_properties.enabled:
                logger.debug(f"Skipping disabled secret: {secret_properties.name}")
                continue

            try:
                # Get the secret value
                secret = client.get_secret(secret_properties.name)

                if secret.value is None:
                    logger.warning(f"Secret '{secret_properties.name}' has no value, skipping")
                    continue

                # Convert secret name to environment variable format
                # "client-id" -> "CLIENT_ID"
                env_var_name = secret_properties.name.replace("-", "_").upper()

                # Set as environment variable
                os.environ[env_var_name] = secret.value
                secrets_loaded += 1

                logger.debug(f"Loaded secret: {secret_properties.name} -> {env_var_name}")

            except Exception as e:
                logger.error(f"Failed to load secret '{secret_properties.name}': {e}")
                raise

        logger.info(f"Successfully loaded {secrets_loaded} secrets from Key Vault")
        return True

    except ImportError as e:
        logger.error("Azure SDK not installed. Install with: pip install azure-keyvault-secrets azure-identity")
        raise ImportError(
            "Azure Key Vault SDK not installed. " "Install with: pip install deltashare_api[azure]"
        ) from e

    except Exception as e:
        logger.error(f"Failed to load secrets from Key Vault: {e}")
        raise


def get_secret_from_keyvault(
    secret_name: str,
    vault_url: Optional[str] = None,
) -> Optional[str]:
    """Get a single secret from Azure Key Vault.

    This is useful for fetching secrets on-demand rather than at startup.

    Args:
        secret_name: Name of the secret in Key Vault (use hyphens, e.g., 'client-id')
        vault_url: Azure Key Vault URL. If not provided, reads from
                   AZURE_KEYVAULT_URL environment variable.

    Returns:
        The secret value, or None if Key Vault is not configured.

    Raises:
        Exception: If Key Vault access fails or secret not found.
    """
    kv_url = vault_url or os.getenv("AZURE_KEYVAULT_URL")

    if not kv_url:
        return None

    import logging

    from azure.identity import (
        DefaultAzureCredential,
        ManagedIdentityCredential,
    )
    from azure.keyvault.secrets import SecretClient

    # Suppress verbose Azure SDK logging
    logging.getLogger("azure.identity").setLevel(logging.ERROR)
    logging.getLogger("azure.core.pipeline.policies").setLevel(logging.ERROR)

    # Use ManagedIdentityCredential in Azure, DefaultAzureCredential locally
    if os.getenv("WEBSITE_INSTANCE_ID"):
        credential = ManagedIdentityCredential()
    else:
        credential = DefaultAzureCredential(exclude_visual_studio_code_credential=True)

    client = SecretClient(vault_url=kv_url, credential=credential)

    secret = client.get_secret(secret_name)
    return secret.value
