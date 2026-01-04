"""Custom httpx Auth for static token injection."""

from __future__ import annotations

from typing import Generator

import httpx


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
