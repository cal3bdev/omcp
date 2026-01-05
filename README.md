# OMCP

**Give AI agents access to your API in minutes, not weeks.**

OMCP converts your OpenAPI spec into a [Model Context Protocol](https://modelcontextprotocol.io/) server. Point it at your spec, run one command, and AI agents can call your API.

```
Your OpenAPI Spec  →  OMCP  →  AI agents call your API
```

No tool definitions to write. No integration code to maintain. Just your spec and one config file.

---

## The Problem

You have an API. You want AI agents to use it. Your options today:

| Approach | Pain |
|----------|------|
| Write tool definitions manually | Tedious, error-prone, falls out of sync with your API |
| Use an agent framework | Still have to map every endpoint, handle auth, manage context limits |
| Build from scratch | Weeks of integration work for each API |

**With OMCP:** Point at your OpenAPI spec. Run `omcp serve`. Done.

---

## Quick Start

### Installation

```bash
git clone https://github.com/cal3bdev/omcp.git
cd omcp
uv sync
```

### Minimal Setup

```yaml
# omcp.yaml
name: "My API"
spec: "./openapi.json"
base_url: "https://api.example.com"

auth:
  type: bearer
  token: "${API_TOKEN}"
```

```bash
export API_TOKEN="your-token"
uv run omcp serve
```

**That's it.** Your AI agent can now call your API.

### Connect to Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "my-api": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/omcp", "omcp", "serve"]
    }
  }
}
```

---

## Who Is This For

OMCP is for developers who already have an API and want AI agents to use it:

| You Are | Your Goal | Why OMCP |
|---------|-----------|----------|
| **SaaS developer** | Add AI chat to your product | Uses your existing API, zero new backend code |
| **Platform engineer** | Build internal AI tooling | Hub architecture handles 100+ endpoints |
| **Startup founder** | Ship AI features fast | Minutes to integrate, not weeks |
| **Enterprise team** | AI layer on existing systems | Works with your existing auth |

**If you have an API and an OpenAPI spec, OMCP gets you to "AI-ready" in minutes.**

---

## Why OMCP

| Without OMCP | With OMCP |
|--------------|-----------|
| Write tool definitions for every endpoint | Point at your OpenAPI spec |
| Maintain tool code as your API evolves | Changes auto-propagate from spec |
| Handle auth, errors, retries manually | Built-in auth providers |
| 100+ tools overwhelm agent context | Hub architecture scales to any size |
| Agents struggle with cryptic auto-generated names | LLM optimizes names and descriptions |
| Build separate integration for each agent platform | MCP works with Claude, GPT, Gemini, and more |

---

## Key Features

### 🚀 Zero-Code Tool Generation

Your OpenAPI spec is the source of truth. OMCP reads it and generates MCP tools automatically:

```yaml
# This is your entire configuration
name: "My API"
spec: "./openapi.json"
base_url: "https://api.example.com"
```

Every endpoint becomes a tool. Schemas become parameters. Descriptions become tool documentation.

### 🔐 Multi-Tenant Ready

One OMCP server handles unlimited users. Each request carries its own token:

```
User A (their JWT) ──┐
                     ├──►  OMCP  ──►  Your API
User B (their JWT) ──┘
```

OMCP validates and forwards. Your API handles authorization exactly as it does today. No credential storage. No session management. No changes to your auth system.

```yaml
# Dynamic auth: each user provides their own token
auth:
  type: jwt
  validation:
    enabled: true
    jwks_url: "https://auth.example.com/.well-known/jwks.json"
```

### 📈 Scales to Any API Size

OMCP adapts to your API's complexity:

| API Size | Mode | How It Works |
|----------|------|--------------|
| Small (<30 ops) | `single` | One MCP server, all tools exposed directly |
| Medium (30-100 ops) | `modular` | Split into domain-specific micro-MCPs |
| Large (100+ ops) | `modular` + Hub | Micro-MCPs behind a hub with 6 meta-tools |

The hub prevents context window bloat by exposing discovery tools instead of hundreds of individual tools.

### 🧠 LLM-Powered Optimization

OMCP uses an LLM to transform cryptic auto-generated names into agent-friendly tools:

| Auto-Generated | LLM-Optimized |
|----------------|---------------|
| `get_widgets_widgets_get` | `list_widgets` |
| `post_users_users_post` | `create_user` |
| `adjust_stock_widgets__widget_id__stock_patch` | `adjust_widget_stock` |

Every suggestion is validated against your actual spec. No hallucinated endpoints.

---

## Architecture

### Single Mode

For smaller APIs, each operation becomes one MCP tool:

```
┌─────────────┐         ┌─────────────┐         ┌─────────────┐
│  AI Agent   │   MCP   │    OMCP     │  HTTP   │  Your API   │
│  (Claude)   │ ──────► │   Server    │ ──────► │  (REST)     │
└─────────────┘         └─────────────┘         └─────────────┘
```

### Modular Mode with Hub

For large APIs, the hub exposes 6 meta-tools while providing access to all underlying operations:

```
┌─────────────────────────────────────────────────────────────────┐
│                          AI Agent                               │
│                   (sees only 6 meta-tools)                      │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                          OMCP Hub                               │
│   ┌─────────────────────────────────────────────────────────┐   │
│   │  list_modules   find_tool      call_tool                │   │
│   │  list_tools     get_schema     hub_status               │   │
│   └─────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬─────────────────────────────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          ▼                     ▼                     ▼
    ┌───────────┐         ┌───────────┐         ┌───────────┐
    │   Users   │         │  Orders   │         │ Payments  │
    │  Module   │         │  Module   │         │  Module   │
    │ (15 tools)│         │ (20 tools)│         │ (12 tools)│
    └───────────┘         └───────────┘         └───────────┘
          │                     │                     │
          └─────────────────────┼─────────────────────┘
                                ▼
                        ┌─────────────┐
                        │  Your API   │
                        └─────────────┘
```

**Agent workflow:**

```python
# 1. Discover what's available
find_tool("payment")              # → Shows payment-related tools

# 2. Understand parameters  
get_tool_schema("payments",       # → Full JSON schema
                "process_payment")

# 3. Execute
call_tool("payments",             # → Processes the payment
          "process_payment", 
          {"order_id": "123"})
```

---

## Examples

### Demo API (Getting Started)

Basic example with a small API:

```bash
# Terminal 1: Start the demo API
uv run python examples/demo_api/start.py

# Terminal 2: OMCP serves at http://localhost:9000
```

### MegaStore (Large API + Hub)

100+ endpoint e-commerce API demonstrating modular mode with LLM planning:

```bash
# Start everything with web UI
uv run python examples/large_api/start.py --ui

# Open http://localhost:8000
```

**Features:**
- 100+ endpoints split into ~10 domain modules
- LLM-generated module organization
- Hub meta-tool pattern
- Chainlit web UI with tool visualization

### Notes API (Multi-Tenant Authentication)

Multi-tenant example where each user authenticates with their own JWT:

```bash
# Start with web UI
uv run python examples/auth_api/start.py --ui

# Open http://localhost:8000
# Switch between users: Alice (admin), Bob, Charlie
```

**Features:**
- Per-request JWT authentication
- User isolation (each user sees only their data)
- Role-based access control
- Passthrough mode (OMCP forwards tokens, API validates)

---

## Authentication

### Static Auth (Server-Wide)

For APIs where OMCP uses a single credential:

```yaml
# Bearer token
auth:
  type: bearer
  token: "${API_TOKEN}"

# API key
auth:
  type: api_key
  key: "${API_KEY}"
  header_name: "X-API-Key"

# OAuth2 with PKCE
auth:
  type: oauth2
  client_id: "${CLIENT_ID}"
  client_secret: "${CLIENT_SECRET}"
  auth_url: "https://auth.example.com/authorize"
  token_url: "https://auth.example.com/token"
  scopes: ["read", "write"]
```

Run OAuth2 flow: `uv run omcp auth`

### Dynamic Auth (Per-Request JWT)

For multi-tenant scenarios where each client provides their own token:

```yaml
auth:
  type: jwt
  validation:
    enabled: false  # Passthrough: your API validates
    
  # OR validate in OMCP first:
  validation:
    enabled: true
    jwks_url: "https://auth.example.com/.well-known/jwks.json"
    issuer: "https://auth.example.com"
    audience: "my-api"
```

**How it works:**

1. Client sends request with `Authorization: Bearer <user-token>`
2. OMCP extracts token (optionally validates via JWKS)
3. OMCP forwards token to your API
4. Your API authorizes the user as it always does
5. User gets only their data

**No credential storage. No changes to your API. Just works.**

---

## Endpoint Filtering

Control exactly which endpoints become MCP tools:

```yaml
endpoints:
  # Exclude dangerous or internal routes
  exclude:
    - "DELETE *"          # All DELETE methods
    - "* /internal/**"    # All internal routes
    - "* /admin/**"       # All admin routes
    - "GET /health"       # Specific endpoint

  # Or whitelist specific endpoints
  include:
    - "GET /users/*"
    - "POST /orders"
```

**Pattern syntax:**
- `METHOD /path` — Specific method and path
- `* /path` — All methods for a path
- `METHOD *` — All paths for a method
- `/path/**` — Path and all sub-paths

Filters are applied **before** LLM processing—your exclusions are enforced absolutely.

---

## LLM-Powered Planning

Generate optimized tool names and module organization:

```bash
# Set your LLM API key
export GEMINI_API_KEY="your-key"

# Generate optimized plan
uv run omcp plan

# Serve with optimized names
uv run omcp serve
```

The plan is saved to `omcp.plan.json` and validated against your spec:
- ✅ Every tool maps to a real operation
- ✅ No hallucinated endpoints
- ✅ Module groupings make semantic sense
- ✅ Safety policies are enforced

---

## Configuration Reference

See [`example.omcp.yaml`](example.omcp.yaml) for a complete reference with all options documented.

### Minimal

```yaml
name: "My API"
spec: "./openapi.json"
base_url: "https://api.example.com"

auth:
  type: bearer
  token: "${API_TOKEN}"
```

### Full

```yaml
name: "Large API"
spec: "https://api.example.com/openapi.json"
base_url: "https://api.example.com"

mode: modular  # single | modular

auth:
  type: bearer
  token: "${API_TOKEN}"

# Endpoint filtering
endpoints:
  exclude:
    - "* /internal/**"
    - "DELETE *"

# LLM planner
llm:
  enabled: true
  provider: gemini  # openai | anthropic | gemini
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
  split_strategy: llm  # llm | tags | path
  runtime:
    base_port: 9100
    host: "127.0.0.1"

# Hub configuration
hub:
  enabled: true
  port: 9000
  transport: http  # http | sse | stdio
```

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `omcp serve` | Run MCP server(s) |
| `omcp plan` | Generate LLM-optimized plan |
| `omcp list` | List operations from spec |
| `omcp auth` | Run OAuth2 authorization flow |

```bash
uv run omcp serve -c config.yaml
uv run omcp plan -c config.yaml
uv run omcp list -c config.yaml --excluded
uv run omcp list -c config.yaml --by-module
```

---

## Hub Meta-Tools Reference

When using modular mode with hub enabled:

| Tool | Purpose |
|------|---------|
| `list_modules()` | List all modules with descriptions and tool counts |
| `list_module_tools(module)` | List tools in a specific module |
| `find_tool(query)` | Search for tools by keyword across all modules |
| `get_tool_schema(module, tool)` | Get full parameter schema for a tool |
| `call_tool(module, tool, args)` | Execute any tool in any module |
| `hub_status()` | Get hub statistics |

---

## Environment Variables

Reference in config with `${VAR_NAME}`:

```bash
# API Authentication
API_TOKEN=your-api-token

# LLM Providers (choose one)
GEMINI_API_KEY=your-gemini-key
OPENAI_API_KEY=your-openai-key
ANTHROPIC_API_KEY=your-anthropic-key

# OAuth2
CLIENT_ID=your-client-id
CLIENT_SECRET=your-client-secret
```

---

## How It Works

```
┌─────────────────────────────────────────────────────────────────┐
│                        OMCP Pipeline                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   1. Load      OpenAPI spec (file or URL)                      │
│   2. Filter    Apply endpoint include/exclude rules            │
│   3. Plan      LLM suggests names, modules, descriptions       │
│   4. Validate  Check suggestions against actual spec           │
│   5. Build     Generate FastMCP servers deterministically      │
│   6. Serve     Run via stdio, SSE, or HTTP transport           │
│   7. Execute   Tool calls → authenticated HTTP requests        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

**Key principle:** LLM suggestions are never trusted blindly. Every tool is validated against operations that actually exist in your spec.

---

## Project Structure

```
src/omcp/
├── auth/           # Auth providers (bearer, api_key, oauth2, jwt)
├── config/         # Configuration models (Pydantic v2)
├── hub/            # Hub server and meta-tools
├── modules/        # Module splitting and micro-MCP generation
├── planner/        # LLM planning and validation
├── server/         # Single server mode
├── spec/           # OpenAPI parsing and normalization
└── cli.py          # Typer CLI

examples/
├── auth_api/       # Dynamic JWT authentication demo
├── demo_api/       # Simple getting started example
├── large_api/      # 100+ endpoint hub demo
└── messy_api/      # Filtering and LLM optimization demo
```

---

## Contributing

```bash
uv sync
uv run pytest
uv run pytest tests/test_planner.py -v
```

181 tests passing.

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## Roadmap

- [x] OpenAPI → MCP tool generation
- [x] Single server mode
- [x] Modular mode with hub
- [x] LLM-powered planning
- [x] Static authentication (bearer, API key, OAuth2)
- [x] Dynamic authentication (JWT passthrough)
- [ ] Response shaping (truncation, redaction)
- [ ] Streaming support for long operations
- [ ] OMCP Cloud (hosted, managed credentials)
- [ ] Semantic tool search (embeddings)

---

## License

MIT

---

## Links

- [Model Context Protocol](https://modelcontextprotocol.io/)
- [FastMCP](https://github.com/jlowin/fastmcp)
- [OpenAPI Specification](https://spec.openapis.org/oas/latest.html)

---

