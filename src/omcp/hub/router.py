"""Hub router - route tool calls to appropriate modules."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from omcp.auth.dynamic import get_current_auth_context
from omcp.hub.registry import HubRegistry, RegisteredModule
from omcp.utils.errors import OMCPError


class RoutingMode(str, Enum):
    """How the hub routes requests to modules."""

    TOOL_TO_MODULE = "tool_to_module"  # Route by tool name
    OPERATION_TO_MODULE = "operation_to_module"  # Route by operationId


class HubRoutingError(OMCPError):
    """Error during hub routing."""

    pass


@dataclass
class RouteResult:
    """Result of routing a tool call."""

    module: RegisteredModule
    tool_name: str
    success: bool
    response: Any = None
    error: str | None = None


class HubRouter:
    """Router for directing tool calls to appropriate modules.

    The hub router:
    1. Looks up which module handles a tool
    2. Forwards the request to that module
    3. Returns the response back to the caller
    """

    def __init__(
        self,
        registry: HubRegistry,
        mode: RoutingMode = RoutingMode.TOOL_TO_MODULE,
        enforce_policy: bool = True,
        blocked_tools: list[str] | None = None,
        timeout: float = 60.0,
    ) -> None:
        """Initialize the router.

        Args:
            registry: Hub registry with module information
            mode: Routing mode (tool_to_module or operation_to_module)
            enforce_policy: Whether to enforce blocked tools policy
            blocked_tools: List of tool names that should be blocked
            timeout: Request timeout in seconds
        """
        self.registry = registry
        self.mode = mode
        self.enforce_policy = enforce_policy
        self.blocked_tools = set(blocked_tools or [])
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def is_tool_allowed(self, tool_name: str) -> bool:
        """Check if a tool is allowed by policy.

        Args:
            tool_name: Tool name to check

        Returns:
            True if tool is allowed
        """
        if not self.enforce_policy:
            return True
        return tool_name not in self.blocked_tools

    def resolve_module(self, tool_name: str) -> RegisteredModule | None:
        """Resolve which module handles a tool.

        Args:
            tool_name: Tool name to resolve

        Returns:
            RegisteredModule or None if not found
        """
        return self.registry.get_module_for_tool(tool_name)

    async def route_tool_call(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> RouteResult:
        """Route a tool call to the appropriate module.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments

        Returns:
            RouteResult with response or error

        Raises:
            HubRoutingError: If routing fails
        """
        # Check policy
        if not self.is_tool_allowed(tool_name):
            raise HubRoutingError(
                f"Tool '{tool_name}' is blocked by policy",
                details="This tool has been disabled by the hub administrator",
            )

        # Find module
        module = self.resolve_module(tool_name)
        if module is None:
            raise HubRoutingError(
                f"No module found for tool: {tool_name}",
                details=f"Available tools: {', '.join(self.registry.list_tools()[:10])}...",
            )

        # Forward request to module
        try:
            response = await self._forward_to_module(module, tool_name, arguments or {})
            return RouteResult(
                module=module,
                tool_name=tool_name,
                success=True,
                response=response,
            )
        except Exception as e:
            return RouteResult(
                module=module,
                tool_name=tool_name,
                success=False,
                error=str(e),
            )

    async def _forward_to_module(
        self,
        module: RegisteredModule,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> Any:
        """Forward a tool call to a module.

        Args:
            module: Target module
            tool_name: Tool name
            arguments: Tool arguments

        Returns:
            Response from the module
        """
        # Build MCP tool call request
        # Note: This follows the MCP JSON-RPC format
        request_body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            },
        }

        # Build headers, including auth from current context
        # Uses configured header name and scheme from the auth context
        headers: dict[str, str] = {"Content-Type": "application/json"}
        auth_ctx = get_current_auth_context()
        if auth_ctx and auth_ctx.token:
            headers.update(auth_ctx.get_auth_headers())

        # Send request to module
        response = await self.client.post(
            module.url,
            json=request_body,
            headers=headers,
        )

        if response.status_code != 200:
            raise HubRoutingError(
                f"Module {module.name} returned error: {response.status_code}",
                details=response.text[:500],
            )

        result = response.json()

        # Check for JSON-RPC error
        if "error" in result:
            error = result["error"]
            raise HubRoutingError(
                f"Module {module.name} error: {error.get('message', 'Unknown error')}",
                details=str(error.get("data", "")),
            )

        return result.get("result")

    async def list_available_tools(self) -> list[dict[str, Any]]:
        """List all available tools across all modules.

        Returns:
            List of tool info dicts
        """
        tools = []
        for module in self.registry.list_modules():
            for tool_name in module.tools:
                allowed = self.is_tool_allowed(tool_name)
                tools.append({
                    "name": tool_name,
                    "module": module.name,
                    "module_url": module.url,
                    "allowed": allowed,
                })
        return tools

    def get_routing_info(self) -> dict[str, Any]:
        """Get routing configuration info.

        Returns:
            Dictionary with routing settings
        """
        return {
            "mode": self.mode.value,
            "enforce_policy": self.enforce_policy,
            "blocked_tools_count": len(self.blocked_tools),
            "timeout": self.timeout,
            "module_count": len(self.registry),
            "tool_count": len(self.registry.list_tools()),
        }
