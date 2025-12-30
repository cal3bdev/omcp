"""Plan generation using LLM."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Sequence

from omcp.config.models import LLMSettings
from omcp.planner.llm import LLMAdapter, create_llm_adapter
from omcp.planner.prompts import SYSTEM_PROMPT, build_plan_prompt
from omcp.planner.schema import (
    OMCPPlan,
    PlanPolicy,
    PlanProvenance,
    PlannedModule,
    PlannedTool,
)
from omcp.spec.normalizer import NormalizedSpec, OperationInfo
from omcp.utils.errors import PlanGenerationError

# Default chunk size for batched processing
DEFAULT_CHUNK_SIZE = 30


async def generate_plan(
    spec: NormalizedSpec,
    settings: LLMSettings,
    api_name: str | None = None,
    filtered_operations: Sequence[OperationInfo] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> OMCPPlan:
    """Generate an OMCP plan from a normalized spec using LLM.

    Args:
        spec: Normalized OpenAPI specification
        settings: LLM configuration settings
        api_name: Override API name (default: from spec)
        filtered_operations: Pre-filtered list of operations to include.
            If provided, only these operations will be sent to the LLM.
            This should be used to apply user-defined endpoint filters
            BEFORE LLM processing.
        chunk_size: Max operations per LLM call. If total ops > chunk_size,
            will process in batches and merge results.

    Returns:
        Generated OMCPPlan

    Raises:
        PlanGenerationError: If generation fails
    """
    # Create LLM adapter
    adapter = create_llm_adapter(settings)

    # Use filtered operations if provided, otherwise use all from spec
    ops_to_process = list(filtered_operations if filtered_operations is not None else spec.operations)

    # If operations fit in one chunk, use simple generation
    if len(ops_to_process) <= chunk_size:
        return await _generate_single_batch(
            operations=ops_to_process,
            spec=spec,
            settings=settings,
            adapter=adapter,
            api_name=api_name,
        )
    
    # Otherwise, use chunked generation
    from omcp.utils.console import print_info
    print_info(f"Large API ({len(ops_to_process)} ops) - processing in chunks of {chunk_size}")
    
    return await _generate_chunked(
        operations=ops_to_process,
        spec=spec,
        settings=settings,
        adapter=adapter,
        api_name=api_name,
        chunk_size=chunk_size,
    )


async def _generate_single_batch(
    operations: Sequence[OperationInfo],
    spec: NormalizedSpec,
    settings: LLMSettings,
    adapter: LLMAdapter,
    api_name: str | None,
) -> OMCPPlan:
    """Generate plan for a single batch of operations."""
    # Build operations list for prompt
    ops_list = _operations_to_list(operations)

    # Get policy constraints
    policy = settings.strategy.policy
    naming = settings.strategy.naming

    # Build the prompt
    user_prompt = build_plan_prompt(
        api_name=api_name or spec.title,
        base_url=spec.base_url,
        operations=ops_list,
        blocked_methods=policy.block_methods,
        blocked_paths=policy.block_path_globs,
        max_tools=settings.strategy.max_tools_total,
        target_per_module=settings.strategy.target_tools_per_module,
        naming_style=naming.style,
        max_name_length=naming.max_name_length,
    )

    # Generate the plan
    response = await adapter.generate(SYSTEM_PROMPT, user_prompt)

    # Parse the response
    plan_data = _parse_llm_response(response)

    # Build the plan object
    return _build_plan(
        plan_data=plan_data,
        spec=spec,
        settings=settings,
        adapter=adapter,
        api_name=api_name,
    )


async def _generate_chunked(
    operations: list[OperationInfo],
    spec: NormalizedSpec,
    settings: LLMSettings,
    adapter: LLMAdapter,
    api_name: str | None,
    chunk_size: int,
) -> OMCPPlan:
    """Generate plan by processing operations in chunks and merging results."""
    from omcp.utils.console import print_info
    
    # Split into chunks
    chunks = [operations[i:i + chunk_size] for i in range(0, len(operations), chunk_size)]
    print_info(f"Split into {len(chunks)} chunks")
    
    all_modules: dict[str, PlannedModule] = {}
    all_tools: list[PlannedTool] = []
    
    # Get policy constraints
    policy = settings.strategy.policy
    naming = settings.strategy.naming
    
    for i, chunk in enumerate(chunks):
        print_info(f"Processing chunk {i + 1}/{len(chunks)} ({len(chunk)} operations)...")
        
        ops_list = _operations_to_list(chunk)
        
        user_prompt = build_plan_prompt(
            api_name=api_name or spec.title,
            base_url=spec.base_url,
            operations=ops_list,
            blocked_methods=policy.block_methods,
            blocked_paths=policy.block_path_globs,
            max_tools=settings.strategy.max_tools_total,
            target_per_module=settings.strategy.target_tools_per_module,
            naming_style=naming.style,
            max_name_length=naming.max_name_length,
        )
        
        response = await adapter.generate(SYSTEM_PROMPT, user_prompt)
        plan_data = _parse_llm_response(response)
        
        # Merge modules (dedupe by name)
        for mod_data in plan_data.get("modules", []):
            name = mod_data.get("name", "default")
            if name not in all_modules:
                all_modules[name] = PlannedModule(
                    name=name,
                    description=mod_data.get("description", ""),
                    policy_overrides=mod_data.get("policy_overrides", {}),
                )
        
        # Collect tools
        for tool_data in plan_data.get("tools", []):
            all_tools.append(
                PlannedTool(
                    operation_id=tool_data.get("operation_id", ""),
                    method=tool_data.get("method", ""),
                    path=tool_data.get("path", ""),
                    tool_name=tool_data.get("tool_name", tool_data.get("operation_id", "")),
                    description=tool_data.get("description", ""),
                    expose=tool_data.get("expose", True),
                    module=tool_data.get("module", "default"),
                    safety_notes=tool_data.get("safety_notes", []),
                )
            )
    
    # Ensure at least one module
    modules = list(all_modules.values())
    if not modules:
        modules.append(PlannedModule(name="default", description="Default module"))
    
    print_info(f"Merged: {len(modules)} modules, {len(all_tools)} tools")
    
    # Build provenance
    provenance = PlanProvenance(
        planner_model=adapter.model_name,
        planner_provider=settings.provider.value,
        generated_at=datetime.now(timezone.utc),
        spec_hash=spec.content_hash,
    )

    # Build policy
    plan_policy = PlanPolicy(
        block_methods=settings.strategy.policy.block_methods,
        block_path_patterns=settings.strategy.policy.block_path_globs,
        require_auth_for_writes=settings.strategy.policy.require_auth_for_non_get,
    )

    return OMCPPlan(
        api_name=api_name or spec.title,
        base_url=spec.base_url,
        policy=plan_policy,
        modules=modules,
        tools=all_tools,
        provenance=provenance,
    )


def _operations_to_list(operations: Sequence[OperationInfo]) -> list[dict[str, Any]]:
    """Convert operations to list format for prompt.
    
    Args:
        operations: Sequence of OperationInfo objects (can be filtered subset)
    
    Returns:
        List of operation dicts for LLM prompt
    """
    return [
        {
            "operation_id": op.operation_id,
            "method": op.method,
            "path": op.path,
            "summary": op.summary,
            "description": op.description,
            "tags": op.tags,
            "parameters": op.parameters,
            "has_request_body": op.has_request_body,
            "deprecated": op.deprecated,
        }
        for op in operations
    ]


def _spec_to_operations_list(spec: NormalizedSpec) -> list[dict[str, Any]]:
    """Convert normalized spec operations to list format for prompt.
    
    DEPRECATED: Use _operations_to_list with filtered_operations instead.
    """
    return _operations_to_list(spec.operations)


def _parse_llm_response(response: str) -> dict[str, Any]:
    """Parse LLM response as JSON.

    Args:
        response: Raw LLM response text

    Returns:
        Parsed JSON data

    Raises:
        PlanGenerationError: If parsing fails
    """
    # Clean up response - remove markdown code blocks if present
    text = response.strip()
    if text.startswith("```json"):
        text = text[7:]
    if text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise PlanGenerationError(
            "Failed to parse LLM response as JSON",
            details=f"Error: {e}\nResponse: {text[:500]}...",
        )


def _build_plan(
    plan_data: dict[str, Any],
    spec: NormalizedSpec,
    settings: LLMSettings,
    adapter: LLMAdapter,
    api_name: str | None,
) -> OMCPPlan:
    """Build OMCPPlan from parsed LLM response.

    Args:
        plan_data: Parsed JSON from LLM
        spec: Original normalized spec
        settings: LLM settings
        adapter: LLM adapter used
        api_name: Override API name

    Returns:
        Constructed OMCPPlan
    """
    # Parse modules
    modules = []
    for mod_data in plan_data.get("modules", []):
        modules.append(
            PlannedModule(
                name=mod_data.get("name", "default"),
                description=mod_data.get("description", ""),
                policy_overrides=mod_data.get("policy_overrides", {}),
            )
        )

    # If no modules defined, create a default one
    if not modules:
        modules.append(
            PlannedModule(
                name="default",
                description="Default module for all operations",
            )
        )

    # Parse tools
    tools = []
    for tool_data in plan_data.get("tools", []):
        tools.append(
            PlannedTool(
                operation_id=tool_data.get("operation_id", ""),
                method=tool_data.get("method", ""),
                path=tool_data.get("path", ""),
                tool_name=tool_data.get("tool_name", tool_data.get("operation_id", "")),
                description=tool_data.get("description", ""),
                expose=tool_data.get("expose", True),
                module=tool_data.get("module", "default"),
                safety_notes=tool_data.get("safety_notes", []),
            )
        )

    # Build provenance
    provenance = PlanProvenance(
        planner_model=adapter.model_name,
        planner_provider=settings.provider.value,
        generated_at=datetime.now(timezone.utc),
        spec_hash=spec.content_hash,
    )

    # Build policy
    policy = PlanPolicy(
        block_methods=settings.strategy.policy.block_methods,
        block_path_patterns=settings.strategy.policy.block_path_globs,
        require_auth_for_writes=settings.strategy.policy.require_auth_for_non_get,
    )

    return OMCPPlan(
        api_name=api_name or spec.title,
        base_url=spec.base_url,
        policy=policy,
        modules=modules,
        tools=tools,
        provenance=provenance,
    )


def generate_default_plan(
    spec: NormalizedSpec,
    api_name: str | None = None,
) -> OMCPPlan:
    """Generate a default plan without LLM (uses operationIds directly).

    Useful for when LLM is not configured or as a fallback.

    Args:
        spec: Normalized OpenAPI specification
        api_name: Override API name

    Returns:
        Default OMCPPlan with minimal transformations
    """
    # Create tools from operations
    tools = []
    for op in spec.operations:
        tools.append(
            PlannedTool(
                operation_id=op.operation_id,
                method=op.method,
                path=op.path,
                tool_name=op.operation_id,  # Keep original name
                description=op.summary or op.description,
                expose=True,
                module="default",
            )
        )

    # Create default module
    modules = [
        PlannedModule(
            name="default",
            description="All API operations",
        )
    ]

    # Build provenance
    provenance = PlanProvenance(
        planner_model="none",
        planner_provider="default",
        generated_at=datetime.now(timezone.utc),
        spec_hash=spec.content_hash,
    )

    return OMCPPlan(
        api_name=api_name or spec.title,
        base_url=spec.base_url,
        modules=modules,
        tools=tools,
        provenance=provenance,
    )
