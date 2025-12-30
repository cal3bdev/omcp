"""MCP server runner with transport support."""

from __future__ import annotations

import asyncio
import signal
from enum import Enum
from typing import Any

from fastmcp import FastMCP

from omcp.config.models import OMCPConfig, ServerSettings
from omcp.server.builder import ServerBuilder, build_server
from omcp.utils.console import print_error, print_info, print_success
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

        print_info(f"Starting {self.config.name}")
        print_info(f"Transport: {transport.value}")

        if transport == Transport.STDIO:
            self._run_stdio()
        elif transport == Transport.SSE:
            self._run_sse()
        elif transport == Transport.HTTP:
            self._run_http()

    def _run_stdio(self) -> None:
        """Run server with stdio transport."""
        print_info("Running with stdio transport (for Claude Desktop)")
        print_info("Server is ready. Waiting for MCP client connection...")

        # FastMCP's run method handles stdio
        self.mcp.run()

    def _run_sse(self) -> None:
        """Run server with SSE transport."""
        host = self.config.server.host
        port = self.config.server.port

        print_info(f"Running with SSE transport on {host}:{port}")
        print_success(f"Server ready at http://{host}:{port}/sse")

        self.mcp.run(transport="sse", host=host, port=port)

    def _run_http(self) -> None:
        """Run server with HTTP transport."""
        host = self.config.server.host
        port = self.config.server.port

        print_info(f"Running with HTTP transport on {host}:{port}")
        print_success(f"Server ready at http://{host}:{port}")

        # FastMCP uses streamable-http transport
        self.mcp.run(transport="streamable-http", host=host, port=port)

    async def run_async(self) -> None:
        """Run the MCP server asynchronously."""
        transport = self._get_transport()

        print_info(f"Starting {self.config.name}")
        print_info(f"Transport: {transport.value}")

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
        print_info("Shutting down...")
        if self._shutdown_event:
            self._shutdown_event.set()

    async def _run_stdio_async(self) -> None:
        """Run server with stdio transport asynchronously."""
        print_info("Running with stdio transport")
        # For stdio, we just run the sync version in executor
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.mcp.run)

    async def _run_sse_async(self) -> None:
        """Run server with SSE transport asynchronously."""
        host = self.config.server.host
        port = self.config.server.port

        print_info(f"Running with SSE transport on {host}:{port}")
        print_success(f"Server ready at http://{host}:{port}/sse")

        # Run in executor since FastMCP.run is blocking
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self.mcp.run(transport="sse", host=host, port=port),
        )

    async def _run_http_async(self) -> None:
        """Run server with HTTP transport asynchronously."""
        host = self.config.server.host
        port = self.config.server.port

        print_info(f"Running with HTTP transport on {host}:{port}")
        print_success(f"Server ready at http://{host}:{port}")

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: self.mcp.run(transport="streamable-http", host=host, port=port),
        )


def run_server(config: OMCPConfig) -> None:
    """Build and run an MCP server from configuration.

    Args:
        config: OMCP configuration
    """
    runner = ServerRunner(config)
    runner.run()
