"""
Dependencies with Lifecycle Management
Database, cache, and HTTP client with initialization and cleanup hooks
"""

from typing import Optional, Any, Dict
import logging
import httpx
from config import Settings

logger = logging.getLogger(__name__)


class DatabaseClient:
    """
    Database client with lifecycle management.

    Manages connection pool initialization and cleanup.
    In production, use SQLAlchemy or asyncpg.
    """

    def __init__(self, settings: Settings):
        """
        Initialize database client.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.pool = None
        self._closed = False
        self._initialized = False
        logger.debug(f"DatabaseClient created (not yet initialized)")

    async def initialize(self):
        """
        Initialize database connection pool.

        Creates pool with configured size and timeout.
        """
        if self._initialized:
            logger.warning("DatabaseClient already initialized")
            return

        logger.info(
            f"Initializing database pool: "
            f"url={self.settings.database_url[:20]}..., "
            f"pool_size={self.settings.database_pool_size}"
        )

        try:
            # Simulate connection pool creation
            # In production: await create_async_engine(...)
            self.pool = {
                "url": self.settings.database_url,
                "size": self.settings.database_pool_size,
                "timeout": self.settings.database_timeout,
                "max_overflow": self.settings.database_max_overflow,
                "connections": [],
                "active_connections": 0,
            }

            # Mark the client as initialized BEFORE running the connection
            # probe — query() guards on self._initialized and would raise
            # RuntimeError("Database client not initialized") if we ran the
            # probe first. Set the flag here, then run the probe; if the
            # probe fails, the except branch below logs and re-raises.
            self._initialized = True

            # Test connection
            await self.query("SELECT 1")

            logger.info("Database pool initialized successfully")

        except Exception as e:
            # Roll back the initialized flag if the probe failed so callers
            # don't see a half-initialized client.
            self._initialized = False
            logger.error(f"Failed to initialize database: {e}")
            raise

    async def query(self, sql: str, params: Dict[str, Any] = None) -> list:
        """
        Execute database query.

        Args:
            sql: SQL query string
            params: Query parameters

        Returns:
            List of query results

        Raises:
            RuntimeError: If client is closed
        """
        if self._closed:
            raise RuntimeError("Database client is closed")

        if not self._initialized:
            raise RuntimeError("Database client not initialized")

        logger.debug(f"Executing query: {sql[:100]}...")

        # Simulate query execution
        # In production: async with self.pool.connect() as conn: ...
        self.pool["active_connections"] += 1
        try:
            result = [{"id": 1, "data": "sample result"}]
            return result
        finally:
            self.pool["active_connections"] -= 1

    async def execute(self, sql: str, params: Dict[str, Any] = None) -> int:
        """
        Execute database command (INSERT, UPDATE, DELETE).

        Args:
            sql: SQL command
            params: Command parameters

        Returns:
            Number of affected rows

        Raises:
            RuntimeError: If client is closed
        """
        if self._closed:
            raise RuntimeError("Database client is closed")

        logger.debug(f"Executing command: {sql[:100]}...")

        # Simulate command execution
        return 1

    def get_stats(self) -> Dict[str, Any]:
        """
        Get database pool statistics.

        Returns:
            Dictionary with pool stats
        """
        if not self.pool:
            return {"status": "not_initialized"}

        return {
            "status": "initialized",
            "pool_size": self.pool["size"],
            "active_connections": self.pool["active_connections"],
            "max_overflow": self.pool["max_overflow"],
        }

    async def close(self):
        """
        Close database connections.

        Closes all connections in pool and releases resources.
        """
        if self._closed:
            logger.debug("DatabaseClient already closed")
            return

        logger.info("Closing database pool...")

        try:
            if self.pool:
                # Wait for active connections to finish
                active = self.pool.get("active_connections", 0)
                if active > 0:
                    logger.warning(f"Closing with {active} active connections")

                # Close all connections
                self.pool["connections"].clear()
                self.pool = None

            self._closed = True
            self._initialized = False
            logger.info("Database pool closed successfully")

        except Exception as e:
            logger.error(f"Error closing database: {e}")
            raise


class CacheClient:
    """
    Redis cache client with lifecycle management.

    Manages cache connection and provides get/set operations.
    In production, use redis-py or aioredis.
    """

    def __init__(self, settings: Settings):
        """
        Initialize cache client.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.connection = None
        self._cache: Dict[str, Any] = {}  # Simulated cache storage
        self._closed = False
        self._initialized = False
        logger.debug("CacheClient created (not yet initialized)")

    async def initialize(self):
        """
        Initialize cache connection.

        Connects to Redis server (simulated in this implementation).
        """
        if self._initialized:
            logger.warning("CacheClient already initialized")
            return

        logger.info(
            f"Connecting to Redis: "
            f"{self.settings.redis_host}:{self.settings.redis_port}/{self.settings.redis_db}"
        )

        try:
            # Simulate Redis connection
            # In production: await redis.from_url(...)
            self.connection = {
                "host": self.settings.redis_host,
                "port": self.settings.redis_port,
                "db": self.settings.redis_db,
                "password": self.settings.redis_password,
            }

            # Test connection
            await self.set("_health_check_", "ok", ttl=10)
            health = await self.get("_health_check_")
            if health != "ok":
                raise RuntimeError("Cache health check failed")

            self._initialized = True
            logger.info("Redis connection established")

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found

        Raises:
            RuntimeError: If client is closed
        """
        if self._closed:
            raise RuntimeError("Cache client is closed")

        value = self._cache.get(key)
        logger.debug(f"Cache {'HIT' if value else 'MISS'}: {key}")
        return value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if not specified)

        Raises:
            RuntimeError: If client is closed
        """
        if self._closed:
            raise RuntimeError("Cache client is closed")

        self._cache[key] = value
        ttl_to_use = ttl or self.settings.redis_ttl
        logger.debug(f"Cache SET: {key} (ttl={ttl_to_use}s)")

    async def delete(self, key: str):
        """Delete key from cache."""
        if key in self._cache:
            del self._cache[key]
            logger.debug(f"Cache DELETE: {key}")

    async def flush(self):
        """
        Flush pending writes to cache.

        In production, this would ensure all writes are persisted.
        """
        if not self._initialized:
            return

        logger.info(f"Flushing cache... ({len(self._cache)} entries)")
        # Simulate flush operation
        logger.debug(f"Flushed {len(self._cache)} cache entries")

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        return {
            "status": "initialized" if self._initialized else "not_initialized",
            "entries": len(self._cache),
            "ttl": self.settings.redis_ttl,
        }

    async def close(self):
        """
        Close cache connection.

        Flushes pending writes and closes connection.
        """
        if self._closed:
            logger.debug("CacheClient already closed")
            return

        logger.info("Closing Redis connection...")

        try:
            # Flush before closing
            await self.flush()

            if self.connection:
                # In production: await self.connection.close()
                self.connection = None

            self._closed = True
            self._initialized = False
            logger.info("Redis connection closed successfully")

        except Exception as e:
            logger.error(f"Error closing cache: {e}")
            raise


class HTTPClient:
    """
    HTTP client with connection pooling.

    Uses httpx for async HTTP requests with connection pooling.
    """

    def __init__(self, settings: Settings):
        """
        Initialize HTTP client.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.client: Optional[httpx.AsyncClient] = None
        self._closed = False
        self._initialized = False
        logger.debug("HTTPClient created (not yet initialized)")

    async def initialize(self):
        """
        Initialize HTTP client with connection pool.

        Creates httpx client with configured timeout and connection limits.
        """
        if self._initialized:
            logger.warning("HTTPClient already initialized")
            return

        logger.info(
            f"Initializing HTTP client: "
            f"timeout={self.settings.http_timeout}s, "
            f"max_connections={self.settings.http_max_connections}"
        )

        try:
            self.client = httpx.AsyncClient(
                timeout=self.settings.http_timeout,
                limits=httpx.Limits(
                    max_connections=self.settings.http_max_connections,
                    max_keepalive_connections=self.settings.http_max_keepalive,
                ),
                http2=True,  # Enable HTTP/2
            )

            self._initialized = True
            logger.info("HTTP client initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize HTTP client: {e}")
            raise

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """
        Make GET request.

        Args:
            url: Request URL
            **kwargs: Additional request parameters

        Returns:
            HTTP response

        Raises:
            RuntimeError: If client is closed
        """
        if self._closed:
            raise RuntimeError("HTTP client is closed")

        if not self._initialized:
            raise RuntimeError("HTTP client not initialized")

        logger.debug(f"GET {url}")
        return await self.client.get(url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        """
        Make POST request.

        Args:
            url: Request URL
            **kwargs: Additional request parameters

        Returns:
            HTTP response

        Raises:
            RuntimeError: If client is closed
        """
        if self._closed:
            raise RuntimeError("HTTP client is closed")

        logger.debug(f"POST {url}")
        return await self.client.post(url, **kwargs)

    def get_stats(self) -> Dict[str, Any]:
        """
        Get HTTP client statistics.

        Returns:
            Dictionary with client stats
        """
        return {
            "status": "initialized" if self._initialized else "not_initialized",
            "timeout": self.settings.http_timeout,
            "max_connections": self.settings.http_max_connections,
        }

    async def close(self):
        """
        Close HTTP client.

        Closes all connections and releases resources.
        """
        if self._closed:
            logger.debug("HTTPClient already closed")
            return

        logger.info("Closing HTTP client...")

        try:
            if self.client:
                await self.client.aclose()
                self.client = None

            self._closed = True
            self._initialized = False
            logger.info("HTTP client closed successfully")

        except Exception as e:
            logger.error(f"Error closing HTTP client: {e}")
            raise


# Example usage
async def example_usage():
    """Demonstrate dependency lifecycle."""
    from config import load_config

    settings = load_config()

    # Create dependencies
    database = DatabaseClient(settings)
    cache = CacheClient(settings)
    http = HTTPClient(settings)

    try:
        # Initialize
        await database.initialize()
        await cache.initialize()
        await http.initialize()

        # Use dependencies
        result = await database.query("SELECT * FROM orders")
        print(f"Database result: {result}")

        await cache.set("key", "value")
        cached = await cache.get("key")
        print(f"Cache result: {cached}")

        # Get stats
        print(f"DB stats: {database.get_stats()}")
        print(f"Cache stats: {cache.get_stats()}")
        print(f"HTTP stats: {http.get_stats()}")

    finally:
        # Cleanup
        await http.close()
        await cache.close()
        await database.close()


if __name__ == "__main__":
    import asyncio

    asyncio.run(example_usage())
