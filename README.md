# Lumos
> The open-source AI Action Firewall for MCP agents.

![License: MIT](https://img.shields.io/badge/License-MIT-green) ![Python: 3.12+](https://img.shields.io/badge/Python-3.12%2B-blue) ![Tests passing](https://img.shields.io/badge/Tests-passing-brightgreen)

Lumos sits between AI agents and MCP tool servers, intercepts every tool call, validates cryptographic identity, evaluates YAML policy rules for allow, deny, rate limit, and budget enforcement, forwards allowed requests, blocks denied ones, and logs every decision to a tamper-evident Merkle audit trail. You do not need to modify your agent code to use it.

AI agents with access to tools can take actions their users never intended. There is no standard way to enforce what an agent is and is not allowed to do. Lumos fixes this at the transport layer before the tool server ever sees the request.

## How it works

```text
Your Agent
    |
    v
+--------------------------------------+
|              Lumos Proxy             |
|                                      |
|  1. Validate capability token (DB)   |
|  2. Evaluate YAML policy             |
|  3. Allow or Block                   |
|  4. Log to Merkle audit trail        |
+--------------------------------------+
     | allow                | block
     v                      v
MCP Tool Server      MCP Error Response
(your real server)   (agent sees denial)
```

Every MCP tool call flows through the Lumos proxy before it reaches your real tool server. The proxy validates the capability token, applies policy, forwards only approved requests, and records the outcome in the audit chain.

## Quickstart

### 1. Clone and configure

```bash
git clone https://github.com/your-org/lumos
cd lumos
cp .env.example .env
# Edit .env - set LUMOS_ADMIN_TOKEN to a secret value
```

### 2. Start the stack

```bash
docker compose -f docker/docker-compose.yml up -d
```

Wait for all three services to be healthy:

```bash
docker compose -f docker/docker-compose.yml ps
```

### 3. Initialise the database

```bash
curl -X POST http://localhost:4001/internal/db/init \
  -H "Authorization: Bearer your-admin-token"
```

### 4. Register an agent

```bash
curl -X POST http://localhost:4001/v1/agents \
  -H "Authorization: Bearer your-admin-token" \
  -H "Content-Type: application/json" \
  -d '{"agent_id": "my-agent", "display_name": "My First Agent"}'
```

### 5. Point your MCP client at the proxy

For Claude Desktop, edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "my-server-via-lumos": {
      "url": "http://localhost:4000/proxy",
      "headers": {
        "x-lumos-agent-id": "my-agent"
      }
    }
  }
}
```

For Cursor or Windsurf, use the same proxy URL in your MCP server config.

### 6. Write a policy

Edit `policies/default.yaml`:

```yaml
rules:
  - name: block-delete-tools
    tool: "tool.delete*"
    action: deny
    reason: "Deletion tools are blocked by policy"

  - name: allow-everything-else
    tool: "*"
    action: allow

rate_limits:
  "*":
    window_seconds: 60
    max_calls: 100

budgets:
  "*":
    period: daily
    limit: 1000
```

Policy reloads automatically within 1 second. No restart needed.

## API reference

| Method | Path | Description |
|--------|------|-------------|
| GET | /health | Health check |
| POST | /v1/agents | Register agent |
| POST | /v1/agents/{id}/keys | Add Ed25519 key |
| POST | /v1/auth/nonce | Get auth nonce |
| POST | /v1/auth/session | Create session |
| POST | /v1/capabilities | Issue capability token |
| GET | /api/events | List audit events |
| GET | /api/agents | List agents with stats |
| GET | /api/stats/summary | Dashboard summary |
| GET | /api/stats/costs | Budget usage |
| GET | /api/policy | Get current policy |
| PUT | /api/policy | Update policy |
| GET | /api/audit/verify | Verify Merkle chain |

All endpoints except `/health` and `/v1/auth/nonce` require `Authorization: Bearer <admin-token>`.

## What's implemented

- Ed25519 cryptographic agent identity
- Nonce-based challenge-response authentication (replay-resistant)
- Session JWTs + capability JWTs (EdDSA signed, short-lived)
- DB-backed fail-closed token validation
- MCP JSON-RPC 2.0 proxy (HTTP transport)
- YAML policy engine with hot reload (< 1s)
- 10 argument matchers (equals, not_equals, contains, regex, gt, lt, in, etc.)
- DB-backed rate limiting (fixed window, per agent and tool)
- DB-backed budget enforcement (daily/monthly, strict reservation)
- Async audit trail with automatic PII redaction
- Tamper-evident Merkle SHA-256 hash chain on all audit events
- Expiry sweeper (sessions, capabilities, nonces cleaned automatically)
- REST API (events, agents, stats, policy, sessions, audit chain)
- Docker Compose full stack (one command startup)

## What's not implemented yet

- Dashboard UI (planned Phase 8)
- CLI tool (planned Phase 8)
- STDIO transport (for local MCP servers)
- SSE transport (for streaming MCP clients)
- Multi-tenant / organisation model
- Automated key rotation
- Distributed policy versioning and rollout safety
- Real production load testing (current tests are in-process only)

## Running tests

Start the test database:

```bash
docker compose -f docker-compose.test.yml up -d
```

Run the full suite:

```bash
pytest tests/ -v
```

Expected output: 79+ tests passing.

## Status

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Data layer (PostgreSQL schema, models, repositories) | Complete |
| 2 | Identity + auth (Ed25519, nonce, sessions, capabilities) | Complete |
| 3 | Enforcement endpoint (/v1/enforce) | Complete |
| 4 | Proxy core (MCP interception, forwarding, audit queue) | Complete |
| 5 | Policy engine (YAML, matchers, rate limits, budgets, PII) | Complete |
| 6 | Merkle audit chain + expiry sweeper | Complete |
| 7 | REST API + Docker | Complete |
| 8 | Dashboard + CLI | Not started |

## Architecture

```text
+-----------------+     +-----------------+
|   Lumos API     |     |  Lumos Proxy    |
|   port 4001     |     |   port 4000     |
|                 |     |                 |
|  Identity mgmt  |     |  MCP intercept  |
|  Token issuance |     |  Policy enforce |
|  REST API       |     |  Audit queue    |
+--------+--------+     +--------+--------+
         |                       |
         +----------+------------+
                    |
           +--------v--------+
           |   PostgreSQL    |
           |  (TimescaleDB)  |
           |                 |
           |  agents         |
           |  sessions       |
           |  capabilities   |
           |  audit_events   |
           |  rate_limit_... |
           |  budget_state   |
           +-----------------+
```

## Contributing

PRs welcome. Run the test suite before submitting. For security issues, open a private GitHub issue.

## License

MIT
