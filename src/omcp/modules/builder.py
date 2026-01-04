"""Module builder - build FastMCP servers for individual modules."""

from __future__ import annotations

from typing import Any

import httpx
from fastmcp import FastMCP
from fastmcp.server.auth import AuthProvider as FastMCPAuthProvider

from omcp.auth import AuthProvider
from omcp.config.models import AuthType, OMCPConfig
from omcp.modules.splitter import ModuleDefinition
from omcp.spec.normalizer import NormalizedSpec


class ModuleBuilder:
    """Builder for creating MCP servers for individual modules."""

    def __init__(
        self,
        module: ModuleDefinition,
        spec: NormalizedSpec,
        config: OMCPConfig,
        auth: AuthProvider,
    ) -> None:
        """Initialize the module builder.

        Args:
            module: Module definition with operations
            spec: Full normalized OpenAPI spec
            config: OMCP configuration
            auth: Shared auth provider
        """
        self.module = module
        self.spec = spec
        self.config = config
        self.auth = auth
        self._mcp: FastMCP | None = None

    def _create_module_spec(self) -> dict[str, Any]:
        """Create a filtered OpenAPI spec for this module.

        Returns:
            OpenAPI spec dict containing only this module's operations
        """
        # Start with a copy of the base spec
        module_spec = {
            "openapi": self.spec.spec.get("openapi", "3.0.0"),
            "info": {
                "title": f"{self.config.name} - {self.module.name}",
                "version": self.spec.spec.get("info", {}).get("version", "1.0.0"),
                "description": self.module.description,
            },
            "servers": [{"url": self.spec.base_url}],
            "paths": {},
        }

        # Get operation IDs for this module
        module_op_ids = {op.operation_id for op in self.module.operations}

        # Copy only paths/operations for this module
        original_paths = self.spec.spec.get("paths", {})
        for path, path_item in original_paths.items():
            filtered_methods = {}

            for method in ["get", "post", "put", "patch", "delete", "head", "options"]:
                if method not in path_item:
                    continue

                operation = path_item[method]
                op_id = operation.get("operationId", "")

                if op_id in module_op_ids:
                    filtered_methods[method] = operation

            if filtered_methods:
                module_spec["paths"][path] = filtered_methods

        # Copy components if present (for schema references)
        if "components" in self.spec.spec:
            module_spec["components"] = self.spec.spec["components"]

        return module_spec

    @property
    def is_jwt_auth(self) -> bool:
        """Check if JWT auth is configured."""
        return self.config.auth.type == AuthType.JWT

    @property
    def jwt_validation_enabled(self) -> bool:
        """Check if JWT validation is enabled (vs passthrough)."""
        return self.is_jwt_auth and self.config.auth.validation.enabled

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

    def _create_component_filter(self) -> Any:
        """Create a component filter for this module.

        Returns a function that filters and customizes tool components.
        """
        module_op_ids = {op.operation_id for op in self.module.operations}
        tool_descriptions = self.module.tool_descriptions

        def component_fn(component: Any, openapi_spec: Any = None) -> Any | None:
            # Get operation ID from HTTPRoute object
            op_id = getattr(component, "operation_id", None)

            # Filter out operations not in this module
            if op_id and op_id not in module_op_ids:
                return None

            # Apply description override
            if op_id and op_id in tool_descriptions:
                # HTTPRoute is a Pydantic model - use model_copy to modify
                component = component.model_copy(update={"description": tool_descriptions[op_id]})

            return component

        return component_fn

    def _create_mcp_names(self) -> dict[str, str] | None:
        """Create tool name mapping from plan.

        Returns:
            Dict mapping operationId to tool_name, or None if no overrides
        """
        if not self.module.tool_names:
            return None
        return self.module.tool_names

    def get_tool_names(self) -> list[str]:
        """Get the list of tool names this module will expose.

        Returns:
            List of tool names (using plan names if available, else operation IDs)
        """
        if self.module.tool_names:
            return list(self.module.tool_names.values())
        return [op.operation_id for op in self.module.operations]

    def _create_fastmcp_auth(self) -> FastMCPAuthProvider | None:
        """Create FastMCP auth provider for JWT validation.

        For JWT auth with validation enabled, creates a JWTVerifier.
        For passthrough mode, returns None - FastMCP handles header forwarding.

        Returns:
            JWTVerifier for validation mode, None for passthrough
        """
        if not self.jwt_validation_enabled:
            return None

        from fastmcp.server.auth.providers.jwt import JWTVerifier

        validation = self.config.auth.validation

        kwargs: dict[str, Any] = {}

        if validation.jwks_url:
            # Enforce HTTPS for JWKS endpoints in production
            if not validation.jwks_url.startswith("https://"):
                import warnings
                warnings.warn(
                    f"JWKS URL should use HTTPS for security: {validation.jwks_url}",
                    UserWarning,
                    stacklevel=2,
                )
            kwargs["jwks_uri"] = validation.jwks_url
        elif validation.issuer:
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
        """Build the FastMCP server for this module.

        Returns:
            Configured FastMCP server instance
        """
        if self._mcp is not None:
            return self._mcp

        # Create filtered spec for this module
        module_spec = self._create_module_spec()

        # Create HTTP client
        http_client = self._create_http_client()

        # Create component filter
        component_fn = self._create_component_filter()

        # Get tool name overrides
        mcp_names = self._create_mcp_names()

        # Create module name for server
        server_name = f"{self.config.name}:{self.module.name}"

        # Build the server from OpenAPI - from_openapi is a classmethod that returns a new instance!
        mcp = FastMCP.from_openapi(
            openapi_spec=module_spec,
            client=http_client,
            mcp_component_fn=component_fn,
            mcp_names=mcp_names,
            name=server_name,
        )

        # Set FastMCP auth for JWT validation mode
        fastmcp_auth = self._create_fastmcp_auth()
        if fastmcp_auth:
            mcp.auth = fastmcp_auth

        self._mcp = mcp
        return mcp

    def get_tool_list(self) -> list[dict[str, Any]]:
        """Get list of tools that will be exposed by this module.

        Returns:
            List of tool info dicts
        """
        tools = []
        for op in self.module.operations:
            tool_name = self.module.tool_names.get(op.operation_id, op.operation_id)
            description = self.module.tool_descriptions.get(
                op.operation_id, op.summary or op.description
            )

            tools.append({
                "name": tool_name,
                "operation_id": op.operation_id,
                "method": op.method,
                "path": op.path,
                "description": description,
                "module": self.module.name,
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
        # Header forwarding for passthrough is automatic via get_http_headers()
        return []


def build_module_server(
    module: ModuleDefinition,
    spec: NormalizedSpec,
    config: OMCPConfig,
    auth: AuthProvider,
) -> FastMCP:
    """Build a FastMCP server for a module.

    Args:
        module: Module definition
        spec: Full normalized spec
        config: OMCP configuration
        auth: Shared auth provider

    Returns:
        Configured FastMCP server
    """
    builder = ModuleBuilder(module, spec, config, auth)
    return builder.build()
