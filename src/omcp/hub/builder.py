"""Hub builder - build the Hub MCP server."""

from __future__ import annotations

from typing import Any

from fastmcp import FastMCP

from omcp.config.models import HubSettings
from omcp.hub.registry import HubRegistry
from omcp.hub.router import HubRouter, RoutingMode


class HubBuilder:
    """Builder for creating the Hub MCP server.

    The Hub exposes:
    - `list_modules` tool - List all available modules
    - `list_tools` tool - List all available tools
    - `get_module_info` tool - Get details about a module
    - `module_docs` resource - Documentation for each module
    """

    def __init__(
        self,
        registry: HubRegistry,
        settings: HubSettings,
        router: HubRouter | None = None,
    ) -> None:
        """Initialize the hub builder.

        Args:
            registry: Hub registry with modules
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
            Configured FastMCP server
        """
        if self._mcp is not None:
            return self._mcp

        mcp = FastMCP(name=self.settings.name)

        # Register discovery tools
        if self.settings.discovery.expose_registry_tool:
            self._register_discovery_tools(mcp)

        # Register module documentation resources
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
            URLs, and tool counts.
            """
            return [m.to_dict() for m in self.registry.list_modules()]

        @mcp.tool()
        def list_tools() -> list[dict[str, Any]]:
            """List all available tools across all modules.

            Returns a list of tools with their names and which module
            they belong to.
            """
            tools = []
            for module in self.registry.list_modules():
                for tool_name in module.tools:
                    tools.append({
                        "name": tool_name,
                        "module": module.name,
                    })
            return tools

        @mcp.tool()
        def get_module_info(module_name: str) -> dict[str, Any] | None:
            """Get detailed information about a specific module.

            Args:
                module_name: Name of the module to look up

            Returns:
                Module information or null if not found
            """
            module = self.registry.get_module(module_name)
            if module:
                return {
                    **module.to_dict(),
                    "metadata": module.metadata,
                }
            return None

        @mcp.tool()
        def find_tool(tool_name: str) -> dict[str, Any] | None:
            """Find which module contains a specific tool.

            Args:
                tool_name: Name of the tool to find

            Returns:
                Module info containing the tool, or null if not found
            """
            module = self.registry.get_module_for_tool(tool_name)
            if module:
                return {
                    "tool": tool_name,
                    "module": module.name,
                    "module_url": module.url,
                    "module_description": module.description,
                }
            return None

        @mcp.tool()
        def hub_status() -> dict[str, Any]:
            """Get hub status and statistics.

            Returns hub configuration, module count, and routing info.
            """
            return {
                "name": self.settings.name,
                "module_count": len(self.registry),
                "tool_count": len(self.registry.list_tools()),
                "routing": self.router.get_routing_info(),
                "modules": self.registry.list_module_names(),
            }

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

        # Register per-module resources dynamically
        # Note: FastMCP resource registration is done at build time,
        # so we create resources for currently registered modules
        for module in self.registry.list_modules():
            self._register_module_doc_resource(mcp, module.name)

    def _register_module_doc_resource(self, mcp: FastMCP, module_name: str) -> None:
        """Register a documentation resource for a specific module."""
        # Create a closure to capture the module name
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
                "## Connection Info",
                f"- URL: {module.url}",
                "",
                "## Available Tools",
            ]

            if module.tools:
                for tool in module.tools:
                    lines.append(f"- `{tool}`")
            else:
                lines.append("No tools registered.")

            if module.metadata:
                lines.append("")
                lines.append("## Metadata")
                for key, value in module.metadata.items():
                    lines.append(f"- {key}: {value}")

            return "\n".join(lines)


def build_hub(
    registry: HubRegistry,
    settings: HubSettings,
) -> FastMCP:
    """Build a Hub MCP server.

    Args:
        registry: Hub registry with modules
        settings: Hub configuration

    Returns:
        Configured FastMCP server
    """
    builder = HubBuilder(registry, settings)
    return builder.build()
