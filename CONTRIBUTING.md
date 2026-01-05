# Contributing to OMCP

Thanks for your interest in contributing to OMCP! This document covers everything you need to get started.

## Development Setup

### Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip

### Installation

```bash
# Clone the repository
git clone https://github.com/cal3bdev/omcp.git
cd omcp

# Install dependencies
uv sync

# Verify installation
uv run omcp --version
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run specific test file
uv run pytest tests/test_planner.py

# Run specific test
uv run pytest tests/test_planner.py::test_plan_validation -v

# Run with coverage
uv run pytest --cov=omcp
```

### Running the CLI

```bash
# Show help
uv run omcp --help

# Run with a config
uv run omcp serve -c examples/demo_api/omcp.yaml

# Generate a plan
uv run omcp plan -c examples/large_api/omcp.yaml

# List operations
uv run omcp list -c examples/demo_api/omcp.yaml
```

---

## Project Structure

```
src/omcp/
├── auth/           # Authentication providers
│   ├── factory.py      # Auth provider factory
│   ├── providers.py    # Bearer, API key, OAuth2 implementations
│   ├── jwt.py          # JWT validation
│   ├── context.py      # Auth context for requests
│   └── middleware.py   # Auth middleware
│
├── config/         # Configuration
│   ├── models.py       # Pydantic models for all config
│   ├── loader.py       # YAML loading and validation
│   └── env.py          # Environment variable substitution
│
├── spec/           # OpenAPI handling
│   ├── loader.py       # Spec loading (file/URL)
│   ├── normalizer.py   # Spec normalization
│   └── validator.py    # Spec validation
│
├── planner/        # LLM planning
│   ├── schema.py       # Plan schema (OMCPPlan)
│   ├── prompts.py      # LLM prompts
│   ├── adapters.py     # LLM provider adapters
│   ├── generator.py    # Plan generation
│   └── validator.py    # Plan validation against spec
│
├── server/         # Single server mode
│   ├── builder.py      # FastMCP server builder
│   └── runner.py       # Server runner
│
├── modules/        # Modular mode
│   ├── splitter.py     # Module splitting strategies
│   ├── builder.py      # Module builder
│   └── runner.py       # Multi-module runner
│
├── hub/            # Hub server
│   ├── registry.py     # Module registry
│   ├── router.py       # Tool routing
│   ├── builder.py      # Hub builder with meta-tools
│   └── runner.py       # Hub runner
│
├── filters/        # Endpoint filtering
│   └── patterns.py     # Include/exclude pattern matching
│
├── utils/          # Utilities
│   ├── console.py      # Rich console output
│   ├── errors.py       # Custom exceptions
│   └── ui.py           # CLI UI components
│
└── cli.py          # Typer CLI entry point

tests/              # Test suite
examples/           # Example projects
```

---

## Code Style

### Formatting

We use [Ruff](https://github.com/astral-sh/ruff) for linting and formatting:

```bash
# Check formatting
uv run ruff check .

# Fix formatting issues
uv run ruff check --fix .

# Format code
uv run ruff format .
```

### Type Hints

All code should include type hints:

```python
# Good
def create_server(config: OMCPConfig, spec: NormalizedSpec) -> FastMCP:
    ...

# Avoid
def create_server(config, spec):
    ...
```

### Imports

Organize imports in this order:
1. Standard library
2. Third-party packages
3. Local imports

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel

from omcp.config import OMCPConfig
from omcp.spec import NormalizedSpec
```

### Docstrings

Use Google-style docstrings for public functions and classes:

```python
def validate_plan(plan: OMCPPlan, spec: NormalizedSpec) -> ValidationResult:
    """Validate an OMCP plan against the OpenAPI spec.

    Checks that all tools reference real operations and that
    module assignments are valid.

    Args:
        plan: The OMCP plan to validate.
        spec: The normalized OpenAPI spec.

    Returns:
        ValidationResult with any errors or warnings.

    Raises:
        ValidationError: If the plan has critical errors.
    """
```

---

## Testing

### Test Organization

- `tests/test_*.py` - Unit tests for each module
- `tests/fixtures/` - Test fixtures (specs, configs)

### Writing Tests

Use pytest with clear test names:

```python
class TestServerBuilder:
    """Test server builder."""

    def test_builder_loads_spec(self):
        """Builder loads and normalizes spec."""
        config = load_config(FIXTURES / "test_config.yaml")
        builder = ServerBuilder(config)

        assert builder.spec.title == "Test API"
        assert len(builder.spec.operations) == 5

    def test_builder_with_endpoint_exclude(self):
        """Builder respects endpoint exclusions."""
        config = load_config(FIXTURES / "test_config.yaml")
        config.endpoints.exclude = ["DELETE *"]

        builder = ServerBuilder(config)
        tools = builder.get_tool_list()

        assert not any(t["method"] == "DELETE" for t in tools)
```

### Test Coverage

Aim for high coverage on core modules:
- `config/` - Configuration loading and validation
- `spec/` - OpenAPI parsing and normalization
- `planner/` - Plan generation and validation
- `filters/` - Endpoint filtering

---

## Pull Request Process

### Before Submitting

1. **Run tests**: `uv run pytest`
2. **Check formatting**: `uv run ruff check .`
3. **Update tests**: Add tests for new functionality
4. **Update docs**: Update README if adding features

### PR Guidelines

- **One feature per PR**: Keep PRs focused
- **Clear title**: Describe what the PR does
- **Link issues**: Reference related issues with `Fixes #123`
- **Small commits**: Break large changes into logical commits

### Commit Messages

Use conventional commit format:

```
feat: Add semantic search for tool discovery
fix: Handle empty spec paths correctly
docs: Update authentication examples
refactor: Simplify module splitting logic
test: Add tests for JWT validation
```

---

## Architecture Guidelines

### Design Principles

1. **Spec as source of truth**: All tool generation derives from the OpenAPI spec
2. **LLM suggestions, deterministic validation**: Never trust LLM output blindly
3. **Safety by default**: Block dangerous operations unless explicitly allowed
4. **Modular scaling**: Architecture should scale from 1 to 500+ operations

### Adding New Features

When adding features, consider:

1. **Configuration**: Add to `config/models.py` with Pydantic validation
2. **CLI**: Add commands or options to `cli.py`
3. **Tests**: Add comprehensive tests
4. **Examples**: Update examples if applicable
5. **Documentation**: Update README and example.omcp.yaml

### Error Handling

Use custom exceptions from `utils/errors.py`:

```python
from omcp.utils.errors import ConfigError, SpecError, PlanError

# Configuration errors
raise ConfigError("Invalid auth type", details={"type": config.auth.type})

# Spec errors
raise SpecError("Missing required field", field="paths")

# Plan validation errors
raise PlanError("Tool references non-existent operation", tool=tool_name)
```

---

## Examples

### Running Examples

Each example has a `start.py` for easy startup:

```bash
# Demo API (simple)
uv run python examples/demo_api/start.py

# Large API with hub
uv run python examples/large_api/start.py --ui

# Auth API (multi-tenant)
uv run python examples/auth_api/start.py --ui
```

### Adding Examples

New examples should include:
- `main.py` - FastAPI application
- `omcp.yaml` - OMCP configuration
- `start.py` - One-command startup script
- `README.md` - Documentation

---

## Getting Help

- **Issues**: Open an issue for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions

---

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
