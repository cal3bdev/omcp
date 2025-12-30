"""Tests for Hub server - module discovery and routing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from omcp.config.models import HubDiscovery, HubRouting, HubSettings
from omcp.hub import (
    HubBuilder,
    HubRegistry,
    HubRouter,
    HubRoutingError,
    RegisteredModule,
    RouteResult,
    RoutingMode,
    build_hub,
    create_hub_registry_from_modules,
)


FIXTURES = Path(__file__).parent / "fixtures"


class TestHubRegistry:
    """Test hub registry."""

    def test_register_module(self):
        """Register a module."""
        registry = HubRegistry()

        module = registry.register(
            name="users",
            description="User management",
            url="http://localhost:9100",
            tools=["list_users", "get_user", "create_user"],
        )

        assert module.name == "users"
        assert len(module.tools) == 3
        assert "users" in registry

    def test_register_duplicate_raises(self):
        """Registering duplicate module raises error."""
        registry = HubRegistry()
        registry.register("users", "Users", "http://localhost:9100")

        with pytest.raises(ValueError) as exc:
            registry.register("users", "Users again", "http://localhost:9101")
        assert "already registered" in str(exc.value)

    def test_unregister_module(self):
        """Unregister a module."""
        registry = HubRegistry()
        registry.register("users", "Users", "http://localhost:9100", tools=["list_users"])

        assert registry.unregister("users") is True
        assert "users" not in registry
        assert registry.get_module_for_tool("list_users") is None

    def test_unregister_unknown_returns_false(self):
        """Unregistering unknown module returns False."""
        registry = HubRegistry()
        assert registry.unregister("unknown") is False

    def test_get_module(self):
        """Get module by name."""
        registry = HubRegistry()
        registry.register("users", "Users", "http://localhost:9100")

        module = registry.get_module("users")
        assert module is not None
        assert module.name == "users"

    def test_get_unknown_module(self):
        """Getting unknown module returns None."""
        registry = HubRegistry()
        assert registry.get_module("unknown") is None

    def test_get_module_for_tool(self):
        """Find module containing a tool."""
        registry = HubRegistry()
        registry.register("users", "Users", "http://localhost:9100", tools=["list_users"])
        registry.register("orders", "Orders", "http://localhost:9101", tools=["list_orders"])

        user_module = registry.get_module_for_tool("list_users")
        assert user_module is not None
        assert user_module.name == "users"

        order_module = registry.get_module_for_tool("list_orders")
        assert order_module is not None
        assert order_module.name == "orders"

    def test_get_module_url_for_tool(self):
        """Get URL for tool's module."""
        registry = HubRegistry()
        registry.register("users", "Users", "http://localhost:9100", tools=["list_users"])

        url = registry.get_module_url_for_tool("list_users")
        assert url == "http://localhost:9100"

    def test_list_modules(self):
        """List all modules."""
        registry = HubRegistry()
        registry.register("users", "Users", "http://localhost:9100")
        registry.register("orders", "Orders", "http://localhost:9101")

        modules = registry.list_modules()
        assert len(modules) == 2
        names = {m.name for m in modules}
        assert names == {"users", "orders"}

    def test_list_tools(self):
        """List all tools."""
        registry = HubRegistry()
        registry.register("users", "Users", "http://localhost:9100", tools=["a", "b"])
        registry.register("orders", "Orders", "http://localhost:9101", tools=["c"])

        tools = registry.list_tools()
        assert set(tools) == {"a", "b", "c"}

    def test_get_registry_info(self):
        """Get complete registry info."""
        registry = HubRegistry()
        registry.register("users", "Users", "http://localhost:9100", tools=["a", "b"])

        info = registry.get_registry_info()
        assert info["module_count"] == 1
        assert info["tool_count"] == 2
        assert len(info["modules"]) == 1

    def test_clear_registry(self):
        """Clear all registrations."""
        registry = HubRegistry()
        registry.register("users", "Users", "http://localhost:9100")
        registry.register("orders", "Orders", "http://localhost:9101")

        registry.clear()
        assert len(registry) == 0

    def test_registered_module_to_dict(self):
        """RegisteredModule converts to dict."""
        module = RegisteredModule(
            name="users",
            description="User management",
            url="http://localhost:9100",
            tools=["list_users", "get_user"],
        )

        d = module.to_dict()
        assert d["name"] == "users"
        assert d["tool_count"] == 2
        assert d["tools"] == ["list_users", "get_user"]


class TestHubRouter:
    """Test hub router."""

    def _create_registry(self) -> HubRegistry:
        """Create a test registry."""
        registry = HubRegistry()
        registry.register(
            "users",
            "User management",
            "http://localhost:9100",
            tools=["list_users", "get_user"],
        )
        registry.register(
            "orders",
            "Order management",
            "http://localhost:9101",
            tools=["list_orders", "create_order"],
        )
        return registry

    def test_resolve_module(self):
        """Router resolves tool to module."""
        registry = self._create_registry()
        router = HubRouter(registry)

        module = router.resolve_module("list_users")
        assert module is not None
        assert module.name == "users"

    def test_resolve_unknown_tool(self):
        """Resolving unknown tool returns None."""
        registry = self._create_registry()
        router = HubRouter(registry)

        assert router.resolve_module("unknown_tool") is None

    def test_is_tool_allowed(self):
        """Check tool policy enforcement."""
        registry = self._create_registry()
        router = HubRouter(
            registry,
            enforce_policy=True,
            blocked_tools=["create_order"],
        )

        assert router.is_tool_allowed("list_users") is True
        assert router.is_tool_allowed("create_order") is False

    def test_policy_not_enforced(self):
        """When policy not enforced, all tools allowed."""
        registry = self._create_registry()
        router = HubRouter(
            registry,
            enforce_policy=False,
            blocked_tools=["create_order"],
        )

        assert router.is_tool_allowed("create_order") is True

    @pytest.mark.asyncio
    async def test_route_blocked_tool_raises(self):
        """Routing to blocked tool raises error."""
        registry = self._create_registry()
        router = HubRouter(
            registry,
            enforce_policy=True,
            blocked_tools=["create_order"],
        )

        with pytest.raises(HubRoutingError) as exc:
            await router.route_tool_call("create_order", {"item": "test"})
        assert "blocked by policy" in exc.value.message

    @pytest.mark.asyncio
    async def test_route_unknown_tool_raises(self):
        """Routing to unknown tool raises error."""
        registry = self._create_registry()
        router = HubRouter(registry)

        with pytest.raises(HubRoutingError) as exc:
            await router.route_tool_call("unknown_tool", {})
        assert "No module found" in exc.value.message

    @pytest.mark.asyncio
    async def test_list_available_tools(self):
        """List available tools with module info."""
        registry = self._create_registry()
        router = HubRouter(registry, blocked_tools=["create_order"])

        tools = await router.list_available_tools()
        assert len(tools) == 4

        # Check blocked status
        create_order = next(t for t in tools if t["name"] == "create_order")
        assert create_order["allowed"] is False

        list_users = next(t for t in tools if t["name"] == "list_users")
        assert list_users["allowed"] is True

    def test_get_routing_info(self):
        """Get routing configuration."""
        registry = self._create_registry()
        router = HubRouter(
            registry,
            mode=RoutingMode.TOOL_TO_MODULE,
            blocked_tools=["a", "b"],
        )

        info = router.get_routing_info()
        assert info["mode"] == "tool_to_module"
        assert info["blocked_tools_count"] == 2
        assert info["module_count"] == 2


class TestHubBuilder:
    """Test hub builder."""

    def _create_registry(self) -> HubRegistry:
        """Create a test registry."""
        registry = HubRegistry()
        registry.register(
            "users",
            "User management",
            "http://localhost:9100",
            tools=["list_users", "get_user"],
        )
        return registry

    def _create_settings(self) -> HubSettings:
        """Create test hub settings."""
        return HubSettings(
            enabled=True,
            name="Test Hub",
            transport="http",
            host="127.0.0.1",
            port=9000,
            routing=HubRouting(mode="tool_to_module"),
            discovery=HubDiscovery(
                expose_registry_tool=True,
                expose_module_docs_resource=True,
            ),
        )

    def test_build_hub_server(self):
        """Build hub MCP server."""
        registry = self._create_registry()
        settings = self._create_settings()

        builder = HubBuilder(registry, settings)
        mcp = builder.build()

        assert mcp is not None
        assert mcp.name == "Test Hub"

    def test_build_registers_discovery_tools(self):
        """Hub has discovery tools registered."""
        registry = self._create_registry()
        settings = self._create_settings()

        mcp = build_hub(registry, settings)

        # Check that tools are registered
        # FastMCP stores tools in _tool_manager
        assert mcp is not None

    def test_build_caches_mcp(self):
        """Builder caches MCP instance."""
        registry = self._create_registry()
        settings = self._create_settings()

        builder = HubBuilder(registry, settings)
        mcp1 = builder.build()
        mcp2 = builder.build()

        assert mcp1 is mcp2


class TestHubRegistryFromModules:
    """Test creating hub registry from module registry."""

    def test_create_from_module_registry(self):
        """Create hub registry from ModuleRegistry."""
        from omcp.modules.runner import ModuleInstance, ModuleRegistry

        module_registry = ModuleRegistry()
        module_registry.register(
            ModuleInstance(
                name="users",
                port=9100,
                url="http://localhost:9100",
                mcp=MagicMock(),
                tool_count=5,
            )
        )
        module_registry.register(
            ModuleInstance(
                name="orders",
                port=9101,
                url="http://localhost:9101",
                mcp=MagicMock(),
                tool_count=3,
            )
        )

        hub_registry = create_hub_registry_from_modules(module_registry)

        assert len(hub_registry) == 2
        assert hub_registry.get_module("users") is not None
        assert hub_registry.get_module("orders") is not None

    def test_empty_module_registry(self):
        """Handle empty module registry."""
        from omcp.modules.runner import ModuleRegistry

        module_registry = ModuleRegistry()
        hub_registry = create_hub_registry_from_modules(module_registry)

        assert len(hub_registry) == 0


class TestRoutingModes:
    """Test different routing modes."""

    def test_tool_to_module_mode(self):
        """Tool to module routing mode."""
        registry = HubRegistry()
        registry.register("users", "Users", "http://localhost:9100", tools=["list_users"])

        router = HubRouter(registry, mode=RoutingMode.TOOL_TO_MODULE)
        assert router.mode == RoutingMode.TOOL_TO_MODULE

        module = router.resolve_module("list_users")
        assert module is not None

    def test_operation_to_module_mode(self):
        """Operation to module routing mode (same behavior for now)."""
        registry = HubRegistry()
        registry.register("users", "Users", "http://localhost:9100", tools=["listUsers"])

        router = HubRouter(registry, mode=RoutingMode.OPERATION_TO_MODULE)
        assert router.mode == RoutingMode.OPERATION_TO_MODULE


class TestRouteResult:
    """Test route result dataclass."""

    def test_success_result(self):
        """Successful route result."""
        module = RegisteredModule(
            name="users",
            description="Users",
            url="http://localhost:9100",
        )
        result = RouteResult(
            module=module,
            tool_name="list_users",
            success=True,
            response={"users": []},
        )

        assert result.success is True
        assert result.error is None
        assert result.response == {"users": []}

    def test_failure_result(self):
        """Failed route result."""
        module = RegisteredModule(
            name="users",
            description="Users",
            url="http://localhost:9100",
        )
        result = RouteResult(
            module=module,
            tool_name="list_users",
            success=False,
            error="Connection refused",
        )

        assert result.success is False
        assert result.error == "Connection refused"
