"""Micro-MCP module generation and runtime."""

from omcp.modules.builder import ModuleBuilder, build_module_server
from omcp.modules.runner import (
    ModuleInstance,
    ModuleRegistry,
    ModuleRunner,
    run_modules,
)
from omcp.modules.splitter import (
    ModuleDefinition,
    SplitResult,
    split_by_hybrid,
    split_by_path,
    split_by_plan,
    split_by_tags,
    split_operations,
)

__all__ = [
    # Splitter
    "ModuleDefinition",
    "SplitResult",
    "split_operations",
    "split_by_plan",
    "split_by_tags",
    "split_by_path",
    "split_by_hybrid",
    # Builder
    "ModuleBuilder",
    "build_module_server",
    # Runner
    "ModuleInstance",
    "ModuleRegistry",
    "ModuleRunner",
    "run_modules",
]
