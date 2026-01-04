"""Hub builder - build the Hub MCP server with meta-tool pattern.

The hub provides discovery and execution tools rather than proxying
individual tools. This keeps the context small while providing full
access to all module tools.
"""

from __future__ import annotations

import json
from typing import Any

from fastmcp import FastMCP

from omcp.auth.dynamic import get_current_auth_context
from omcp.config.models import HubSettings
from omcp.hub.registry import HubRegistry, ToolSchema
from omcp.hub.router import HubRouter, RoutingMode


class HubBuilder:
    """Builder for creating the Hub MCP server.

    The Hub uses a meta-tool pattern to avoid context bloat:
    - Discovery tools: list_modules, list_module_tools, find_tool, get_tool_schema
    - Execution tool: call_tool (routes to appropriate module)

    This keeps the hub's tool count small (~5 tools) while providing
    access to all underlying module tools.
    """

    def __init__(
        self,
        registry: HubRegistry,
        settings: HubSettings,
        router: HubRouter | None = None,
    ) -> None:
        """Initialize the hub builder.

        Args:
            registry: Hub registry with modules and tool schemas
            settings: Hub configuration settings
            router: Optional pre-configured router
        """
        self.registry = registry
        self.settings = settings
        self.router = router or HubRouter(
            registry=registry,
            mode=RoutingMode(settings.routing.mode),
            enforce_policy=settings.routing.enforce_policy,
        )
        self._mcp: FastMCP | None = None

    def build(self) -> FastMCP:
        """Build the Hub FastMCP server.

        Returns:
            Configured FastMCP server with meta-tools
        """
        if self._mcp is not None:
            return self._mcp

        mcp = FastMCP(name=self.settings.name)

        # Register the meta-tools
        self._register_discovery_tools(mcp)
        self._register_execution_tool(mcp)

        # Register module documentation resources (optional)
        if self.settings.discovery.expose_module_docs_resource:
            self._register_module_resources(mcp)

        self._mcp = mcp
        return mcp

    def _register_discovery_tools(self, mcp: FastMCP) -> None:
        """Register discovery tools on the MCP server."""

        @mcp.tool()
        def list_modules() -> list[dict[str, Any]]:
            """List all available modules in the hub.

            Returns a list of modules with their names, descriptions,
            and tool counts. Use this to understand what capabilities
            are available.

            Returns:
                List of module info dicts with name, description, tool_count
            """
            return [m.to_dict() for m in self.registry.list_modules()]

        @mcp.tool()
        def list_module_tools(module_name: str) -> list[dict[str, Any]]:
            """List all tools in a specific module.

            Use this after list_modules() to see what tools a module provides.

            Args:
                module_name: Name of the module to list tools for

            Returns:
                List of tool summaries with name, description
            """
            module = self.registry.get_module(module_name)
            if not module:
                return [{"error": f"Module not found: {module_name}"}]

            tools = []
            for tool_name in module.tools:
                schema = module.tool_schemas.get(tool_name)
                if schema:
                    tools.append(schema.to_summary())
                else:
                    tools.append({"name": tool_name, "module": module_name})
            return tools

        @mcp.tool()
        def find_tool(query: str) -> list[dict[str, Any]]:
            """Search for tools by name or description.

            Use this when you're not sure which module has the tool you need.
            Searches across all modules for matching tools.

            Args:
                query: Search term (case-insensitive, matches tool names and descriptions)

            Returns:
                List of matching tools with name, module, and description
            """
            results = self.registry.search_tools(query)
            return [r.to_summary() for r in results]

        @mcp.tool()
        def get_tool_schema(module_name: str, tool_name: str) -> dict[str, Any]:
            """Get the full schema for a tool including all parameters.

            IMPORTANT: Always call this before using call_tool() to understand
            what arguments the tool expects.

            Args:
                module_name: Name of the module containing the tool
                tool_name: Name of the tool

            Returns:
                Full tool schema with parameters, request_body, and descriptions
            """
            module = self.registry.get_module(module_name)
            if not module:
                return {"error": f"Module not found: {module_name}"}

            schema = module.tool_schemas.get(tool_name)
            if not schema:
                # Try global lookup
                schema = self.registry.get_tool_schema(tool_name)

            if schema:
                return schema.to_dict()
            return {"error": f"Tool not found: {tool_name} in module {module_name}"}

        @mcp.tool()
        def hub_status() -> dict[str, Any]:
            """Get hub status and statistics.

            Returns hub configuration, module count, total tool count,
            and list of module names.
            """
            return {
                "name": self.settings.name,
                "module_count": len(self.registry),
                "tool_count": len(self.registry.list_tools()),
                "modules": self.registry.list_module_names(),
            }

    def _register_execution_tool(self, mcp: FastMCP) -> None:
        """Register the call_tool execution tool."""

        @mcp.tool()
        async def call_tool(
            module_name: str,
            tool_name: str,
            arguments: dict[str, Any] | None = None,
        ) -> str:
            """Execute a tool in a module.

            This is the main way to call any tool in any module.
            Always use get_tool_schema() first to understand the required arguments.

            Args:
                module_name: Name of the module containing the tool
                tool_name: Name of the tool to call
                arguments: Dict of arguments to pass to the tool (check schema first!)

            Returns:
                JSON string with the tool's response or error
            """
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client

            module = self.registry.get_module(module_name)
            if not module:
                return json.dumps({"error": f"Module not found: {module_name}"})

            if tool_name not in module.tools:
                return json.dumps({
                    "error": f"Tool '{tool_name}' not found in module '{module_name}'",
                    "available_tools": module.tools[:10],
                })

            args = arguments or {}

            # Get auth headers from current context to forward to module
            # Uses configured header name and scheme from the auth context
            headers: dict[str, str] = {}
            auth_ctx = get_current_auth_context()
            if auth_ctx and auth_ctx.token:
                headers = auth_ctx.get_auth_headers()

            try:
                # Connect to the module's MCP server
                module_endpoint = f"{module.url}/mcp"
                async with streamablehttp_client(module_endpoint, headers=headers) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()

                        # List available tools for debugging
                        available = await session.list_tools()
                        available_names = [t.name for t in available.tools] if available.tools else []

                        # Check if tool exists on module
                        if tool_name not in available_names:
                            return json.dumps({
                                "error": f"Tool '{tool_name}' not found on module server",
                                "module": module_name,
                                "module_endpoint": module_endpoint,
                                "available_tools_on_module": available_names[:20],
                                "hint": "Tool names may differ between hub registry and module server",
                            }, indent=2)

                        # Call the tool with the provided arguments
                        result = await session.call_tool(tool_name, args)

                        # Extract and return the response
                        if result.content:
                            texts = [c.text for c in result.content if hasattr(c, "text")]
                            if texts:
                                # Try to parse as JSON for cleaner output
                                try:
                                    parsed = json.loads(texts[0])
                                    return json.dumps(parsed, indent=2)
                                except json.JSONDecodeError:
                                    return texts[0] if len(texts) == 1 else json.dumps(texts)

                        return json.dumps({"status": "success", "result": str(result.content)})

            except Exception as e:
                return json.dumps({
                    "error": f"Failed to call tool: {str(e)}",
                    "module": module_name,
                    "tool": tool_name,
                    "module_url": module.url,
                }, indent=2)

    def _register_module_resources(self, mcp: FastMCP) -> None:
        """Register module documentation resources."""

        @mcp.resource("hub://modules")
        def modules_index() -> str:
            """Index of all modules in the hub."""
            lines = ["# OMCP Hub Modules\n"]
            for module in self.registry.list_modules():
                lines.append(f"## {module.name}")
                lines.append(f"{module.description}\n")
                lines.append(f"- URL: {module.url}")
                lines.append(f"- Tools: {len(module.tools)}")
                if module.tools:
                    lines.append(f"- Tool list: {', '.join(module.tools[:10])}")
                    if len(module.tools) > 10:
                        lines.append(f"  ... and {len(module.tools) - 10} more")
                lines.append("")
            return "\n".join(lines)

        # Register per-module resources
        for module in self.registry.list_modules():
            self._register_module_doc_resource(mcp, module.name)

    def _register_module_doc_resource(self, mcp: FastMCP, module_name: str) -> None:
        """Register a documentation resource for a specific module."""
        resource_uri = f"hub://modules/{module_name}"

        @mcp.resource(resource_uri)
        def module_docs() -> str:
            module = self.registry.get_module(module_name)
            if not module:
                return f"# Module Not Found: {module_name}"

            lines = [
                f"# {module.name}",
                "",
                module.description,
                "",
                "## Available Tools",
            ]

            for tool_name in module.tools:
                schema = module.tool_schemas.get(tool_name)
                if schema:
                    lines.append(f"\n### {tool_name}")
                    lines.append(schema.description)
                    if schema.parameters:
                        lines.append("\n**Parameters:**")
                        for param in schema.parameters:
                            required = "(required)" if param.get("required") else "(optional)"
                            lines.append(f"- `{param.get('name')}` {required}: {param.get('description', '')}")
                else:
                    lines.append(f"- `{tool_name}`")

            return "\n".join(lines)


def build_hub(
    registry: HubRegistry,
    settings: HubSettings,
) -> FastMCP:
    """Build a Hub MCP server.

    Args:
        registry: Hub registry with modules and tool schemas
        settings: Hub configuration

    Returns:
        Configured FastMCP server with meta-tools
    """
    builder = HubBuilder(registry, settings)
    return builder.build()
