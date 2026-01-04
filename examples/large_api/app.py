"""Chainlit UI for the MegaStore E-Commerce API example using Google ADK.

A chat interface for managing the full e-commerce platform.

Usage:
    # First start the servers:
    uv run python examples/large_api/start.py

    # Then run the Chainlit app:
    uv run chainlit run examples/large_api/app.py
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
API_URL = os.getenv("API_URL", "http://localhost:8002")
MCP_URL = os.getenv("MCP_URL", "http://localhost:9000/mcp")

AGENT_INSTRUCTION = """You are a helpful assistant connected to an OMCP Hub that provides access to a large API organized into modules.

## Hub Meta-Tools (6 tools)
The hub uses a meta-tool pattern to avoid context bloat. You have these 6 tools:

### Discovery Tools
1. **list_modules()** - List all available modules with descriptions and tool counts
2. **list_module_tools(module_name)** - List all tools in a specific module
3. **find_tool(query)** - Search for tools by keyword across all modules
4. **get_tool_schema(module_name, tool_name)** - Get FULL parameter schema for a tool
5. **hub_status()** - Get hub statistics

### Execution Tool
6. **call_tool(module_name, tool_name, arguments)** - Execute ANY tool in any module

## Discovery Strategy (IMPORTANT!)

### When you need to find a capability:
1. **Search with simple keywords** - Use single nouns like "payment", "order", "user"
   - GOOD: find_tool("payment") → finds create_payment, list_payments, refund_payment
   - BAD: find_tool("record payment") → may miss tools named differently

2. **If search returns no results, explore modules:**
   - Call list_modules() to see all available modules
   - Look for a relevant module (e.g., "payment_processing")
   - Call list_module_tools(module_name) to see all tools in that module

3. **Try alternative terms** - If "record" doesn't work, try "create", "add", "new"

### For complex tasks:
Start with list_modules() to understand what's available, then drill down.

## Workflow: Discover → Understand → Execute

### Step 1: Discover
Use find_tool(query) with simple keywords:
```
find_tool("user") → Returns tools matching "user" with their module names
find_tool("payment") → Returns all payment-related tools
```

### Step 2: Understand (IMPORTANT!)
ALWAYS get the schema before calling a tool:
```
get_tool_schema("user_management", "list_users") → Returns parameters, types, required fields
```

### Step 3: Execute
Use call_tool with the correct arguments:
```
call_tool(
    module_name="user_management",
    tool_name="list_users",
    arguments={"limit": 10, "offset": 0}
)
```

## Example Interaction

User: "List all users"

1. find_tool(query="user")
   → Returns: [{"name": "list_users", "module": "user_management", ...}]

2. get_tool_schema(module_name="user_management", tool_name="list_users")
   → Returns: {"parameters": [{"name": "limit", "required": false}, ...]}

3. call_tool(module_name="user_management", tool_name="list_users", arguments={})
   → Returns the list of users

## Key Points
- NEVER call call_tool without first checking get_tool_schema for required arguments
- Search with SINGLE KEYWORDS for best results: "payment" not "make a payment"
- If find_tool returns nothing, use list_modules() then list_module_tools()
- NEVER assume a capability doesn't exist without checking list_modules()
- The arguments parameter in call_tool must be a dict matching the tool's schema
- All actual API work goes through call_tool - you cannot call API tools directly

## Best Practices
- **Optional parameters**: When a parameter is optional, consider what the default might be. If unclear, specify it explicitly to avoid unexpected behavior (e.g., refund amount defaulting to 0)
- **Gather data first**: Before write operations (create, update, delete, refund), gather all needed data (amounts, IDs, details) so you can provide complete arguments
- **Learn tool patterns**: If you've seen similar tools (e.g., user_id as path param), you can skip schema lookup for obvious cases
- **Chain lookups**: When you only have a name, think: name → list entities → find ID → use ID for next operation
"""


def create_agent(model: str = "gemini-3-flash-preview") -> tuple[LlmAgent, McpToolset]:
    """Create an ADK agent with MCP connection to the Hub."""
    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=MCP_URL),
    )

    agent = LlmAgent(
        model=model,
        name="megastore_agent",
        instruction=AGENT_INSTRUCTION,
        tools=[toolset],
    )

    return agent, toolset


@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session with ADK agent."""
    await cl.Message(
        content="Welcome to **MegaStore E-Commerce**! Setting up your agent..."
    ).send()

    try:
        agent, toolset = create_agent()

        tools = await toolset.get_tools()
        tool_count = len(tools)

        session_service = InMemorySessionService()
        runner = Runner(
            agent=agent,
            app_name="megastore_chainlit",
            session_service=session_service,
        )
        session = await session_service.create_session(
            app_name="megastore_chainlit",
            user_id="user",
        )

        cl.user_session.set("runner", runner)
        cl.user_session.set("session", session)
        cl.user_session.set("toolset", toolset)

        await cl.Message(
            content=f"Connected to OMCP Hub!\n\n"
            f"**{tool_count} tools available** across multiple modules.\n\n"
            f"Try asking:\n"
            f'- "Show me all products"\n'
            f'- "List users in the system"\n'
            f'- "What\'s in Alice\'s cart?" (use user_alice)\n'
            f'- "Show the sales dashboard"\n'
            f'- "List open support tickets"'
        ).send()

    except Exception as e:
        await cl.Message(
            content=f"Failed to connect to OMCP Hub: {e}\n\n"
            "Make sure the servers are running:\n"
            "```bash\nuv run python examples/large_api/start.py\n```"
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

    response_msg = cl.Message(content="")
    await response_msg.send()

    collected_text = ""

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
                    if hasattr(part, "text") and part.text:
                        collected_text += part.text
                        response_msg.content = collected_text
                        await response_msg.update()

                    if hasattr(part, "function_call") and part.function_call:
                        fc = part.function_call
                        async with cl.Step(name=fc.name, type="tool") as step:
                            step.input = dict(fc.args) if fc.args else {}

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
