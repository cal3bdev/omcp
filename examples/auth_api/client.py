#!/usr/bin/env python3
"""
ADK Agent Client for Notes API with JWT Authentication.

This client demonstrates OMCP's dynamic authentication by:
1. Getting a JWT token for a specified user
2. Connecting to OMCP with the token in headers
3. Running an interactive agent session

Usage:
    uv run python examples/auth_api/client.py --user alice
    uv run python examples/auth_api/client.py --user bob
    uv run python examples/auth_api/client.py --user charlie
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.genai import types

load_dotenv()

console = Console()

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8080")
MCP_URL = os.getenv("MCP_URL", "http://localhost:9000/mcp")

# Available test users
USERS = {
    "alice": {"role": "admin", "description": "Admin user with 2 notes + stats access"},
    "bob": {"role": "user", "description": "Regular user with 2 notes"},
    "charlie": {"role": "user", "description": "Regular user with 1 note"},
}

# Agent instruction for Notes API
NOTES_AGENT_INSTRUCTION = """You are a helpful assistant connected to a Notes API via OMCP.

## Available Tools (7 total)
- **get_me** - Get current user information
- **list_notes** - List all your notes
- **create_note** - Create a new note (requires title and content)
- **get_note** - Get a specific note by ID
- **update_note** - Update a note (title and/or content)
- **delete_note** - Delete a note by ID
- **get_stats** - Get system statistics (admin only)

## Important Guidelines
1. You are already authenticated - just call the tools directly
2. Each user can only see and manage their own notes
3. For get_stats: Try calling it when requested - the API will return an error if the user lacks permission
4. When creating notes, ask for title and content if not provided
5. Be helpful and concise in your responses

## Note Format
Notes have: id, title, content, created_at, updated_at
"""


async def get_token(username: str) -> str:
    """Get JWT token for a user from the API."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{API_URL}/auth/token",
            params={"username": username, "password": username},
        )
        if response.status_code != 200:
            raise RuntimeError(f"Failed to get token: {response.text}")
        data = response.json()
        return data["access_token"]


def create_authenticated_agent(
    token: str,
    username: str,
    model: str = "gemini-2.0-flash",
) -> tuple[LlmAgent, McpToolset]:
    """Create an ADK agent with authenticated MCP connection."""
    # Create MCP toolset with auth header
    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=MCP_URL,
            headers={"Authorization": f"Bearer {token}"},
        ),
    )

    agent = LlmAgent(
        model=model,
        name=f"notes_agent_{username}",
        instruction=NOTES_AGENT_INSTRUCTION,
        tools=[toolset],
    )

    return agent, toolset


async def run_agent(username: str, model: str = "gemini-2.0-flash"):
    """Run interactive agent session for a user."""
    # Show header
    user_info = USERS.get(username, {})
    console.print(Panel.fit(
        f"[bold blue]Notes Agent[/bold blue]\n"
        f"User: [green]{username}[/green] ({user_info.get('role', 'user')})\n"
        f"[dim]{user_info.get('description', '')}[/dim]",
        border_style="blue",
    ))

    # Get token
    console.print("\n[dim]Authenticating...[/dim]", end=" ")
    try:
        token = await get_token(username)
        console.print("[green]OK[/green]")
    except Exception as e:
        console.print(f"[red]Failed: {e}[/red]")
        console.print("\n[yellow]Make sure the Notes API is running:[/yellow]")
        console.print("  uv run uvicorn examples.auth_api.main:app --port 8080")
        return

    # Create agent
    console.print("[dim]Connecting to OMCP...[/dim]", end=" ")
    try:
        agent, toolset = create_authenticated_agent(token, username, model)
        console.print("[green]OK[/green]")
    except Exception as e:
        console.print(f"[red]Failed: {e}[/red]")
        console.print("\n[yellow]Make sure OMCP is running:[/yellow]")
        console.print("  uv run omcp serve --config examples/auth_api/omcp.yaml")
        return

    # Show available tools
    try:
        tools = await toolset.get_tools()
        console.print(f"\n[dim]Available tools: {', '.join(t.name for t in tools)}[/dim]")
    except Exception as e:
        console.print(f"[red]Failed to list tools: {e}[/red]")
        console.print("\n[yellow]Make sure OMCP is running:[/yellow]")
        console.print("  uv run omcp serve --config examples/auth_api/omcp.yaml")
        await toolset.close()
        return

    # Create runner
    session_service = InMemorySessionService()
    runner = Runner(
        agent=agent,
        app_name="notes_client",
        session_service=session_service,
    )
    session = await session_service.create_session(
        app_name="notes_client",
        user_id=username,
    )

    console.print("\n[bold]Chat with your Notes Agent[/bold]")
    console.print("[dim]Type 'quit' to exit, 'help' for suggestions[/dim]\n")

    try:
        while True:
            try:
                query = console.input(f"[bold cyan]{username}>[/bold cyan] ").strip()
                if not query:
                    continue
                if query.lower() in ("quit", "exit", "q"):
                    break
                if query.lower() == "help":
                    console.print(Panel(
                        "Try these:\n"
                        "- 'What notes do I have?'\n"
                        "- 'Create a note about my weekend plans'\n"
                        "- 'Who am I?'\n"
                        "- 'Show system stats' (admin only)\n"
                        "- 'Delete my first note'",
                        title="Suggestions",
                        border_style="dim",
                    ))
                    continue

                # Run query
                console.print()
                async for event in runner.run_async(
                    user_id=username,
                    session_id=session.id,
                    new_message=types.Content(
                        role="user",
                        parts=[types.Part(text=query)]
                    ),
                ):
                    if hasattr(event, 'content') and event.content and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                console.print(f"[green]Agent:[/green] {part.text}")
                            if hasattr(part, 'function_call') and part.function_call:
                                fc = part.function_call
                                console.print(f"[dim]  → {fc.name}({dict(fc.args) if fc.args else ''})[/dim]")

                console.print()

            except KeyboardInterrupt:
                console.print("\n[dim]Use 'quit' to exit[/dim]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

    finally:
        console.print("\n[dim]Closing connection...[/dim]")
        await toolset.close()
        console.print("[dim]Goodbye![/dim]")


def main():
    parser = argparse.ArgumentParser(
        description="Notes Agent - Chat with your notes using AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --user alice     # Run as alice (admin)
  %(prog)s --user bob       # Run as bob (user)
  %(prog)s -u charlie       # Run as charlie (user)

Available users:
  alice   - Admin with 2 notes, can view stats
  bob     - User with 2 notes
  charlie - User with 1 note

Password = username for all users.
        """,
    )
    parser.add_argument(
        "-u", "--user",
        choices=list(USERS.keys()),
        required=True,
        help="User to authenticate as",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.0-flash",
        help="Gemini model to use (default: gemini-2.0-flash)",
    )

    args = parser.parse_args()
    asyncio.run(run_agent(args.user, args.model))


if __name__ == "__main__":
    main()
