"""Authentication middleware for extracting and validating tokens."""

from __future__ import annotations

from typing import TYPE_CHECKING

from omcp.auth.context import AuthContext, TokenClaims
from omcp.auth.errors import (
    InvalidAuthSchemeError,
    MissingAuthError,
    MissingTokenError,
)

if TYPE_CHECKING:
    from omcp.auth.jwt import JWTValidator
    from omcp.config.models import DynamicAuthConfig


def extract_token(authorization_header: str | None) -> str:
    """Extract bearer token from Authorization header.

    Args:
        authorization_header: The Authorization header value

    Returns:
        The extracted token string

    Raises:
        MissingAuthError: If header is missing
        InvalidAuthSchemeError: If not using Bearer scheme
        MissingTokenError: If token is empty
    """
    if not authorization_header:
        raise MissingAuthError()

    # Split scheme and token
    parts = authorization_header.split(" ", 1)

    if len(parts) == 1:
        # No space found - could be just "Bearer" or a raw token
        scheme = parts[0]
        if scheme.lower() == "bearer":
            raise MissingTokenError()
        else:
            raise InvalidAuthSchemeError(scheme)

    scheme, token = parts

    if scheme.lower() != "bearer":
        raise InvalidAuthSchemeError(scheme)

    token = token.strip()
    if not token:
        raise MissingTokenError()

    return token


async def create_auth_context(
    authorization_header: str | None,
    config: DynamicAuthConfig | None,
    jwt_validator: JWTValidator | None = None,
) -> AuthContext:
    """Create an AuthContext from the request Authorization header.

    Args:
        authorization_header: The Authorization header value
        config: Dynamic auth configuration
        jwt_validator: Optional JWT validator for token validation

    Returns:
        AuthContext with token and optionally validated claims

    Raises:
        AuthError subclass on authentication failure
    """
    # Extract token from header
    token = extract_token(authorization_header)

    # If validation is disabled or no validator, return unvalidated context
    if not config or not config.validation.enabled or not jwt_validator:
        return AuthContext(token=token, validated=False)

    # Validate the token
    claims_dict = await jwt_validator.validate(token)
    claims = TokenClaims.from_jwt(claims_dict)

    return AuthContext(
        token=token,
        claims=claims,
        validated=True,
    )


class AuthMiddleware:
    """Middleware for handling authentication in MCP requests.

    This middleware extracts tokens from requests and optionally validates them.
    It's designed to be stateless - no credentials are stored.
    """

    def __init__(
        self,
        config: DynamicAuthConfig | None = None,
        jwt_validator: JWTValidator | None = None,
    ) -> None:
        """Initialize the auth middleware.

        Args:
            config: Dynamic auth configuration
            jwt_validator: Optional JWT validator
        """
        self.config = config
        self.jwt_validator = jwt_validator

    async def authenticate(self, authorization_header: str | None) -> AuthContext:
        """Authenticate a request and return the auth context.

        Args:
            authorization_header: The Authorization header value

        Returns:
            AuthContext for the request

        Raises:
            AuthError subclass on authentication failure
        """
        return await create_auth_context(
            authorization_header=authorization_header,
            config=self.config,
            jwt_validator=self.jwt_validator,
        )

    def is_validation_enabled(self) -> bool:
        """Check if token validation is enabled."""
        return (
            self.config is not None
            and self.config.validation.enabled
            and self.jwt_validator is not None
        )
