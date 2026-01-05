"""Authentication providers and token management."""

from omcp.auth.api_key import ApiKeyAuth, ApiKeyLocation
from omcp.auth.base import AuthProvider
from omcp.auth.bearer import BearerAuth
from omcp.auth.context import AuthContext, TokenClaims
from omcp.auth.errors import (
    AuthError,
    InvalidAudienceError,
    InvalidAuthSchemeError,
    InvalidIssuerError,
    InvalidTokenError,
    JWKSFetchError,
    MissingAuthError,
    MissingTokenError,
    TokenExpiredError,
    UpstreamAuthError,
    UpstreamForbiddenError,
)
from omcp.auth.factory import create_auth_provider
from omcp.auth.jwt import JWTValidator, create_jwt_validator
from omcp.auth.jwks import JWKSClient, get_jwks_client
from omcp.auth.httpx_auth import StaticTokenAuth
from omcp.auth.middleware import AuthMiddleware, create_auth_context, extract_token
from omcp.auth.none import NoneAuth
from omcp.auth.oauth2 import OAuth2Auth
from omcp.auth.storage import StoredToken, TokenStorage

__all__ = [
    # Base
    "AuthProvider",
    # Providers
    "ApiKeyAuth",
    "ApiKeyLocation",
    "BearerAuth",
    "NoneAuth",
    "OAuth2Auth",
    # Context
    "AuthContext",
    "TokenClaims",
    # Middleware
    "AuthMiddleware",
    # JWT
    "JWTValidator",
    "JWKSClient",
    # httpx auth
    "StaticTokenAuth",
    # Factory functions
    "create_auth_provider",
    "create_jwt_validator",
    "create_auth_context",
    "extract_token",
    "get_jwks_client",
    # Storage
    "TokenStorage",
    "StoredToken",
    # Errors
    "AuthError",
    "MissingAuthError",
    "InvalidAuthSchemeError",
    "MissingTokenError",
    "TokenExpiredError",
    "InvalidTokenError",
    "InvalidAudienceError",
    "InvalidIssuerError",
    "JWKSFetchError",
    "UpstreamAuthError",
    "UpstreamForbiddenError",
]
