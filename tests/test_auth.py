"""Tests for authentication providers."""

import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from omcp.auth import (
    ApiKeyAuth,
    ApiKeyLocation,
    BearerAuth,
    OAuth2Auth,
    StoredToken,
    TokenStorage,
    create_auth_provider,
)
from omcp.config.models import AuthConfig, AuthType
from omcp.utils.errors import AuthError, ConfigError


class TestApiKeyAuth:
    """Test API Key authentication provider."""

    @pytest.mark.asyncio
    async def test_header_auth(self):
        """API key in header."""
        auth = ApiKeyAuth(key="test-key", header_name="X-API-Key")
        headers = await auth.get_headers()
        assert headers == {"X-API-Key": "test-key"}

    @pytest.mark.asyncio
    async def test_header_auth_sync(self):
        """API key in header (sync)."""
        auth = ApiKeyAuth(key="test-key", header_name="X-API-Key")
        headers = auth.get_headers_sync()
        assert headers == {"X-API-Key": "test-key"}

    @pytest.mark.asyncio
    async def test_query_auth(self):
        """API key in query parameter."""
        auth = ApiKeyAuth(
            key="test-key",
            location=ApiKeyLocation.QUERY,
            param_name="apikey",
        )
        headers = await auth.get_headers()
        assert headers == {}
        params = auth.get_query_params()
        assert params == {"apikey": "test-key"}

    def test_is_valid(self):
        """API key validity check."""
        auth = ApiKeyAuth(key="test-key")
        assert auth.is_valid() is True

        empty_auth = ApiKeyAuth(key="")
        assert empty_auth.is_valid() is False

    @pytest.mark.asyncio
    async def test_refresh_noop(self):
        """Refresh is no-op for API keys."""
        auth = ApiKeyAuth(key="test-key")
        await auth.refresh()  # Should not raise


class TestBearerAuth:
    """Test Bearer token authentication provider."""

    @pytest.mark.asyncio
    async def test_bearer_header(self):
        """Bearer token in Authorization header."""
        auth = BearerAuth(token="my-token")
        headers = await auth.get_headers()
        assert headers == {"Authorization": "Bearer my-token"}

    @pytest.mark.asyncio
    async def test_bearer_header_sync(self):
        """Bearer token (sync)."""
        auth = BearerAuth(token="my-token")
        headers = auth.get_headers_sync()
        assert headers == {"Authorization": "Bearer my-token"}

    @pytest.mark.asyncio
    async def test_custom_header_name(self):
        """Custom header name."""
        auth = BearerAuth(token="my-token", header_name="X-Auth-Token")
        headers = await auth.get_headers()
        assert headers == {"X-Auth-Token": "Bearer my-token"}

    @pytest.mark.asyncio
    async def test_custom_prefix(self):
        """Custom token prefix."""
        auth = BearerAuth(token="my-token", prefix="Token")
        headers = await auth.get_headers()
        assert headers == {"Authorization": "Token my-token"}

    def test_is_valid(self):
        """Bearer token validity check."""
        auth = BearerAuth(token="my-token")
        assert auth.is_valid() is True

        empty_auth = BearerAuth(token="")
        assert empty_auth.is_valid() is False


class TestTokenStorage:
    """Test token storage."""

    def test_store_and_load(self):
        """Store and load a token."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TokenStorage(storage_dir=tmpdir)

            token = StoredToken(
                access_token="access123",
                refresh_token="refresh456",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )

            storage.store("test-provider", token)

            loaded = storage.load("test-provider")
            assert loaded is not None
            assert loaded.access_token == "access123"
            assert loaded.refresh_token == "refresh456"

    def test_load_nonexistent(self):
        """Load non-existent token returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TokenStorage(storage_dir=tmpdir)
            assert storage.load("nonexistent") is None

    def test_delete_token(self):
        """Delete a stored token."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TokenStorage(storage_dir=tmpdir)

            token = StoredToken(access_token="access123")
            storage.store("test-provider", token)

            assert storage.delete("test-provider") is True
            assert storage.load("test-provider") is None
            assert storage.delete("test-provider") is False

    def test_list_providers(self):
        """List all providers with stored tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TokenStorage(storage_dir=tmpdir)

            storage.store("provider1", StoredToken(access_token="a"))
            storage.store("provider2", StoredToken(access_token="b"))

            providers = storage.list_providers()
            assert set(providers) == {"provider1", "provider2"}

    def test_clear_all(self):
        """Clear all stored tokens."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TokenStorage(storage_dir=tmpdir)

            storage.store("provider1", StoredToken(access_token="a"))
            storage.store("provider2", StoredToken(access_token="b"))

            storage.clear()
            assert storage.list_providers() == []


class TestStoredToken:
    """Test StoredToken model."""

    def test_is_expired_no_expiry(self):
        """Token without expiry is never expired."""
        token = StoredToken(access_token="test")
        assert token.is_expired() is False

    def test_is_expired_future(self):
        """Token expiring in future is not expired."""
        token = StoredToken(
            access_token="test",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert token.is_expired() is False

    def test_is_expired_past(self):
        """Token that expired is expired."""
        token = StoredToken(
            access_token="test",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert token.is_expired() is True

    def test_is_expired_buffer(self):
        """Token expiring within buffer is considered expired."""
        token = StoredToken(
            access_token="test",
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=30),
        )
        # With 60 second buffer, should be expired
        assert token.is_expired(buffer_seconds=60) is True
        # With 10 second buffer, should not be expired
        assert token.is_expired(buffer_seconds=10) is False

    def test_can_refresh(self):
        """Check if token can be refreshed."""
        token_with_refresh = StoredToken(
            access_token="test",
            refresh_token="refresh123",
        )
        assert token_with_refresh.can_refresh() is True

        token_without_refresh = StoredToken(access_token="test")
        assert token_without_refresh.can_refresh() is False


class TestOAuth2Auth:
    """Test OAuth2 authentication provider."""

    def test_pkce_generation(self):
        """PKCE code verifier and challenge are generated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TokenStorage(storage_dir=tmpdir)
            auth = OAuth2Auth(
                client_id="test-client",
                auth_url="https://auth.example.com/authorize",
                token_url="https://auth.example.com/token",
                storage=storage,
            )

            url = auth.get_authorization_url()

            # Check URL contains required params
            assert "client_id=test-client" in url
            assert "code_challenge=" in url
            assert "code_challenge_method=S256" in url
            assert "response_type=code" in url

    def test_authorization_url_with_scopes(self):
        """Authorization URL includes scopes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TokenStorage(storage_dir=tmpdir)
            auth = OAuth2Auth(
                client_id="test-client",
                auth_url="https://auth.example.com/authorize",
                token_url="https://auth.example.com/token",
                scopes=["read", "write"],
                storage=storage,
            )

            url = auth.get_authorization_url()
            assert "scope=read+write" in url or "scope=read%20write" in url

    def test_is_valid_no_token(self):
        """No token means not valid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TokenStorage(storage_dir=tmpdir)
            auth = OAuth2Auth(
                client_id="test-client",
                auth_url="https://auth.example.com/authorize",
                token_url="https://auth.example.com/token",
                storage=storage,
            )

            assert auth.is_valid() is False

    def test_is_valid_with_token(self):
        """Valid token means valid."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TokenStorage(storage_dir=tmpdir)

            # Pre-store a valid token
            token = StoredToken(
                access_token="valid-token",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
            storage.store("test-provider", token)

            auth = OAuth2Auth(
                client_id="test-client",
                auth_url="https://auth.example.com/authorize",
                token_url="https://auth.example.com/token",
                storage=storage,
                provider_name="test-provider",
            )

            assert auth.is_valid() is True

    @pytest.mark.asyncio
    async def test_get_headers_no_token(self):
        """Getting headers without token raises error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TokenStorage(storage_dir=tmpdir)
            auth = OAuth2Auth(
                client_id="test-client",
                auth_url="https://auth.example.com/authorize",
                token_url="https://auth.example.com/token",
                storage=storage,
            )

            with pytest.raises(AuthError) as exc:
                await auth.get_headers()
            assert "No OAuth2 token" in str(exc.value.message)

    @pytest.mark.asyncio
    async def test_get_headers_with_token(self):
        """Getting headers with valid token works."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage = TokenStorage(storage_dir=tmpdir)

            # Pre-store a valid token
            token = StoredToken(
                access_token="valid-token",
                token_type="Bearer",
                expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
            )
            storage.store("test-provider", token)

            auth = OAuth2Auth(
                client_id="test-client",
                auth_url="https://auth.example.com/authorize",
                token_url="https://auth.example.com/token",
                storage=storage,
                provider_name="test-provider",
            )

            headers = await auth.get_headers()
            assert headers == {"Authorization": "Bearer valid-token"}


class TestAuthFactory:
    """Test auth provider factory."""

    def test_create_api_key_auth(self):
        """Create API key auth from config."""
        config = AuthConfig(type=AuthType.API_KEY, key="my-api-key")
        auth = create_auth_provider(config)

        assert isinstance(auth, ApiKeyAuth)
        assert auth.get_headers_sync() == {"Authorization": "my-api-key"}

    def test_create_api_key_auth_from_token(self):
        """Create API key auth using token field."""
        config = AuthConfig(type=AuthType.API_KEY, token="my-api-key")
        auth = create_auth_provider(config)

        assert isinstance(auth, ApiKeyAuth)

    def test_create_api_key_missing_key(self):
        """API key auth without key raises error."""
        config = AuthConfig(type=AuthType.API_KEY)
        with pytest.raises(ConfigError) as exc:
            create_auth_provider(config)
        assert "key" in str(exc.value.message).lower()

    def test_create_bearer_auth(self):
        """Create bearer auth from config."""
        config = AuthConfig(type=AuthType.BEARER, token="my-token")
        auth = create_auth_provider(config)

        assert isinstance(auth, BearerAuth)
        assert auth.get_headers_sync() == {"Authorization": "Bearer my-token"}

    def test_create_bearer_missing_token(self):
        """Bearer auth without token raises error."""
        config = AuthConfig(type=AuthType.BEARER)
        with pytest.raises(ConfigError) as exc:
            create_auth_provider(config)
        assert "token" in str(exc.value.message).lower()

    def test_create_oauth2_auth(self):
        """Create OAuth2 auth from config."""
        config = AuthConfig(
            type=AuthType.OAUTH2,
            client_id="my-client",
            auth_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
            scopes=["read", "write"],
        )
        auth = create_auth_provider(config)

        assert isinstance(auth, OAuth2Auth)

    def test_create_oauth2_missing_client_id(self):
        """OAuth2 auth without client_id raises error."""
        config = AuthConfig(
            type=AuthType.OAUTH2,
            auth_url="https://auth.example.com/authorize",
            token_url="https://auth.example.com/token",
        )
        with pytest.raises(ConfigError) as exc:
            create_auth_provider(config)
        assert "client_id" in str(exc.value.message).lower()

    def test_create_oauth2_missing_auth_url(self):
        """OAuth2 auth without auth_url raises error."""
        config = AuthConfig(
            type=AuthType.OAUTH2,
            client_id="my-client",
            token_url="https://auth.example.com/token",
        )
        with pytest.raises(ConfigError) as exc:
            create_auth_provider(config)
        assert "auth_url" in str(exc.value.message).lower()

    def test_create_oauth2_missing_token_url(self):
        """OAuth2 auth without token_url raises error."""
        config = AuthConfig(
            type=AuthType.OAUTH2,
            client_id="my-client",
            auth_url="https://auth.example.com/authorize",
        )
        with pytest.raises(ConfigError) as exc:
            create_auth_provider(config)
        assert "token_url" in str(exc.value.message).lower()
