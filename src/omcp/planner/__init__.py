"""LLM-based planning pipeline for tool optimization."""

from omcp.planner.diff import PlanDiff, compute_diff, diff_summary, print_diff
from omcp.planner.generate import generate_default_plan, generate_plan
from omcp.planner.llm import (
    AnthropicAdapter,
    GeminiAdapter,
    LLMAdapter,
    OpenAIAdapter,
    create_llm_adapter,
)
from omcp.planner.schema import (
    OMCPPlan,
    PlanPolicy,
    PlanProvenance,
    PlannedModule,
    PlannedTool,
)
from omcp.planner.validate import (
    ValidationError,
    ValidationResult,
    raise_if_invalid,
    validate_plan,
)

__all__ = [
    # Schema
    "OMCPPlan",
    "PlannedTool",
    "PlannedModule",
    "PlanPolicy",
    "PlanProvenance",
    # Generation
    "generate_plan",
    "generate_default_plan",
    # LLM Adapters
    "LLMAdapter",
    "GeminiAdapter",
    "OpenAIAdapter",
    "AnthropicAdapter",
    "create_llm_adapter",
    # Validation
    "validate_plan",
    "raise_if_invalid",
    "ValidationResult",
    "ValidationError",
    # Diff
    "compute_diff",
    "print_diff",
    "diff_summary",
    "PlanDiff",
]
