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
    """

    dltshr_workspace_url: str
    """Databricks Delta Sharing workspace URL."""

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

    model_config = SettingsConfigDict(case_sensitive=False)
