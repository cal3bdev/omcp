"""Hub runner - run the hub server."""

from __future__ import annotations

import asyncio
import signal
from typing import Any

from fastmcp import FastMCP

from omcp.config.models import HubSettings
from omcp.hub.builder import HubBuilder, build_hub
from omcp.hub.registry import HubRegistry, ToolSchema
from omcp.hub.router import HubRouter
from omcp.modules.runner import ModuleRegistry
from omcp.planner.schema import OMCPPlan
from omcp.spec.normalizer import NormalizedSpec
from omcp.utils.console import print_info, print_success


class HubRunner:
    """Runner for the Hub MCP server."""

    def __init__(
        self,
        registry: HubRegistry,
        settings: HubSettings,
    ) -> None:
        """Initialize the hub runner.

        Args:
            registry: Hub registry (pre-populated with modules)
            settings: Hub configuration
        """
        self.hub_registry = registry
        self.settings = settings
        self._mcp: FastMCP | None = None
        self._shutdown_event: asyncio.Event | None = None

    @property
    def mcp(self) -> FastMCP:
        """Get the MCP server, building if necessary."""
        if self._mcp is None:
            self._mcp = build_hub(self.hub_registry, self.settings)
        return self._mcp

    def run(self) -> None:
        """Run the hub server synchronously."""
        transport = self.settings.transport
        host = self.settings.host
        port = self.settings.port

        print_info(f"Starting Hub: {self.settings.name}")
        print_info(f"Transport: {transport}")

        if transport == "stdio":
            self.mcp.run()
        elif transport == "sse":
            print_success(f"Hub ready at http://{host}:{port}/sse")
            self.mcp.run(transport="sse", host=host, port=port)
        else:  # http
            print_success(f"Hub ready at http://{host}:{port}")
            self.mcp.run(transport="streamable-http", host=host, port=port)

    async def run_async(self) -> None:
        """Run the hub server asynchronously."""
        transport = self.settings.transport
        host = self.settings.host
        port = self.settings.port

        print_info(f"Starting Hub: {self.settings.name}")

        self._shutdown_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._handle_shutdown)
            except NotImplementedError:
                pass

        try:
            if transport == "stdio":
                await loop.run_in_executor(None, self.mcp.run)
            elif transport == "sse":
                print_success(f"Hub ready at http://{host}:{port}/sse")
                await loop.run_in_executor(
                    None,
                    lambda: self.mcp.run(transport="sse", host=host, port=port),
                )
            else:
                print_success(f"Hub ready at http://{host}:{port}")
                await loop.run_in_executor(
                    None,
                    lambda: self.mcp.run(transport="streamable-http", host=host, port=port),
                )
        finally:
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.remove_signal_handler(sig)
                except (NotImplementedError, ValueError):
                    pass

    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        print_info("Shutting down hub...")
        if self._shutdown_event:
            self._shutdown_event.set()


def _resolve_schema_ref(ref: str, components: dict[str, Any]) -> dict[str, Any]:
    """Resolve a $ref reference to its actual schema.

    Args:
        ref: Reference string like "#/components/schemas/UserCreate"
        components: The components section of the OpenAPI spec

    Returns:
        Resolved schema dict, or empty dict if not found
    """
    if not ref.startswith("#/components/schemas/"):
        return {}

    schema_name = ref.split("/")[-1]
    schemas = components.get("schemas", {})
    return schemas.get(schema_name, {})


def create_hub_registry_from_modules(
    module_registry: ModuleRegistry,
    spec: NormalizedSpec | None = None,
    plan: OMCPPlan | None = None,
) -> HubRegistry:
    """Create a HubRegistry from a ModuleRegistry with full tool schemas.

    Converts the module instances from ModuleRunner into registered modules
    for the hub, including full tool schemas for the meta-tool pattern.

    Args:
        module_registry: Module registry from ModuleRunner
        spec: Normalized OpenAPI spec (for parameter schemas)
        plan: OMCP plan (for tool names and descriptions)

    Returns:
        HubRegistry populated with modules and tool schemas
    """
    hub_registry = HubRegistry()

    # Get components for resolving $ref references
    components = spec.spec.get("components", {}) if spec else {}

    # Build lookup tables from spec and plan
    op_to_spec: dict[str, dict[str, Any]] = {}
    op_to_plan: dict[str, Any] = {}

    if spec:
        # Build operation_id -> operation spec mapping
        for path, path_item in spec.spec.get("paths", {}).items():
            for method in ["get", "post", "put", "patch", "delete", "head", "options"]:
                if method not in path_item:
                    continue
                op = path_item[method]
                op_id = op.get("operationId", "")
                if op_id:
                    op_to_spec[op_id] = {
                        "method": method.upper(),
                        "path": path,
                        "parameters": op.get("parameters", []),
                        "requestBody": op.get("requestBody"),
                        "summary": op.get("summary", ""),
                        "description": op.get("description", ""),
                    }

    if plan:
        # Build operation_id -> plan tool mapping
        for tool in plan.tools:
            op_to_plan[tool.operation_id] = tool

    for instance in module_registry.all_modules:
        tool_schemas: list[ToolSchema] = []

        # Get tool info from the module instance
        # instance.tools contains tool names, we need to map back to operation IDs
        for tool_name in instance.tools:
            # Find the operation_id for this tool
            operation_id = tool_name  # Default: tool_name is operation_id

            # Check if plan has a mapping
            if plan:
                for plan_tool in plan.tools:
                    if plan_tool.tool_name == tool_name:
                        operation_id = plan_tool.operation_id
                        break

            # Get spec info
            spec_info = op_to_spec.get(operation_id, {})
            plan_tool = op_to_plan.get(operation_id)

            # Build parameter list from OpenAPI spec
            parameters: list[dict[str, Any]] = []
            if spec_info.get("parameters"):
                for param in spec_info["parameters"]:
                    parameters.append({
                        "name": param.get("name", ""),
                        "in": param.get("in", "query"),
                        "required": param.get("required", False),
                        "description": param.get("description", ""),
                        "schema": param.get("schema", {}),
                    })

            # Build request body info with resolved $ref
            request_body = None
            if spec_info.get("requestBody"):
                rb = spec_info["requestBody"]
                content = rb.get("content", {})
                json_schema = content.get("application/json", {}).get("schema", {})

                # Resolve $ref if present
                if "$ref" in json_schema:
                    resolved = _resolve_schema_ref(json_schema["$ref"], components)
                    if resolved:
                        json_schema = resolved

                request_body = {
                    "required": rb.get("required", False),
                    "description": rb.get("description", ""),
                    "schema": json_schema,
                }

            # Get description from plan or spec
            description = ""
            if plan_tool:
                description = plan_tool.description
            elif spec_info:
                description = spec_info.get("description") or spec_info.get("summary", "")

            schema = ToolSchema(
                name=tool_name,
                operation_id=operation_id,
                module=instance.name,
                method=spec_info.get("method", ""),
                path=spec_info.get("path", ""),
                description=description,
                parameters=parameters,
                request_body=request_body,
            )
            tool_schemas.append(schema)

        # Get module description from plan if available
        module_description = f"Module: {instance.name}"
        if plan:
            for plan_module in plan.modules:
                if plan_module.name == instance.name:
                    module_description = plan_module.description
                    break

        hub_registry.register(
            name=instance.name,
            description=module_description,
            url=instance.url,
            tool_schemas=tool_schemas,
            metadata={
                "port": instance.port,
                "tool_count": instance.tool_count,
            },
        )

    return hub_registry


def run_hub(
    registry: HubRegistry,
    settings: HubSettings,
) -> None:
    """Run the hub server.

    Args:
        registry: Hub registry with modules
        settings: Hub configuration
    """
    runner = HubRunner(registry, settings)
    runner.run()
