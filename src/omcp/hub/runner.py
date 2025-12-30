"""Hub runner - run the hub server."""

from __future__ import annotations

import asyncio
import signal
from typing import Any

from fastmcp import FastMCP

from omcp.config.models import HubSettings
from omcp.hub.builder import HubBuilder, build_hub
from omcp.hub.registry import HubRegistry
from omcp.hub.router import HubRouter
from omcp.modules.runner import ModuleRegistry
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


def create_hub_registry_from_modules(
    module_registry: ModuleRegistry,
) -> HubRegistry:
    """Create a HubRegistry from a ModuleRegistry.

    Converts the module instances from ModuleRunner into
    registered modules for the hub.

    Args:
        module_registry: Module registry from ModuleRunner

    Returns:
        HubRegistry populated with modules
    """
    hub_registry = HubRegistry()

    for instance in module_registry.all_modules:
        # Get tool names from the MCP server if available
        tools: list[str] = []
        if instance.mcp is not None:
            # Try to extract tool names from the MCP server
            try:
                # FastMCP stores tools internally
                if hasattr(instance.mcp, "_tool_manager"):
                    tool_manager = instance.mcp._tool_manager
                    if hasattr(tool_manager, "tools"):
                        tools = list(tool_manager.tools.keys())
            except Exception:
                pass

        hub_registry.register(
            name=instance.name,
            description=f"Module: {instance.name}",
            url=instance.url,
            tools=tools,
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
