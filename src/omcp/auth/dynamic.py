"""Dynamic authentication provider for stateless token passthrough."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Generator

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


def set_current_auth_context(ctx: AuthContext | None) -> Token[AuthContext | None]:
    """Set the auth context for the current request.

    Returns:
        A token that can be used with reset_auth_context() to restore
        the previous value. This ensures proper cleanup in nested contexts.
    """
    return _request_auth_context.set(ctx)


def reset_auth_context(token: Token[AuthContext | None]) -> None:
    """Reset the auth context to its previous value.

    This should be used in a finally block to ensure the context is
    properly restored even if an exception occurs.

    Args:
        token: The token returned by set_current_auth_context()
    """
    _request_auth_context.reset(token)


@contextmanager
def auth_context_scope(ctx: AuthContext | None) -> Generator[None, None, None]:
    """Context manager for safely scoping auth context.

    Ensures the auth context is properly reset to its previous value
    when the scope exits, even if an exception occurs.

    Usage:
        with auth_context_scope(auth_context):
            # auth_context is available via get_current_auth_context()
            await process_request()
        # Previous context (or None) is automatically restored

    Args:
        ctx: The auth context to set for this scope
    """
    token = _request_auth_context.set(ctx)
    try:
        yield
    finally:
        _request_auth_context.reset(token)


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

    def extract_token(self, authorization_header: str | None) -> str:
        """Extract token from Authorization header.

        Args:
            authorization_header: The Authorization header value

        Returns:
            The extracted token string

        Raises:
            MissingAuthError: If header is missing
            InvalidAuthSchemeError: If not using expected scheme (when scheme is set)
            MissingTokenError: If token is empty
        """
        if not authorization_header:
            raise MissingAuthError()

        # Get expected scheme from config (None means raw token, no scheme)
        expected_scheme = self.config.header.scheme

        # If no scheme configured, treat entire header value as raw token
        if expected_scheme is None:
            token = authorization_header.strip()
            if not token:
                raise MissingTokenError()
            return token

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

        # Get header config for forwarding
        header_name = self.config.header.name or "Authorization"
        header_scheme = self.config.header.scheme  # Can be None for raw tokens

        # If validation is disabled or no validator, return unvalidated context
        if not self.config.validation.enabled or not self.jwt_validator:
            return AuthContext(
                token=token,
                validated=False,
                header_name=header_name,
                header_scheme=header_scheme,
            )

        # Validate the token
        claims_dict = await self.jwt_validator.validate(token)
        claims = TokenClaims.from_jwt(claims_dict)

        return AuthContext(
            token=token,
            claims=claims,
            validated=True,
            header_name=header_name,
            header_scheme=header_scheme,
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
