# OMCP Implementation Tasks

This document breaks down the OMCP v2.0 implementation into phases and actionable tasks.

---

## Phase 1: Project Foundation & Core Infrastructure ✅

### 1.1 Project Setup
- [x] Create `pyproject.toml` with dependencies:
  - typer (CLI)
  - pydantic v2 (config/models)
  - httpx (HTTP client)
  - fastmcp (MCP server)
  - rich (output formatting)
  - pyyaml (YAML parsing)
  - pytest, pytest-asyncio (testing)
- [x] Set up src layout: `src/omcp/`
- [x] Create `__init__.py` files for all packages
- [x] Set up basic CLI entry point (`cli.py`)

### 1.2 Configuration System (`src/omcp/config/`)
- [x] `models.py` - Pydantic models:
  - [x] `AuthConfig` (type, token/key, OAuth settings)
  - [x] `Mode` enum (single/modular)
  - [x] `LLMProvider` enum (openai/anthropic/local)
  - [x] `LLMNaming`, `LLMPolicy`, `LLMStrategy` models
  - [x] `LLMSettings` model
  - [x] `ModuleRuntime`, `ModulesSettings` models
  - [x] `HubRouting`, `HubDiscovery`, `HubSettings` models
  - [x] `ServerSettings` model
  - [x] `AdvancedSettings` model (headers, retry, response limits)
  - [x] `OMCPConfig` root model combining all settings
- [x] `loader.py` - Load config from YAML file
- [x] `env.py` - Environment variable substitution (e.g., `${API_TOKEN}`)

### 1.3 Spec Loader (`src/omcp/spec/`)
- [x] `loader.py` - Load OpenAPI spec:
  - [x] Local file support (JSON/YAML)
  - [x] Remote URL support (httpx)
  - [x] Auto-detect format
- [x] `validator.py` - Basic OpenAPI validation:
  - [x] Check required fields (openapi version, info, paths)
  - [x] Validate structure

### 1.4 Spec Normalizer (`src/omcp/spec/normalizer.py`)
- [x] Dereference `$ref` (resolve internal references)
- [x] Merge/resolve `servers` with config `base_url`
- [x] Generate deterministic `operationId` for operations missing one
- [x] Build operation index table (method, path, operationId, tags, summary, parameters)
- [x] Ensure output is stable/deterministic across runs

### 1.5 Error Handling (`src/omcp/utils/errors.py`)
- [x] `OMCPError` base class
- [x] `ConfigError` - Invalid configuration
- [x] `SpecLoadError` - Failed to load/parse spec
- [x] `SpecValidationError` - Invalid OpenAPI spec
- [x] `AuthError` - Authentication failures

### 1.6 Console Utilities (`src/omcp/utils/console.py`)
- [x] Rich console setup
- [x] Error formatting helpers
- [x] Progress indicators

---

## Phase 2: Authentication System ✅

### 2.1 Auth Base (`src/omcp/auth/base.py`)
- [x] `AuthProvider` abstract base class:
  - [x] `async def get_headers() -> dict`
  - [x] `async def refresh() -> None`
  - [x] `def is_valid() -> bool`

### 2.2 Auth Providers
- [x] `api_key.py` - API Key authentication:
  - [x] Header-based (`X-API-Key`)
  - [x] Query parameter-based
- [x] `bearer.py` - Bearer token authentication
- [x] `oauth2.py` - OAuth2 with PKCE:
  - [x] Authorization URL generation
  - [x] Token exchange
  - [x] Token refresh
  - [x] Local callback server for auth flow

### 2.3 Auth Storage (`src/omcp/auth/storage.py`)
- [x] Secure token storage (file-based with restricted permissions)
- [x] Token expiry tracking
- [x] Refresh token management

### 2.4 Auth Factory
- [x] `create_auth_provider(config: AuthConfig) -> AuthProvider`
- [x] Provider selection based on config type

---

## Phase 3: Single Server Mode (v1 Behavior) ✅

### 3.1 Endpoint Filtering (`src/omcp/filters/`)
- [x] `parser.py` - Parse filter patterns:
  - [x] Method filters (`GET *`, `DELETE *`)
  - [x] Path filters (`/users/*`, `*/admin/*`)
  - [x] Combined filters (`GET /users/*`)
- [x] `routemap.py` - Generate FastMCP RouteMap:
  - [x] Apply include patterns
  - [x] Apply exclude patterns
  - [x] Build final route configuration

### 3.2 Server Builder (`src/omcp/server/builder.py`)
- [x] Build FastMCP server from config:
  - [x] Load and normalize spec
  - [x] Create auth provider
  - [x] Apply endpoint filters
  - [x] Configure tool name overrides
  - [x] Set up HTTP client with auth headers
- [x] Component customization callback:
  - [x] Description overrides
  - [x] Parameter modifications

### 3.3 Server Runner (`src/omcp/server/runner.py`)
- [x] Run server with transport:
  - [x] stdio transport (for Claude Desktop)
  - [x] SSE transport
  - [x] HTTP transport
- [x] Graceful shutdown handling

### 3.4 CLI Commands (Initial)
- [x] `omcp serve` - Run single server
- [x] `omcp list` - List available operations
- [x] `omcp auth` - OAuth2 flow (if configured)

---

## Phase 4: LLM Planner ✅

### 4.1 Plan Schema (`src/omcp/planner/schema.py`)
- [x] `PlannedTool` model:
  - [x] operation_id, method, path (from spec)
  - [x] tool_name (LLM-suggested)
  - [x] description (LLM-enhanced)
  - [x] expose (bool)
  - [x] module (assignment)
  - [x] safety_notes (list)
- [x] `PlannedModule` model:
  - [x] name, description
  - [x] policy_overrides (optional)
- [x] `OMCPPlan` model:
  - [x] version, api_name, base_url
  - [x] policy (global)
  - [x] modules list
  - [x] tools list
  - [x] provenance (model, timestamp, input hashes)

### 4.2 Prompt Templates (`src/omcp/planner/prompts.py`)
- [x] System prompt (planner role, hard rules, quality rules)
- [x] Plan prompt template (inputs, tasks, output format)
- [x] Template variable substitution

### 4.3 LLM Adapters (`src/omcp/planner/llm.py`)
- [x] `LLMAdapter` abstract base:
  - [x] `async def generate(prompt: str) -> str`
- [x] `GeminiAdapter` (primary):
  - [x] API key auth
  - [x] Model selection (default: gemini-2.0-flash)
  - [x] Temperature/max_tokens control
  - [x] Structured output (JSON mode)
- [x] `OpenAIAdapter`:
  - [x] API key auth
  - [x] Model selection
  - [x] Temperature/max_tokens control
  - [x] Structured output (JSON mode)
- [x] `AnthropicAdapter`:
  - [x] API key auth
  - [x] Model selection
  - [x] Structured output handling
- [x] Adapter factory based on config

### 4.4 Plan Generator (`src/omcp/planner/generate.py`)
- [x] Build operation table from normalized spec
- [x] Format prompt with constraints
- [x] Parse LLM response as JSON
- [x] Handle markdown-wrapped JSON responses
- [x] Build OMCPPlan from parsed response
- [x] Default plan generator (non-LLM fallback)

### 4.5 Plan Validators (`src/omcp/planner/validate.py`)
- [x] `validate_operations()` - Every tool references real operationId
- [x] `validate_policy()` - Blocked methods/paths not exposed
- [x] `validate_uniqueness()` - No duplicate tool names or module names
- [x] `validate_size()` - Enforce max_tools_total, max_tools_per_module
- [x] `validate_naming()` - Check name length, format, snake_case
- [x] Combined `validate_plan()` that runs all validators
- [x] Detailed error reporting for failures

### 4.6 Plan Diff (`src/omcp/planner/diff.py`)
- [x] Compare Plan vs raw spec defaults
- [x] Show naming changes
- [x] Show excluded endpoints
- [x] Show module assignments
- [x] Rich formatted output
- [x] One-line diff summary

### 4.7 CLI: `omcp plan`
- [x] Load config and spec
- [x] Run LLM planner (if enabled)
- [x] Validate generated plan
- [x] Save plan to file
- [x] Show diff summary
- [x] Support --no-validate flag
- [x] Support --diff flag

---

## Phase 5: Modular Servers (Micro-MCPs) ✅

### 5.1 Module Splitter (`src/omcp/modules/splitter.py`)
- [x] Split strategies:
  - [x] `llm` - Use Plan module assignments
  - [x] `tags` - Split by OpenAPI tags
  - [x] `path` - Split by first path segment
  - [x] `hybrid` - Tags with path fallback
- [x] Apply allow/deny lists
- [x] Return module→operations mapping

### 5.2 Module Builder (`src/omcp/modules/builder.py`)
- [x] Build FastMCP server per module:
  - [x] Filter spec to module's operations only
  - [x] Apply Plan tool names and descriptions
  - [x] Configure module-specific route maps
  - [x] Set up shared auth provider
- [x] Component callback for per-tool customization

### 5.3 Module Runner (`src/omcp/modules/runner.py`)
- [x] Process management for multiple servers:
  - [x] Assign ports (base_port + N)
  - [x] Start all modules
  - [x] Graceful shutdown of all modules
- [x] Transport modes:
  - [x] HTTP (streamable-http)
  - [x] SSE
- [x] Module registry (name → URL mapping)

### 5.4 CLI Updates
- [x] `omcp serve` - Detect modular mode, run all modules
- [x] `omcp serve --plan` - Specify plan file for module assignments
- [x] `omcp list --by-module` - Show module assignments when plan exists

---

## Phase 6: Hub Server ✅

### 6.1 Hub Registry (`src/omcp/hub/registry.py`)
- [x] Module registration:
  - [x] Name, description, URL
  - [x] Tool list per module
  - [x] Metadata support
- [x] Module lookup by name
- [x] Tool→module lookup
- [x] Registry info/stats

### 6.2 Hub Router (`src/omcp/hub/router.py`)
- [x] Routing modes:
  - [x] `tool_to_module` - Route by tool name
  - [x] `operation_to_module` - Route by operationId
- [x] HTTP client for module calls (JSON-RPC format)
- [x] Policy enforcement (block disallowed tools)
- [x] Error handling for module failures

### 6.3 Hub Builder (`src/omcp/hub/builder.py`)
- [x] Build Hub as FastMCP server exposing:
  - [x] `list_modules()` tool - Return available modules
  - [x] `list_tools()` tool - List all tools across modules
  - [x] `get_module_info()` tool - Get module details
  - [x] `find_tool()` tool - Find which module has a tool
  - [x] `hub_status()` tool - Get hub status
  - [x] `hub://modules` resource - Module index
  - [x] `hub://modules/<name>` resources - Per-module docs
- [x] Configure discovery settings

### 6.4 Hub Runner (`src/omcp/hub/runner.py`)
- [x] Run hub server with transport options
- [x] Create hub registry from module registry
- [x] Async support

### 6.5 CLI Updates
- [x] `omcp serve` - Start hub when enabled (after modules)
- [x] Hub status in output

---

## Phase 7: Polish & Production Readiness

### 7.1 Testing (`tests/`)
- [ ] `test_config.py` - Config loading and validation
- [ ] `test_spec.py` - Spec loading and normalization
- [ ] `test_auth.py` - Auth providers
- [ ] `test_filters.py` - Endpoint filtering
- [ ] `test_server.py` - Single server build/run
- [ ] `test_planner.py` - Plan generation and validation
- [ ] `test_modules.py` - Module splitting and building
- [ ] `test_hub.py` - Hub routing and discovery
- [ ] `fixtures/` - Sample OpenAPI specs for tests

### 7.2 Documentation
- [ ] README.md with quick start
- [ ] Example configurations
- [ ] Example OpenAPI specs

### 7.3 CI/CD
- [ ] GitHub Actions workflow
- [ ] Linting (ruff)
- [ ] Type checking (mypy)
- [ ] Test coverage

### 7.4 Error Messages & UX
- [ ] Clear error messages for common failures
- [ ] Progress indicators for long operations
- [ ] Plan diff visualization
- [ ] Module status display

---

## Dependency Graph

```
Phase 1 (Foundation)
    ↓
Phase 2 (Auth) ←──────────────────┐
    ↓                              │
Phase 3 (Single Server) ──────────┤
    ↓                              │
Phase 4 (Planner) ─────────────────┤
    ↓                              │
Phase 5 (Modules) ─────────────────┤
    ↓                              │
Phase 6 (Hub) ─────────────────────┘
    ↓
Phase 7 (Polish)
```

---

## Key Milestones

1. **M1: Basic CLI** - Can load config, load spec, list operations
2. **M2: Single Server** - Can run MCP server with auth and filters
3. **M3: LLM Planner** - Can generate and validate OMCP Plan
4. **M4: Modular Servers** - Can run multiple micro-MCPs from Plan
5. **M5: Hub** - Can run hub with discovery and routing
6. **M6: Production Ready** - Tests, docs, CI all complete
