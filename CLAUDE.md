# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python client library and FastAPI application for the Databricks Delta Share API. The project provides REST API endpoints for managing Delta Sharing recipients and shares.

**Package name:** `deltashare_api`
**Module name:** `dbrx_api` (note the discrepancy)
**Python version:** 3.12+

## Development Commands

### Setup
```bash
# Install dev dependencies
make install

# Clean build artifacts and caches
make clean
```

### Testing
```bash
# Run all tests
make test

# Run quick tests (excludes slow tests)
make test-quick

# Run a specific test file
bash run.sh run-tests tests/test_specific.py

# Run a specific test function
bash run.sh run-tests tests/test_file.py::test_function_name

# Serve test coverage report
make serve-coverage-report
```

### Code Quality
```bash
# Run linting and formatting (black, isort, autoflake)
make lint

# CI version (skips no-commit-to-branch check)
make lint-ci
```

### Running the API
```bash
# Run development server with auto-reload
make run-dev

# Or directly via Python
python -m src.dbrx_api.main
```

### Building and Publishing
```bash
# Build wheel and sdist
make build

# Test wheel locally
make test-wheel-locally

# Publish to test PyPI
make publish-test

# Publish to production PyPI
make publish-prod
```

## Architecture

### Core Structure
```
src/dbrx_api/
├── main.py              # FastAPI app creation and configuration
├── settings.py          # Pydantic settings (reads from env vars)
├── schemas.py           # Request/response models
├── errors.py            # Global error handlers
├── routes_share.py      # Share-related API endpoints
├── routes_recipient.py  # Recipient-related API endpoints
├── dbrx_auth/
│   └── token_gen.py     # Databricks authentication token generation
└── dltshr/
    ├── share.py         # Share business logic (Databricks SDK calls)
    └── recipient.py     # Recipient business logic (Databricks SDK calls)
```

### Application Layers

1. **Routes Layer** (`routes_*.py`)
   - FastAPI route handlers
   - Request validation and response serialization
   - Calls business logic functions from `dltshr/` modules

2. **Business Logic Layer** (`dltshr/`)
   - `share.py`: Share operations (create, delete, add/remove data objects, manage recipients)
   - `recipient.py`: Recipient operations (create D2D/D2O recipients, manage IPs, rotate tokens)
   - Uses Databricks SDK (`databricks.sdk.WorkspaceClient`)
   - Authenticates via `dbrx_auth.token_gen.get_auth_token()`

3. **Configuration**
   - `Settings` class uses `pydantic_settings` to load from environment variables
   - Required env var: `dltshr_workspace_url` (Databricks workspace URL)
   - Settings are attached to FastAPI app state: `request.app.state.settings`

### Key Patterns

- **Authentication**: Each business logic function obtains a session token via `get_auth_token(datetime.now(timezone.utc))[0]` and creates a `WorkspaceClient`
- **Router Registration**: Two routers (`ROUTER_SHARE`, `ROUTER_RECIPIENT`) are registered in `main.py`
- **Error Handling**: Global middleware catches broad exceptions, custom handler for Pydantic validation errors
- **OpenAPI Customization**: Custom `operationId` generator creates prettier function names for generated SDKs

### Dependencies

- **Core**: `fastapi`, `pydantic`, `pydantic_settings`, `dotenv`, `typing-extensions`
- **Optional groups**:
  - `[dbrx]`: `databricks-sdk` (required for actual functionality)
  - `[api]`: `uvicorn` (required to run the server)
  - `[azure]`: `azure-storage-blob`, `azure-identity`
  - `[test]`: `pytest`, `pytest-cov`
  - `[static-code-qa]`: linting/formatting tools
  - `[dev]`: All optional dependencies combined

## Code Quality Configuration

- **Line length**: 119 characters (black, flake8, isort)
- **Formatter**: black
- **Import sorting**: isort with VERTICAL_HANGING_INDENT profile
- **Linter**: pylint, flake8
- **Test coverage**: Minimum 0% (configured but not enforced)
- **Pre-commit hooks**: Includes trailing whitespace, end-of-file-fixer, merge conflict detection, large file checks, and more

## Important Notes

- The package is named `deltashare_api` but the module is `dbrx_api` - be aware of this mismatch when importing
- The API docs are served at the root URL (`/`) for easy access
- Version is read from `version.txt` file dynamically
- Pre-commit hook prevents direct commits to `main` branch (skipped in CI with `SKIP=no-commit-to-branch`)
