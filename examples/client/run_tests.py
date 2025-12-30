"""
Test runner for MCP Agent.

Runs test prompts and measures success/performance.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from agent import run_query, list_tools
from prompts import SIMPLE_PROMPTS, MEDIUM_PROMPTS, COMPLEX_PROMPTS, TestPrompt

load_dotenv()

console = Console()


@dataclass
class TestResult:
    """Result of a single test."""
    prompt: TestPrompt
    response: str
    duration: float
    success: bool
    error: str | None = None
    tools_called: list[str] = field(default_factory=list)


@dataclass
class TestSuite:
    """Collection of test results."""
    name: str
    results: list[TestResult] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    
    @property
    def total(self) -> int:
        return len(self.results)
    
    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.success)
    
    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if not r.success)
    
    @property
    def pass_rate(self) -> float:
        return self.passed / self.total * 100 if self.total > 0 else 0
    
    @property
    def avg_duration(self) -> float:
        if not self.results:
            return 0
        return sum(r.duration for r in self.results) / len(self.results)


async def run_test(prompt: TestPrompt, mcp_url: str, verbose: bool = False) -> TestResult:
    """Run a single test prompt."""
    start = time.time()
    error = None
    response = ""
    success = False
    
    try:
        response = await run_query(prompt.query, mcp_url=mcp_url, verbose=verbose)
        # Simple heuristic: if we got a response with content, consider it a success
        success = len(response) > 50
    except Exception as e:
        error = str(e)
        success = False
    
    duration = time.time() - start
    
    return TestResult(
        prompt=prompt,
        response=response,
        duration=duration,
        success=success,
        error=error,
    )


async def run_test_suite(
    prompts: list[TestPrompt],
    name: str,
    mcp_url: str,
    verbose: bool = False,
) -> TestSuite:
    """Run a suite of test prompts."""
    suite = TestSuite(name=name)
    suite.start_time = datetime.now()
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Running {name}...", total=len(prompts))
        
        for prompt in prompts:
            progress.update(task, description=f"Testing: {prompt.name[:40]}...")
            result = await run_test(prompt, mcp_url=mcp_url, verbose=verbose)
            suite.results.append(result)
            progress.advance(task)
    
    suite.end_time = datetime.now()
    return suite


def print_suite_results(suite: TestSuite):
    """Print results of a test suite."""
    console.print(f"\n[bold]{suite.name}[/bold]")
    
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Test", style="cyan", width=40)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Duration", justify="right", width=12)
    table.add_column("Error", style="red", width=30)
    
    for result in suite.results:
        status = "[green]✓ PASS[/green]" if result.success else "[red]✗ FAIL[/red]"
        error = result.error[:27] + "..." if result.error and len(result.error) > 30 else (result.error or "")
        table.add_row(
            result.prompt.name[:40],
            status,
            f"{result.duration:.2f}s",
            error,
        )
    
    console.print(table)
    
    console.print(f"\n[bold]Summary:[/bold]")
    console.print(f"  Total: {suite.total}")
    console.print(f"  Passed: [green]{suite.passed}[/green]")
    console.print(f"  Failed: [red]{suite.failed}[/red]")
    console.print(f"  Pass Rate: {suite.pass_rate:.1f}%")
    console.print(f"  Avg Duration: {suite.avg_duration:.2f}s")


def save_results(suites: list[TestSuite], filepath: str):
    """Save test results to JSON."""
    data = {
        "timestamp": datetime.now().isoformat(),
        "suites": []
    }
    
    for suite in suites:
        suite_data = {
            "name": suite.name,
            "total": suite.total,
            "passed": suite.passed,
            "failed": suite.failed,
            "pass_rate": suite.pass_rate,
            "avg_duration": suite.avg_duration,
            "results": [
                {
                    "name": r.prompt.name,
                    "query": r.prompt.query,
                    "success": r.success,
                    "duration": r.duration,
                    "error": r.error,
                    "response_length": len(r.response),
                }
                for r in suite.results
            ]
        }
        data["suites"].append(suite_data)
    
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)
    
    console.print(f"\n[dim]Results saved to {filepath}[/dim]")


async def main():
    """Run all test suites."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run MCP Agent tests")
    parser.add_argument("--url", default=os.getenv("MCP_URL", "http://localhost:9000/mcp"),
                        help="MCP server streamable HTTP endpoint")
    parser.add_argument("--suite", choices=["simple", "medium", "complex", "all"],
                        default="all", help="Which test suite to run")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--output", "-o", help="Save results to JSON file")
    args = parser.parse_args()
    
    console.print("[bold]MCP Agent Test Runner[/bold]")
    console.print(f"Server: {args.url}\n")
    
    # Check connection
    try:
        tools = await list_tools(args.url)
        console.print(f"[green]✓[/green] Connected - {len(tools)} tools available\n")
    except Exception as e:
        console.print(f"[red]✗[/red] Failed to connect: {e}")
        return
    
    suites = []
    
    if args.suite in ("simple", "all"):
        suite = await run_test_suite(SIMPLE_PROMPTS, "Simple Tests", args.url, args.verbose)
        suites.append(suite)
        print_suite_results(suite)
    
    if args.suite in ("medium", "all"):
        suite = await run_test_suite(MEDIUM_PROMPTS, "Medium Tests", args.url, args.verbose)
        suites.append(suite)
        print_suite_results(suite)
    
    if args.suite in ("complex", "all"):
        suite = await run_test_suite(COMPLEX_PROMPTS, "Complex Tests", args.url, args.verbose)
        suites.append(suite)
        print_suite_results(suite)
    
    # Overall summary
    if len(suites) > 1:
        total = sum(s.total for s in suites)
        passed = sum(s.passed for s in suites)
        console.print(f"\n[bold]Overall:[/bold] {passed}/{total} ({passed/total*100:.1f}%)")
    
    if args.output:
        save_results(suites, args.output)


if __name__ == "__main__":
    asyncio.run(main())
