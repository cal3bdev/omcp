"""
MCP Agent using Google ADK with native McpToolset.

This agent connects to an MCP server and uses its tools to answer queries.
"""

import asyncio
import os
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams
from google.genai import types

load_dotenv()


def create_mcp_agent(
    mcp_url: str = "http://localhost:9000/mcp",
    model: str = "gemini-2.0-flash",
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

## Workflow: Discover → Understand → Execute

### Step 1: Discover
Use find_tool(query) to search for relevant tools:
```
find_tool("user") → Returns tools matching "user" with their module names
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
- find_tool does partial matching: "order" matches "list_orders", "get_order", "create_order"
- The arguments parameter in call_tool must be a dict matching the tool's schema
- All actual API work goes through call_tool - you cannot call API tools directly"""

    agent = LlmAgent(
        model=model,
        name=name,
        instruction=instruction or default_instruction,
        tools=[toolset],
    )
    
    return agent, toolset


async def run_query(
    query: str,
    mcp_url: str = "http://localhost:9000/mcp",
    verbose: bool = True,
) -> str:
    """
    Run a single query against the MCP agent.
    
    Args:
        query: The user query to process
        mcp_url: MCP server streamable HTTP endpoint
        verbose: Whether to print progress
    
    Returns:
        The agent's response
    """
    agent, toolset = create_mcp_agent(mcp_url=mcp_url)
    
    try:
        runner = InMemoryRunner(agent=agent, app_name="mcp_client")
        
        if verbose:
            print(f"\n{'='*60}")
            print(f"Query: {query}")
            print(f"{'='*60}")
        
        # Create a session and run the query
        session = await runner.session_service.create_session(
            app_name="mcp_client",
            user_id="test_user",
        )
        
        response_text = ""
        async for event in runner.run_async(
            user_id="test_user",
            session_id=session.id,
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
        
    finally:
        await toolset.close()


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
    """Interactive CLI for testing the MCP agent."""
    import sys
    
    mcp_url = os.getenv("MCP_URL", "http://localhost:9000/mcp")
    
    print(f"MCP Agent CLI")
    print(f"Connected to: {mcp_url}")
    print("-" * 40)
    
    # List available tools
    try:
        tools = await list_tools(mcp_url)
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
    
    while True:
        try:
            query = input("You: ").strip()
            if not query:
                continue
            if query.lower() in ("quit", "exit", "q"):
                break
            
            await run_query(query, mcp_url=mcp_url)
            print()
            
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
