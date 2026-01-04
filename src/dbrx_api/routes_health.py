"""Health check endpoints for monitoring application status."""

from datetime import (
    datetime,
    timezone,
)

from fastapi import (
    APIRouter,
    Request,
    status,
)
from fastapi.responses import JSONResponse
from loguru import logger

ROUTER_HEALTH = APIRouter(tags=["Health"])


@ROUTER_HEALTH.get(
    "/health",
    summary="Health check endpoint",
    description="Basic health check that returns application status and metadata",
    responses={
        status.HTTP_200_OK: {
            "description": "Application is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "timestamp": "2026-01-05T12:00:00.000000Z",
                        "service": "Delta Share API",
                        "version": "v1",
                    }
                }
            },
        }
    },
)
async def health_check(request: Request):
    """
    Basic health check endpoint.

    Returns application status and metadata. This endpoint is lightweight
    and does not perform any external dependency checks.

    Used by:
    - Azure Web App health monitoring
    - Load balancers
    - Kubernetes liveness probes
    """
    settings = request.app.state.settings

    response_data = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "Delta Share API",
        "version": "v1",
        "workspace_url": settings.dltshr_workspace_url,
    }

    logger.debug("Health check requested", status="healthy")

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response_data,
    )


@ROUTER_HEALTH.get(
    "/health/ready",
    summary="Readiness check endpoint",
    description="Readiness check that verifies the application can access critical dependencies",
    responses={
        status.HTTP_200_OK: {
            "description": "Application is ready to serve requests",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ready",
                        "timestamp": "2026-01-05T12:00:00.000000Z",
                        "service": "Delta Share API",
                        "checks": {
                            "settings": "ok",
                            "authentication": "ok",
                        },
                    }
                }
            },
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Application is not ready to serve requests",
            "content": {
                "application/json": {
                    "example": {
                        "status": "not_ready",
                        "timestamp": "2026-01-05T12:00:00.000000Z",
                        "service": "Delta Share API",
                        "checks": {
                            "settings": "ok",
                            "authentication": "failed",
                        },
                        "error": "Authentication configuration missing",
                    }
                }
            },
        },
    },
)
async def readiness_check(request: Request):
    """
    Readiness check endpoint.

    Verifies that the application is ready to serve requests by checking:
    - Settings are loaded
    - Authentication credentials are configured

    Used by:
    - Kubernetes readiness probes
    - Load balancers to determine if instance should receive traffic
    """
    settings = request.app.state.settings

    checks = {
        "settings": "ok",
        "authentication": "ok",
    }

    is_ready = True
    error_message = None

    # Check if critical settings are configured
    if not settings.dltshr_workspace_url:
        checks["settings"] = "failed"
        is_ready = False
        error_message = "Workspace URL not configured"

    # Check if authentication credentials are configured
    if not all([settings.client_id, settings.client_secret, settings.account_id]):
        checks["authentication"] = "failed"
        is_ready = False
        error_message = "Authentication credentials not configured"

    response_data = {
        "status": "ready" if is_ready else "not_ready",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service": "Delta Share API",
        "checks": checks,
    }

    if error_message:
        response_data["error"] = error_message

    response_status = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    logger.debug(
        "Readiness check requested",
        status=response_data["status"],
        checks=checks,
        is_ready=is_ready,
    )

    return JSONResponse(
        status_code=response_status,
        content=response_data,
    )


@ROUTER_HEALTH.get(
    "/health/live",
    summary="Liveness check endpoint",
    description="Simple liveness check to verify the application is running",
    responses={
        status.HTTP_200_OK: {
            "description": "Application is alive",
            "content": {
                "application/json": {
                    "example": {
                        "status": "alive",
                        "timestamp": "2026-01-05T12:00:00.000000Z",
                    }
                }
            },
        }
    },
)
async def liveness_check():
    """
    Liveness check endpoint.

    Minimal endpoint that simply returns OK if the application process is running.
    This endpoint performs no dependency checks and should always succeed if the
    application is running.

    Used by:
    - Kubernetes liveness probes
    - Container orchestration platforms to determine if app should be restarted
    """
    response_data = {
        "status": "alive",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=response_data,
    )
