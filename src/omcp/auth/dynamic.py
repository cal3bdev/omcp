"""Dynamic authentication provider for stateless token passthrough."""

from __future__ import annotations

import os
from contextvars import ContextVar
from typing import TYPE_CHECKING, Any

from omcp.auth.base import AuthProvider
from omcp.auth.context import AuthContext, TokenClaims
from omcp.auth.errors import (
    InvalidAuthSchemeError,
    MissingAuthError,
    MissingTokenError,
)
from omcp.auth.jwt import JWTValidator

if TYPE_CHECKING:
    from omcp.config.models import AuthConfig


# Context variable to hold the current request's auth context
_request_auth_context: ContextVar[AuthContext | None] = ContextVar(
    "request_auth_context", default=None
)


def get_current_auth_context() -> AuthContext | None:
    """Get the auth context for the current request."""
    return _request_auth_context.get()


def set_current_auth_context(ctx: AuthContext | None) -> None:
    """Set the auth context for the current request."""
    _request_auth_context.set(ctx)


class DynamicAuth(AuthProvider):
    """Dynamic authentication provider for stateless token passthrough.

    Unlike static auth providers, DynamicAuth:
    - Does NOT store credentials
    - Expects tokens to be provided per-request via context
    - Optionally validates tokens (JWT)
    - Forwards tokens to upstream APIs

    This implements the "clients own tokens" pattern where:
    1. Client obtains token from identity provider
    2. Client sends token to OMCP in Authorization header
    3. OMCP validates (optional) and forwards to upstream
    """

    def __init__(
        self,
        config: AuthConfig,
        jwt_validator: JWTValidator | None = None,
    ) -> None:
        """Initialize dynamic auth provider.

        Args:
            config: Authentication configuration
            jwt_validator: Optional JWT validator for token validation
        """
        self.config = config
        self.jwt_validator = jwt_validator
        self._dev_mode_token: str | None = None

        # Load dev mode token if enabled
        if config.dev_mode.enabled and config.dev_mode.token_env:
            self._dev_mode_token = os.environ.get(config.dev_mode.token_env)

    def extract_token(self, authorization_header: str | None) -> str:
        """Extract bearer token from Authorization header.

        Args:
            authorization_header: The Authorization header value

        Returns:
            The extracted token string

        Raises:
            MissingAuthError: If header is missing (and no dev token)
            InvalidAuthSchemeError: If not using expected scheme
            MissingTokenError: If token is empty
        """
        # If no header provided, check dev mode fallback
        if not authorization_header:
            if self._dev_mode_token:
                return self._dev_mode_token
            raise MissingAuthError()

        # Get expected scheme from config
        expected_scheme = self.config.header.scheme or "Bearer"

        # Split scheme and token
        parts = authorization_header.split(" ", 1)

        if len(parts) == 1:
            # No space found
            scheme = parts[0]
            if scheme.lower() == expected_scheme.lower():
                raise MissingTokenError()
            else:
                raise InvalidAuthSchemeError(scheme)

        scheme, token = parts

        if scheme.lower() != expected_scheme.lower():
            raise InvalidAuthSchemeError(scheme)

        token = token.strip()
        if not token:
            raise MissingTokenError()

        return token

    async def authenticate(self, authorization_header: str | None) -> AuthContext:
        """Authenticate a request and return auth context.

        Args:
            authorization_header: The Authorization header value

        Returns:
            AuthContext with token and validated claims (if validation enabled)

        Raises:
            AuthError subclass on authentication failure
        """
        # Extract token
        token = self.extract_token(authorization_header)

        # If validation is disabled or no validator, return unvalidated context
        if not self.config.validation.enabled or not self.jwt_validator:
            return AuthContext(token=token, validated=False)

        # Validate the token
        claims_dict = await self.jwt_validator.validate(token)
        claims = TokenClaims.from_jwt(claims_dict)

        return AuthContext(
            token=token,
            claims=claims,
            validated=True,
        )

    async def get_headers(self) -> dict[str, str]:
        """Get authentication headers for HTTP requests.

        Uses the auth context from the current request to get the token.

        Returns:
            Dict with Authorization header if token available
        """
        ctx = get_current_auth_context()
        if ctx and ctx.token:
            scheme = self.config.header.scheme or "Bearer"
            header_name = self.config.header.name or "Authorization"
            return {header_name: f"{scheme} {ctx.token}"}
        return {}

    def get_headers_sync(self) -> dict[str, str]:
        """Synchronous version - uses context var directly."""
        ctx = get_current_auth_context()
        if ctx and ctx.token:
            scheme = self.config.header.scheme or "Bearer"
            header_name = self.config.header.name or "Authorization"
            return {header_name: f"{scheme} {ctx.token}"}
        return {}

    async def refresh(self) -> None:
        """No-op for dynamic auth - clients manage their own tokens."""
        pass

    def is_valid(self) -> bool:
        """Check if we have a valid token in context.

        For dynamic auth, validity depends on current request context.
        """
        ctx = get_current_auth_context()
        return ctx is not None and ctx.token is not None

    def is_dev_mode_enabled(self) -> bool:
        """Check if dev mode is enabled and token is available."""
        return self.config.dev_mode.enabled and self._dev_mode_token is not None

    def get_dev_mode_status(self) -> dict[str, Any]:
        """Get dev mode status for diagnostics."""
        if not self.config.dev_mode.enabled:
            return {"enabled": False}

        return {
            "enabled": True,
            "token_env": self.config.dev_mode.token_env,
            "token_set": self._dev_mode_token is not None,
        }


def create_dynamic_auth(config: AuthConfig) -> DynamicAuth:
    """Create a DynamicAuth provider from configuration.

    Args:
        config: Authentication configuration with JWT settings

    Returns:
        Configured DynamicAuth instance
    """
    jwt_validator = None

    # Create JWT validator if validation is enabled and JWKS URL is provided
    if config.validation.enabled and config.validation.jwks_url:
        from omcp.auth.jwt import create_jwt_validator

        jwt_validator = create_jwt_validator(config.validation)

    return DynamicAuth(config=config, jwt_validator=jwt_validator)
