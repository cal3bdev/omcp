"""Chainlit UI for the Widget Store API example using Google ADK.

A chat interface for managing widgets, orders, and reviews.

Usage:
    # First start the servers:
    uv run python examples/messy_api/start.py

    # Then run the Chainlit app:
    uv run chainlit run examples/messy_api/app.py
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
API_URL = os.getenv("API_URL", "http://localhost:8001")
MCP_URL = os.getenv("MCP_URL", "http://localhost:9000/mcp")

AGENT_INSTRUCTION = """You are a helpful assistant for the Acme Widget Store, connected via OMCP.

## Available Tools (Widgets, Orders, Reviews)

### Widgets
- **get_widgets** - List widgets (filter: category, min_price, max_price, in_stock)
- **create_widget** - Create a widget (name, price required; optional: category, stock)
- **get_widget** - Get widget by ID
- **update_widget** - Update a widget
- **delete_widget** - Delete a widget
- **adjust_stock** - Change stock level (delta: +/- amount)

### Orders
- **list_orders** - List orders (filter: status)
- **create_order** - Create order (widget_id, quantity, shipping_address)
- **get_order** - Get order by ID
- **cancel_order** - Cancel a pending order

### Reviews
- **get_reviews** - List reviews (filter: widget_id)
- **create_review** - Add review (widget_id, rating 1-5, optional comment)

### Utility
- **health_check** - Check API health

## Guidelines
1. Be helpful and concise
2. Widgets have: id, name, price, category, stock
3. Orders have: id, widget_id, quantity, shipping_address, status, total
4. Reviews have: id, widget_id, rating, comment
"""


def create_agent(model: str = "gemini-2.0-flash") -> tuple[LlmAgent, McpToolset]:
    """Create an ADK agent with MCP connection."""
    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=MCP_URL),
    )

    agent = LlmAgent(
        model=model,
        name="widget_store_agent",
        instruction=AGENT_INSTRUCTION,
        tools=[toolset],
    )

    return agent, toolset


@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session with ADK agent."""
    await cl.Message(
        content="Welcome to **Acme Widget Store**! Setting up your agent..."
    ).send()

    try:
        agent, toolset = create_agent()

        tools = await toolset.get_tools()
        tool_names = ", ".join(f"`{t.name}`" for t in tools)

        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="widget_store_chainlit",
            session_service=session_service,
        )
        session = await session_service.create_session(
            app_name="widget_store_chainlit",
            user_id="user",
        )

        cl.user_session.set("runner", runner)
        cl.user_session.set("session", session)
        cl.user_session.set("toolset", toolset)

        await cl.Message(
            content=f"Connected to OMCP!\n\n"
            f"**Available tools:** {tool_names}\n\n"
            f"Try asking:\n"
            f'- "Show me all widgets"\n'
            f'- "Create a widget called Super Gadget for $29.99"\n'
            f'- "Place an order for widget xyz"\n'
            f'- "Leave a 5-star review for widget abc"'
        ).send()

    except Exception as e:
        await cl.Message(
            content=f"Failed to connect to OMCP: {e}\n\n"
            "Make sure the servers are running:\n"
            "```bash\nuv run python examples/messy_api/start.py\n```"
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

    collected_text = ""
    tool_steps: dict[str, cl.Step] = {}  # Track steps by function name

    try:
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
                    # Collect text (don't display yet - show after tool calls)
                    if hasattr(part, "text") and part.text:
                        collected_text += part.text

                    # Handle function call - create step and track it
                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        step = cl.Step(name=fc.name, type="tool")
                        step.input = dict(fc.args) if fc.args else {}
                        await step.send()
                        tool_steps[fc.name] = step

                    # Handle function response - update the step with output
                    if hasattr(part, "function_response") and part.function_response:
                        fr = part.function_response
                        if fr.name in tool_steps:
                            step = tool_steps[fr.name]
                            if fr.response:
                                # Set output as dict for nice rendering (like input)
                                step.output = fr.response
                            await step.update()

        # Send final response after all tool calls complete
        if collected_text:
            await cl.Message(content=collected_text).send()

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        await cl.Message(content=f"Error: {e}\n\n```\n{error_details}\n```").send()


if __name__ == "__main__":
    from chainlit.cli import run_chainlit
    run_chainlit(__file__)
