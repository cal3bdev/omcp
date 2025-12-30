"""Base authentication provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class AuthProvider(ABC):
    """Abstract base class for authentication providers.

    All auth providers must implement methods to:
    - Get headers for HTTP requests
    - Refresh credentials if needed
    - Check if credentials are valid
    """

    @abstractmethod
    async def get_headers(self) -> dict[str, str]:
        """Get authentication headers for HTTP requests.

        Returns:
            Dict of header name -> value to include in requests
        """
        ...

    def get_headers_sync(self) -> dict[str, str]:
        """Synchronous version of get_headers.

        Default implementation runs the async version.
        Override for providers that don't need async.
        """
        import asyncio

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.get_headers())

        # If there's already a loop, we need to handle differently
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, self.get_headers())
            return future.result()

    @abstractmethod
    async def refresh(self) -> None:
        """Refresh the authentication credentials.

        For providers with expiring tokens (OAuth2), this should
        refresh the access token. For static credentials, this
        can be a no-op.

        Raises:
            AuthError: If refresh fails
        """
        ...

    @abstractmethod
    def is_valid(self) -> bool:
        """Check if the current credentials are valid.

        Returns:
            True if credentials exist and haven't expired
        """
        ...

    def get_query_params(self) -> dict[str, str]:
        """Get authentication query parameters.

        Some APIs use query params instead of headers for auth.
        Default returns empty dict.

        Returns:
            Dict of param name -> value to include in requests
        """
        return {}

    def on_response(self, status_code: int, headers: dict[str, Any]) -> None:
        """Hook called after each response.

        Can be used to detect auth failures and trigger refresh.

        Args:
            status_code: HTTP response status code
            headers: Response headers
        """
        pass
