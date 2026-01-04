"""MCP server runner with transport support."""

from __future__ import annotations

import asyncio
import signal
from enum import Enum

from fastmcp import FastMCP

from omcp.config.models import OMCPConfig
from omcp.server.builder import ServerBuilder
from omcp.utils.errors import OMCPError


class Transport(str, Enum):
    """Server transport type."""

    STDIO = "stdio"
    SSE = "sse"
    HTTP = "http"


class ServerRunner:
    """Runner for MCP servers with different transports."""

    def __init__(
        self,
        config: OMCPConfig,
        mcp: FastMCP | None = None,
    ) -> None:
        """Initialize the server runner.

        Args:
            config: OMCP configuration
            mcp: Optional pre-built FastMCP server
        """
        self.config = config
        self._mcp = mcp
        self._builder: ServerBuilder | None = None
        self._shutdown_event: asyncio.Event | None = None

    @property
    def mcp(self) -> FastMCP:
        """Get the MCP server, building if necessary."""
        if self._mcp is None:
            self._builder = ServerBuilder(self.config)
            self._mcp = self._builder.build()
        return self._mcp

    @property
    def builder(self) -> ServerBuilder | None:
        """Get the server builder if available."""
        return self._builder

    def _get_transport(self) -> Transport:
        """Get the transport type from config."""
        transport_str = self.config.server.transport.lower()
        try:
            return Transport(transport_str)
        except ValueError:
            raise OMCPError(
                f"Unknown transport: {transport_str}",
                details=f"Supported transports: {', '.join(t.value for t in Transport)}",
            )

    def run(self) -> None:
        """Run the MCP server synchronously."""
        transport = self._get_transport()

        if transport == Transport.STDIO:
            self._run_stdio()
        elif transport == Transport.SSE:
            self._run_sse()
        elif transport == Transport.HTTP:
            self._run_http()

    def _run_stdio(self) -> None:
        """Run server with stdio transport."""
        # FastMCP's run method handles stdio, suppress its banner
        self.mcp.run(show_banner=False)

    def _run_sse(self) -> None:
        """Run server with SSE transport."""
        host = self.config.server.host
        port = self.config.server.port
        # FastMCP handles auth via mcp.auth (set in ServerBuilder.build())
        self.mcp.run(transport="sse", host=host, port=port, show_banner=False)

    def _run_http(self) -> None:
        """Run server with HTTP transport."""
        host = self.config.server.host
        port = self.config.server.port
        # FastMCP handles auth via mcp.auth (set in ServerBuilder.build())
        self.mcp.run(transport="streamable-http", host=host, port=port, show_banner=False)

    async def run_async(self) -> None:
        """Run the MCP server asynchronously."""
        transport = self._get_transport()
        self._shutdown_event = asyncio.Event()

        # Set up signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, self._handle_shutdown)

        try:
            if transport == Transport.STDIO:
                await self._run_stdio_async()
            elif transport == Transport.SSE:
                await self._run_sse_async()
            elif transport == Transport.HTTP:
                await self._run_http_async()
        finally:
            # Clean up signal handlers
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.remove_signal_handler(sig)

    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        if self._shutdown_event:
            self._shutdown_event.set()

    async def _run_stdio_async(self) -> None:
        """Run server with stdio transport asynchronously."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, lambda: self.mcp.run(show_banner=False))

    async def _run_sse_async(self) -> None:
        """Run server with SSE transport asynchronously."""
        host = self.config.server.host
        port = self.config.server.port
        mcp = self.mcp
        # FastMCP handles auth via mcp.auth (set in ServerBuilder.build())
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: mcp.run(transport="sse", host=host, port=port, show_banner=False),
        )

    async def _run_http_async(self) -> None:
        """Run server with HTTP transport asynchronously."""
        host = self.config.server.host
        port = self.config.server.port
        mcp = self.mcp
        # FastMCP handles auth via mcp.auth (set in ServerBuilder.build())
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: mcp.run(transport="streamable-http", host=host, port=port, show_banner=False),
        )


def run_server(config: OMCPConfig) -> None:
    """Build and run an MCP server from configuration.

    Args:
        config: OMCP configuration
    """
    runner = ServerRunner(config)
    runner.run()
