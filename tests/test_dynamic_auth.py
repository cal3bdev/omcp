"""Tests for dynamic authentication functionality."""

from __future__ import annotations

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

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
    InvalidAuthSchemeError,
    InvalidTokenError,
    MissingAuthError,
    MissingTokenError,
    TokenExpiredError,
)
from omcp.auth.httpx_auth import DynamicTokenAuth, StaticTokenAuth
from omcp.auth.middleware import extract_token
from omcp.config.models import (
    AuthConfig,
    AuthHeaderConfig,
    AuthType,
    JWTValidationConfig,
)


class TestTokenClaims:
    """Tests for TokenClaims parsing."""

    def test_from_jwt_basic_claims(self):
        """Test parsing basic JWT claims."""
        claims = {
            "sub": "user123",
            "iss": "https://auth.example.com",
            "aud": "my-api",
            "exp": 1700000000,
            "iat": 1699999000,
        }
        token_claims = TokenClaims.from_jwt(claims)

        assert token_claims.sub == "user123"
        assert token_claims.iss == "https://auth.example.com"
        assert token_claims.aud == "my-api"
        assert token_claims.exp == datetime.fromtimestamp(1700000000)
        assert token_claims.iat == datetime.fromtimestamp(1699999000)
        assert token_claims.raw == claims

    def test_from_jwt_with_scope_string(self):
        """Test parsing scope as space-separated string."""
        claims = {"sub": "user123", "scope": "read write admin"}
        token_claims = TokenClaims.from_jwt(claims)

        assert token_claims.scopes == ["read", "write", "admin"]

    def test_from_jwt_with_scopes_list(self):
        """Test parsing scopes as list."""
        claims = {"sub": "user123", "scopes": ["read", "write"]}
        token_claims = TokenClaims.from_jwt(claims)

        assert token_claims.scopes == ["read", "write"]

    def test_from_jwt_no_expiry(self):
        """Test claims without expiry."""
        claims = {"sub": "user123"}
        token_claims = TokenClaims.from_jwt(claims)

        assert token_claims.exp is None
        assert token_claims.iat is None


class TestAuthContext:
    """Tests for AuthContext."""

    def test_user_id_from_claims(self):
        """Test extracting user ID from claims."""
        claims = TokenClaims(sub="user123")
        ctx = AuthContext(token="abc", claims=claims, validated=True)

        assert ctx.user_id == "user123"

    def test_user_id_no_claims(self):
        """Test user ID when no claims."""
        ctx = AuthContext(token="abc", validated=False)

        assert ctx.user_id is None

    def test_scopes_from_claims(self):
        """Test extracting scopes from claims."""
        claims = TokenClaims(scopes=["read", "write"])
        ctx = AuthContext(token="abc", claims=claims, validated=True)

        assert ctx.scopes == ["read", "write"]

    def test_has_scope(self):
        """Test scope checking."""
        claims = TokenClaims(scopes=["read", "write"])
        ctx = AuthContext(token="abc", claims=claims, validated=True)

        assert ctx.has_scope("read") is True
        assert ctx.has_scope("admin") is False

    def test_get_claim(self):
        """Test getting arbitrary claims."""
        claims = TokenClaims(raw={"custom_claim": "value123"})
        ctx = AuthContext(token="abc", claims=claims, validated=True)

        assert ctx.get_claim("custom_claim") == "value123"
        assert ctx.get_claim("missing", "default") == "default"


class TestExtractToken:
    """Tests for token extraction from headers."""

    def test_extract_bearer_token(self):
        """Test extracting bearer token."""
        token = extract_token("Bearer my-token-123")
        assert token == "my-token-123"

    def test_extract_bearer_case_insensitive(self):
        """Test bearer scheme is case insensitive."""
        token = extract_token("bearer my-token")
        assert token == "my-token"

        token = extract_token("BEARER my-token")
        assert token == "my-token"

    def test_missing_header_raises(self):
        """Test missing header raises error."""
        with pytest.raises(MissingAuthError):
            extract_token(None)

    def test_empty_header_raises(self):
        """Test empty header raises error."""
        with pytest.raises(MissingAuthError):
            extract_token("")

    def test_wrong_scheme_raises(self):
        """Test wrong scheme raises error."""
        with pytest.raises(InvalidAuthSchemeError) as exc_info:
            extract_token("Basic dXNlcjpwYXNz")

        assert "Basic" in str(exc_info.value)

    def test_bearer_no_token_raises(self):
        """Test Bearer without token raises error."""
        with pytest.raises(MissingTokenError):
            extract_token("Bearer ")

    def test_just_bearer_raises(self):
        """Test just 'Bearer' with no space raises error."""
        with pytest.raises(MissingTokenError):
            extract_token("Bearer")

    def test_token_whitespace_trimmed(self):
        """Test token whitespace is trimmed."""
        token = extract_token("Bearer   my-token  ")
        assert token == "my-token"


class TestContextVariable:
    """Tests for auth context variable management."""

    def test_set_and_get_context(self):
        """Test setting and getting auth context."""
        ctx = AuthContext(token="test-token", validated=False)

        token = set_current_auth_context(ctx)
        try:
            retrieved = get_current_auth_context()

            assert retrieved is ctx
            assert retrieved.token == "test-token"
        finally:
            # Proper cleanup using reset
            reset_auth_context(token)

    def test_default_context_is_none(self):
        """Test default context is None."""
        token = set_current_auth_context(None)
        try:
            assert get_current_auth_context() is None
        finally:
            reset_auth_context(token)

    def test_context_scope_manager(self):
        """Test auth_context_scope context manager."""
        ctx = AuthContext(token="scoped-token", validated=False)

        # Verify context is None before
        assert get_current_auth_context() is None

        with auth_context_scope(ctx):
            # Context is set inside scope
            retrieved = get_current_auth_context()
            assert retrieved is ctx
            assert retrieved.token == "scoped-token"

        # Context is reset after scope
        assert get_current_auth_context() is None

    def test_context_scope_restores_previous_value(self):
        """Test that context manager restores previous value, not just None."""
        outer_ctx = AuthContext(token="outer-token", validated=False)
        inner_ctx = AuthContext(token="inner-token", validated=False)

        outer_token = set_current_auth_context(outer_ctx)
        try:
            assert get_current_auth_context() is outer_ctx

            with auth_context_scope(inner_ctx):
                assert get_current_auth_context() is inner_ctx

            # Should restore to outer context, not None
            assert get_current_auth_context() is outer_ctx
        finally:
            reset_auth_context(outer_token)

    def test_context_scope_cleanup_on_exception(self):
        """Test that context is properly reset even when exception occurs."""
        ctx = AuthContext(token="exception-test", validated=False)

        assert get_current_auth_context() is None

        with pytest.raises(ValueError):
            with auth_context_scope(ctx):
                assert get_current_auth_context() is ctx
                raise ValueError("Test exception")

        # Context should be reset despite exception
        assert get_current_auth_context() is None


class TestDynamicAuth:
    """Tests for DynamicAuth provider."""

    def create_config(
        self,
        validation_enabled: bool = False,
        scheme: str = "Bearer",
    ) -> AuthConfig:
        """Create test auth config."""
        return AuthConfig(
            type=AuthType.JWT,
            validation=JWTValidationConfig(enabled=validation_enabled),
            header=AuthHeaderConfig(name="Authorization", scheme=scheme),
        )

    def test_extract_token_success(self):
        """Test token extraction from header."""
        config = self.create_config()
        auth = DynamicAuth(config)

        token = auth.extract_token("Bearer my-token")
        assert token == "my-token"

    def test_extract_token_missing_raises(self):
        """Test missing token raises error."""
        config = self.create_config()
        auth = DynamicAuth(config)

        with pytest.raises(MissingAuthError):
            auth.extract_token(None)

    @pytest.mark.asyncio
    async def test_authenticate_no_validation(self):
        """Test authentication without validation."""
        config = self.create_config(validation_enabled=False)
        auth = DynamicAuth(config)

        ctx = await auth.authenticate("Bearer my-token")

        assert ctx.token == "my-token"
        assert ctx.validated is False
        assert ctx.claims is None

    @pytest.mark.asyncio
    async def test_authenticate_with_validation(self):
        """Test authentication with JWT validation."""
        config = self.create_config(validation_enabled=True)

        # Mock JWT validator
        mock_validator = MagicMock()
        mock_validator.validate = AsyncMock(
            return_value={"sub": "user123", "exp": 1700000000}
        )

        auth = DynamicAuth(config, jwt_validator=mock_validator)
        ctx = await auth.authenticate("Bearer my-token")

        assert ctx.token == "my-token"
        assert ctx.validated is True
        assert ctx.claims.sub == "user123"
        mock_validator.validate.assert_called_once_with("my-token")

    def test_get_headers_from_context(self):
        """Test getting headers from context."""
        config = self.create_config()
        auth = DynamicAuth(config)

        # Set context
        ctx = AuthContext(token="test-token", validated=False)
        token = set_current_auth_context(ctx)

        try:
            headers = auth.get_headers_sync()
            assert headers == {"Authorization": "Bearer test-token"}
        finally:
            reset_auth_context(token)

    def test_get_headers_no_context(self):
        """Test headers when no context set."""
        config = self.create_config()
        auth = DynamicAuth(config)

        token = set_current_auth_context(None)
        try:
            headers = auth.get_headers_sync()
            assert headers == {}
        finally:
            reset_auth_context(token)

    def test_is_valid_with_context(self):
        """Test is_valid when context is set."""
        config = self.create_config()
        auth = DynamicAuth(config)

        ctx = AuthContext(token="test-token", validated=False)
        token = set_current_auth_context(ctx)

        try:
            assert auth.is_valid() is True
        finally:
            reset_auth_context(token)

    def test_is_valid_no_context(self):
        """Test is_valid when no context."""
        config = self.create_config()
        auth = DynamicAuth(config)

        token = set_current_auth_context(None)
        try:
            assert auth.is_valid() is False
        finally:
            reset_auth_context(token)


class TestDynamicTokenAuth:
    """Tests for httpx DynamicTokenAuth."""

    def test_adds_token_from_context(self):
        """Test token is added from context."""
        auth = DynamicTokenAuth(header_name="Authorization", scheme="Bearer")

        # Set context
        ctx = AuthContext(token="test-token", validated=False)
        context_token = set_current_auth_context(ctx)

        try:
            # Create mock request
            import httpx

            request = httpx.Request("GET", "https://api.example.com/test")

            # Run auth flow
            flow = auth.auth_flow(request)
            modified_request = next(flow)

            assert modified_request.headers["Authorization"] == "Bearer test-token"
        finally:
            reset_auth_context(context_token)

    def test_no_token_without_context(self):
        """Test no token added when no context."""
        auth = DynamicTokenAuth()

        context_token = set_current_auth_context(None)
        try:
            import httpx

            request = httpx.Request("GET", "https://api.example.com/test")

            flow = auth.auth_flow(request)
            modified_request = next(flow)

            assert "Authorization" not in modified_request.headers
        finally:
            reset_auth_context(context_token)


class TestStaticTokenAuth:
    """Tests for httpx StaticTokenAuth."""

    def test_adds_bearer_token(self):
        """Test static bearer token is added."""
        auth = StaticTokenAuth(token="static-token", scheme="Bearer")

        import httpx

        request = httpx.Request("GET", "https://api.example.com/test")

        flow = auth.auth_flow(request)
        modified_request = next(flow)

        assert modified_request.headers["Authorization"] == "Bearer static-token"

    def test_adds_raw_token(self):
        """Test raw token without scheme."""
        auth = StaticTokenAuth(token="api-key-123", scheme=None, header_name="X-API-Key")

        import httpx

        request = httpx.Request("GET", "https://api.example.com/test")

        flow = auth.auth_flow(request)
        modified_request = next(flow)

        assert modified_request.headers["X-API-Key"] == "api-key-123"


class TestAuthErrors:
    """Tests for auth error types."""

    def test_auth_error_to_dict(self):
        """Test error conversion to dict."""
        error = MissingAuthError()
        data = error.to_dict()

        assert data["error_code"] == "missing_auth"
        assert "Authorization" in data["error_message"]
        assert "hint" in data

    def test_invalid_token_with_reason(self):
        """Test invalid token error with reason."""
        error = InvalidTokenError("signature verification failed")

        assert "signature verification failed" in str(error)
        assert error.status_code == 401

    def test_token_expired_error(self):
        """Test token expired error."""
        error = TokenExpiredError()

        assert error.code == "token_expired"
        assert error.status_code == 401


class TestCreateDynamicAuth:
    """Tests for create_dynamic_auth factory."""

    def test_creates_without_validation(self):
        """Test creating auth without validation."""
        config = AuthConfig(
            type=AuthType.JWT,
            validation=JWTValidationConfig(enabled=False),
        )

        auth = create_dynamic_auth(config)

        assert isinstance(auth, DynamicAuth)
        assert auth.jwt_validator is None

    def test_creates_with_validation_no_jwks(self):
        """Test creating auth with validation but no JWKS URL."""
        config = AuthConfig(
            type=AuthType.JWT,
            validation=JWTValidationConfig(enabled=True, jwks_url=None),
        )

        auth = create_dynamic_auth(config)

        assert isinstance(auth, DynamicAuth)
        # No validator created without JWKS URL
        assert auth.jwt_validator is None


class TestAuthFactory:
    """Tests for auth factory JWT support."""

    def test_create_jwt_auth(self):
        """Test factory creates DynamicAuth for JWT type."""
        from omcp.auth.factory import create_auth_provider

        config = AuthConfig(
            type=AuthType.JWT,
            validation=JWTValidationConfig(enabled=False),
        )

        auth = create_auth_provider(config)

        assert isinstance(auth, DynamicAuth)
