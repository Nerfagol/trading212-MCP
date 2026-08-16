# Contributing

Contributions are welcome when they preserve the project's small, stateless,
strictly read-only design.

## Development setup

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
ruff check .
mypy src tests
pytest
python -m build
docker build -t trading212-mcp:local .
```

Tests must use mocked responses. Never use or include real Trading 212 credentials,
tunnel credentials, account values, portfolio values, `.env` files, or captured
Authorization headers.

## Non-negotiable boundary

The Trading 212 client may contain only explicitly allowlisted retrieval
endpoints called with `GET`. Contributions must not add POST, PUT, PATCH, DELETE,
buying, selling, order placement, order creation, order cancellation, order
modification, or a generic HTTP request/proxy method.

Run `pytest tests/test_security.py -q` and review [docs/security.md](docs/security.md)
before opening a pull request. For security reports, use the private process in
[SECURITY.md](SECURITY.md), not a public pull request or issue.
