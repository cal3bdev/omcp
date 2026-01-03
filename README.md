# OMCP

**Turn any REST API into an AI-ready tool interface in minutes.**

OMCP (OpenAPI to MCP) converts OpenAPI specifications into [Model Context Protocol](https://modelcontextprotocol.io/) servers, enabling AI agents like Claude, Gemini, and GPT to interact with your APIs through a standardized tool interface—no custom integration code required.

```
Your OpenAPI Spec  →  OMCP  →  AI Agent calls your API
```

---

## Why OMCP?

Building AI agents that interact with APIs is painful:

| The Hard Way | With OMCP |
|--------------|-----------|
| Write custom tool definitions for each endpoint | Point at your OpenAPI spec |
| Maintain tool code as API evolves | Spec changes auto-propagate |
| Handle auth, retries, error mapping manually | Built-in auth providers |
| Context window bloat with 100+ tools | Smart hub architecture |
| Agent struggles with poor tool names | LLM-powered name/description optimization |

**OMCP bridges the gap between your existing REST APIs and AI agents.**

---

## Key Features

### Instant MCP Servers
Drop in any OpenAPI 3.0 spec (JSON or YAML, file or URL) and get a working MCP server immediately.

### Smart Scaling for Large APIs
APIs with 100+ endpoints overwhelm AI context windows. OMCP's **modular hub architecture** splits large APIs into domain-specific micro-MCPs, exposing just 6 meta-tools to the agent while providing access to all underlying operations.

### LLM-Powered Optimization
Automatically improve cryptic auto-generated names like `get_widgets_widgets_get` into agent-friendly names like `list_widgets`. Let an LLM organize endpoints into logical modules and write clear descriptions.

### Production-Ready Auth
Bearer tokens, API keys, OAuth2 with PKCE—all built in. Environment variable substitution keeps secrets out of config files.

### Flexible Filtering
Include/exclude patterns let you expose exactly the endpoints you want. Block dangerous operations, hide internal routes, or whitelist specific functionality.

---

## Quick Start

### Installation

```bash
git clone https://github.com/anthropics/omcp.git
cd omcp
uv sync
```

### 1. Create a Config File

```yaml
# omcp.yaml
name: "My API"
spec: "./openapi.json"
base_url: "https://api.example.com"

auth:
  type: bearer
  token: "${API_TOKEN}"
```

### 2. Run the Server

```bash
export API_TOKEN="your-token"
uv run omcp serve
```

### 3. Connect Your AI Agent

**Claude Desktop** (`claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "my-api": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/omcp", "omcp", "serve", "-c", "/path/to/omcp.yaml"]
    }
  }
}
```

**Any MCP Client** (HTTP transport):
```
http://localhost:8000/mcp
```

That's it. Your AI agent can now call your API.

---

## Try the Demo

Run the full hub demo with a 100+ operation e-commerce API:

### Terminal 1: Start the Backend API
```bash
cd examples/large_api
uv run uvicorn main:app --host 127.0.0.1 --port 8002
```

### Terminal 2: Start the OMCP Hub
```bash
cd examples/large_api
uv run omcp serve -c omcp.yaml
```

You'll see the custom startup UI:
```
 ██████╗ ███╗   ███╗ ██████╗██████╗
██╔═══██╗████╗ ████║██╔════╝██╔══██╗
██║   ██║██╔████╔██║██║     ██████╔╝
...
╭─────────────── Configuration ───────────────╮
│       API  MegaStore E-Commerce             │
│      Mode  modular                          │
│ Transport  http                             │
╰─────────────────────────────────────────────╯
╭──────────────── Modules ────────────────────╮
│ user_management    │ http://127.0.0.1:9100  │
│ product_catalog    │ http://127.0.0.1:9101  │
│ order_management   │ http://127.0.0.1:9102  │
│ ...                │                        │
╰─────────────────────────────────────────────╯
╭─────────── ● All Services Ready ────────────╮
│ Hub  http://127.0.0.1:9000                  │
╰─────────────────────────────────────────────╯
```

### Terminal 3: Run the Agent CLI
```bash
uv run python examples/client/agent.py
```

### Example Conversation
```
You: Create a user John Doe with john@example.com

Agent: User John Doe has been created with ID `abc123`.

You: Add a MacBook Pro to his cart and checkout with his address

Agent: I've added the MacBook Pro 16" ($3,499.99) to John's cart
and completed checkout to his address. Order ID: `ord_456`.
```

See `examples/client/prompts.md` for more example scenarios.

---

## Architecture

### Single Mode (Small APIs)

For APIs with fewer than ~30 operations:

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  AI Agent   │  MCP    │    OMCP     │  HTTP   │  Your API   │
│  (Claude)   │ ──────► │   Server    │ ──────► │  (REST)     │
└─────────────┘         └─────────────┘         └─────────────┘
```

Each API operation becomes one MCP tool.

### Modular Mode (Large APIs)

For APIs with 30-500+ operations, the hub prevents context window bloat:

```
┌─────────────────────────────────────────────────────────────────┐
│                          AI Agent                                │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Sees only 6 meta-tools
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                        OMCP Hub                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  list_modules()     find_tool()      call_tool()          │  │
│  │  list_module_tools()  get_tool_schema()  hub_status()     │  │
│  └───────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ Routes to appropriate module
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
  ┌───────────┐       ┌───────────┐       ┌───────────┐
  │   Users   │       │  Orders   │       │ Payments  │
  │  Module   │       │  Module   │       │  Module   │
  │ (15 tools)│       │ (20 tools)│       │ (12 tools)│
  └─────┬─────┘       └─────┬─────┘       └─────┬─────┘
        └───────────────────┼───────────────────┘
                            ▼
                    ┌─────────────┐
                    │  Your API   │
                    └─────────────┘
```

The agent discovers tools through `find_tool()`, gets schemas via `get_tool_schema()`, and executes via `call_tool()`. Full API access with minimal context overhead.

---

## Real-World Performance

Tested with a 100+ operation e-commerce API (MegaStore) split into 16 modules:

### Agent Task Completion

| Task | Result | Agent Prompts Needed |
|------|--------|---------------------|
| List all users | Pass | 0 |
| Create new user | Pass | 0 |
| Check order status | Pass | 1 |
| Process payment | Pass | 0 |
| Issue refund | Pass | 0 |

### Agent Performance Score (Gemini 2.0 Flash)

| Metric | Score |
|--------|-------|
| Tool Discovery | 9/10 |
| Problem Solving | 9/10 |
| Autonomy | 9/10 |
| Self-Correction | 9/10 |
| **Overall** | **8.5/10** |

172/172 unit tests passing.

---

## Configuration

### Minimal (Single Mode)

```yaml
name: "My API"
spec: "./openapi.json"
base_url: "https://api.example.com"
auth:
  type: bearer
  token: "${API_TOKEN}"
```

### Full (Modular Mode with LLM)

```yaml
name: "Large API"
spec: "https://api.example.com/openapi.json"
base_url: "https://api.example.com"

mode: modular

auth:
  type: bearer
  token: "${API_TOKEN}"

# Endpoint filtering
endpoints:
  exclude:
    - "* /internal/**"
    - "* /admin/**"
    - "DELETE *"

# LLM-powered optimization
llm:
  enabled: true
  provider: gemini  # or: openai, anthropic
  model: gemini-2.0-flash
  api_key: "${GEMINI_API_KEY}"
  strategy:
    max_tools_total: 200
    target_tools_per_module: 40
    naming:
      style: verb_noun
      max_name_length: 40

# Module configuration
modules:
  enabled: true
  split_strategy: llm
  runtime:
    base_port: 9100
    host: "127.0.0.1"

# Hub configuration
hub:
  enabled: true
  port: 9000
  transport: http
```

---

## LLM-Powered Planning

OMCP can use an LLM to dramatically improve the agent experience:

### Before/After Tool Names

| Auto-Generated | LLM-Optimized |
|----------------|---------------|
| `get_widgets_widgets_get` | `list_widgets` |
| `post_users_users_post` | `create_user` |
| `adjust_stock_widgets__widget_id__stock_patch` | `adjust_widget_stock` |

### Before/After Descriptions

| Original | LLM-Optimized |
|----------|---------------|
| `"gets widgets from the database"` | `"Retrieves all widgets with optional filtering by status and category."` |
| `"change stock level"` | `"Adjusts the stock level of a specific widget. Requires widget ID and new quantity."` |

### Generate a Plan

```bash
# Set your LLM API key
export GEMINI_API_KEY="your-key"

# Generate optimized plan
uv run omcp plan -c omcp.yaml

# Plan saved to omcp.plan.json
# Now serve with the optimized names/descriptions
uv run omcp serve -c omcp.yaml
```

---

## Endpoint Filtering

Control exactly which endpoints become MCP tools:

```yaml
endpoints:
  # Whitelist approach
  include:
    - "GET /users"
    - "GET /users/*"
    - "POST /orders"

  # Blacklist approach
  exclude:
    - "* /debug/**"       # All methods under /debug
    - "* /internal/**"    # All internal routes
    - "DELETE *"          # All DELETE methods
    - "GET /health/detailed"  # Specific endpoint
```

**Pattern Syntax:**
- `METHOD /path` - Specific method and path
- `* /path` - All methods for a path
- `METHOD *` - All paths for a method
- `/path/**` - Path and all sub-paths
- `/path/*` - Direct children only

Filters are applied **before** LLM processing—your exclusions are the hard rule.

---

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
  header_name: "X-API-Key"
```

### OAuth2
```yaml
auth:
  type: oauth2
  client_id: "${CLIENT_ID}"
  client_secret: "${CLIENT_SECRET}"
  auth_url: "https://auth.example.com/authorize"
  token_url: "https://auth.example.com/token"
  scopes: ["read", "write"]
```

Run the OAuth flow:
```bash
uv run omcp auth -c omcp.yaml
```

### No Auth
```yaml
auth:
  type: none
```

---

## Hub Meta-Tools Reference

When using modular mode, the hub exposes these 6 tools to agents:

| Tool | Purpose |
|------|---------|
| `list_modules()` | List all modules with descriptions and tool counts |
| `list_module_tools(module_name)` | List tools in a specific module |
| `find_tool(query)` | Search for tools by keyword across all modules |
| `get_tool_schema(module_name, tool_name)` | Get full parameter schema for a tool |
| `hub_status()` | Get hub statistics |
| `call_tool(module_name, tool_name, arguments)` | Execute any tool in any module |

### Agent Workflow

```
1. find_tool("payment")           → Discover relevant tools
2. get_tool_schema("payments",    → Understand required parameters
     "process_payment")
3. call_tool("payments",          → Execute with correct arguments
     "process_payment",
     {"order_id": "123", "amount": 99.99})
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `omcp serve` | Run MCP server(s) |
| `omcp plan` | Generate LLM-optimized plan |
| `omcp list` | List operations from spec |
| `omcp auth` | Run OAuth2 flow |

```bash
# Common usage
uv run omcp serve -c config.yaml
uv run omcp plan -c config.yaml
uv run omcp list -c config.yaml --excluded  # Show filtered ops too
```

---

## Environment Variables

Create a `.env` file:

```bash
# API Authentication
API_TOKEN=your-api-token

# LLM Providers (for planning)
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key

# OAuth2
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
```

Reference in config: `${VAR_NAME}`

---

## Project Structure

```
src/omcp/
├── auth/           # Auth providers (bearer, api_key, oauth2)
├── config/         # Configuration models (Pydantic)
├── hub/            # Hub server (meta-tool pattern)
├── modules/        # Module splitting and building
├── planner/        # LLM-powered planning
├── server/         # Single server mode
├── spec/           # OpenAPI parsing and normalization
└── cli.py          # Typer CLI

examples/
├── demo_api/       # Simple test API
├── large_api/      # 100+ operation test API
└── messy_api/      # Filtering/LLM demo API
```

---

## Roadmap

See [STATUS.md](STATUS.md) for current capabilities and test results.

**Planned improvements:**
- Dynamic per-request authentication (multi-tenant support)
- Semantic search for tool discovery
- Response streaming for long operations
- Multi-API hub (connect multiple different APIs)
- Persistent conversation memory
- Metrics and observability

---

## How It Works

1. **Load**: OMCP loads your OpenAPI spec (file or URL)
2. **Normalize**: Spec is normalized and validated
3. **Plan** (optional): LLM analyzes and optimizes tool names/descriptions/modules
4. **Build**: FastMCP servers are generated from the spec
5. **Serve**: MCP server(s) run via stdio, SSE, or HTTP transport
6. **Execute**: Agent tool calls are translated to HTTP requests with proper auth

The plan is validated deterministically—LLM suggestions are checked against the actual spec to prevent hallucinated operations.

---

## Contributing

```bash
# Install dev dependencies
uv sync

# Run tests
uv run pytest

# Run specific test
uv run pytest tests/test_planner.py -v
```

---

## License

MIT

---

## Links

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [FastMCP](https://github.com/jlowin/fastmcp)
- [OpenAPI Specification](https://spec.openapis.org/oas/latest.html)
