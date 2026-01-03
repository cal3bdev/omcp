# Notes API - Dynamic Authentication Example

This example demonstrates OMCP's dynamic authentication feature, where clients provide their own JWT tokens that OMCP forwards to the upstream API.

## Architecture

```
┌─────────────┐     ┌──────────────┐     ┌────────────────┐
│ ADK Client  │────▶│     OMCP     │────▶│   Notes API    │
│  (+ Token)  │     │ (Passthrough)│     │ (Validates JWT)│
└─────────────┘     └──────────────┘     └────────────────┘
```

1. Client obtains JWT from Notes API (`POST /auth/token`)
2. Client sends MCP requests to OMCP with `Authorization: Bearer <token>`
3. OMCP forwards the token to upstream API calls
4. Notes API validates the token and returns user-specific data

## Quick Start

### 1. Start the Notes API

```bash
uv run uvicorn examples.auth_api.main:app --port 8080
```

### 2. Start OMCP with Dynamic Auth

```bash
uv run omcp serve --config examples/auth_api/omcp.yaml
```

### 3. Run the Agent Client

```bash
# Run as alice (admin)
uv run python examples/auth_api/client.py --user alice

# Run as bob (regular user)
uv run python examples/auth_api/client.py --user bob

# Run as charlie
uv run python examples/auth_api/client.py -u charlie
```

The client will:
- Authenticate as the specified user
- Connect to OMCP with the JWT token
- Start an interactive AI agent session

## Test Users

| Username | Password | Role  | Notes |
|----------|----------|-------|-------|
| alice    | alice    | admin | 2 notes, can view stats |
| bob      | bob      | user  | 2 notes |
| charlie  | charlie  | user  | 1 note |

## API Endpoints

### Authentication (Direct to API)

```bash
# Get token
curl -X POST "http://localhost:8080/auth/token?username=alice&password=alice"

# List users
curl http://localhost:8080/auth/users
```

### MCP Tools (via OMCP)

| Tool | Description |
|------|-------------|
| `get_me` | Get current user info |
| `list_notes` | List user's notes |
| `create_note` | Create a new note |
| `get_note` | Get a specific note |
| `update_note` | Update a note |
| `delete_note` | Delete a note |
| `get_stats` | System stats (admin only) |

## Manual Testing

```bash
# Get a token
TOKEN=$(curl -s -X POST "http://localhost:8080/auth/token?username=alice&password=alice" | jq -r '.access_token')

# Call OMCP with the token
curl -X POST http://localhost:9000/mcp/v1 \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "list_notes",
      "arguments": {}
    }
  }'
```

## Configuration

The `omcp.yaml` uses JWT auth type with validation disabled (passthrough mode):

```yaml
auth:
  type: jwt
  validation:
    enabled: false  # Upstream API validates tokens
  header:
    name: Authorization
    scheme: Bearer
```

## Key Concepts

1. **Stateless Passthrough**: OMCP doesn't store or manage tokens - it just forwards them
2. **User Isolation**: Each user only sees their own notes
3. **Role-Based Access**: Admin users can access stats endpoint
4. **Token Ownership**: Clients are responsible for obtaining and refreshing tokens
