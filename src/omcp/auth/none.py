"""No-authentication provider for public APIs."""

from __future__ import annotations

from omcp.auth.base import AuthProvider


class NoneAuth(AuthProvider):
    """Auth provider that provides no authentication.

    Used for public APIs that don't require authentication.
    """

    async def get_headers(self) -> dict[str, str]:
        """Return empty headers."""
        return {}

    def get_headers_sync(self) -> dict[str, str]:
        """Return empty headers (sync)."""
        return {}

    async def refresh(self) -> None:
        """No-op refresh."""
        pass

    def is_valid(self) -> bool:
        """Always valid."""
        return True
