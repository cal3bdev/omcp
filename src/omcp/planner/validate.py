"""Plan validation - deterministic checks on LLM output."""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from typing import Sequence

from omcp.config.models import LLMSettings
from omcp.planner.schema import OMCPPlan, PlannedTool
from omcp.spec.normalizer import NormalizedSpec
from omcp.utils.errors import PlanValidationError


@dataclass
class ValidationError:
    """A single validation error."""

    code: str
    message: str
    tool: PlannedTool | None = None


@dataclass
class ValidationResult:
    """Result of plan validation."""

    valid: bool
    errors: list[ValidationError] = field(default_factory=list)
    warnings: list[ValidationError] = field(default_factory=list)

    def add_error(
        self,
        code: str,
        message: str,
        tool: PlannedTool | None = None,
    ) -> None:
        """Add a validation error."""
        self.errors.append(ValidationError(code=code, message=message, tool=tool))
        self.valid = False

    def add_warning(
        self,
        code: str,
        message: str,
        tool: PlannedTool | None = None,
    ) -> None:
        """Add a validation warning (doesn't fail validation)."""
        self.warnings.append(ValidationError(code=code, message=message, tool=tool))


def validate_plan(
    plan: OMCPPlan,
    spec: NormalizedSpec,
    settings: LLMSettings | None = None,
) -> ValidationResult:
    """Validate an OMCP plan against the spec and settings.

    Runs all validators and returns combined result.

    Args:
        plan: The plan to validate
        spec: The normalized spec the plan was generated from
        settings: Optional LLM settings for constraint checking

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult(valid=True)

    # Run all validators
    validate_operations_exist(plan, spec, result)
    validate_unique_tool_names(plan, result)
    validate_unique_module_names(plan, result)
    validate_module_assignments(plan, result)

    if settings:
        validate_policy_compliance(plan, settings, result)
        validate_size_constraints(plan, settings, result)
        validate_naming_constraints(plan, settings, result)

    return result


def validate_operations_exist(
    plan: OMCPPlan,
    spec: NormalizedSpec,
    result: ValidationResult,
) -> None:
    """Validate that all planned tools reference real operations.

    This is the "no hallucination" check - ensures LLM didn't invent operations.
    """
    # Build set of valid operation signatures
    valid_ops = {
        (op.operation_id, op.method.upper(), op.path) for op in spec.operations
    }

    for tool in plan.tools:
        sig = (tool.operation_id, tool.method.upper(), tool.path)
        if sig not in valid_ops:
            result.add_error(
                code="INVALID_OPERATION",
                message=f"Tool references non-existent operation: {tool.operation_id} ({tool.method} {tool.path})",
                tool=tool,
            )


def validate_unique_tool_names(
    plan: OMCPPlan,
    result: ValidationResult,
) -> None:
    """Validate that all tool names are unique."""
    seen_names: dict[str, PlannedTool] = {}

    for tool in plan.tools:
        if not tool.expose:
            continue

        if tool.tool_name in seen_names:
            result.add_error(
                code="DUPLICATE_TOOL_NAME",
                message=f"Duplicate tool name: {tool.tool_name}",
                tool=tool,
            )
        else:
            seen_names[tool.tool_name] = tool


def validate_unique_module_names(
    plan: OMCPPlan,
    result: ValidationResult,
) -> None:
    """Validate that all module names are unique."""
    seen_names: set[str] = set()

    for module in plan.modules:
        if module.name in seen_names:
            result.add_error(
                code="DUPLICATE_MODULE_NAME",
                message=f"Duplicate module name: {module.name}",
            )
        else:
            seen_names.add(module.name)


def validate_module_assignments(
    plan: OMCPPlan,
    result: ValidationResult,
) -> None:
    """Validate that all tool module assignments reference defined modules."""
    module_names = {m.name for m in plan.modules}

    for tool in plan.tools:
        if tool.expose and tool.module not in module_names:
            result.add_warning(
                code="UNKNOWN_MODULE",
                message=f"Tool {tool.tool_name} assigned to undefined module: {tool.module}",
                tool=tool,
            )


def validate_policy_compliance(
    plan: OMCPPlan,
    settings: LLMSettings,
    result: ValidationResult,
) -> None:
    """Validate that plan respects policy constraints."""
    policy = settings.strategy.policy

    for tool in plan.tools:
        if not tool.expose:
            continue

        # Check blocked methods
        if tool.method.upper() in [m.upper() for m in policy.block_methods]:
            result.add_error(
                code="BLOCKED_METHOD",
                message=f"Tool {tool.tool_name} uses blocked method: {tool.method}",
                tool=tool,
            )

        # Check blocked path patterns
        for pattern in policy.block_path_globs:
            if _path_matches_pattern(tool.path, pattern):
                result.add_error(
                    code="BLOCKED_PATH",
                    message=f"Tool {tool.tool_name} matches blocked path pattern: {pattern}",
                    tool=tool,
                )


def validate_size_constraints(
    plan: OMCPPlan,
    settings: LLMSettings,
    result: ValidationResult,
) -> None:
    """Validate size constraints (max tools, tools per module)."""
    strategy = settings.strategy

    # Check total tools
    exposed_count = len(plan.get_exposed_tools())
    if exposed_count > strategy.max_tools_total:
        result.add_error(
            code="TOO_MANY_TOOLS",
            message=f"Plan has {exposed_count} tools, max allowed is {strategy.max_tools_total}",
        )

    # Check tools per module
    by_module = plan.get_tools_by_module()
    for module_name, tools in by_module.items():
        if len(tools) > strategy.max_tools_per_module:
            result.add_warning(
                code="MODULE_TOO_LARGE",
                message=f"Module {module_name} has {len(tools)} tools, target is {strategy.target_tools_per_module}",
            )


def validate_naming_constraints(
    plan: OMCPPlan,
    settings: LLMSettings,
    result: ValidationResult,
) -> None:
    """Validate naming constraints."""
    naming = settings.strategy.naming

    for tool in plan.tools:
        if not tool.expose:
            continue

        # Check name length
        if len(tool.tool_name) > naming.max_name_length:
            result.add_warning(
                code="NAME_TOO_LONG",
                message=f"Tool name too long: {tool.tool_name} ({len(tool.tool_name)} > {naming.max_name_length})",
                tool=tool,
            )

        # Check for avoided patterns
        for avoid in naming.avoid:
            if avoid.lower() in tool.tool_name.lower():
                result.add_warning(
                    code="NAME_CONTAINS_AVOIDED",
                    message=f"Tool name contains avoided pattern '{avoid}': {tool.tool_name}",
                    tool=tool,
                )

        # Check snake_case format
        if not _is_snake_case(tool.tool_name):
            result.add_warning(
                code="NAME_NOT_SNAKE_CASE",
                message=f"Tool name is not snake_case: {tool.tool_name}",
                tool=tool,
            )


def _path_matches_pattern(path: str, pattern: str) -> bool:
    """Check if path matches a glob pattern."""
    # Normalize
    path = "/" + path.strip("/")
    pattern = "/" + pattern.strip("/")

    # Handle ** patterns
    if "**" in pattern:
        regex = pattern.replace("**", ".*").replace("*", "[^/]*")
        return bool(re.match(f"^{regex}$", path))

    return fnmatch.fnmatch(path, pattern)


def _is_snake_case(name: str) -> bool:
    """Check if name is valid snake_case."""
    return bool(re.match(r"^[a-z][a-z0-9]*(_[a-z0-9]+)*$", name))


def raise_if_invalid(result: ValidationResult) -> None:
    """Raise PlanValidationError if validation failed.

    Args:
        result: Validation result to check

    Raises:
        PlanValidationError: If there are validation errors
    """
    if not result.valid:
        error_msgs = [f"  - [{e.code}] {e.message}" for e in result.errors]
        details = "\n".join(error_msgs)
        raise PlanValidationError(
            f"Plan validation failed with {len(result.errors)} error(s)",
            details=details,
        )
