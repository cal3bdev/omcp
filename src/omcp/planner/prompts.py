"""Prompt templates for the LLM planner."""

from __future__ import annotations

from typing import Any

SYSTEM_PROMPT = """You are OMCP Planner, a tool-surface designer for MCP (Model Context Protocol).
Your job is to analyze an OpenAPI specification and produce a JSON plan that improves agent usability and safety.

## Hard Rules (MUST follow)
1. You may ONLY reference operations explicitly included in the input operations table
2. You MUST output valid JSON that matches the schema exactly
3. You MUST ensure tool_name values are unique across the entire plan
4. You MUST respect the policy constraints (blocked methods/paths)
5. Tool names MUST use snake_case format (e.g., list_users, create_order)

## Quality Guidelines
- Tool names should be verb_noun format (list_users, get_order, create_invoice)
- Descriptions should be concise but high-signal, mentioning key parameters and behaviors
- Prefer fewer, higher-quality tools over exposing everything
- Group related operations into coherent modules
- Flag potentially dangerous operations (admin, delete, internal) with safety notes

## Naming Conventions
- Use "list_" prefix for endpoints returning collections
- Use "get_" prefix for endpoints returning single items
- Use "create_" prefix for POST endpoints creating resources
- Use "update_" prefix for PUT/PATCH endpoints
- Use "delete_" prefix for DELETE endpoints (if allowed by policy)
- Include the resource name in the tool name

## Module Guidelines
- Group by domain/resource (users, orders, products, etc.)
- Keep modules cohesive - tools in a module should be related
- Aim for 10-40 tools per module
- Use descriptive module names (user_management, order_processing)
"""

PLAN_PROMPT_TEMPLATE = """# API Information
- Name: {api_name}
- Base URL: {base_url}

# Policy Constraints
- Blocked methods: {blocked_methods}
- Blocked path patterns: {blocked_paths}
- Max tools total: {max_tools}
- Target tools per module: {target_per_module}

# Naming Constraints
- Style: {naming_style}
- Max name length: {max_name_length}

# Operations Table
The following operations are available in the OpenAPI spec:

{operations_table}

# Your Task
Analyze these operations and produce a JSON plan with:
1. Module definitions (name + description for each logical grouping)
2. Tool mappings for each operation:
   - Improved tool_name (snake_case, verb_noun)
   - High-signal description
   - expose: true/false based on policy and usefulness
   - module assignment
   - safety_notes if relevant

# Output Format
Return ONLY valid JSON matching this structure:
```json
{{
  "modules": [
    {{"name": "module_name", "description": "What this module does"}}
  ],
  "tools": [
    {{
      "operation_id": "original_operation_id",
      "method": "GET",
      "path": "/path",
      "tool_name": "improved_name",
      "description": "Clear description for agents",
      "expose": true,
      "module": "module_name",
      "safety_notes": []
    }}
  ]
}}
```

Return ONLY the JSON, no markdown code blocks or other text.
"""


def format_operations_table(operations: list[dict[str, Any]]) -> str:
    """Format operations as a readable table for the prompt.

    Args:
        operations: List of operation dicts with method, path, operation_id, etc.

    Returns:
        Formatted string table
    """
    lines = []
    lines.append("| Operation ID | Method | Path | Summary | Tags |")
    lines.append("|--------------|--------|------|---------|------|")

    for op in operations:
        op_id = op.get("operation_id", "")
        method = op.get("method", "")
        path = op.get("path", "")
        summary = op.get("summary", "")[:50]  # Truncate long summaries
        tags = ", ".join(op.get("tags", []))

        lines.append(f"| {op_id} | {method} | {path} | {summary} | {tags} |")

    return "\n".join(lines)


def build_plan_prompt(
    api_name: str,
    base_url: str,
    operations: list[dict[str, Any]],
    blocked_methods: list[str],
    blocked_paths: list[str],
    max_tools: int = 200,
    target_per_module: int = 40,
    naming_style: str = "verb_noun",
    max_name_length: int = 40,
) -> str:
    """Build the complete plan generation prompt.

    Args:
        api_name: Name of the API
        base_url: Base URL of the API
        operations: List of operation dicts from normalized spec
        blocked_methods: HTTP methods to block
        blocked_paths: Path patterns to block
        max_tools: Maximum total tools to expose
        target_per_module: Target number of tools per module
        naming_style: Tool naming style
        max_name_length: Maximum tool name length

    Returns:
        Complete prompt string
    """
    operations_table = format_operations_table(operations)

    return PLAN_PROMPT_TEMPLATE.format(
        api_name=api_name,
        base_url=base_url,
        blocked_methods=", ".join(blocked_methods) or "none",
        blocked_paths=", ".join(blocked_paths) or "none",
        max_tools=max_tools,
        target_per_module=target_per_module,
        naming_style=naming_style,
        max_name_length=max_name_length,
        operations_table=operations_table,
    )
