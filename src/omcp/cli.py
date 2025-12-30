"""OMCP CLI - OpenAPI to MCP converter."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Optional

import typer

from omcp import __version__
from omcp.config import load_config
from omcp.config.models import AuthType, Mode
from omcp.utils.console import console, create_table, print_error, print_info, print_success, print_warning
from omcp.utils.errors import OMCPError

app = typer.Typer(
    name="omcp",
    help="Convert OpenAPI specifications into MCP servers.",
    no_args_is_help=True,
)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"omcp version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", "-v", callback=version_callback, is_eager=True),
    ] = None,
) -> None:
    """OMCP - OpenAPI to MCP converter."""
    pass


ConfigOption = Annotated[
    Path,
    typer.Option(
        "--config",
        "-c",
        help="Path to omcp.yaml config file",
        exists=True,
        dir_okay=False,
    ),
]


@app.command()
def serve(
    config: ConfigOption = Path("omcp.yaml"),
    plan_file: Annotated[
        Optional[Path],
        typer.Option("--plan", "-p", help="Path to omcp.plan.json for modular mode"),
    ] = None,
) -> None:
    """Run MCP server(s) based on configuration.

    In single mode, runs one MCP server.
    In modular mode, runs multiple micro-MCPs and optionally a hub.
    """
    try:
        cfg = load_config(config)
        print_info(f"Loaded config: {cfg.name}")
        print_info(f"Mode: {cfg.mode.value}")
        print_info(f"Spec: {cfg.spec}")

        if cfg.mode == Mode.MODULAR:
            _serve_modular(cfg, plan_file)
        else:
            _serve_single(cfg)

    except OMCPError as e:
        print_error(e)
        raise typer.Exit(1)
    except KeyboardInterrupt:
        print_info("Server stopped")


def _serve_single(cfg) -> None:
    """Run single server mode."""
    from omcp.server import ServerBuilder, run_server

    # Build and show tool list first
    builder = ServerBuilder(cfg)
    tools = builder.get_tool_list()

    print_info(f"Exposing {len(tools)} tools")

    # Run the server
    run_server(cfg)


def _serve_modular(cfg, plan_file: Path | None) -> None:
    """Run modular server mode with multiple micro-MCPs and optional hub."""
    import asyncio
    import json
    from concurrent.futures import ThreadPoolExecutor

    from omcp.hub import HubRunner, create_hub_registry_from_modules
    from omcp.modules import ModuleRunner
    from omcp.planner.schema import OMCPPlan
    from omcp.spec import load_spec_sync, normalize_spec, validate_spec

    # Load and normalize spec
    print_info(f"Loading spec: {cfg.spec}")
    raw_spec = load_spec_sync(cfg.spec)
    validate_spec(raw_spec)
    spec = normalize_spec(raw_spec, cfg.base_url)
    print_info(f"Found {len(spec.operations)} operations")

    # Load plan if provided or if using LLM strategy
    plan: OMCPPlan | None = None

    if plan_file and plan_file.exists():
        print_info(f"Loading plan: {plan_file}")
        plan_data = json.loads(plan_file.read_text())
        plan = OMCPPlan.model_validate(plan_data)
        print_info(f"Plan has {len(plan.tools)} tools in {len(plan.modules)} modules")
    elif cfg.modules.split_strategy == "llm":
        # Try default plan path
        default_plan = Path(cfg.llm.output.plan_path)
        if default_plan.exists():
            print_info(f"Loading plan: {default_plan}")
            plan_data = json.loads(default_plan.read_text())
            plan = OMCPPlan.model_validate(plan_data)
            print_info(f"Plan has {len(plan.tools)} tools in {len(plan.modules)} modules")
        else:
            print_error("LLM split strategy requires a plan file")
            print_info(f"Run 'omcp plan' first or provide --plan option")
            raise typer.Exit(1)

    # Create module runner
    module_runner = ModuleRunner(cfg, spec, plan)

    # Show module info
    module_info = module_runner.get_module_info()
    print_info(f"Starting {len(module_info)} modules:")
    for info in module_info:
        print_info(f"  {info['name']}: {info['tool_count']} tools")

    # Check if hub is enabled
    if cfg.hub.enabled:
        # Run modules and hub together
        asyncio.run(_run_modules_and_hub(cfg, module_runner))
    else:
        # Just run modules
        module_runner.run()


async def _run_modules_and_hub(cfg, module_runner) -> None:
    """Run modules and hub together."""
    import signal
    from concurrent.futures import ThreadPoolExecutor

    from omcp.hub import HubRunner, create_hub_registry_from_modules

    # Start modules first (they need to be running for hub to connect)
    # We'll run them in background and start hub after a brief delay

    shutdown_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: shutdown_event.set())
        except NotImplementedError:
            pass

    executor = ThreadPoolExecutor(max_workers=len(module_runner.split_result.modules) + 1)

    try:
        # Build modules and get registry
        modules = module_runner.split_result.modules
        transport = cfg.modules.runtime.transport
        if transport == "http":
            transport = "streamable-http"
        host = cfg.modules.runtime.host

        module_tasks = []
        for index, module in enumerate(modules):
            port = module_runner._get_module_port(index)
            url = module_runner._get_module_url(port)

            builder = module_runner._build_module(module)
            mcp = builder.build()

            # Register in module runner's registry
            from omcp.modules.runner import ModuleInstance

            instance = ModuleInstance(
                name=module.name,
                port=port,
                url=url,
                mcp=mcp,
                tool_count=len(module.operations),
            )
            module_runner.registry.register(instance)

            print_success(f"  {module.name}: {url} ({len(module.operations)} tools)")

            # Start module in executor
            task = loop.run_in_executor(
                executor,
                lambda m=mcp, h=host, p=port, t=transport: m.run(transport=t, host=h, port=p),
            )
            module_tasks.append(task)

        # Brief delay to let modules start
        await asyncio.sleep(0.5)

        # Create hub registry from module registry
        hub_registry = create_hub_registry_from_modules(module_runner.registry)
        print_info(f"Hub registry: {len(hub_registry)} modules registered")

        # Start hub
        hub_runner = HubRunner(hub_registry, cfg.hub)
        print_success(f"Hub ready at http://{cfg.hub.host}:{cfg.hub.port}")

        hub_task = loop.run_in_executor(executor, hub_runner.run)

        print_info("All services started. Press Ctrl+C to stop.")

        # Wait for shutdown
        await shutdown_event.wait()

    finally:
        executor.shutdown(wait=False)
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.remove_signal_handler(sig)
            except (NotImplementedError, ValueError):
                pass


@app.command()
def plan(
    config: ConfigOption = Path("omcp.yaml"),
    output: Annotated[
        Optional[Path],
        typer.Option("--output", "-o", help="Output path for the plan file"),
    ] = None,
    no_validate: Annotated[
        bool,
        typer.Option("--no-validate", help="Skip plan validation"),
    ] = False,
    show_diff: Annotated[
        bool,
        typer.Option("--diff", "-d", help="Show diff after generation"),
    ] = True,
) -> None:
    """Generate an OMCP plan using the LLM planner.

    Analyzes the OpenAPI spec and produces optimized tool names,
    descriptions, module assignments, and safety policies.
    """
    import asyncio
    import json

    try:
        cfg = load_config(config)
        print_info(f"Loaded config: {cfg.name}")

        if not cfg.llm.enabled:
            print_error("LLM planner is not enabled in config")
            print_info("Set llm.enabled: true in config to use the planner")
            raise typer.Exit(1)

        # Load and normalize spec
        from omcp.spec import load_spec_sync, normalize_spec, validate_spec

        print_info(f"Loading spec: {cfg.spec}")
        raw_spec = load_spec_sync(cfg.spec)
        validate_spec(raw_spec)
        spec = normalize_spec(raw_spec, cfg.base_url)
        print_info(f"Found {len(spec.operations)} operations in spec")

        # Apply endpoint filters BEFORE sending to LLM
        # User-defined exclusions are the "hard" filter
        from omcp.filters import build_route_map

        route_map = build_route_map(
            spec,
            include_patterns=cfg.endpoints.include or None,
            exclude_patterns=cfg.endpoints.exclude or None,
        )
        
        # Get only the operations that pass the endpoint filter
        included_op_ids = {e.operation_id for e in route_map.get_included_operations()}
        filtered_operations = [op for op in spec.operations if op.operation_id in included_op_ids]
        
        excluded_count = len(spec.operations) - len(filtered_operations)
        if excluded_count > 0:
            print_info(f"Excluded {excluded_count} operations by endpoint filters")
        print_info(f"Sending {len(filtered_operations)} operations to LLM")

        # Generate plan
        from omcp.planner import (
            compute_diff,
            generate_plan,
            print_diff,
            raise_if_invalid,
            validate_plan,
        )

        print_info(f"Generating plan with {cfg.llm.provider.value} ({cfg.llm.model})...")

        generated_plan = asyncio.run(
            generate_plan(spec, cfg.llm, api_name=cfg.name, filtered_operations=filtered_operations)
        )

        print_success(f"Generated plan with {len(generated_plan.tools)} tools")

        # Validate
        if not no_validate:
            print_info("Validating plan...")
            result = validate_plan(generated_plan, spec, cfg.llm)

            if result.warnings:
                for warning in result.warnings:
                    print_warning(f"[{warning.code}] {warning.message}")

            raise_if_invalid(result)
            print_success("Plan validation passed")

        # Show diff
        if show_diff:
            diff = compute_diff(generated_plan, spec)
            print_diff(diff, console)

        # Save plan
        output_path = output or Path(cfg.llm.output.plan_path)
        plan_json = generated_plan.model_dump_json(indent=2)
        output_path.write_text(plan_json)
        print_success(f"Plan saved to {output_path}")

    except OMCPError as e:
        print_error(e)
        raise typer.Exit(1)


@app.command("list")
def list_operations(
    config: ConfigOption = Path("omcp.yaml"),
    plan_file: Annotated[
        Optional[Path],
        typer.Option("--plan", "-p", help="Path to omcp.plan.json for module info"),
    ] = None,
    show_excluded: Annotated[
        bool,
        typer.Option("--excluded", "-e", help="Also show excluded operations"),
    ] = False,
    by_module: Annotated[
        bool,
        typer.Option("--by-module", "-m", help="Group tools by module (requires plan or modular mode)"),
    ] = False,
) -> None:
    """List available operations from the OpenAPI spec.

    If a plan file is provided, shows module assignments.
    """
    import json

    try:
        cfg = load_config(config)

        # Check if we should show modular view
        if by_module or cfg.mode == Mode.MODULAR:
            _list_modular(cfg, plan_file, show_excluded)
        else:
            _list_single(cfg, plan_file, show_excluded)

    except OMCPError as e:
        print_error(e)
        raise typer.Exit(1)


def _list_single(cfg, plan_file: Path | None, show_excluded: bool) -> None:
    """List operations in single mode."""
    from omcp.server import ServerBuilder

    builder = ServerBuilder(cfg)
    tools = builder.get_tool_list()

    # Create table
    table = create_table(
        f"Tools from {cfg.name}",
        ["Tool Name", "Method", "Path", "Description"],
    )

    for tool in tools:
        desc = tool["description"]
        if len(desc) > 50:
            desc = desc[:47] + "..."
        table.add_row(
            tool["name"],
            tool["method"],
            tool["path"],
            desc,
        )

    console.print(table)
    print_info(f"Total: {len(tools)} tools")

    if show_excluded:
        excluded = builder.route_map.get_excluded_operations()
        if excluded:
            console.print()
            exc_table = create_table(
                "Excluded Operations",
                ["Operation ID", "Method", "Path"],
            )
            for op in excluded:
                exc_table.add_row(op.operation_id, op.method, op.path)
            console.print(exc_table)
            print_info(f"Excluded: {len(excluded)} operations")


def _list_modular(cfg, plan_file: Path | None, show_excluded: bool) -> None:
    """List operations grouped by module."""
    import json

    from omcp.modules import ModuleRunner
    from omcp.planner.schema import OMCPPlan
    from omcp.spec import load_spec_sync, normalize_spec, validate_spec

    # Load and normalize spec
    raw_spec = load_spec_sync(cfg.spec)
    validate_spec(raw_spec)
    spec = normalize_spec(raw_spec, cfg.base_url)

    # Load plan if provided
    plan: OMCPPlan | None = None

    if plan_file and plan_file.exists():
        plan_data = json.loads(plan_file.read_text())
        plan = OMCPPlan.model_validate(plan_data)
    elif cfg.modules.split_strategy == "llm":
        default_plan = Path(cfg.llm.output.plan_path)
        if default_plan.exists():
            plan_data = json.loads(default_plan.read_text())
            plan = OMCPPlan.model_validate(plan_data)

    # Create module runner to get module info
    runner = ModuleRunner(cfg, spec, plan)
    module_info = runner.get_module_info()

    total_tools = 0
    for info in module_info:
        # Create table for each module
        table = create_table(
            f"Module: {info['name']} ({info['tool_count']} tools)",
            ["Tool Name", "Method", "Path", "Description"],
        )

        for tool in info["tools"]:
            desc = tool["description"] or ""
            if len(desc) > 40:
                desc = desc[:37] + "..."
            table.add_row(
                tool["name"],
                tool["method"],
                tool["path"],
                desc,
            )

        console.print(table)
        console.print()
        total_tools += info["tool_count"]

    print_info(f"Total: {len(module_info)} modules, {total_tools} tools")


@app.command()
def auth(
    config: ConfigOption = Path("omcp.yaml"),
    clear: Annotated[
        bool,
        typer.Option("--clear", help="Clear stored tokens instead of authenticating"),
    ] = False,
) -> None:
    """Run OAuth2 authorization flow.

    Opens a browser for authorization and stores the resulting tokens.
    """
    try:
        cfg = load_config(config)
        print_info(f"Loaded config: {cfg.name}")

        if cfg.auth.type != AuthType.OAUTH2:
            print_error(f"Auth type is {cfg.auth.type.value}, not oauth2")
            print_info("This command is only for OAuth2 authentication")
            raise typer.Exit(1)

        from omcp.auth import OAuth2Auth, TokenStorage

        # Create OAuth2 provider
        storage = TokenStorage()
        oauth = OAuth2Auth(
            client_id=cfg.auth.client_id or "",
            auth_url=cfg.auth.auth_url or "",
            token_url=cfg.auth.token_url or "",
            scopes=cfg.auth.scopes,
            client_secret=cfg.auth.client_secret,
            provider_name=cfg.name,
            storage=storage,
        )

        if clear:
            oauth.clear_token()
            print_success("Cleared stored tokens")
            return

        # Check if already authenticated
        if oauth.is_valid():
            print_info("Already authenticated with valid token")
            if not typer.confirm("Re-authenticate?"):
                return

        # Run the auth flow
        print_info("Opening browser for authorization...")
        print_info(f"Callback URL: {oauth.redirect_uri}")

        token = oauth.run_auth_flow(open_browser=True)

        print_success("Authentication successful!")
        print_info(f"Token expires: {token.expires_at or 'never'}")

    except OMCPError as e:
        print_error(e)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
