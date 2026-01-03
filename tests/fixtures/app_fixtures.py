"""Fixtures for FastAPI application and settings."""

import sys
from datetime import (
    datetime,
    timedelta,
    timezone,
)
from pathlib import Path
from unittest.mock import (
    MagicMock,
    patch,
)

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
def mock_token_manager():
    """Mock TokenManager that returns a test token."""
    from dbrx_api.dbrx_auth.token_manager import TokenManager

    # Create a mock token manager
    mock_manager = MagicMock(spec=TokenManager)

    # Configure the mock to return a test token
    test_token = "test-databricks-token"
    test_expiry = datetime.now(timezone.utc) + timedelta(hours=1)

    mock_manager.get_token.return_value = (test_token, test_expiry)
    mock_manager.is_token_valid.return_value = True
    mock_manager.cached_token = test_token
    mock_manager.cached_expiry = test_expiry

    return mock_manager


@pytest.fixture
def app(mock_settings, mock_token_manager):
    """Create FastAPI test application with mocked settings and token manager."""
    from dbrx_api.main import create_app

    # Create app with mocked settings
    # We need to patch TokenManager creation to use our mock
    with patch("dbrx_api.main.TokenManager", return_value=mock_token_manager):
        app = create_app(settings=mock_settings)
        yield app


@pytest.fixture
def client(app):
    """Create FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client
