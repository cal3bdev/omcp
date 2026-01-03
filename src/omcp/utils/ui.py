"""Custom terminal UI for OMCP server startup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.align import Align
from rich.box import ROUNDED, HEAVY, DOUBLE
from rich.columns import Columns
from rich.console import Console, Group
from rich.panel import Panel
from rich.style import Style
from rich.table import Table
from rich.text import Text

if TYPE_CHECKING:
    from omcp.config.models import OMCPConfig

# Use stderr to avoid polluting stdout (needed for stdio MCP transport)
console = Console(stderr=True)

# Color scheme
BRAND_COLOR = "cyan"
ACCENT_COLOR = "bright_cyan"
SUCCESS_COLOR = "green"
DIM_COLOR = "bright_black"
WARN_COLOR = "yellow"


LOGO = """
 ██████╗ ███╗   ███╗ ██████╗██████╗
██╔═══██╗████╗ ████║██╔════╝██╔══██╗
██║   ██║██╔████╔██║██║     ██████╔╝
██║   ██║██║╚██╔╝██║██║     ██╔═══╝
╚██████╔╝██║ ╚═╝ ██║╚██████╗██║
 ╚═════╝ ╚═╝     ╚═╝ ╚═════╝╚═╝
"""

LOGO_SMALL = """
┌─┐┌┬┐┌─┐┌─┐
│ ││││││  ├─┘
└─┘┴ ┴└─┘┴
"""


@dataclass
class ModuleInfo:
    """Information about a running module."""
    name: str
    url: str
    tool_count: int
    tools: list[str]


@dataclass
class ServerInfo:
    """Information about server configuration."""
    name: str
    mode: str
    transport: str
    host: str
    port: int
    spec: str
    total_tools: int
    modules: list[ModuleInfo] | None = None
    hub_enabled: bool = False
    hub_url: str | None = None


def print_banner(version: str = "") -> None:
    """Print the OMCP startup banner."""
    logo_text = Text(LOGO, style=f"bold {BRAND_COLOR}")

    subtitle = Text()
    subtitle.append("OpenAPI ", style=DIM_COLOR)
    subtitle.append("→ ", style=ACCENT_COLOR)
    subtitle.append("MCP", style=f"bold {BRAND_COLOR}")
    if version:
        subtitle.append(f"  v{version}", style=DIM_COLOR)

    content = Group(
        Align.center(logo_text),
        Align.center(subtitle),
    )

    console.print()
    console.print(content)
    console.print()


def print_config_summary(info: ServerInfo) -> None:
    """Print a summary of the server configuration."""
    # Create info grid
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style=DIM_COLOR, justify="right")
    grid.add_column(style="white")

    grid.add_row("API", Text(info.name, style="bold white"))
    grid.add_row("Mode", Text(info.mode, style=ACCENT_COLOR))
    grid.add_row("Transport", info.transport)
    grid.add_row("Spec", _truncate_path(info.spec, 40))

    panel = Panel(
        grid,
        title=f"[{BRAND_COLOR}]Configuration[/]",
        border_style=DIM_COLOR,
        box=ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)


def print_single_server_ready(info: ServerInfo) -> None:
    """Print ready message for single server mode."""
    # Server status
    status_grid = Table.grid(padding=(0, 2))
    status_grid.add_column(style=DIM_COLOR, justify="right")
    status_grid.add_column()

    url = f"http://{info.host}:{info.port}" if info.transport != "stdio" else "stdio"
    status_grid.add_row("Endpoint", Text(url, style=f"bold {SUCCESS_COLOR}"))
    status_grid.add_row("Tools", Text(str(info.total_tools), style="bold white"))

    panel = Panel(
        status_grid,
        title=f"[{SUCCESS_COLOR}]● Server Ready[/]",
        border_style=SUCCESS_COLOR,
        box=ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)
    _print_footer()


def print_modules_starting(modules: list[ModuleInfo]) -> None:
    """Print info about modules being started."""
    table = Table(
        box=ROUNDED,
        border_style=DIM_COLOR,
        title=f"[{BRAND_COLOR}]Modules[/]",
        title_style="",
        show_header=True,
        header_style=f"bold {DIM_COLOR}",
        padding=(0, 1),
    )

    table.add_column("Module", style="bold white")
    table.add_column("URL", style=DIM_COLOR)
    table.add_column("Tools", justify="right", style=ACCENT_COLOR)

    for mod in modules:
        table.add_row(
            mod.name,
            mod.url,
            str(mod.tool_count),
        )

    console.print(table)


def print_hub_ready(info: ServerInfo) -> None:
    """Print ready message for hub server."""
    content = Table.grid(padding=(0, 2))
    content.add_column(style=DIM_COLOR, justify="right")
    content.add_column()

    if info.hub_url:
        content.add_row("Hub", Text(info.hub_url, style=f"bold {SUCCESS_COLOR}"))

    module_count = len(info.modules) if info.modules else 0
    content.add_row("Modules", Text(str(module_count), style="bold white"))
    content.add_row("Total Tools", Text(str(info.total_tools), style="bold white"))

    panel = Panel(
        content,
        title=f"[{SUCCESS_COLOR}]● All Services Ready[/]",
        border_style=SUCCESS_COLOR,
        box=ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)
    _print_footer()


def print_modular_ready(info: ServerInfo) -> None:
    """Print ready message for modular mode without hub."""
    content = Table.grid(padding=(0, 2))
    content.add_column(style=DIM_COLOR, justify="right")
    content.add_column()

    module_count = len(info.modules) if info.modules else 0
    content.add_row("Modules", Text(str(module_count), style="bold white"))
    content.add_row("Total Tools", Text(str(info.total_tools), style="bold white"))

    panel = Panel(
        content,
        title=f"[{SUCCESS_COLOR}]● Modules Ready[/]",
        border_style=SUCCESS_COLOR,
        box=ROUNDED,
        padding=(0, 1),
    )
    console.print(panel)
    _print_footer()


def print_tool_list(tools: list[dict], title: str = "Tools") -> None:
    """Print a compact list of tools."""
    if not tools:
        return

    table = Table(
        box=ROUNDED,
        border_style=DIM_COLOR,
        title=f"[{BRAND_COLOR}]{title}[/]",
        title_style="",
        show_header=True,
        header_style=f"bold {DIM_COLOR}",
        padding=(0, 1),
        expand=False,
    )

    table.add_column("Tool", style="white", no_wrap=True)
    table.add_column("Method", style=DIM_COLOR, width=7)
    table.add_column("Path", style=DIM_COLOR)

    # Show first 10 tools, then summary
    display_tools = tools[:10]
    for tool in display_tools:
        method_style = _get_method_style(tool.get("method", ""))
        table.add_row(
            tool["name"],
            Text(tool.get("method", ""), style=method_style),
            _truncate_path(tool.get("path", ""), 30),
        )

    if len(tools) > 10:
        table.add_row(
            Text(f"... and {len(tools) - 10} more", style=DIM_COLOR),
            "",
            "",
        )

    console.print(table)


def print_status(message: str, status: str = "info") -> None:
    """Print a status message."""
    icons = {
        "info": ("●", BRAND_COLOR),
        "success": ("✓", SUCCESS_COLOR),
        "warning": ("!", WARN_COLOR),
        "loading": ("◌", DIM_COLOR),
    }
    icon, color = icons.get(status, ("●", BRAND_COLOR))
    console.print(f"[{color}]{icon}[/] {message}")


def _print_footer() -> None:
    """Print the footer with exit instructions."""
    console.print()
    console.print(
        Text("Press Ctrl+C to stop", style=DIM_COLOR),
        justify="center",
    )
    console.print()


def _truncate_path(path: str, max_len: int) -> str:
    """Truncate a path for display."""
    if len(path) <= max_len:
        return path
    return "..." + path[-(max_len - 3):]


def _get_method_style(method: str) -> str:
    """Get color style for HTTP method."""
    styles = {
        "GET": "green",
        "POST": "yellow",
        "PUT": "blue",
        "PATCH": "cyan",
        "DELETE": "red",
    }
    return styles.get(method.upper(), DIM_COLOR)