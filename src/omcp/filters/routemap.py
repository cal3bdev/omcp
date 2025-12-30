"""RouteMap generation for FastMCP OpenAPI integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from omcp.filters.parser import EndpointFilter
from omcp.spec.normalizer import NormalizedSpec, OperationInfo


@dataclass
class RouteMapEntry:
    """A single route map entry for FastMCP."""

    operation_id: str
    method: str
    path: str
    tool_name: str | None = None  # Override tool name
    description: str | None = None  # Override description
    include: bool = True  # Whether to include this route


@dataclass
class RouteMap:
    """Route map configuration for FastMCP.

    Controls which endpoints become MCP tools and how they're named.
    """

    entries: list[RouteMapEntry] = field(default_factory=list)

    # Tool name overrides: operationId -> tool_name
    name_overrides: dict[str, str] = field(default_factory=dict)

    # Description overrides: operationId -> description
    description_overrides: dict[str, str] = field(default_factory=dict)

    def get_included_operations(self) -> list[RouteMapEntry]:
        """Get all included route entries."""
        return [e for e in self.entries if e.include]

    def get_excluded_operations(self) -> list[RouteMapEntry]:
        """Get all excluded route entries."""
        return [e for e in self.entries if not e.include]

    def to_fastmcp_routes(self) -> list[str]:
        """Convert to FastMCP route list format.

        Returns list of "METHOD /path" strings for included routes.
        """
        return [f"{e.method} {e.path}" for e in self.entries if e.include]

    def to_fastmcp_names(self) -> dict[str, str]:
        """Get tool name mapping for FastMCP.

        Returns operationId -> tool_name mapping.
        """
        names = dict(self.name_overrides)
        for entry in self.entries:
            if entry.include and entry.tool_name:
                names[entry.operation_id] = entry.tool_name
        return names


def build_route_map(
    spec: NormalizedSpec,
    include_patterns: Sequence[str] | None = None,
    exclude_patterns: Sequence[str] | None = None,
    tool_overrides: dict[str, dict[str, str]] | None = None,
) -> RouteMap:
    """Build a RouteMap from a normalized spec with filtering.

    Args:
        spec: Normalized OpenAPI spec
        include_patterns: Patterns for endpoints to include
        exclude_patterns: Patterns for endpoints to exclude
        tool_overrides: Per-operationId overrides {opId: {name: ..., description: ...}}

    Returns:
        RouteMap with filtered and configured routes
    """
    endpoint_filter = EndpointFilter(include_patterns, exclude_patterns)
    tool_overrides = tool_overrides or {}

    route_map = RouteMap()

    for op in spec.operations:
        # Check if operation should be included
        filter_result = endpoint_filter.should_include(op.method, op.path)

        # Get any overrides for this operation
        overrides = tool_overrides.get(op.operation_id, {})

        entry = RouteMapEntry(
            operation_id=op.operation_id,
            method=op.method,
            path=op.path,
            tool_name=overrides.get("name"),
            description=overrides.get("description"),
            include=filter_result.included,
        )

        route_map.entries.append(entry)

        # Store overrides in route_map level dicts too
        if overrides.get("name"):
            route_map.name_overrides[op.operation_id] = overrides["name"]
        if overrides.get("description"):
            route_map.description_overrides[op.operation_id] = overrides["description"]

    return route_map


def create_component_callback(
    route_map: RouteMap,
) -> Callable[[dict[str, Any]], dict[str, Any] | None]:
    """Create a FastMCP component callback for customizing tools.

    The callback is called for each tool component and can:
    - Return None to exclude the tool
    - Return modified component dict to customize it
    - Return component unchanged to keep defaults

    Args:
        route_map: RouteMap with configuration

    Returns:
        Callback function for FastMCP
    """

    def callback(component: dict[str, Any]) -> dict[str, Any] | None:
        # Get operation ID from component
        # FastMCP stores this in the component metadata
        op_id = component.get("operationId") or component.get("name", "")

        # Check if this operation should be excluded
        for entry in route_map.entries:
            if entry.operation_id == op_id and not entry.include:
                return None

        # Apply description override
        if op_id in route_map.description_overrides:
            component = dict(component)
            component["description"] = route_map.description_overrides[op_id]

        return component

    return callback
