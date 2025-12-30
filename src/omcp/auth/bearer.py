"""Bearer token authentication provider."""

from __future__ import annotations

from omcp.auth.base import AuthProvider


class BearerAuth(AuthProvider):
    """Bearer token authentication provider.

    Sends token in Authorization header as "Bearer <token>".
    """

    def __init__(
        self,
        token: str,
        header_name: str = "Authorization",
        prefix: str = "Bearer",
    ) -> None:
        """Initialize bearer auth.

        Args:
            token: The bearer token value
            header_name: Header name (default: Authorization)
            prefix: Token prefix (default: Bearer)
        """
        self._token = token
        self._header_name = header_name
        self._prefix = prefix

    async def get_headers(self) -> dict[str, str]:
        """Get Authorization header with bearer token."""
        return {self._header_name: f"{self._prefix} {self._token}"}

    def get_headers_sync(self) -> dict[str, str]:
        """Sync version - no async needed for static token."""
        return {self._header_name: f"{self._prefix} {self._token}"}

    async def refresh(self) -> None:
        """No-op for static bearer tokens."""
        pass

    def is_valid(self) -> bool:
        """Bearer token is valid if it exists and is non-empty."""
        return bool(self._token)
