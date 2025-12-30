"""Tests for endpoint filtering."""

from pathlib import Path

import pytest

from omcp.filters import (
    EndpointFilter,
    FilterPattern,
    RouteMap,
    build_route_map,
    parse_pattern,
    parse_patterns,
)
from omcp.spec import load_spec_sync, normalize_spec


FIXTURES = Path(__file__).parent / "fixtures"


class TestFilterPatternParsing:
    """Test filter pattern parsing."""

    def test_parse_method_and_path(self):
        """Parse METHOD /path pattern."""
        pattern = parse_pattern("GET /users/*")
        assert pattern.method == "GET"
        assert pattern.path_pattern == "/users/*"

    def test_parse_method_only(self):
        """Parse METHOD * pattern."""
        pattern = parse_pattern("DELETE *")
        assert pattern.method == "DELETE"
        assert pattern.path_pattern is None

    def test_parse_path_only(self):
        """Parse /path pattern (no method)."""
        pattern = parse_pattern("/admin/*")
        assert pattern.method is None
        assert pattern.path_pattern == "/admin/*"

    def test_parse_wildcard_method(self):
        """Parse * /path pattern."""
        pattern = parse_pattern("* /health")
        assert pattern.method is None
        assert pattern.path_pattern == "/health"

    def test_parse_multiple(self):
        """Parse multiple patterns."""
        patterns = parse_patterns(["GET /users", "DELETE *", "/admin/*"])
        assert len(patterns) == 3

    def test_parse_empty_raises(self):
        """Empty pattern raises error."""
        with pytest.raises(ValueError):
            parse_pattern("")


class TestFilterPatternMatching:
    """Test filter pattern matching."""

    def test_exact_method_and_path(self):
        """Exact method and path match."""
        pattern = parse_pattern("GET /users")
        assert pattern.matches("GET", "/users") is True
        assert pattern.matches("POST", "/users") is False
        assert pattern.matches("GET", "/posts") is False

    def test_method_case_insensitive(self):
        """Method matching is case insensitive."""
        pattern = parse_pattern("get /users")
        assert pattern.matches("GET", "/users") is True
        assert pattern.matches("get", "/users") is True

    def test_path_wildcard(self):
        """Path wildcard matching."""
        pattern = parse_pattern("GET /users/*")
        assert pattern.matches("GET", "/users/123") is True
        assert pattern.matches("GET", "/users/abc") is True
        assert pattern.matches("GET", "/users") is False  # No trailing segment

    def test_path_double_wildcard(self):
        """Double wildcard matches multiple segments."""
        pattern = parse_pattern("GET /api/**")
        assert pattern.matches("GET", "/api/users") is True
        assert pattern.matches("GET", "/api/users/123") is True
        assert pattern.matches("GET", "/api/users/123/posts") is True

    def test_method_only_wildcard(self):
        """Method only pattern matches all paths."""
        pattern = parse_pattern("DELETE *")
        assert pattern.matches("DELETE", "/users") is True
        assert pattern.matches("DELETE", "/posts/123") is True
        assert pattern.matches("GET", "/users") is False

    def test_path_only_matches_all_methods(self):
        """Path only pattern matches all methods."""
        pattern = parse_pattern("/admin/*")
        assert pattern.matches("GET", "/admin/users") is True
        assert pattern.matches("POST", "/admin/settings") is True
        assert pattern.matches("DELETE", "/admin/data") is True
        assert pattern.matches("GET", "/users") is False


class TestEndpointFilter:
    """Test endpoint filtering."""

    def test_no_filters_includes_all(self):
        """No filters means include everything."""
        filt = EndpointFilter()
        result = filt.should_include("GET", "/users")
        assert result.included is True

    def test_exclude_pattern(self):
        """Exclude pattern excludes matching endpoints."""
        filt = EndpointFilter(exclude_patterns=["DELETE *"])
        assert filt.should_include("DELETE", "/users").included is False
        assert filt.should_include("GET", "/users").included is True

    def test_include_pattern(self):
        """Include pattern only includes matching endpoints."""
        filt = EndpointFilter(include_patterns=["GET /users/*"])
        assert filt.should_include("GET", "/users/123").included is True
        assert filt.should_include("POST", "/users").included is False
        assert filt.should_include("GET", "/posts").included is False

    def test_include_overrides_exclude(self):
        """Include can override exclude for specific endpoints."""
        filt = EndpointFilter(
            include_patterns=["GET /admin/status"],
            exclude_patterns=["/admin/*"],
        )
        # /admin/* is excluded, but GET /admin/status is explicitly included
        assert filt.should_include("GET", "/admin/status").included is True
        assert filt.should_include("GET", "/admin/users").included is False

    def test_filter_operations(self):
        """Filter a list of operations."""
        filt = EndpointFilter(exclude_patterns=["DELETE *"])
        operations = [
            ("GET", "/users"),
            ("POST", "/users"),
            ("DELETE", "/users/123"),
            ("GET", "/posts"),
        ]
        filtered = filt.filter_operations(operations)
        assert len(filtered) == 3
        assert ("DELETE", "/users/123") not in filtered


class TestRouteMap:
    """Test route map building."""

    def test_build_route_map_no_filters(self):
        """Build route map with no filters includes all ops."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        normalized = normalize_spec(spec, "https://api.example.com")

        route_map = build_route_map(normalized)

        included = route_map.get_included_operations()
        assert len(included) == 5  # All operations

    def test_build_route_map_with_exclude(self):
        """Build route map with exclude filter."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        normalized = normalize_spec(spec, "https://api.example.com")

        route_map = build_route_map(
            normalized,
            exclude_patterns=["DELETE *"],
        )

        included = route_map.get_included_operations()
        excluded = route_map.get_excluded_operations()

        # Should exclude DELETE /pets/{petId}
        assert any(op.method == "DELETE" for op in excluded)
        assert not any(op.method == "DELETE" for op in included)

    def test_build_route_map_with_overrides(self):
        """Build route map with tool name overrides."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        normalized = normalize_spec(spec, "https://api.example.com")

        route_map = build_route_map(
            normalized,
            tool_overrides={
                "listPets": {"name": "get_all_pets", "description": "Fetch all pets"},
            },
        )

        names = route_map.to_fastmcp_names()
        assert names.get("listPets") == "get_all_pets"
        assert route_map.description_overrides.get("listPets") == "Fetch all pets"

    def test_to_fastmcp_routes(self):
        """Convert to FastMCP route format."""
        spec = load_spec_sync(str(FIXTURES / "petstore.json"))
        normalized = normalize_spec(spec, "https://api.example.com")

        route_map = build_route_map(normalized)
        routes = route_map.to_fastmcp_routes()

        assert "GET /pets" in routes
        assert "POST /pets" in routes
        assert "GET /pets/{petId}" in routes
