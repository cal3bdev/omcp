"""API Key authentication provider."""

from __future__ import annotations

from enum import Enum

from omcp.auth.base import AuthProvider


class ApiKeyLocation(str, Enum):
    """Where to send the API key."""

    HEADER = "header"
    QUERY = "query"


class ApiKeyAuth(AuthProvider):
    """API Key authentication provider.

    Supports sending the API key in:
    - HTTP header (default, e.g., X-API-Key)
    - Query parameter
    """

    def __init__(
        self,
        key: str,
        header_name: str = "X-API-Key",
        location: ApiKeyLocation = ApiKeyLocation.HEADER,
        param_name: str | None = None,
    ) -> None:
        """Initialize API key auth.

        Args:
            key: The API key value
            header_name: Header name when location=header (default: X-API-Key)
            location: Where to send the key (header or query)
            param_name: Query param name when location=query (default: api_key)
        """
        self._key = key
        self._header_name = header_name
        self._location = location
        self._param_name = param_name or "api_key"

    async def get_headers(self) -> dict[str, str]:
        """Get auth headers (if using header location)."""
        if self._location == ApiKeyLocation.HEADER:
            return {self._header_name: self._key}
        return {}

    def get_headers_sync(self) -> dict[str, str]:
        """Sync version - no async needed for static key."""
        if self._location == ApiKeyLocation.HEADER:
            return {self._header_name: self._key}
        return {}

    def get_query_params(self) -> dict[str, str]:
        """Get auth query params (if using query location)."""
        if self._location == ApiKeyLocation.QUERY:
            return {self._param_name: self._key}
        return {}

    async def refresh(self) -> None:
        """No-op for static API keys."""
        pass

    def is_valid(self) -> bool:
        """API key is valid if it exists and is non-empty."""
        return bool(self._key)
