# Widget Store API - Filtering & Cleanup Demo

A demonstration of OMCP's endpoint filtering capabilities using an intentionally "messy" API with debug routes, admin endpoints, legacy paths, and poor documentation.

## Overview

This example shows:
- **Endpoint Filtering**: Exclude internal/debug/admin routes
- **Pattern Matching**: Glob patterns for bulk exclusions
- **Single Mode**: Simple server without modules

```
┌─────────────┐     ┌─────────────────────────────────────────┐
│  Chainlit   │────▶│              OMCP (Single)              │
│   Web UI    │     │  Filters out: /debug/*, /admin/*, etc.  │
└─────────────┘     │  Exposes: widgets, orders, reviews      │
                    └───────────────────────────────────────────┘
                                        │
                    ┌───────────────────▼───────────────────────┐
                    │          Widget Store API                 │
                    │  ├── /widgets/*     (✓ included)         │
                    │  ├── /orders/*      (✓ included)         │
                    │  ├── /reviews/*     (✓ included)         │
                    │  ├── /debug/*       (✗ excluded)         │
                    │  ├── /internal/*    (✗ excluded)         │
                    │  ├── /admin/*       (✗ excluded)         │
                    │  └── /v1/*          (✗ excluded)         │
                    └───────────────────────────────────────────┘
```

## The Problem

Real-world APIs often have endpoints that shouldn't be exposed as MCP tools:

| Category | Examples | Why Exclude? |
|----------|----------|--------------|
| Debug | `/debug/logs`, `/debug/metrics` | Internal diagnostics |
| Admin | `/admin/reset`, `/admin/seed` | Dangerous operations |
| Internal | `/internal/cache`, `/internal/metrics` | Infrastructure |
| Legacy | `/v1/*`, `/api/*` | Deprecated, redundant |
| Meta | `/`, `/docs-redirect` | Not useful as tools |

## Quick Start

### One Command

```bash
# Start everything: API + OMCP + Chainlit UI
uv run python examples/messy_api/start.py --ui

# Open http://localhost:8000 in your browser
```

This starts:
- **Widget Store API** at http://localhost:8001
- **OMCP Server** at http://localhost:9000 (filtered)
- **Chainlit UI** at http://localhost:8000

### Without UI

```bash
# Start API + OMCP only
uv run python examples/messy_api/start.py
```

## API Endpoints

### Included (Exposed as Tools)

#### Widgets
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/widgets` | List widgets with filters |
| POST | `/widgets` | Create a widget |
| GET | `/widgets/{id}` | Get widget by ID |
| PUT | `/widgets/{id}` | Update widget |
| DELETE | `/widgets/{id}` | Delete widget |
| PATCH | `/widgets/{id}/stock` | Adjust stock level |

#### Orders
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/orders` | List orders |
| POST | `/orders` | Create order |
| GET | `/orders/{id}` | Get order |
| POST | `/orders/{id}/cancel` | Cancel order |

#### Reviews
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/reviews` | List reviews |
| POST | `/reviews` | Create review |

#### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Basic health check |

### Excluded (Filtered Out)

| Pattern | Endpoints | Reason |
|---------|-----------|--------|
| `* /debug/**` | `/debug/logs`, `/debug/logs` (POST/DELETE) | Debug tools |
| `* /internal/**` | `/internal/cache`, `/internal/metrics` | Internal infra |
| `* /admin/**` | `/admin/reset`, `/admin/seed`, `/admin/export` | Dangerous ops |
| `* /v1/**` | `/v1/widgets`, `/v1/orders` | Legacy/deprecated |
| `* /api/**` | `/api/widgets` | Alternative legacy |
| `GET /` | Root endpoint | Not useful |
| `GET /docs-redirect` | Documentation redirect | Not useful |
| `GET /health/detailed` | Detailed health | Internal only |

## Configuration

`omcp.yaml`:

```yaml
name: "Acme Widget Store"
spec: "http://127.0.0.1:8001/openapi.json"
base_url: "http://127.0.0.1:8001"

mode: single

# Endpoint filtering
endpoints:
  exclude:
    - "* /debug/**"        # All debug endpoints
    - "* /internal/**"     # All internal endpoints
    - "* /admin/**"        # All admin endpoints
    - "* /v1/**"           # Legacy v1 API
    - "* /api/**"          # Alternative legacy paths
    - "GET /"              # Root endpoint
    - "GET /docs-redirect" # Documentation redirect
    - "GET /health/detailed"  # Detailed health
```

### Filter Pattern Syntax

```
METHOD /path/pattern
```

| Pattern | Matches |
|---------|---------|
| `GET /users` | Exactly `GET /users` |
| `* /admin/**` | Any method under `/admin/` |
| `POST /debug/*` | `POST /debug/logs` but not `/debug/sub/path` |
| `DELETE /users/{id}` | `DELETE /users/123` |

### Alternative: Include-Only Mode

See `omcp_include_only.yaml` for whitelist-based filtering:

```yaml
endpoints:
  include:
    - "* /widgets/**"
    - "* /orders/**"
    - "* /reviews/**"
    - "GET /health"
  exclude: []
```

## MCP Tools (After Filtering)

OMCP exposes these tools (13 total, down from 25+):

| Tool | Description |
|------|-------------|
| `get_widgets` | List widgets with filters |
| `create_widget` | Create a new widget |
| `get_widget` | Get widget by ID |
| `update_widget` | Update widget data |
| `delete_widget` | Remove a widget |
| `adjust_stock` | Change stock level |
| `list_orders` | Get all orders |
| `create_order` | Place an order |
| `get_order` | Get order details |
| `cancel_order` | Cancel pending order |
| `get_reviews` | List reviews |
| `create_review` | Add a review |
| `health_check` | Check API health |

## Example Conversations

```
Show me all widgets
```

```
Create a widget called "Super Gadget" priced at $29.99
```

```
Place an order for widget xyz, quantity 2, ship to 123 Main St
```

```
Leave a 5-star review for widget abc with comment "Great product!"
```

```
Adjust stock for widget xyz by +50 units
```

```
Cancel order order_123
```

## Testing Filtering

Compare tool counts before and after filtering:

```bash
# Without filtering (hypothetically ~25 tools)
# All endpoints would be exposed including debug, admin, etc.

# With filtering (13 tools)
curl http://localhost:9000/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}' | jq '.result.tools | length'
```

## Key Concepts

1. **Endpoint Filtering**: Control which API endpoints become MCP tools
2. **Glob Patterns**: Use `*` and `**` for flexible path matching
3. **Method Matching**: Filter by HTTP method (`GET`, `POST`, `*`)
4. **Safety First**: Block dangerous operations by default
5. **Clean Tool Surface**: Expose only what agents should use

