"""Plan diff - show what changed vs raw spec defaults."""

from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import Console
from rich.table import Table

from omcp.planner.schema import OMCPPlan
from omcp.spec.normalizer import NormalizedSpec


@dataclass
class ToolDiff:
    """Diff for a single tool."""

    # Required fields (no defaults)
    operation_id: str
    method: str
    path: str
    original_name: str
    new_name: str
    original_desc: str
    new_desc: str

    # Optional fields (with defaults)
    name_changed: bool = False
    desc_changed: bool = False
    exposed: bool = True
    module: str = "default"


@dataclass
class PlanDiff:
    """Complete diff between plan and raw spec."""

    # Tool changes
    renamed_tools: list[ToolDiff] = field(default_factory=list)
    redescribed_tools: list[ToolDiff] = field(default_factory=list)
    excluded_tools: list[ToolDiff] = field(default_factory=list)

    # Module info
    modules: list[str] = field(default_factory=list)
    tools_per_module: dict[str, int] = field(default_factory=dict)

    # Stats
    total_operations: int = 0
    total_exposed: int = 0
    total_excluded: int = 0


def compute_diff(plan: OMCPPlan, spec: NormalizedSpec) -> PlanDiff:
    """Compute diff between plan and raw spec.

    Args:
        plan: The generated plan
        spec: The original normalized spec

    Returns:
        PlanDiff with all changes
    """
    diff = PlanDiff()
    diff.total_operations = len(spec.operations)

    # Build spec operation lookup
    spec_ops = {op.operation_id: op for op in spec.operations}

    # Analyze each tool in the plan
    for tool in plan.tools:
        spec_op = spec_ops.get(tool.operation_id)
        if spec_op is None:
            continue

        tool_diff = ToolDiff(
            operation_id=tool.operation_id,
            method=tool.method,
            path=tool.path,
            original_name=tool.operation_id,
            new_name=tool.tool_name,
            original_desc=spec_op.summary or spec_op.description,
            new_desc=tool.description,
            exposed=tool.expose,
            module=tool.module,
        )

        # Check for name change
        if tool.tool_name != tool.operation_id:
            tool_diff.name_changed = True
            diff.renamed_tools.append(tool_diff)

        # Check for description change
        if tool.description and tool.description != (spec_op.summary or spec_op.description):
            tool_diff.desc_changed = True
            diff.redescribed_tools.append(tool_diff)

        # Check for exclusion
        if not tool.expose:
            diff.excluded_tools.append(tool_diff)
            diff.total_excluded += 1
        else:
            diff.total_exposed += 1

    # Module stats
    diff.modules = [m.name for m in plan.modules]
    diff.tools_per_module = {
        name: len(tools) for name, tools in plan.get_tools_by_module().items()
    }

    return diff


def print_diff(diff: PlanDiff, console: Console | None = None) -> None:
    """Print the plan diff to console.

    Args:
        diff: The computed diff
        console: Rich console (default: new console)
    """
    if console is None:
        console = Console()

    # Summary
    console.print("\n[bold]Plan Summary[/bold]")
    console.print(f"  Total operations: {diff.total_operations}")
    console.print(f"  Exposed as tools: {diff.total_exposed}")
    console.print(f"  Excluded: {diff.total_excluded}")
    console.print(f"  Names changed: {len(diff.renamed_tools)}")
    console.print(f"  Descriptions changed: {len(diff.redescribed_tools)}")

    # Modules
    if diff.modules:
        console.print("\n[bold]Modules[/bold]")
        for module in diff.modules:
            count = diff.tools_per_module.get(module, 0)
            console.print(f"  {module}: {count} tools")

    # Renamed tools
    if diff.renamed_tools:
        console.print("\n[bold]Renamed Tools[/bold]")
        table = Table(show_header=True)
        table.add_column("Original")
        table.add_column("New Name")
        table.add_column("Module")

        for tool in diff.renamed_tools[:20]:  # Limit display
            table.add_row(tool.original_name, tool.new_name, tool.module)

        console.print(table)
        if len(diff.renamed_tools) > 20:
            console.print(f"  ... and {len(diff.renamed_tools) - 20} more")

    # Excluded tools
    if diff.excluded_tools:
        console.print("\n[bold]Excluded Operations[/bold]")
        table = Table(show_header=True)
        table.add_column("Operation")
        table.add_column("Method")
        table.add_column("Path")

        for tool in diff.excluded_tools[:20]:
            table.add_row(tool.operation_id, tool.method, tool.path)

        console.print(table)
        if len(diff.excluded_tools) > 20:
            console.print(f"  ... and {len(diff.excluded_tools) - 20} more")


def diff_summary(diff: PlanDiff) -> str:
    """Get a one-line summary of the diff.

    Args:
        diff: The computed diff

    Returns:
        Summary string
    """
    parts = []
    parts.append(f"{diff.total_exposed}/{diff.total_operations} tools exposed")

    if diff.renamed_tools:
        parts.append(f"{len(diff.renamed_tools)} renamed")

    if diff.excluded_tools:
        parts.append(f"{len(diff.excluded_tools)} excluded")

    if len(diff.modules) > 1:
        parts.append(f"{len(diff.modules)} modules")

    return ", ".join(parts)
