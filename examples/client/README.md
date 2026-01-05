# MCP Client Examples

This directory contains client implementations for interacting with OMCP servers using Google ADK (Agent Development Kit).

## Overview

Two client implementations are provided:

| Client | Interface | Use Case |
|--------|-----------|----------|
| `agent.py` | Terminal CLI | Testing, automation, scripting |
| `web_ui.py` | Gradio Web UI | Interactive exploration, demos |

## Architecture

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────┐
│  Client (ADK)   │────▶│     OMCP     │────▶│  REST API   │
│  Gemini + MCP   │     │    Server    │     │  (Backend)  │
└─────────────────┘     └──────────────┘     └─────────────┘
```

## Requirements

```bash
pip install google-adk gradio rich python-dotenv
```

Or use the requirements file:

```bash
pip install -r requirements.txt
```

## Environment Variables

```bash
# Required: Google API key for Gemini
export GOOGLE_API_KEY="your-gemini-api-key"

# Optional: Custom MCP server URL (default: http://localhost:9000/mcp)
export MCP_URL="http://localhost:9000/mcp"
```

---

## Terminal Agent (`agent.py`)

An interactive CLI agent with conversation memory that connects to OMCP servers.

### Features

- **Conversation Memory**: Uses ADK's `InMemorySessionService` and `InMemoryMemoryService` for multi-turn conversations
- **MCP Toolset Integration**: Leverages `McpToolset` with Streamable HTTP connection
- **Hub Discovery Workflow**: Built-in system prompt for the discover → understand → execute pattern
- **Rich Output**: Shows tool calls and arguments as they execute

### Quick Start

```bash
# Start any OMCP server (e.g., large_api example)
uv run python examples/large_api/start.py

# In another terminal, run the agent
uv run python examples/client/agent.py
```

### Programmatic Usage

```python
from agent import ConversationSession, run_query, list_tools

# One-off query (no memory)
response = await run_query("List all users")

# Persistent conversation session
session = ConversationSession(mcp_url="http://localhost:9000/mcp")
await session.initialize()

# Multi-turn conversation with memory
await session.send_message("What products do you have?")
await session.send_message("Show me the cheapest one")  # Remembers context
await session.send_message("Add it to my cart")

await session.close()
```

### Hub Meta-Tool Workflow

The agent is pre-configured with instructions for the OMCP Hub's meta-tool pattern:

1. **Discover**: `find_tool("payment")` or `list_modules()`
2. **Understand**: `get_tool_schema("payments", "create_payment")`
3. **Execute**: `call_tool("payments", "create_payment", {"amount": 100})`

---

## Web UI (`web_ui.py`)

A Gradio-based chat interface for interactive MCP exploration.

### Features

- **Real-time Chat**: Streaming responses with tool call indicators
- **Tool Discovery**: "List Tools" button to explore available MCP tools
- **Session Management**: Clear chat or reset entire session
- **Example Prompts**: Quick-start buttons for common queries

### Quick Start

```bash
# Start any OMCP server
uv run python examples/demo_api/start.py

# Launch the web UI
uv run python examples/client/web_ui.py

# Open http://localhost:7860 in your browser
```

### Interface

- **MCP Server URL**: Configure which OMCP server to connect to
- **List Tools**: Discover available tools before chatting
- **Chat Input**: Natural language queries
- **Example Buttons**: Pre-filled prompts for common tasks

---

## Example Prompts

See [prompts.md](./prompts.md) for a comprehensive list of example prompts organized by complexity:

- **Simple Queries**: Single-module operations
- **Multi-Module Queries**: Cross-module operations (2-3 modules)
- **Complex Scenarios**: Full workflows (4+ modules)
- **Conversational Turns**: Multi-turn context-aware queries

### Quick Examples

```
# Simple
List all users in the system
Show me all products under $100

# Multi-module
What has Alice Johnson ordered in the past?
What's the status of order ord_003 including payment and shipping?

# Complex
Carol has a support ticket about her delayed order. Look up her ticket,
check her order status, and give me a full summary.
```

---

## Supported OMCP Modes

These clients work with both OMCP server modes:

### Single Mode (Direct Tools)

```
┌────────┐     ┌───────────────┐
│ Client │────▶│ OMCP (Single) │
└────────┘     │ 15 tools      │
               └───────────────┘
```

Tools are exposed directly (e.g., `list_users`, `create_order`).

### Modular Mode (Hub Meta-Tools)

```
┌────────┐     ┌───────────────┐     ┌─────────────────┐
│ Client │────▶│  OMCP (Hub)   │────▶│ Module Servers  │
└────────┘     │ 6 meta-tools  │     │ (micro-MCPs)    │
               └───────────────┘     └─────────────────┘
```

Uses meta-tools: `list_modules`, `find_tool`, `get_tool_schema`, `call_tool`, etc.

---

## Troubleshooting

### Connection Errors

```bash
# Make sure the OMCP server is running
curl http://localhost:9000/mcp

# Check the MCP_URL environment variable
echo $MCP_URL
```

### API Key Issues

```bash
# Verify your Google API key is set
echo $GOOGLE_API_KEY

# Test with a simple Gemini call
python -c "from google.genai import Client; Client().models.list()"
```

### Tool Discovery Fails

```bash
# List tools directly from the MCP server
python -c "
from agent import list_tools
import asyncio
print(asyncio.run(list_tools()))
"
```
