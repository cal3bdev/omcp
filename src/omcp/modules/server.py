"""Standalone module server runner.

This script runs a single MCP module server in its own process,
avoiding asyncio event loop conflicts when running multiple servers.
"""

import argparse
import json
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run a single MCP module server")
    parser.add_argument("--config", "-c", required=True, help="Path to omcp.yaml")
    parser.add_argument("--plan", "-p", required=True, help="Path to omcp.plan.json")
    parser.add_argument("--module", "-m", required=True, help="Module name to run")
    parser.add_argument("--port", type=int, required=True, help="Port to run on")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to")
    parser.add_argument("--transport", default="streamable-http", help="Transport type")
    args = parser.parse_args()

    # Import after parsing to avoid slow startup if just showing help
    from omcp.config import load_config
    from omcp.modules.builder import ModuleBuilder
    from omcp.planner.schema import OMCPPlan
    from omcp.spec import load_spec, normalize_spec

    # Load config and spec
    config = load_config(Path(args.config))
    spec = load_spec(config.spec)
    normalized = normalize_spec(spec, config.base_url)

    # Load plan
    with open(args.plan) as f:
        plan_data = json.load(f)
    plan = OMCPPlan.model_validate(plan_data)

    # Find the module in the plan
    module_def = None
    for module in plan.modules:
        if module.name == args.module:
            module_def = module
            break

    if module_def is None:
        print(f"Error: Module '{args.module}' not found in plan", file=sys.stderr)
        sys.exit(1)

    # Build the module server
    from omcp.auth import create_auth_provider
    auth = create_auth_provider(config.auth, config.base_url)

    builder = ModuleBuilder(
        name=module_def.name,
        description=module_def.description,
        spec=normalized,
        base_url=config.base_url,
        auth=auth,
    )

    # Add operations from the module definition
    for tool in module_def.tools:
        op = normalized.operations.get(tool.operation_id)
        if op:
            builder.add_operation(
                op,
                tool_name=tool.name,
                tool_description=tool.description,
            )

    mcp = builder.build()

    # Run the server
    print(f"Starting module '{args.module}' on {args.host}:{args.port}")
    mcp.run(transport=args.transport, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
