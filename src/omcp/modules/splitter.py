"""Module splitter - split operations into modules based on strategy."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from omcp.config.models import ModulesSettings
from omcp.planner.schema import OMCPPlan
from omcp.spec.normalizer import NormalizedSpec, OperationInfo


@dataclass
class ModuleDefinition:
    """A module with its assigned operations."""

    name: str
    description: str
    operations: list[OperationInfo] = field(default_factory=list)

    # Tool customizations from plan
    tool_names: dict[str, str] = field(default_factory=dict)  # op_id -> name
    tool_descriptions: dict[str, str] = field(default_factory=dict)  # op_id -> desc


@dataclass
class SplitResult:
    """Result of splitting operations into modules."""

    modules: list[ModuleDefinition]
    unassigned: list[OperationInfo] = field(default_factory=list)

    def get_module(self, name: str) -> ModuleDefinition | None:
        """Get module by name."""
        return next((m for m in self.modules if m.name == name), None)

    @property
    def total_operations(self) -> int:
        """Total operations across all modules."""
        return sum(len(m.operations) for m in self.modules)


def split_by_plan(
    spec: NormalizedSpec,
    plan: OMCPPlan,
    settings: ModulesSettings,
) -> SplitResult:
    """Split operations into modules based on plan assignments.

    Args:
        spec: Normalized OpenAPI spec
        plan: OMCP plan with module assignments
        settings: Module settings (allow/deny lists)

    Returns:
        SplitResult with modules and their operations
    """
    # Build operation lookup
    op_lookup = {op.operation_id: op for op in spec.operations}

    # Create modules from plan
    modules: dict[str, ModuleDefinition] = {}
    for plan_module in plan.modules:
        if _module_allowed(plan_module.name, settings):
            modules[plan_module.name] = ModuleDefinition(
                name=plan_module.name,
                description=plan_module.description,
            )

    # Assign operations based on plan tools
    unassigned: list[OperationInfo] = []

    for tool in plan.tools:
        if not tool.expose:
            continue

        op = op_lookup.get(tool.operation_id)
        if op is None:
            continue

        module_name = tool.module
        if module_name in modules:
            module = modules[module_name]
            module.operations.append(op)
            module.tool_names[tool.operation_id] = tool.tool_name
            module.tool_descriptions[tool.operation_id] = tool.description
        else:
            unassigned.append(op)

    return SplitResult(
        modules=list(modules.values()),
        unassigned=unassigned,
    )


def split_by_tags(
    spec: NormalizedSpec,
    settings: ModulesSettings,
) -> SplitResult:
    """Split operations into modules based on OpenAPI tags.

    Each unique tag becomes a module. Operations with multiple tags
    are assigned to the first tag. Operations without tags go to 'default'.

    Args:
        spec: Normalized OpenAPI spec
        settings: Module settings (allow/deny lists)

    Returns:
        SplitResult with modules and their operations
    """
    modules: dict[str, ModuleDefinition] = {}
    unassigned: list[OperationInfo] = []

    for op in spec.operations:
        # Get first tag or 'default'
        tag = op.tags[0] if op.tags else "default"
        module_name = _sanitize_module_name(tag)

        if not _module_allowed(module_name, settings):
            continue

        if module_name not in modules:
            modules[module_name] = ModuleDefinition(
                name=module_name,
                description=f"Operations tagged with '{tag}'",
            )

        modules[module_name].operations.append(op)

    return SplitResult(
        modules=list(modules.values()),
        unassigned=unassigned,
    )


def split_by_path(
    spec: NormalizedSpec,
    settings: ModulesSettings,
) -> SplitResult:
    """Split operations into modules based on first path segment.

    Operations are grouped by the first segment of their path.
    e.g., /users/123 -> 'users' module, /orders/456 -> 'orders' module

    Args:
        spec: Normalized OpenAPI spec
        settings: Module settings (allow/deny lists)

    Returns:
        SplitResult with modules and their operations
    """
    modules: dict[str, ModuleDefinition] = {}
    unassigned: list[OperationInfo] = []

    for op in spec.operations:
        # Extract first path segment
        segments = [s for s in op.path.split("/") if s and not s.startswith("{")]
        module_name = segments[0] if segments else "root"
        module_name = _sanitize_module_name(module_name)

        if not _module_allowed(module_name, settings):
            continue

        if module_name not in modules:
            modules[module_name] = ModuleDefinition(
                name=module_name,
                description=f"Operations under /{module_name}",
            )

        modules[module_name].operations.append(op)

    return SplitResult(
        modules=list(modules.values()),
        unassigned=unassigned,
    )


def split_by_hybrid(
    spec: NormalizedSpec,
    settings: ModulesSettings,
) -> SplitResult:
    """Split operations using tags with path fallback.

    Uses tags when available, falls back to path-based grouping
    for operations without tags.

    Args:
        spec: Normalized OpenAPI spec
        settings: Module settings (allow/deny lists)

    Returns:
        SplitResult with modules and their operations
    """
    modules: dict[str, ModuleDefinition] = {}
    unassigned: list[OperationInfo] = []

    for op in spec.operations:
        # Prefer tag, fallback to path
        if op.tags:
            tag = op.tags[0]
            module_name = _sanitize_module_name(tag)
            description = f"Operations tagged with '{tag}'"
        else:
            segments = [s for s in op.path.split("/") if s and not s.startswith("{")]
            module_name = segments[0] if segments else "root"
            module_name = _sanitize_module_name(module_name)
            description = f"Operations under /{module_name}"

        if not _module_allowed(module_name, settings):
            continue

        if module_name not in modules:
            modules[module_name] = ModuleDefinition(
                name=module_name,
                description=description,
            )

        modules[module_name].operations.append(op)

    return SplitResult(
        modules=list(modules.values()),
        unassigned=unassigned,
    )


def split_operations(
    spec: NormalizedSpec,
    settings: ModulesSettings,
    plan: OMCPPlan | None = None,
) -> SplitResult:
    """Split operations into modules based on configured strategy.

    Args:
        spec: Normalized OpenAPI spec
        settings: Module settings with strategy
        plan: Optional OMCP plan (required for 'llm' strategy)

    Returns:
        SplitResult with modules and their operations

    Raises:
        ValueError: If strategy is 'llm' but no plan provided
    """
    strategy = settings.split_strategy

    if strategy == "llm":
        if plan is None:
            raise ValueError("Plan required for 'llm' split strategy")
        return split_by_plan(spec, plan, settings)
    elif strategy == "tags":
        return split_by_tags(spec, settings)
    elif strategy == "path":
        return split_by_path(spec, settings)
    elif strategy == "hybrid":
        return split_by_hybrid(spec, settings)
    else:
        raise ValueError(f"Unknown split strategy: {strategy}")


def _module_allowed(name: str, settings: ModulesSettings) -> bool:
    """Check if module is allowed by allow/deny lists.

    Args:
        name: Module name to check
        settings: Module settings with allow/deny lists

    Returns:
        True if module is allowed
    """
    import fnmatch

    # Check deny list first
    for pattern in settings.deny:
        if fnmatch.fnmatch(name, pattern):
            return False

    # Check allow list
    for pattern in settings.allow:
        if fnmatch.fnmatch(name, pattern):
            return True

    return False


def _sanitize_module_name(name: str) -> str:
    """Sanitize a string for use as module name.

    Converts to lowercase, replaces spaces/special chars with underscores.

    Args:
        name: Raw name string

    Returns:
        Sanitized module name
    """
    import re

    # Lowercase and replace non-alphanumeric with underscore
    name = name.lower()
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = name.strip("_")
    return name or "default"
