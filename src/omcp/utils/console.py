"""Console output utilities using Rich."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from omcp.utils.errors import OMCPError

# Use stderr for all output to avoid polluting stdout (needed for stdio MCP transport)
console = Console(stderr=True)
error_console = Console(stderr=True)


def print_error(error: OMCPError | str) -> None:
    """Print an error message."""
    if isinstance(error, OMCPError):
        message = f"[bold red]Error:[/] {error.message}"
        if error.details:
            message += f"\n[dim]{error.details}[/]"
    else:
        message = f"[bold red]Error:[/] {error}"
    error_console.print(message)


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green]✓[/] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold yellow]![/] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[bold blue]>[/] {message}")


def print_panel(title: str, content: str) -> None:
    """Print content in a panel."""
    console.print(Panel(content, title=title))


def create_table(title: str, columns: list[str]) -> Table:
    """Create a table with the given columns."""
    table = Table(title=title)
    for col in columns:
        table.add_column(col)
    return table


def create_progress() -> Progress:
    """Create a progress indicator."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    )
