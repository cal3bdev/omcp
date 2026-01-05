"""Factory for creating auth providers from config."""

from __future__ import annotations

from omcp.auth.api_key import ApiKeyAuth, ApiKeyLocation
from omcp.auth.base import AuthProvider
from omcp.auth.bearer import BearerAuth
from omcp.auth.none import NoneAuth
from omcp.auth.oauth2 import OAuth2Auth
from omcp.auth.storage import TokenStorage
from omcp.config.models import AuthConfig, AuthType
from omcp.utils.errors import ConfigError


def create_auth_provider(
    config: AuthConfig,
    provider_name: str = "default",
    storage: TokenStorage | None = None,
) -> AuthProvider:
    """Create an auth provider from configuration.

    Args:
        config: Authentication configuration
        provider_name: Name for OAuth2 token storage
        storage: Optional token storage instance

    Returns:
        Configured AuthProvider instance

    Raises:
        ConfigError: If config is invalid or missing required fields
    """
    if config.type == AuthType.NONE:
        return NoneAuth()
    elif config.type == AuthType.API_KEY:
        return _create_api_key_auth(config)
    elif config.type == AuthType.BEARER:
        return _create_bearer_auth(config)
    elif config.type == AuthType.OAUTH2:
        return _create_oauth2_auth(config, provider_name, storage)
    elif config.type == AuthType.JWT:
        # JWT auth is handled by FastMCP's built-in capabilities:
        # - Header forwarding via get_http_headers()
        # - Token validation via JWTVerifier (set on mcp.auth)
        # No custom auth provider needed.
        return NoneAuth()
    else:
        raise ConfigError(f"Unknown auth type: {config.type}")


def _create_api_key_auth(config: AuthConfig) -> ApiKeyAuth:
    """Create API key auth provider."""
    key = config.key or config.token
    if not key:
        raise ConfigError(
            "API key auth requires 'key' or 'token' field",
            details="Set auth.key or auth.token in config",
        )

    # Determine location based on header_name
    # If it looks like a standard auth header, use header location
    # Otherwise could be query param (future: add explicit location config)
    return ApiKeyAuth(
        key=key,
        header_name=config.header_name,
        location=ApiKeyLocation.HEADER,
    )


def _create_bearer_auth(config: AuthConfig) -> BearerAuth:
    """Create bearer token auth provider."""
    token = config.token
    if not token:
        raise ConfigError(
            "Bearer auth requires 'token' field",
            details="Set auth.token in config",
        )

    return BearerAuth(
        token=token,
        header_name=config.header_name,
    )


def _create_oauth2_auth(
    config: AuthConfig,
    provider_name: str,
    storage: TokenStorage | None,
) -> OAuth2Auth:
    """Create OAuth2 auth provider."""
    if not config.client_id:
        raise ConfigError(
            "OAuth2 auth requires 'client_id' field",
            details="Set auth.client_id in config",
        )

    if not config.auth_url:
        raise ConfigError(
            "OAuth2 auth requires 'auth_url' field",
            details="Set auth.auth_url in config",
        )

    if not config.token_url:
        raise ConfigError(
            "OAuth2 auth requires 'token_url' field",
            details="Set auth.token_url in config",
        )

    return OAuth2Auth(
        client_id=config.client_id,
        auth_url=config.auth_url,
        token_url=config.token_url,
        scopes=config.scopes,
        client_secret=config.client_secret,
        provider_name=provider_name,
        storage=storage or TokenStorage(),
    )
