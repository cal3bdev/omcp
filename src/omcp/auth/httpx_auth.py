"""Custom httpx Auth for dynamic token injection."""

from __future__ import annotations

from typing import Generator

import httpx

from omcp.auth.dynamic import get_current_auth_context


class DynamicTokenAuth(httpx.Auth):
    """httpx Auth that injects tokens from request context.

    This auth class reads the current auth context (set per-request)
    and adds the token to outgoing HTTP requests. This enables
    dynamic/passthrough authentication where tokens come from
    incoming MCP requests.
    """

    def __init__(
        self,
        header_name: str = "Authorization",
        scheme: str | None = "Bearer",
    ) -> None:
        """Initialize dynamic token auth.

        Args:
            header_name: Name of the header to set
            scheme: Auth scheme (e.g., "Bearer"), or None for raw token
        """
        self.header_name = header_name
        self.scheme = scheme

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """Add auth header from current context to request.

        Args:
            request: The outgoing HTTP request

        Yields:
            The request with auth header added (if token available)
        """
        ctx = get_current_auth_context()

        if ctx and ctx.token:
            # Always use context's header config - it was set during authentication
            # and reflects how the token should be forwarded to upstream
            header_name = ctx.header_name
            scheme = ctx.header_scheme

            # Add the token to the request (with scheme if configured)
            if scheme:
                request.headers[header_name] = f"{scheme} {ctx.token}"
            else:
                request.headers[header_name] = ctx.token

        yield request


class StaticTokenAuth(httpx.Auth):
    """httpx Auth with a static token.

    Used for static auth modes (API key, Bearer token).
    """

    def __init__(
        self,
        token: str,
        header_name: str = "Authorization",
        scheme: str | None = "Bearer",
    ) -> None:
        """Initialize static token auth.

        Args:
            token: The static token to use
            header_name: Name of the header to set
            scheme: Auth scheme (None for raw token, "Bearer" for Bearer token)
        """
        self.token = token
        self.header_name = header_name
        self.scheme = scheme

    def auth_flow(
        self, request: httpx.Request
    ) -> Generator[httpx.Request, httpx.Response, None]:
        """Add static auth header to request.

        Args:
            request: The outgoing HTTP request

        Yields:
            The request with auth header added
        """
        if self.scheme:
            request.headers[self.header_name] = f"{self.scheme} {self.token}"
        else:
            request.headers[self.header_name] = self.token

        yield request
