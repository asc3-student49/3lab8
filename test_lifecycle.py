"""
Tests with Overridden Dependencies
Demonstrates testing with fake dependencies
"""

import pytest
from unittest.mock import AsyncMock
from lifecycle_manager import LifecycleManager, ManagedDependencies
from config import Settings
from dependencies import DatabaseClient, CacheClient, HTTPClient


class FakeDatabaseClient:
    """Fake database for testing."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.initialized = False
        self.closed = False
        self.queries = []
        self._closed = False
        self._initialized = False

    async def initialize(self):
        """Initialize fake database."""
        self.initialized = True
        self._initialized = True

    async def query(self, sql: str, params: dict = None):
        """Record query and return fake result."""
        self.queries.append((sql, params))
        return [{"id": 1, "test": "data"}]

    async def execute(self, sql: str, params: dict = None):
        """Execute fake command."""
        self.queries.append((sql, params))
        return 1

    def get_stats(self):
        """Get fake stats."""
        return {"status": "initialized", "queries": len(self.queries)}

    async def close(self):
        """Close fake database."""
        self.closed = True
        self._closed = True
        self._initialized = False


class FakeCacheClient:
    """Fake cache for testing."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.storage = {}
        self.initialized = False
        self.closed = False
        self._closed = False
        self._initialized = False

    async def initialize(self):
        """Initialize fake cache."""
        self.initialized = True
        self._initialized = True

    async def get(self, key: str):
        """Get from fake cache."""
        return self.storage.get(key)

    async def set(self, key: str, value, ttl: int = None):
        """Set in fake cache."""
        self.storage[key] = value

    async def delete(self, key: str):
        """Delete from fake cache."""
        if key in self.storage:
            del self.storage[key]

    async def flush(self):
        """Flush fake cache."""
        pass

    def get_stats(self):
        """Get fake stats."""
        return {"status": "initialized", "entries": len(self.storage)}

    async def close(self):
        """Close fake cache."""
        self.closed = True
        self._closed = True
        self._initialized = False


class FakeHTTPClient:
    """Fake HTTP client for testing."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.initialized = False
        self.closed = False
        self.requests = []
        self._closed = False
        self._initialized = False

    async def initialize(self):
        """Initialize fake HTTP client."""
        self.initialized = True
        self._initialized = True

    async def get(self, url: str, **kwargs):
        """Fake GET request."""
        self.requests.append(("GET", url))

        # Return mock response
        class MockResponse:
            status_code = 200
            text = '{"result": "fake data"}'

        return MockResponse()

    async def post(self, url: str, **kwargs):
        """Fake POST request."""
        self.requests.append(("POST", url))

        class MockResponse:
            status_code = 201
            text = '{"created": true}'

        return MockResponse()

    def get_stats(self):
        """Get fake stats."""
        return {"status": "initialized", "requests": len(self.requests)}

    async def close(self):
        """Close fake HTTP client."""
        self.closed = True
        self._closed = True
        self._initialized = False


@pytest.fixture
def test_settings():
    """Create test settings.

    Note: ``Settings.environment`` is ``Literal["development", "staging",
    "production"]`` and is ``@field_validator``-guarded — ``"test"`` is not
    in the allowed set and would raise ``ValidationError`` before any
    test body runs. Use ``"development"`` here instead.
    """
    return Settings(
        openai_api_key="test_key_123",
        ai_model="openai:gpt-5.4-mini",
        environment="development",
        debug=True,
        database_url="sqlite:///:memory:",
        redis_host="localhost",
        log_level="DEBUG",
    )


@pytest.mark.asyncio
async def test_lifecycle_initialization(test_settings):
    """Test lifecycle manager initialization."""
    manager = LifecycleManager(test_settings)

    deps = await manager.initialize()

    assert deps is not None
    assert deps.database is not None
    assert deps.cache is not None
    assert deps.http is not None
    assert deps.settings == test_settings

    await manager.shutdown()

    assert not manager._initialized


@pytest.mark.asyncio
async def test_lifecycle_context_manager(test_settings):
    """Test lifecycle context manager."""
    manager = LifecycleManager(test_settings)

    async with manager.lifespan() as deps:
        # Resources available inside context
        assert deps.database is not None
        assert manager.is_initialized()

        # Use dependencies
        result = await deps.database.query("SELECT 1")
        assert result is not None

    # Resources cleaned up after context
    assert not manager.is_initialized()


@pytest.mark.asyncio
async def test_lifecycle_cleanup_on_error(test_settings, monkeypatch):
    """Test cleanup happens even on initialization error."""
    manager = LifecycleManager(test_settings)

    # Make HTTP client initialization fail
    async def failing_init(self):
        raise RuntimeError("Initialization failed")

    monkeypatch.setattr(HTTPClient, "initialize", failing_init)

    with pytest.raises(RuntimeError, match="Initialization failed"):
        await manager.initialize()

    # Verify cleanup attempted
    assert manager.dependencies is None
    assert not manager._initialized


@pytest.mark.asyncio
async def test_with_fake_dependencies(test_settings):
    """Test using fake dependencies."""
    fake_db = FakeDatabaseClient(test_settings)
    fake_cache = FakeCacheClient(test_settings)
    fake_http = FakeHTTPClient(test_settings)

    await fake_db.initialize()
    await fake_cache.initialize()
    await fake_http.initialize()

    # Use fake dependencies
    result = await fake_db.query("SELECT * FROM test")
    assert result == [{"id": 1, "test": "data"}]
    assert len(fake_db.queries) == 1
    assert fake_db.queries[0][0] == "SELECT * FROM test"

    await fake_cache.set("key", "value")
    cached = await fake_cache.get("key")
    assert cached == "value"

    response = await fake_http.get("http://example.com")
    assert response.status_code == 200
    assert len(fake_http.requests) == 1

    # Cleanup
    await fake_db.close()
    await fake_cache.close()
    await fake_http.close()

    assert fake_db.closed
    assert fake_cache.closed
    assert fake_http.closed


@pytest.mark.asyncio
async def test_health_check(test_settings):
    """Test health check functionality."""
    manager = LifecycleManager(test_settings)

    # Health check before initialization
    health = await manager.health_check()
    assert not health["healthy"]
    assert health["status"] == "not_initialized"

    # Initialize and check again
    await manager.initialize()
    health = await manager.health_check()

    assert "checks" in health
    assert "database" in health["checks"]
    assert "cache" in health["checks"]
    assert "http" in health["checks"]

    await manager.shutdown()


@pytest.mark.asyncio
async def test_shutdown_with_errors(test_settings, monkeypatch):
    """Test shutdown continues even with errors."""
    manager = LifecycleManager(test_settings)
    await manager.initialize()

    # Make database close fail
    async def failing_close(self):
        raise RuntimeError("Close failed")

    monkeypatch.setattr(DatabaseClient, "close", failing_close)

    # Shutdown should not raise, just log errors
    await manager.shutdown()

    # Should still be marked as shut down
    assert not manager._initialized


@pytest.mark.asyncio
async def test_double_initialization(test_settings):
    """Test that double initialization is handled gracefully."""
    manager = LifecycleManager(test_settings)

    deps1 = await manager.initialize()
    deps2 = await manager.initialize()  # Should return same deps

    assert deps1 is deps2

    await manager.shutdown()


@pytest.mark.asyncio
async def test_shutdown_before_initialization(test_settings):
    """Test shutdown on uninitialized manager."""
    manager = LifecycleManager(test_settings)

    # Should not raise
    await manager.shutdown()

    assert not manager._initialized


@pytest.mark.asyncio
async def test_dependencies_isolation():
    """Test that different managers have isolated dependencies."""
    settings1 = Settings(openai_api_key="key1", environment="development")
    settings2 = Settings(openai_api_key="key2", environment="development")

    manager1 = LifecycleManager(settings1)
    manager2 = LifecycleManager(settings2)

    deps1 = await manager1.initialize()
    deps2 = await manager2.initialize()

    # Should be separate instances
    assert deps1 is not deps2
    assert deps1.database is not deps2.database
    assert deps1.cache is not deps2.cache

    await manager1.shutdown()
    await manager2.shutdown()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
