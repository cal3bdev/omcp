"""Chainlit UI for the Auth API example using Google ADK.

A beautiful chat interface with:
- User profile selection (Alice, Bob, Charlie)
- Tool call visualization via ADK events
- Streaming responses

Usage:
    # First start the servers:
    uv run python examples/auth_api/start.py

    # Then run the Chainlit app:
    uv run chainlit run examples/auth_api/app.py
"""

from __future__ import annotations

import os

import chainlit as cl
import httpx
from dotenv import load_dotenv
from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.genai import types

# Load environment variables
load_dotenv()

# Configuration
API_URL = os.getenv("API_URL", "http://localhost:8080")
MCP_URL = os.getenv("MCP_URL", "http://localhost:9000/mcp")

# User profiles
USERS = {
    "alice": {
        "role": "admin",
        "icon": "https://api.dicebear.com/7.x/avataaars/svg?seed=alice",
        "description": "Admin user with full access to notes and system stats",
    },
    "bob": {
        "role": "user",
        "icon": "https://api.dicebear.com/7.x/avataaars/svg?seed=bob",
        "description": "Regular user with access to personal notes only",
    },
    "charlie": {
        "role": "user",
        "icon": "https://api.dicebear.com/7.x/avataaars/svg?seed=charlie",
        "description": "Regular user with access to personal notes only",
    },
}

AGENT_INSTRUCTION = """You are a helpful assistant connected to a Notes API via OMCP.

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
        return response.json()["access_token"]


def create_authenticated_agent(
    token: str,
    username: str,
    model: str = "gemini-3-flash-preview",
) -> tuple[LlmAgent, McpToolset]:
    """Create an ADK agent with authenticated MCP connection."""
    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(
            url=MCP_URL,
            headers={"Authorization": f"Bearer {token}"},
        ),
    )

    agent = LlmAgent(
        model=model,
        name=f"notes_agent_{username}",
        instruction=AGENT_INSTRUCTION,
        tools=[toolset],
    )

    return agent, toolset


@cl.set_chat_profiles
async def chat_profiles():
    """Define available user profiles."""
    return [
        cl.ChatProfile(
            name="alice",
            markdown_description=f"**Alice** (Admin)\n\n{USERS['alice']['description']}",
            icon=USERS["alice"]["icon"],
        ),
        cl.ChatProfile(
            name="bob",
            markdown_description=f"**Bob** (User)\n\n{USERS['bob']['description']}",
            icon=USERS["bob"]["icon"],
        ),
        cl.ChatProfile(
            name="charlie",
            markdown_description=f"**Charlie** (User)\n\n{USERS['charlie']['description']}",
            icon=USERS["charlie"]["icon"],
        ),
    ]


@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session with ADK agent."""
    # Get selected profile
    chat_profile = cl.user_session.get("chat_profile") or "alice"
    user_info = USERS.get(chat_profile, USERS["alice"])

    # Show welcome message
    await cl.Message(
        content=f"Welcome **{chat_profile.title()}**! You are logged in as **{user_info['role']}**.\n\n"
        "Setting up your agent..."
    ).send()

    # Get JWT token
    try:
        token = await get_token(chat_profile)
    except Exception as e:
        await cl.Message(
            content=f"Failed to authenticate: {e}\n\n"
            "Make sure the servers are running:\n"
            "```bash\nuv run python examples/auth_api/start.py\n```"
        ).send()
        return

    # Create ADK agent with MCP toolset
    try:
        agent, toolset = create_authenticated_agent(token, chat_profile)

        # Get available tools
        tools = await toolset.get_tools()
        tool_names = ", ".join(f"`{t.name}`" for t in tools)

        # Create session service and runner
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="notes_chainlit",
            session_service=session_service,
        )
        session = await session_service.create_session(
            app_name="notes_chainlit",
            user_id=chat_profile,
        )

        # Store in user session
        cl.user_session.set("runner", runner)
        cl.user_session.set("session", session)
        cl.user_session.set("toolset", toolset)
        cl.user_session.set("username", chat_profile)

        await cl.Message(
            content=f"Connected to OMCP!\n\n"
            f"**Available tools:** {tool_names}\n\n"
            f"Try asking:\n"
            f"- \"What notes do I have?\"\n"
            f"- \"Create a note about my weekend plans\"\n"
            f"- \"Who am I?\"\n"
            + (f"- \"Show system stats\"\n" if user_info["role"] == "admin" else "")
        ).send()

    except Exception as e:
        await cl.Message(
            content=f"Failed to connect to OMCP: {e}\n\n"
            "Make sure OMCP is running:\n"
            "```bash\nuv run python examples/auth_api/start.py\n```"
        ).send()


@cl.on_chat_end
async def on_chat_end():
    """Clean up when chat ends."""
    toolset = cl.user_session.get("toolset")
    if toolset:
        await toolset.close()


@cl.on_message
async def on_message(message: cl.Message):
    """Handle incoming messages using ADK runner."""
    runner: Runner = cl.user_session.get("runner")
    session = cl.user_session.get("session")
    username = cl.user_session.get("username", "user")

    if not runner or not session:
        await cl.Message(
            content="Agent not initialized. Please refresh the page."
        ).send()
        return

    # Create response message for streaming
    response_msg = cl.Message(content="")
    await response_msg.send()

    collected_text = ""
    current_tool_step = None

    try:
        # Run the agent
        async for event in runner.run_async(
            user_id=username,
            session_id=session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=message.content)]
            ),
        ):
            if hasattr(event, "content") and event.content and event.content.parts:
                for part in event.content.parts:
                    # Handle text response
                    if hasattr(part, "text") and part.text:
                        collected_text += part.text
                        response_msg.content = collected_text
                        await response_msg.update()

                    # Handle function call
                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        # Create a step for the tool call
                        async with cl.Step(name=fc.name, type="tool") as step:
                            step.input = dict(fc.args) if fc.args else {}
                            # The actual tool execution happens inside ADK
                            # We just show it was called

                    # Handle function response (tool result)
                    if hasattr(part, "function_response") and part.function_response:
                        fr = part.function_response
                        # Update the tool step with result if we have one
                        # Note: ADK handles this internally, we just observe

        # Final update
        if collected_text:
            response_msg.content = collected_text
            await response_msg.update()

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        response_msg.content = f"Error: {e}\n\n```\n{error_details}\n```"
        await response_msg.update()


if __name__ == "__main__":
    from chainlit.cli import run_chainlit
    run_chainlit(__file__)
