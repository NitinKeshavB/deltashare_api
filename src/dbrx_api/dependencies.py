"""FastAPI dependencies for accessing app state."""

from fastapi import Request

from dbrx_api.dbrx_auth.token_manager import TokenManager
from dbrx_api.settings import Settings


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
