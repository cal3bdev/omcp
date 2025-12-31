"""
MCP Agent using Google ADK with native McpToolset.

This agent connects to an MCP server and uses its tools to answer queries.
Uses ADK's memory services for conversation persistence.
"""

import asyncio
import os
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.tools import load_memory
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.genai import types

load_dotenv()

# Shared services for memory persistence
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()


def create_mcp_agent(
    mcp_url: str = "http://localhost:9000/mcp",
    model: str = "gemini-3-flash-preview",
    name: str = "mcp_agent",
    instruction: str | None = None,
) -> tuple[LlmAgent, McpToolset]:
    """
    Create an agent connected to an MCP server.

    Args:
        mcp_url: Streamable HTTP endpoint URL of the MCP server
        model: Gemini model to use
        name: Agent name
        instruction: Custom system instruction

    Returns:
        Tuple of (agent, toolset) - toolset must be closed when done
    """
    # Create MCP toolset with Streamable HTTP connection
    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=mcp_url),
    )

    default_instruction = """You are a helpful assistant connected to an OMCP Hub that provides access to a large API organized into modules.

## Memory
You have access to conversation memory. Use the load_memory tool to recall information from earlier in the conversation if needed.

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
- Use load_memory to recall facts from earlier in the conversation

## Best Practices
- **Optional parameters**: When a parameter is optional, consider what the default might be. If unclear, specify it explicitly to avoid unexpected behavior (e.g., refund amount defaulting to 0)
- **Gather data first**: Before write operations (create, update, delete, refund), gather all needed data (amounts, IDs, details) so you can provide complete arguments
- **Learn tool patterns**: If you've seen similar tools (e.g., user_id as path param), you can skip schema lookup for obvious cases
- **Chain lookups**: When you only have a name, think: name → list entities → find ID → use ID for next operation"""

    agent = LlmAgent(
        model=model,
        name=name,
        instruction=instruction or default_instruction,
        tools=[toolset, load_memory],
    )

    return agent, toolset


class ConversationSession:
    """Maintains a persistent conversation session with ADK memory services."""

    APP_NAME = "mcp_client"
    USER_ID = "test_user"

    def __init__(self, mcp_url: str, model: str = "gemini-3-flash-preview"):
        self.mcp_url = mcp_url
        self.model = model
        self.agent = None
        self.toolset = None
        self.runner = None
        self.session = None
        self._initialized = False

    async def initialize(self) -> list[str]:
        """Initialize the agent and session. Returns list of available tools."""
        self.agent, self.toolset = create_mcp_agent(mcp_url=self.mcp_url, model=self.model)

        # Use Runner with shared session and memory services
        self.runner = Runner(
            agent=self.agent,
            app_name=self.APP_NAME,
            session_service=session_service,
            memory_service=memory_service,
        )

        self.session = await session_service.create_session(
            app_name=self.APP_NAME,
            user_id=self.USER_ID,
        )
        self._initialized = True

        # Get tool names
        tools = await self.toolset.get_tools()
        return [tool.name for tool in tools]

    async def send_message(self, query: str, verbose: bool = True) -> str:
        """Send a message and get response, maintaining conversation history."""
        if not self._initialized:
            raise RuntimeError("Session not initialized. Call initialize() first.")

        if verbose:
            print(f"\n{'='*60}")
            print(f"Query: {query}")
            print(f"{'='*60}")

        response_text = ""
        async for event in self.runner.run_async(
            user_id=self.USER_ID,
            session_id=self.session.id,
            new_message=types.Content(
                role="user",
                parts=[types.Part(text=query)]
            ),
        ):
            if verbose and hasattr(event, 'content'):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            print(f"Agent: {part.text}")
                            response_text += part.text

            # Check for function calls
            if verbose and hasattr(event, 'content'):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, 'function_call') and part.function_call:
                            fc = part.function_call
                            print(f"  → Calling tool: {fc.name}")
                            print(f"    Args: {fc.args}")

        return response_text

    async def close(self):
        """Clean up resources."""
        if self.toolset:
            await self.toolset.close()


async def run_query(
    query: str,
    mcp_url: str = "http://localhost:9000/mcp",
    verbose: bool = True,
) -> str:
    """
    Run a single query against the MCP agent (no memory between calls).

    For persistent conversations, use ConversationSession instead.
    """
    session = ConversationSession(mcp_url=mcp_url)
    try:
        await session.initialize()
        return await session.send_message(query, verbose=verbose)
    finally:
        await session.close()


async def list_tools(mcp_url: str = "http://localhost:9000/mcp") -> list[str]:
    """List all available tools from the MCP server."""
    toolset = McpToolset(
        connection_params=StreamableHTTPConnectionParams(url=mcp_url),
    )

    try:
        tools = await toolset.get_tools()
        return [tool.name for tool in tools]
    finally:
        await toolset.close()


async def main():
    """Interactive CLI for testing the MCP agent with conversation memory."""
    import sys

    mcp_url = os.getenv("MCP_URL", "http://localhost:9000/mcp")

    print("MCP Agent CLI (with conversation memory)")
    print(f"Connected to: {mcp_url}")
    print("-" * 40)

    # Create persistent session
    session = ConversationSession(mcp_url=mcp_url)

    try:
        tools = await session.initialize()
        print(f"Available tools ({len(tools)}):")
        for tool in tools[:10]:
            print(f"  - {tool}")
        if len(tools) > 10:
            print(f"  ... and {len(tools) - 10} more")
        print("-" * 40)
    except Exception as e:
        print(f"Error connecting to MCP server: {e}")
        print("Make sure the MCP server is running!")
        sys.exit(1)

    print("Enter queries (or 'quit' to exit):\n")

    try:
        while True:
            try:
                query = input("You: ").strip()
                if not query:
                    continue
                if query.lower() in ("quit", "exit", "q"):
                    break

                await session.send_message(query)
                print()

            except KeyboardInterrupt:
                print("\nGoodbye!")
                break
            except Exception as e:
                print(f"Error: {e}")
    finally:
        await session.close()


if __name__ == "__main__":
    asyncio.run(main())
