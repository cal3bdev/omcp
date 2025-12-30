# OMCP - OpenAPI to MCP

Convert OpenAPI specifications into MCP (Model Context Protocol) servers for AI agents.

## Features

- 🔌 **Instant MCP servers** from any OpenAPI spec
- 🔐 **Multiple auth methods**: Bearer, API Key, OAuth2, None
- 🎯 **Endpoint filtering**: Include/exclude patterns to control exposed tools
- 🤖 **LLM-powered planning**: Auto-improve tool names and descriptions
- 📦 **Modular mode**: Split large APIs into micro-MCPs with a hub router

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/omcp.git
cd omcp

# Create virtual environment and install
python -m venv .venv
source .venv/bin/activate
uv pip install -e .
```

## Quick Start

1. Create an `omcp.yaml` configuration file:

```yaml
name: "My API"
spec: "./openapi.json"  # or URL: "https://api.example.com/openapi.json"
base_url: "https://api.example.com"

auth:
  type: bearer
  token: "${API_TOKEN}"

# Optional: Filter endpoints
endpoints:
  include: []  # Empty = include all
  exclude:
    - "* /internal/**"
    - "* /admin/**"
```

2. Run the server:

```bash
omcp serve
```

3. Add to Claude Desktop (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "my-api": {
      "command": "omcp",
      "args": ["serve", "-c", "/path/to/omcp.yaml"]
    }
  }
}
```

## Examples

### Demo API (Simple)

A simple task manager API for basic testing.

```bash
# Start the demo API server
cd examples/demo_api
python main.py  # Runs on http://127.0.0.1:8000

# In another terminal, run the MCP server
omcp serve -c examples/demo_api/omcp.yaml
```

### Messy API (Advanced Filtering & LLM Rewriting)

A more complex "Widget Store" API demonstrating:
- Endpoint filtering (exclude debug, admin, legacy routes)
- LLM-powered tool name and description improvements
- Module organization

```bash
# Start the messy API server
cd examples/messy_api
python main.py  # Runs on http://127.0.0.1:8001

# Run with basic filtering (no LLM)
omcp serve -c examples/messy_api/omcp.yaml

# Or generate an LLM-optimized plan first
export GEMINI_API_KEY="your-key"  # or OPENAI_API_KEY
omcp plan -c examples/messy_api/omcp_llm.yaml
omcp serve -c examples/messy_api/omcp_llm.yaml
```

**Example: Before/After LLM Rewriting**

| Original Name | LLM-Improved Name |
|---------------|-------------------|
| `get_widgets_widgets_get` | `list_widgets` |
| `adjust_stock_widgets__widget_id__stock_patch` | `adjust_widget_stock` |

| Original Description | LLM-Improved Description |
|---------------------|-------------------------|
| `"gets widgets from the database"` | `"Lists all widgets."` |
| `"change stock level"` | `"Adjusts the stock level of a specific widget by its ID."` |

## Endpoint Filtering

Control which API endpoints become MCP tools using include/exclude patterns:

```yaml
endpoints:
  # Include patterns (whitelist approach)
  include:
    - "GET /users"
    - "GET /users/*"
    - "POST /orders"
  
  # Exclude patterns (blacklist approach)
  exclude:
    - "* /debug/**"      # All methods under /debug
    - "* /internal/**"   # All internal routes
    - "* /admin/**"      # All admin routes
    - "DELETE *"         # All DELETE methods
    - "GET /health/detailed"  # Specific endpoint
```

**Pattern Syntax:**
- `METHOD /path` - Match specific method and path
- `* /path` - Match all methods for a path
- `METHOD *` - Match all paths for a method
- `/path/**` - Match path and all sub-paths
- `/path/*` - Match direct children only

## LLM Planner

Use an LLM to automatically improve tool names, descriptions, and organize into modules:

```yaml
llm:
  enabled: true
  provider: gemini  # or: openai, anthropic
  model: gemini-2.0-flash
  api_key: "${GEMINI_API_KEY}"
  
  strategy:
    max_tools_total: 50
    target_tools_per_module: 15
    naming:
      style: verb_noun
      max_name_length: 40
    policy:
      block_methods: []
      block_path_globs:
        - "/debug/**"
        - "/internal/**"
```

Generate a plan:

```bash
omcp plan -c omcp.yaml
# Creates omcp.plan.json with optimized tool definitions
```

**Note:** User-defined endpoint filters (`endpoints.exclude`) are applied **before** sending to the LLM. Your exclusions are the "hard rule" - the LLM only sees and processes the endpoints you've allowed.

## Authentication

### Bearer Token
```yaml
auth:
  type: bearer
  token: "${API_TOKEN}"
```

### API Key
```yaml
auth:
  type: api_key
  key: "${API_KEY}"
  header: "X-API-Key"  # or use 'query' param
```

### OAuth2
```yaml
auth:
  type: oauth2
  client_id: "${OAUTH_CLIENT_ID}"
  client_secret: "${OAUTH_CLIENT_SECRET}"
  auth_url: "https://auth.example.com/authorize"
  token_url: "https://auth.example.com/token"
  scopes: ["read", "write"]
```

Run the OAuth flow:
```bash
omcp auth -c omcp.yaml
```

### No Auth
```yaml
auth:
  type: none
```

## Commands

| Command | Description |
|---------|-------------|
| `omcp serve` | Run MCP server(s) based on configuration |
| `omcp plan` | Generate OMCP plan using LLM planner |
| `omcp list` | List available operations from the spec |
| `omcp auth` | Run OAuth2 authorization flow |

### Common Options

```bash
omcp serve -c config.yaml      # Specify config file
omcp plan -c config.yaml -o plan.json  # Custom output path
omcp list -c config.yaml --excluded    # Show excluded operations too
```

## Environment Variables

Create a `.env` file (see `.env.example`):

```bash
# LLM API Keys
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key

# API Authentication
API_TOKEN=your-api-token
API_KEY=your-api-key

# OAuth2
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
```

Reference in config with `${VAR_NAME}` syntax:

```yaml
auth:
  type: bearer
  token: "${API_TOKEN}"
```

## Configuration Reference

See [project.md](project.md) for full configuration schema.

## License

MIT
