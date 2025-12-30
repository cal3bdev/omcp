# MCP Client with Google ADK

A test client for interacting with OMCP-generated MCP servers using Google's Agent Development Kit (ADK).

## Features

- **Native MCP Support**: Uses ADK's built-in `McpToolset` for seamless MCP integration
- **Interactive CLI**: Chat with the agent from your terminal
- **Test Suite**: Automated testing with categorized prompts
- **Web UI**: Gradio-based web interface for interactive testing

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set your Gemini API key:
```bash
export GEMINI_API_KEY=your_key_here
# Or create a .env file
echo "GEMINI_API_KEY=your_key" > .env
```

3. Start your MCP server (e.g., from examples/large_api):
```bash
cd ../large_api
omcp serve --plan omcp.plan.json --modular
```

## Usage

### Interactive CLI

```bash
python agent.py
```

This starts an interactive session where you can chat with the agent.

### Run Test Suite

```bash
# Run all tests
python run_tests.py

# Run specific test suite
python run_tests.py --suite simple
python run_tests.py --suite medium
python run_tests.py --suite complex

# Custom MCP URL
python run_tests.py --url http://localhost:9000/sse

# Save results to JSON
python run_tests.py --output results.json

# Verbose output
python run_tests.py -v
```

### Web UI

```bash
python web_ui.py
```

Then open http://localhost:7860 in your browser.

## Files

- `agent.py` - Core agent implementation using ADK's McpToolset
- `prompts.py` - Test prompts organized by complexity
- `run_tests.py` - Automated test runner with rich output
- `web_ui.py` - Gradio web interface

## How It Works

The client uses Google ADK's native MCP support:

```python
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import SseConnectionParams

# Connect to MCP server via SSE
toolset = McpToolset(
    connection_params=SseConnectionParams(url="http://localhost:9000/sse"),
)

# Create agent with MCP tools
agent = LlmAgent(
    model="gemini-2.0-flash",
    tools=[toolset],
)
```

The ADK handles all MCP protocol communication, tool discovery, and execution automatically.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GEMINI_API_KEY` | - | Your Google Gemini API key |
| `MCP_URL` | `http://localhost:9000/sse` | MCP server SSE endpoint |

## Test Prompts

Prompts are organized into three complexity levels:

- **Simple**: Single-tool operations (list, get, check)
- **Medium**: Multi-step operations requiring 2-3 tools
- **Complex**: Workflows requiring coordination across multiple domains

See `prompts.py` for the full list.
