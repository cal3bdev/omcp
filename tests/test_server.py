"""Tests for single server build and run."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from omcp.config import load_config
from omcp.config.models import AuthType, JWTValidationConfig, ToolOverride
from omcp.server import ServerBuilder


FIXTURES = Path(__file__).parent / "fixtures"


class TestServerBuilder:
    """Test server builder."""

    def test_builder_loads_spec(self):
        """Builder loads and normalizes spec."""
        # Create a config that points to the fixture
        config = load_config(FIXTURES / "test_config.yaml")
        # Override spec path to use fixture
        config.spec = str(FIXTURES / "petstore.json")

        builder = ServerBuilder(config)

        assert builder.spec.title == "Pet Store API"
        assert len(builder.spec.operations) == 5

    def test_builder_creates_auth(self):
        """Builder creates auth provider."""
        config = load_config(FIXTURES / "test_config.yaml")
        config.spec = str(FIXTURES / "petstore.json")

        builder = ServerBuilder(config)

        assert builder.auth.is_valid() is True

    def test_builder_creates_route_map(self):
        """Builder creates route map."""
        config = load_config(FIXTURES / "test_config.yaml")
        config.spec = str(FIXTURES / "petstore.json")

        builder = ServerBuilder(config)

        assert len(builder.route_map.entries) == 5

    def test_builder_get_tool_list(self):
        """Builder returns tool list."""
        config = load_config(FIXTURES / "test_config.yaml")
        config.spec = str(FIXTURES / "petstore.json")

        builder = ServerBuilder(config)
        tools = builder.get_tool_list()

        assert len(tools) == 5
        assert any(t["name"] == "listPets" for t in tools)
        assert any(t["method"] == "GET" for t in tools)

    def test_builder_with_endpoint_exclude(self):
        """Builder respects endpoint exclusions."""
        config = load_config(FIXTURES / "test_config.yaml")
        config.spec = str(FIXTURES / "petstore.json")
        config.endpoints.exclude = ["DELETE *"]

        builder = ServerBuilder(config)
        tools = builder.get_tool_list()

        # Should have 4 tools (DELETE excluded)
        assert len(tools) == 4
        assert not any(t["method"] == "DELETE" for t in tools)

    def test_builder_with_tool_override(self):
        """Builder applies tool overrides."""
        config = load_config(FIXTURES / "test_config.yaml")
        config.spec = str(FIXTURES / "petstore.json")
        config.tools = {
            "listPets": ToolOverride(name="fetch_pets", description="Get all pets"),
        }

        builder = ServerBuilder(config)
        tools = builder.get_tool_list()

        pet_tool = next(t for t in tools if t["operation_id"] == "listPets")
        assert pet_tool["name"] == "fetch_pets"
        assert pet_tool["description"] == "Get all pets"


class TestServerBuilderBuild:
    """Test server builder build method."""

    def test_builder_builds_mcp(self):
        """Builder builds FastMCP server."""
        config = load_config(FIXTURES / "test_config.yaml")
        config.spec = str(FIXTURES / "petstore.json")

        builder = ServerBuilder(config)
        mcp = builder.build()

        assert mcp is not None
        assert mcp.name == "Test API"

    def test_builder_caches_mcp(self):
        """Builder caches MCP instance."""
        config = load_config(FIXTURES / "test_config.yaml")
        config.spec = str(FIXTURES / "petstore.json")

        builder = ServerBuilder(config)
        mcp1 = builder.build()
        mcp2 = builder.build()

        assert mcp1 is mcp2


class TestJWKSHttpsEnforcement:
    """Test HTTPS enforcement for JWKS URLs."""

    def test_http_jwks_url_rejected(self):
        """HTTP JWKS URLs should be rejected for non-localhost."""
        config = load_config(FIXTURES / "test_config.yaml")
        config.spec = str(FIXTURES / "petstore.json")
        config.auth.type = AuthType.JWT
        config.auth.validation = JWTValidationConfig(
            enabled=True,
            jwks_url="http://example.com/.well-known/jwks.json",
        )

        builder = ServerBuilder(config)

        with pytest.raises(ValueError) as exc:
            builder._create_fastmcp_auth()

        assert "JWKS URL must use HTTPS" in str(exc.value)

    def test_https_jwks_url_allowed(self):
        """HTTPS JWKS URLs should be allowed."""
        config = load_config(FIXTURES / "test_config.yaml")
        config.spec = str(FIXTURES / "petstore.json")
        config.auth.type = AuthType.JWT
        config.auth.validation = JWTValidationConfig(
            enabled=True,
            jwks_url="https://example.com/.well-known/jwks.json",
        )

        builder = ServerBuilder(config)

        # Mock the JWTVerifier import to avoid needing actual FastMCP
        with patch("fastmcp.server.auth.providers.jwt.JWTVerifier") as mock_verifier:
            mock_verifier.return_value = MagicMock()
            result = builder._create_fastmcp_auth()
            assert result is not None
            mock_verifier.assert_called_once()

    def test_localhost_http_allowed(self):
        """HTTP should be allowed for localhost (development)."""
        config = load_config(FIXTURES / "test_config.yaml")
        config.spec = str(FIXTURES / "petstore.json")
        config.auth.type = AuthType.JWT
        config.auth.validation = JWTValidationConfig(
            enabled=True,
            jwks_url="http://localhost:8000/.well-known/jwks.json",
        )

        builder = ServerBuilder(config)

        # Mock the JWTVerifier import
        with patch("fastmcp.server.auth.providers.jwt.JWTVerifier") as mock_verifier:
            mock_verifier.return_value = MagicMock()
            result = builder._create_fastmcp_auth()
            assert result is not None

    def test_127_0_0_1_http_allowed(self):
        """HTTP should be allowed for 127.0.0.1 (development)."""
        config = load_config(FIXTURES / "test_config.yaml")
        config.spec = str(FIXTURES / "petstore.json")
        config.auth.type = AuthType.JWT
        config.auth.validation = JWTValidationConfig(
            enabled=True,
            jwks_url="http://127.0.0.1:8000/.well-known/jwks.json",
        )

        builder = ServerBuilder(config)

        # Mock the JWTVerifier import
        with patch("fastmcp.server.auth.providers.jwt.JWTVerifier") as mock_verifier:
            mock_verifier.return_value = MagicMock()
            result = builder._create_fastmcp_auth()
            assert result is not None
