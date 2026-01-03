"""Fixtures for FastAPI application and settings."""

import sys
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

# Ensure tests can import from parent directory
THIS_DIR = Path(__file__).parent
TESTS_DIR = THIS_DIR.parent
TESTS_DIR_PARENT = (TESTS_DIR / "..").resolve()
sys.path.insert(0, str(TESTS_DIR_PARENT))


@pytest.fixture
def mock_settings():
    """Mock Settings object with test configuration."""
    from dbrx_api.settings import Settings

    with patch.dict(
        "os.environ",
        {
            "DLTSHR_WORKSPACE_URL": "https://test-workspace.azuredatabricks.net/",
            "CLIENT_ID": "test-client-id",
            "CLIENT_SECRET": "test-client-secret",
            "ACCOUNT_ID": "test-account-id",
            "ENABLE_BLOB_LOGGING": "false",
            "ENABLE_POSTGRESQL_LOGGING": "false",
        },
    ):
        settings = Settings()
        yield settings


@pytest.fixture
def mock_get_auth_token():
    """Mock get_auth_token function that returns a test token."""
    test_token = "test-databricks-token"
    test_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
    return (test_token, test_expiry)


@pytest.fixture
def app(mock_settings):
    """Create FastAPI test application with mocked settings."""
    from dbrx_api.main import create_app

    # Create app with mocked settings
    app = create_app(settings=mock_settings)
    yield app


@pytest.fixture
def client(app):
    """Create FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client
