"""Request context middleware for logging."""
from contextvars import ContextVar
from typing import (
    Any,
    Callable,
)

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

# Context variables to store request-specific data
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
client_ip_ctx: ContextVar[str] = ContextVar("client_ip", default="")
user_identity_ctx: ContextVar[str] = ContextVar("user_identity", default="")
user_agent_ctx: ContextVar[str] = ContextVar("user_agent", default="")
request_path_ctx: ContextVar[str] = ContextVar("request_path", default="")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Middleware to capture and log request context information."""

    async def dispatch(self, request: Request, call_next: Callable) -> Any:
        """
        Capture request context and add to logging.

        Captures:
        - Request ID (from header or generated)
        - Client IP (real IP from Azure headers or direct)
        - User identity (from Azure AD, API key, or custom auth)
        - User agent (browser/client info)
        - Request path and method
        """
        # Generate or get request ID
        request_id = request.headers.get("X-Request-ID", self._generate_request_id())
        request_id_ctx.set(request_id)

        # Get real client IP (Azure Web App headers)
        client_ip = self._get_client_ip(request)
        client_ip_ctx.set(client_ip)

        # Get user identity (multiple sources)
        user_identity = self._get_user_identity(request)
        user_identity_ctx.set(user_identity)

        # Get user agent
        user_agent = request.headers.get("User-Agent", "unknown")
        user_agent_ctx.set(user_agent)

        # Get request path
        request_path = f"{request.method} {request.url.path}"
        request_path_ctx.set(request_path)

        # Configure logger with context
        with logger.contextualize(
            request_id=request_id,
            client_ip=client_ip,
            user_identity=user_identity,
            user_agent=user_agent,
            request_path=request_path,
            referer=request.headers.get("Referer", "direct"),
            origin=request.headers.get("Origin", "unknown"),
        ):
            # Log the incoming request with full details
            logger.info(
                "Incoming request",
                method=request.method,
                path=request.url.path,
                query_params=str(request.query_params),
                # Additional structured fields for external tables
                event_type="request_received",
                http_method=request.method,
                url_path=str(request.url.path),
                url_query=str(request.query_params) if request.query_params else None,
                http_version=request.scope.get("http_version", "1.1"),
                content_type=request.headers.get("Content-Type"),
                content_length=request.headers.get("Content-Length"),
            )

            # Process request and capture timing
            import time

            start_time = time.time()
            response = await call_next(request)
            duration_ms = (time.time() - start_time) * 1000

            # Log the response with full details
            logger.info(
                "Request completed",
                status_code=response.status_code,
                # Additional structured fields for external tables
                event_type="request_completed",
                http_status=response.status_code,
                response_time_ms=round(duration_ms, 2),
                response_content_type=response.headers.get("content-type"),
                response_content_length=response.headers.get("content-length"),
            )

            return response

    def _get_client_ip(self, request: Request) -> str:
        """
        Get real client IP address.

        Azure Web App provides these headers:
        - X-Forwarded-For: Original client IP
        - X-Azure-ClientIP: Client IP from Azure
        - X-Forwarded-Host: Original host
        """
        # Try Azure-specific headers first
        client_ip = request.headers.get("X-Azure-ClientIP")
        if client_ip:
            return client_ip

        # Try standard forwarded headers
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # X-Forwarded-For can contain multiple IPs, take the first one
            return forwarded_for.split(",")[0].strip()

        # Fallback to direct client
        if request.client:
            return request.client.host

        return "unknown"

    def _get_user_identity(self, request: Request) -> str:
        """
        Get user identity from multiple sources.

        Priority order:
        1. Azure AD authentication (Easy Auth headers)
        2. Custom authorization header (Bearer token)
        3. API key header
        4. Client certificate (for mTLS)
        5. Anonymous
        """
        # Azure AD / Easy Auth headers
        # When Azure App Service Authentication is enabled, these headers are automatically added
        azure_user_principal = request.headers.get("X-MS-CLIENT-PRINCIPAL-NAME")
        if azure_user_principal:
            azure_user_id = request.headers.get("X-MS-CLIENT-PRINCIPAL-ID", "")
            return f"{azure_user_principal} ({azure_user_id})" if azure_user_id else azure_user_principal

        # Check for Bearer token (you'd decode this in real implementation)
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            # In production, decode JWT token to get user info
            # For now, just indicate it's a bearer token user
            token_preview = auth_header[7:27] + "..."  # First 20 chars
            return f"bearer_token:{token_preview}"

        # Check for API key header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            # In production, look up API key owner in database
            key_preview = api_key[:8] + "..." if len(api_key) > 8 else api_key
            return f"api_key:{key_preview}"

        # Check for client certificate (mTLS)
        client_cert = request.headers.get("X-ARR-ClientCert")  # Azure App Service header
        if client_cert:
            return "mtls:certificate_auth"

        # Anonymous access
        return "anonymous"

    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        import uuid

        return str(uuid.uuid4())


def get_request_context() -> dict:
    """
    Get current request context for logging.

    Returns:
        Dictionary with request context variables
    """
    return {
        "request_id": request_id_ctx.get(),
        "client_ip": client_ip_ctx.get(),
        "user_identity": user_identity_ctx.get(),
        "user_agent": user_agent_ctx.get(),
        "request_path": request_path_ctx.get(),
    }
