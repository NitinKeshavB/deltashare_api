"""Settings for the files API."""

from typing import Optional

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class Settings(BaseSettings):
    """
    Settings for the files API.

    [pydantic.BaseSettings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) is a popular
    framework for organizing, validating, and reading configuration values from a variety of sources
    including environment variables.

    This class automatically reads from:
    1. Environment variables (production - Azure Web App Configuration)
    2. .env file (local development)

    All variable names are case-insensitive.
    """

    # Databricks Workspace Configuration
    dltshr_workspace_url: str
    """Databricks Delta Sharing workspace URL (required)."""

    # Databricks Authentication (Service Principal)
    client_id: str
    """Azure Service Principal Client ID for Databricks authentication (required)."""

    client_secret: str
    """Azure Service Principal Client Secret for Databricks authentication (required)."""

    account_id: str
    """Databricks Account ID for authentication (required)."""

    # Optional: Cached authentication token (managed automatically)
    databricks_token: Optional[str] = None
    """Cached Databricks OAuth access token (optional, auto-generated if not provided)."""

    token_expires_at_utc: Optional[str] = None
    """Expiration time for cached token in ISO format (optional, auto-managed)."""

    # Azure Storage for logs
    azure_storage_account_url: Optional[str] = None
    """Azure Storage Account URL for log storage (e.g., https://<account>.blob.core.windows.net)"""

    azure_storage_logs_container: str = "deltashare-logs"
    """Azure Blob Storage container name for logs."""

    enable_blob_logging: bool = False
    """Enable logging to Azure Blob Storage."""

    # PostgreSQL for critical logs
    postgresql_connection_string: Optional[str] = None
    """PostgreSQL connection string for critical log storage."""

    enable_postgresql_logging: bool = False
    """Enable logging to PostgreSQL database."""

    postgresql_log_table: str = "application_logs"
    """PostgreSQL table name for logs."""

    postgresql_min_log_level: str = "WARNING"
    """Minimum log level to store in PostgreSQL (WARNING, ERROR, CRITICAL)."""

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",  # Load from .env file if it exists (local development)
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra environment variables not defined in the model
        # In production, .env file won't exist and pydantic will read from system environment variables
        validate_default=True,  # Validate default values
    )
