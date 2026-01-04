"""Chainlit UI for the Task Manager API example using Google ADK.

A chat interface for managing tasks and notes.

Usage:
    # First start the servers:
    uv run python examples/demo_api/start.py

    # Then run the Chainlit app:
    uv run chainlit run examples/demo_api/app.py
"""

from __future__ import annotations

import os

import chainlit as cl
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
API_URL = os.getenv("API_URL", "http://localhost:8000")
MCP_URL = os.getenv("MCP_URL", "http://localhost:9000/mcp")

AGENT_INSTRUCTION = """You are a helpful task management assistant connected to a Task Manager API via OMCP.

## Available Tools
- **list_tasks** - List all tasks (can filter by completed, priority)
- **create_task** - Create a new task (title required, optional: description, priority, due_date)
- **get_task** - Get a specific task by ID
- **update_task** - Update a task's fields
- **delete_task** - Delete a task
- **complete_task** - Mark a task as completed
- **list_notes** - List all notes (can filter by task_id)
- **create_note** - Create a new note (content required, optional: task_id)
- **get_note** - Get a specific note by ID
- **delete_note** - Delete a note
- **get_stats** - Get statistics about tasks and notes
- **health_check** - Check API health

## Guidelines
1. Be helpful and concise
2. When creating tasks, ask for title if not provided
3. Use appropriate priority levels: low, medium, high
4. Format due dates as YYYY-MM-DD
"""


def create_agent(model: str = "gemini-2.0-flash") -> tuple[LlmAgent, McpToolset]:
    """Create an ADK agent with MCP connection."""
    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=MCP_URL),
    )

    agent = LlmAgent(
        model=model,
        name="task_manager_agent",
        instruction=AGENT_INSTRUCTION,
        tools=[toolset],
    )

    return agent, toolset


@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session with ADK agent."""
    await cl.Message(
        content="Welcome to **Task Manager**! Setting up your agent..."
    ).send()

    try:
        agent, toolset = create_agent()

        # Get available tools
        tools = await toolset.get_tools()
        tool_names = ", ".join(f"`{t.name}`" for t in tools)

        # Create session service and runner
        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="task_manager_chainlit",
            session_service=session_service,
        )
        session = await session_service.create_session(
            app_name="task_manager_chainlit",
            user_id="user",
        )

        # Store in user session
        cl.user_session.set("runner", runner)
        cl.user_session.set("session", session)
        cl.user_session.set("toolset", toolset)

        await cl.Message(
            content=f"Connected to OMCP!\n\n"
            f"**Available tools:** {tool_names}\n\n"
            f"Try asking:\n"
            f'- "What tasks do I have?"\n'
            f'- "Create a task to buy groceries"\n'
            f'- "Show me the stats"\n'
            f'- "Add a high priority task for meeting prep due 2024-12-31"'
        ).send()

    except Exception as e:
        await cl.Message(
            content=f"Failed to connect to OMCP: {e}\n\n"
            "Make sure the servers are running:\n"
            "```bash\nuv run python examples/demo_api/start.py\n```"
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

    if not runner or not session:
        await cl.Message(
            content="Agent not initialized. Please refresh the page."
        ).send()
        return

    # Create response message for streaming
    response_msg = cl.Message(content="")
    await response_msg.send()

    collected_text = ""

    try:
        # Run the agent
        async for event in runner.run_async(
            user_id="user",
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
                        async with cl.Step(name=fc.name, type="tool") as step:
                            step.input = dict(fc.args) if fc.args else {}

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
