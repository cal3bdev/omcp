"""Secure token storage for OAuth2 credentials."""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from omcp.utils.errors import AuthError


class StoredToken(BaseModel):
    """Stored OAuth2 token data."""

    access_token: str
    token_type: str = "Bearer"
    expires_at: datetime | None = None
    refresh_token: str | None = None
    scope: str | None = None

    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provider_name: str = ""

    def is_expired(self, buffer_seconds: int = 60) -> bool:
        """Check if the access token is expired.

        Args:
            buffer_seconds: Consider expired this many seconds early

        Returns:
            True if token is expired or will expire within buffer
        """
        if self.expires_at is None:
            return False

        now = datetime.now(timezone.utc)
        # Ensure expires_at is timezone-aware
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        from datetime import timedelta

        return now >= (expires_at - timedelta(seconds=buffer_seconds))

    def can_refresh(self) -> bool:
        """Check if token can be refreshed."""
        return bool(self.refresh_token)


class TokenStorage:
    """File-based token storage with restricted permissions.

    Stores tokens in a JSON file with 600 permissions (owner read/write only).
    """

    DEFAULT_DIR = ".omcp"
    DEFAULT_FILE = "tokens.json"

    def __init__(self, storage_dir: str | Path | None = None) -> None:
        """Initialize token storage.

        Args:
            storage_dir: Directory for token storage (default: ~/.omcp)
        """
        if storage_dir is None:
            storage_dir = Path.home() / self.DEFAULT_DIR
        self._storage_dir = Path(storage_dir)
        self._storage_file = self._storage_dir / self.DEFAULT_FILE

    def _ensure_storage_dir(self) -> None:
        """Create storage directory with restricted permissions."""
        if not self._storage_dir.exists():
            self._storage_dir.mkdir(parents=True, mode=0o700)

    def _read_storage(self) -> dict[str, Any]:
        """Read the token storage file."""
        if not self._storage_file.exists():
            return {}

        try:
            content = self._storage_file.read_text()
            return json.loads(content) if content else {}
        except (json.JSONDecodeError, OSError) as e:
            raise AuthError("Failed to read token storage", details=str(e))

    def _write_storage(self, data: dict[str, Any]) -> None:
        """Write to token storage file with restricted permissions."""
        self._ensure_storage_dir()

        try:
            content = json.dumps(data, indent=2, default=str)
            self._storage_file.write_text(content)
            # Set file permissions to 600 (owner read/write only)
            os.chmod(self._storage_file, stat.S_IRUSR | stat.S_IWUSR)
        except OSError as e:
            raise AuthError("Failed to write token storage", details=str(e))

    def store(self, provider_name: str, token: StoredToken) -> None:
        """Store a token for a provider.

        Args:
            provider_name: Unique name for the provider/API
            token: Token data to store
        """
        token.provider_name = provider_name
        data = self._read_storage()
        data[provider_name] = token.model_dump(mode="json")
        self._write_storage(data)

    def load(self, provider_name: str) -> StoredToken | None:
        """Load a token for a provider.

        Args:
            provider_name: Unique name for the provider/API

        Returns:
            StoredToken if found, None otherwise
        """
        data = self._read_storage()
        token_data = data.get(provider_name)

        if token_data is None:
            return None

        try:
            return StoredToken.model_validate(token_data)
        except Exception:
            return None

    def delete(self, provider_name: str) -> bool:
        """Delete a stored token.

        Args:
            provider_name: Unique name for the provider/API

        Returns:
            True if token was deleted, False if not found
        """
        data = self._read_storage()
        if provider_name not in data:
            return False

        del data[provider_name]
        self._write_storage(data)
        return True

    def list_providers(self) -> list[str]:
        """List all providers with stored tokens.

        Returns:
            List of provider names
        """
        data = self._read_storage()
        return list(data.keys())

    def clear(self) -> None:
        """Delete all stored tokens."""
        if self._storage_file.exists():
            self._storage_file.unlink()
