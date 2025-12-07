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

    s3_bucket_name: str
    """Name of the S3 bucket used by this API as the underlying file store."""

    model_config = SettingsConfigDict(case_sensitive=False)
