"""Error handling for FastAPI application and Databricks SDK exceptions."""

import pydantic
from fastapi import (
    Request,
    status,
)
from fastapi.responses import JSONResponse
from loguru import logger

from dbrx_api.monitoring.logger import log_response_info

# Import Databricks SDK exceptions with fallback for when SDK is not available
try:
    from databricks.sdk.errors import (
        BadRequest,
        DatabricksError,
        NotFound,
        PermissionDenied,
        Unauthenticated,
    )

    DATABRICKS_SDK_AVAILABLE = True
except ImportError:
    DATABRICKS_SDK_AVAILABLE = False
    DatabricksError = Exception  # type: ignore[misc, assignment]
    Unauthenticated = Exception  # type: ignore[misc, assignment]
    PermissionDenied = Exception  # type: ignore[misc, assignment]
    NotFound = Exception  # type: ignore[misc, assignment]
    BadRequest = Exception  # type: ignore[misc, assignment]

# Explicit exports
__all__ = [
    "DATABRICKS_SDK_AVAILABLE",
    "DatabricksError",
    "handle_broad_exceptions",
    "handle_databricks_errors",
    "handle_databricks_connection_error",
    "handle_pydantic_validation_errors",
]


# fastapi docs on middlewares: https://fastapi.tiangolo.com/tutorial/middleware/
async def handle_broad_exceptions(request: Request, call_next):
    """Handle any exception that goes unhandled by a more specific exception handler."""
    try:
        return await call_next(request)
    except Exception as err:  # pylint: disable=broad-except
        logger.exception(err)

        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
        log_response_info(response)
        return response


# fastapi docs on error handlers: https://fastapi.tiangolo.com/tutorial/handling-errors/
async def handle_pydantic_validation_errors(request: Request, exc: pydantic.ValidationError) -> JSONResponse:
    """Handle Pydantic validation errors."""
    errors = exc.errors()
    logger.exception(exc)
    response = JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": [
                {
                    "msg": error["msg"],
                    "input": error["input"],
                }
                for error in errors
            ]
        },
    )
    log_response_info(response)

    return response


async def handle_databricks_errors(request: Request, exc: DatabricksError) -> JSONResponse:
    """
    Handle Databricks SDK errors and convert them to appropriate HTTP responses.

    Maps Databricks-specific exceptions to HTTP status codes:
    - Unauthenticated -> 401 Unauthorized
    - PermissionDenied -> 403 Forbidden
    - NotFound -> 404 Not Found
    - BadRequest -> 400 Bad Request
    - Other DatabricksError -> 502 Bad Gateway (upstream service error)

    Parameters
    ----------
    request : Request
        FastAPI request object
    exc : DatabricksError
        Databricks SDK exception

    Returns
    -------
    JSONResponse
        HTTP response with appropriate status code and error details
    """
    error_message = str(exc)
    error_type = type(exc).__name__

    logger.error(
        "Databricks API error",
        error_type=error_type,
        error_message=error_message,
        request_path=request.url.path,
    )

    # Map specific Databricks exceptions to HTTP status codes
    if DATABRICKS_SDK_AVAILABLE:
        if isinstance(exc, Unauthenticated):
            response = JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={
                    "detail": "Databricks authentication failed. Please verify your credentials.",
                    "error_type": error_type,
                },
            )
        elif isinstance(exc, PermissionDenied):
            response = JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={
                    "detail": "Access denied to the requested Databricks resource.",
                    "error_type": error_type,
                },
            )
        elif isinstance(exc, NotFound):
            response = JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    "detail": "The requested Databricks resource was not found.",
                    "error_type": error_type,
                },
            )
        elif isinstance(exc, BadRequest):
            response = JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                content={
                    "detail": f"Invalid request to Databricks: {error_message}",
                    "error_type": error_type,
                },
            )
        else:
            # Generic DatabricksError - treat as upstream service failure
            response = JSONResponse(
                status_code=status.HTTP_502_BAD_GATEWAY,
                content={
                    "detail": f"Databricks service error: {error_message}",
                    "error_type": error_type,
                },
            )
    else:
        # SDK not available, generic error handling
        response = JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Databricks SDK error occurred",
                "error_type": error_type,
            },
        )

    log_response_info(response)
    return response


def handle_databricks_connection_error(error: Exception) -> JSONResponse:
    """
    Handle connection errors when communicating with Databricks workspace.

    This function handles network-level errors that occur when trying to
    connect to a Databricks workspace (timeouts, DNS failures, etc.).

    Parameters
    ----------
    error : Exception
        The connection error exception

    Returns
    -------
    JSONResponse
        503 Service Unavailable response
    """
    error_message = str(error)

    logger.error(
        "Databricks connection error",
        error_message=error_message,
        error_type=type(error).__name__,
    )

    # Check for common connection error patterns
    if "timeout" in error_message.lower():
        detail = "Connection to Databricks workspace timed out. Please try again later."
    elif "name or service not known" in error_message.lower() or "nodename nor servname" in error_message.lower():
        detail = "Unable to resolve Databricks workspace URL. Please verify the URL is correct."
    elif "connection refused" in error_message.lower():
        detail = "Connection to Databricks workspace was refused. Please verify the URL is correct."
    elif "ssl" in error_message.lower() or "certificate" in error_message.lower():
        detail = "SSL/TLS error connecting to Databricks workspace."
    else:
        detail = f"Unable to connect to Databricks workspace: {error_message}"

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "detail": detail,
            "error_type": "ConnectionError",
        },
    )
