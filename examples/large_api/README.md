# MegaStore E-Commerce API - Modular OMCP Demo

A comprehensive example demonstrating OMCP's **modular mode** with a large-scale e-commerce API (~100 endpoints) split into micro-MCPs via an LLM planner.

## Overview

This example shows:
- **Modular Mode**: Large API split into coherent micro-MCPs
- **LLM Planning**: Gemini generates intelligent module groupings
- **Hub Architecture**: Meta-tool pattern for scalable tool access
- **Real-World Scale**: ~100 endpoints across 10+ domains

```
┌─────────────┐     ┌─────────────────────────────────────────────────┐
│  Chainlit   │────▶│                    OMCP Hub                     │
│   Web UI    │     │  (6 meta-tools: find_tool, call_tool, etc.)     │
└─────────────┘     └───────────┬───────────────────────────┬─────────┘
                                │                           │
                    ┌───────────▼────────┐     ┌────────────▼──────────┐
                    │  User Management   │     │   Product Catalog     │
                    │    (micro-MCP)     │     │     (micro-MCP)       │
                    │   10 tools         │     │    15 tools           │
                    └────────────────────┘     └───────────────────────┘
                                │                           │
                    ┌───────────▼────────┐     ┌────────────▼──────────┐
                    │  Order Processing  │     │   Payment & Shipping  │
                    │    (micro-MCP)     │     │     (micro-MCP)       │
                    │   12 tools         │     │    18 tools           │
                    └────────────────────┘     └───────────────────────┘
                                         ...
```

## Quick Start

### One Command

```bash
# Start everything: API + OMCP Hub + Chainlit UI
uv run python examples/large_api/start.py --ui

# Open http://localhost:8000 in your browser
```

This starts:
- **MegaStore API** at http://localhost:8002
- **Module Servers** at ports 9100+
- **OMCP Hub** at http://localhost:9000
- **Chainlit UI** at http://localhost:8000

### Without UI

```bash
# Start API + OMCP Hub only
uv run python examples/large_api/start.py
```

### Generate a New Plan

```bash
# Re-run LLM planner to regenerate module groupings
uv run omcp plan --config examples/large_api/omcp.yaml
```

## API Domains

The MegaStore API covers these domains:

| Domain | Endpoints | Description |
|--------|-----------|-------------|
| **Users** | 10 | User CRUD, addresses, wishlists |
| **Products** | 15 | Catalog, categories, search |
| **Cart** | 8 | Shopping cart, checkout |
| **Orders** | 12 | Order lifecycle, tracking |
| **Payments** | 8 | Payment processing, refunds |
| **Shipping** | 10 | Shipments, carriers, rates |
| **Addresses** | 6 | Address management |
| **Promotions** | 8 | Coupons, discounts |
| **Inventory** | 8 | Stock management |
| **Support** | 8 | Tickets, FAQ |
| **Analytics** | 6 | Sales, revenue reports |
| **Notifications** | 5 | User notifications |

## Hub Meta-Tools

Instead of exposing 100+ tools, the Hub provides 6 meta-tools:

| Tool | Description |
|------|-------------|
| `list_modules` | List all available modules |
| `list_module_tools` | List tools in a specific module |
| `find_tool` | Search for tools by keyword |
| `get_tool_schema` | Get full parameter schema for a tool |
| `call_tool` | Execute any tool in any module |
| `hub_status` | Get hub statistics |

### Discovery Workflow

```
1. find_tool("payment")
   → Returns: create_payment (payments), refund_payment (payments), ...

2. get_tool_schema("payments", "create_payment")
   → Returns: {order_id: str (required), amount: float, method: str}

3. call_tool("payments", "create_payment", {order_id: "ord_001", amount: 99.99})
   → Returns: {id: "pay_123", status: "pending", ...}
```

## Seeded Test Data

The API comes pre-loaded with realistic data:

### Users
| ID | Name | City |
|----|------|------|
| user_alice | Alice Johnson | San Francisco |
| user_bob | Bob Smith | Seattle |
| user_carol | Carol White | Austin |
| user_david | David Brown | Denver |
| user_emma | Emma Davis | Miami |

### Products (17 items)
- **Phones**: iPhone 15 Pro, Samsung Galaxy S24, Pixel 8
- **Laptops**: MacBook Pro 16", ThinkPad X1, Dell XPS 15
- **Clothing**: T-shirts, jeans, dresses, blazers
- **Furniture**: Sofa, desk, chair
- **Sports**: Bike, treadmill, yoga mat

### Active Orders
- `ord_003` (Bob): MacBook Pro - shipped
- `ord_004` (Carol): Furniture - processing
- `ord_005` (David): Bike - pending

### Coupons
- `WELCOME10` - 10% off, min $50
- `SUMMER20` - 20% off, min $100
- `VIP30` - 30% off, min $500

## Example Conversations

### Simple Queries

```
Show me all products
```

```
What orders are pending?
```

```
List users in the system
```

### Multi-Module Queries

```
What has Alice Johnson ordered in the past?
```

```
Show me Bob's order including payment and shipping status
```

```
Which products have reviews?
```

### Complex Workflows

```
Carol has a support ticket about a delayed order. Look up her ticket,
check her order status, and give me a summary including payment info.
```

```
Create a new order for user_emma: iPhone 15 Pro, ship to her saved address,
pay with Visa, and create the shipment with FedEx.
```

```
Give me a complete business snapshot: total users, products, pending orders,
open tickets, and revenue from completed orders.
```

See [../client/prompts.md](../client/prompts.md) for more example prompts.

## Configuration

`omcp.yaml`:

```yaml
name: "MegaStore E-Commerce"
spec: "http://127.0.0.1:8002/openapi.json"
base_url: "http://127.0.0.1:8002"

# Modular mode - splits into micro-MCPs
mode: modular

# Hub aggregates all modules
hub:
  enabled: true
  name: "MegaStore Hub"
  port: 9000

# Module configuration
modules:
  enabled: true
  split_strategy: llm  # Uses LLM-generated plan
  runtime:
    base_port: 9100

# LLM planner settings
llm:
  enabled: true
  provider: gemini
  model: gemini-2.0-flash
  strategy:
    target_tools_per_module: 20
```

## The OMCP Plan

The LLM generates `omcp.plan.json` defining module structure:

```json
{
  "modules": [
    {
      "name": "user_management",
      "description": "User accounts, profiles, addresses, wishlists",
      "tools": [
        {"operation_id": "list_users", "name": "list_users", ...},
        {"operation_id": "create_user", "name": "create_user", ...}
      ]
    },
    {
      "name": "product_catalog",
      "description": "Products, categories, search, reviews",
      "tools": [...]
    }
  ]
}
```

## Testing with curl

```bash
# List modules
curl http://localhost:9000/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": 1,
    "method": "tools/call",
    "params": {"name": "list_modules", "arguments": {}}
  }'

# Find tools by keyword
curl http://localhost:9000/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": 2,
    "method": "tools/call",
    "params": {"name": "find_tool", "arguments": {"query": "user"}}
  }'

# Call a tool
curl http://localhost:9000/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": 3,
    "method": "tools/call",
    "params": {
      "name": "call_tool",
      "arguments": {
        "module_name": "user_management",
        "tool_name": "list_users",
        "arguments": {}
      }
    }
  }'
```

## Key Concepts

1. **Modular Mode**: Large APIs are split into coherent micro-MCPs
2. **LLM Planner**: Intelligent grouping based on domain semantics
3. **Hub Pattern**: 6 meta-tools prevent context window bloat
4. **Discover → Understand → Execute**: Workflow for finding and using tools
5. **Micro-MCP Isolation**: Each module runs as a separate server
6. **Plan Validation**: LLM output is validated against actual API spec

