"""MCP server builder using FastMCP."""

from __future__ import annotations

from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.openapi import MCPType

from omcp.auth import AuthProvider, create_auth_provider
from omcp.config.models import AuthType, OMCPConfig
from omcp.filters import RouteMap, build_route_map
from omcp.spec import NormalizedSpec, load_spec_sync, normalize_spec, validate_spec

from fastmcp.server.auth import AuthProvider as FastMCPAuthProvider


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
    def is_jwt_auth(self) -> bool:
        """Check if JWT auth is configured."""
        return self.config.auth.type == AuthType.JWT

    @property
    def jwt_validation_enabled(self) -> bool:
        """Check if JWT validation is enabled (vs passthrough)."""
        return self.is_jwt_auth and self.config.auth.validation.enabled

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
        """Create configured HTTP client.

        For JWT auth (both passthrough and validation modes), FastMCP
        automatically forwards headers from the incoming request to upstream
        via get_http_headers(). No special httpx auth is needed.

        For static auth types (API key, bearer), headers are set directly.
        """
        # Start with advanced headers from config
        headers = dict(self.config.advanced.headers)

        # For static auth types, add headers directly
        # JWT auth relies on FastMCP's automatic header forwarding
        if self.config.auth.type not in (AuthType.JWT, AuthType.NONE):
            auth_headers = self.auth.get_headers_sync()
            headers.update(auth_headers)

        return httpx.AsyncClient(
            base_url=self.spec.base_url,
            headers=headers,
            timeout=httpx.Timeout(self.config.server.timeout),
        )

    def _create_route_map_fn(self) -> Any:
        """Create a route mapping function for FastMCP endpoint filtering.

        Returns a function that determines which routes to include/exclude.
        FastMCPOpenAPI calls this with (route, mcp_type) and expects:
        - MCPType.EXCLUDE to exclude the route
        - MCPType.TOOL/RESOURCE/etc to include with that type
        - None to use the default type
        """
        # Build set of excluded operation IDs for fast lookup
        excluded_ops = {op.operation_id for op in self.route_map.get_excluded_operations()}

        def route_map_fn(route: Any, current_type: MCPType) -> MCPType | None:
            op_id = getattr(route, "operation_id", None)

            # If this operation should be excluded, return EXCLUDE
            if op_id and op_id in excluded_ops:
                return MCPType.EXCLUDE

            # Otherwise, keep the default type
            return None

        return route_map_fn

    def _create_component_fn(self) -> Any | None:
        """Create a component customization function for FastMCP.

        Returns a function that customizes components (e.g., description overrides).
        FastMCPOpenAPI calls this with (route, component) to modify in-place.

        Returns None if no customization is needed.
        """
        desc_overrides = self.route_map.description_overrides

        # If no overrides, no need for a component function
        if not desc_overrides:
            return None

        def component_fn(route: Any, component: Any) -> None:
            # Get operation ID from route
            op_id = getattr(route, "operation_id", None)

            # Apply description override if present
            if op_id and op_id in desc_overrides:
                component.description = desc_overrides[op_id]

        return component_fn

    def _create_fastmcp_auth(self) -> FastMCPAuthProvider | None:
        """Create FastMCP auth provider for JWT validation.

        For JWT auth with validation enabled, creates a JWTVerifier that
        validates tokens before processing requests. FastMCP still handles
        header forwarding to upstream automatically.

        For passthrough mode (validation disabled), returns None - FastMCP's
        built-in header forwarding handles passing the Authorization header
        to upstream APIs.

        Returns:
            JWTVerifier for validation mode, None for passthrough
        """
        if not self.jwt_validation_enabled:
            return None

        from fastmcp.server.auth.providers.jwt import JWTVerifier

        validation = self.config.auth.validation

        # Build JWTVerifier kwargs based on config
        kwargs: dict[str, Any] = {}

        if validation.jwks_url:
            # Enforce HTTPS for JWKS endpoints (allow localhost for development)
            from urllib.parse import urlparse
            parsed = urlparse(validation.jwks_url)
            is_localhost = parsed.hostname in ("localhost", "127.0.0.1")
            if parsed.scheme != "https" and not is_localhost:
                raise ValueError(
                    f"JWKS URL must use HTTPS for security: {validation.jwks_url}. "
                    "Only localhost URLs are allowed to use HTTP for development."
                )
            kwargs["jwks_uri"] = validation.jwks_url
        elif validation.issuer:
            # For symmetric/static key validation, we'd need a public_key
            # For now, require JWKS URL for validation
            raise ValueError(
                "JWT validation requires jwks_url to be configured. "
                "Set validation.enabled=false for passthrough mode."
            )

        if validation.issuer:
            kwargs["issuer"] = validation.issuer
        if validation.audience:
            kwargs["audience"] = validation.audience
        if validation.algorithms and len(validation.algorithms) > 0:
            kwargs["algorithm"] = validation.algorithms[0]

        return JWTVerifier(**kwargs)

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

        # Create route filter for include/exclude
        route_map_fn = self._create_route_map_fn()

        # Create component customization function (for description overrides)
        component_fn = self._create_component_fn()

        # Use FastMCP's OpenAPI integration - from_openapi is a CLASS METHOD
        # that returns a new FastMCPOpenAPI instance (subclass of FastMCP)
        mcp = FastMCP.from_openapi(
            openapi_spec=self.spec.spec,
            client=http_client,
            route_map_fn=route_map_fn,
            mcp_component_fn=component_fn,
            mcp_names=mcp_names if mcp_names else None,
            name=self.config.name,
        )

        # Set FastMCP auth for JWT validation mode
        # Passthrough mode relies on FastMCP's automatic header forwarding
        fastmcp_auth = self._create_fastmcp_auth()
        if fastmcp_auth:
            mcp.auth = fastmcp_auth

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

    def get_asgi_middleware(self) -> list[Any]:
        """Get ASGI middleware for HTTP transport.

        Note: For JWT auth, FastMCP handles authentication natively via its
        auth provider system. Custom middleware is no longer needed.

        Returns:
            Empty list (middleware handled by FastMCP auth provider)
        """
        # JWT auth is now handled by FastMCP's built-in auth provider
        # (JWTVerifier set on mcp.auth in build())
        # Header forwarding for passthrough is automatic via get_http_headers()
        return []


def build_server(config: OMCPConfig) -> FastMCP:
    """Build an MCP server from configuration.

    Args:
        config: OMCP configuration

    Returns:
        Configured FastMCP server
    """
    builder = ServerBuilder(config)
    return builder.build()
