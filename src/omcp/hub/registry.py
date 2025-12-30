"""Hub registry - track and lookup registered modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolSchema:
    """Schema for a tool including parameters."""

    name: str
    operation_id: str
    module: str
    method: str
    path: str
    description: str
    parameters: list[dict[str, Any]] = field(default_factory=list)
    request_body: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to LLM-friendly dictionary format.

        Returns a clean schema without JSON Schema $ref references,
        suitable for LLM function calling.
        """
        result: dict[str, Any] = {
            "name": self.name,
            "module": self.module,
            "method": self.method,
            "path": self.path,
            "description": self.description,
        }

        # Convert parameters to simple format
        if self.parameters:
            params = []
            for p in self.parameters:
                param_info: dict[str, Any] = {
                    "name": p.get("name", ""),
                    "required": p.get("required", False),
                    "location": p.get("in", "query"),  # query, path, header
                }
                if p.get("description"):
                    param_info["description"] = p["description"]

                # Extract type from schema
                schema = p.get("schema", {})
                if schema:
                    param_info["type"] = schema.get("type", "string")
                    if "enum" in schema:
                        param_info["allowed_values"] = schema["enum"]
                    if "default" in schema:
                        param_info["default"] = schema["default"]

                params.append(param_info)
            result["parameters"] = params

        # Convert request body to simple format
        if self.request_body:
            body_info: dict[str, Any] = {
                "required": self.request_body.get("required", False),
            }
            if self.request_body.get("description"):
                body_info["description"] = self.request_body["description"]

            # Extract properties from schema (avoid $ref)
            schema = self.request_body.get("schema", {})
            if schema:
                # Handle direct properties
                if "properties" in schema:
                    fields = []
                    required_fields = set(schema.get("required", []))
                    for prop_name, prop_schema in schema["properties"].items():
                        field_info: dict[str, Any] = {
                            "name": prop_name,
                            "required": prop_name in required_fields,
                            "type": prop_schema.get("type", "string"),
                        }
                        if prop_schema.get("description"):
                            field_info["description"] = prop_schema["description"]
                        if "enum" in prop_schema:
                            field_info["allowed_values"] = prop_schema["enum"]
                        fields.append(field_info)
                    body_info["fields"] = fields
                elif "$ref" in schema:
                    # If it's just a reference, note what it references
                    ref = schema["$ref"]
                    body_info["schema_ref"] = ref.split("/")[-1]  # e.g., "UserCreate"
                    body_info["note"] = "Pass a JSON object matching this schema"

            result["request_body"] = body_info

        return result

    def to_summary(self) -> dict[str, Any]:
        """Convert to brief summary."""
        return {
            "name": self.name,
            "module": self.module,
            "description": self.description[:100] + "..." if len(self.description) > 100 else self.description,
        }


@dataclass
class RegisteredModule:
    """A module registered with the hub."""

    name: str
    description: str
    url: str
    tools: list[str] = field(default_factory=list)
    tool_schemas: dict[str, ToolSchema] = field(default_factory=dict)
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
    - Tool name → Tool schema (for get_tool_schema)
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._modules: dict[str, RegisteredModule] = {}
        self._tool_to_module: dict[str, str] = {}
        self._tool_schemas: dict[str, ToolSchema] = {}

    def register(
        self,
        name: str,
        description: str,
        url: str,
        tools: list[str] | None = None,
        tool_schemas: list[ToolSchema] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> RegisteredModule:
        """Register a module with the hub.

        Args:
            name: Module name (must be unique)
            description: Module description
            url: Module URL endpoint
            tools: List of tool names exposed by this module
            tool_schemas: List of ToolSchema objects with full schema info
            metadata: Optional additional metadata

        Returns:
            The registered module

        Raises:
            ValueError: If module name already registered
        """
        if name in self._modules:
            raise ValueError(f"Module already registered: {name}")

        # Build tool_schemas dict for the module
        schemas_dict: dict[str, ToolSchema] = {}
        if tool_schemas:
            for schema in tool_schemas:
                schemas_dict[schema.name] = schema

        # If tools list not provided, derive from schemas
        tool_names = tools or [s.name for s in (tool_schemas or [])]

        module = RegisteredModule(
            name=name,
            description=description,
            url=url,
            tools=tool_names,
            tool_schemas=schemas_dict,
            metadata=metadata or {},
        )

        self._modules[name] = module

        # Build tool→module index and tool→schema index
        for tool in module.tools:
            if tool in self._tool_to_module:
                # Tool name collision - keep first registration
                continue
            self._tool_to_module[tool] = name

        for schema in (tool_schemas or []):
            if schema.name not in self._tool_schemas:
                self._tool_schemas[schema.name] = schema

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

        # Remove tool mappings and schemas
        for tool in module.tools:
            if self._tool_to_module.get(tool) == name:
                del self._tool_to_module[tool]
            if tool in self._tool_schemas:
                del self._tool_schemas[tool]

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

    def get_tool_schema(self, tool_name: str) -> ToolSchema | None:
        """Get the full schema for a tool.

        Args:
            tool_name: Tool name to look up

        Returns:
            ToolSchema or None if not found
        """
        return self._tool_schemas.get(tool_name)

    def search_tools(self, query: str) -> list[ToolSchema]:
        """Search for tools by name or description.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching ToolSchema objects
        """
        query_lower = query.lower().replace(" ", "_")
        results = []
        for schema in self._tool_schemas.values():
            if (query_lower in schema.name.lower() or
                query_lower in schema.description.lower()):
                results.append(schema)
        return results

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
        self._tool_schemas.clear()

    def __len__(self) -> int:
        """Return number of registered modules."""
        return len(self._modules)

    def __contains__(self, name: str) -> bool:
        """Check if module is registered."""
        return name in self._modules
