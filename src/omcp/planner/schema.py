"""OMCP Plan schema - the output of the LLM planner."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class PlannedTool(BaseModel):
    """A planned tool mapping from an OpenAPI operation."""

    # From the OpenAPI spec (must match exactly)
    operation_id: str
    method: str
    path: str

    # LLM-suggested improvements
    tool_name: str  # The tool name exposed to agents
    description: str  # High-signal agent description

    # Exposure control
    expose: bool = True  # Whether to expose this tool

    # Module assignment (for modular mode)
    module: str = "default"

    # Safety notes from the planner
    safety_notes: list[str] = Field(default_factory=list)


class PlannedModule(BaseModel):
    """A planned module (micro-MCP) grouping."""

    name: str
    description: str
    # Optional module-level policy overrides
    policy_overrides: dict[str, Any] = Field(default_factory=dict)


class PlanPolicy(BaseModel):
    """Global policy settings for the plan."""

    block_methods: list[str] = Field(default_factory=lambda: ["DELETE"])
    block_path_patterns: list[str] = Field(default_factory=list)
    require_auth_for_writes: bool = True


class PlanProvenance(BaseModel):
    """Metadata about how the plan was generated."""

    planner_model: str = ""
    planner_provider: str = ""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    spec_hash: str = ""  # Hash of input spec for cache invalidation
    config_hash: str = ""  # Hash of relevant config


class OMCPPlan(BaseModel):
    """The complete OMCP Plan - output of the LLM planner.

    This is a deterministic, validated artifact that bridges
    LLM suggestions and server generation.
    """

    version: str = "2.0"

    # API metadata
    api_name: str
    base_url: str

    # Global policy
    policy: PlanPolicy = Field(default_factory=PlanPolicy)

    # Module definitions
    modules: list[PlannedModule] = Field(default_factory=list)

    # Tool mappings (one per exposed operation)
    tools: list[PlannedTool] = Field(default_factory=list)

    # Generation metadata
    provenance: PlanProvenance = Field(default_factory=PlanProvenance)

    def get_tools_by_module(self) -> dict[str, list[PlannedTool]]:
        """Group tools by their module assignment."""
        by_module: dict[str, list[PlannedTool]] = {}
        for tool in self.tools:
            if tool.expose:
                if tool.module not in by_module:
                    by_module[tool.module] = []
                by_module[tool.module].append(tool)
        return by_module

    def get_exposed_tools(self) -> list[PlannedTool]:
        """Get all tools marked for exposure."""
        return [t for t in self.tools if t.expose]

    def get_excluded_tools(self) -> list[PlannedTool]:
        """Get all tools marked as not exposed."""
        return [t for t in self.tools if not t.expose]

    def get_tool_name_map(self) -> dict[str, str]:
        """Get operationId -> tool_name mapping for exposed tools."""
        return {t.operation_id: t.tool_name for t in self.tools if t.expose}

    def get_description_map(self) -> dict[str, str]:
        """Get operationId -> description mapping for exposed tools."""
        return {t.operation_id: t.description for t in self.tools if t.expose}
