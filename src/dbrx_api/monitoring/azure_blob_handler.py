"""Azure Blob Storage handler for loguru."""
import json
from datetime import timezone
from typing import Any

from loguru import logger

try:
    from azure.identity import DefaultAzureCredential
    from azure.storage.blob import BlobServiceClient

    AZURE_SDK_AVAILABLE = True
except ImportError:
    logger.warning("Azure SDK not installed - blob logging will be disabled")
    DefaultAzureCredential = None  # type: ignore
    BlobServiceClient = None  # type: ignore
    AZURE_SDK_AVAILABLE = False


class AzureBlobLogHandler:
    """Handler to send logs to Azure Blob Storage."""

    def __init__(
        self,
        storage_account_url: str,
        container_name: str = "deltashare-logs",
        use_managed_identity: bool = True,
    ):
        """
        Initialize Azure Blob Storage handler.

        Args:
            storage_account_url: Azure Storage Account URL (e.g., https://<account>.blob.core.windows.net)
            container_name: Container name for logs (default: deltashare-logs)
            use_managed_identity: Use managed identity for authentication (default: True)
        """
        self.storage_account_url = storage_account_url
        self.container_name = container_name
        self.use_managed_identity = use_managed_identity
        self.blob_service_client = None
        self.container_client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize Azure Blob Storage client."""
        if not AZURE_SDK_AVAILABLE:
            logger.warning("Azure SDK not available - skipping blob storage initialization")
            self.blob_service_client = None
            self.container_client = None
            return

        try:
            if self.use_managed_identity:
                credential = DefaultAzureCredential()  # type: ignore
                self.blob_service_client = BlobServiceClient(  # type: ignore
                    account_url=self.storage_account_url, credential=credential
                )
            else:
                # No credential - anonymous access or SAS token in URL
                self.blob_service_client = BlobServiceClient(account_url=self.storage_account_url)  # type: ignore

            # Get or create container
            self.container_client = self.blob_service_client.get_container_client(self.container_name)
            if not self.container_client.exists():
                self.container_client.create_container()
                logger.info(f"Created blob container: {self.container_name}")

        except Exception as e:
            logger.error(f"Failed to initialize Azure Blob Storage client: {e}")
            self.blob_service_client = None
            self.container_client = None

    def sink(self, message: Any) -> None:
        """
        Loguru sink function to write logs to Azure Blob Storage.

        Args:
            message: Log message from loguru
        """
        if not self.blob_service_client:
            # Silently skip if client not initialized
            return

        try:
            # Parse the log record
            record = message.record
            timestamp = record["time"].astimezone(timezone.utc)

            # Create blob name with date partitioning: YYYY/MM/DD/HH/logs_YYYYMMDD_HHmmss_uuid.json
            blob_name = (
                f"{timestamp.year:04d}/"
                f"{timestamp.month:02d}/"
                f"{timestamp.day:02d}/"
                f"{timestamp.hour:02d}/"
                f"log_{timestamp.strftime('%Y%m%d_%H%M%S_%f')}.json"
            )

            # Prepare log entry
            # Handle both real loguru records and test mocks
            level = record["level"]["name"] if isinstance(record["level"], dict) else record["level"].name
            log_entry = {
                "timestamp": timestamp.isoformat(),
                "level": level,
                "logger": record["name"],
                "function": record["function"],
                "line": record["line"],
                "message": record["message"],
                "extra": record["extra"],
            }

            # Add exception info if present
            if record["exception"]:
                log_entry["exception"] = {
                    "type": str(record["exception"].type),
                    "value": str(record["exception"].value),
                    "traceback": record["exception"].traceback,
                }

            # Upload to blob storage
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=blob_name)
            blob_client.upload_blob(
                json.dumps(log_entry, default=str, indent=2), overwrite=False, content_type="application/json"
            )

        except Exception as e:
            # Don't let logging errors crash the app
            # Log to stderr but don't recurse
            print(f"Error writing log to Azure Blob Storage: {e}", flush=True)

    def __call__(self, message: Any) -> None:
        """Allow handler to be called directly."""
        self.sink(message)
