"""PostgreSQL handler for loguru - stores critical logs in database."""
import json
from datetime import timezone
from typing import (
    Any,
    Optional,
)

from loguru import logger

try:
    import asyncpg
    from asyncpg import Pool

    ASYNCPG_AVAILABLE = True
except ImportError:
    logger.warning("asyncpg not installed - PostgreSQL logging will be disabled")
    asyncpg = None  # type: ignore
    Pool = None  # type: ignore
    ASYNCPG_AVAILABLE = False


class PostgreSQLLogHandler:
    """Handler to send critical logs to PostgreSQL database."""

    def __init__(
        self,
        connection_string: str,
        table_name: str = "application_logs",
        min_level: str = "WARNING",
    ):
        """
        Initialize PostgreSQL handler.

        Args:
            connection_string: PostgreSQL connection string
            table_name: Table name for logs (default: application_logs)
            min_level: Minimum log level to store (default: WARNING)
        """
        self.connection_string = connection_string
        self.table_name = table_name
        self.min_level = min_level
        self.pool: Optional[Pool] = None
        self._level_priority = {
            "TRACE": 0,
            "DEBUG": 1,
            "INFO": 2,
            "SUCCESS": 3,
            "WARNING": 4,
            "ERROR": 5,
            "CRITICAL": 6,
        }
        self._min_priority = self._level_priority.get(min_level, 4)

    async def _ensure_pool(self) -> None:
        """Ensure asyncpg connection pool is initialized."""
        if not ASYNCPG_AVAILABLE:
            logger.warning("asyncpg not available - PostgreSQL logging disabled")
            return

        try:
            self.pool = await asyncpg.create_pool(self.connection_string, min_size=2, max_size=10, command_timeout=60)  # type: ignore
            logger.info("PostgreSQL logging pool initialized")

            # Create table if it doesn't exist
            await self._create_table_if_not_exists()

        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL logging pool: {e}")
            self.pool = None

    async def initialize_pool(self) -> None:
        """Initialize asyncpg connection pool (alias for _ensure_pool)."""
        await self._ensure_pool()

    async def _create_table_if_not_exists(self) -> None:
        """Create logs table if it doesn't exist."""
        if not self.pool:
            return

        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.table_name} (
            id BIGSERIAL PRIMARY KEY,
            timestamp TIMESTAMPTZ NOT NULL,
            level VARCHAR(20) NOT NULL,
            logger_name VARCHAR(255),
            function_name VARCHAR(255),
            line_number INTEGER,
            message TEXT NOT NULL,
            extra_data JSONB,
            exception_type VARCHAR(255),
            exception_value TEXT,
            exception_traceback TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );

        -- Create indexes for common queries
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_timestamp ON {self.table_name}(timestamp DESC);
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_level ON {self.table_name}(level);
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_created_at ON {self.table_name}(created_at DESC);
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_extra_data ON {self.table_name} USING GIN(extra_data);
        """

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(create_table_sql)
            logger.info(f"Application logs table '{self.table_name}' ready")
        except Exception as e:
            logger.error(f"Failed to create logs table: {e}")

    def sink(self, message: Any) -> None:
        """
        Loguru sink function to write logs to PostgreSQL.

        Note: This is a synchronous wrapper - actual DB write happens async in background.

        Args:
            message: Log message from loguru
        """
        if not self.pool:
            return

        try:
            record = message.record

            # Check if log level meets minimum threshold
            # Handle both real loguru records and test mocks
            level_name = record["level"]["name"] if isinstance(record["level"], dict) else record["level"].name
            level_priority = self._level_priority.get(level_name, 0)
            if level_priority < self._min_priority:
                return

            timestamp = record["time"].astimezone(timezone.utc)

            # Prepare log data
            log_data = {
                "timestamp": timestamp,
                "level": level_name,
                "logger_name": record["name"],
                "function_name": record["function"],
                "line_number": record["line"],
                "message": record["message"],
                "extra_data": json.dumps(record["extra"], default=str) if record["extra"] else None,
                "exception_type": None,
                "exception_value": None,
                "exception_traceback": None,
            }

            # Add exception info if present
            if record["exception"]:
                log_data["exception_type"] = str(record["exception"].type.__name__)
                log_data["exception_value"] = str(record["exception"].value)
                # Store formatted traceback
                import traceback as tb

                log_data["exception_traceback"] = "".join(
                    tb.format_exception(
                        record["exception"].type, record["exception"].value, record["exception"].traceback
                    )
                )

            # Schedule async insert (fire and forget)
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, schedule the task
                    asyncio.create_task(self._insert_log(log_data))
                else:
                    # If no loop, run in new loop (fallback)
                    asyncio.run(self._insert_log(log_data))
            except RuntimeError:
                # No event loop - skip database logging
                pass

        except Exception as e:
            # Don't let logging errors crash the app
            print(f"Error writing log to PostgreSQL: {e}", flush=True)

    async def _insert_log(self, log_data: dict) -> None:
        """
        Insert log entry into PostgreSQL.

        Args:
            log_data: Dictionary containing log data
        """
        if not self.pool:
            return

        insert_sql = f"""
        INSERT INTO {self.table_name} (
            timestamp, level, logger_name, function_name, line_number,
            message, extra_data, exception_type, exception_value, exception_traceback
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """

        try:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    insert_sql,
                    log_data["timestamp"],
                    log_data["level"],
                    log_data["logger_name"],
                    log_data["function_name"],
                    log_data["line_number"],
                    log_data["message"],
                    log_data["extra_data"],
                    log_data["exception_type"],
                    log_data["exception_value"],
                    log_data["exception_traceback"],
                )
        except Exception as e:
            print(f"Failed to insert log into PostgreSQL: {e}", flush=True)

    async def close(self) -> None:
        """Close the connection pool."""
        if self.pool:
            await self.pool.close()
            logger.info("PostgreSQL logging pool closed")

    def __call__(self, message: Any) -> None:
        """Allow handler to be called directly."""
        self.sink(message)
