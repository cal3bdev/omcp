"""Tests for single server build and run."""

from pathlib import Path

import pytest

from omcp.config import load_config
from omcp.config.models import ToolOverride
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
