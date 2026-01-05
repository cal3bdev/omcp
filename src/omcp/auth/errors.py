"""Authentication error types for dynamic auth."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class AuthError(Exception):
    """Base authentication error."""

    code: str
    message: str
    hint: str | None = None
    status_code: int = 401

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-RPC error data format."""
        data = {
            "error_code": self.code,
            "error_message": self.message,
        }
        if self.hint:
            data["hint"] = self.hint
        return data


# Specific error types for clear error handling


class MissingAuthError(AuthError):
    """No Authorization header provided."""

    def __init__(self) -> None:
        super().__init__(
            code="missing_auth",
            message="Authorization header required",
            hint="Include 'Authorization: Bearer <token>' header",
            status_code=401,
        )


class InvalidAuthSchemeError(AuthError):
    """Authorization header doesn't use Bearer scheme."""

    def __init__(self, scheme: str) -> None:
        super().__init__(
            code="invalid_auth_scheme",
            message=f"Authorization must use Bearer scheme, got '{scheme}'",
            hint="Use 'Authorization: Bearer <token>' format",
            status_code=401,
        )


class MissingTokenError(AuthError):
    """Bearer scheme present but token is empty."""

    def __init__(self) -> None:
        super().__init__(
            code="missing_token",
            message="Bearer token is empty",
            hint="Provide a valid token after 'Bearer '",
            status_code=401,
        )


class TokenExpiredError(AuthError):
    """JWT token has expired."""

    def __init__(self) -> None:
        super().__init__(
            code="token_expired",
            message="Access token has expired",
            hint="Refresh your token and retry",
            status_code=401,
        )


class InvalidTokenError(AuthError):
    """Token validation failed."""

    def __init__(self, reason: str | None = None) -> None:
        message = "Invalid access token"
        if reason:
            message = f"Invalid access token: {reason}"
        super().__init__(
            code="invalid_token",
            message=message,
            hint="Ensure you're using a valid, properly signed token",
            status_code=401,
        )


class InvalidAudienceError(AuthError):
    """Token audience doesn't match expected value."""

    def __init__(self, expected: str) -> None:
        super().__init__(
            code="invalid_audience",
            message="Token not valid for this API",
            hint=f"Token must have audience: {expected}",
            status_code=401,
        )


class InvalidIssuerError(AuthError):
    """Token issuer doesn't match expected value."""

    def __init__(self, expected: str) -> None:
        super().__init__(
            code="invalid_issuer",
            message="Token from unrecognized issuer",
            hint=f"Token must be issued by: {expected}",
            status_code=401,
        )


class JWKSFetchError(AuthError):
    """Failed to fetch JWKS from URL."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(
            code="jwks_fetch_failed",
            message=f"Failed to fetch signing keys: {reason}",
            hint="Check JWKS URL configuration and network connectivity",
            status_code=500,
        )


class UpstreamAuthError(AuthError):
    """Upstream API rejected the token."""

    def __init__(self, status: int) -> None:
        super().__init__(
            code="upstream_auth_failed",
            message="Upstream API rejected the token",
            hint="Token may be expired, revoked, or invalid for this API",
            status_code=401,
        )


class UpstreamForbiddenError(AuthError):
    """Upstream API returned 403 Forbidden."""

    def __init__(self) -> None:
        super().__init__(
            code="upstream_forbidden",
            message="You don't have permission for this operation",
            hint="Check your token's scopes and permissions",
            status_code=403,
        )
