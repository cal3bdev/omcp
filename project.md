# OMCP - OpenAPI to MCP

## Technical Specification v2.0 (LLM-Assisted, Modular MCP)

---

## 1. Executive Summary

### 1.1 Vision

OMCP (OpenAPI to MCP) is a CLI tool that converts any OpenAPI specification into one or more fully functional MCP (Model Context Protocol) servers—so AI agents can interact with REST APIs without custom integration code. 

**v2.0 extends v1.0** by adding:

* An **LLM refinement pipeline** that produces clean tool naming, better descriptions, safer defaults, and “bloat control”
* A **modular generation model** (“micro-MCPs”) instead of one mega server
* An optional **Hub** that exposes modules as a unified, discoverable surface

### 1.2 Problem Statement

Even with OpenAPI available, connecting LLM agents to real APIs tends to become messy:

* Tool surfaces become bloated (hundreds/thousands of endpoints)
* Names are inconsistent / unhelpful (operationId often poor)
* Specs are “correct” but not “agent-friendly” (missing intent, ambiguous params)
* Some endpoints are unsafe/unfit (delete/admin/internal), but are still exposed

v1.0 solved the mechanical conversion; v2.0 solves **agent usability + scale + governance**.

### 1.3 Solution

OMCP v2.0 automates the full pipeline:

1. Load OpenAPI spec (file/URL), normalize it
2. (Optional) Run **LLM Planner** to generate a deterministic “OMCP Plan”
3. Build **one or more MCP servers** (“modules”) from the Plan
4. Optionally run an **OMCP Hub** that:

   * Lists available modules
   * Routes calls to the right module (HTTP/SSE deployment mode)
5. Run MCP server(s) using stdio/sse/http transports

### 1.4 Target Users

* Developers building AI agents that need API access
* Teams exposing internal APIs to LLMs safely
* Anyone with an OpenAPI spec who wants MCP compatibility at any scale

---

## 2. Architecture Overview

### 2.1 System Diagram (v2.0)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                                  OMCP CLI                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐ │
│  │  CLI Layer   │──▶│  Config Load │──▶│  Spec Loader  │──▶│ Spec Normalize│ │
│  │  (Typer)     │   │ (Pydantic)   │   │ (httpx/yaml)  │   │ (dereference) │ │
│  └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘ │
│          │                                │                                  │
│          │                                ▼                                  │
│          │                      ┌──────────────────┐                         │
│          │                      │  LLM Planner     │                         │
│          │                      │  (optional)      │                         │
│          │                      │  → OMCP Plan     │                         │
│          │                      └──────────────────┘                         │
│          │                                │                                  │
│          ▼                                ▼                                  │
│  ┌──────────────────┐          ┌──────────────────┐                          │
│  │ Deterministic     │          │ Module Generator │                          │
│  │ Validators        │          │ (micro-MCPs)     │                          │
│  │ (no hallucination)│          └──────────────────┘                          │
│  └──────────────────┘                    │                                    │
│                                          ▼                                    │
│                              ┌───────────────────────┐                        │
│                              │ FastMCP Servers        │                        │
│                              │  - module_users        │                        │
│                              │  - module_orders       │                        │
│                              │  - module_admin (off)  │                        │
│                              └───────────────────────┘                        │
│                                          │                                    │
│                                          ▼                                    │
│                              ┌───────────────────────┐                        │
│                              │ Optional OMCP Hub      │                        │
│                              │ (registry + routing)   │                        │
│                              └───────────────────────┘                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 Data Flow (v2.0)

```
1. User invokes OMCP CLI
        │
        ▼
2. Load config (file or CLI args)
        │
        ▼
3. Fetch/parse OpenAPI spec
        │
        ▼
4. Normalize spec (resolve refs, merge servers/base_url, fix common issues)
        │
        ▼
5. (Optional) LLM Planner generates OMCP Plan:
        - endpoint selection (anti-bloat)
        - tool naming/description rewrite
        - module split strategy
        - safety policies
        │
        ▼
6. Deterministic validators:
        - Plan only references real operations
        - No name collisions
        - Safety constraints enforced
        │
        ▼
7. Generate 1..N FastMCP servers using Plan
        │
        ▼
8. Run server(s) (stdio/sse/http)
        │
        ▼
9. Agent uses tools → routed to correct module → proxied to API
        │
        ▼
10. Response normalized & returned to agent
```

### 2.3 Technology Stack

| Component         | Technology              | Rationale                                                  |
| ----------------- | ----------------------- | ---------------------------------------------------------- |
| CLI Framework     | Typer                   | Modern, type-hinted CLI with auto-generated help           |
| Config Validation | Pydantic v2             | Type-safe config + env var support                         |
| HTTP Client       | httpx                   | Async, consistent with FastMCP usage                       |
| MCP Engine        | FastMCP                 | Production-ready OpenAPI→MCP conversion                    |
| Output Formatting | Rich                    | Clear UX for plan diffs + module summaries                 |
| LLM Provider      | Pluggable               | OpenAI/Anthropic/local; deterministic output w/ validators |
| Testing           | pytest + pytest-asyncio | Standard Python testing                                    |

### 2.4 Key v2.0 Design Principles

1. **LLM produces suggestions, not truth**
   LLM output is treated as a *proposal* (“Plan”), then validated deterministically.

2. **Determinism at the edges**

   * Inputs: normalized OpenAPI snapshot
   * Output: Plan (JSON), validated and reproducible

3. **Modular by default**
   Micro-MCPs keep tool sets small, coherent, and easier for agents to use.

4. **Safety & governance as first-class**
   Strong defaults to avoid exposing dangerous endpoints unintentionally.

---

## 3. Project Structure

```
omcp/
├── pyproject.toml
├── README.md
├── LICENSE
│
├── src/
│   └── omcp/
│       ├── cli.py
│       │
│       ├── config/
│       │   ├── models.py
│       │   ├── loader.py
│       │   └── env.py
│       │
│       ├── spec/
│       │   ├── loader.py
│       │   ├── normalizer.py         # NEW: deref, merge servers, canonicalize
│       │   └── validator.py
│       │
│       ├── planner/                  # NEW: LLM planning pipeline
│       │   ├── __init__.py
│       │   ├── prompts.py            # prompt templates
│       │   ├── llm.py                # provider adapters
│       │   ├── schema.py             # Plan models (Pydantic)
│       │   ├── generate.py           # generate Plan from spec
│       │   ├── validate.py           # deterministic Plan validators
│       │   └── diff.py               # Plan/spec diff reports
│       │
│       ├── modules/                  # NEW: micro-MCP generation + runtime
│       │   ├── splitter.py           # split operations into modules
│       │   ├── builder.py            # build per-module FastMCP
│       │   └── runner.py             # run N modules (process mgmt for http/sse)
│       │
│       ├── hub/                      # NEW: optional hub server
│       │   ├── builder.py
│       │   ├── registry.py
│       │   └── router.py
│       │
│       ├── auth/
│       │   ├── base.py
│       │   ├── api_key.py
│       │   ├── bearer.py
│       │   ├── oauth2.py
│       │   └── storage.py
│       │
│       ├── filters/
│       │   ├── parser.py
│       │   └── routemap.py
│       │
│       ├── server/
│       │   ├── builder.py            # still used for single-server mode
│       │   └── runner.py
│       │
│       └── utils/
│           ├── console.py
│           └── errors.py
│
└── tests/
    ├── test_planner.py
    ├── test_modules.py
    ├── test_hub.py
    └── fixtures/
```

---

## 4. Configuration Schema

### 4.1 Full Configuration Reference

```yaml
# omcp.yaml - Complete configuration reference (v2.0)

# ============================================================================
# REQUIRED FIELDS
# ============================================================================

name: "My API Server"

# OpenAPI specification location (file path or URL)
spec: "./openapi.json"

# Base URL of the actual API
base_url: "https://api.example.com"

# ============================================================================
# AUTHENTICATION (required - choose one type)
# ============================================================================

auth:
  type: bearer
  token: "${API_TOKEN}"

# ============================================================================
# MODE SELECTION (v2.0)
# ============================================================================
# - single: one MCP server (v1 behavior)
# - modular: multiple micro-MCPs + optional hub
mode: modular

# ============================================================================
# LLM PLANNER (optional but recommended for modular mode)
# ============================================================================
llm:
  enabled: true

  # Provider: "openai" | "anthropic" | "local" (adapter-based)
  provider: openai

  # Model name depends on provider
  model: "gpt-4.1-mini"

  # Auth (env var recommended)
  api_key: "${LLM_API_KEY}"

  # Determinism controls
  temperature: 0.1
  max_tokens: 5000

  # Planning strategy
  strategy:
    # Goals: reduce tool bloat, improve naming, improve descriptions,
    # enforce safe endpoint exposure, propose modules
    objectives:
      - "minimize_tool_surface"
      - "agent_friendly_naming"
      - "high_signal_descriptions"
      - "safe_by_default"
      - "cohesive_modules"

    # Maximum number of tools to expose overall (soft cap; validators enforce hard caps)
    max_tools_total: 200

    # Prefer: 10-60 tools per module by default
    target_tools_per_module: 40
    max_tools_per_module: 80

    # Naming style guidance
    naming:
      style: "verb_noun"           # e.g., list_users, create_invoice
      avoid:
        - "generic_verbs"          # do, process, handle
        - "internal_prefixes"      # internal_, admin_
      include_resource_in_name: true
      max_name_length: 40

    # Endpoint safety / policy constraints
    policy:
      block_methods: ["DELETE"]     # default
      block_path_globs:
        - "*/admin/*"
        - "*/internal/*"
      require_auth_for_non_get: true
      pii_redaction: true

  # Prompt templates (you can override; defaults ship with OMCP)
  prompts:
    system: "omcp/planner/system_prompt_v2"
    plan: "omcp/planner/plan_prompt_v2"

  # Plan output
  output:
    # Where to write the plan file
    plan_path: "./omcp.plan.json"
    # Keep intermediate artifacts for debugging
    save_normalized_spec: true
    normalized_spec_path: "./.omcp/spec.normalized.json"

# ============================================================================
# MODULARIZATION (micro-MCPs)
# ============================================================================
modules:
  enabled: true

  # Split strategy:
  # - "llm" : use Plan module assignments
  # - "tags": split by OpenAPI tags
  # - "path": split by first path segment
  # - "hybrid": tags->path fallback
  split_strategy: "llm"

  # Module allow/deny list (after split)
  allow:
    - "*"                # all
  deny:
    - "admin"            # example

  # Module runtime settings (http/sse only)
  runtime:
    base_port: 9100      # modules run on 9100..N
    host: "127.0.0.1"
    transport: http      # recommended for hub routing

# ============================================================================
# HUB (optional)
# ============================================================================
hub:
  enabled: true
  name: "My API Hub"
  transport: http
  host: "127.0.0.1"
  port: 9000

  # Hub behavior
  routing:
    # route tool calls to module based on Plan mapping
    mode: "tool_to_module"
    # safety: hub enforces policy again even if module misconfigured
    enforce_policy: true

  # Discovery surface
  discovery:
    expose_registry_tool: true
    expose_module_docs_resource: true

# ============================================================================
# ENDPOINT FILTERING (optional; still supported)
# ============================================================================
endpoints:
  include: []
  exclude:
    - "DELETE *"
    - "*/admin/*"
    - "* /internal/*"

# ============================================================================
# TOOL CUSTOMIZATION (optional; Plan typically fills this automatically)
# ============================================================================
tools:
  # key is operationId; Plan generation can populate these
  get_users:
    name: "list_users"
    description: "List users with optional filters."

# ============================================================================
# SERVER SETTINGS (single-mode server or hub server)
# ============================================================================
server:
  timeout: 60
  transport: stdio
  host: "127.0.0.1"
  port: 8000

# ============================================================================
# ADVANCED OPTIONS
# ============================================================================
advanced:
  headers:
    User-Agent: "OMCP/2.0"
  retry:
    max_attempts: 3
    backoff_factor: 0.5
  response:
    max_size_mb: 10
    truncate_arrays: 100
```

### 4.2 Minimal Configuration Examples

**Modular + Hub (recommended for deployments):**

```yaml
name: "Acme API"
spec: "https://api.acme.com/openapi.json"
base_url: "https://api.acme.com"
auth:
  type: bearer
  token: "${ACME_TOKEN}"

mode: modular

llm:
  enabled: true
  provider: openai
  model: "gpt-4.1-mini"
  api_key: "${LLM_API_KEY}"

modules:
  enabled: true
  split_strategy: "llm"
  runtime:
    transport: http
    host: "127.0.0.1"
    base_port: 9100

hub:
  enabled: true
  transport: http
  host: "127.0.0.1"
  port: 9000
```

**Single-server mode (v1 behavior, no LLM):**

```yaml
name: "Pet Store API"
spec: "https://petstore.swagger.io/v2/swagger.json"
base_url: "https://petstore.swagger.io/v2"
auth:
  type: api_key
  key: "${PETSTORE_API_KEY}"
mode: single
```

---

## 5. Pydantic Models

### 5.1 Configuration Models (v2.0 additions)

```python
# src/omcp/config/models.py

from __future__ import annotations
from typing import Literal, Annotated
from pydantic import BaseModel, Field
from enum import Enum


class Mode(str, Enum):
    SINGLE = "single"
    MODULAR = "modular"


class LLMProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    LOCAL = "local"


class LLMNaming(BaseModel):
    style: str = "verb_noun"
    avoid: list[str] = Field(default_factory=list)
    include_resource_in_name: bool = True
    max_name_length: int = 40


class LLMPolicy(BaseModel):
    block_methods: list[str] = Field(default_factory=lambda: ["DELETE"])
    block_path_globs: list[str] = Field(default_factory=list)
    require_auth_for_non_get: bool = True
    pii_redaction: bool = True


class LLMStrategy(BaseModel):
    objectives: list[str] = Field(default_factory=list)
    max_tools_total: int = 200
    target_tools_per_module: int = 40
    max_tools_per_module: int = 80
    naming: LLMNaming = Field(default_factory=LLMNaming)
    policy: LLMPolicy = Field(default_factory=LLMPolicy)


class LLMPrompts(BaseModel):
    system: str = "omcp/planner/system_prompt_v2"
    plan: str = "omcp/planner/plan_prompt_v2"


class LLMOutput(BaseModel):
    plan_path: str = "./omcp.plan.json"
    save_normalized_spec: bool = True
    normalized_spec_path: str = "./.omcp/spec.normalized.json"


class LLMSettings(BaseModel):
    enabled: bool = False
    provider: LLMProvider = LLMProvider.OPENAI
    model: str = "gpt-4.1-mini"
    api_key: str | None = None
    temperature: float = 0.1
    max_tokens: int = 5000
    strategy: LLMStrategy = Field(default_factory=LLMStrategy)
    prompts: LLMPrompts = Field(default_factory=LLMPrompts)
    output: LLMOutput = Field(default_factory=LLMOutput)


class ModuleRuntime(BaseModel):
    base_port: int = 9100
    host: str = "127.0.0.1"
    transport: str = "http"  # "http" | "sse"


class ModulesSettings(BaseModel):
    enabled: bool = False
    split_strategy: str = "llm"  # llm|tags|path|hybrid
    allow: list[str] = Field(default_factory=lambda: ["*"])
    deny: list[str] = Field(default_factory=list)
    runtime: ModuleRuntime = Field(default_factory=ModuleRuntime)


class HubRouting(BaseModel):
    mode: str = "tool_to_module"
    enforce_policy: bool = True


class HubDiscovery(BaseModel):
    expose_registry_tool: bool = True
    expose_module_docs_resource: bool = True


class HubSettings(BaseModel):
    enabled: bool = False
    name: str = "OMCP Hub"
    transport: str = "http"
    host: str = "127.0.0.1"
    port: int = 9000
    routing: HubRouting = Field(default_factory=HubRouting)
    discovery: HubDiscovery = Field(default_factory=HubDiscovery)
```

### 5.2 Planner Output Models (The “OMCP Plan”)

```python
# src/omcp/planner/schema.py

from __future__ import annotations
from pydantic import BaseModel, Field


class PlannedTool(BaseModel):
    operation_id: str
    method: str
    path: str

    # The tool name exposed to agents
    tool_name: str

    # High-signal agent description (NOT just OpenAPI summary)
    description: str

    # Whether it is exposed at all
    expose: bool = True

    # Optional: which module this tool belongs to
    module: str = "default"

    # Optional: additional constraints
    safety_notes: list[str] = Field(default_factory=list)


class PlannedModule(BaseModel):
    name: str
    description: str
    # module-level policy overrides (optional)
    policy_overrides: dict = Field(default_factory=dict)


class OMCPPlan(BaseModel):
    version: str = "2.0"

    api_name: str
    base_url: str

    # Global policy (hub and modules enforce this)
    policy: dict

    # Modules + tools
    modules: list[PlannedModule]
    tools: list[PlannedTool]

    # For traceability & debugging
    provenance: dict = Field(default_factory=dict)
```

---

## 6. Authentication System

OMCP keeps the v1.0 auth providers (API key, bearer, OAuth2 PKCE + refresh).
v2.0 adds **policy-aware gating**: planners and hubs can enforce “require auth for non-GET”, block specific methods/paths, etc.

### 6.1 Auth Provider Interface

(unchanged from v1.0; see baseline interface patterns). 

### 6.2–6.5 Providers & Factory

(unchanged from v1.0, but used by both single and modular builds). 

### 6.6 v2.0 Additions: Auth + Policy Coupling

**New behavior:**

* If policy says `require_auth_for_non_get=true`, OMCP refuses to generate or run write tools unless auth config is present and valid.
* Hub (if enabled) can enforce policy independently, acting as a “second lock”.

---

## 7. Endpoint Filtering System

v2.0 retains pattern filtering, but now integrates it with the Planner:

* **Filtering happens in two planes**

  1. **Deterministic filters** (include/exclude patterns) — always enforced
  2. **Planner exposure decisions** (Plan.tools[].expose) — validated and enforced

### 7.1 Pattern Parser

(unchanged; still supports `GET /users/*`, `/health`, `DELETE *`, etc.). 

### 7.2 RouteMap Generator

(unchanged, but now invoked per-module in modular mode). 

### 7.3 v2.0 Tool-Level Excludes (Deterministic)

In v1.0 notes, excluding by operationId was mentioned as something to handle via component callbacks. 
v2.0 formalizes this:

* If Plan marks `expose=false` for a given operationId, OMCP enforces it by:

  * RouteMap exclusion where possible (method/path)
  * Component callback enforcement (last-mile check)

---

## 8. Spec Loader & Normalizer

### 8.1 Spec Loader

v1.0 loader supports local/remote JSON/YAML. 

### 8.2 NEW: Spec Normalizer

The Normalizer produces a canonical snapshot used by both Planner and builders.

**Responsibilities:**

* Dereference `$ref` where feasible (or produce a resolved view)
* Merge/resolve `servers` with `base_url` preference rules
* Ensure every operation has stable identifiers:

  * Prefer OpenAPI `operationId`
  * If missing, generate deterministic `operationId` from `method + path`
* Collect metadata per operation (tags, summary, parameters) into a Planner-friendly table

```python
# src/omcp/spec/normalizer.py (sketch)

def normalize_openapi(spec: dict, base_url: str) -> dict:
    """
    Produce a canonical, planner-friendly OpenAPI snapshot.
    Output must be stable across runs for the same input.
    """
    # 1) resolve/deref refs (best-effort)
    # 2) ensure operationIds
    # 3) canonicalize servers/base_url
    # 4) extract per-operation metadata index
    return normalized
```

**Why this matters:**
The Planner must never “see” an inconsistent spec view; determinism starts here.

---

## 9. LLM Planner (Core v2.0 Capability)

### 9.1 Purpose

The LLM Planner is the “agent ergonomics engine” that:

* Detects **bloat** (too many endpoints / too granular)
* Generates **better tool names** aligned to intent
* Produces **high-signal tool descriptions**
* Proposes a **module split** so each micro-MCP is coherent
* Suggests **safety exclusions** (admin/internal/delete) beyond basic patterns

**Important:** the Planner never directly mutates the OpenAPI spec.
It outputs an **OMCP Plan** that is validated before use.

### 9.2 Planner Inputs

The Planner receives:

* Normalized OpenAPI snapshot (canonical)
* A compact “operation table” (method/path/operationId/summary/tags)
* Config constraints:

  * max tool counts
  * naming style rules
  * safety policy rules
  * module sizing targets

### 9.3 Planner Outputs: The OMCP Plan

The OMCP Plan is a structured JSON document with:

* Global policy
* Module list (name + description)
* Tool list (one per operation):

  * tool_name, description, expose flag, module assignment
* Provenance:

  * planner model, timestamp, hashes of inputs (optional)

### 9.4 Prompting Strategy (How the LLM Actually Helps)

#### 9.4.1 Two-Pass Planning (Recommended)

**Pass A: Analysis + Proposal**

* Summarize the API surface
* Identify clusters (tags/path segments)
* Recommend split into modules with rationales
* Recommend exposure set under `max_tools_total`

**Pass B: Deterministic Plan Emission**

* Output Plan strictly following schema
* No free-form prose in the final response

Why two-pass:

* You get the benefit of LLM reasoning
* You still receive a clean, machine-consumable artifact

#### 9.4.2 The “No Hallucination Contract”

We force the model into a closed world:

* It can only refer to operations included in the input operation table
* It must copy operation_id + method + path exactly
* Validators will reject the plan otherwise

#### 9.4.3 Naming Heuristics (Bloat + Usability)

The Planner is instructed to:

* Prefer **verb + resource** (list_users, get_invoice, create_charge)
* Avoid “internal”, “admin”, or environment names in tool names
* Normalize synonyms:

  * “fetch/list” → list_
  * “retrieve/get” → get_
  * “remove/delete” → delete_ (often blocked by policy)
* Cap name length and ensure uniqueness

#### 9.4.4 Description Heuristics (High Signal)

Instead of OpenAPI summaries like “Get user”, descriptions should:

* State intent + key constraints
* Mention important parameters and safe usage patterns
* Mention pagination behavior if present
* Mention side effects for writes (create/update)

Example:

* Bad: “Create user”
* Better: “Create a new user. Requires email + role. Returns created user id. Use sparingly; triggers welcome email.”

### 9.5 Default Planner System Prompt (v2.0)

```text
You are OMCP Planner, a tool-surface designer for MCP.
Your job is to produce a strict JSON plan that improves agent usability and safety.

Hard rules:
- You may ONLY reference operations explicitly included in the input operations table.
- You MUST output JSON that matches the provided schema exactly.
- You MUST ensure tool_name values are unique within the whole plan.
- You MUST respect the policy constraints (blocked methods/paths).
- Prefer minimal bloat: fewer, higher-signal tools. Do NOT expose internal/admin endpoints.

Quality rules:
- Tool names must be verb_noun.
- Descriptions must be concise, high-signal, and mention key parameters.
- Modules should be coherent and sized near target_tools_per_module.
```

### 9.6 Default Planner Plan Prompt (v2.0)

```text
Given:
- API_NAME, BASE_URL
- POLICY constraints
- NAMING constraints
- SIZE constraints
- OPERATIONS TABLE (operation_id, method, path, tags, summary, param_names)

Tasks:
1) Propose 3-8 modules with names + descriptions.
2) Select which operations to expose (expose=true/false).
3) For each exposed operation, propose:
   - tool_name (unique, verb_noun)
   - description (high-signal)
   - module assignment
4) Output ONLY valid JSON matching OMCPPlan schema.

Return JSON only.
```

### 9.7 Deterministic Validators (Plan Gate)

Before building any server(s), OMCP validates:

1. **Operation existence check**
   Every Plan tool must match a real `operationId + method + path` from normalized spec.

2. **Policy enforcement**

   * block_methods
   * block_path_globs
   * require_auth_for_non_get

3. **Uniqueness & collisions**

   * tool_name uniqueness across all modules
   * module name uniqueness

4. **Size constraints**

   * enforce max_tools_total
   * enforce max_tools_per_module

5. **Stability checks (optional)**

   * deterministic naming fallback if model output is incomplete

If validation fails, OMCP:

* prints a rich diff report
* exits non-zero (unless `--force` in dev mode)

### 9.8 CLI Commands for Planner

* `omcp plan --config omcp.yaml`
  Generates `omcp.plan.json` + normalized spec snapshot.

* `omcp plan --interactive` (future)
  Allows human approval of module split + exposure decisions.

* `omcp diff --plan omcp.plan.json`
  Shows what changed vs defaults (naming overrides, excluded endpoints, module mapping).

---

## 10. Server Builder (Single + Modular)

### 10.1 Single Server Builder (v1 behavior retained)

Single server builder continues to call `FastMCP.from_openapi(...)` with route_maps and name overrides. 

### 10.2 NEW: Modular Builder (micro-MCPs)

In modular mode:

* OMCP groups planned tools by module
* Builds one FastMCP server per module using:

  * module-specific route maps (include only that module’s operations)
  * module-specific mcp_names mapping (operationId → planned tool_name)
  * module-level policy overrides (optional)

**Key constraint:**

* For stdio clients (e.g., Claude Desktop), you typically register multiple servers directly.
* For hub routing, modules should run over **HTTP/SSE** so the hub can call them.

### 10.3 Component Customization Callback (Expanded)

The callback becomes the enforcement point for:

* description overrides
* final “expose=false” deny
* optional response shaping hints (truncate arrays, redact PII)

---

## 11. OMCP Hub (Optional)

### 11.1 Purpose

The Hub provides a unified entrypoint when you deploy multiple modules over HTTP/SSE.

It offers:

* **Registry / discovery**: what modules exist + what they contain
* **Routing**: given a tool name, forward to the correct module
* **Policy enforcement**: block disallowed calls centrally

### 11.2 Hub Operation Model

The Hub runs as its own MCP server exposing:

1. Tool: `list_modules()`
   Returns module names, descriptions, endpoints, and module URLs.

2. Tool: `call(tool_name, args)` (optional)
   Routes to a module based on Plan mapping.

3. Resource: `module_docs/<module>` (optional)
   Returns the module’s tool list + descriptions for clients that want prefetch.

### 11.3 Hub Routing Modes

* `tool_to_module` (default): Plan mapping tool_name → module
* `operation_to_module`: route based on operation_id
* `manual`: explicit mapping in config

### 11.4 Transport Constraints

* Hub is most useful with `http` or `sse` transports.
* In pure stdio environments, “hub” is less useful; clients can register each module directly.

---

## 12. CLI Interface (v2.0)

### 12.1 Commands

* `omcp serve`

  * In single mode: run one server
  * In modular mode: run modules (+ hub if enabled)

* `omcp plan`
  Generate Plan using the LLM planner (and validators)

* `omcp list`
  List operations or planned tools; show module assignment if plan provided

* `omcp auth`
  OAuth2 authorization flow (unchanged)

### 12.2 Example Flows

**Generate plan then run modular:**

```bash
omcp plan --config omcp.yaml
omcp serve --config omcp.yaml
```

**Run modular without LLM (tags split fallback):**

```bash
omcp serve --config omcp.yaml --no-llm --split-strategy tags
```

---

## 13. Error Handling

v1.0 error classes remain; v2.0 adds planner-specific errors:

* `PlanGenerationError`
* `PlanValidationError`
* `ModuleRuntimeError`
* `HubRoutingError`

(Existing patterns apply). 

---

## 14. Dependencies

Additions for v2.0:

* LLM provider SDKs (optional extras)
* JSON schema / structured output helpers (optional)

Core dependencies remain consistent with v1.0 baseline. 

---

## 15. Testing Strategy

### 15.1 New Test Categories

| Category            | Description                                        | Tools               |
| ------------------- | -------------------------------------------------- | ------------------- |
| Planner Contract    | Ensure Plan schema correctness + no hallucinations | pytest              |
| Plan Validation     | Ensure policy + collision + size enforcement       | pytest              |
| Modular Integration | Build multiple servers from plan                   | pytest              |
| Hub Routing         | Route tool calls to correct module                 | pytest + httpx mock |

### 15.2 Key Test Cases (v2.0)

* Plan rejects non-existent operationIds
* Plan rejects duplicate tool_name collisions
* Policy blocks DELETE even if LLM tries to expose it
* Hub denies blocked endpoints even if a module misconfigures
* Deterministic fallback naming when missing

---

## 16. Implementation Phases (v2.0)

### Phase 1: Core v2 Infrastructure (Week 1)

* [ ] Spec normalizer + operation index
* [ ] Plan schema + validators
* [ ] `omcp plan` command

### Phase 2: Modular Servers (Week 2)

* [ ] Module splitter + per-module FastMCP build
* [ ] Module runner (http/sse)
* [ ] Tool name + description overrides per plan

### Phase 3: Hub (Week 3)

* [ ] Hub registry + discovery
* [ ] Hub routing to modules
* [ ] Hub policy enforcement

### Phase 4: Polish (Week 4)

* [ ] Rich plan diff output
* [ ] Strong docs + examples
* [ ] Packaging + CI + test coverage

---

## Appendix A: Glossary

(extended from v1.0)

| Term        | Definition                                                 |
| ----------- | ---------------------------------------------------------- |
| MCP         | Model Context Protocol - standard for LLM tool integration |
| OMCP Plan   | Deterministic JSON plan produced by LLM + validators       |
| Micro-MCP   | A small MCP server for a coherent subset of tools          |
| Hub         | MCP server that provides discovery + routing for modules   |
| FastMCP     | Python library for building MCP servers                    |
| PKCE        | OAuth2 security extension                                  |
| RouteMap    | FastMCP configuration for endpoint → tool mapping          |
| operationId | Unique identifier for an API operation in OpenAPI          |

---

## Appendix B: References

(keep v1.0 references + add planner notes)

* MCP Specification
* FastMCP Documentation
* OpenAPI Specification
* Typer Documentation
* Pydantic Documentation

---

