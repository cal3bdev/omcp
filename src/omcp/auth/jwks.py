"""JWKS (JSON Web Key Set) fetching and caching."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from omcp.auth.errors import JWKSFetchError


@dataclass
class CachedJWKS:
    """Cached JWKS with expiration."""

    keys: dict[str, Any]  # kid -> key mapping
    raw: dict[str, Any]  # Raw JWKS response
    fetched_at: float  # Unix timestamp
    expires_at: float  # Unix timestamp


class JWKSClient:
    """Client for fetching and caching JWKS from a URL.

    Implements automatic caching with configurable TTL and
    thread-safe async fetching.
    """

    def __init__(
        self,
        jwks_url: str,
        cache_ttl_seconds: int = 3600,
        http_timeout: float = 10.0,
    ) -> None:
        """Initialize the JWKS client.

        Args:
            jwks_url: URL to fetch JWKS from
            cache_ttl_seconds: How long to cache JWKS (default 1 hour)
            http_timeout: HTTP request timeout in seconds
        """
        self.jwks_url = jwks_url
        self.cache_ttl_seconds = cache_ttl_seconds
        self.http_timeout = http_timeout
        self._cache: CachedJWKS | None = None
        self._fetch_lock = asyncio.Lock()

    async def get_key(self, kid: str) -> dict[str, Any]:
        """Get a specific key by key ID.

        Args:
            kid: Key ID to look up

        Returns:
            The JWK for the given kid

        Raises:
            JWKSFetchError: If JWKS fetch fails
            KeyError: If kid not found in JWKS
        """
        jwks = await self.get_jwks()

        if kid not in jwks.keys:
            # Key not found - maybe JWKS was rotated, force refresh
            jwks = await self._fetch_jwks(force=True)

        if kid not in jwks.keys:
            raise KeyError(f"Key ID '{kid}' not found in JWKS")

        return jwks.keys[kid]

    async def get_jwks(self) -> CachedJWKS:
        """Get the cached JWKS, fetching if needed.

        Returns:
            Cached JWKS data

        Raises:
            JWKSFetchError: If fetch fails
        """
        now = time.time()

        # Return cached if still valid
        if self._cache and now < self._cache.expires_at:
            return self._cache

        return await self._fetch_jwks()

    async def _fetch_jwks(self, force: bool = False) -> CachedJWKS:
        """Fetch JWKS from URL with locking.

        Args:
            force: Force refresh even if cache is valid

        Returns:
            Fetched and cached JWKS

        Raises:
            JWKSFetchError: If fetch fails
        """
        async with self._fetch_lock:
            now = time.time()

            # Double-check cache after acquiring lock
            if not force and self._cache and now < self._cache.expires_at:
                return self._cache

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(
                        self.jwks_url,
                        timeout=self.http_timeout,
                        headers={"Accept": "application/json"},
                    )
                    response.raise_for_status()
                    raw = response.json()

            except httpx.TimeoutException:
                raise JWKSFetchError(self.jwks_url, "Request timed out")
            except httpx.HTTPStatusError as e:
                raise JWKSFetchError(self.jwks_url, f"HTTP {e.response.status_code}")
            except httpx.RequestError as e:
                raise JWKSFetchError(self.jwks_url, str(e))
            except Exception as e:
                raise JWKSFetchError(self.jwks_url, f"Unexpected error: {e}")

            # Parse keys into kid -> key mapping
            keys = {}
            for key in raw.get("keys", []):
                kid = key.get("kid")
                if kid:
                    keys[kid] = key

            self._cache = CachedJWKS(
                keys=keys,
                raw=raw,
                fetched_at=now,
                expires_at=now + self.cache_ttl_seconds,
            )

            return self._cache

    def clear_cache(self) -> None:
        """Clear the cached JWKS."""
        self._cache = None


# Global JWKS clients cache (keyed by URL)
_jwks_clients: dict[str, JWKSClient] = {}


def get_jwks_client(
    jwks_url: str,
    cache_ttl_seconds: int = 3600,
) -> JWKSClient:
    """Get or create a JWKS client for the given URL.

    Clients are cached globally to avoid duplicate fetches.

    Args:
        jwks_url: JWKS endpoint URL
        cache_ttl_seconds: Cache TTL

    Returns:
        JWKSClient instance
    """
    if jwks_url not in _jwks_clients:
        _jwks_clients[jwks_url] = JWKSClient(
            jwks_url=jwks_url,
            cache_ttl_seconds=cache_ttl_seconds,
        )
    return _jwks_clients[jwks_url]
