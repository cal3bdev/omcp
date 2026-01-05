# Task Manager API - Simple OMCP Demo

A minimal example demonstrating OMCP's core functionality with a simple task management API.

## Overview

This example shows how to:
- Run an OMCP server against a REST API
- Use single-server mode (no modules/hub)
- Connect with a Chainlit chat UI using Google ADK

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Chainlit   │────▶│     OMCP     │────▶│  Task Manager   │
│   Web UI    │     │   (Single)   │     │      API        │
└─────────────┘     └──────────────┘     └─────────────────┘
```

## Quick Start

### One Command

```bash
# Start everything: API + OMCP + Chainlit UI
uv run python examples/demo_api/start.py --ui

# Open http://localhost:8000 in your browser
```

This starts:
- **Task Manager API** at http://localhost:8000
- **OMCP Server** at http://localhost:9000
- **Chainlit UI** at http://localhost:8000

### Without UI

```bash
# Start API + OMCP only
uv run python examples/demo_api/start.py
```

### Manual Setup

```bash
# Terminal 1: Start the API
uv run uvicorn examples.demo_api.main:app --port 8000

# Terminal 2: Start OMCP
uv run omcp serve --config examples/demo_api/omcp.yaml

# Terminal 3: Optional Chainlit UI
uv run chainlit run examples/demo_api/app.py
```

## API Endpoints

### Tasks
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/tasks` | List tasks (filter: completed, priority) |
| POST | `/tasks` | Create a task |
| GET | `/tasks/{id}` | Get task by ID |
| PATCH | `/tasks/{id}` | Update task fields |
| DELETE | `/tasks/{id}` | Delete task |
| POST | `/tasks/{id}/complete` | Mark task complete |

### Notes
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/notes` | List notes (filter: task_id) |
| POST | `/notes` | Create a note |
| GET | `/notes/{id}` | Get note by ID |
| DELETE | `/notes/{id}` | Delete note |

### Utility
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/stats` | Task/note statistics |
| GET | `/health` | Health check |

## MCP Tools

OMCP exposes these tools to AI agents:

| Tool | Description |
|------|-------------|
| `list_tasks` | List tasks with optional filters |
| `create_task` | Create a new task |
| `get_task` | Get task by ID |
| `update_task` | Update task fields |
| `delete_task` | Delete a task |
| `complete_task` | Mark task as complete |
| `list_notes` | List notes |
| `create_note` | Create a note |
| `get_note` | Get note by ID |
| `delete_note` | Delete a note |
| `get_stats` | Get statistics |
| `health_check` | Check API health |

## Example Conversations

Try these in the Chainlit UI:

```
What tasks do I have?
```

```
Create a task to buy groceries with high priority
```

```
Add a note "Don't forget milk" to task 1
```

```
Mark task 1 as complete
```

```
Show me the stats
```

```
Create a task "Meeting prep" due 2025-01-15 with description "Prepare slides for Q1 review"
```

## Configuration

`omcp.yaml`:

```yaml
name: "Task Manager"
spec: "http://127.0.0.1:8000/openapi.json"
base_url: "http://127.0.0.1:8000"

# No authentication needed
auth:
  type: none

# Simple single-server mode
mode: single

server:
  transport: http
  name: "task-manager-mcp"
  host: "127.0.0.1"
  port: 9000
```

## Testing with curl

```bash
# List tools
curl http://localhost:9000/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'

# Create a task
curl http://localhost:9000/mcp -X POST \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {
      "name": "create_task",
      "arguments": {
        "title": "Test task",
        "priority": "high"
      }
    }
  }'
```

## Key Concepts

1. **Single Mode**: All API endpoints become MCP tools directly (no hub/modules)
2. **No Auth**: Simplest setup - no authentication required
3. **Streamable HTTP**: Uses HTTP transport for Chainlit/ADK compatibility
4. **Tool Mapping**: Each REST endpoint becomes one MCP tool

