# Contributing to Lumos

## Getting started

```bash
git clone https://github.com/your-org/lumos
cd lumos
cp .env.example .env
# Edit .env with your local DB credentials

python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Running tests

```bash
# Start test database
docker compose -f docker-compose.test.yml up -d

# Run full suite
pytest tests/ -v
```

All tests must pass before submitting a PR.

## Project structure

```text
lumos/
|-- api/        REST API (port 4001)
|-- auth/       Ed25519 crypto, JWT issuance and validation
|-- db/         asyncpg connection, schema, models, repositories
|-- policy/     YAML policy engine, matchers, rate limits, budgets
`-- proxy/      MCP proxy (port 4000), audit queue, identity
policies/       YAML policy files (hot-reloaded)
tests/          Full test suite
docker/         Dockerfiles and compose file
```

## Code style

- Python 3.12+
- Type hints on all function signatures
- Async everywhere - no blocking calls in async code
- Parameterized SQL queries - no string formatting into SQL
- Fail closed - on any security-relevant error, deny

## Submitting a PR

1. Fork the repo
2. Create a branch: `git checkout -b feature/your-feature`
3. Make your changes
4. Run tests: `pytest tests/ -v`
5. Push and open a PR against `main`

## Security issues

Do not open public issues for security vulnerabilities.
Open a private GitHub issue instead.
