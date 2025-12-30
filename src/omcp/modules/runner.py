"""Module runner - run multiple micro-MCP servers."""

from __future__ import annotations

import asyncio
import signal
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from fastmcp import FastMCP

from omcp.auth import AuthProvider, create_auth_provider
from omcp.config.models import OMCPConfig
from omcp.modules.builder import ModuleBuilder, build_module_server
from omcp.modules.splitter import ModuleDefinition, SplitResult, split_operations
from omcp.planner.schema import OMCPPlan
from omcp.spec.normalizer import NormalizedSpec
from omcp.utils.console import print_error, print_info, print_success, print_warning


@dataclass
class ModuleInstance:
    """A running module server instance."""

    name: str
    port: int
    url: str
    mcp: FastMCP | None  # None when running in subprocess mode
    tool_count: int
    tools: list[str] = field(default_factory=list)  # Tool names for hub registry


@dataclass
class ModuleRegistry:
    """Registry of running module instances."""

    modules: dict[str, ModuleInstance] = field(default_factory=dict)

    def register(self, instance: ModuleInstance) -> None:
        """Register a module instance."""
        self.modules[instance.name] = instance

    def get(self, name: str) -> ModuleInstance | None:
        """Get module by name."""
        return self.modules.get(name)

    def get_by_tool(self, tool_name: str) -> ModuleInstance | None:
        """Find module containing a tool (requires iteration)."""
        # This would need tool->module mapping for efficiency
        # For now, just return None (hub will need explicit mapping)
        return None

    @property
    def all_modules(self) -> list[ModuleInstance]:
        """Get all registered modules."""
        return list(self.modules.values())

    def get_registry_info(self) -> list[dict[str, Any]]:
        """Get registry info for all modules."""
        return [
            {
                "name": m.name,
                "url": m.url,
                "port": m.port,
                "tool_count": m.tool_count,
            }
            for m in self.modules.values()
        ]


class ModuleRunner:
    """Runner for multiple micro-MCP module servers."""

    def __init__(
        self,
        config: OMCPConfig,
        spec: NormalizedSpec,
        plan: OMCPPlan | None = None,
    ) -> None:
        """Initialize the module runner.

        Args:
            config: OMCP configuration
            spec: Normalized OpenAPI spec
            plan: Optional OMCP plan for LLM-based splitting
        """
        self.config = config
        self.spec = spec
        self.plan = plan
        self._auth: AuthProvider | None = None
        self._split_result: SplitResult | None = None
        self._builders: dict[str, ModuleBuilder] = {}
        self._registry = ModuleRegistry()
        self._shutdown_event: asyncio.Event | None = None
        self._executor: ThreadPoolExecutor | None = None

    @property
    def auth(self) -> AuthProvider:
        """Get shared auth provider."""
        if self._auth is None:
            self._auth = create_auth_provider(
                self.config.auth,
                provider_name=self.config.name,
            )
        return self._auth

    @property
    def split_result(self) -> SplitResult:
        """Get split result, computing if necessary."""
        if self._split_result is None:
            self._split_result = split_operations(
                self.spec,
                self.config.modules,
                self.plan,
            )
        return self._split_result

    @property
    def registry(self) -> ModuleRegistry:
        """Get the module registry."""
        return self._registry

    def _get_module_port(self, index: int) -> int:
        """Get port number for a module.

        Args:
            index: Module index (0-based)

        Returns:
            Port number
        """
        return self.config.modules.runtime.base_port + index

    def _get_module_url(self, port: int) -> str:
        """Get URL for a module.

        Args:
            port: Module port

        Returns:
            Module URL
        """
        host = self.config.modules.runtime.host
        transport = self.config.modules.runtime.transport

        if transport == "sse":
            return f"http://{host}:{port}/sse"
        else:
            return f"http://{host}:{port}"

    def _build_module(self, module: ModuleDefinition) -> ModuleBuilder:
        """Build a module server.

        Args:
            module: Module definition

        Returns:
            ModuleBuilder instance
        """
        if module.name not in self._builders:
            self._builders[module.name] = ModuleBuilder(
                module=module,
                spec=self.spec,
                config=self.config,
                auth=self.auth,
            )
        return self._builders[module.name]

    def build_all(self) -> None:
        """Build all module servers without starting them.
        
        This pre-builds all ModuleBuilder instances for later use.
        """
        for module in self.split_result.modules:
            self._build_module(module)

    def _run_module_sync(
        self,
        mcp: FastMCP,
        host: str,
        port: int,
        transport: str,
    ) -> None:
        """Run a single module server synchronously.

        Args:
            mcp: FastMCP server instance
            host: Host to bind to
            port: Port to bind to
            transport: Transport type (sse or streamable-http)
        """
        mcp.run(transport=transport, host=host, port=port)

    async def run_async(self) -> None:
        """Run all module servers asynchronously."""
        modules = self.split_result.modules

        if not modules:
            print_warning("No modules to run")
            return

        print_info(f"Starting {len(modules)} module servers")

        # Set up shutdown handling
        self._shutdown_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, self._handle_shutdown)
            except NotImplementedError:
                # Windows doesn't support add_signal_handler
                pass

        # Create thread pool for running servers
        self._executor = ThreadPoolExecutor(max_workers=len(modules))

        try:
            # Build and start all modules
            tasks = []
            transport = self.config.modules.runtime.transport
            host = self.config.modules.runtime.host

            # Map transport names
            if transport == "http":
                transport = "streamable-http"

            for index, module in enumerate(modules):
                port = self._get_module_port(index)
                url = self._get_module_url(port)

                # Build the module server
                builder = self._build_module(module)
                mcp = builder.build()

                # Register the instance
                instance = ModuleInstance(
                    name=module.name,
                    port=port,
                    url=url,
                    mcp=mcp,
                    tool_count=len(module.operations),
                    tools=builder.get_tool_names(),
                )
                self._registry.register(instance)

                print_success(f"  {module.name}: {url} ({len(module.operations)} tools)")

                # Create task to run this module
                task = loop.run_in_executor(
                    self._executor,
                    self._run_module_sync,
                    mcp,
                    host,
                    port,
                    transport,
                )
                tasks.append(task)

            print_info("All modules started. Press Ctrl+C to stop.")

            # Wait for shutdown or all tasks to complete
            done, pending = await asyncio.wait(
                [asyncio.create_task(self._shutdown_event.wait())] +
                [asyncio.ensure_future(t) for t in tasks],
                return_when=asyncio.FIRST_COMPLETED,
            )

        finally:
            # Cleanup
            if self._executor:
                self._executor.shutdown(wait=False)

            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.remove_signal_handler(sig)
                except (NotImplementedError, ValueError):
                    pass

    def _handle_shutdown(self) -> None:
        """Handle shutdown signal."""
        print_info("Shutting down modules...")
        if self._shutdown_event:
            self._shutdown_event.set()

    def run(self) -> None:
        """Run all module servers synchronously."""
        asyncio.run(self.run_async())

    def get_module_info(self) -> list[dict[str, Any]]:
        """Get info about all modules that will be created.

        Returns:
            List of module info dicts
        """
        modules = self.split_result.modules
        info = []

        for index, module in enumerate(modules):
            port = self._get_module_port(index)
            url = self._get_module_url(port)

            builder = self._build_module(module)
            tools = builder.get_tool_list()

            info.append({
                "name": module.name,
                "description": module.description,
                "port": port,
                "url": url,
                "tool_count": len(tools),
                "tools": tools,
            })

        return info


def run_modules(
    config: OMCPConfig,
    spec: NormalizedSpec,
    plan: OMCPPlan | None = None,
) -> None:
    """Run all module servers from configuration.

    Args:
        config: OMCP configuration
        spec: Normalized OpenAPI spec
        plan: Optional OMCP plan
    """
    runner = ModuleRunner(config, spec, plan)
    runner.run()
