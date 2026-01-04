"""ASGI middleware for dynamic authentication."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from omcp.auth.context import AuthContext
from omcp.auth.dynamic import reset_auth_context, set_current_auth_context
from omcp.auth.errors import AuthError

if TYPE_CHECKING:
    from omcp.auth.dynamic import DynamicAuth


class DynamicAuthMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that extracts auth tokens from HTTP requests.

    This middleware:
    1. Extracts Authorization header from incoming HTTP requests
    2. Validates the token (if validation is enabled)
    3. Sets the auth context for the request duration
    4. Clears the context after the request completes

    The auth context is then available to downstream handlers (like
    httpx auth classes) via get_current_auth_context().
    """

    def __init__(
        self,
        app: Any,
        dynamic_auth: DynamicAuth,
        require_auth: bool = True,
    ) -> None:
        """Initialize the auth middleware.

        Args:
            app: The ASGI application
            dynamic_auth: DynamicAuth provider for token validation
            require_auth: If True, reject requests without valid auth
        """
        super().__init__(app)
        self.dynamic_auth = dynamic_auth
        self.require_auth = require_auth

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Any],
    ) -> Response:
        """Process request with auth context.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler

        Returns:
            The response from downstream handlers
        """
        # Get auth header using configured header name (default: Authorization)
        header_name = self.dynamic_auth.config.header.name or "Authorization"
        auth_header = request.headers.get(header_name)

        # Skip auth for certain paths (health checks, etc.)
        if self._should_skip_auth(request):
            return await call_next(request)

        try:
            # Authenticate the request
            auth_context = await self.dynamic_auth.authenticate(auth_header)

            # Set the context for this request, keeping token for proper reset
            context_token = set_current_auth_context(auth_context)

            try:
                # Process the request
                response = await call_next(request)
                return response
            finally:
                # Reset to previous context value (proper cleanup)
                reset_auth_context(context_token)

        except AuthError as e:
            if not self.require_auth and auth_header is None:
                # No auth provided but not required - proceed without context
                context_token = set_current_auth_context(None)
                try:
                    return await call_next(request)
                finally:
                    reset_auth_context(context_token)

            # Auth required but failed - return error
            return self._create_auth_error_response(e)

    def _should_skip_auth(self, request: Request) -> bool:
        """Check if auth should be skipped for this request.

        Args:
            request: The incoming request

        Returns:
            True if auth should be skipped
        """
        # Skip auth for health check endpoints
        if request.url.path in ("/health", "/healthz", "/_health"):
            return True

        # Skip auth for OPTIONS requests (CORS preflight)
        if request.method == "OPTIONS":
            return True

        return False

    def _create_auth_error_response(self, error: AuthError) -> JSONResponse:
        """Create a JSON-RPC error response for auth failures.

        Args:
            error: The auth error

        Returns:
            JSON-RPC error response
        """
        return JSONResponse(
            status_code=error.status_code,
            content={
                "jsonrpc": "2.0",
                "error": {
                    "code": -32000,  # Server error
                    "message": error.message,
                    "data": error.to_dict(),
                },
                "id": None,
            },
        )


def create_auth_middleware(
    dynamic_auth: DynamicAuth,
    require_auth: bool = True,
) -> type[DynamicAuthMiddleware]:
    """Create an auth middleware class with configuration.

    This factory creates a middleware class that can be added to
    Starlette/FastAPI applications.

    Args:
        dynamic_auth: DynamicAuth provider
        require_auth: If True, reject requests without valid auth

    Returns:
        Configured middleware class
    """

    class ConfiguredAuthMiddleware(DynamicAuthMiddleware):
        def __init__(self, app: Any) -> None:
            super().__init__(
                app=app,
                dynamic_auth=dynamic_auth,
                require_auth=require_auth,
            )

    return ConfiguredAuthMiddleware
