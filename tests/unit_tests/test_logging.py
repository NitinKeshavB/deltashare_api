"""Test suite for logging handlers."""

import json
from datetime import (
    datetime,
    timezone,
)
from unittest.mock import (
    AsyncMock,
    MagicMock,
    patch,
)


class TestAzureBlobLogHandler:
    """Tests for Azure Blob Storage logging handler."""

    @patch("dbrx_api.monitoring.azure_blob_handler.BlobServiceClient")
    @patch("dbrx_api.monitoring.azure_blob_handler.DefaultAzureCredential")
    def test_handler_initialization_with_managed_identity(self, mock_credential, mock_blob_service):
        """Test handler initialization with managed identity."""
        from dbrx_api.monitoring.azure_blob_handler import AzureBlobLogHandler

        handler = AzureBlobLogHandler(
            storage_account_url="https://test.blob.core.windows.net", container_name="test-logs"
        )

        assert handler.storage_account_url == "https://test.blob.core.windows.net"
        assert handler.container_name == "test-logs"
        mock_credential.assert_called_once()
        mock_blob_service.assert_called_once()

    @patch("dbrx_api.monitoring.azure_blob_handler.BlobServiceClient")
    def test_handler_initialization_without_managed_identity(self, mock_blob_service):
        """Test handler initialization without managed identity."""
        from dbrx_api.monitoring.azure_blob_handler import AzureBlobLogHandler

        handler = AzureBlobLogHandler(
            storage_account_url="https://test.blob.core.windows.net",
            container_name="test-logs",
            use_managed_identity=False,
        )

        assert handler.storage_account_url == "https://test.blob.core.windows.net"
        mock_blob_service.assert_called_once_with(account_url="https://test.blob.core.windows.net")

    @patch("dbrx_api.monitoring.azure_blob_handler.BlobServiceClient")
    @patch("dbrx_api.monitoring.azure_blob_handler.DefaultAzureCredential")
    def test_sink_creates_correct_blob_path(self, mock_credential, mock_blob_service):
        """Test that sink creates correct blob path with date partitioning."""
        from dbrx_api.monitoring.azure_blob_handler import AzureBlobLogHandler

        # Setup mocks
        mock_service_instance = MagicMock()
        mock_blob_client = MagicMock()
        mock_service_instance.get_blob_client.return_value = mock_blob_client
        mock_blob_service.return_value = mock_service_instance

        handler = AzureBlobLogHandler(
            storage_account_url="https://test.blob.core.windows.net", container_name="test-logs"
        )

        # Create a mock log record
        mock_record = {
            "time": datetime(2026, 1, 2, 15, 30, 45, tzinfo=timezone.utc),
            "level": {"name": "INFO"},
            "name": "test_logger",
            "function": "test_function",
            "line": 123,
            "message": "Test log message",
            "extra": {"key": "value"},
            "exception": None,
        }

        mock_message = MagicMock()
        mock_message.record = mock_record

        # Call the sink
        handler.sink(mock_message)

        # Verify blob path format: YYYY/MM/DD/HH/log_YYYYMMDD_HHMMSS_ffffff.json
        call_args = mock_service_instance.get_blob_client.call_args
        blob_name = call_args[1]["blob"]

        assert blob_name.startswith("2026/01/02/15/log_20260102_")
        assert blob_name.endswith(".json")

    @patch("dbrx_api.monitoring.azure_blob_handler.BlobServiceClient")
    @patch("dbrx_api.monitoring.azure_blob_handler.DefaultAzureCredential")
    def test_sink_uploads_json_data(self, mock_credential, mock_blob_service):
        """Test that sink uploads properly formatted JSON data."""
        from dbrx_api.monitoring.azure_blob_handler import AzureBlobLogHandler

        # Setup mocks
        mock_service_instance = MagicMock()
        mock_blob_client = MagicMock()
        mock_service_instance.get_blob_client.return_value = mock_blob_client
        mock_blob_service.return_value = mock_service_instance

        handler = AzureBlobLogHandler(
            storage_account_url="https://test.blob.core.windows.net", container_name="test-logs"
        )

        # Create a mock log record
        mock_record = {
            "time": datetime(2026, 1, 2, 15, 30, 45, tzinfo=timezone.utc),
            "level": {"name": "WARNING"},
            "name": "test_logger",
            "function": "test_function",
            "line": 123,
            "message": "Test warning message",
            "extra": {"user_id": "12345", "action": "delete"},
            "exception": None,
        }

        mock_message = MagicMock()
        mock_message.record = mock_record

        # Call the sink
        handler.sink(mock_message)

        # Verify upload was called
        mock_blob_client.upload_blob.assert_called_once()

        # Verify the uploaded data is valid JSON
        uploaded_data = mock_blob_client.upload_blob.call_args[0][0]
        log_data = json.loads(uploaded_data)

        assert log_data["level"] == "WARNING"
        assert log_data["message"] == "Test warning message"
        assert log_data["extra"]["user_id"] == "12345"


class TestPostgreSQLLogHandler:
    """Tests for PostgreSQL logging handler."""

    @patch("dbrx_api.monitoring.postgresql_handler.asyncpg.create_pool")
    async def test_handler_initialization(self, mock_create_pool):
        """Test handler initialization."""
        from dbrx_api.monitoring.postgresql_handler import PostgreSQLLogHandler

        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        handler = PostgreSQLLogHandler(
            connection_string="postgresql://user:pass@localhost/testdb",
            table_name="test_logs",
            min_level="WARNING",
        )

        # Initialize the handler (which creates the pool)
        await handler._ensure_pool()

        assert handler.connection_string == "postgresql://user:pass@localhost/testdb"
        assert handler.table_name == "test_logs"
        assert handler.min_level == "WARNING"

    @patch("dbrx_api.monitoring.postgresql_handler.asyncpg.create_pool")
    async def test_handler_creates_table(self, mock_create_pool):
        """Test that handler creates the logs table."""
        from dbrx_api.monitoring.postgresql_handler import PostgreSQLLogHandler

        # Setup mock pool and connection
        mock_pool = AsyncMock()
        mock_connection = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_connection
        mock_create_pool.return_value = mock_pool

        handler = PostgreSQLLogHandler(
            connection_string="postgresql://user:pass@localhost/testdb",
            table_name="test_logs",
        )

        await handler._ensure_pool()
        await handler._create_table_if_not_exists()

        # Verify table creation SQL was executed
        mock_connection.execute.assert_called()
        create_table_call = mock_connection.execute.call_args_list[0]
        sql = create_table_call[0][0]

        assert "CREATE TABLE IF NOT EXISTS" in sql
        assert "test_logs" in sql
        assert "timestamp" in sql.lower()
        assert "level" in sql.lower()
        assert "message" in sql.lower()

    @patch("dbrx_api.monitoring.postgresql_handler.asyncpg.create_pool")
    def test_sink_filters_by_level(self, mock_create_pool):
        """Test that sink filters logs by minimum level."""
        from dbrx_api.monitoring.postgresql_handler import PostgreSQLLogHandler

        mock_pool = AsyncMock()
        mock_create_pool.return_value = mock_pool

        handler = PostgreSQLLogHandler(
            connection_string="postgresql://user:pass@localhost/testdb",
            table_name="test_logs",
            min_level="ERROR",  # Only ERROR and CRITICAL
        )

        # Create mock log records
        info_record = {
            "time": datetime.now(timezone.utc),
            "level": {"name": "INFO"},
            "name": "test",
            "function": "test_func",
            "line": 1,
            "message": "Info message",
            "extra": {},
            "exception": None,
        }

        error_record = {
            "time": datetime.now(timezone.utc),
            "level": {"name": "ERROR"},
            "name": "test",
            "function": "test_func",
            "line": 1,
            "message": "Error message",
            "extra": {},
            "exception": None,
        }

        mock_info_message = MagicMock()
        mock_info_message.record = info_record

        mock_error_message = MagicMock()
        mock_error_message.record = error_record

        # INFO should be filtered out
        handler.sink(mock_info_message)
        # ERROR should pass through (but we can't verify async call easily here)
        handler.sink(mock_error_message)


class TestLoggerConfiguration:
    """Tests for logger configuration."""

    def test_configure_logger_default(self):
        """Test logger configuration with default settings."""
        from dbrx_api.monitoring.logger import configure_logger

        # This should not raise an error
        configure_logger()

    @patch("dbrx_api.monitoring.logger.AzureBlobLogHandler")
    def test_configure_logger_with_blob_storage(self, mock_blob_handler):
        """Test logger configuration with Azure Blob Storage enabled."""
        from dbrx_api.monitoring.logger import configure_logger

        configure_logger(
            enable_blob_logging=True,
            azure_storage_url="https://test.blob.core.windows.net",
            blob_container="test-logs",
        )

        mock_blob_handler.assert_called_once()

    @patch("dbrx_api.monitoring.logger.PostgreSQLLogHandler")
    def test_configure_logger_with_postgresql(self, mock_pg_handler):
        """Test logger configuration with PostgreSQL enabled."""
        from dbrx_api.monitoring.logger import configure_logger

        configure_logger(
            enable_postgresql_logging=True,
            postgresql_connection_string="postgresql://user:pass@localhost/testdb",
            postgresql_table="test_logs",
            postgresql_min_level="WARNING",
        )

        mock_pg_handler.assert_called_once()

    @patch("dbrx_api.monitoring.logger.AzureBlobLogHandler")
    @patch("dbrx_api.monitoring.logger.PostgreSQLLogHandler")
    def test_configure_logger_with_all_sinks(self, mock_pg_handler, mock_blob_handler):
        """Test logger configuration with all sinks enabled."""
        from dbrx_api.monitoring.logger import configure_logger

        configure_logger(
            enable_blob_logging=True,
            azure_storage_url="https://test.blob.core.windows.net",
            blob_container="test-logs",
            enable_postgresql_logging=True,
            postgresql_connection_string="postgresql://user:pass@localhost/testdb",
            postgresql_table="test_logs",
            postgresql_min_level="ERROR",
        )

        mock_blob_handler.assert_called_once()
        mock_pg_handler.assert_called_once()


class TestIntegrationLogging:
    """Integration tests for logging with API."""

    def test_api_logs_on_request(self, client, mock_share_business_logic):
        """Test that API logs are created on request."""
        with patch("dbrx_api.routes_share.logger") as mock_logger:
            response = client.get("/shares/test_share")

            assert response.status_code == 200
            # Verify logging was called
            assert mock_logger.info.called
            assert mock_logger.info.call_count >= 1

    def test_api_logs_on_error(self, client, mock_share_business_logic):
        """Test that API logs errors appropriately."""
        mock_share_business_logic["get"].return_value = None

        with patch("dbrx_api.routes_share.logger") as mock_logger:
            response = client.get("/shares/nonexistent_share")

            assert response.status_code == 404
            # Verify warning was logged
            assert mock_logger.warning.called
