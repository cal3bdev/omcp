"""Hub registry - track and lookup registered modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RegisteredModule:
    """A module registered with the hub."""

    name: str
    description: str
    url: str
    tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "description": self.description,
            "url": self.url,
            "tools": self.tools,
            "tool_count": len(self.tools),
        }


class HubRegistry:
    """Registry for tracking modules and their tools.

    The hub registry maintains a mapping of:
    - Module name → Module info
    - Tool name → Module name (for routing)
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._modules: dict[str, RegisteredModule] = {}
        self._tool_to_module: dict[str, str] = {}

    def register(
        self,
        name: str,
        description: str,
        url: str,
        tools: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RegisteredModule:
        """Register a module with the hub.

        Args:
            name: Module name (must be unique)
            description: Module description
            url: Module URL endpoint
            tools: List of tool names exposed by this module
            metadata: Optional additional metadata

        Returns:
            The registered module

        Raises:
            ValueError: If module name already registered
        """
        if name in self._modules:
            raise ValueError(f"Module already registered: {name}")

        module = RegisteredModule(
            name=name,
            description=description,
            url=url,
            tools=tools or [],
            metadata=metadata or {},
        )

        self._modules[name] = module

        # Build tool→module index
        for tool in module.tools:
            if tool in self._tool_to_module:
                # Tool name collision - log warning but don't fail
                existing = self._tool_to_module[tool]
                # Keep first registration
                continue
            self._tool_to_module[tool] = name

        return module

    def unregister(self, name: str) -> bool:
        """Unregister a module.

        Args:
            name: Module name to unregister

        Returns:
            True if module was found and removed
        """
        if name not in self._modules:
            return False

        module = self._modules.pop(name)

        # Remove tool mappings
        for tool in module.tools:
            if self._tool_to_module.get(tool) == name:
                del self._tool_to_module[tool]

        return True

    def get_module(self, name: str) -> RegisteredModule | None:
        """Get a module by name.

        Args:
            name: Module name

        Returns:
            RegisteredModule or None if not found
        """
        return self._modules.get(name)

    def get_module_for_tool(self, tool_name: str) -> RegisteredModule | None:
        """Get the module containing a tool.

        Args:
            tool_name: Tool name to look up

        Returns:
            RegisteredModule or None if tool not found
        """
        module_name = self._tool_to_module.get(tool_name)
        if module_name:
            return self._modules.get(module_name)
        return None

    def get_module_url_for_tool(self, tool_name: str) -> str | None:
        """Get the URL for the module containing a tool.

        Args:
            tool_name: Tool name to look up

        Returns:
            Module URL or None if tool not found
        """
        module = self.get_module_for_tool(tool_name)
        return module.url if module else None

    def list_modules(self) -> list[RegisteredModule]:
        """Get all registered modules.

        Returns:
            List of all registered modules
        """
        return list(self._modules.values())

    def list_module_names(self) -> list[str]:
        """Get names of all registered modules.

        Returns:
            List of module names
        """
        return list(self._modules.keys())

    def list_tools(self) -> list[str]:
        """Get all registered tool names.

        Returns:
            List of all tool names across all modules
        """
        return list(self._tool_to_module.keys())

    def get_registry_info(self) -> dict[str, Any]:
        """Get complete registry information.

        Returns:
            Dictionary with modules and summary info
        """
        return {
            "module_count": len(self._modules),
            "tool_count": len(self._tool_to_module),
            "modules": [m.to_dict() for m in self._modules.values()],
        }

    def clear(self) -> None:
        """Clear all registrations."""
        self._modules.clear()
        self._tool_to_module.clear()

    def __len__(self) -> int:
        """Return number of registered modules."""
        return len(self._modules)

    def __contains__(self, name: str) -> bool:
        """Check if module is registered."""
        return name in self._modules
