# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Python FastAPI application for the Databricks Delta Share API. The project enables data engineering teams to share Databricks assets (tables, views, streaming tables, materialized views, and notebooks) with clients both internal and external to the enterprise through REST API endpoints.

**Package name:** `deltashare_api`
**Module name:** `dbrx_api` (note the discrepancy - be aware when importing)
**Python version:** 3.12+

### Core Domain Concepts

- **Share**: A named collection of Databricks data objects (tables, views, schemas) that can be shared with recipients
- **Recipient**: An entity (internal or external) that receives access to shared data
  - **D2D (Databricks-to-Databricks)**: Recipients with Databricks infrastructure using DATABRICKS authentication
  - **D2O (Databricks-to-Open)**: Recipients without Databricks using TOKEN authentication
- **Data Objects**: Tables, views, streaming tables, materialized views that can be added to shares

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

- **Authentication**: Each business logic function obtains a session token via `get_auth_token(datetime.now(timezone.utc))[0]` and creates a `WorkspaceClient`. Tokens are cached in memory with 5-minute refresh buffer before expiry.
- **Router Registration**: Two routers (`ROUTER_SHARE`, `ROUTER_RECIPIENT`) are registered in `main.py`
- **Error Handling**:
  - Global middleware catches broad exceptions
  - Custom handler for Pydantic validation errors
  - Service layer returns `ShareInfo | str` or `RecipientInfo | str` - string indicates error
  - Routes map error strings to appropriate HTTP status codes (409 for conflicts, 403 for permissions, 404 for not found, 400 for bad requests)
- **OpenAPI Customization**: Custom `operationId` generator creates prettier function names for generated SDKs
- **Response Field Naming**: Use PascalCase for API response fields (`Message`, `Share`, `Recipient`), snake_case for request bodies and internal fields

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

## Databricks SDK Usage Patterns

### WorkspaceClient Creation
```python
from databricks.sdk import WorkspaceClient
from dbrx_api.dbrx_auth.token_gen import get_auth_token
from datetime import datetime, timezone

session_token = get_auth_token(datetime.now(timezone.utc))[0]
w_client = WorkspaceClient(host=dltshr_workspace_url, token=session_token)
```

### Available SDK Operations
- **Shares**: `w_client.shares.create()`, `get()`, `list_shares()`, `update()`, `delete()`, `share_permissions()`, `update_permissions()`
- **Recipients**: `w_client.recipients.create()`, `get()`, `list()`, `update()`, `delete()`, `rotate_token()`

### Data Object Management
Use `SharedDataObject` and `SharedDataObjectUpdate` with action types:
- `SharedDataObjectUpdateAction.ADD` - Add objects to share
- `SharedDataObjectUpdateAction.REMOVE` - Remove objects from share
- `SharedDataObjectUpdateAction.UPDATE` - Update object properties

Object types: `TABLE`, `VIEW`, `SCHEMA` (from `SharedDataObjectDataObjectType`)

### Recipient Type Differences
- **D2D recipients**: Use `AuthenticationType.DATABRICKS`, require `data_recipient_global_metastore_id` (format: `cloud:region:uuid`), do NOT support IP access lists
- **D2O recipients**: Use `AuthenticationType.TOKEN`, return activation URL and tokens, support `IpAccessList` with `allowed_ip_addresses`

## Route Naming Conventions

| HTTP Method | Route Pattern | Function Name |
|-------------|---------------|---------------|
| GET | `/shares` | `list_shares_all` |
| GET | `/shares/{share_name}` | `get_shares_by_name` |
| POST | `/shares/{share_name}` | `create_share` |
| PUT | `/shares/{share_name}/...` | `update_share_...` |
| DELETE | `/shares/{share_name}` | `delete_share_by_name` |

## Important Notes

- The package is named `deltashare_api` but the module is `dbrx_api` - be aware of this mismatch when importing
- The API docs are served at the root URL (`/`) for easy access
- Version is read from `version.txt` file dynamically
- Pre-commit hook prevents direct commits to `main` branch (skipped in CI with `SKIP=no-commit-to-branch`)
- Environment-specific configuration via `.env` files (not committed) or Azure App Configuration
- Required environment variables for authentication: `CLIENT_ID`, `CLIENT_SECRET`, `ACCOUNT_ID`, `dltshr_workspace_url`
