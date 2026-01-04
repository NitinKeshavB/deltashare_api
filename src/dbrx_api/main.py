from textwrap import dedent

import pydantic
from fastapi import FastAPI
from fastapi.routing import APIRoute
from loguru import logger

from dbrx_api.errors import (
    handle_broad_exceptions,
    handle_pydantic_validation_errors,
)
from dbrx_api.monitoring.logger import configure_logger
from dbrx_api.monitoring.request_context import RequestContextMiddleware
from dbrx_api.routes_health import ROUTER_HEALTH
from dbrx_api.routes_recipient import ROUTER_RECIPIENT
from dbrx_api.routes_share import ROUTER_SHARE
from dbrx_api.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create a FastAPI application."""
    settings = settings or Settings()

    # Reconfigure logger with Azure/PostgreSQL logging if enabled in settings
    configure_logger(
        enable_blob_logging=settings.enable_blob_logging,
        azure_storage_url=settings.azure_storage_account_url,
        blob_container=settings.azure_storage_logs_container,
        enable_postgresql_logging=settings.enable_postgresql_logging,
        postgresql_connection_string=settings.postgresql_connection_string,
        postgresql_table=settings.postgresql_log_table,
        postgresql_min_level=settings.postgresql_min_log_level,
    )

    logger.info("Starting DeltaShare API application", workspace_url=settings.dltshr_workspace_url)

    app = FastAPI(
        title="Delta Share API",
        summary="API for managing Delta Share recipients and shares.",
        version="v1",
        description=dedent(
            """
        ![Maintained by](https://img.shields.io/badge/Maintained_by-EDP%20Delta%20share_Team-green?style=for-the-badge)


        | Helpful Links | Notes |
        | --- | --- |
        | [Delta Share Confluence ](https://jlldigitalproductengineering.atlassian.net/wiki/spaces/DP/pages/20491567149/Enterprise+Delta+Share+Application) |`update-in-progress` |
        | [Delta Share Dev Team](https://jlldigitalproductengineering.atlassian.net/wiki/spaces/DP/pages/20587905070/Delta+Share+team) |`update-in-progress` |
        | [Delta Share CDR Sign off](https://jlldigitalproductengineering.atlassian.net/wiki/spaces/jlltknowledgebase/pages/20324713069/External+Delta+Sharing+Framework+-+Architectural+Design+High+Level) | `signed-off` |
        | [Delta Share Project Repo](https://github.com/JLLT-Apps/JLLT-EDP-DeltaShare) | `Databricks-API-Web repo` |
        | [Delta Share status codes](https://jlldigitalproductengineering.atlassian.net/wiki/spaces/DP/pages/edit-v2/20587249733?draftShareId=a715edeb-f8fc-4c02-90c4-a40ffdff3ecd) | `update-in-progress` |
        | [API Status](https://jlldigitalproductengineering.atlassian.net/wiki/spaces/DP/pages/20587970637/API+Dev+Status) | <img alt="Static Badge" src="https://img.shields.io/badge/Recipient_Done-Green?style=for-the-badge&logoColor=green"> <img alt="Static Badge" src="https://img.shields.io/badge/share_Done-blue?style=for-the-badge&color=blue"> |
        """
        ),
        docs_url="/",  # its easier to find the docs when they live on the base url
        generate_unique_id_function=custom_generate_unique_id,
        swagger_ui_parameters={
            "defaultModelsExpandDepth": -1,  # Hide schemas section
            "defaultModelExpandDepth": 1,  # Keep models collapsed if shown
        },
    )
    app.state.settings = settings

    # Add request context middleware for tracking who/where requests come from
    app.add_middleware(RequestContextMiddleware)

    app.include_router(ROUTER_HEALTH)
    app.include_router(ROUTER_SHARE)
    app.include_router(ROUTER_RECIPIENT)
    app.add_exception_handler(
        exc_class_or_status_code=pydantic.ValidationError,
        handler=handle_pydantic_validation_errors,
    )
    app.middleware("http")(handle_broad_exceptions)

    return app


def custom_generate_unique_id(route: APIRoute):
    """
    Generate prettier `operationId`s in the OpenAPI schema.

    These become the function names in generated client SDKs.
    """
    if route.tags:
        return f"{route.tags[0]}-{route.name}"
    return route.name


if __name__ == "__main__":
    import uvicorn

    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
