"""MCP server builder using FastMCP."""

from __future__ import annotations

from typing import Any

import httpx
from fastmcp import FastMCP

from omcp.auth import AuthProvider, create_auth_provider
from omcp.config.models import OMCPConfig
from omcp.filters import RouteMap, build_route_map
from omcp.spec import NormalizedSpec, load_spec_sync, normalize_spec, validate_spec


class ServerBuilder:
    """Builder for creating MCP servers from OpenAPI specs."""

    def __init__(self, config: OMCPConfig) -> None:
        """Initialize the server builder.

        Args:
            config: OMCP configuration
        """
        self.config = config
        self._spec: NormalizedSpec | None = None
        self._auth: AuthProvider | None = None
        self._route_map: RouteMap | None = None
        self._mcp: FastMCP | None = None

    @property
    def spec(self) -> NormalizedSpec:
        """Get the normalized spec, loading if necessary."""
        if self._spec is None:
            self._spec = self._load_and_normalize_spec()
        return self._spec

    @property
    def auth(self) -> AuthProvider:
        """Get the auth provider, creating if necessary."""
        if self._auth is None:
            self._auth = create_auth_provider(
                self.config.auth,
                provider_name=self.config.name,
            )
        return self._auth

    @property
    def route_map(self) -> RouteMap:
        """Get the route map, building if necessary."""
        if self._route_map is None:
            self._route_map = self._build_route_map()
        return self._route_map

    def _load_and_normalize_spec(self) -> NormalizedSpec:
        """Load and normalize the OpenAPI spec."""
        raw_spec = load_spec_sync(self.config.spec)
        validate_spec(raw_spec)
        return normalize_spec(raw_spec, self.config.base_url)

    def _build_route_map(self) -> RouteMap:
        """Build route map with filters and overrides."""
        # Convert tool overrides from config format
        tool_overrides: dict[str, dict[str, str]] = {}
        for op_id, override in self.config.tools.items():
            tool_overrides[op_id] = {}
            if override.name:
                tool_overrides[op_id]["name"] = override.name
            if override.description:
                tool_overrides[op_id]["description"] = override.description

        return build_route_map(
            self.spec,
            include_patterns=self.config.endpoints.include or None,
            exclude_patterns=self.config.endpoints.exclude or None,
            tool_overrides=tool_overrides,
        )

    def _create_http_client(self) -> httpx.AsyncClient:
        """Create configured HTTP client with auth."""
        # Get auth headers
        auth_headers = self.auth.get_headers_sync()

        # Merge with advanced headers from config
        headers = {**self.config.advanced.headers, **auth_headers}

        return httpx.AsyncClient(
            base_url=self.spec.base_url,
            headers=headers,
            timeout=httpx.Timeout(self.config.server.timeout),
        )

    def _create_component_filter(self) -> Any:
        """Create a component filter function for FastMCP.

        Returns a function that filters out excluded operations and
        applies description overrides.

        Note: FastMCP passes HTTPRoute Pydantic model objects, not dicts.
        """
        # Build sets for fast lookup
        included_ops = {op.operation_id for op in self.route_map.get_included_operations()}
        desc_overrides = self.route_map.description_overrides

        def component_fn(component: Any, openapi_spec: Any = None) -> Any | None:
            # Get operation ID from HTTPRoute object
            op_id = getattr(component, "operation_id", None)

            # Check if this operation should be excluded
            if op_id and op_id not in included_ops:
                return None

            # Apply description override if present
            if op_id and op_id in desc_overrides:
                # HTTPRoute is a Pydantic model - use model_copy to modify
                component = component.model_copy(update={"description": desc_overrides[op_id]})

            return component

        return component_fn

    def build(self) -> FastMCP:
        """Build the FastMCP server.

        Returns:
            Configured FastMCP server instance
        """
        if self._mcp is not None:
            return self._mcp

        # Get tool name overrides
        mcp_names = self.route_map.to_fastmcp_names()

        # Create HTTP client
        http_client = self._create_http_client()

        # Create component filter for include/exclude
        component_fn = self._create_component_filter()

        # Use FastMCP's OpenAPI integration - from_openapi is a CLASS METHOD
        # that returns a new FastMCPOpenAPI instance (subclass of FastMCP)
        mcp = FastMCP.from_openapi(
            openapi_spec=self.spec.spec,
            client=http_client,
            mcp_component_fn=component_fn,
            mcp_names=mcp_names if mcp_names else None,
            name=self.config.name,
        )

        self._mcp = mcp
        return mcp

    def get_tool_list(self) -> list[dict[str, Any]]:
        """Get list of tools that will be exposed.

        Returns:
            List of tool info dicts with name, description, method, path
        """
        tools = []
        for entry in self.route_map.get_included_operations():
            # Find the operation info
            op_info = next(
                (op for op in self.spec.operations if op.operation_id == entry.operation_id),
                None,
            )

            tool_name = entry.tool_name or entry.operation_id
            description = entry.description or (op_info.summary if op_info else "")

            tools.append({
                "name": tool_name,
                "operation_id": entry.operation_id,
                "method": entry.method,
                "path": entry.path,
                "description": description,
            })

        return tools


def build_server(config: OMCPConfig) -> FastMCP:
    """Build an MCP server from configuration.

    Args:
        config: OMCP configuration

    Returns:
        Configured FastMCP server
    """
    builder = ServerBuilder(config)
    return builder.build()
