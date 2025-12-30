# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

OMCP (OpenAPI to MCP) is a CLI tool that converts OpenAPI specifications into MCP (Model Context Protocol) servers. It enables AI agents to interact with REST APIs without custom integration code.

**Key capabilities:**
- Load and normalize OpenAPI specs (file/URL)
- Optional LLM planner for tool naming, descriptions, and module organization
- Generate single or modular MCP servers ("micro-MCPs")
- Optional Hub server for unified discovery and routing

## Build & Development Commands

```bash
# Install dependencies (once pyproject.toml exists)
uv sync

# Run the CLI
uv run omcp <command>

# Run tests
uv run pytest

# Run single test file
uv run pytest tests/test_planner.py

# Run specific test
uv run pytest tests/test_planner.py::test_plan_validation -v
```

## Architecture

### Core Data Flow

1. CLI (Typer) → Config Load (Pydantic) → Spec Loader (httpx/yaml) → Spec Normalizer
2. (Optional) LLM Planner generates OMCP Plan (JSON)
3. Deterministic validators verify Plan references real operations
4. Module Generator builds FastMCP server(s) from Plan
5. Servers run via stdio/sse/http transports

### Key Modules

- `src/omcp/cli.py` - Main CLI entry point using Typer
- `src/omcp/config/` - Pydantic models for configuration
- `src/omcp/spec/` - OpenAPI loading, normalization, validation
- `src/omcp/planner/` - LLM planning pipeline (prompts, schema, validators)
- `src/omcp/modules/` - Micro-MCP generation and runtime
- `src/omcp/hub/` - Optional hub server for module discovery/routing
- `src/omcp/auth/` - Auth providers (API key, bearer, OAuth2)
- `src/omcp/server/` - Single-server mode builder/runner

### The OMCP Plan

The Plan is a structured JSON document that bridges LLM suggestions and deterministic execution:
- Contains module definitions, tool mappings, and policy
- LLM output is validated against the actual OpenAPI spec (no hallucinated operations)
- Tool names must be unique, follow naming conventions, respect size limits

### Design Principles

1. **LLM produces suggestions, not truth** - Plan is validated deterministically before use
2. **Determinism at the edges** - Normalized spec in, validated Plan out
3. **Modular by default** - Micro-MCPs keep tool sets coherent and manageable
4. **Safety as first-class** - Block dangerous endpoints (DELETE, admin paths) by default

## CLI Commands

```bash
omcp serve       # Run server(s) - single or modular mode
omcp plan        # Generate OMCP Plan using LLM planner
omcp list        # List operations/planned tools
omcp auth        # OAuth2 authorization flow
```

## Configuration

Config lives in `omcp.yaml`. Key settings:
- `mode`: "single" (one server) or "modular" (micro-MCPs + optional hub)
- `llm.enabled`: Whether to use LLM planner
- `modules.split_strategy`: "llm", "tags", "path", or "hybrid"
- `hub.enabled`: Whether to run unified hub server

## Tech Stack

- CLI: Typer
- Config: Pydantic v2
- HTTP: httpx (async)
- MCP: FastMCP
- Output: Rich
- Testing: pytest + pytest-asyncio
