"""Hub server for module discovery and routing."""

from omcp.hub.builder import HubBuilder, build_hub
from omcp.hub.registry import HubRegistry, RegisteredModule
from omcp.hub.router import HubRouter, HubRoutingError, RouteResult, RoutingMode
from omcp.hub.runner import (
    HubRunner,
    create_hub_registry_from_modules,
    run_hub,
)

__all__ = [
    # Registry
    "HubRegistry",
    "RegisteredModule",
    # Router
    "HubRouter",
    "HubRoutingError",
    "RouteResult",
    "RoutingMode",
    # Builder
    "HubBuilder",
    "build_hub",
    # Runner
    "HubRunner",
    "create_hub_registry_from_modules",
    "run_hub",
]
