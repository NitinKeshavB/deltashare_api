"""Settings for the files API."""

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

    model_config = SettingsConfigDict(case_sensitive=False)
