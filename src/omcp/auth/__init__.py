"""Authentication providers and token management."""

from omcp.auth.api_key import ApiKeyAuth, ApiKeyLocation
from omcp.auth.asgi import DynamicAuthMiddleware, create_auth_middleware
from omcp.auth.base import AuthProvider
from omcp.auth.bearer import BearerAuth
from omcp.auth.context import AuthContext, TokenClaims
from omcp.auth.dynamic import (
    DynamicAuth,
    auth_context_scope,
    create_dynamic_auth,
    get_current_auth_context,
    reset_auth_context,
    set_current_auth_context,
)
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
from omcp.auth.httpx_auth import DynamicTokenAuth, StaticTokenAuth
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
    "DynamicAuth",
    # Dynamic auth
    "AuthContext",
    "TokenClaims",
    "AuthMiddleware",
    "JWTValidator",
    "JWKSClient",
    "DynamicTokenAuth",
    "StaticTokenAuth",
    "DynamicAuthMiddleware",
    # Context management
    "get_current_auth_context",
    "set_current_auth_context",
    "reset_auth_context",
    "auth_context_scope",
    # Factory functions
    "create_auth_provider",
    "create_dynamic_auth",
    "create_jwt_validator",
    "create_auth_context",
    "create_auth_middleware",
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
